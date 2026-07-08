"""``harmonics demo`` — a curated tour of the whole agent voice.

Wires the already-built demo pipeline into a CLI verb: :func:`harmonics.demo.
showcase` renders the curated tour (:mod:`harmonics.demo.matrix`) to a list of
:class:`~harmonics.demo.core.Clip`\\ s, and this module only decides where
those clips GO — played live, written to a gallery/WAVs, or streamed as the
note-sequence-per-clip JSON payload. It makes **no new synthesis decisions**
of its own, mirroring ``harmonics say``'s dispatch shape
(:mod:`harmonics.cli._commands.say`):

* **``--play``** (takes priority over every file flag): plays every clip live
  via :func:`harmonics.demo.play.play_clips` (lazy backend: ``simpleaudio``
  then ``sounddevice``); with neither installed it raises the pipeline's own
  friendly :class:`~harmonics.cli._errors.CliError` — this module lets that
  propagate rather than re-wrapping it into a generic error.
* **File flags** (``--html``/``--wav``/``--out``, any combination, all
  independent of one another): :func:`harmonics.demo.gallery.render_gallery`
  for a self-contained HTML gallery, :func:`harmonics.demo.files.
  write_wav_dir` for one WAV per clip, :func:`harmonics.demo.files.
  write_concat_wav` for the whole tour as one WAV. Each write is wrapped so an
  ``OSError`` (missing parent directory, permission denied, …) becomes a
  structured :class:`CliError` (exit :data:`~harmonics.cli._errors.
  EXIT_ENV_ERROR`) instead of a bare traceback.
* **Neither**: the dry-run default. ``--json`` streams :func:`harmonics.demo.
  files.json_payload` (one note-sequence entry per clip); otherwise a compact
  human listing, one line per clip.

``--articulation`` (default ``None``) is deliberately NOT ``"smooth"``:
``None`` means "render each clip in its OWN curated articulation" (see
:func:`harmonics.demo.core.showcase`'s own doc), so the dedicated
``"articulations"`` tour section still demonstrates all four wav styles side
by side. Passing an explicit style (e.g. ``--articulation alien``) overrides
the WHOLE tour to that one voice. Either way the note sequences themselves
never change — only how they are synthesized to wav — so ``--json``/the
dry-run listing are identical regardless of ``--articulation``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from harmonics.cli._errors import EXIT_ENV_ERROR, CliError
from harmonics.cli._output import emit_result
from harmonics.demo import Clip, showcase
from harmonics.demo.files import json_payload, write_concat_wav, write_wav_dir
from harmonics.demo.gallery import render_gallery
from harmonics.demo.play import play_clips

#: Axis fields shown in the dry-run listing's summary, in the design-spine's
#: canonical order (matches ``harmonics.axes.Axes.as_dict``).
_AXIS_FIELDS: tuple[str, ...] = ("intent", "confidence", "urgency", "state", "identity")


def _raise_write_error(path: str, err: OSError) -> None:
    """Translate an ``OSError`` from a file write into the structured
    :class:`CliError` contract (missing parent dir, permission denied, disk
    full, …) instead of letting it bubble up as an "unexpected" error."""
    raise CliError(
        code=EXIT_ENV_ERROR,
        message=f"could not write {path}: {err}",
        remediation="check the path, permissions, and that the parent directory exists",
    ) from err


def _axes_summary(clip: Clip) -> str:
    """The clip's SET (non-``None``) axes fields as a compact ``k=v`` list,
    for the dry-run listing."""
    fields = clip.axes.as_dict()
    return ", ".join(
        f"{field}={fields[field]}" for field in _AXIS_FIELDS if fields[field] is not None
    )


def _format_text(clips: list[Clip]) -> str:
    """A compact, human-readable listing: one line per clip."""
    if not clips:
        return "(no clips)"
    lines = [f"{clip.label}  [{_axes_summary(clip)}]  {len(clip.notes)} notes" for clip in clips]
    return "\n".join(lines)


def _resolve_device(args: argparse.Namespace) -> str | None:
    """The output device for ``--play``: the ``--device`` flag if given, else
    ``$HARMONICS_AUDIO_DEVICE``, else ``None`` — in which case
    :func:`harmonics.demo.play.play_clips` prefers a resampling sound-server
    device (pipewire/pulse) before falling back to the backend's default."""
    return args.device or os.environ.get("HARMONICS_AUDIO_DEVICE") or None


def _play_live(clips: list[Clip], device: str | None, json_mode: bool) -> None:
    """``--play``: play every clip live. ``play_clips`` raises its own
    ``CliError`` when no backend is installed; that propagates unchanged."""
    play_clips(clips, device=device)
    if json_mode:
        emit_result({"played": len(clips)}, json_mode=True)
    else:
        emit_result(f"played {len(clips)} clip(s)", json_mode=False)


def _write_requested_files(clips: list[Clip], args: argparse.Namespace) -> list[str]:
    """Write whichever of ``--html``/``--wav``/``--out`` were requested — all
    independent of one another (unlike ``--play``, which takes priority and
    returns early); returns the summary strings for the "wrote" line."""
    wrote: list[str] = []
    if args.html:
        try:
            Path(args.html).write_text(render_gallery(clips), encoding="utf-8")
        except OSError as err:
            _raise_write_error(args.html, err)
        wrote.append(args.html)
    if args.wav:
        try:
            paths = write_wav_dir(clips, args.wav)
        except OSError as err:
            _raise_write_error(args.wav, err)
        wrote.append(f"{args.wav} ({len(paths)} files)")
    if args.out:
        try:
            write_concat_wav(clips, args.out)
        except OSError as err:
            _raise_write_error(args.out, err)
        wrote.append(args.out)
    return wrote


def cmd_demo(args: argparse.Namespace) -> int | None:
    json_mode = bool(getattr(args, "json", False))

    clips = showcase(articulation=args.articulation)

    if args.play:
        _play_live(clips, _resolve_device(args), json_mode)
        return None

    wrote = _write_requested_files(clips, args)
    if wrote:
        if json_mode:
            emit_result({"wrote": wrote, "clips": len(clips)}, json_mode=True)
        else:
            emit_result(f"wrote {', '.join(wrote)}", json_mode=False)
        return None

    if json_mode:
        emit_result(json_payload(clips), json_mode=True)
    else:
        emit_result(_format_text(clips), json_mode=False)
    return None


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "demo",
        help=(
            "Tour the whole agent voice: play it, write an HTML gallery / "
            "WAVs, or stream the note sequences (dry-run by default)."
        ),
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit the note-sequence-per-clip payload as JSON.",
    )
    p.add_argument(
        "--html",
        default=None,
        metavar="FILE",
        help="Write a self-contained, browser-playable HTML gallery to FILE.",
    )
    p.add_argument(
        "--wav",
        default=None,
        metavar="DIR",
        help="Write one WAV per clip into DIR.",
    )
    p.add_argument(
        "--out",
        default=None,
        metavar="FILE",
        help="Write one concatenated WAV of the whole tour to FILE.",
    )
    p.add_argument(
        "--play",
        action="store_true",
        help=(
            "Play every clip live (needs the audio extra: "
            "uv tool install 'harmonics-cli[audio]'); else a friendly error."
        ),
    )
    p.add_argument(
        "--device",
        default=None,
        metavar="NAME|INDEX",
        help=(
            "Output device for --play (a name substring or index), e.g. "
            "--device pipewire. Overrides $HARMONICS_AUDIO_DEVICE; the default "
            "prefers a resampling sound-server device (pipewire/pulse)."
        ),
    )
    p.add_argument(
        "--articulation",
        choices=("discrete", "speechy", "smooth", "alien"),
        default=None,
        help=(
            "Re-render the WHOLE tour in this voice; default: each clip's "
            "own (the 'articulations' section already shows all four)."
        ),
    )
    p.set_defaults(func=cmd_demo)

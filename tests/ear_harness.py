"""Reusable offline assertions for note sequences (the "ear harness").

This module is the offline half of the two-part measurement the project's
honesty conditions require for audio claims (see
``docs/ear-test-protocol.md`` for the human half — the blind-listening
protocol). It is a plain, importable helper module, **not** a test module
itself: pytest will not collect it (its name doesn't match ``test_*.py`` /
``*_test.py``), and it defines no ``test_*`` functions. Other test modules
import from it and call its assertions on the sequences they build or
render.

Every helper here operates on the generic :class:`~harmonics.notes.NoteEvent`
model only — it has no dependency on any axes/mapping/contour module, on
purpose: a gesture is "well-formed" or "deterministic" independent of how its
notes were chosen.

Pure stdlib + ``harmonics.notes`` — no third-party imports, so this module
stays importable with no audio device, matching the offline-testable-core
rule in ``CLAUDE.md``.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Callable

from harmonics.notes import NoteEvent

#: MIDI note numbers are a 7-bit value (0-127 inclusive); mirrors
#: harmonics/notes.py's own range so this module doesn't need to import
#: its private constants.
_MIN_PITCH = 0
_MAX_PITCH = 127

#: Velocity is normalized to the unit interval.
_MIN_VELOCITY = 0.0
_MAX_VELOCITY = 1.0

#: Third-party modules known to be part of an audio/sound stack. Matched by
#: top-level module name. This list is a belt-and-suspenders complement to
#: the substring heuristic in :func:`assert_offline_no_audio` below — it
#: catches names (like ``pygame``) that the "audio"/"sound" substring check
#: would otherwise miss.
_KNOWN_AUDIO_MODULES = frozenset(
    {
        "sounddevice",
        "simpleaudio",
        "pyaudio",
        "pygame",
        "playsound",
        "pydub",
        "ossaudiodev",
        "winsound",
        "alsaaudio",
        "pyalsaaudio",
        "rtmidi",
        "mido",
        "miniaudio",
        "soundfile",
        "librosa",
    }
)


def assert_well_formed(seq: list[NoteEvent]) -> None:
    """Assert a note sequence is structurally valid.

    Re-checks every invariant :class:`~harmonics.notes.NoteEvent` normally
    enforces at construction time, independent of that enforcement — a
    sequence handed to this helper may contain events built by means other
    than the validated constructor (e.g. deserialized from an untrusted
    source, or hand-built for a test). Checks, in order:

    * the sequence is non-empty;
    * every event's onset (``start``) is non-negative;
    * every event's ``duration`` is non-negative;
    * every event's ``velocity`` lies in ``[0.0, 1.0]``;
    * every event's ``pitch`` is a MIDI note number in ``[0, 127]``.

    Deliberately does **not** require onsets to be sorted/monotonic across
    events: a gesture may contain overlapping or simultaneous events (a
    chord, or two parallel voices), which is legitimate.

    Raises ``AssertionError`` naming the offending index and field on the
    first violation found.
    """
    assert seq, "note sequence must be non-empty"
    for i, ev in enumerate(seq):
        assert ev.start >= 0, f"event {i}: start must be >= 0, got {ev.start!r}"
        assert ev.duration >= 0, f"event {i}: duration must be >= 0, got {ev.duration!r}"
        assert _MIN_VELOCITY <= ev.velocity <= _MAX_VELOCITY, (
            f"event {i}: velocity must be in [{_MIN_VELOCITY}, {_MAX_VELOCITY}], "
            f"got {ev.velocity!r}"
        )
        assert (
            _MIN_PITCH <= ev.pitch <= _MAX_PITCH
        ), f"event {i}: pitch must be in [{_MIN_PITCH}, {_MAX_PITCH}], got {ev.pitch!r}"


def assert_deterministic(
    render_callable: Callable[..., list[NoteEvent]], *args: Any, **kwargs: Any
) -> list[NoteEvent]:
    """Assert two calls to ``render_callable(*args, **kwargs)`` are identical.

    Renderers in this project are meant to be pure functions of their
    inputs — no wall-clock, no randomness, no hidden state — so calling one
    twice with identical arguments must yield an identical sequence, field
    for field. ``NoteEvent`` is a frozen dataclass, so list/element equality
    is exact value equality; no custom comparator is needed.

    Returns the (shared) sequence on success, so a caller can chain further
    assertions (e.g. :func:`assert_well_formed`) without rendering a third
    time.
    """
    first = render_callable(*args, **kwargs)
    second = render_callable(*args, **kwargs)
    assert first == second, (
        "render_callable is not deterministic: two calls with identical "
        f"arguments produced different sequences:\n{first!r}\n!=\n{second!r}"
    )
    return first


def assert_offline_no_audio(module_name: str) -> None:
    """Assert importing ``module_name`` pulls in no third-party audio library.

    Forces a fresh import of ``module_name`` and inspects every module that
    import newly loaded into ``sys.modules`` as a result. Fails if any newly
    loaded top-level module name either is a :data:`_KNOWN_AUDIO_MODULES`
    entry, or merely *looks like* a sound stack (contains ``"audio"`` or
    ``"sound"``, case-insensitively) — covering both known libraries
    (``sounddevice``, ``simpleaudio``, ``pyaudio``, ``pygame``, ...) and
    unanticipated ones that follow the same naming convention.

    Modules under the stdlib or under the ``harmonics`` package itself are
    always allowed — this includes the stdlib ``wave`` module, which only
    writes WAV *files* and never touches a sound device.

    This is the same technique ``tests/test_notes.py`` uses inline for
    ``harmonics.notes``, generalized into a reusable helper so other modules
    (mapping, rendering, CLI verbs) can make the same offline-import claim
    without duplicating the logic.
    """
    stdlib_names = set(sys.stdlib_module_names)
    before = set(sys.modules)

    sys.modules.pop(module_name, None)
    importlib.import_module(module_name)

    newly_imported = set(sys.modules) - before

    for mod_name in newly_imported:
        top_level = mod_name.split(".")[0]
        if top_level == "harmonics" or top_level in stdlib_names or mod_name in stdlib_names:
            continue
        assert (
            top_level not in _KNOWN_AUDIO_MODULES
        ), f"{module_name!r} pulled in known audio-stack module {mod_name!r}"
        lowered = top_level.lower()
        assert "audio" not in lowered and "sound" not in lowered, (
            f"{module_name!r} pulled in a module that looks like an audio " f"stack: {mod_name!r}"
        )

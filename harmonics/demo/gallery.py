"""``harmonics demo --html`` — the pure HTML gallery renderer.

Turns a list of :class:`~harmonics.demo.core.Clip` into a single,
self-contained, browser-playable HTML document: one card per clip, showing
its label, its set (non-``None``) :class:`~harmonics.axes.Axes` fields as
chips, a compact note-sequence summary, and a playable ``<audio>`` element
with the clip's wav embedded inline as a ``data:audio/wav;base64,...`` URI.

This module makes **no synthesis decisions** and touches no audio device or
third-party library — it only formats bytes that :mod:`harmonics.demo.core`
already rendered. Pure stdlib (``base64``, ``html``) so it stays importable
and testable with no audio backend on the path.

Deterministic: :func:`render_gallery` is a pure function of ``clips`` — same
input, byte-identical output, every call. No timestamps, no random ids, no
hashing of anything unstable; the only "ids" used (anchors) are derived from
a clip's position in the list, which is itself part of the input.
"""

from __future__ import annotations

import base64
import html

from harmonics.demo.core import Clip

_TITLE = "harmonics-cli — voice showcase"

_INTRO = (
    "A self-contained tour of the harmonics voice: every intent, several agent "
    "identities, confidence/urgency shading, sentence-to-tune inference, emphasis "
    "stress, and the four wav articulation styles — each rendered here as a "
    "playable clip. No server, no network, no external assets: this page is the "
    "whole tour."
)

#: Axis fields shown as chips, in the design-spine's canonical order.
_AXIS_FIELDS: tuple[str, ...] = ("intent", "confidence", "urgency", "state", "identity")

_STYLE = """
    :root {
      color-scheme: light dark;
      --bg: #f7f7f9;
      --fg: #1b1d22;
      --muted: #565b66;
      --card-bg: #ffffff;
      --card-border: #dcdfe6;
      --chip-bg: #eef0f5;
      --chip-fg: #33384a;
      --accent: #5b5fc7;
      --header-bg: #ffffff;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #14151a;
        --fg: #e9eaef;
        --muted: #9aa0ad;
        --card-bg: #1d1f26;
        --card-border: #33374a;
        --chip-bg: #262a38;
        --chip-fg: #cdd1e0;
        --accent: #9ea3ff;
        --header-bg: #1a1c22;
      }
    }
    :root[data-theme="dark"] {
      --bg: #14151a;
      --fg: #e9eaef;
      --muted: #9aa0ad;
      --card-bg: #1d1f26;
      --card-border: #33374a;
      --chip-bg: #262a38;
      --chip-fg: #cdd1e0;
      --accent: #9ea3ff;
      --header-bg: #1a1c22;
    }
    :root[data-theme="light"] {
      color-scheme: light;
      --bg: #f7f7f9;
      --fg: #1b1d22;
      --muted: #565b66;
      --card-bg: #ffffff;
      --card-border: #dcdfe6;
      --chip-bg: #eef0f5;
      --chip-fg: #33384a;
      --accent: #5b5fc7;
      --header-bg: #ffffff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 0 0 3rem;
      background: var(--bg);
      color: var(--fg);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      line-height: 1.5;
    }
    header {
      background: var(--header-bg);
      border-bottom: 1px solid var(--card-border);
      padding: 1.5rem 1.25rem;
    }
    header h1 {
      margin: 0 0 0.4rem;
      font-size: 1.4rem;
    }
    header p {
      margin: 0;
      max-width: 60rem;
      color: var(--muted);
      font-size: 0.95rem;
    }
    main {
      max-width: 60rem;
      margin: 0 auto;
      padding: 0 1.25rem;
    }
    h2.group-header {
      margin: 2rem 0 0.75rem;
      font-size: 1.05rem;
      color: var(--accent);
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 0.3rem;
    }
    .clip {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 0.5rem;
      padding: 0.9rem 1.1rem;
      margin: 0.75rem 0;
    }
    .clip h3 {
      margin: 0 0 0.5rem;
      font-size: 1rem;
      font-weight: 600;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin: 0 0 0.6rem;
      padding: 0;
      list-style: none;
    }
    .chip {
      background: var(--chip-bg);
      color: var(--chip-fg);
      border-radius: 999px;
      padding: 0.15rem 0.65rem;
      font-size: 0.8rem;
      white-space: nowrap;
    }
    .notes {
      margin: 0 0 0.6rem;
      font-size: 0.8rem;
      color: var(--muted);
      word-break: break-word;
    }
    audio {
      width: 100%;
      max-width: 24rem;
    }
""".strip("\n")


def _chips_html(clip: Clip) -> str:
    items = []
    for field in _AXIS_FIELDS:
        value = getattr(clip.axes, field)
        if value is None:
            continue
        text = html.escape(f"{field}: {value}")
        items.append(f'<li class="chip chip-{html.escape(field)}">{text}</li>')
    if not items:
        return ""
    return '<ul class="chips">' + "".join(items) + "</ul>"


def _notes_summary_html(clip: Clip) -> str:
    count = len(clip.notes)
    if count == 0:
        return '<p class="notes">0 notes</p>'
    parts = [
        f"{n.voice} p{n.pitch} v{n.velocity:.2f} @{n.start:.2f}s+{n.duration:.2f}s"
        for n in clip.notes
    ]
    noun = "note" if count == 1 else "notes"
    summary = f"{count} {noun}: " + ", ".join(parts)
    return f'<p class="notes">{html.escape(summary)}</p>'


def _audio_html(clip: Clip) -> str:
    b64 = base64.b64encode(clip.wav).decode("ascii")
    return f'<audio controls preload="none" src="data:audio/wav;base64,{b64}"></audio>'


def _clip_group(label: str) -> str:
    # The group is the label's leading token before the first ":"; also strip a
    # trailing " (agent)" qualifier so, e.g., "say (spark): ..." and "say: ..."
    # both group under "say" instead of splitting into separate headers.
    return label.split(":", 1)[0].split(" (", 1)[0]


def _clip_html(index: int, clip: Clip) -> str:
    anchor = f"clip-{index}"
    label_html = html.escape(clip.label)
    return "\n".join(
        [
            f'<section class="clip" id="{anchor}">',
            f"<h3>{label_html}</h3>",
            _chips_html(clip),
            _notes_summary_html(clip),
            _audio_html(clip),
            "</section>",
        ]
    )


def render_gallery(clips: list[Clip]) -> str:
    """Return a self-contained HTML document showing every clip: its label,
    axes, note summary, and a playable embedded WAV.

    Fully self-contained — all CSS is inlined in a ``<style>`` block and every
    clip's audio is a base64 ``data:audio/wav;base64,...`` URI, so the
    document never references an external host (no CDN, no webfont, no
    remote image). Pure function of ``clips``: calling it twice on the same
    (or an equal) list returns an identical string — no timestamps, no
    random ids, and any per-clip anchor is derived only from the clip's
    index in the list.

    One card is emitted per clip, in the given order; a section header is
    emitted whenever the clip's group (its label prefix before ``":"``, minus
    any ``" (agent)"`` qualifier) changes from the previous clip's, grouping
    the tour without requiring any extra input.
    """
    body_sections: list[str] = []
    last_group: object = object()  # sentinel: never equals a real group name
    for index, clip in enumerate(clips):
        group = _clip_group(clip.label)
        if group != last_group:
            body_sections.append(f'<h2 class="group-header">{html.escape(group)}</h2>')
            last_group = group
        body_sections.append(_clip_html(index, clip))

    body = "\n".join(body_sections)

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(_TITLE)}</title>\n"
        f"<style>{_STYLE}</style>\n"
        "</head>\n"
        "<body>\n"
        "<header>\n"
        f"<h1>{html.escape(_TITLE)}</h1>\n"
        f"<p>{html.escape(_INTRO)}</p>\n"
        "</header>\n"
        "<main>\n"
        f"{body}\n"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )

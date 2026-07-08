"""``harmonics.audio`` — the offline audio backend (see :mod:`harmonics.audio.synth`).

Re-exports :func:`render_wav`/:func:`write_wav`/:func:`play` so callers (the
``play``/``say`` CLI verbs) can write ``from harmonics.audio import play`` /
``harmonics.audio.play(seq)`` without reaching into the ``synth`` submodule
directly. Importing this package pulls in only the standard library — see
``harmonics/audio/synth.py``'s module docstring for the isolation rule that
guarantees that (the optional playback library only loads lazily, inside
:func:`play` itself, at call time).
"""

from __future__ import annotations

from harmonics.audio.synth import DEFAULT_SAMPLE_RATE, play, render_wav, write_wav

__all__ = ["render_wav", "write_wav", "play", "DEFAULT_SAMPLE_RATE"]

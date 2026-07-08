"""The ``harmonics demo`` package — a curated tour of the agent voice.

Exposes the public surface: the curated data (:mod:`harmonics.demo.matrix`)
and the deterministic, offline renderer (:mod:`harmonics.demo.core`) that
turns it into concrete clips. Deliberately does NOT import the (not-yet-
built) gallery/file/live-playback modules here, so importing this package
stays backend-free — no HTML renderer, no file writer, no audio device import
anywhere in this module's own import graph.
"""

from __future__ import annotations

from harmonics.demo.core import Clip, showcase
from harmonics.demo.matrix import GROUPS, MATRIX, ClipSpec, iter_clips

__all__ = [
    "showcase",
    "Clip",
    "ClipSpec",
    "GROUPS",
    "MATRIX",
    "iter_clips",
]

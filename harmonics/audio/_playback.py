"""Shared live-playback helpers: output-device selection + friendly errors.

Both live-playback paths — :func:`harmonics.audio.synth.play` (one gesture)
and :func:`harmonics.demo.play.play_clips` (a sequence of pre-rendered clips)
— need the SAME two things once a ``sounddevice`` backend is in hand: pick
which output device to open, and turn a device failure into the project's
structured :class:`~harmonics.cli._errors.CliError` instead of a bare
``PortAudioError``. That shared logic lives here, in one internal module, so
``harmonics.demo.play`` no longer reaches into ``harmonics.audio.synth``'s
internals to get it.

Like the rest of :mod:`harmonics.audio`, importing this module pulls in only
the standard library — the optional ``sounddevice`` backend is passed IN (as
an already-imported module object) by the caller's own lazy import, never
imported here.
"""

from __future__ import annotations

from harmonics.cli._errors import EXIT_ENV_ERROR, CliError

#: Sound-server PortAudio device names that resample (accept an arbitrary
#: sample rate), tried IN ORDER when no device is explicitly requested.
#: Preferring one of these makes live playback "just work" on a host whose raw
#: ALSA ``default`` sink is a FIXED-rate device (e.g. a 16 kHz USB audio
#: adapter) that would otherwise reject the synth's 44.1 kHz — i.e. this is
#: what "default to pipewire" means in practice. On a host without such a
#: device (macOS/Windows, or a plain ALSA box) none match and playback falls
#: back to the backend's own default. Override either way with ``--device`` /
#: ``$HARMONICS_AUDIO_DEVICE`` (see :func:`select_output_device`).
PREFERRED_OUTPUT_DEVICES: tuple[str, ...] = ("pipewire", "pulse")


def select_output_device(sounddevice: object, requested: int | str | None) -> int | str | None:
    """Choose which output device a ``sounddevice`` playback call should open.

    An explicitly ``requested`` device always wins: an ``int`` (or an
    all-digit string) is treated as a device index, any other non-empty
    string as a name substring — both of which ``sounddevice.play(device=...)``
    accepts. With nothing requested, prefer a resampling sound-server device
    (see :data:`PREFERRED_OUTPUT_DEVICES`) when one is present, returning its
    index; otherwise return ``None`` so the caller omits ``device=`` and the
    backend uses its own default. Any failure to enumerate devices also yields
    ``None`` (fall back to the default) rather than raising.
    """
    if requested is not None and requested != "":
        if isinstance(requested, str) and requested.isdigit():
            return int(requested)
        return requested
    try:
        devices = list(sounddevice.query_devices())
    except Exception:  # noqa: BLE001 - can't enumerate -> just use the default device
        return None
    for name in PREFERRED_OUTPUT_DEVICES:
        for index, dev in enumerate(devices):
            if dev.get("max_output_channels", 0) > 0 and name in dev.get("name", "").lower():
                return index
    return None


def output_device_listing(sounddevice: object) -> str:
    """A short, best-effort ``[index] name`` list of output-capable devices,
    for the remediation hint of a device error. Returns ``""`` if the backend
    can't be enumerated (the hint then simply omits the listing)."""
    try:
        devices = list(sounddevice.query_devices())
    except Exception:  # noqa: BLE001 - listing is best-effort inside an error path
        return ""
    return "; ".join(
        f"[{index}] {dev.get('name', '?')}"
        for index, dev in enumerate(devices)
        if dev.get("max_output_channels", 0) > 0
    )


def device_playback_error(sounddevice: object | None, exc: Exception, sample_rate: int) -> CliError:
    """Wrap a live-device failure (e.g. a PortAudio invalid-sample-rate error
    from a sink that can't accept the synth's rate) in the project's
    structured :class:`~harmonics.cli._errors.CliError` — an ENVIRONMENT error
    (:data:`~harmonics.cli._errors.EXIT_ENV_ERROR`) with an actionable hint —
    instead of letting it reach the CLI's last-resort "unexpected error, file
    a bug" handler. It is not a bug: the device or its routing is the problem,
    so the hint points at ``--device`` and ``--wav``. Pass ``sounddevice=None``
    (the ``simpleaudio`` backend, which can't enumerate devices) to omit the
    device listing."""
    hint = (
        f"the audio device could not play {sample_rate} Hz audio. Select another "
        "with --device NAME|INDEX or $HARMONICS_AUDIO_DEVICE (e.g. "
        "--device pipewire), or render a file with --wav and play it yourself"
    )
    listing = output_device_listing(sounddevice) if sounddevice is not None else ""
    if listing:
        hint += f". Output devices: {listing}"
    return CliError(
        code=EXIT_ENV_ERROR,
        message=f"audio playback failed: {exc}",
        remediation=hint,
    )

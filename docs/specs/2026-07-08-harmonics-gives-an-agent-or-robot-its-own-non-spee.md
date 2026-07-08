# harmonics gives an agent or robot its own non-speech VOICE: it turns the agent's live intent, confidence, urgency, state, and identity into short, pleasant sonic gestures a listener recognizes by who is speaking and what they mean — the first-person inverse of a spectator soundtrack, rendered as a note sequence first and sound second.

> harmonics gives an agent or robot its own non-speech VOICE: it turns the agent's live intent, confidence, urgency, state, and identity into short, pleasant sonic gestures a listener recognizes by who is speaking and what they mean — the first-person inverse of a spectator soundtrack, rendered as a note sequence first and sound second.

## Audience

- AI agents and physical robots that must express themselves without a screen or speech, plus the humans and peer agents nearby who listen and need to know — by ear — who is present, what they intend, and how it's going.

## Before → After

- Before: Today a headless agent is silent, or borrows a third-person spectator soundtrack (like league-of-agents' replay score) that narrates a match from the outside off an event log; there is no first-person non-speech channel an agent emits as itself, live, in the moment.
- After: An agent can render its current meaning (intent/confidence/urgency/state/identity) into a short, pleasant note sequence — and thence audio — that a listener recognizes as *that agent* saying *that thing*, produced offline, deterministically, with a dependency-free core.

## Why it matters

- A recognizable non-speech voice makes a headless agent or robot present and legible by ear — you can tell who is working, who just succeeded, who is stuck — with no screen to read and no speech to synthesize or parse.

## Requirements

- A pure text->notes core: 'harmonics play --intent <i> [--confidence <c>] [--urgency <u>] [--state <s>] [--as <agent>]' maps the axes to a documented note-event sequence. Dry-run by default (emits the notes); making sound or a file needs an explicit --play/--out. The core imports no audio stack and runs with no device.
  - honesty: Same axes + same identity + same nonce (--seq) produce an identical note sequence, and the micro-variation across nonces is itself a pure function of the nonce — no wall-clock, no unseeded randomness; the whole text->notes path runs in tests with no third-party import and no audio device present.
- Each agent carries a recognizable signature (its 'voice print' — key / instrument-timbre / motif seed) derived deterministically from its identity string, generalizing league's per-team register into per-agent identity, with an optional hand-authored override in the palette.
  - honesty: The same identity always renders the same signature; two distinct identities render audibly distinct, stable signatures; a hand-authored palette override deterministically replaces the derived one.
- The palette stays pleasant and non-fatiguing even at the urgent end: urgency is carried by tempo, attack sharpness, and repetition — never by dissonance or raw loudness — so an urgent voice is attention-grabbing but never an alarm-clock, and repeated play next to a human does not fatigue.
  - honesty: 'Non-fatiguing' and 'non-alarm' are checkable on the note sequence: every gesture stays within a documented consonant palette and bounded velocity/attack, and the urgent-vs-calm difference shows up only as bounded inter-onset/tempo/repetition — never as added dissonance or a raised level ceiling.
- 'harmonics say "<sentence>"' parses a sentence into the five axes and then renders it — the text->notes surface. It ships in the same increment as 'play', reusing 'play's mapping once axes are inferred. Dry-run by default like every producing verb.
  - honesty: Sentence->axes inference is deterministic and offline: a documented cue/keyword->axis rule table (not a network or model call) maps a sentence to the axes; the same sentence always yields the same axes; the test path makes no network call and imports no model.
- A caller-supplied nonce ('--seq', with a stable default) selects among deterministic micro-variations of the same gesture, so repeated utterances feel alive rather than robotic while staying fully reproducible (generalizing league's field-hashed variety).
  - honesty: Two different nonces yield audibly-but-subtly different utterances of the same intent; the same nonce always yields the same one; the default (no --seq) is itself a fixed, documented value — variation is never a function of wall-clock or entropy.
- The 'say' tune is derived from the sentence's own units (letters / syllables / words -> pitch, timbre, rhythm steps), not only from inferred axes, so a human can APPROXIMATELY connect the sound back to the text — following 'what is being said' by how it is voiced, the way you follow a hummed phrase. Still non-speech: no phonemes are reproduced.
  - honesty: The text->contour mapping is documented and deterministic (same text -> same contour); in a small blind ear-test, listeners match a rendered tune back to its source phrase (from a short candidate set) better than chance.
- The agent/robot can STRESS parts of the tune via pitch and volume to emote — raising pitch and/or loudness on marked segments, emphasis carried explicitly (emphasis markers in the text or a stress argument), layered over the intent/confidence/urgency axes. Stress modulation stays WITHIN the palette's documented non-fatiguing level ceiling (the pleasantness requirement above), so emphasis never becomes an alarm.
  - honesty: Stressing a segment measurably raises that segment's note pitch and/or velocity in the emitted sequence relative to the neutral baseline, deterministically and within the level ceiling; with no stress markers the render is the documented neutral baseline.

## Honesty conditions

- In a blind ear test the output reads as one agent's discrete first-person utterance — not an ambient bed narrating events — and two identities rendering the same axes are recognizably different voices.
- The audience is real and reachable: a concrete consumer exists on each side — a headless/robot agent that emits, and a human or peer agent that listens and acts on what it hears.
- The after-state is demonstrable end to end: one command takes axes (or a sentence) and yields a note sequence, and an audio backend can render that sequence — with the core path needing no audio device.
- The gap is real: no existing surface gives an agent a first-person non-speech voice; league's soundtrack is third-person and event-log-driven, per its own module docs.
- The benefit is observable: from sound alone, with no screen, a listener identifies who is acting and the broad state (working/succeeded/blocked) above chance.
- The boundary is enforceable: the surface reproduces no phonemes or words, and its output is driven by the agent's own axes/sentence — never by an external match or event log.
- The signal is measured, not asserted: tests assert on emitted note sequences with no device, and a documented ear-test protocol backs the two human-discrimination claims (agent-vs-agent, success-vs-question).
- The legibility/stress signal is measured: a documented ear-test protocol exists — tune->phrase matching from a candidate set and stressed-part identification — with a stated better-than-chance bar.

## Success signals

- Given axes plus an agent identity, harmonics emits a deterministic note sequence (dry-run, no audio device) that unit tests assert on directly; and by ear a listener can tell two different agents apart, and tell a confident success from an uncertain question.
- By ear a listener can approximately connect a rendered 'say' tune to its source sentence, and can tell which parts were stressed — the voice reads as 'this text, emoted', not an arbitrary motif.

## Scope / boundaries

- Not TTS (no words or phonemes); not a spectator soundtrack, match score, or event-log narration; not an ambient bed you tune out. It is a first-person utterance you attend to, driven by the agent's own axes rather than an external timeline.

## Decisions

- A rendered gesture is a sequence of note events, each a small record (start, duration, pitch, velocity, voice/timbre) — the machine-readable 'notes' of text-to-notes. This sequence is the unit-test surface and the MIDI/robot-consumable representation; audio backends render FROM it, never instead of it.

## Hard questions

- Does the first increment ship only 'play' (explicit axes -> notes), with 'say' (sentence -> inferred axes) as a follow-up? Or must sentence inference land in the same increment? [RESOLVED: both 'play' (explicit axes) and 'say' (sentence inference) ship in increment 1 — see the 'say' requirement.]
- risk: Even with bounded palette/velocity/tempo proxies, final 'pleasantness' needs a human ear; the checkable proxies reduce but do not eliminate subjectivity.

## Open questions (non-blocking — settle in the plan)

- Audio backend for actual sound (pure-Python sine/FM offline default vs sounddevice / simpleaudio / soundfont). The core stays dependency-free and offline-testable, so this does not block the spec.
- Granularity of the text->contour unit (per-letter vs per-syllable vs per-word, and how letters color pitch/timbre) — the legibility requirement is fixed; the exact unit is an implementation choice.

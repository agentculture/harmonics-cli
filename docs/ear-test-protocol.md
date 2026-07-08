# Ear-test protocol

harmonics makes human-discrimination claims that no offline note-sequence
assertion can settle on its own — "a listener can tell two agents apart", "a
success sounds confident and a question sounds unsure". The offline harness in
`tests/ear_harness.py` proves the *notes* are well-formed and deterministic;
it cannot prove a human ear reads them the way the design spine intends. This
document is the other half: a blind-listening protocol, run by a human
facilitator with real listeners, for each human-discrimination claim the
project makes. Per the honesty-conditions rule in `CLAUDE.md`, these claims
are measured, not asserted — this file is the measurement instrument.

## Scope

Four discriminations are covered, one per section below:

1. [Agent-vs-agent](#1-agent-vs-agent-identity-discrimination) — listeners
   tell two different agents apart by their signatures.
2. [Success-vs-question](#2-success-vs-question-intentconfidence-discrimination)
   — listeners tell a confident success from an uncertain question.
3. [Tune→phrase matching](#3-tunephrase-matching) — listeners match a
   rendered `say` tune back to its source sentence from a candidate set.
4. [Stressed-part identification](#4-stressed-part-identification) —
   listeners identify which part of an utterance was stressed.

Each section states: the task, the stimuli, the listener panel size (`N`),
the candidate-set size (`k`) where relevant, the chance level, the trial
count, and an explicit numeric pass bar stated as "well above chance". Every
pass bar in this document was chosen with a wide margin over the level needed
for bare statistical significance (a one-tailed exact binomial test against
the chance level, α = 0.05) — see [Statistical grounding](#statistical-grounding)
for the numbers. This protocol targets the audio verbs in the build brief
(`harmonics play`, `harmonics say`, the per-agent signature palette); it is
written now, ahead of those verbs landing, so the bar is fixed before the
implementation exists to be graded against it.

## General setup (applies to all four protocols)

- **Equipment**: closed-back or in-ear headphones in a quiet room (no
  open-plan office noise floor). All clips normalized to the same peak
  loudness so volume alone is never a cue.
- **Listener panel**: no musical training required — the palette is meant to
  read to *any* agent operator, not just trained ears. Screen only for
  self-reported normal hearing.
- **Blinding**: listeners never see axis labels, agent names, or file names
  during a trial — clips are presented as anonymized "Clip A" / "Clip B" /
  "Clip X" or numbered candidates. The facilitator holds the answer key
  separately from the listener-facing materials.
- **Session length**: sessions are capped at roughly 15 minutes of active
  listening per protocol per listener, with trial order randomized
  per-listener to cancel ordering/fatigue effects.
- **Scoring**: every trial is scored as correct/incorrect against the
  answer key; no partial credit. Aggregate accuracy is percent correct across
  *all* trials from *all* listeners pooled (not averaged per-listener), and
  is the number compared against the pass bar.
- **Analysis**: report aggregate accuracy plus the exact one-tailed binomial
  p-value against the chance level for that protocol. A pass requires both
  the accuracy to clear the numeric bar below *and* p < 0.05 — in practice
  every bar below already implies p ≪ 0.05 at the specified trial count (see
  [Statistical grounding](#statistical-grounding)), so the accuracy bar is
  the binding constraint.
- **Reporting**: each run is logged with date, panel size, per-trial raw
  scores (not just the aggregate), and the stimuli set used, so a run can be
  reproduced or audited later.

## 1. Agent-vs-agent identity discrimination

**Claim under test**: two agents' signature motifs (per the *identity* axis
in the design spine) are distinguishable by ear.

- **Task**: ABX. The listener hears clip **A** (agent X's signature), clip
  **B** (agent Y's signature), then clip **X**, which is a fresh render of
  either agent's signature. The listener answers "X matches A" or "X matches
  B".
- **Candidate-set size**: `k = 2` (two agents per ABX round; the identity
  claim is inherently pairwise).
- **Listeners**: `N = 20`.
- **Trials**: 10 ABX rounds per listener against one agent pair, repeated
  across at least 3 distinct agent pairs drawn from the signature palette (so
  a pass isn't an artifact of one unusually-distinctive pair). Which clip is
  presented as "X" is balanced 50/50 across trials.
- **Chance level**: 50% (binary forced choice).
- **Pass bar**: **≥75% correct** aggregate across all trials (150 of 200
  trials at `N = 20` × 10 trials), well above the 50% chance line.

## 2. Success-vs-question (intent/confidence) discrimination

**Claim under test**: a high-confidence `success` render and a low-confidence
`question` render — opposite ends of the *intent* and *confidence* axes — are
told apart reliably, without the listener seeing any label.

- **Task**: two-alternative forced choice (2AFC). The listener hears one
  unlabeled clip, rendered from either `intent=success, confidence=high` or
  `intent=question, confidence=low`, and answers "confident success" or
  "uncertain question".
- **Candidate-set size**: `k = 2` (the two response categories).
- **Listeners**: `N = 20`.
- **Trials**: 20 trials per listener (10 of each category in randomized
  order, no more than 2 of the same category back-to-back).
- **Chance level**: 50% (binary forced choice).
- **Pass bar**: **≥80% correct** aggregate across all trials (320 of 400
  trials at `N = 20` × 20 trials), well above the 50% chance line. The bar is
  set higher than the identity test (§1) deliberately: success-vs-question
  sits at opposite ends of two axes at once, so if listeners can't clear a
  high bar here, the confidence/urgency mapping itself — not just a
  borderline pair — has failed.

## 3. Tune→phrase matching

**Claim under test**: a tune rendered by `harmonics say "<sentence>"` still
carries enough of the source sentence's meaning that a listener can match it
back to the sentence that produced it, out of a small set of plausible
candidates.

- **Task**: match-to-sample. The listener hears one rendered tune, then reads
  `k` candidate sentences (1 true source + `k - 1` distractors). Distractors
  are drawn to differ from the source on at least one axis (different
  intent, confidence, or urgency) rather than being near-synonyms, so the
  test measures axis discrimination, not lexical guessing. The listener picks
  the candidate they believe produced the tune.
- **Candidate-set size**: `k = 4` (chance = 1/4 = 25%).
- **Listeners**: `N = 20`.
- **Trials**: 15 trials per listener, each with a fresh tune and a freshly
  drawn candidate set of size `k = 4`.
- **Chance level**: 1/k = 25%.
- **Pass bar**: **≥70% correct** aggregate across all trials (210 of 300
  trials at `N = 20` × 15 trials), well above the 25% chance line.
- **Extended (optional) variant**: the same task at `k = 8` (chance =
  12.5%), pass bar **≥50% correct**, still well above chance, run only after
  the `k = 4` variant passes — a stress test of how far the matching signal
  degrades as the candidate set grows.

## 4. Stressed-part identification

**Claim under test**: within a single multi-segment utterance, the segment
the renderer marked as emphasized (elevated confidence/urgency contour on
that segment, per the design spine's sonic mapping) is the segment listeners
perceive as stressed.

- **Task**: forced choice among segments. The listener hears one rendered
  utterance built from exactly 4 word/chunk segments, with one segment
  rendered as stressed, and picks which of the 4 segments (by position: 1st,
  2nd, 3rd, or 4th) sounded stressed.
- **Candidate-set size**: `k = 4` (fixed at 4 segments per test utterance so
  every trial has the same chance level).
- **Listeners**: `N = 20`.
- **Trials**: 15 trials per listener; the stressed segment's position is
  rotated evenly across the 4 positions (matching the trial count as closely
  as integer division allows) so no position is over- or under-represented
  in the answer key.
- **Chance level**: 1/k = 25%.
- **Pass bar**: **≥65% correct** aggregate across all trials (195 of 300
  trials at `N = 20` × 15 trials), well above the 25% chance line. The bar
  sits below the tune-matching bar (§3) because within-utterance stress is a
  finer-grained discrimination than whole-tune matching.

## Statistical grounding

Every pass bar above was chosen to clear bare statistical significance by a
wide margin. For a one-tailed exact binomial test against the stated chance
level at the stated trial count, the number of correct trials needed for
p < 0.05 is far below the pass bar in every case:

| Protocol | Trials (`n`) | Chance | Bar needed for p < 0.05 | Chosen pass bar | Exact p at pass bar |
|---|---|---|---|---|---|
| Agent-vs-agent (§1) | 200 | 50% | ≥113 (56.5%) | ≥150 (75%) | ≈ 4.2 × 10⁻¹³ |
| Success-vs-question (§2) | 400 | 50% | ≥217 (54.2%) | ≥320 (80%) | ≈ 2.2 × 10⁻³⁵ |
| Tune→phrase matching (§3) | 300 | 25% | ≥88 (29.3%) | ≥210 (70%) | ≈ 4.8 × 10⁻⁶⁰ |
| Stressed-part ID (§4) | 300 | 25% | ≥88 (29.3%) | ≥195 (65%) | ≈ 4.0 × 10⁻⁴⁸ |

In other words, a pass at any of the bars above is not a marginal
statistical squeak-by — it is a wide, decisive margin over chance, matching
the "well above chance" framing used throughout this document (e.g. "≥70%
correct with k=4, well above the 25% chance line" for §3).

## Relationship to the offline harness

This protocol is deliberately **human-in-the-loop and manual** — it is not
run by `pytest` and does not gate CI. It complements, and does not replace,
`tests/ear_harness.py`:

- the offline harness proves a rendered `list[NoteEvent]` is well-formed and
  that rendering is deterministic, with no audio device and no third-party
  audio import in the test path;
- this protocol proves that when those well-formed notes actually become
  sound, a human ear reads the intended meaning back out of them.

A claim in the honesty conditions is only considered measured, not merely
asserted, once both halves — the offline assertion and a logged run of the
matching protocol above — exist.

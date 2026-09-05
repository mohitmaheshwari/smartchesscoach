# Reflection as Accepted Evidence — Scope

**Status:** DRAFT — awaiting Mohit signoff. No code until signed off.
**Date:** 2026-09-05
**Feature name:** `reflection_accepted_evidence`

---

## 0. Existing surfaces audit

### What already touches this need

| Surface / store | What it already provides | Rows / users |
|---|---|---|
| `/progress` (`UnifiedProgress.jsx`) | "Currently working on" → "Also tracking" → "You beat these", with `reduction_pct` over 90 days | live page |
| `user_active_focus` + `focus_bridge` | The one thing a player is working on; 7 `topic_key` values | 273 / 53 |
| `phase8_release_evidence.py:541-559` | Transfer verdict from later unassisted games: `improved` / `still_recurring` / `insufficient_evidence` | live |
| `reflection_sessions` | The player's accepted cause, bound to an engine-verified event | 3 / 1 |
| `quick_tag_registry.TAG_DEFINITIONS` | The 21 answer options, each already carrying `predicates` (the board fact that licensed it) and `category_boost` | code |
| `user_concept_understanding` | Legacy per-concept model, 229 distinct ids | 3,852 / 63 |
| `user_pattern_events` | Raw pattern fires | 108,181 / 59 |
| `user_teaching_memory` | What was taught | 29,974 / 48 |
| `coach_memory`, `player_profiles`, `player_identities`, `user_pattern_decay` | Older per-user models | 122 / 70 / 67 / 105 |

### The overlap, honestly

The chain this feature wants — *fundamental → tracked → measured improvement → shown to the player* —
**already exists end to end.** `/progress` renders it and Phase 8 computes the verdict.

Two things are genuinely absent:

1. **Reflections cannot join it.** Six vocabularies, no mapping between them:
   `topic_key` (7) · reflection `concept_id` (dotted) · `concept_used` (13) · legacy
   `concept_id` (229) · tag `predicates` (9) · `category_boost` (6).
2. **Nothing carries provenance.** Every weakness on `/progress` is *inferred* by a detector.
   There is no way to record "the player agreed to this", which is the entire value here.

The good news, found while auditing: `TAG_DEFINITIONS` is already a clean table. Every answer
option states the board fact that licensed it — `thought_piece_safe` and `thought_protected` both
carry `predicates: ["user_piece_left_hanging"]`. **The join runs through predicates, not through
the 229 legacy ids**: 9 predicate values map onto the 7 fundamentals. That is a reviewable table,
not a migration.

It also exposes a split that matters. Five options carry **no predicate at all** —
`thought_winning`, `felt_danger`, `wanted_to_finish`, `rushed_conversion`, `played_fast`. These
are self-reported *states*, not board facts. Nothing engine-side can confirm or refute them, so
they cannot drive a transfer verdict. Two more, `not_sure` and `none_of_these`, are non-answers.

### Decision: **EXTEND**

Building a separate reflection profile would be the third surface showing a player their
weaknesses. Reflections become a **provenance-carrying input** to the model that exists.

---

## 1. What it is

When a player reviews a game and we show them a mistake, we ask what they were thinking. They
pick an answer — *"I did not notice the bishop on d2 attacking my bishop on b4"* — before we
reveal anything. Today that answer is counted and thrown away.

This feature makes that answer the strongest evidence in the player's profile. The coach stops
saying only *"you hung a piece"* (which the engine inferred) and starts saying *"you keep missing
attackers — you told me so twice"* (which the player agreed to). Because the player accepted it,
it can be said with confidence, and because it is attached to an engine-verified move, it can be
measured: does that specific habit get better in later games they played alone?

---

## 2. What the user sees

**On `/progress`, the active card gains a provenance line.** Today it says what we detected.
After this, when the player has told us, it says so:

```
┌──────────────────────────────────────────────────────────────┐
│  CURRENTLY WORKING ON                                        │
│                                                              │
│  Missing the attacker                                        │
│  You told us this twice — once about a knight on c2,         │
│  once about a bishop on b4. Both times you said you          │
│  hadn't noticed the piece that was attacking it.             │
│                                                              │
│  ● You said this          2 games                            │
│  ○ We also detected it    9 moves                            │
│                                                              │
│  Since then: not enough games yet to say if it's improving   │
│                                                              │
│  [ Practice spotting attackers ]                             │
└──────────────────────────────────────────────────────────────┘
```

Three states for the bottom line, and only these three:

- `not enough games yet to say if it's improving` — fewer than the transfer window
- `still happening — 3 times in your last 10 games` — recurring
- `you've stopped doing this — 0 times in your last 10 games` — improved

**In the reflection prompt itself, nothing changes.** The question, options and timing are
already right. This feature is about what happens to the answer.

**When the player has NOT told us anything**, the card reads exactly as it does today. No
regression, no empty provenance row.

---

## 3. In scope (V1)

- **One canonical fundamentals vocabulary.** The dotted reflection id is already
  `<fundamental>.<mechanism>` where the prefix *is* an existing `topic_key`
  (`piece_safety.simple_hang` → `piece_safety`). Adopt that as canonical; it needs no new
  vocabulary invented.
- **One `fundamental` field added to each `TAG_DEFINITIONS` row**, derived from the predicate it
  already declares. Extending the existing registry rather than adding a parallel mapping file —
  the registry is already the canonical quick-tag authority that builds the options.
- **Write the accepted cause into the profile** on reflection submit: the `selected_option_id`
  (one of the 21 in `QuickTagId`), the fundamental, the mechanism, the `event_id`, and
  `source: player_accepted`.
- **Two tiers, kept apart.** An option with a predicate is *board-anchored* and can carry a
  transfer verdict. An option without one (`thought_winning`, `felt_danger`, `wanted_to_finish`,
  `rushed_conversion`, `played_fast`) is a *self-reported state*: recorded and shown, never
  measured, never called improved or still-recurring.
- **`not_sure` and `none_of_these` are never written as a cause.** They are the player declining
  to answer. Counting them as accepted evidence would be the worst failure this feature could
  have.
- **Provenance is first-class.** Every weakness the profile holds carries `player_accepted` or
  `detector_inferred`. Nothing is silently merged.
- **Misconception is orthogonal to fundamental.** `thought_piece_safe` already appeared under two
  different concepts in one game — the model must express "one habit, two fundamentals" rather
  than two weaknesses.
- **Feed `focus_bridge`** so a player-accepted cause can inform the active focus.
- **Reuse the Phase 8 transfer verdict unchanged** — accepted causes flow into the same
  `improved` / `still_recurring` / `insufficient_evidence` machinery.
- **`/progress` renders the provenance line** and the three states above.
- **Fail closed**: no accepted cause, no provenance row. Never invent one.

---

## 4. Explicitly out of scope (V1)

- **Any ranking or scoring rule** that weighs accepted vs inferred evidence numerically. There
  are 3 reflections in the database; a weight picked now would be picked with no distribution.
  V1 stores and displays; it does not score.
- **Migrating the 229 legacy `user_concept_understanding` ids.** The predicate join makes them
  unnecessary for V1. No backfill, no deletion, no mapping attempted.
- **Changing the reflection prompt, its options, or when it appears.** The capture format is
  already correct.
- **Retiring any of the nine existing weakness stores.** Consolidation is a separate decision.
- **Coaching copy that claims causation** ("because you said this, you improved"). V1 reports
  what was said and what happened, separately.
- **New reflection surfaces** (in Play with Coach, on Home). Game review only.
- **LLM summarisation of accepted causes.** Deterministic strings only.

---

## 5. Success criteria

V1 is successful when, for a player who has answered at least one reflection:

1. Their accepted cause appears on `/progress` with `You said this`, naming the fundamental and
   the number of games — verified by opening the page as a real non-admin pilot user.
2. The same accepted cause reaches `focus_bridge` and can become the active focus.
3. Phase 8's transfer verdict runs on it and returns one of the three states honestly, including
   `insufficient_evidence` when that is the truth.
4. A player with no reflections sees `/progress` exactly as it renders today — no empty rows, no
   regression. Verified against a second pilot user.
5. Zero cases where a misconception the player did not select is attributed to them. This is a
   correctness gate, not a metric.

Deliberately **not** a success criterion: engagement, reflection count, or improvement rate.
Those are outcomes of launching, not of this architecture.

---

## 6. Open questions

**Q1. Where do the 9 predicates land among the 7 fundamentals?**
Why unresolved: most are obvious — `user_piece_left_hanging` → `piece_safety`,
`simple_tactic_missed` → `missed_tactic`, `time_pressure_detected` → `time_management`. Three are
not. `user_attacked_instead_of_defending` could be `king_safety` or `threat_awareness`;
`user_defended_phantom_threat` is a false-alarm habit that matches none of the 7; `is_opening_phase`
is a phase, not a weakness.
Unblocking step: one 9-row table, reviewed in a single pass. The three hard rows either get a
fundamental or get excluded — no guessing.

**Q2. Should an accepted cause be able to override a detector-inferred focus?**
Why unresolved: product judgement. If a player says "I didn't see the attacker" but the detector
says the dominant pattern is king safety, which does the coach lead with?
Unblocking step: Mohit's call. V1 can display both and lead with the accepted one without
deleting the inferred one.

**Q3. How many accepted events before the profile treats it as a habit?**
Why unresolved: needs a distribution that does not exist yet.
Unblocking step: deferred to `/lock-via-data` after the pilot produces reflections. V1 shows the
raw count ("You told us this twice") rather than a threshold verdict.

**Q4. Does `calculation.*` map to an existing fundamental or need a new one?**
Why unresolved: `calculation.legal_material_loss` has no `canonical_source` and its
`quality_id` is the many-to-one `review:verified_single_game_cause`, unlike
`piece_safety.simple_hang` which maps 1:1 to a detector.
Unblocking step: inspect the `calculation.*` concepts against the 7 topic_keys before coding. If
the reflection `concept_id` prefix and the tag predicate disagree on the fundamental, the predicate
wins — it is the board fact.

---

## 7. Pre-code requirements

1. **Mohit signs off on this document.** Hard gate.
2. **Q1 answered** — the 9-row predicate table is written and reviewed, with the excluded
   predicates named.
3. **Q4 answered** — `calculation.*` either maps to an existing fundamental or is explicitly
   deferred.
4. **Q2 answered** — Mohit's call on accepted-vs-inferred precedence.
5. **The pilot cohort is enrolled**, so there is at least one non-admin user who can produce a
   reflection to verify success criteria 1–4 against a real account rather than a fixture.
6. **`/audit-pre-code` run** once 1–5 are true.
7. Q3 stays open by design and goes to `/lock-via-data` after the pilot, not before code.

---

## Why this is worth building before launch

Not live yet is the argument *for* this, not against it. The reflection record is already
well-formed — event, concept, quality grade, selected option, elapsed time, answered-before-reveal.
What is missing is anywhere for it to land. Building the landing place after users arrive means
their first weeks of accepted evidence are counted and discarded, which is exactly what happens
to the three reflections in the database today.

Thresholds need a distribution first. Architecture does not.

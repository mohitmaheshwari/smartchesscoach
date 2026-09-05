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
| `user_concept_understanding` | Legacy per-concept model, 229 distinct ids | 3,852 / 63 |
| `user_pattern_events` | Raw pattern fires | 108,181 / 59 |
| `user_teaching_memory` | What was taught | 29,974 / 48 |
| `coach_memory`, `player_profiles`, `player_identities`, `user_pattern_decay` | Older per-user models | 122 / 70 / 67 / 105 |

### The overlap, honestly

The chain this feature wants — *fundamental → tracked → measured improvement → shown to the player* —
**already exists end to end.** `/progress` renders it and Phase 8 computes the verdict.

Two things are genuinely absent:

1. **Reflections cannot join it.** Four vocabularies, no mapping:
   `topic_key` (7) · reflection `concept_id` (dotted) · `concept_used` (13) · legacy `concept_id` (229).
2. **Nothing carries provenance.** Every weakness on `/progress` is *inferred* by a detector.
   There is no way to record "the player agreed to this", which is the entire value here.

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
- **A mapping table** from the other three vocabularies onto it, stored as data, not code
  branches. Unmapped legacy ids stay unmapped and are excluded rather than guessed.
- **Write the accepted cause into the profile** on reflection submit: the `selected_option_id`
  (one of the 19 already in `reflect_constants.py`), the fundamental, the mechanism, the
  `event_id`, and `source: player_accepted`.
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
- **Migrating the 229 legacy `user_concept_understanding` ids.** They are mapped where a mapping
  is obvious and otherwise left alone. No backfill, no deletion.
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

**Q1. Which vocabulary wins where a mapping is ambiguous?**
Why unresolved: `topic_key` has 7 values; the legacy store has 229. Some legacy ids
(`TAC_HANGING_PIECE`) map cleanly to `piece_safety`; others (`DEF_WALK_KING`, `knight_on_rim`)
do not obviously belong to any of the 7.
Unblocking step: list every legacy id against the 7 fundamentals and mark the residue
explicitly unmapped. One pass, reviewable as a table.

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
Unblocking step: inspect the `calculation.*` concepts against the 7 topic_keys before coding.

---

## 7. Pre-code requirements

1. **Mohit signs off on this document.** Hard gate.
2. **Q1 answered** — the legacy-id mapping table exists and is reviewed, with the unmapped
   residue named.
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

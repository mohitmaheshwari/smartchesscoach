# Reflection as Accepted Evidence — Scope

**Status:** SIGNED OFF 2026-09-05. V1 implementation in progress.
**Date:** 2026-09-05
**Feature name:** `reflection_accepted_evidence`

---

## 0. Existing surfaces audit

### What already touches this need

| Surface / store | What it already provides | Rows / users |
|---|---|---|
| `/progress` (`UnifiedProgress.jsx`) | "Currently working on" → "Also tracking" → "You beat these" — synthesised in ONE frontend `useMemo` (lines 249-485) from `/progress/narrative`. **Correction: this page does NOT read `user_active_focus` or `focus_bridge` at all.** `get_progress_narrative` builds `sections["weaknesses"]` from `problem_lifecycle` + `cognitive_gap`. The original audit row below mis-attributed the page to the focus system, which is why the first draft's render plan did not connect. | live page |
| `user_active_focus` + `focus_bridge` | The one thing a player is working on. Feeds Play-with-Coach, greetings, HomePage FocusCard and dashboard v2 — **not** `/progress`. | 273 / 53 |
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

### Decision: **EXTEND the surface, but NOT the store** (revised after the pre-code audit)

The original decision was a flat EXTEND: put the accepted cause into `user_active_focus` and let
the existing model carry it. The audit showed that specific extension is unsafe — a second active
row breaks a single-focus invariant enforced by an unsorted `find_one` across five consumers, and
leaks into an unfiltered read in `training_advanced.py:1553`.

So the revision is narrower and, I think, more honest:
- **Store:** the accepted cause gets its **own collection**, keyed by `event_id`, carrying
  provenance. It does not become a second `user_active_focus` row.
- **Surface:** still no new page. `/progress` remains the one place a player sees their weaknesses;
  the accepted cause is joined into the existing `sections["weaknesses"]` payload at render time.

That keeps the thing worth keeping from EXTEND — no third weakness surface — while not welding
player self-reports into a collection whose consumers all assume detector-inferred rows.

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

Three states for the bottom line, and only these three — **though V1 renders only the first**, because
the transfer verdict it would need is not reusable (see Section 3):

- `not enough games yet to say if it's improving` — fewer than the transfer window
- `still happening — 3 times in your last 10 games` — recurring
- `you've stopped doing this — 0 times in your last 10 games` — improved

**In the reflection prompt itself, nothing changes.** The question, options and timing are
already right. This feature is about what happens to the answer.

**When the player has NOT told us anything**, the card reads exactly as it does today. No
regression, no empty provenance row.

---

## 3. In scope (V1)

- **One canonical fundamentals vocabulary: the topic universe in
  `primary_weakness_picker.IMPACT_TABLE_BY_BAND`.** Two earlier drafts of this line were wrong and
  the correction matters, so it is recorded rather than quietly edited:
  - The dotted reflection id is *not* reliably `<fundamental>.<mechanism>` — that holds for
    `piece_safety.simple_hang` but not for `calculation.*` (Q4). The prefix is a hint, not a spine.
  - The spine is *not* "the 7 `topic_key` values" either. Those 7 are simply the values that
    happen to exist in `user_active_focus` today. The **code** can write 12: the 11 keys in
    `IMPACT_TABLE_BY_BAND` (`piece_safety`, `king_safety`, `missed_tactic`, `tactical_oversight`,
    `calculation_depth`, `piece_activity`, `pawn_structure`, `opening_knowledge`,
    `endgame_technique`, `threat_awareness`, `punish_blunders`) plus `time_management`, which
    `primary_weakness_picker.py:732` appends as a candidate outside the band table.
  Binding the mapping to observed data rather than to the writable universe would have produced a
  table that silently stops matching the moment a new topic is picked. The mapping targets the
  writable universe.
  **Known sprawl, deliberately not "fixed" here:** at least two other topic dictionaries disagree
  with it — `TOPIC_TO_MOMENTS_KEY` (11 keys, e.g. `fork_misses`, `neglecting_development`) and
  `focus_area_badges._TOPIC_BADGE` (9 keys). V1 does not add a fourth; it maps onto the writable
  universe and leaves reconciliation as its own piece of work.
- **One `fundamental` field added to each `TAG_DEFINITIONS` row**, derived from the predicate it
  already declares. Extending the existing registry rather than adding a parallel mapping file —
  the registry is already the canonical quick-tag authority that builds the options.
- **Write the accepted cause into the profile** on reflection submit: the `selected_option_id`
  (one of the 21 in `QuickTagId`), the fundamental, the mechanism, the `event_id`, and
  `source: player_accepted`.
- **Three tiers, not two.** An earlier draft said "an option without a predicate is a
  self-reported state" and listed 5. There are **7** predicate-less tags, and two of them are the
  non-answers — so "no predicate" must never be used as the test for "self-reported state":
  - *board-anchored* (14 tags, 9 predicates) — carries a fundamental and can be measured.
  - *self-reported state* (5: `thought_winning`, `felt_danger`, `wanted_to_finish`,
    `rushed_conversion`, `played_fast`) — recorded and shown, never measured, never called
    improved or still-recurring.
  - *non-answer* (2: `not_sure`, `none_of_these`) — recorded as "asked and declined", never a
    cause of any kind. `REQUIRED_ESCAPE_IDS` in `review_reflection_service.py:19` already names
    exactly this pair; use that constant rather than re-listing them.
- **`not_sure` and `none_of_these` are never written as a cause.** They are the player declining
  to answer. Counting them as accepted evidence would be the worst failure this feature could
  have — and this is not hypothetical: of the 3 reflections that exist, the selected options are
  `thought_piece_safe`, `thought_piece_safe`, `not_sure`. **One in three is already a non-answer.**
- **Filter `user_active_focus` on `type`, and handle `type: None`.** 39 rows are strengths (all
  with `topic_key: None`), and 8 more carry `type: None` with a real `topic_key`. A `!= "strength"`
  filter keeps those 8, which is the intent — but the null must be handled explicitly rather than
  relied on.
- **Provenance is first-class.** Every weakness the profile holds carries `player_accepted` or
  `detector_inferred`. Nothing is silently merged.
- **Misconception is orthogonal to fundamental.** `thought_piece_safe` already appeared under two
  different concepts in one game — the model must express "one habit, two fundamentals" rather
  than two weaknesses.
- **~~Feed `focus_bridge`~~ — CUT FROM V1. Writing a player-accepted row into `user_active_focus`
  would corrupt existing consumers.** Two verified reasons:
  - `routes/training_advanced.py:1553` reads `find_one({"user_id", "status": "active"})` with **no
    `type` filter and no sort**. A new row type leaks straight into the Lab Coach's-Pick selection.
    This is the same bug class already recorded for strength rows.
  - `focus_bridge.get_active_focus_bundle` names five consumers (session goal, session greeting,
    coach game session, HomePage FocusCard, dashboard v2), all of which assume exactly one active
    weakness row. The invariant is enforced by an unsorted `find_one`, not a unique index, so a
    second active row makes "the user's focus" non-deterministic across every one of them.
  The accepted cause therefore lives in **its own store** in V1 and is joined at render time. It
  never becomes a second active-focus row.
- **~~Reuse the Phase 8 transfer verdict unchanged~~ — CUT FROM V1. It cannot be reused, and the
  earlier claim that it could was wrong.** `build_phase8_journey_projection(db, user_id)`
  (`phase8_release_evidence.py:491`) takes **no parameter naming what is measured**. It is a
  hardcoded singleton for one detector: it filters on the module constants `QUALITY_ID`
  (destination-safety), `FOCUS_KIND = "piece_safety/destination_safety_exact"` and `PIC_SKILL_ID`,
  and gates on `is_authorized(QUALITY_ID, PLAN)` — the single PLAN-grade entry in the whole
  authorization registry. A player-accepted cause cannot enter it without parameterising the
  module and granting a second PLAN authorization, and PLAN grade demands board-verified evidence
  that a self-report by definition is not.
  So V1 stores the accepted cause and shows the raw count; the "is it improving?" verdict is a
  separate piece of work with its own scope. The three-state line in Section 2 therefore renders
  only `not enough games yet` in V1 — which is honest, since with 3 reflections in the database it
  is also true.
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
3. The stored cause carries enough to measure later — `event_id`, fundamental, mechanism, tier and
   `source: player_accepted` — verified by reading the row back, not by a verdict. (Replaces the
   original criterion, which required the Phase 8 verdict to run on it. That is not achievable in
   V1: the verdict is a hardcoded singleton for one detector. Keeping the old criterion would have
   made V1 fail on a dependency it was never going to have.)
4. A player with no reflections sees `/progress` exactly as it renders today — no empty rows, no
   regression. Verified against a second pilot user.
5. Zero cases where a misconception the player did not select is attributed to them. This is a
   correctness gate, not a metric.

Deliberately **not** a success criterion: engagement, reflection count, or improvement rate.
Those are outcomes of launching, not of this architecture.

---

## 6. Open questions

**Q1. Where do the 9 predicates land among the 7 fundamentals? — RESOLVED, one call left**

Mapped from each tag's player-facing label rather than from the predicate name:

| predicate | tags | fundamental |
|---|---|---|
| `user_piece_left_hanging` | "I thought my piece was safe" / "I thought it was protected" | `piece_safety` |
| `time_pressure_detected` | "Time pressure" | `time_management` |
| `opponent_has_winning_capture` | "I missed a capture threat" | `threat_awareness` |
| `user_ignored_forcing_reply` | "I missed a threat" / "I thought I had time" / "I underestimated counterplay" | `threat_awareness` |
| `simple_tactic_missed` | "I ignored forcing sequence" | `missed_tactic` |
| `opponent_has_immediate_check` | "I didn't see the check" | `threat_awareness` *(not `king_safety`: the failure is not noticing a forcing move, not a structurally weak king)* |
| `user_attacked_instead_of_defending` | "I attacked and ignored his threat" | **excluded in V1** — the player says they *saw* the threat and chose to attack anyway, so this is a priority failure, not an awareness one, and none of the 7 names it. Filing it under `threat_awareness` would assert the player failed to notice something they just told us they noticed. Mislabelling the cause is the exact harm this feature exists to prevent, so it is excluded rather than guessed, and recorded as a known gap. |
| `user_defended_phantom_threat` | "I defended something that wasn't threatened" | **excluded** — a false-positive habit; none of the 7 covers seeing threats that aren't there |
| `is_opening_phase` | "I was following opening idea" | **excluded** — a phase marker, not a weakness |

So **6 of 9 map cleanly and 3 are excluded** rather than guessed. Exclusion is not a gap to be
filled later by picking the nearest label — it is the fail-closed behaviour this feature requires.
A predicate with no honest fundamental produces no accepted cause at all.

**Q2. Should an accepted cause override a detector-inferred focus? — RESOLVED: it leads, it does
not replace**

V1 shows **both** and leads with the accepted one. It never deletes, downgrades or overwrites a
detector-inferred focus.

Why this way: overriding is irreversible in effect. Once the inferred cause is gone we can no
longer tell whether the player's self-report was right. Keeping both preserves the disagreement,
and the disagreement is itself the signal worth having — a player who says "I didn't see the
attacker" while the detector says king safety is telling us something about their self-model.
Overwriting would destroy that comparison before there is enough data to run it.

**Q3. How many accepted events before the profile treats it as a habit?**
Why unresolved: needs a distribution that does not exist yet.
Unblocking step: deferred to `/lock-via-data` after the pilot produces reflections. V1 shows the
raw count ("You told us this twice") rather than a threshold verdict.

**Q4. Does `calculation.*` map to an existing fundamental? — RESOLVED: no**

The two real `calculation.*` rows are `calculation.verified_stored_line` and
`calculation.legal_material_loss`. Both carry `quality_id: review:verified_single_game_cause` and
`canonical_source: None`, unlike `piece_safety.simple_hang` which carries
`gap:piece_safety:simple_hang` and `personal_curriculum.piece_safety.v1`.

"calculation" is **not** one of the 7 `topic_key` values, so the prefix does not resolve to a
fundamental. That is what breaks the spine claim in Section 3. Two of the three stored reflections
are therefore unmappable by prefix — the predicate table is what makes them mappable, via the
option the player actually selected (`thought_piece_safe` → `user_piece_left_hanging` →
`piece_safety`), regardless of which concept the event was filed under.

**Rule this settles:** where the reflection `concept_id` prefix and the tag predicate disagree, the
**predicate wins** — it is tied to the option the player chose, and it resolves for every row.

---

## 7. Pre-code requirements

1. ~~**Mohit signs off on this document.**~~ — DONE 2026-09-05.
2. ~~**Q1 answered**~~ — DONE: the 9-row predicate table is in Section 6; 6 map, 3 excluded.
3. ~~**Q4 answered**~~ — DONE: `calculation.*` does not map; the predicate wins over the prefix.
4. ~~**Q2 answered**~~ — DONE: the accepted cause leads, the inferred one is kept. No overwrite.
5. ~~**The pilot cohort is enrolled**~~ — DONE 2026-09-05: 39 real non-admin users in cohort
   `phase8_release_rescue_2026_09`, all with an analyzed game and an active non-strength focus,
   access granted 39/39. So success criteria 1–4 can be verified against real accounts rather
   than fixtures. (A 40th is blocked by a duplicate super-admin user doc sharing one email; the
   synthetic `verify@chessguru.ai` account is paused and must never be counted — its games are
   clones of the founder's.)
6. **`/audit-pre-code` run** once 1–5 are true. ← the only remaining gate.
7. Q3 stays open by design and goes to `/lock-via-data` after the pilot, not before code.

---

## Why this is worth building before launch

Not live yet is the argument *for* this, not against it. The reflection record is already
well-formed — event, concept, quality grade, selected option, elapsed time, answered-before-reveal.
What is missing is anywhere for it to land. Building the landing place after users arrive means
their first weeks of accepted evidence are counted and discarded, which is exactly what happens
to the three reflections in the database today.

Thresholds need a distribution first. Architecture does not.

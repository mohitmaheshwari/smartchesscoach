# The coaching loop, for every concept

**Status:** scope, 2026-10-20. No code written.
**Supersedes:** `phase1_lesson_evidence_review_scope.md`, which scoped the loop for one
concept. That document stays valid as the detail of WS0–WS3; this one is the frame it
sits in.
**Founder direction:** *"obviously chessguru has to work for several concepts with the
loop, so that's the overall scope"* — plus loop tracking.

---

## 1. What "the loop works for concept X" means

Testable definition, five stages. A concept is **loop-complete** only with all five. Any
missing stage breaks the chain, and the product today has concepts missing each of them.

| # | stage | the question | where it lives |
|---|---|---|---|
| 1 | **Detect** | can we find X in a real game, reliably enough to say so? | detector + `detector_quality` grade |
| 2 | **Plan** | can X become someone's current priority? | `user_active_focus`, the picker |
| 3 | **Teach** | is there content that teaches X interactively? | lesson content, `learning_sessions` |
| 4 | **Practise** | is there a pool to drill X? | puzzle pools |
| 5 | **Observe & track** | do we see X applied in a *later real game*, and record it? | `lesson_result.application`, mastery state |

Stage 5 is the one that makes this a coach rather than a dashboard, and it is the stage
the product already does best — and then discards (see §3.1).

## 2. Measured coverage, today

Identity space: **70 `detector_quality` authorizations**. The family lesson evidence
actually uses is `gap:*` — 16 ids, of which **9 are PLAN grade** (the lock's highest bar:
Caption plus 200 fires, 60% recall, 30 true negatives) and 2 are CAPTION.

| concept family | 1 Detect | 2 Plan (focus rows) | 3 Teach | 4 Practise (puzzles) | 5 Evidence |
|---|---|---|---|---|---|
| **piece_safety** | CAPTION ×2, PLAN ×1, SHADOW ×1 | 219 (34 active) | yes | 4,707 | **5,765 events** |
| missed_tactic | **PLAN ×4**, SHADOW ×1 | 11 (9 active) | no | 3,726 | **0** |
| king_safety | **PLAN ×1**, SHADOW ×1 | 37 (8 active) | no | 151 | **0** |
| time_management | **PLAN ×3** | 27 (2 active) | no | **0** | **0** |
| opening_knowledge | SHADOW ×2 | 0 | yes (41 publishable) | 143 | **0** |
| endgames | SHADOW ×26, CAPTION ×3 | 0 | yes (20 publishable) | 12 | **15 events** |
| calculation_depth | **none** | 0 | no | **47,319** | **0** |

Lesson evidence, in full — only two ids have any:

| gap id | events | outcomes |
|---|---|---|
| `gap:piece_safety:destination_safety_exact` | 5,153 | 3,595 applied / 1,535 missed |
| `gap:piece_safety:simple_hang` | 612 | **0 applied** / 607 missed |

That second row is its own finding: `simple_hang` has recorded 607 failures and **not one
success**. A concept that can only ever be failed cannot show improvement, so it is unfit
to carry a progress claim in its current form, independent of everything else here.

## 3. There are three different breadth failures, not one

Treating "make it work for more concepts" as one task would produce the wrong work. The
measurements separate it into three, each needing a different fix.

### 3.1 Failure A — detected and planned, but never taught (missed_tactic, king_safety, time_management)

Eight PLAN-grade gap detectors, all reaching the plan surface (75 focus rows between
them, 19 currently active), and **zero** lesson content, so zero evidence. These concepts
can already be found and prioritised; a player is told this is their weakness and then
there is nothing to study.

**Fix: author content.** Not engineering. The detectors already clear the lock's highest
bar, which is the expensive half.

**Exception worth stating:** `time_management` has three PLAN detectors and zero puzzles,
and puzzles cannot train clock use. It needs a different teaching form entirely
(pacing exercises against a clock), so it should not be lumped in with the other two.

### 3.2 Failure B — taught, but never observed in later games (endgames, openings)

20 publishable endgame lessons and 41 publishable openings, with content authored and
verified — and 15 lesson events in total. The endgame detectors that would notice a player
applying the lesson in a real game are 26-of-29 SHADOW, and measured earlier at near-zero
fire rates. So a player can be taught the Lucena position and the system will never see
them use it.

**Fix: engineering, specifically stage 5 for authored content.** Each authored lesson needs
an application observer — a detector that recognises the taught idea occurring in an
organic game. Where a geometric detector is not feasible, the honest alternative is to
measure practice transfer rather than claim game transfer, and to say which one is being
shown.

### 3.3 Failure C — practised, but not a concept the system knows (calculation_depth)

47,319 puzzles, the single largest pool in the product, serving a label with **no gap
detector, no focus rows and no lesson content**. It cannot enter the loop at all; it is
drill supply attached to nothing the coach can diagnose or track.

**Fix: a decision, not a build.** Either `calculation_depth` becomes a real concept with a
detector and content, or that pool is re-labelled against concepts that exist. Leaving
47k puzzles pointed at a non-concept guarantees practice that no progress measure can read.

## 4. The keystone, unchanged: one concept identity

From the Phase 1 revision, and it gates everything above. Six vocabularies that do not
meet:

| vocabulary | ids | example |
|---|---|---|
| `detector_quality` | 70 | `gap:piece_safety:simple_hang` |
| mastery (`user_concept_understanding`) | 261 | `DEF_MOST_ATTACKED` |
| observed (`move_observations`) | 63 | `destination_safety_exact` |
| focus (`user_active_focus`) | 7 | `piece_safety` |
| `pattern_catalog.json` | 35 | `missed_mate` |
| lesson ids in use | 5 | `piece_safety.simple_hang` |

Lesson ids ∩ mastery ids = **zero**; all 995 mastered pairs sit on ids with no lesson.

**Adopt `detector_quality_id` as canonical** — it is already the authorization key *and*
already carried on lesson evidence at `lesson_result.application.detector_quality_id`, the
only identity an authority and an evidence record already agree on. Derive the others from
it. Do not author a seventh mapping file.

Note the one real cost of this choice: `move_observations` ids (63) and mastery ids (261)
are both richer than the 70 authorizations, so some will not map. Those are not concepts
the loop can track, and saying so is better than inventing a parent for each.

## 5. Loop tracking — how we will know it works

The founder asked for tracking explicitly. It is a per-concept report, not a dashboard,
and it is the acceptance test for this whole scope.

**Per concept, the five stage flags** from §1, plus the conversions between them:

| measure | definition |
|---|---|
| detect rate | fires per 100 user moves, by grade |
| plan reach | distinct users with an active focus on it |
| teach reach | distinct users with ≥1 lesson event |
| practise reach | distinct users with ≥1 attempt |
| **application rate** | `applied / (applied + missed)` on organic games |
| **transfer delta** | application rate after first teaching − before, same user, same concept |

`transfer delta` is the only one that answers the vision's actual question. It needs
`occurred_at` ordering against the teaching date, which the ledger already carries.

Three rules for this report, each from a mistake already made here:

1. **Denominators, never counts.** `applied / offered`, never "applied 3,595 times".
2. **A concept with no failures and a concept with no successes are both unfit** to carry
   a progress claim. `simple_hang` (0 applied / 607 missed) fails this today.
3. **Separate practice transfer from game transfer** and label which is shown. Puzzle
   success is not game understanding.

Where it lives: one script in `backend/scripts/`, the pattern used by
`what_a_real_user_sees.py`, runnable per concept and per user, with the three named
Phase-5 users as its fixture.

## 6. Priority order, with reasoning

1. **WS0 — concept identity.** Gates everything. Nothing else can be verified without it.
2. **Loop tracking report (§5).** Second, not last, deliberately: it is how every later
   phase gets judged, and building it early means each concept closed is provably closed.
3. **Close one family end-to-end that is NOT piece_safety** — `missed_tactic`. Chosen
   because it is the cheapest complete loop available: 4 PLAN detectors already exist,
   3,726 puzzles already exist, 9 active focus rows already exist, and only stage 3
   (content) is missing. One concept family proves the pattern; proving it on
   `piece_safety` would prove nothing, since that is the one already wired.
4. **Then king_safety** (same shape, thinner puzzle supply at 151).
5. **Stage 5 observers for authored endgame content** (Failure B) — engineering-heavy, and
   it unlocks 20 lessons at once.
6. **Decide `calculation_depth`** (Failure C) — a decision that can be taken at any point
   and should not block the above.
7. **`time_management`** last of the detected set, because it needs a teaching form that
   does not exist yet.

Phase 1's WS1 (review queue) and WS2 (mastery reads reviewed evidence) run alongside 1–3;
they are how evidence becomes admissible, and they are detailed in the Phase 1 scope.

## 7. Not in scope

- **Pillar Five retrieval** (teaching from other players' games). Separate, later, and
  dependent on this loop existing first.
- **New detectors** beyond stage-5 observers. 36 of 48 concept detectors are SHADOW; the
  constraint is verification, not supply.
- **Re-grading or re-authoring existing content.**
- **Opening breadth** (38 of 79 openings unpublishable) — a content backlog, tracked
  separately.

## 8. Verification

Each item gets a positive and a negative control, because several conclusions in this
document survived only until the negative control ran.

1. **Loop-complete is provable per concept.** For the chosen family, assert all five stage
   flags true and a non-zero application rate — and assert the same report shows a
   *missing* stage for a family that has one, so the report can fail.
2. **Non-zero delta before building.** For each concept closed, `transfer delta` must be
   computable and must differ from the pre-teaching baseline. If identical, the loop is not
   closed regardless of how the flags look.
3. **No identity regressions.** After WS0, every id currently resolvable must still
   resolve; the count of unmappable mastery ids must be *reported*, not silently dropped.
4. **Review stays stratified.** Per the Phase 1 revision, one event per (user, concept)
   pair round-robin — the largest pair holds 1,405 events.

## 9. Decisions needed

1. **Content authoring for `missed_tactic` and `king_safety`** — who writes it? This is
   the critical path for item 3, and it is authoring, not engineering.
2. **`calculation_depth`**: promote to a real concept, or re-label 47,319 puzzles?
3. **`simple_hang` has zero recorded successes.** Is the detector only capable of firing on
   failure? If so it needs a success branch before it can carry progress.
4. **Unmappable ids under WS0** — 261 mastery ids against 70 authorizations. Report and
   retire the remainder, or keep two tiers of concept?
5. **`time_management` teaching form** — pacing drills are a new surface. In or out?

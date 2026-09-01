# Personalized Game Review Coach — Phase 0 Data Lock

**Date:** 2026-09-01  
**Status:** LOCKED for Phase 1 contracts; behavioral thresholds remain explicitly unclaimed  
**Scope:** `docs/personalized_game_review_coach_scope.md`  
**Spec:** `docs/personalized_game_review_coach_spec.md`  
**Raw aggregate snapshot:** `backend/data/corpus_snapshots/personalized_game_review_phase0_2026-09-01.json`

## 1. Decision summary

Phase 1 may begin with these facts locked:

1. `MoveTeachingDecision` remains the only per-move teaching authority. The new review layer may organize verified decisions; it may not rediscover chess truth.
2. Detector authorization is a hard admission gate. Caption-grade may explain one position. Plan-grade is required for recurrence, prescription and mastery claims.
3. The current production bottleneck is authorization, not raw signal volume. Only `gap:piece_safety:simple_hang` is Plan-grade.
4. `simple_hang` is useful longitudinally but sparse within one game: it reaches 96.4% of observed users over history and only 13.4% of games.
5. `backend/data/coaching/endgame_theory_tree.json` is the canonical endgame lesson source. The legacy `backend/data/endgames.json` format becomes an adapter target, not a second authority.
6. Opening content remains owned by `opening_curriculum.json` behind `opening_unified_source`. Trap content remains owned by `traps.json` behind `trap_library`.
7. Reflection options are a backend teaching contract. The frontend must render supplied options and must stop inventing chess interpretations.
8. Historical reviews regenerate lazily on read first. No bulk backfill is authorized by this lock.

The following numbers are deliberately **not locked**:

- final review moment count;
- final reflection question count;
- planner scoring weights;
- mastery transition counts;
- retention or recovery thresholds.

Those are not omissions. Production currently contains only three learning sessions and zero reflection sessions, so claiming behavioral thresholds would be invented precision.

## 2. Measurement method and privacy

Production measurements used the credential-free SSH/container method in `docs/production_db_access.md`. Credentials stayed inside the running backend container. Queries returned only aggregate counts and field names.

The versioned snapshot contains:

- no user IDs;
- no game IDs;
- no FENs;
- no moves;
- no credentials.

The production database is live. The initial observation count was 437,462 and the later detector query saw 437,545. This small difference is expected ingestion, not nondeterminism.

Local content validation used the checked-out JSON sources plus `python-chess` legality checks. File SHA-256 values are recorded in the raw snapshot so the evidence can be reproduced against the same inputs.

## 3. Production corpus

| Measure | Count |
|---|---:|
| Users | 120 |
| Games | 14,542 |
| Game analyses | 13,877 |
| Stored V5 reviews swept | 13,630 |
| User moves in V5 sweep | 437,022 |
| Move observations at detector query | 437,545 |
| Learning sessions | 3 |
| Reflection sessions | 0 |

The corpus is large enough to measure structural opportunity and detector reach. It is not large enough to infer how many questions users will answer, how much review they will finish, or how many successful applications prove mastery.

## 4. What one current review contains

Across 13,630 stored V5 reviews:

| Per-game signal | Median | p75 | p90 | Games with zero |
|---|---:|---:|---:|---:|
| User mistakes | 5 | 8.75 | 13 | 5.2% |
| Raw teaching moves | 11 | 16 | 22 | 0.1% |
| Raw principle/shape-rich moves | 23 | 31 | 41 | 0% |
| Structurally reflection-eligible moves | 2 | 3 | 4 | 25.9% |
| Positive demonstrations | 12 | 17 | 23 | 0.4% |
| Raw opening events | 28 | 40 | 55 | 5.3% |
| Raw trap events | 0 | 0 | 0 | 97.6% |
| Raw endgame events | 3 | 13 | 24 | 39.7% |
| Legacy selected moments | 0 | — | 0 | 99.1% |
| Legacy personal connections | 0 | — | 0 | 99.1% |

The raw review is not short of data. It is short of one verified selection path that turns the data into a coherent coaching conversation.

Raw principle, shape, phase, opening and endgame fields are **candidates**, not automatically valid player-facing lessons. Authorization and source-specific proof still apply.

## 5. Detector authorization and real reach

The authorization registry has 12 explicit entries:

| Grade | Count | Meaning |
|---|---:|---|
| Plan | 1 | May drive diagnosis, prescription and mastery |
| Caption | 0 | May explain a position only |
| Shadow | 6 | Measure, but do not claim to the player |
| Disabled | 5 | Known unsafe; do not execute in player paths |

Unknown IDs fail closed to Shadow.

The only Plan-grade ID is:

`gap:piece_safety:simple_hang`

Its production reach is:

| Measure | Result |
|---|---:|
| Events | 2,087 |
| Games affected | 1,825 / 13,665 (13.4%) |
| Users affected | 54 / 56 (96.4%) |
| Median events in an affected game | 1 |
| Games with 2+ events | 1.6% |
| Games with 3+ events | 0.3% |

### Lock

`simple_hang` can support “this keeps happening to you” and a piece-safety learning plan when the player’s history satisfies the existing recurrence contract.

It cannot be treated as the entire game review intelligence layer. A rich review needs independently verified opening, trap, endgame, positive-play and future promoted-detector events.

### Rejected alternative

Admitting all stored principles or shapes because they appear frequently would make the UI look full, but would bypass `detector_quality.py` and turn unreviewed hypotheses into coaching claims. That is rejected.

## 6. Canonical chess-content owners

### Openings

Canonical content:

- `backend/data/opening_curriculum.json`
- consumer boundary: `backend/services/opening_unified_source.py`

Measured content:

- 79 entries;
- 28 with a main line;
- 25 with variations;
- 24 with critical positions;
- 23 with middlegame plans;
- 23 with endgame tips;
- 14 with demands.

The other opening lookup, naming and tree services are consumers or migration candidates. They may not become new authoring authorities. Phase 2 must route new Game Review reads through the unified source.

### Traps

Canonical content:

- `backend/data/traps.json`
- consumer boundary: `backend/services/trap_library.py`

Measured content:

- 28 families;
- 54 trap entries;
- 54/54 with setup;
- 54/54 with a line;
- 54/54 with an explanation.

`trap_scanner`, `trap_recognition`, `verified_opening_traps` and detector services may produce evidence. They may not define competing lesson text or stable trap identity.

### Endgames

Two sources were compared:

| Property | Legacy `endgames.json` | `endgame_theory_tree.json` |
|---|---:|---:|
| Lessons | 6 | 18 |
| Practice positions | 0 | 54 |
| Legal checked answer moves | 2 full lines | 54/54 positions |
| Invalid/illegal stored material | 4 of 6 solution lines | 0 positions |
| Structured rule per lesson | partial | 18/18 |

The illegal legacy solution lines occur in:

- rook checkmate;
- opposition;
- Lucena position;
- Philidor position.

### Lock

`backend/data/coaching/endgame_theory_tree.json` is canonical. `endgame_theory_service.py` owns public lesson resolution. `endgame_teaching.py` must eventually adapt stable legacy IDs to this source so Play with Coach does not lose content or break URLs.

No legacy lesson is silently hidden. Any unique teaching text must be migrated into the canonical lesson before the legacy file is retired.

## 7. Duplicate-authority migration inventory

This inventory distinguishes content authorities from legitimate readers.

| Domain | Current split | Phase 2 ownership |
|---|---|---|
| Per-move teaching | caption pipeline plus voice/orchestrator selection | `MoveTeachingDecision`; review planner only organizes |
| Opening knowledge | unified source plus multiple lookup/naming/tree services | `opening_unified_source` |
| Trap knowledge | one JSON library plus several scanners/recognizers | `trap_library` for content; evidence adapters for detection |
| Endgame knowledge | six-lesson legacy file and 18-lesson theory tree | `endgame_theory_service` |
| Reflection options | frontend `_generateThoughtOptions` and backend `TAG_DEFINITIONS` | backend `ReflectionPrompt` contract |
| Move intent | `move_intent_service.py` and `services/move_intent_analyzer.py` | one backend intent evidence contract |
| Learning writes | review, puzzle and play paths have separate write shapes | one idempotent learning-event adapter |

Migration rule: adapters can preserve stable IDs and response shapes, but they cannot fork chess facts, wording, thresholds or state transitions.

## 8. Reflection candidate lock

Structural candidate availability is:

| Questions required | Reviews with enough candidates |
|---:|---:|
| 1 | 74.1% |
| 2 | 51.3% |
| 3 | 30.9% |
| 4 | 16.9% |

### Lock

- The first validation compares **one** question against **two**.
- Three or more questions are rejected for V1 validation because they would exclude 69.1% of current reviews before measuring friction.
- `not_sure` and `none_of_these` are mandatory.
- Free typing is not part of the normal path.
- No final one-versus-two winner is claimed until validation sessions measure completion and coach usefulness.

## 9. Planner candidate definitions

Three planner families were considered.

### A. Raw severity ranking

Sort all mistakes by centipawn loss and take the largest.

**Rejected.** It over-selects tactical damage, ignores teaching authority, can repeat one idea and cannot distinguish “large loss” from “right lesson for this player.”

### B. Numeric weighted score

Combine severity, detector confidence, recurrence, novelty, positive evidence and chapter diversity.

**Deferred to shadow.** The inputs do not yet share a normalized `TeachableEvent` contract, and almost every detector is Shadow. Choosing weights now would optimize incomparable fields.

### C. Authorization-first constrained planner

1. Reject unsupported claims.
2. Assign eligible events to evidence-backed roles: turning point, recurring weakness, knowledge gap, positive demonstration, reflection, next action.
3. Prefer a personal recurrence connection when Plan-grade evidence exists.
4. Apply diversity and narrative selection only among admitted events.
5. Render fewer chapters when the evidence is thin.

**Locked as the Phase 1/2 architecture.** Exact caps and tie-break weights remain a Phase 3 shadow bake-off.

## 10. Mastery and learning-loop lock

The architecture may record idempotent evidence events:

- reviewed;
- reflected;
- practised;
- solved with or without help;
- applied in a later real game;
- retained after the games-played review interval.

It may not label a skill learned, applied or retained using new numeric thresholds yet.

Reason: three learning sessions cannot support a transition bake-off. Existing `personal_curriculum.py` state names and cadence contracts remain the compatibility boundary until longitudinal evidence exists.

## 11. Historical regeneration lock

Stored V5 reviews are numerous (13,630), while stored legacy personal connections and selected moments are nearly absent. Bulk rewriting all history before shadow validation would add cost and migration risk without evidence of revisits.

### Lock

- generate the new contract lazily when an eligible historical review is opened;
- keep the old stored review readable;
- version the plan and its input hashes;
- do not bulk backfill production in Phase 1;
- measure historical-review opens during the A/B before deciding on active-user backfill.

## 12. Phase 1 entry and exit gates

Phase 1 may add contracts and serializers behind `PERSONALIZED_GAME_REVIEW_COACH_ENABLED=false`.

It must prove:

1. flag-off API and DOM parity;
2. unknown detector IDs cannot enter Plan or Mastery surfaces;
3. every `TeachableEvent` carries provenance and source version;
4. canonical content IDs resolve without copying lesson facts;
5. reflection options are backend-owned;
6. repeated serialization is deterministic;
7. no database writes or visible behavior occur in Phase 1.

Phase 2 remains blocked until the Phase 1 contract review passes. Planner weights, question winner and mastery numbers remain blocked until their named experiments produce evidence.

## 13. What would change this lock

Revise this document only with new versioned evidence:

- a detector promotion packet changes authorization;
- an endgame content migration proves greater canonical coverage without invalid positions;
- reflection sessions establish a one-versus-two winner;
- planner shadow scoring plus blinded coach review establishes caps/weights;
- longitudinal application data establishes mastery transitions.

Do not revise it because a fuller UI looks better or because a threshold feels reasonable.

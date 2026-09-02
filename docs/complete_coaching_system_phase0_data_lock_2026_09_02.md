# Complete Coaching System — Phase 0 Evidence and Migration Lock

**Date:** 2026-09-02
**Status:** LOCKED — Mohit explicitly approved this evidence lock on 2026-09-02
**Architecture:** `docs/complete_coaching_system_spec.md`
**Raw aggregate snapshot:** `backend/data/corpus_snapshots/complete_coaching_system_phase0_2026-09-02.json`

## 1. Decision summary

Phase 0 answers the five questions in the architecture spec without pretending the current evidence says more than it does:

1. **Learner-model prediction is not validated.** Personal raw frequency improved precision@3 over a leave-one-player-out global list by only 0.0081, with a 95% bootstrap interval from -0.0325 to 0.0569. Its top-1 hit rate was worse. Recency and severity were materially worse.
2. **Build the next independent promotion packet for `tactic:free_piece_exact`.** It has 1,302 distinct stored proof sources, an exact legal proof family, high relevance to 600–1500 players and a simple teaching action. Fork, aligned tactics and forced mate follow. This orders review work; it promotes nothing.
3. **Transfer is measurable in principle but not yet proven in users.** v18 has 3,239 exact destination-safety opportunities, but 29 canonical shadow application events are all misses and there is no post-lesson handled cohort. No mastery count or recovery rule is locked.
4. **Legacy history is preserved, not upgraded by guess.** Twenty-nine valid `LessonResult v2` events are canonical-evidence candidates. The 400 old puzzle attempts and counter-derived “studied/mastery” claims remain historical `measurement_unknown` unless their missing provenance can be reproduced.
5. **Otter/Maia remain subordinate.** They may rank an already safe Play-with-Coach candidate set. Puzzle difficulty, findability and distractor effects remain shadow until prospective first, unassisted, rating-stamped attempts exist.
6. **No fixed duration or Elo promise.** The product may schedule a review in games played, with a calendar backstop. It may show a forecast only after prospective completion-to-transfer calibration.

These are the safe starting constraints for Phase 1. They are not a claim that the complete coaching loop is already working.

## 2. Evidence identity and privacy

The architecture was audited at `origin/working-code` `656e3374`. Production reported `f7ecace1`. The only difference is deletion of two dead frontend board components and one frontend package entry; backend measurement code is identical.

Production measurements used the SSH/container method in `docs/production_db_access.md`. Credentials remained inside `chess-coach-backend`. Every query was read-only and returned aggregates only.

Current measured corpus:

| Measure | Count |
|---|---:|
| Users | 122 |
| Games | 14,632 |
| Game analyses | 13,969 |
| Move observations | 441,048 |
| Learning sessions | 13 |
| Puzzle attempts | 400 |

No Stockfish analysis was rerun. No user, game, move, position, PGN, caption, identifier or credential is in the versioned snapshot.

## 3. Crosswalk: content is broad; proven coaching is narrow

The reproducible report `backend/scripts/report_coach_detector_capabilities.py` derives its rows from canonical registries:

| Capability | Result |
|---|---:|
| Registered concept detectors | 48 |
| Curriculum-mapped detectors | 34 |
| Personalized workspace-supported detectors | 24 |
| Player-effect state | 47 Shadow, 1 Disabled |

Content coverage:

| Domain | Publishable | Detector-covered | Curriculum-selectable |
|---|---:|---:|---:|
| Openings | 41 | 41 | 41 |
| Traps | 36 | 36 | 31 |
| Opening ideas | 19 | 19 | **0** |
| Endgames | 20 | 20 | 16 |

The broader authorization registry contains 172 quality IDs: one Plan, three Caption, 163 Shadow and five Disabled. This is not contradictory: the first report covers one execution registry; the authorization report covers every registered proof/detector namespace.

Ten concept-detector IDs have no curriculum mapping, including knight outpost, rook on an open file, rook on the seventh, luft and three opening-principle detectors. Phase 1 must make the generated `ConceptContractIndex` fail on dangling identity rather than inventing mappings at a UI call site.

### Lock

Content availability never implies Caption, Plan or Mastery authority. A concept contract may be curriculum-only or research-only. Exact ownership remains:

- concept identity: `skill_tree.json`;
- authorization: `detector_quality.py`;
- openings: `opening_curriculum.json` through `opening_unified_source.py`;
- traps: `traps.json` through `trap_library.py`;
- endgames: `endgame_theory_tree.json` through `endgame_theory_service.py`.

## 4. Predictive validity: the current profile thesis did not beat the control

The first repository script had two limitations: its corpus-wide control included future test games, and it omitted the rating-only baseline named by the architecture. Phase 0 reran the experiment with:

- chronological 70/30 train/test splits;
- at least 30 analysed games and 40 named test moves;
- leave-one-player-out global and rating-band controls using training data only;
- 5,000 paired bootstrap resamples with seed `20260902`;
- 41 eligible players.

| Predictor | Precision@3 | Exact top-1 hit | Mean lift vs global | 95% lift interval |
|---|---:|---:|---:|---:|
| Global leave-one-out | 0.8618 | **0.8537** | — | — |
| Rating-only leave-one-out | 0.8618 | 0.8293 | 0.0000 | [0.0000, 0.0000] |
| Personal frequency | **0.8699** | 0.8049 | 0.0081 | **[-0.0325, 0.0569]** |
| Personal recency | 0.7805 | 0.4878 | -0.0813 | [-0.1626, 0.0000] |
| Personal severity | 0.6992 | 0.1220 | -0.1626 | [-0.2358, -0.0813] |

Personal frequency beat the global list for five players, tied it for 32 and lost for four. Its top choice differed from global for only 19.51% of players. Median named-label coverage in the test window was 15.23%.

### Lock

ChessGuru may say it found a verified recurring focus when the applicable Plan detector and recurrence contract pass. It may **not** say the current learner model predicts a player's next weakness better than a generic baseline.

### Rejected alternatives

- Reporting 0.8699 without the 0.8618 control.
- Treating old `cognitive_gap` labels as semantic gold.
- Using recency because it sounds personal; it regressed here.
- Using summed centipawn loss as “importance”; severity was the worst predictor and centipawn loss does not identify the lesson.

The correct next predictive experiment uses promoted exact concept events, more than one Plan family and a held-out future window. Until then, prediction stays research-only.

## 5. Detector promotion bake-off

The two admitted puzzle pools contain a large offline candidate corpus. Counts below are deduplicated by stored source fingerprint:

| Candidate family | Distinct proof sources | Current grade | Decision |
|---|---:|---|---|
| `free_piece_exact` | **1,302** | Shadow | First independent Caption packet |
| `fork_with_stored_payoff` | 587 | Shadow | Second |
| `aligned_with_stored_payoff` | 362 | Shadow | Third; split pin/skewer semantics during review |
| `forced_mate_exact` | 232 | Shadow | Fourth |
| opening-plan exact decision | 220 | Shadow | Map the 19 plans before promotion review |
| `trapped_piece_exact` | 129 | Shadow | Review after the first tactical wave |
| discovered attack with payoff | 101 | Shadow | Eligible for a full Caption packet |
| back-rank mate exact | 27 | Shadow | Targeted controls required; natural sample is below 50 |
| remove-defender with payoff | 24 | Shadow | Targeted controls required |
| trap exact decision | 18 | Shadow | Targeted canonical/adversarial evidence required |

`simple_hang` has 6,440 distinct sources but is already Caption-grade and failed the Plan recall requirement. It is not selected merely because it is largest. `destination_safety_exact` is already the one Plan-grade detector.

### Why free piece is first

It combines the largest unpromoted exact proof population, direct legal verification, a concrete move/square explanation, existing puzzle supply and an obvious learner action: notice and take an opponent piece that cannot be recovered. It is meaningfully different from the active destination-safety focus: one recognizes an available win; the other prevents moving one's own piece into loss.

### Lock

The sequence authorizes **promotion-packet construction only**. The existing surface-specific bars remain unchanged. A failed packet keeps that family Shadow and does not block the next family.

Opening and trap knowledge are not removed. Their exact-decision candidates stay available as broad/generic practice while mapping and blind semantic review are completed.

## 6. Opportunity, transfer and mastery

v18 coverage for exact destination safety:

| Measure | Result |
|---|---:|
| Users | 11 |
| Games | 800 |
| Observations | 21,342 |
| Comparable legal destination-capture opportunities | 3,239 |
| Handled outcomes | 2,955 |
| Miss outcomes | 284 |
| Fully authorized exact fires | 222 across 180 games / 8 users |

Rolling opportunities:

| Window | Median | p25 | p90 | Windows with at least one | Windows with at least six |
|---|---:|---:|---:|---:|---:|
| 1 game | 4 | 2 | 8 | 85.88% | 31.38% |
| 2 games | 8 | 5 | 14 | 93.03% | 68.06% |
| 3 games | 13 | 8 | 20 | 95.64% | 81.41% |

This looks abundant, but the sensitivity check changes what may be claimed: one account supplies 625 games containing opportunities. After excluding it, only 62 such games remain across ten users. There are no verified successful post-lesson applications in `LessonResult v2`: all 29 accepted shadow results are application misses and all nine projected learners remain `new`.

### Lock

- `occurred`, `handled`, `missed`, `unclear` and `did_not_occur` remain distinct.
- No opportunity means neither success nor failure.
- A handled row is raw outcome evidence, not proof the lesson caused or was consciously applied.
- No mastery threshold, recovery count or “lesson over” rule is locked from this corpus.
- Phase 2 must first record lesson chronology, assistance, version fingerprints and distinct-position identity prospectively.

### Rejected alternatives

- “Two solved puzzles means learned.”
- “Three clean games means improved” without a comparable-opportunity denominator.
- Treating 2,955 historical handled moves as post-teaching success.
- Locking a threshold from rolling windows dominated by one player.

## 7. Legacy migration

Current canonical-shaped evidence:

| Evidence | Count |
|---|---:|
| Learning-session documents | 13 |
| Users | 9 |
| Events | 40 |
| Valid shadow `LessonResult v2` events | 29 |
| Sessions with content version | 4 |
| Sessions with diagnostic version | 1 |
| Sessions with proof-contract version | **0** |
| Sessions with compatibility fingerprint | **0** |

All 29 accepted results are `application` attempts and do not promote a learner state.

Legacy puzzle attempts:

| Field | Present |
|---|---:|
| Attempts | 400 |
| Correct result | 400 |
| Timestamp | 400 |
| Time taken | 347 |
| Puzzle ID | 310 |
| Non-empty moves tried | 9 |
| Attempt ID / played UCI / first answer | **0 / 0 / 0** |
| Assistance or reveal state | **0** |
| Attempt-time rating and provenance | **0** |
| Model/proof/admission version | **0** |
| Content/grader/source-event version | **0** |

The earlier full legacy census found 7,613 skill records, only 187 with auditable evidence. Counters such as seen/correct/wrong, `learned_at`, acknowledged and clean streak remain useful history but do not encode the canonical assistance, grader, opportunity or source-event meaning.

### Migration disposition

- **Preserve:** every legitimate record, attempt, counter and timestamp.
- **Canonical candidate:** only parseable `LessonResult v2` events whose content and compatibility contracts still match.
- **Downgrade:** old puzzle attempts and legacy status labels to `measurement_unknown`; they may inform “you studied this before,” never “you learned/proved this.”
- **Reject:** manufactured backfills of missing assistance, first answer, rating, event time, proof version or mastery.

## 8. Human models and exact endgames

The existing locked human-runtime evidence remains valid:

- Otter history-only: 55.7% held-out top-1, 91.6% top-5, NLL 1.351 across 3,257 moves.
- Maia-2 no-history fallback: 51.8% top-1 versus a 10.5% frequency baseline.
- Clock conditioning lost to history-only and cannot support “you rushed.”
- Fathom/Syzygy may state exact result truth only with a complete legal-move partition and matching provenance.

### Lock

| Use | Status |
|---|---|
| Rank an already-safe Play-with-Coach candidate set | Allowed behind its existing guarded flag |
| Prefer a human-likely move among exact-evaluation ties | Allowed behind the same guard |
| Decide correctness, weakness, intention or mastery | Forbidden |
| Visible puzzle difficulty or ordering | Shadow |
| Difficulty calibration from 400 old attempts | Rejected |
| Findability/distractor research | Shadow |

The blocker is now concrete: all 400 historical attempts lack first-answer identity, assistance and attempt-time rating. Phase 2's attempt-v2 contract is a prerequisite, not optional instrumentation.

## 9. Plan duration

The earlier D_live opportunity lock selected review after three measured games with a 21-day calendar backstop from 24 users. It did not authorize a claim that improvement takes 21 days.

Current exact evidence covers only 11 users, is dominated by one account and contains no prospective lesson-completion-to-transfer cohort.

### Lock

The UI may say:

> We will review this after your next three measured games. If you have not played, I will check in again in about three weeks.

It may not say:

> Go from 1100 to 1200 in 21 days.

A future duration display must be a calibrated range based on that player's game cadence, assigned work completion and observed transfer, with confidence and an as-of date. A review checkpoint can be shown now; a result date cannot.

## 10. Rival-authority migration inventory

Runtime callers that must move behind the canonical contracts:

| Rival path | Current callers |
|---|---|
| `pwc_skill_gate` | `routes/coach.py`, `routes/coach_play.py`, `routes/training_advanced.py`, `realtime_coaching_feedback.py` |
| `engine2_skill_builder.pick_next_skill` | `routes/admin.py`, `today_composer.py` |
| legacy `summarize_mastery` | `routes/training_advanced.py` |
| focus-mastery interpretations | `backend/focus_mastery_service.py`, duplicated `/missions/focus-mastery`, `coach_advanced.py` |
| direct `user_active_focus` read | `routes/training_advanced.py` |

`services/mastery_gate_service.py` remains in the repository, but no direct runtime invocation was found outside its own batch helper on the audited base. It is a retirement candidate, not a dependency to reproduce.

Migration remains adapter-first: compare old and new outputs, preserve history, then retire the old reader. Whole-file replacement or mass status rewriting is prohibited.

## 11. What this lock authorizes

After Mohit's explicit approval, Phase 1 may add only:

- the generated `ConceptContractIndex`;
- the non-lossy `VerifiedClaimSet`;
- session compatibility fingerprints;
- source, alias and authorization guards;
- default-off/shadow parity tests.

Phase 1 may not:

- promote any detector;
- change a player's focus, puzzle order, mastery, progress or visible difficulty;
- migrate production data;
- expose a human-model score;
- promise a result date;
- rerun Stockfish;
- delete a legacy authority before parity.

Mohit's explicit approval on 2026-09-02 cleared this decision gate. Phase 1 is authorized only within the boundaries above.

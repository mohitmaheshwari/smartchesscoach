# Detector promotion review — 2026-09-25

Task: "go again and see all your lichess provers and promote detectors."

**I did not promote anything, and promotion turns out not to be the blocker.**
Four of the motifs are already Caption-grade. Nothing in production calls them.

---

## 1. The headline

| | |
|---|---|
| Games with a flagged mistake | **85.5%** (342 / 400) |
| Games where a detector is *allowed* to explain one | **40.0%** (160 / 400) |
| Production gate | `DETECTOR_QUALITY_GATE_ENFORCED=true` (checked on the box) |

The detection is not missing. It runs, and the registry throws it away:

| observation | fires / 400 games | speaks in prod? |
|---|---|---|
| `missed_tactic:missed_generic_tactic` | 211 | silent |
| `king_safety` | 200 | silent |
| `piece_safety:destination_safety_exact` | 149 | **speaks** |
| `piece_safety:small_slip` | 131 | silent |
| `opening_knowledge` | 127 | silent |
| `opening_knowledge:unverified_hint` | 90 | silent |
| `missed_tactic:missed_fork` | 86 | silent |
| `piece_safety:simple_hang` | 83 | **speaks** |
| `endgame_technique:generic_endgame_slip` | 75 | silent |
| `missed_tactic:missed_pin` | 28 | silent |

Two ids carry the entire coached surface.

## 2. The provers are good

Corrected bench, Lichess theme tags, 120 puzzles per theme rated 600–1500:

| prover | theme | recall | cross-fire (raw) |
|---|---|---|---|
| `build_interference_proof` | interference | **100.0%** | fork 0% · pin 0% |
| `build_advanced_pawn_proof` | advancedPawn | **100.0%** | fork 0% · pin 0% |
| `build_forced_mate_proof` | mateIn2 | **100.0%** | fork 2% · pin 10% |
| `build_xray_attack_proof` | xRayAttack | **99.2%** | fork 0% · pin 5% |
| `build_free_piece_proof` | hangingPiece | **99.2%** | fork 1% · pin 2% |
| `build_fork_proof` | fork | **97.5%** | pin 50% · mate 44% |
| `build_deflection_proof` | deflection | 93.3% | fork 2% · pin 2% |
| `build_discovered_attack_proof` | discoveredAttack | 93.3% | fork 5% · pin 2% |
| `build_clearance_proof` | clearance | 93.3% | fork 1% · pin 6% |
| `build_attraction_proof` | attraction | 92.5% | fork 0% · pin 0% |
| `build_trapped_piece_opportunity_proof` | trappedPiece | 92.5% | fork 1% · pin 0% |
| `build_aligned_tactic_proof` | pin | 87.5% | fork 32% · mate 31% |
| `build_removal_defender_proof` | capturingDefender | 81.7% | fork 6% · pin 9% |
| `build_defensive_move_proof` | defensiveMove | 60.8% | fork 2% · pin 20% |
| `build_back_rank_mate_proof` | backRankMate | **13.3%** | fork 0% · pin 8% |
| `build_trapped_piece_proof` | trappedPiece | **0.8%** | fork 1% · pin 0% |
| `build_destination_safety_proof` | — | not measurable here | — |

## 3. Why nothing gets promoted on this evidence

`docs/detector_quality_threshold_lock_2026_08_27.md` says promotion is based on
reviewed semantic examples, *"not firing volume, implementation agreement,
engine centipawn loss alone, **or an external theme tag**."*

A Lichess theme tag is precisely what this whole bench is. Caption-grade needs
**≥95% reviewed semantic precision over ≥50 reviewed fires**, plus ≥20 true
negatives and zero critical false claims. Lichess recall cannot supply any of
that — and the lock has no recall floor for Caption-grade at all, so recall
alone can never promote.

What this bench *is* good for: deciding which detectors deserve the expensive
human review, and catching detectors that are broken.

## 4. Promotion is not the blocker — the wire is

Four of these motifs are **already Caption-grade**:

```
tactic:fork_with_stored_payoff        caption
tactic:free_piece_exact               caption
tactic:forced_mate_exact              caption
tactic:aligned_with_stored_payoff     caption
```

They produced **zero fires in 400 games.** Reason:

```
$ grep -rn "build_fork_proof" backend/services backend/routes backend/*.py
  (nothing — only the _puzzle_proof module itself, tests, and admin_* routes)
```

No production file calls any `build_*_proof`. `move_observation_deriver` has
its own weaker inline logic and never consults a prover. The good
implementation is wired to the admin review page and nothing else.

This is the same failure recorded on 2026-07-13 as *"last-wire failure is the
disease"*, and in the detector-loop skill: *"the fork proof scored 66% and
coaching had never seen a single missed knight fork."* Seven weeks on, unfixed.

### There is also an id-namespace split

Provers emit **dotted** ids; the registry holds **colon** ids. Nothing
translates between them.

```
gap:piece_safety:simple_hang   -> CAPTION   (in registry)
piece_safety.simple_hang       -> SHADOW    (prover's own id, no row)
```

Registry id prefixes: `concept:` 24, `gap:` 10, `tactic:` 7, `curriculum:` 7,
`review:` 6, `shape:` 3, `principle:` 3, `brain:` 3, `legacy_endgame:` 1.
Rows using the prover shape: **0**.

So a promotion row written against `tactic.knight_fork` would authorise nothing.

## 5. Mohit's multi-tagging point, generalised

> "a puzzle can solve multiple purposes, like for example a fork might also be
> doing check-mate."

Ruled on the board instead of by tag agreement. It held everywhere it was
tested:

| prover | vs | raw cross-fire | **true** cross-fire |
|---|---|---|---|
| `removal_defender` | fork | 7.9% | **0.0%** |
| `removal_defender` | pin | 7.1% | **0.0%** |
| `forced_mate` | pin | 12.1% | **2.1%** |
| `aligned_tactic` | mateIn2 | 32.1% | 15.0% |
| `aligned_tactic` | fork | 33.6% | 20.7% |
| `fork` (earlier) | mateIn2 | 44% | 22.5% |
| `fork` (earlier) | pin | 50% | 11.9% |

`removal_defender` and `forced_mate` are clean. `aligned_tactic` and `fork`
genuinely over-fire even after adjudication.

**Caveat, stated because it changes the reading:** the `removal_defender` rule
only checks the solution was a capture — it does not verify the captured man
was defending anything. That 0.0% is not a real adjudication. The `clearance`
row was ruled with the fork rule, which is simply the wrong rule. Treat both as
unproven, not clean. `forced_mate` (`is_checkmate()`) and `aligned_tactic`
(ray geometry) are rigorous.

## 6. Three bugs in my first bench — all mine

1. **Builder chosen by `next(n for n in dir(mod))`.** `dir()` is alphabetical,
   so `trapped_piece` was benchmarked on `build_trapped_piece_opportunity_proof`
   — a different question. I reported 96% for a function nobody asked about.
   The real `build_trapped_piece_proof` scores **0.8%**.
2. **`build_destination_safety_proof` takes `(board, move_evaluation: Dict,
   played, best)`.** My 4-arg fallback shifted every argument by one, so it
   could only ever return `None`. I reported 0.0% for the single **most active
   speaking detector in production** (149 fires). A zero needs a positive
   control.
3. **The "played" move was an arbitrary legal move.** Provers that gate on the
   played move cannot be measured this way — a Lichess puzzle supplies the
   solution, never a realistic blunder. Predicted, then tested by trying every
   legal move: `build_piece_safety_proof` went **58.3% → 91.7%**. Confirmed
   artefact. `back_rank_mate` did **not** move (13.3%), so its gap is real.

I also reported the registry as 12 rows from a regex; the API says **64**
(51 shadow, 7 caption, 5 disabled, 1 plan), and `simple_hang` is Caption, not
Plan.

## 7. Recommendation

1. **Do not touch the registry.** Promotion is not the constraint and the lock
   rejects this evidence type by name.
2. **Wire the four already-Caption-grade provers into
   `move_observation_deriver`**, behind a flag, defaulted off. This needs no
   promotion packet — the authority already exists. This is the change that
   makes a user feel the detectors.
3. **Fix the id namespace** so a prover's `concept_id` resolves to a registry
   row, or the wiring in (2) silently authorises nothing.
4. **Investigate two real defects**: `build_trapped_piece_proof` at 0.8% and
   `build_back_rank_mate_proof` at 13.3% against a repo baseline of 99.5%.
5. Human-review precision for `interference`, `advanced_pawn`, `xray_attack`
   and `deflection` on **real games** — the only evidence the lock accepts.

Items 2 and 3 need Scope-Driven sign-off before code.

## Reproducing

```bash
docker exec chess-coach-backend python backend/scripts/detector_bench/lichess_prover_bench.py
docker exec chess-coach-backend python backend/scripts/detector_bench/cross_fire_adjudicator.py
docker exec chess-coach-backend python backend/scripts/detector_bench/coverage_under_gate.py
docker exec chess-coach-backend python backend/scripts/detector_bench/true_concept_ids.py
```

All four are read-only.

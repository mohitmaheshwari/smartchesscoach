# Detector promotion review — 2026-09-25

Task: "go again and see all your lichess provers and promote detectors."

**I did not promote anything, and promotion turns out not to be the blocker.**

> **CORRECTION, same day.** Section 4 of the first version of this document
> claimed *"nothing in production calls any `build_*_proof`"*. That was wrong.
> It was grepped against a local checkout **671 commits behind
> `origin/working-code`**. At origin the four Caption-grade provers **are**
> wired — `caption_facts.py`, `verified_puzzle_builder.py`,
> `game_decryption_v5_service.py`, `shape_detectors.py`,
> `cognitive_gap_subtypes.py`. The cited gold evidence files exist at origin
> too. Every number measured **inside the container** (registry contents,
> recall, cross-fire, coverage) was run against origin-matching code and
> stands; only the host-grep conclusions were wrong. Section 4 is rewritten
> below.

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

## 4. What is wired, and what is not

Measured in the container (= `origin/working-code`), excluding the provers'
own modules, tests and `admin_*` routes:

| prover | production callers |
|---|---|
| `build_fork_proof` | 5 — caption_facts, verified_puzzle_builder, cognitive_gap_subtypes, game_decryption_v5_service, shape_detectors |
| `build_discovered_attack_proof` | 3 — caption_pipeline, verified_puzzle_builder, cognitive_gap_subtypes |
| `build_free_piece_proof` | 2 — caption_facts, verified_puzzle_builder |
| `build_aligned_tactic_proof` | 2 — caption_facts, verified_puzzle_builder |
| `build_forced_mate_proof` | 1 — verified_puzzle_builder |
| `build_removal_defender_proof` | 1 — verified_puzzle_builder |
| `build_back_rank_mate_proof` | 1 — verified_puzzle_builder |
| **`build_interference_proof`** | **0** |
| **`build_advanced_pawn_proof`** | **0** |
| **`build_xray_attack_proof`** | **0** |
| **`build_deflection_proof`** | **0** |
| **`build_clearance_proof`** | **0** |
| **`build_attraction_proof`** | **0** |
| **`build_trapped_piece_opportunity_proof`** | **0** |
| `build_defensive_move_proof` | 0 (60.8% recall — not a candidate) |

So the four Caption-grade motifs are wired. The genuine gap is **seven provers
scoring 92.5–100% Lichess recall with ≤5% cross-fire and no caller at all.**

### An id-namespace split still needs checking before wiring any of them

Registry ids are colon-prefixed; prover `concept_id`s are dotted, and a
container-side search found no translation helper:

```
gap:piece_safety:simple_hang   -> CAPTION   (in registry)
piece_safety.simple_hang       -> SHADOW    (prover's own id, no row)
```

Registry rows using the prover shape: **0**. Since the wired provers evidently
do reach captions, `caption_facts.py` must resolve authority some other way —
that path must be read before assuming a new prover inherits it.

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

1. **Work from a fresh checkout.** This one is 671 commits behind
   `origin/working-code` and it produced a false headline. See
   [[feedback_author_content_in_a_worktree_at_origin]].
2. **Do not touch the registry.** The lock rejects this evidence type by name.
3. **Rank the seven unwired provers by fires/game on real games before wiring
   any of them.** Lichess recall says a prover is right when the motif is
   present; it says nothing about how often it is present in 600–1500 games.
   Recorded precedent: promoted `discovered_attack` fires on 1.8% of games.
4. **Read how `caption_facts.py` grants a prover authority** — the dotted/colon
   split means a new prover may not inherit it.
5. **Investigate two real defects**: `build_trapped_piece_proof` at 0.8% and
   `build_back_rank_mate_proof` at 13.3% against a repo baseline of 99.5%.

Item 3 is measurement and needs no sign-off. Wiring needs Scope-Driven
sign-off.

## Reproducing

```bash
docker exec chess-coach-backend python backend/scripts/detector_bench/lichess_prover_bench.py
docker exec chess-coach-backend python backend/scripts/detector_bench/cross_fire_adjudicator.py
docker exec chess-coach-backend python backend/scripts/detector_bench/coverage_under_gate.py
docker exec chess-coach-backend python backend/scripts/detector_bench/true_concept_ids.py
```

All four are read-only.

---

## 8. Fires per real game — the ranking that actually decides (added same day)

Lichess recall says a prover is right *when the motif is present*. It says
nothing about how often it is present in 600-1500 games. Measured on 400
analysed games, 2,537 user moves at >=100cp loss. Positive control: the wired
`build_fork_proof` must fire, and does.

| prover | Lichess recall | fires/game | **% of real games** | callers |
|---|---|---|---|---|
| `build_clearance_proof` | 93.3% | 0.78 | **47.0%** | 0 |
| `build_fork_proof` *(control)* | 97.5% | 0.92 | 46.5% | 5 |
| `build_trapped_piece_opportunity_proof` | 92.5% | 0.15 | 11.5% | 0 |
| `build_advanced_pawn_proof` | 100.0% | 0.14 | 9.0% | 0 |
| `build_xray_attack_proof` | 99.2% | 0.06 | 6.0% | 0 |
| `build_deflection_proof` | 93.3% | 0.06 | 4.8% | 0 |
| `build_interference_proof` | 100.0% | 0.04 | 2.8% | 0 |
| `build_attraction_proof` | 92.5% | 0.02 | 2.2% | 0 |

**The ranking inverts.** The two 100%-recall provers (`interference`,
`advanced_pawn`) sit near the bottom in real games. `clearance`, mid-table on
Lichess, fires as often as the wired fork detector.

### The true-negative control, and why it proves less than it appears

On 6,981 user moves at <30cp loss, **every prover fired zero times**. That
looks like perfect discrimination and is not: each prover gates on
`cp_loss < 100` and returns `None` before any motif logic runs. **This measured
the centipawn gate, not the motif.** It is recorded so nobody later cites it as
precision evidence.

### Do not wire `clearance` on this number

A clearance sacrifice does not occur in 47% of 600-1500 games. The detector
itself is careful — `clearance_puzzle_proof.py` documents twelve puzzles played
out move by move, keeps a deliberate refusal, and reports 94.9% detector /
**83.0% verified** recall, matching this bench. The geometry is sound.

But it requires `pv_after_best` and walks the engine line. In a Lichess
`clearance` puzzle the clearance *is* the point; in an arbitrary blunder's best
line, one friendly piece stepping out of another's way co-occurs by accident.
Geometric truth is not a licensed coaching claim — see
`feedback_precision_vs_meaning_are_separate_audits`.

**So `clearance` is the top candidate for semantic review, not for wiring.**
Reviewing 50 of its fires on real games is the cheapest high-value next step,
and it is the one evidence type the quality lock accepts.

Added benches: `fires_per_real_game.py`, `true_negative_control.py`.

---

## 9. Correction: read `quality_id`, not `concept_id`

Section 4 said the registry and the provers live in namespaces that never meet,
and that "17 of 17 provers cannot reach a caption." **Wrong field.** A proof
bundle carries both:

- `concept_id` — dotted, semantic: `tactic.clearance`
- `quality_id` — colon, and what the registry is keyed on:
  `tactic:clearance_with_stored_payoff`

Read through `quality_id`, the namespaces match exactly and six provers reach a
player-facing surface today:

| prover | quality_id | grade |
|---|---|---|
| `destination_safety` | `gap:piece_safety:destination_safety_exact` | **plan** |
| `fork` | `tactic:fork_with_stored_payoff` | **caption** |
| `forced_mate` | `tactic:forced_mate_exact` | **caption** |
| `free_piece` | `tactic:free_piece_exact` | **caption** |
| `piece_safety` | `gap:piece_safety:simple_hang` | **caption** |
| `aligned_tactic` | `tactic:aligned_with_stored_payoff` | **caption** |
| `trapped_piece` | `gap:piece_safety:trapped_piece_exact` | shadow |
| `discovered_attack` | `tactic:discovered_attack_with_stored_payoff` | shadow |
| `back_rank_mate` | `tactic:back_rank_mate_exact` | shadow |
| `removal_defender` | `tactic:remove_defender_with_stored_payoff` | shadow |
| `clearance` | `tactic:clearance_with_stored_payoff` | shadow, **no row** |
| `deflection` | `tactic:deflection_with_stored_payoff` | shadow, **no row** |
| `attraction` | `tactic:attraction_with_stored_payoff` | shadow, **no row** |
| `interference` | `tactic:interference_with_stored_payoff` | shadow, **no row** |
| `xray_attack` | `tactic:xray_attack_with_stored_payoff` | shadow, **no row** |
| `advanced_pawn` | `endgame:advanced_pawn_with_stored_payoff` | shadow, **no row** |
| `defensive_move` | `defense:quiet_move_that_answers_a_threat` | shadow, **no row** |

There is no namespace bug and nothing to "fix" before wiring. Seven provers
simply have no registry row yet.

## 10. Clearance semantic review — it does not clear Caption grade as scoped

310 fires on real user blunders (>=100cp) across 400 games. `_locate_clearance`
walks **every** initiator ply of the stored line and records
`clearance_ply_in_line`, so the licensing question is answered from the
detector's own recorded facts:

| where the clearance sits | fires | share | |
|---|---|---|---|
| **ply 0** — the best move *is* the clearance | 208 | **67.1%** | licensed: it is the move the user got wrong |
| **ply 2** — clearance happens later in the line | 102 | **32.9%** | scenery: the user never reached this position |

**A third of fires would teach the wrong move.** At ply 2 the user's mistake was
the *first* move of the line; the clearance is downstream of a continuation they
never played. Caption-grade needs >=95% semantic precision. 67.1% is nowhere
near it, so `clearance` must not be promoted as currently scoped.

**It is fixable by a one-line gate, not a rewrite.** The proof already exposes
`clearance_is_immediate`. Restricting fires to `clearance_ply_in_line == 0`
leaves **208 fires** — comfortably past the lock's ">=50 reviewed fires" — and
every one of them is about the move the user actually played. That is the
version worth putting through human review.

### One thing to check first

Every one of the 310 fires is `onto` (the follow-up lands on the vacated
square); **zero** are `through` (a slider crossing it). The detector's own
docstring documents seven of its twelve reference puzzles as `through`, so the
positive control exists and this hard zero needs explaining before review —
either real games genuinely differ, or `_left_the_way` behaves differently on
stored PV data than on puzzle lines.

Other recorded facts: the clearance move is a capture in only 11.0% of fires
(so "win material" is rarely the real lesson), and the follow-up is +2 plies
later in 73.2% of cases, +4 in 26.8%.

Benches: `clearance_semantic_review.py`, `registry_quality_ids.py`.

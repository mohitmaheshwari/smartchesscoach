# Deterministic Teaching Intelligence — Second Data Lock

**Date:** 2026-09-14
**Status:** PROPOSED FOR MOHIT'S APPROVAL; NO PRODUCT IMPLEMENTATION AUTHORIZED YET
**Scope:** `docs/deterministic_teaching_intelligence_scope.md`
**First lock:** `docs/deterministic_teaching_intelligence_data_lock_2026-09-13.md`

## Decision 1 — the measured problem is causal teaching reach

The first implementation slice must improve the number of positions in which the rendered review teaches the verified reason, not the number of captions, detectors, labels or best moves stored internally.

The frozen 100-game development comparison found:

| Measure | Result |
|---|---:|
| Complete games reviewed blind by Codex | 100 |
| Games containing at least one candidate teaching lesson | 96 |
| Honest no-strong-lesson games | 4 |
| Candidate plies | 254 |
| Candidate plies with stored engine evidence | 249 |
| Candidate plies without stored engine evidence | 5 |
| Reusable game-family teaching opportunities | 192 |
| Opportunities causally taught by the current rendered product | 24 |
| Current causal teaching coverage | **12.50%** |
| Stored move captions | 6,372 |
| Stored caption-explanation fields | **0** |
| Stored teachable events | **3** |
| Games with a stored whole-game plan | **3** |

The product therefore has abundant text but little connected, causal teaching. The first product build must close that last wire. Internal fact availability alone cannot satisfy the release gate.

The five candidate plies without stored engine evidence remain explicitly **not measured** for consequence. They are not counted as safe, low-value or negative examples.

## Decision 2 — policy comparison

The comparison below is generated from the frozen packet, frozen blind Codex review, frozen current-system baseline and frozen semantic-coverage adjudication. An opportunity is counted once per game and required family. Same move with a different reason does not count as current coverage.

| Candidate policy | Families | Uncovered opportunities | Games reached | Players reached | Confirmed high-consequence opportunities | Maximum visible coverage if every candidate proves |
|---|---:|---:|---:|---:|---:|---:|
| Pareto winner only | 1 | 36 | 36 | 24/34 | 35 | 31.25% |
| **High-feasibility reach floor** | **4** | **73** | **61** | **30/34** | **72** | **50.52%** |
| Frequency-first top eight | 8 | 127 | 83 | 34/34 | 121 | 78.65% |
| Every high-feasibility family | 14 | 109 | 80 | 34/34 | 107 | 69.27% |
| Every proposed family | 19 | 168 | 92 | 34/34 | 159 | 100.00% |

### Selected policy

Select the **high-feasibility reach floor** for the first product implementation bundle.

A family enters this bundle only when all of the following are true in the fresh development distribution:

- deterministic proof feasibility is **high**;
- at least **eight** currently uncovered opportunities exist;
- at least **seven** distinct players have an uncovered opportunity;
- a canonical proof asset already exists that can verify the claimed consequence without an LLM.

This produces exactly four families:

1. `forced_mate_story` — 36 uncovered opportunities, 24 players, 35 confirmed high-consequence;
2. `multi_move_material_accounting` — 19 uncovered opportunities, 14 players, 19 confirmed high-consequence;
3. `queen_safety_or_greedy_capture` — 10 uncovered opportunities, 9 players, 10 confirmed high-consequence;
4. `unpunished_opponent_opportunity` — 8 uncovered opportunities, 7 players, 8 confirmed high-consequence.

Together they cover 73 currently uncovered opportunities in 61 games across 30 of 34 development players. Seventy-two of those 73 occurrences have a confirmed high-consequence candidate in the stored evidence that is available.

### Why this policy wins

- The one-family Pareto result is too narrow for the promised whole-game review. The selected bundle more than doubles uncovered opportunities addressed, from 36 to 73, and expands player reach from 24 to 30 while adding only three proof contracts.
- Frequency-first top eight reaches four additional players and 54 additional opportunities, but introduces four medium-feasibility contracts in the same release. That combines exact endgames, positive-play recognition, rook coordination and king-safety commitment before their proof boundaries are independently demonstrated.
- Every-high-feasibility includes ten long-tail families to reach four more players. That is detector-inventory growth rather than the smallest useful player-visible release.
- Every-family is rejected as an implementation batch. It makes the long tail impossible to verify and diagnose independently and repeats the code-built-but-not-reached failure.

The eight-opportunity and seven-player floors are first-release scope boundaries, not permanent definitions of value. They are the smallest measured high-feasibility bundle that reaches at least 30 of 34 development players without expanding beyond four new proof contracts.

## Decision 3 — family proof contracts

These names are research groupings. Product code must express each claim through the existing canonical fact and decision owners; this document does not authorize a parallel classifier or caption bank.

### 3.1 Forced-mate story

Teach the position as a connected forcing story rather than repeating “mate was available” on several adjacent moves.

Required proof:

- stored mate score on the relevant branch;
- legal replay to the terminal mate position;
- exact attacking and escape-square geometry needed for the explanation;
- one story anchor per continuous mating episode;
- no mate claim inferred from centipawn loss or an incomplete line.

### 3.2 Multi-move material accounting

Teach why a sequence wins, loses or merely exchanges material only after the captures, recaptures, intermediate checks and forks have settled.

Required proof:

- legal replay of both played and teaching branches;
- material counted from the same root side;
- continuation through the first settled quiet boundary using the canonical stored-line verifier;
- explicit handling of delayed recaptures and intermediate forcing moves;
- no “wins a piece” claim when the stored line stops before a legal recovery.

### 3.3 Queen safety or greedy capture

Teach the concrete decision behind a queen capture, queen exchange or queen move: what the tempting move allows, what must be preserved, and why the alternative keeps the game playable.

Required proof:

- the tempting candidate is legal and position-relative;
- every stated forcing response is legally replayed;
- material or mating payoff is settled rather than read from the first capture;
- actor identity is explicit so the player and opponent can never be reversed;
- the explanation may not say “avoid trading queens” as a universal rule. It must name the verified consequence in this position.

### 3.4 Unpunished opponent opportunity

Teach a real chance the opponent had but did not take, without rewriting history as though it happened.

Required proof:

- branch starts immediately before the opponent's decision;
- stored opponent best line and stored played line are both legal;
- the missed chance has a verified mating, settled-material or exact defensive payoff;
- visible wording is counterfactual: “They could have …, but they missed it”;
- the lesson explains what the player should notice next time without blaming them for material that was never lost.

## Decision 4 — canonical implementation boundary

After approval, implementation may extend only these existing owners:

- `caption_facts.py` for typed causal facts;
- `stored_line_verifier.py` for shared legal replay and settled payoff;
- `caption_pipeline.MoveTeachingDecision` for one complete teaching decision;
- `game_review_event_adapter.py` for authorized event projection;
- `game_review_planner.py` for ordering and the inherited three-moment cap;
- `whole_game_review_composer.py` for connected whole-game presentation;
- `detector_quality.py` for surface authorization;
- the existing opening, trap and endgame registries only when one of the selected facts needs an exact canonical identity.

Implementation must not add another general-purpose fact table, phase detector, caption renderer, principle bank, concept taxonomy or review ranker. Maia/Otter may propose or order human-plausible candidates but cannot prove any claim. No runtime LLM is permitted for chess truth or required wording.

## Decision 5 — build and validation order

The four families are implemented and graded separately in this order:

1. forced-mate story;
2. multi-move material accounting;
3. queen safety or greedy capture;
4. unpunished opponent opportunity.

For each family:

1. write the typed fact and exact proof contract;
2. add hard negatives for the known false-claim classes before rendering copy;
3. generate the player-visible event through the canonical pipeline;
4. verify replay reaches the exact claimed payoff;
5. independently review at least 50 visible claims;
6. require at least 95% semantic precision with Wilson 95% lower bound at least 85%;
7. require zero critical false chess claims;
8. keep the family Shadow when any gate fails.

After all admitted families are composed, rerun the paired current-versus-candidate 100-game comparison. The release remains blocked unless the lower bound of the player-clustered 95% bootstrap interval for useful causal lesson coverage is above zero. The sealed 34-game holdout remains unopened until the implementation and all development decisions are frozen.

The 50-claim promotion packet may draw from fresh non-holdout corpus positions that match the exact frozen family contract. It may not reuse the sealed holdout, identities, user text, current answer keys or unverified captions.

## Decision 6 — long-tail preservation

The other 15 families are **deferred, not removed or hidden from the roadmap**:

- exact endgame;
- clean or positive play;
- rook activity and coordination;
- king-safety commitment;
- passed-pawn race;
- opening purpose;
- back-rank geometry;
- defensive removal of an attacker;
- known trap or mating pattern;
- countercheck or forcing defence;
- forcing pawn tempo;
- fork or double-attack geometry;
- pin, x-ray or line geometry;
- zwischenzug or move order;
- promotion choice.

Their frozen occurrences remain evidence for the next cycle. They are not converted into generic captions, and they are not allowed to borrow authorization from one of the selected four families. After the first bundle is graded, the opportunity report is recomputed against the new rendered baseline and the next family decision returns to `/lock-via-data`.

## Critical regressions locked regardless of frequency

The following defects block release even if aggregate coverage improves:

- a line stops before a legal recapture, fork or intermediate check that removes the claimed payoff;
- a quiet check is excluded from settlement and changes the result;
- a player move is described as the opponent's move, or vice versa;
- a mating branch is captioned as merely winning material;
- a promotion is explained by a secondary attack while omitting the promotion/conversion fact;
- a counterfactual opponent chance is worded as an event that actually occurred;
- adjacent captions repeat one forcing episode as several unrelated lessons;
- a same-move but wrong-reason explanation is counted as causal coverage.

## Frozen evidence and reproducibility

| Artifact | SHA-256 |
|---|---|
| Development packet | `b9d912b1cc72fb1c928c576a70baf1b982e0cdbe08e28eb01e8a55915948af91` |
| Blind Codex complete-game review | `ae933d3445ab4a4057ea6bb5b9ecad780b191ab4fa7eccb5787a0d051af504b6` |
| Current authorized system baseline | `0bd15422c57742133701376d46c0cd2a2ab5194170890232897995bbf0692c60` |
| Current semantic-coverage adjudication | `a6d16a4ad3bb57d2e769d55e8e883f4f4882751e28e3c16e74499603bbd758ae` |
| Opportunity report | `4177d68cc6d39889e823e43ba75d0c2ca64051229f4cf6df870302c4a4dad0a4` |

The opportunity report is reproducible offline with:

```bash
cd backend
python scripts/measure_deterministic_teaching_intelligence_opportunities.py \
  --output data/corpus_snapshots/deterministic_teaching_intelligence_opportunity_report_v1_2026-09-14.json
```

It performs zero database reads, database writes, engine runs and model calls, does not open the holdout, and grants no player-facing authorization.

## Authorization boundary after approval

Approval of this second lock authorizes implementation and development-set validation of the four selected proof families through the canonical pipeline. It does not authorize:

- opening the sealed holdout before development is frozen;
- player-facing detector promotion without the per-family quality packet;
- review regeneration, migration or historical backfill;
- production flags, rollout, push or deployment;
- new families outside the selected four;
- runtime LLM chess judgment;
- a change to mastery or transfer claims.

Those remain separate, evidence-gated decisions.

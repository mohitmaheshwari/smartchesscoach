# Deterministic Teaching Opportunities — Independent Review Repair

Date: 2026-09-14
Branch: `codex/deterministic-whole-game-teaching-review-v1`
Status: v3 proof contract implemented in Shadow; blinded development recheck pending

## Independent result that blocked v2

An independent reviewer judged every one of the 250 development cases without reading detector code, implementation files or the separate answer key. All 500 displayed branches replayed legally and zero cases were structurally invalid, but the visible wording failed the quality gate:

| Family | Reviewed | True | False | Uncertain | Critical false claims | Precision | Wilson 95% lower |
|---|---:|---:|---:|---:|---:|---:|---:|
| Forced-mate story | 33 | 31 | 2 | 0 | 1 | 93.94% | 80.39% |
| Multi-move material | 165 | 130 | 35 | 0 | 4 | 78.79% | 71.93% |
| Queen safety or greedy capture | 20 | 15 | 4 | 1 | 3 | 75.00% | 53.13% |
| Unpunished opponent opportunity | 32 | 23 | 7 | 2 | 7 | 71.88% | 54.63% |

Overall: 199 true, 48 false, 3 uncertain, 15 critical false claims. The raw precision was 79.6%, with a Wilson 95% lower bound of 74.2%. No family was promoted and no authorization changed.

The submitted review was mechanically bound to the exact packet SHA and its explicit independence attestation was added to the file. No verdict or review note was changed.

Historical artifacts:

| Artifact | SHA-256 |
|---|---|
| `backend/data/detector_gold/deterministic_teaching_opportunity_independent_review_v1.json` | `fb82d49e5b93343b556bfbf08dbbb1ba8f6f07a2efffd2cf47625d7405d442ac` |
| `backend/data/corpus_snapshots/deterministic_teaching_opportunity_independent_review_score_v1_2026-09-14.json` | `ce18158f25dd90ede4f0937e7d7f8496cc56b8f5a20f294c5f117dca53d0dd8c` |

## Root causes and systemic repairs

### 1. Sequence delta was worded as total board balance

`settled_material_gain_cp` measures what material changes during a branch. It does not say whether the side is ahead or behind on the board. Phrases such as “the material stays level”, “you come out ahead” and “you finish behind” converted a correct numeric delta into a false position-wide claim.

The v3 renderer now uses the material delta visible in the displayed replay and says only:

- the shown line wins material for the relevant side;
- the shown line loses material for that side; or
- the shown line trades equal material.

When both branches win, the stronger branch says it wins more. When both lose, it says it costs less. No centipawn value is exposed.

### 2. The caption omitted the move that made its conclusion true

The old sentence printed only four moves even when the stored replay contained five. Thirteen conclusions became true only on the unprinted fifth move.

The v3 comparison no longer embeds a shortened material line in the sentence. Its claim is explicitly bounded to “the shown line”, while the replay contract supplies every stored move. Both visible and settled branches must independently show a piece-sized edge before the family is retained.

### 3. A root move was blamed for a later voluntary walk-in

Several queen and opponent captions named a later captured piece even though the learner had dozens of legal alternatives before voluntarily moving it onto the captured square.

The v3 proof contract now:

- attributes a queen loss to the root move only when the opponent captures the queen on the immediate reply;
- treats a queen root capture separately as a greedy-capture comparison;
- admits an opponent material chance only when the best root move captures immediately or leaves exactly one legal reply before the verified capture;
- stores the consequence from the admitted mechanism instead of preferring a later queen loss;
- otherwise abstains.

### 4. Mate wording exceeded the stored proof

“Kh7 stops that finish” was false because it avoided the displayed immediate mate but did not remove a deeper forced mate. The replacement says only that it “avoids the checkmate shown in this replay.”

One missed-mate case ended immediately in stalemate. The terminal-state fact is now typed. Its caption says that the opponent has no legal move and the game is drawn, then shows the checkmating alternative. The reusable cue is to confirm the opponent still has a legal move before finishing.

## Corrected development measurement

The same frozen 100 games were replayed under proof version `verified_teaching_opportunity.v3`. The repair intentionally reduced claims from 250 to 201 while retaining at least one candidate for all 34 anonymized development players:

| Family | v2 candidates | v3 candidates |
|---|---:|---:|
| Forced-mate story | 33 | 33 |
| Multi-move material | 165 | 138 |
| Queen safety or greedy capture | 20 | 15 |
| Unpunished opponent opportunity | 32 | 15 |
| **Total** | **250** | **201** |

The 49 removed claims lacked the stricter visible-payoff or root-causality proof. Seven adjacent mate descriptions remain deduplicated into one story per continuous episode.

Corrected artifacts:

| Artifact | SHA-256 |
|---|---|
| `backend/data/corpus_snapshots/deterministic_teaching_opportunity_family_measurement_v4_2026-09-14.json` | `c2282c63f2f0ba102161484f9cf963b136ae1de1d340712e77be7448e3864b8f` |
| `backend/data/detector_gold/deterministic_teaching_opportunity_blinded_development_review_v2.json` | `53aae01fffc6af6edf7e3c05fbc41b8be6179ad3943f9b6ccda6b45d90c17b92` |
| `backend/data/detector_gold/deterministic_teaching_opportunity_blinded_development_answer_key_v2.json` | `2c6b6f8aed392c44a5aefb684a63fe9f0cb2d54bd844eb029d802d398f93ea15` |

The v2 review packet is development-only and cannot promote a detector. It contains no identity, detector family, quality ID, centipawn value, internal fingerprint or answer.

## Verification

The corrected combined backend matrix passes:

```text
197 passed, 34 skipped
```

It includes exact regressions for the independently found stalemate, mate-delay, false balance, shortened-line, delayed queen walk-in, cooperative opponent line, direct opponent capture and greedy queen cases. Corpus-wide tests check all 201 candidates for forbidden position-wide material wording and enforce the new consequence-ply boundaries.

The 600–1500 voice audit found no centipawn language or unexplained advanced jargon. Every candidate ends with a reusable board action and remains inside the central caption pipeline.

## Next gate

Give an independent reviewer only:

`backend/data/detector_gold/deterministic_teaching_opportunity_blinded_development_review_v2.json`

This recheck asks whether the known defect classes are gone. It is still development evidence and cannot promote any family, even if every verdict is true. After a clean recheck, freeze the implementation and obtain fresh non-holdout evidence with at least 50 visible claims per family. The sealed holdout stays closed until all development decisions are frozen.

No player-facing authorization, backfill, migration, push, deployment, engine run, production read or production write was performed by this repair.

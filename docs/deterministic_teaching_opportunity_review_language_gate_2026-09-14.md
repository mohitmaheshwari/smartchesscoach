# Deterministic Teaching Opportunities — Language and Evidence Gate

Date: 2026-09-14

## Why this addendum exists

The independent v2 review established that the chess-truth repair was real:
200 claims were true, zero were false, one was uncertain, and there were zero
critical false claims. The reviewer also found two player-facing evidence
defects that prevented exposure:

- 146 of 201 comparisons relied on the JSON field label to distinguish the
  move that happened from the move that could have happened.
- eight rows repeated an observed claim about the same position and move.

The reviewer also corrected the evidence arithmetic. Four product families
render seven visibly different claim contracts. A large sample for one
contract may not validate the other six.

## Locked repair

The central caption pipeline now uses explicit agent and tense:

- historical branch: `You played ...` or `They played ...`;
- counterfactual branch: `You could have played ...` or
  `They could have played ...`.

The allowed-mate alternative no longer says that the move stops, avoids, or
escapes mate. It says:

> You could have played Kh7. Replay it, then keep checking for mate.

This preserves the useful alternative without claiming the position is safe.

## One observation, one evidence claim

Each comparison carries a deterministic visible-claim fingerprint derived
from:

- the canonical four-field source FEN;
- the actor;
- the move that was played;
- the historical sentence shown to the learner.

The per-game Shadow summary removes duplicate facts across product families.
The blinded packet builder applies the same identity across games before a
row can count toward a gate. Product-family labels therefore cannot multiply
one observed fact.

## Product families and visible claim contracts

The four product families remain unchanged. Their visible contracts are now
typed and scored independently:

| Product family | Visible claim contract |
| --- | --- |
| forced mate story | missed checkmating finish |
| forced mate story | allowed checkmate |
| forced mate story | stalemate instead of mate |
| multi-move material accounting | complete capture sequence |
| queen safety or greedy capture | greedy queen capture |
| queen safety or greedy capture | immediate queen target |
| unpunished opponent opportunity | opponent missed chance |

A product family passes its numeric gate only when its aggregate score and
every visible claim contract inside it pass. No populated contract can lend
evidence to a thin contract.

## Offline remeasurement

The same frozen 100-game evidence packet was replayed without database access,
engine runs, model calls, identities, or production writes.

| Measure | Result |
| --- | ---: |
| Stored positions checked | 3,775 |
| Raw proved opportunities | 208 |
| Per-game unique candidates | 194 |
| Blinded cross-game unique claims | 193 |
| Player identities exposed | 0 |
| Caption authorizations changed | 0 |

The seven unique-claim counts in the new blinded packet are:

| Visible claim contract | Claims |
| --- | ---: |
| complete capture sequence | 130 |
| allowed checkmate | 23 |
| opponent missed chance | 15 |
| greedy queen capture | 9 |
| missed checkmating finish | 9 |
| immediate queen target | 6 |
| stalemate instead of mate | 1 |

Six of seven contracts remain below the locked 50-claim minimum. The packet
states that shortfall exactly.

## Contract versions

- verified fact: `verified_teaching_opportunity.v4`
- comparison: `teaching_opportunity_comparison.v4`
- per-game Shadow summary: `teaching_opportunity_shadow_summary.v4`
- offline measurement: `deterministic_teaching_opportunity_measurement.v4`
- blinded development packet: v3 file, schema
  `deterministic_teaching_opportunity_blinded_review.v2`

The independent v2 review and its score remain immutable historical evidence
for the previous wording contract. The new v3 packet requires a fresh blinded
review before it can be used even as recheck evidence.

## Exposure decision

All four quality identities remain Shadow. This repair changes no Caption or
Plan authorization, enables no feature flag, and exposes no new player-facing
content.

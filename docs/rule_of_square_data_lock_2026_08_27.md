# Rule-of-square runtime truth - data lock (2026-08-27)

Status: LOCKED FROM SYZYGY-BACKED BAKE-OFF

## Decision

The canonical runtime fact will answer the literal race question with legal
board mutation:

- on the pawn side's turn, consider legal pushes of the critical pawn,
  including a starting-rank double push and promotion;
- on the defending side's turn, consider legal king moves, including capture
  of the pawn or an immediately promoted piece;
- the pawn side chooses a push that escapes; the defender chooses a king route
  that catches;
- the attacking king stays on its current square, where its attacks still make
  defender king moves illegal.

The search is finite because every pawn-side turn advances the pawn. This is a
deterministic chess fact, not a Stockfish score or runtime tablebase call.

V1 eligibility is exactly two kings plus one pawn. Mutual pawn races and every
position with a non-pawn piece abstain.

## Candidate bake-off

| Candidate | Result | Decision |
|---|---|---|
| A - promotion-square distance | Matched only 2/20 targeted positions where it disagreed with the widened formula. It misses interception before the promotion square. | Rejected |
| B - current square zone plus one legal king step | Matched 18/20 targeted disagreements, but failed a starting-rank double push and an equal-tempo race. | Rejected |
| C - speak only when A and B agree | Matched 10/10 initial ordinary positions, then only 31/36 eligible cases across two fresh random KPK batches. Full tablebase WDL also exposed that attacking-king play is not the same claim as an immediate pawn race. | Rejected |
| D - exact legal push-versus-king race | Enumerates the moves that define the coaching claim and handles every failure mode that broke A-C. | Selected |

No numeric distance threshold is introduced.

## Mutual-race lock

Fifteen fixed-seed K+P versus K+P positions were probed in full and with each
pawn stripped:

- exactly one single-pawn position reproduced the full WDL: 11/15;
- both reproduced it: 1/15;
- neither reproduced it: 3/15.

Because 4/15 were not attributable to one critical pawn even under this coarse
test, all mutual pawn races abstain in V1.

## Source and provenance

The measurement used the Lichess tablebase HTTP API:
`https://tablebase.lichess.ovh/standard`, documented by the
`lichess-org/lila-tablebase` project and backed by Syzygy tables.

Retrieved 2026-08-27 UTC. Read-only response-manifest hashes:

- initial 10 KPK + 5 mutual: `8c8704ff7bf7b2860719dcc363b337db81d00c2a715b21f09056d02685c95219`;
- 20 formula-disagreement positions: `1788e9bd4ae1b3eadb1c33a8c3bd199d0f095874ebd3401adaf967b9785cb0a3`;
- 10 additional mutual races: `e00aa565782063c0cfbeabc3fff9ec2afc874d9df06a182c4f99915ec14f2928`;
- random KPK seed 20260830: `28289104b56a9a88ed88ae703f5cd6518a1e5c7cf306fdea5cbec346cd5ffaef`;
- random KPK seed 20260831: `c5d190e00fe40e70b369318df37bf7497b0f126625f6a00e2e7df9669340bc70`.

API documentation:
`https://github.com/lichess-org/lila-tablebase/blob/main/README.md`.

## Gold-case format and split

Each committed case records:

- `case_id`, `fen`, `played_uci` when move grading is required;
- `family` and `split` (`development` or `held_out`);
- `expected_applicable`, `expected_catchable` and expected adapter results;
- tablebase source URL/category/response hash when WDL is a relevant
  cross-check;
- an adjudication note distinguishing pawn-race truth from whole-position WDL.

The positions used above are development evidence. Fresh fixed-seed positions
form the held-out regression packet and may reject the implementation, but the
runtime rule will not be retuned to individual held-out failures.


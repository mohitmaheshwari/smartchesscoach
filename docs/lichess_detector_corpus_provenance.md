# Lichess detector-research corpus provenance

Status: VERIFIED 2026-08-27

## Official source and permitted use

- Source: `https://database.lichess.org/`
- Publisher: Lichess open database.
- License: Creative Commons CC0. The official page explicitly permits
  research, commercial use, modification and redistribution.
- Puzzle source URL: `https://database.lichess.org/lichess_db_puzzle.csv.zst`
- Current official puzzle snapshot observed on 2026-08-27: last updated
  2026-08-02; 6,057,356 rated and automatically tagged puzzles.
- Standard-game source used for the bounded pilot:
  `https://database.lichess.org/standard/lichess_db_standard_rated_2026-07.pgn.zst`
- Official SHA-256 from
  `https://database.lichess.org/standard/sha256sums.txt`:
  `68738b1c448f051dc8d42db645d5b01749988a3bc1c24981adfe44ea92060dc7`.

## Existing production puzzle corpus

Read-only production measurement on 2026-08-27:

- collection: `lichess_puzzles`;
- documents: 4,110,434;
- imported between `2026-04-27T09:53:22.520028+00:00` and
  `2026-04-27T10:09:32.470410+00:00`;
- rating filter represented in storage: 600–2200;
- popularity filter represented in storage: 80–100.

The existing importer stores each row's import time but did not persist the
source snapshot date, response ETag, file size, or whole-file SHA-256. We
therefore cannot retroactively claim a checksum for those 4.11M documents.
They are usable as candidate research material, but any promoted gold packet
must retain its individual puzzle IDs and be independently adjudicated.

## Raw-game bounded pilot

The first 300 games of the checksum-pinned July 2026 standard rated export
were streamed and discarded on 2026-08-27. Nothing was written to MongoDB.

- 300 games / 20,117 plies;
- 0 parse errors;
- rating sides: 44 below 1000, 142 from 1000–1399, 201 from 1400–1799,
  and 213 at 1800+;
- detector fires: rule-of-square 130, opposition 46, KQ-v-K 7, KR-v-K 6,
  Fried Liver defense 3, Scholar's Mate defense 3;
- Lucena, Philidor, trap detection and opening play produced zero fires.

This pilot is sequential rather than random and measures opportunity volume,
not accuracy. It proves that generic raw games are sufficient for frequent
pawn-race/opposition candidates but inefficient for rare technical positions.
Rare endgames must use targeted tablebase/generated strata, and opening/trap
detectors need a correctly populated opening/history context before a larger
sample is useful.

## Corrected fork-theme pilot

The original validator inspected only the first player solution move and found
75.3% agreement. Full-solution replay showed that assumption was wrong:

- 1,000 tagged positives: 997 detected (99.7%);
- first player solution ply: 766;
- later player solution ply: 231;
- unresolved tagged cases: 3;
- 1,000 puzzles without a fork tag: 304 detector fires (30.4%).

The positive result makes Lichess excellent for fork coverage mining. The
negative result shows that absent tags cannot provide specificity gold,
especially when a mate/check also attacks another valuable piece.

## Hanging-piece coverage pilot (2026-08-27)

A read-only sample of 1,000 `hangingPiece`-tagged puzzles replayed the complete
solution and tested the corrected `free_piece` opportunity on every player
solution ply:

- 0 setup/legality errors;
- 976/1,000 matched the tagged solution sequence (97.6%);
- 958 matched the first player solution ply;
- 18 matched a later player solution ply;
- 24 had no strict free-minor-or-above capture match.

The unmatched set includes intermezzos, mate puzzles, hanging pawns, defensive
moves and longer endgame ideas. This is positive-candidate coverage evidence,
not semantic precision: Lichess tags describe the combination and may refer to
a different piece, later position or broader meaning of “hanging.” The puzzle
IDs remain suitable inputs to a blinded review packet; the tag is not the gold
label.

## Retention and separation policy

- External corpus records never enter `games`, `game_analyses`,
  `move_observations`, coach memory, player profiles, or active-focus history.
- Research artifacts retain source URL, snapshot/month, official checksum
  where published, original puzzle/game identifier, selection rule, and
  adjudication state.
- Raw streams are discarded after candidate extraction unless a separately
  reviewed retention need exists.
- A puzzle theme or engine evaluation can nominate a case; neither can be the
  independent semantic label for why a move is wrong.

# Lichess content directory

Pulled 2026-11-09 at Mohit's request ("pull up a rich content directory first,
openings, traps and end game lessons everything from lichess"). Reference data
only: nothing in the product reads these files yet.

| File | What | Count | Source | Licence |
|---|---|---|---|---|
| `lichess_openings.json` | Every named opening and variation: ECO, name, family, variation, PGN, UCI, final EPD, plies | 3,865 lines, 149 families; every line replayed legally with python-chess | github.com/lichess-org/chess-openings (`a.tsv`–`e.tsv`) | CC0-1.0 (checked via the GitHub API) |
| `lichess_practice.json` | All Lichess Practice studies: section, study, and per chapter the start FEN, the goal Lichess sets (`mate in 3`, `+300cp in 5`, `promotion with +100cp`, `draw in 20`), the main-line solution, and Lichess's intro text | 32 studies, 316 chapters: checkmates (7 studies), fundamental tactics (8), advanced tactics (10), pawn endgames (3), rook endgames (4) | lichess.org/practice, each study via `/api/study/{id}.pgn` | **Not granted to us.** Lichess's terms (read 2026-11-09) let anyone reproduce the site within each component's licence, but content users submit, studies included, is licensed *to Lichess*; no licence to third parties is stated for it. Positions and goals are chess facts and are used; the intro text is not shown to users until the licence is checked. One chapter's PGN (Greek Gift) carries an illegal side-line move in Lichess's own file, so its solution may be cut short. |
| `lichess_opening_tactics.json` | Tactics that arose in the opening phase of real Lichess games, grouped by opening family, 25 most-played kept per family | 140 families; 81,883 qualify in our puzzle table (Sicilian 12,219, French 5,240, Caro-Kann 4,759, Italian 4,118); 2,944 kept here | our `lichess_puzzles` table (Lichess puzzle database, imported 2026-04-27): theme `opening`, rating 600–1600, popularity ≥ 80, ≥ 500 plays | CC0 (Lichess puzzle database) |

| `lichess_endgame_puzzles.json` | Endgame positions by type (Lichess's own definition: only that piece kind plus kings and pawns), 25 most-played kept per type | Available at rating 600–1600, popularity ≥ 80: rook 141,599 · pawn 63,537 · queen 31,030 · bishop 26,050 · queen and rook 22,131 · knight 15,893 | our `lichess_puzzles` table | CC0 |

| `lichess_study_lines.json` | Lines from 848 Lichess studies (most-liked list plus searches for traps, gambits and each endgame type): moves and positions only | 7,127 unique lines: 1,920 opening lines (all named), 2,182 endgame lines (pawn 521, rook 478, bishop 270, knight 242, queen 207, mixed 464), 1,542 trap lines of which 790 engine-verified; **61 unique traps both engine-verified and real at 1100–1800** (`real_traps_ranked`, by how often players at that level play the losing move) | lichess.org studies, `/api/study/{id}.pgn`, comments not exported | Moves and positions are chess facts; the authors' text is licensed to Lichess and was not exported |

Trap method: the victim move is the line's biggest Stockfish drop (depth 10)
for the side that played it; engine-verified means that drop is at least
200 cp and the punishing side is still at least +200 at the end of the line.
"Real at 1100–1800" uses our own explorer counts from 3,488,310 Lichess games
of October 2026 (blitz and rapid, both players 1100–1800; built from the CC0
dump by `/root/research/explorer_count.py`): at least 30 games reach the
position and at least 5% of them play the victim move.

## What is still missing

- **Traps proper.** Lichess publishes no trap list. A trap at a given level is a
  popular move that loses at that level, and that needs the opening explorer.
  The explorer now answers 401 without a Lichess API token (checked
  2026-11-09), so `lichess_opening_service.py` gets nothing today.
- **Explorer statistics** (move frequencies and results by rating and speed,
  and the masters database): same token.
- ~~Puzzle refresh.~~ **Done 2026-11-09:** `lichess_puzzles` 4,110,434 →
  4,423,645 (313,211 new, same filters: rating 600–2200, popularity ≥ 80;
  existing rows untouched, `scripts/import_lichess_puzzles.py --only-new`).
  `opening_tags` is now indexed. Undo: delete rows with `imported_at` on
  2026-11-09.
- **Endgames beyond pawn and rook endings.** Lichess Practice has no bishop,
  knight or queen endgame studies; those come from puzzle themes
  (`bishopEndgame`, `knightEndgame`, …) instead.

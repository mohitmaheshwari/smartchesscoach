# Full-game chess-fact audit — sample lock (2026-09-03)

## Decision

Audit **80 complete games**, with **20 games in each rating band**:

- 600–899
- 900–1199
- 1200–1499
- 1500–1999

Within every band, select five games from each of four mutually exclusive audit strata:

1. opening learning opportunity;
2. middlegame tactical or geometric opportunity;
3. endgame learning opportunity;
4. general control game.

Selection must be deterministic from chess content, not user identity, source game id, date, player name, or current coaching label. A game is assigned to the first qualifying stratum in the order above; the general group is filled from the remaining games. The selection program must report eligible counts before exporting so a thin stratum is never silently substituted.

The locked stratum predicates are label-blind:

- **opening:** at least one meaningful user decision through full move 12;
- **endgame:** after removing opening games, at least one meaningful decision with queens off and either no more than four non-pawn pieces or no more than twelve non-king pieces in total;
- **tactical/geometric:** after removing opening and endgame games, at least one 300cp-or-larger decision whose stored best continuation contains a check, capture, or promotion in its first four plies;
- **general:** every remaining game with at least one meaningful user decision.

The corpus census confirmed every mutually exclusive cell is large enough. The thinnest cell is still 53 eligible games (1500–1999 tactical), against five required:

| Rating band | Opening | Endgame | Tactical/geometric | General |
| --- | ---: | ---: | ---: | ---: |
| 600–899 | 959 | 64 | 171 | 77 |
| 900–1199 | 1,772 | 142 | 187 | 180 |
| 1200–1499 | 1,966 | 106 | 151 | 122 |
| 1500–1999 | 1,978 | 68 | 53 | 82 |

## Why 80

A read-only production census derived the mover from `fen_before` and `user_color`, then applied the already locked rating-aware meaningful-mistake thresholds (150cp below 1000, 75cp at 1000–1399, 50cp at 1400–1799, and 30cp at 1800+).

| Rating band | Analysed games | Median user moves | Median meaningful decisions | P75 meaningful | P90 meaningful |
| --- | ---: | ---: | ---: | ---: | ---: |
| 600–899 | 1,386 | 26 | 4 | 6 | 9 |
| 900–1199 | 2,464 | 28 | 5 | 8 | 12 |
| 1200–1499 | 2,392 | 32 | 7 | 11 | 14 |
| 1500–1999 | 2,210 | 36 | 10 | 15 | 19 |

An 80-game sample is expected to contain roughly **2,400 user moves** and **about 500 meaningful user decisions**. Twenty games would yield only about 130 meaningful decisions. Forty games would yield about 260 and leave rare endgame and tactical failure families too thin. Eighty reaches the repository's first serious 500-move detector expansion tier while remaining small enough for position-by-position chess review.

As a separate integrity check, FEN side-to-move agreed with the stored `is_opponent_move` value on **280,682 of 280,682** inspected moves. The audit will still derive actor from FEN so this validation does not become an assumption.

## Stored-evidence boundary

This audit does **not** run Stockfish again. It treats the already stored Stockfish evaluation, best move, and continuations as engine truth, exactly as requested. It audits the deterministic interpretation built above that evidence:

- current category assignment;
- detector fires and misses;
- claimed tactical and geometric mechanisms;
- causal relation between played and better continuations;
- caption factuality and teaching value;
- important learning opportunities the current review omitted.

## Gold procedure

Before trusting any automated gold builder, hand-label 15 diverse meaningful moves against the reconstructed board and stored continuations. The builder must reproduce the agreed single-label precedence and may automate only engine-hard claims. Positional residue remains explicitly human/Codex-reviewed.

Every meaningful user decision is graded separately on:

1. **engine agreement** — the stored evaluations and lines support the claim;
2. **causal correctness** — the explanation identifies why the played move changes the position;
3. **category correctness** — the primary learning label follows the locked precedence;
4. **detector coverage** — proven mechanisms fire and unsupported mechanisms do not;
5. **teaching value** — the caption explains a concrete consequence or transferable idea;
6. **opportunity recall** — a memorable, provable alternative line is not silently omitted.

## Privacy and production contract

The versioned packet may contain only chess evidence required to replay and audit the game:

- anonymous content-derived game key;
- rating band and user colour;
- initial FEN and complete SAN/UCI move sequence;
- stored move evaluations and continuations;
- sanitized current detector/category/caption output.

It must contain **no** user id, source game id, email, player name, username, profile id, date/time, source URL, token, credential, or raw PGN header. Production access is read-only. The export is rejected if any move is illegal on replay, a stored FEN does not match replay, a required continuation is illegal, the sample cells are incomplete, or the privacy scanner finds a forbidden field or identifier pattern.

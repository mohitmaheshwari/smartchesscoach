# Tactic tags on every move, proved on the board

Status: DRAFT 2026-11-13, awaiting Mohit's sign-off.
Extends: `docs/move_observations_scope.md` (signed 2026-06-29).
Feeds: `docs/caption_from_board_meaning_scope.md` (signed 2026-11-12).

## 0. What already exists

| Piece | What it does today | Gap |
|---|---|---|
| `move_observations` (712,801 rows; Mohit 26,416) | One record per user move, written by the analysis worker (`analysis_worker.py` phase 3.3a, `services/move_observation_deriver.py`). | Tactics only as broad categories: `missed_pattern` = piece_safety / missed_tactic / ...; `subtype` has missed_pin (44) and missed_mate (116) but no fork. The "found it" side is empty: `tactical_pattern_executed` set on 1 of 26,415 of his moves; `missed_free_piece` true on 1. |
| 18 board provers (`services/*_puzzle_proof.py`) | Each proves one tactic from a position, the best move and the engine line. | Not called by the deriver. Used for puzzles only. |
| `scripts/validate_motif_prover_against_lichess.py` | Measures a prover against Lichess's human theme tags. | Covered 6 motifs; extended for this scope (see 5). |
| Review captions | Since 2026-11-13 (v248) rule text only; stored model text was 38% wrong. | Many cards name two moves and give no reason. |

Decision: EXTEND `move_observations`. No new collection, no new page.

## 1. What it is

Every move in an analysed game gets tactic tags that a board check has proved:
"missed a fork", "found a fork", "allowed a discovered attack", "missed a
mate", and so on, with the pieces and squares involved. Tags are written once,
when the game is analysed, for both players' moves. The review captions, the
coach plan and Progress then read these tags instead of guessing, so a card can
say exactly what happened on the board.

## 2. What the user sees

The card (review page), built from a tag, not from a model:

    You  21... Nb4   Mistake
    You missed a fork. Nd4 attacks their queen on c2 and their rook on e2 at
    once, and they can only save one.
    [board: d4 arrow to c2, d4 arrow to e2]

    Opponent  9. O-O   Mistake
    Your opponent missed a fork: e6 would hit your knight on d7 and your
    pawn on f7.

The coach (Progress / Home), counted from tags:

    Forks in your last 30 games
    You found 9 and missed 6. Most misses are knight forks on your queen.

## 3. In scope (V1)

- The deriver calls the provers for every move, both sides:
  - missed: the engine's best move is the tactic, the played move is not;
  - found: the played move is the tactic and the engine agrees it was best
    or close to it;
  - allowed: the move lets the opponent's best reply be the tactic.
- Tags carry the motif, the moving piece, the target squares and the prover version.
- Only provers that pass the precision gate (5) may write tags. Today: forced
  mate, free piece, discovered attack, fork, back-rank mate, and "line attack"
  (pin or skewer; named as one of the two only after (6.1) is settled).
- Trapped piece is excluded (42% precision).
- Schema version bump and a full backfill (deriver is a build step; ~15 min corpus run).
- Review captions read the tags first, before any other rule. The sentence is
  built from the tag's pieces and squares, and the arrows from the same squares.
- A real-game check before any tag reaches a card (5).

## 4. Out of scope (V1)

- Clearance (75% precision), interference, x-ray, deflection, attraction: they
  run in shadow and are not shown until each passes the gate.
- Trapped piece: fails the gate.
- New provers. This scope wires what exists.
- The ChessGuru rating (separate scope, paused).
- Any model-written chess text.

## 5. Success criteria

Measured 2026-11-13 on Lichess puzzles rated up to 1800, 1,500 per side,
other tactics as the control (strict verifier):

| Prover | Precision | Recall |
|---|---|---|
| forced mate | 100% | 100% |
| free piece | 99.6% | 96.2% |
| discovered attack | 98.3% | 80.9% |
| pin / skewer (one prover) | 98.3% / 97.8% | 47.1% / 65.6% |
| fork | 96.4% | 76.0% |
| back-rank mate | 100% | 9.7% |
| trapped piece | 42.1% | 0.5% (excluded) |

Gates:
- Precision at least 95% on Lichess (above) AND at least 95% on a hand-read set
  of 60 tags from Mohit's real games (10 per shown motif). A motif under the bar
  stays in shadow.
- On Mohit's 8 newest reviews, mistake cards whose reason comes from a proved
  tag rise from today's level (to be measured at build start) to at least 30%.
- Wrong claims on cards stay under 5% on the hand-read set (stored model text
  was 38%).

## 6. Open questions

1. **Pin or skewer?** One prover covers both. Does its bundle say which, and is
   that label right? Unblock: measure the label against the Lichess pin and
   skewer themes. Until then the card says "a line attack: your bishop hits the
   queen, and the rook behind it."
2. **"Found" threshold.** A played tactic counts as found when it was the
   engine's move or within how many centipawns of it? Unblock: histogram of
   played-tactic cp_loss on real games (lock-via-data).
3. **Opponent moves.** Tag them as their own records or keep them inside the
   next user move (`opponent_previous`, the June design)? Recommendation: own
   records, because "allowed" and "missed" on their moves drive half the cards.
4. **Which card wins** when a move carries two tags (a fork that is also a
   free piece)? Recommendation: mate, then the larger material gain.

## 7. Before any code

- Mohit signs this scope.
- 6.1 measured, 6.2 histogram run.
- The hand-read set of 60 real-game tags drawn and graded.
- `move_observations_scope.md` gets a pointer to this extension.

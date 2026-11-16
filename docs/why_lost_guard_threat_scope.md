# Why button: a guard lost two steps deep

Status: SIGNED 2026-11-16 (Mohit: "go ahead please", on the plan to widen the
lost-guard reason, judge the threat, and stop the side-effect sentence).
Extends: `docs/why_differential_scope.md`.

## 0. What already exists

| Piece | What it does | Gap |
|---|---|---|
| `differential_causes` one-step lost guard (`services/reasoning/differential.py`) | Fires when the reply hits a piece the played move left with **no** defender ("c4 moved the pawn that was guarding d4, so c5 hits your pawn on d4 with nothing defending it"). | Silent when one defender is left that a trade removes. |
| `positional.support_chain_hypothesis` | A pawn-only lost-support family. | Not called by the button; it belongs to `engine.py`'s quiet-move investigation. |
| Exchange-ledger fallback (`material_claim`) | Names the captures in the engine line after the played move. | When the best defence gives material up elsewhere, it names that side effect as the reason. |

Decision: EXTEND the button's lost-guard cause. No new page, no new field on the card.

## 1. What it is

When a move stops a piece guarding a square, and after the opponent's reply the
trade on that square is won only because that guard is gone, the button says so
and names the piece left with no guard.

## 2. What the user sees

The why panel on the review card, for 26.Qc2 in game 4ec5dfca:

    Before: After Qc2, f6 starts a line that ends with axb5 taking your pawn on b5.
    After:  Qc2 stops your queen guarding e5. After f6, they win the trade on e5:
            their bishop takes last with check. Then nothing guards your knight
            on d6. Rbc1 keeps your queen guarding e5.

## 3. In scope

- The moved piece may be any piece (not only a pawn).
- The trade on the square is played out with legal moves, cheapest capturer
  first, so pieces behind others join as the line opens (the g7 bishop sees e5
  only after f6 has captured). The side that starts needs a real gain; a side
  taking back does so unless it loses by it.
- It fires only when: the move is a mistake or worse; the reply is quiet (not a
  capture, not a check) and legal after both moves; the trade is won after the
  played move and not after the better move; at its end the supported piece
  (a knight or more, held only from that square) is attacked, unguarded, and
  cannot be saved with the move left (opponent to move, or every answer to
  check leaves it hanging).
- When it fires, the ledger sentence about the played line is not added: the
  cause already says what is at stake.

## 4. Out of scope

- A general rule against the ledger naming a defence's side effect when no
  cause is found. Measured need first; on this position the new cause replaces it.
- Supports that are not the moved piece's (a guard lost by a line closing).
- Threats that are not a trade on the guarded square (a fork, a mate).

## 5. Success criteria

- The regression set (`docs/qa/why_engine_regression_set.json`, 42 positions):
  no sentence changes except where the new cause fires, and each such fire is
  read against the board and found true.
- Qc2 fires with the sentence above.
- No number in any sentence.

## 6. Open questions

1. Fire rate on real mistakes. Unblock: a read-only pass over stored mistakes
   after deploy, reading every fire.

## 7. Before code

Signed as above; small-feature standing sign-off applies.

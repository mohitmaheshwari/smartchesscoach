# Why button: the threat behind the reply, read from a Stockfish line

Status: SIGNED 2026-11-16 (Mohit: "go", on "Shall I build it?" for the threat
line: "engine should use lines, because those give you what stockfish tells").
Extends: `docs/why_differential_scope.md`, `docs/why_lost_guard_threat_scope.md`.

## 0. What already exists

| Piece | What it does | Gap |
|---|---|---|
| Reply locator + family (`differential.py`, drop/gap 0.6 / 0.4) | Decides whether the reason is in the punishment line (punished) or the better move's line (missed). | Works; not changed. |
| `differential_causes` (one step) | Names what the reply checks, takes, attacks or uncovers that it cannot after the better move. | Silent when the reply is quiet and its point is the move AFTER it. |
| `lost_guard_threat` (two steps, board only, dfc70319) | A guard the played move gave up decides a trade on that square. | Only that one shape; 0 fires on 3,146 real mistakes. |
| Exchange-ledger fallback (`material_claim`) | Names the captures in the played line. | When the best defence pays elsewhere, it names the price, not the threat: "Qd7 starts a line that ends with Qxf6+ taking your bishop" (dev_qf8), "Nxd5 starts a line that ends with Qxg5" (codex_bxd5). |

Decision: EXTEND the button's causes with one more family. No new page or card field.

## 1. What it is

When the opponent's reply carries the mistake, ask Stockfish what that reply
threatens: after the reply, let the mover pass and read Stockfish's best move
and line. If that move wins material or mates after the played move, and does
not after the better move with the same reply, it is the reason, and the button
says so. Where the board shows why it fails after the better move (the better
move guards the square the threat lands on, or the played move stopped a piece
guarding it), one more sentence says that.

## 2. What the user sees

The why panel, dev_qf8 (24...Qf8, better Qh7):

    Before: After Qf8, Qd7 starts a line that ends with Qxf6+ taking your
            bishop on f6 for free.
    After:  After Qf8, Qd7 threatens Qf5+, and mate follows. After Qh7,
            your queen guards f5.

codex_bxd5 (5.Bxd5, better exd5):

    Before: After Bxd5, Nxd5 starts a line that ends with Qxg5 taking your
            knight on g5.
    After:  After Bxd5, Nxd5 threatens Qxg5, taking your knight on g5.

The arrows are the played move and the reply.

## 3. In scope

- Runs only when the move is a mistake or worse, the family is punished or
  mixed, no other cause fired, the reply is not a check (a pass is illegal
  in check), and the ledger's loss, if any, is not taken by the reply itself
  (a reply that simply takes something is already said plainly).
- Stockfish decides that the threat is real: passing after the reply costs the
  mover a clear amount more than its best defence, or Stockfish mates.
- Stockfish decides that it is the difference: the same threat move, after the
  better move and the same reply, does not win (a restricted search), or is
  not legal there.
- The words say only what the line shows: mate, or the piece taken and where,
  read from the threat line with the existing exchange ledger.
- The guard sentence only when the board shows one piece guarding the threat's
  square after the better move and not after the played move.
- Up to three more engine searches per press; the query cap goes from 8 to 10.
  Performance is not a design constraint (Mohit, 2026-11-12).

## 4. Out of scope

- Threats after a checking reply (ho03, verify_rf7). The one-step check
  family and the ledger keep these.
- A threat line with no clean material or mate result (ho23: the threat ...c4
  sets up a mate on f2 that the line itself parries). Silent; the ledger
  sentence stays.
- Saying what the best defence still costs ("stopping it costs your bishop").
  Measured need first.
- The missed family (the reason is the better move's own line).

## 5. Success criteria

- Regression set (42 positions): every sentence that changes is read against
  the board and found true; no other sentence changes.
- On a fixed random sample of real stored mistakes, every fire is read and
  found true. The fire count is reported as measured, whatever it is.
- No number in any sentence.

## 6. Open questions

1. ~~The "clear amount" a pass must cost.~~ Measured 2026-11-16 on 22 probes
   from an 80-mistake random sample: 200 cp kept. Every probe below it
   (28-194) had a line with no clean threat (a knight move, a pawn running to
   promote, the mover's own capture), so the ledger-or-mate gate refuses them
   anyway; the threshold is not the binding gate.

## 5b. Measured 2026-11-16

- Regression set: 5 of 43 sentences change, each read against the board:
  dev_qf8 and codex_bxd5 (the mockups above); ho05 and ho08 ("Qc5 threatens
  Qxf2+, and mate follows. After Rxc2, your rook guards f2": Qxf2+ Kh1 Qxg2#,
  the c2 rook backs the queen); ho04 (silent before: "Kg7 threatens Qa3,
  which wins your knight on e7"). No other sentence changed.
- 80 real mistakes (seed 1116, from the 600 newest analyses): probe ran on 22,
  fired on 3, all true (Be2: Ba6 then Qxe2+; Rhe8: b4 then bxc5, met by Rxf4
  after Rd4; Bb2: Ne4 then Nxc3 on the pinned knight). 10 of 80 answers were
  "starts a line that ends with" before; 2 of those are now the threat.
- Two reading rules came from these: the threat ledger reads 6 plies, not 12
  (codex_bxd5 read "knight and bishop on g5", the bishop a sacrifice seven
  plies on); the guard sentence needs one more guard after the better move
  than after the played move (Bb2 and Bd2 both guard c3; Bd2's point is the pin).
- At most 9 engine searches per press seen; cap 10.

## 7. Before code

Signed as above; small-feature standing sign-off applies.

## 8. Fixes 2026-11-17 (Mohit: "go", on fixing what his own recent games showed)

Found by running the live button over the 60 mistakes of Mohit's 11 newest games
and the 4 positions waiting in the why queue. Bug fixes to shipped behaviour;
tests in `tests/test_why_mate_and_reply_capture.py` (all four fail on 71120c7d).

- **A threat made by the reply piece is no threat when the best defence takes
  that piece.** 2d86e1f9 m17: after Rf8 Nxf6 the defence is gxf6, and the live
  button said "Nxf6 threatens Nh7+". A pass skips the recapture, so the pass
  line cannot see it. Now silent there (`defence_takes_the_reply`).
- **The same capture after the better move means the threat is met, not
  shared.** c31e86a3 m15: Nc6 Nc7 forks queen and rook; after Na6 the defence
  is Nxc7. Was silent ("Nc7 starts a line that ends with Nxa8"); now "After
  Nc6, Nc7 threatens Nxe8, which wins your queen on e8 for a knight. After Na6,
  your knight guards c7." The guard-on-the-threat-square sentence keeps
  precedence where both hold (ho05 still names f2).
- **Mate from the engine's score, on both sides** (`differential.py`, the rule
  `why_on_demand._mate_from_score` already used): the line walk reads six
  plies and needs a move after the mating one. 5ec24941 m19 (Qd3# missed) was
  silent, now "Qd3# was checkmate."; 856f6111 m6 (Ke8 allows mate in six)
  named a pawn on g6, now "After Ke8, Qh5+ leads to mate." A mate outranks the
  material sentence; both-ways mate stays excluded.

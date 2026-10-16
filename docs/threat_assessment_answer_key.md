# Threat-recognition assessment — answer key

Companion to [threat_assessment_board_sheet.md](threat_assessment_board_sheet.md).
**Do not read this before attempting the boards.**

## How each position was verified

Nothing here is taken from a detector flag. For each candidate:

- **The threat is computed on the board.** The opponent's last move must
  **newly** attack one of his pieces worth 3+ that is undefended, or defended
  only by pieces more valuable than the cheapest attacker — or newly create a
  mate in one. "Newly" matters: the same attack present before the move is a
  standing feature of the position, not a threat just created.
- **Acceptable responses are computed, not guessed.** Every legal move is
  played and the position re-examined; a move qualifies if the threatened
  square no longer holds an under-defended piece afterwards, whether by moving
  it, capturing the attacker, blocking, or adding a defender.
- **Cross-checked against the engine.** A position is only used if the stored
  Stockfish best move is itself among the computed answers. If the two
  disagreed, the position was dropped rather than reconciled.
- **Spot-checked by hand.** Five of the twelve were re-verified
  move-by-move with python-chess, confirming attacker and defender counts and
  the legality of every listed answer.

Positions were rejected where he was already in check, where more than half of
all legal moves "answered" the threat (not a test), or where fewer than two or
more than ten answers existed. Candidates were restricted to **move 12 or
later**, so none is opening theory. From 201 verified threat candidates and 749
no-threat candidates, twelve were selected: five where his own move cost 100cp
or more, four where it cost under 50cp, and three controls — so the set is not
simply a list of his failures.

**Prior exposure is recorded per position** and is not clean: 92 of the 100
games have a stored review, so he may have seen these games analysed before.
One position (number 4) was previously extracted as a puzzle or concept
position. That is a real limitation of using his own games, and it is recorded
rather than hidden.

## Key

```
   1.  NO THREAT (control)
       threat: none -- the opponent's g3 creates no new threat
       engine best move     : f5
       he played a move costing 0 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = False; this game has a stored review = True
       fen  r6r/1pp1kp2/pbnpq3/4p3/1P2P3/P1PP2Pp/3N1P1K/R1BQ1R2 b - - 0 17

   2.  NO THREAT (control)
       threat: none -- the opponent's Rhd8 creates no new threat
       engine best move     : Rc3
       he played a move costing 0 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = False; this game has a stored review = True
       fen  1r1r4/4ppkp/1pB2npb/1NqP2N1/7P/1R6/P1P2PP1/3Q1RK1 w - - 7 20

   3.  NO THREAT (control)
       threat: none -- the opponent's b6 creates no new threat
       engine best move     : Na3
       he played a move costing 15 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = False; this game has a stored review = True
       fen  r2k3r/p1qn1ppp/1p1b1n2/P1pP2B1/3P4/5BP1/1PP2P1P/RN1QR1K1 w - - 0 15

   4.  THREAT
       threat: knight on b4 is attacked and not safely defended
       engine best move     : Na6
       moves that answer it : Na6, Nc2, Nc6, Nd3, Nxa2, Nxd5, Qxc3
       best move is among them: True
       he played a move costing 177 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = True; this game has a stored review = True
       fen  1r2k2r/p1p3p1/3b1qp1/3P1p2/1n2pP2/2P3P1/PP4BP/R1BQR1K1 b k - 0 17

   5.  THREAT
       threat: queen on d1 is attacked and not safely defended
       engine best move     : Qxf3
       moves that answer it : Qb1, Qc1, Qd2, Qe1, Qe2, Qf1, Qxf3, gxf3
       best move is among them: True
       he played a move costing 0 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = False; this game has a stored review = True
       fen  r2q1rk1/1pp2pp1/p2p3p/3Pp3/2B5/3P1b1P/PPP2PP1/R2Q2K1 w - - 0 16

   6.  THREAT
       threat: knight on f8 is attacked and not safely defended
       threat: a mate in one is now available to the opponent
       engine best move     : Kg8
       moves that answer it : Kg8, Nd7, Ne6, Ng6
       best move is among them: True
       he played a move costing 0 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = False; this game has a stored review = True
       fen  2K2n1k/5Rpp/8/8/1P6/P5P1/6bP/8 b - - 2 42

   7.  THREAT
       threat: queen on d1 is attacked and not safely defended
       engine best move     : Qxg4
       moves that answer it : Ne2, Nf3, Qb1, Qc1, Qd2, Qd3, Qe2, Qf3, Qxg4
       best move is among them: True
       he played a move costing 0 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = False; this game has a stored review = True
       fen  rn1qkb1r/p3p3/2p1Pppp/1p6/3PpPb1/1B2B3/PPP4P/R2QK1NR w KQkq - 0 12

   8.  THREAT
       threat: bishop on g5 is attacked and not safely defended
       engine best move     : Bf6+
       moves that answer it : Bc1, Bd2, Bd8, Be3, Be7, Bf4, Bf6+, Bh4, Bxh6+
       best move is among them: True
       he played a move costing 0 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = False; this game has a stored review = True
       fen  8/6k1/7p/4KBB1/8/8/8/8 w - - 0 49

   9.  THREAT
       threat: queen on d5 is attacked and not safely defended
       engine best move     : Qxc4
       moves that answer it : Qa5, Qb5, Qc5, Qc6, Qd6, Qe4, Qe5, Qf5, Qxc4, Qxd4+, Qxf3
       best move is among them: True
       he played a move costing 418 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = True; this game has a stored review = True
       fen  r3k2r/pppnbp1p/4b3/3q2p1/2PP4/5NP1/PP2Q1PP/R1B2RK1 b kq - 0 16

  10.  THREAT
       threat: rook on d1 is attacked and not safely defended
       engine best move     : Rc1
       moves that answer it : Ra1, Rb1, Rc1, Rd2, Rd3, Rde1
       best move is among them: True
       he played a move costing 126 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = True; this game has a stored review = True
       fen  rn2k2r/p2p1ppp/1p1ppn2/8/2BP4/BP4N1/P1b2PPP/3R1RK1 w kq - 0 13

  11.  THREAT
       threat: knight on c3 is attacked and not safely defended
       engine best move     : Nd5
       moves that answer it : Na2, Na4, Nb1, Nb5, Nd5, axb4
       best move is among them: True
       he played a move costing 440 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = False; this game has a stored review = False
       fen  1rbqk2r/4bppp/2np1n2/2p1p3/1p2P3/P1NPBN2/1P2BPPP/R2Q1RK1 w k - 0 13

  12.  THREAT
       threat: bishop on b3 is attacked and not safely defended
       engine best move     : Bd1
       moves that answer it : Ba2, Ba4, Bc2, Bd1, Ra3, Rb5
       best move is among them: True
       he played a move costing 116 cp here
       PRIOR EXPOSURE: position extracted as a puzzle/concept before = False; this game has a stored review = True
       fen  2r5/5p1p/4b3/R4p2/2P5/1Bk4P/5KP1/8 w - - 4 32
```

# Why button: the opportunity behind the better move, read from a Stockfish line

Status: SIGNED 2026-11-17 (Mohit: "okay, go", on "Shall I build it?" for the
opportunity line, after "why button should have capability to see if it was a
opportunity line or threat line ... sometimes a mistake is because there was a
better opportunity available").
Mirror of: `docs/why_threat_line_scope.md` (6b5f6747, live since 2026-11-16).

## 0. What already exists

| Piece | What it does | Gap |
|---|---|---|
| Family (`differential.py`, drop/gap 0.6 / 0.4) | Punished = the opponent's best reply carries the gap; missed = no single reply does, the better move's line holds it. | Works; not changed. |
| Missed side: `resolve_missed`, `alternative_double_attack`, ledger gain, check-first | Names what the better move's line takes, mates, forks or chases. | Silent when the better move is quiet and its point is the move AFTER it. |
| Fallback order | Missed family tries the missed side, then the punished side. | When the missed side has nothing, the button explains the punishment although the engine says most of the gap is the opportunity. |
| Threat line (6b5f6747) | Punished side: pass after the reply, Stockfish's best move is the threat. | Punished side only. |

Measured on the 80 random real mistakes of 2026-11-16 (seed 1116, mistakes and
blunders only): of 32 in the missed family, 16 got an opportunity sentence, 11
a punish-side sentence, 5 nothing.

Decision: EXTEND the missed side with one more step. No new page or card field.

## 1. What it is

When the engine says the mistake is a missed opportunity, ask Stockfish what
the better move threatens: after the better move, let the opponent pass and
read Stockfish's best move for the mover. If that move wins material or mates,
and the same move does not after the played move (opponent passing there too),
it is the opportunity, and the button says so before it falls back to the
punish side.

## 2. What the user sees

The why panel, one sentence of this shape (real examples go in 5b once measured):

    Before: After Qc5, Bd4 chases your queen.
    After:  Rad8 was the move: it threatens <T>, which wins their <piece> on <sq>.

Mate: "<better> was the move: it threatens <T>, which is mate." (mate in one)
or "... and mate follows." Opponent cards say "your" where user cards say
"their". The arrow is the better move.

## 3. In scope

- Runs only when the move is a mistake or worse, the family is missed, and the
  missed side's existing answers found nothing (not check-first, not
  resolve_missed, not the double attack, not the ledger gain).
- The better move is not a check (the opponent cannot pass in check), and the
  played move is not a check (same reason on the other branch).
- Stockfish decides the threat is real: after the better move and a pass, its
  best move scores at least 200 cp better for the mover than the better move
  itself, and the 6-ply ledger of that line wins at least a pawn's worth with
  the capture in the first 4 plies and not given back; or Stockfish mates in
  3 or fewer.
- The threat wins at least the gap (added in measurement: at half the gap,
  ho02 named a pawn threat for a move whose cause is a trapped queen).
- Stockfish decides it is the difference: after the played move and a pass,
  (1) no move wins material on the same square (or mates, for a mate threat)
  -- added in measurement: mohit_qc2's Bd3 threatens Bxe4, but Qc2 hits the
  same knight; and (2) the same move restricted is illegal, wins no material
  on the ledger, or does not mate. The eval alone is not enough: a pass is a
  free move on both branches (the codex_bxd5 lesson from the threat line).
- Up to three more engine searches per press; the cap of 10 stays.
- The measurement is kept on every run (`result["opportunity_line"]`).

## 4. Out of scope

- Mixed and punished families (the reply carries the gap there; the threat
  line covers the punished side).
- A reason sentence (why T fails after the played move). The threat line has
  a guard sentence; the mirror would need its own rule and evidence.
- Checks as the better move; their line is already read by the missed side.
- Showing the threat as an arrow: the pass line does not replay from the root.

## 5. Success criteria

- Regression set: every changed sentence read true against the board;
  no other sentence changes.
- The 80-sample: every new fire read true by hand; count of missed-family
  positions answered from the punish side or silent goes down from 16.
- No new test failures.

## 5b. Results (2026-11-17, local Stockfish, button config)

Regression set (42): 2 sentences changed, each read against the board and the
hand grades. Nothing else moved (ho05/ho08 differ from the stored baseline file
only by the guard sentence deployed in 6b5f6747).

    codex_bg5  Before: After Bg5, h6 chases your bishop.
               After:  e5 was the move: it threatens exf6, which wins their
                       knight on f6 for a pawn.
    codex_h6   Before: After h6, c6 chases your queen.
               After:  d4 was the move: it threatens dxe3, which wins their
                       queen on e3 for a pawn.
    mohit_qc2  unchanged (tempo sentence); the first build replaced it, fixed
               by the same-square rule.
    ho02       unchanged; the first build fired a pawn threat, fixed by the
               gap rule.

80 random real mistakes (seed 1116): the line ran on the 16 missed-family
mistakes the existing answers left (11 punish-side + 5 silent) and fired on
2, both checked on the board with python-chess:

    #12  Before: After Qc5, Bd4 chases your queen.
         After:  Rad8 was the move: it threatens Nc4#, which is mate.
                 (after Qc5 and a pass, Nc4+ is met by Qxc4)
    #63  Before: (silent)
         After:  e4 was the move: it threatens exf3, which wins their
                 knight on f3 for a pawn. (exf3 is illegal after exd4)

The other 14: 7 have a quiet best move after the pass (e5, Bc5, Re7, Ng3,
Rh6, Qb8, g7) -- the better move's point is positional or a pawn run, not one
threat; 5 gain under 200 cp from the pass; 1 mate too far (a promotion);
1 the better move is a check. Success criterion "16 goes down": 16 -> 14
(#12 moved from the punish side, #63 from silence). Coverage of the
positional half needs a different idea; not this one.

Tests: tests/test_reasoning_opportunity_line.py, 10 tests, replayed engine
answers. Why/reasoning suite: 539 passed, 2 failed (test_why_study_gate, the
same two as before the change).

## 6. Open questions

- Does 200 cp suit this side? Kept from the threat line; the measurement is
  stored on every run and the sample distribution decides.

## 7. Pre-code

- Signed (above). Branch claude/why-opportunity-line from working-code 6b5f6747.
  No open PR touches the files (PR #1 is March, no reasoning files).

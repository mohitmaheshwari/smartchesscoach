# Do not score material where a capture is still pending

Status: DRAFT for sign-off. No code until Mohit says go.
Written 2026-10-10. Grew out of move 16 Ne4 in the Philidor game.

## The problem in one card

Position `3r1rk1/ppp3pp/5p2/3Pp1q1/3n4/2QPR3/PPPN1PPP/R5K1 w - - 2 16`,
cp_loss 268, severity "serious". The card said:

    Ne4 is a mistake. Rae1 was better - it puts your rook on a line where
    none of your own pawns are in the way.

and the engine-paths panel said **"material over the played line +4"**.

What actually happens is Qxe3, a queen sacrifice. fxe3 is forced, and then
Ne2+ forks the king on g1 and the queen on c3. The queen falls.

    material (+ = the player ahead)
      at the start                     +1
      end of the stored 4-ply line     +5     <- what the card scored
      one ply further, Nxc3            -4     <- what happens

The card does not merely miss the story. It has it **backwards**: it believes
the player wins four points while they are losing their queen.

## Why, and what the fix is NOT

My first reading was that 4 plies is too short and the corpus needs
re-analysing deeper. Mohit: "no, 4 plies are enough, Ne2 gave you the fork,
which should give you the payoff right?"

He is right, and it is much cheaper. The information is already in the stored
line. The last position of that line has a queen hanging, and we score the
material there as though the board had settled. A position with a winning
capture available is not a position to count material in.

So: no re-analysis, no extra plies, no engine. A board walk over the legal
moves at the leaf.

## The rule

At the last position of the stored line:

1. Find the best capture available to the side to move. Value it as the
   victim, minus the capturing piece when the square can be recaptured.
2. If that gain is positive, the leaf is NOT quiet. The material verdict must
   account for it before `move_story` or any material clause reads it.
3. When the line's last move was a CHECK and the checking piece also attacks
   a non-pawn, that is a fork, and it is the reason the capture cannot be
   prevented. Name it in the caption.

Step 1 is a heuristic, not a real static exchange evaluation -- it nets one
recapture, not a full sequence. On the Ne4 card it gives -1 where playing the
moves out gives -4. **The sign is what the verdict needs and the sign is
right; the magnitude is not trustworthy and must not be printed.**

## Measured, 1,500 games, 8,776 user cards at cp_loss >= 100

    stored line lengths        4 plies 8,657 | 3: 100 | 12: 18 | 2: 2

    leaf is NOT quiet (a capture pending)        3,096   35.3%
    ...and the pending capture FLIPS the verdict   488    5.6%
    ...where the last move was a forking check      59

One card in three ends on an unsettled position. In 488 the material verdict
is simply wrong in sign.

For comparison, the earlier framing -- "extend the line by one ply" --
measured 1,040 sign flips (11.9%). The quiet-leaf test catches 488 of those
by looking only at what is already stored. The remaining flips come from
lines that end quietly and then go wrong later, which is a different problem
and NOT in this scope.

## What changes

- `move_story` stops returning `neither` on cards with a real material swing
  hidden behind an unsettled leaf. That moves ARROWS as well as captions,
  because the verdict drives both.
- Material clauses in R12_blunder.json get a correct sign to work from.
- On the 59 forking-check leaves the caption can name the mechanism:
  "Ne2+ forks your king on g1 and your queen on c3."

## What it must not do

- Print the heuristic gain as a number. Sign only.
- Claim a fork that the board does not show: both attacked squares must be
  read off the checking piece's attack set.
- Change anything on a quiet leaf. 64.7% of cards must render identically,
  and the before/after corpus diff has to show that.

## Risks

Moving `move_story` moves arrows. Today's arrow work (3e815958) is keyed to
punishment vs opportunity vs neither, so 488 cards changing verdict will
redraw. That is the intent, but it means the before/after diff must be read
per row, not as a total -- see feedback_snapshot_the_corpus_before_refactoring.

## Open question for Mohit

The 3,096 non-quiet leaves where the sign does NOT flip: the magnitude is
still wrong there. Do we correct those too, or only the 488 where the verdict
is wrong? Correcting all 3,096 is more honest and touches three times as many
cards.

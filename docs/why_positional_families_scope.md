# Why button: positional families — scope

Status: draft for Mohit's sign-off, 2026-11-02. No code until signed.
Parent: `docs/why_differential_scope.md` (the material families, live since 2026-10-31).

## The problem in one position

Scandinavian, Black to move after 1.e4 d5 2.exd5 Qxd5 3.Nc3 Qe6+ 4.Be2. Black
played 4...b6. Stockfish says it costs about 70 cp against Nf6 or Qd6, which at
Mohit's band is an inaccuracy on the boundary of a mistake. The live button says
"No single tactic to point at here. The engine simply prefers Nf6."

A coach says: *Your queen on e6 is standing on the square your e-pawn needs, so
your f8 bishop cannot move and you cannot castle. b6 does not change that. Qd6
gets the queen out of the way; Nf6 brings a piece out. After b6 White develops
with threats and your queen has to move again anyway.*

Every clause of that is a fact the engine can compute (checked 2026-11-02 with
python-chess on the position):

| clause | source |
|---|---|
| the f8 bishop cannot move | zero legal moves from f8 for Black |
| the queen is on the square the e-pawn needs | own queen on e6, directly in front of own pawn e7 |
| e6 is the only way to free the f8 bishop short of g6 | the bishop's exits are e7 (own pawn) and g7 (own pawn) |
| b6 changes none of this | same three facts after b6 |
| Qd6 frees the e-pawn; g6 frees the bishop; Nf6 develops a piece | facts after each alternative |
| the queen gets chased later | queen moves while attacked in the played line, not in the alternative's |

The engine today has only **material** families: capture, exchange, check,
attack, lost guard, double attack. Anything positional is silent by design.
This scope adds the first non-material families, in order of how much of the
silent set they cover.

## What the button will say at the end

For a b6-type move:

> b6 does not bring a piece out. Your queen on e6 is standing where your
> e-pawn needs to go, so the bishop on f8 cannot move and you cannot castle.
> Qd6 steps out of the way. After b6 White keeps developing with threats and
> the queen has to move again anyway.

Short, plain, no numbers, names the better move, gives a board-verified cause
and (when the line shows it) a consequence. Same rubric as the material
families: mechanism / thin / misleading / false / silent.

## Family 1: tempo (development)

**When it may fire.** Only when every material family is silent, the class is
inaccuracy or mistake, and the game is still in development (the mover has an
undeveloped minor piece or has not castled).

**Root facts (board).**
- undeveloped minor pieces of the mover (on their home squares)
- *stuck* pieces: a minor piece with zero legal moves
- for a stuck bishop, the pawn whose advance frees it, and whether that pawn's
  advance square is occupied by the mover's own piece (the queen on e6)
- queen already off its home square

**Move facts (played vs better).** For each of the two moves: develops a minor
piece; castles; frees a stuck piece (directly, or by stepping off the pawn's
square); or none of these. The family fires only when the better move does one
of them and the played move does **none**. If both do none (best move c6, played
b6) it stays silent: shared property, same rule as shared consequences today.

**Line facts (differential, optional consequence).** Along both lines to the
same horizon: the mover's forced retreats (a piece moves while attacked, not
capturing) and developed minors at the horizon. A consequence sentence is added
only when the played line has a forced retreat the alternative's does not, or
the alternative's line is a developed piece ahead. The PV here is unstable
(d4/Nb5/d5 all appear at different depths), so the consequence is optional and
the cause carries the sentence.

**What it must never do.**
- fire when the engine's best move is itself a quiet pawn move (c6, a6 here)
- call a normal developing move a "block" (Nf6 stands in front of f7; Nc3 in
  front of c2; the predicate is "the queen or king stands on the square a
  pawn needs to free a stuck bishop", not "a piece is in front of a pawn")
- say "chases" alone; that sentence was graded thin four times on the set

## Family 2: which piece recaptures

codex_nxe5 and ho15: both lines capture on the same square with a different
piece. The ledger already has the square; the sentence is a comparison
("take with the pawn: after Nxe5 the knight is chased by g4; after dxe5 the
pawn holds the square"). Mechanism = the recapturing piece is chased or traded
in the played line and not in the other.

## Family 3: a piece that falls just past the window

dev_qf8 (bishop falls on ply 9) and mohit_qc2 (h6 pawn). The six-ply unanswered
capture window exists because of ho08 (a pawn on ply 29). The rule to try:
extend to ten plies when the capture is the line's **only** material event and
the eval gap supports it. ho08 stays silent because its line has several.

## Family 4: king exposure

ho22 and ho04: the gap is a king attack (a series of checks ending in material
or a mate threat). Check is already a cause; the family adds the consequence by
counting checks and the king's escape squares along each line.

## Family 5 (candidate, 2026-11-02, not signed): a threat left unanswered

Found on 6.b3 in the b6 game (set entry `mohit_b3`). After b3 and after the
better d4, Black's same reply ...Qg6 attacks the g2 pawn, which nothing
defends. The differential calls that shared and stays silent, and the tempo
family is silent because both pawn moves free the c1 bishop. The difference
is the defence: after b3 White's queen on d1 has no legal move and the least
bad answer gives up the bishop (Bb5+, Bxc6); after d4 the queen reaches d2
and the pawn is poisoned (Qxg2 loses the queen to Bb5+ and Qxg2).

**Root facts (board).** The reply's target: a piece or pawn the best reply
attacks with zero defenders, the same on both branches. The mover's pieces
with zero legal moves (the boxed queen).

**Line facts (differential).** On the better branch, play the capture of the
target and read the engine: a swing of a piece or more means the target is
poisoned, and the line names the refutation (the check that clears the rank).
On the played branch, the mover's piece that could defend has no move, or
the first move of the line gives up material or the bishop pair to cover it.

**Sentence shape.** "After b3, Qg6 attacks the g2 pawn and nothing guards it;
your queen on d1 cannot move to help. d4 opens the queen's road: after d4,
taking on g2 loses the queen to Bb5+." Every clause is a board fact or a
played line; the class stays the engine's.

**What it must never do.** Read a threat off the PV: a first draft of this
note said d4 "threatens d5 against the queen", and the engine says d5 is
worse than Bf4. Play the line before claiming it.

## Measurement before any threshold is locked

1. The 37-position set: positive controls b6 (new entry), ho16, ho18, ho09,
   codex_g4; the 13 mechanism answers must not change; zero fires on the 8
   good moves.
2. Mohit's recent analyzed games (12 games imported 2026-10-31 to 11-02, about
   60 inaccuracies and mistakes, and their good moves as negatives): fire rate
   per family, hand-graded sample of 20.
3. Then the 4,442-position pressure export for scale.

Any cutoff (horizon plies, development count) is read off these distributions,
not chosen first.

## Acceptance

- Family 1 on b6: the sentence above, through luna, with the four guards passing.
- Set: mechanism count rises, misleading and false stay at zero, good moves stay silent.
- Button budget unchanged: the family reads the two PVs the differential already has;
  no extra engine queries.

## Order

1 (tempo) first; it is the b6 case and, at the 1200 band, the commonest class
of silent inaccuracy. Then 2, 3, 4, each with its own measurement pass.

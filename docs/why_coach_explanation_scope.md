# Scope: a coach explanation built from the engine line

Status: DRAFT — needs Mohit's sign-off before any code.
Written 2026-10-05. Every number is from a named run; where a number
changed after I fixed my own measurement, both are shown.

---

## What Mohit asked for

> "that why button just shows the stockfish line, i want a coach level
> explanation there created by that line"

Right now the button returns one sentence naming an outcome — "After
hxg4, Bg3 wins your pawn" — plus arrows. The line is a causal sequence
and a coach explanation is a causal story, so the raw material is
already there. This is about reading it.

## What the line actually contains

Pushing each move and recording what changed gives a small, verifiable
vocabulary per ply: what was captured, whether it gave check, the net
material measured from BEFORE the played move, and which of our pieces
newly became trapped. Nothing is inferred; every item replays.

Worked example — `Bxf7+` (379cp), where the button today says
"After Bxf7+, Kxf7 wins your bishop":

    1. Bxf7+  (you)  net +100cp  takes the pawn; gives check;
                                 bishop on f7 has no safe square
    2. Kxf7   (they) net -200cp  takes the bishop
    3. Be3    (you)  net -200cp
    4. c5     (they) net -200cp

Every clause of a coach version is in that walk already.

## The one-liner is misleading on part of the sample

Worth stating plainly, because it is an argument for doing this at all.
The resolver measures from AFTER the played move, so a recapture reads
as pure loss:

    Bxf3 (180cp)  "After Bxf3, gxf3 wins your bishop."
      ply 1  +300cp  takes the knight
      ply 2    +0cp  takes the bishop
      -> net is ZERO. An even trade, told to the player as a loss. The
         move's real cost was positional and not material at all.

    Qxc2 (181cp)  "After Qxc2, Bxg3 wins your rook."
      ply 1  +300cp  takes the knight   <- the caption hides this
      ply 2  -200cp  takes the rook

## How often each story shape appears

150 answers, depth 18, 8 candidates, Threads=1, mistakes at cp_loss>=100.

| shape | share | what it is |
|---|---|---|
| residue | 22.7% | no story my rules can name |
| nothing_material_happens | 22.0% | line runs, material never moves |
| quiet_then_capture | 18.7% | several silent plies, then a piece falls |
| plain_loss | 11.3% | they take, we take nothing back |
| trap | 10.0% | a piece of ours loses every safe square |
| trade_ends_down | 8.7% | material off both sides, we end short |
| even_trade_mislabelled | 4.0% | net zero, told as a loss |
| unsupported_sac | 2.7% | gave material with check, nothing follows |

**A named story fits 83 of 150 (55%). 45% has none.**

### The number I got wrong first

My first run put `trap` at **57.3%** and coverage at 73%. That was my
measurement, not the board. My throwaway predicate asked only "are all
this piece's destinations attacked" — it never asked whether the piece
was attacked at all, or whether staying put cost anything, so a safe
piece with no good squares counted as trapped.

`board_concepts.trapped_pieces` requires all three and its docstring
names the error: *"Staying put must also lose material, otherwise it is
merely restricted."* Using it, trap is **10.0%** — a 5.7x inflation —
and coverage drops 73% -> 55%.

This is the same defect I fixed in `static_board_lessons` the week
before (requiring the piece to be attacked moved it from 74.5% to 92.2%
silent on good moves). I reintroduced it in a throwaway within a week,
which is the argument for calling the real detector rather than
hand-rolling geometry.

Had I not re-run it, this document would have claimed one template
covers 57% of cases.

## What to build

**Three shapes, not five.** Ranked by measured volume, the top three are
`quiet_then_capture` (18.7%), `plain_loss` (11.3%) and `trap` (10.0%) —
**40% between them**. The two I was going to author first by instinct
sit at 4.0% and 2.7%; at that volume a template is review time spent on
something almost nobody sees.

### The cards, literally

Written for a 600-1500 player: short sentences, one idea each, no
jargon, no numbers, a principle at the end, and never opening with
"you played X".

**quiet_then_capture** (18.7%) — today: *"Qd1 wins their knight."*

> Nothing happened for several moves, then the knight fell because
> nothing was guarding it. A piece with no defender is a target even
> while nothing is attacking it yet.

**plain_loss** (11.3%) — today: *"After c6, Nc4 wins your pawn."*

> The pawn had no defender and there was no way to take anything back.
> Before a move, check what it leaves unguarded.

**trap** (10.0%) — today: *"e4 wins their knight."*

> Your bishop ran out of squares. Every square it could reach was
> covered, so it had nowhere to go. Count a piece's escape squares
> before pawns can come at it.

### What stays silent

**45% gets no coach explanation**, and that is the design, not a gap.

- `nothing_material_happens` (22.0%) is **25 of 33 FORCES_RETREAT**.
  That mechanism's payoff is `max(1, value // 10)` — a tempo proxy, not
  material — so these lines genuinely have no material story. They keep
  today's one-liner.
- `residue` (22.7%) is mixed and my rules name nothing in it.

Those cards keep the existing sentence. Nothing regresses.

## Honest limits of this measurement

- **The shape rules are mine and unvalidated.** They were written from
  six hand-read lines. The 22.7% residue may well be classifiable by
  better rules, so **55% is a floor on what is derivable, not a
  ceiling**.
- **One shape, one line.** A line could carry two stories; the
  classifier picks one by priority order. That is the same
  first-match-wins property that made `R12_blunder` worse as it learned
  more, and it needs watching here.
- **150 is a sample.** `unsupported_sac` is 4 cases. Any claim about the
  shapes under 5% is directional only.

## Before anything renders

1. **Side by side.** The coach text next to today's one-liner for the
   same cards, read rather than scored — the same gate that caught the
   "wins their pawn" undercount.
2. **Every clause replays.** A card may only say what the walk recorded.
   No sentence survives that the board does not prove.
3. **Reuse, do not rebuild.** `board_concepts.newly_trapped_pieces`
   already does the event-vs-state diff with SEE. The trap shape calls
   it. Carrying a second trap predicate is how this measurement went
   wrong in the first place.

## Is it worth building?

Smaller than I pitched. I described five shapes over a 73% story rate;
it is three shapes over 40%, with 45% silent. Against that: the
one-liner is actively misleading on a measured slice — an even trade
told as a loss — and those are the cards a 1200 would most reasonably
trust and be misled by.

My recommendation is to build the three, leave the rest on today's
sentence, and re-measure the residue afterwards with better rules rather
than authoring more templates on instinct.

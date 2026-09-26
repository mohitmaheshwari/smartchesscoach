# opening_knowledge: repaired, and deliberately not promoted

2026-09-26. Written because the plan going in was "mint a
`gap:opening_knowledge:` id so the topic becomes the fourth plannable one".
The measurements say not to, and this records why so nobody spends the hour
again.

## What I went looking for

`opening_knowledge` had one authorized detector,
`left_book_for_a_worse_move`, firing **twice in the whole product**. So the
topic was mute. The plan was to back it with the opening report instead.

## What the data actually said

All 7,507 `opening_knowledge` observations, on production:

```
  subtype                        rows   users   engine-approved   median cp
  (none)                         3814      56             0.0%         121
  unverified_hint                2975      55             0.0%         210
  tempo_wasted_by_repeat          557      48             0.0%         142
  early_flank_pawn_move           159      35             0.0%         149
  left_book_for_a_worse_move        2       2             0.0%         467
```

Two things here are better than expected and one is much worse.

**Better:** every row is already engine-gated. 100% are `mistake` or
`blunder`, 100% are in the opening phase, 0% are moves the engine approved of.
"This was a real error in the opening" is true by construction.

**Worse:** 90% of the evidence (6,789 of 7,507) carries no provable shape --
`unverified_hint` is literally `cp_loss >= 150 and move_number <= 10`. And the
one subtype with real volume was making a false claim.

## `tempo_wasted_by_repeat` was wrong twice over

It told the player: *"opening tempi lost by moving the same piece twice"*, and
instructed him *"don't move the same piece twice unless it captures"*.

**The claim was vacuous.** A knight or bishop standing off its home square has
already moved, so "you moved the same piece twice" was true of **557 of 557**
fires. It carried no information. The code never computed it either -- the
comment in the source admitted it could not -- and what it actually detected
was a **retreat**.

**The accusation was false 43.1% of the time.** In **240 of 557** fires the
engine's own best move moves *that same piece*. So moving it again was not the
error; where it went was.

Negative control, because a high rate proves nothing without one: the same
test over 4,000 opening mistakes generally puts "engine moves the same piece"
at **13.9%**. So 43.1% is a property of retreats specifically, three times
background, not noise.

One fire, chosen because it was the first row returned: `Ng5` at move 10, with
`eval_before` showing the player **winning by four and a half pawns**. He was
being told he had wasted a tempo in the opening.

## The repair

Renamed to `retreated_a_developed_piece` -- the name is now the thing
detected -- behind two gates:

```
  A. the engine's best move moves a DIFFERENT piece        (drops 43.1%)
  B. nothing legally attacks the piece being moved         (drops 29.3%)
```

Gate B exists because a chased piece has to move, and the teachable error then
belongs to the move that walked it into the chase, not to this one. It uses a
legal-capture probe, not `board.attackers()`, which is pseudo-legal and would
count a pinned attacker -- excusing a retreat that was never forced.

**154 of 557 survive.** Spot-checked on the board: `Nf6-d7`, `Bc4-d3` (which
also blocks its own d-pawn), `Nh5-g7` -- all genuine voluntary retreats with
nothing attacking the piece.

The instruction changed with it. It used to be advice about something we never
detected; it is now *"Before you move a piece out, look at where it can be
chased to. A piece that has to come back has done no work."*

## Why it is NOT promoted to plan grade

Measured, not withheld out of caution. The picker scores
`severity_weighted_count x rating_prior` and takes the top, and
`sanitize_plan_observation` filters the ranking and the metric on the same
authorized basis -- so the comparison is just counts. For each of the 33 users
holding a surviving fire, against their already-authorized evidence:

```
  user                openK | piece_safety  king_safety  missed_tactic
  user_a66b5bb10c86      19 | 331           337          111
  user_46f04c4f3b21      17 | 213           185          50
  user_b189135388c9      10 | 330           439          147
  ...                       |
  (33 users, median 3 surviving fires each)

  users where opening_knowledge would outscore every plannable topic: 0 of 33
```

The closest case is 19 against 337, an 18x gap, and severity weights vary by
under 2x across subtypes so weighting cannot reverse it. **Minting the id
would change no user's focus.** It would buy the appearance of a fourth
plannable topic and nothing else, which is the same trick as a detector that
fires twice.

## What would actually make the opening coachable

Not a per-move subtype. The signal that exists is at game level: *which
opening costs this player mistakes*, which `services/opening_report.py`
computes and which needs no book. Measured reach: **43% of users** have an
opening passing the 5-game gate, **51% have one the report can name as weak**.

Acting on that inside the focus loop needs a focus scoped to an **opening**
rather than to a move pattern -- a new kind of focus, measurable
(errors per 100 opening moves in that opening, before vs after) and teachable
(the curriculum tree). That is a real design change and it needs signoff, not
a quiet id.

## What is still a shrug

`unverified_hint`, 2,975 rows, is `cp_loss >= 150 and move_number <= 10`. Its
phrasing is at least honest -- "flagged as this pattern but not board-provable
to a specific subtype" -- so it is left alone. It is where the remaining
opening work is, if anyone wants a real detector.

`early_flank_pawn_move` is left at shadow untouched: 8.2% of its fires are
refuted by "the engine also pushes a flank pawn" against a 5.0% control, which
is too weak a test to condemn it, and 159 rows across 35 users is too thin to
promote it.

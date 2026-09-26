# Scope: derive the why offline, and use it where the caption gives up

Status: DRAFT — needs Mohit's sign-off before any code.
Written 2026-09-25. Every number below is measured, with the run named.

---

## The problem, stated as a number

600 games hold **3,162 cards on the player's own mistakes and blunders**
— about 5 per game. Of those, **853 (27.0%)** render a fallback caption:
a sentence the system reaches for when it could not work out why the move
was bad.

    R12_blunder (and variants)                    ~1,690   53%
    R01_mate (and variants)                         ~423   13%
    R_FALLBACK -> R_PROMOTED_basic_mistake           ~364   12%   <- fallback
    R16_board_state_fallback                         ~290    9%   <- fallback
    R_TIER* floors                                   ~199    6%   <- fallback
    distilled:*                                      ~108    3%

That 27% is the same bucket as the earlier finding that 22.9% of fresh
mistake captions explained neither the punishment nor the alternative.
Two different measurements, one population.

These cards are not badly worded. They are cards where the system had
nothing and had to speak anyway.

## What we already have that fixes it

`services/why_on_demand.py` derives the why from the board and the engine
and **answers 90% of mistakes** (54/60, measured; the earlier 98% was a
40-position overestimate). It is live behind the Why button. Its only
constraint was ever time: 5.4s median, which is impossible during a page
render and irrelevant in a background worker.

So nothing new needs inventing. The derivation moves off the click and
into analysis.

## What we will do

1. **During analysis**, for every user move with cp_loss >= 100, run the
   same derivation the button runs and store the result on the move.
2. **At render time**, use the stored sentence **only where the caption
   rule is one of the fallback tiers** listed above.
3. **Everything else is untouched.** `R12_blunder`, `R01_mate` and the
   distilled rules keep rendering exactly as today.

Expected reach: 27% of mistake cards are eligible, the resolver answers
90% of them, so roughly **a quarter of all mistake cards** gain a derived
sentence. The other three quarters do not change at all.

## Why only the fallback tiers

Because that is where the damage is, and because the blast radius of
"cards that are already bad" is one we can accept. Replacing
`R12_blunder` — 53% of mistake cards — would be a different and much
larger bet, and nothing measured so far says the resolver beats it.

If this ships and holds, widening it is a separate decision with its own
evidence.

## What must be true before any of it renders

**A comparison, not a hope.** Render both the current fallback caption
and the derived sentence for the same few hundred mistakes, put them side
by side, and check the derived one is actually better. My own record in
this area is a reason to insist on this: "it ought to be better" is how
every caption regression in this codebase got shipped.

**A measured cost.** The derivation is ~5.4s per mistake and a game has
~5 of them, so roughly half a minute of engine time per game. Whether
that is acceptable depends on what analysis costs today, which I have not
measured. If it is too slow, the fallback-tier cards alone (27%) can be
derived instead of all mistakes.

**The mismatch gate in place first.** Measured on 108 answers, the
resolver sometimes names a small material gain on a catastrophic move —
"After Qxa7, Rg1+ wins your pawn" at cp_loss 9246. Those must be
suppressed before this reaches a caption, or we will have replaced a
vague sentence with a confidently wrong one. Note the gate is NOT a
simple payoff/cost ratio: `FORCES_RETREAT` carries a synthetic payoff of
`max(1, value//10)`, so a ratio gate would delete 8 good "chases your
knight" captions to fix 5 bad ones.

## What this is not

- Not a caption-pipeline rewrite.
- Not a replacement for the detectors. Measured: every human-ruled
  detector combined fires on at most 21% of mistakes, against the
  resolver's 90%. Where a detector fires it names the *shape*, which
  teaches better than naming the cost — that layering is a later,
  separate piece of work.
- Not a new data source. The derivation reads `fen_before`,
  `pv_after_played` and a live engine call; it writes one field on the
  move it describes.

## How we will know it worked

- The share of mistake cards on a fallback tier falls from 27% toward 3%.
- Every derived sentence replays against the board — no claim trusted
  because of how it reads.
- The cards that were not eligible are byte-identical before and after.
  If anything else moves, the change was wider than intended.

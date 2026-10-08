# Stalemate: the draw nobody is told about

**Status:** built. Measured 2026-10-06 over the full stored corpus.
**Asked for by:** Mohit, 2026-10-06 — "so, we should build a stalemate, can we?"
**Found by:** Farhan, reviewing geometry gaps 2026-09-29. He wrote the
explanation by hand, twice, because nothing in the code computed it:
*"Rd1 is a checkmate winning the game on spot while playing f4 results in a
stalemate (draw)."*

## The population

A stalemate ends the game as a draw. Nothing follows the move. When a player
who was winning plays one, that is the whole story of the game.

Scanned all 18,333 games holding review cards. **132 positions** where the
player who moved was winning (mover-POV eval at or above +300) and the move
they played stalemated the opponent. 68 were the user's move, 64 the
opponent's. Every one is an endgame.

## What was wrong — two different problems

These have to be kept apart, because they have different fixes.

**Stored cards (what a reader sees today).** 127 of the 132 never mention a
stalemate or a draw. 34 read as praise or as a quiet note:

- `Your opponent tidys up the king, keeping it safe.` — on the move that
  turned a lost game into a draw. The best news in that player's game, filed
  as a remark about king safety.
- `Your opponent puts the rook on the open file — rooks belong on open files.`
- `A calm move that keeps their position solid.`
- `Nxf4 allows mate in 2.` — false. The game is over; nothing follows a
  stalemate. 13 cards make this claim.

**Current code (what the fix had to change).** Re-rendering all 132 through
the deployed pipeline shows the praise is already gone — 0 of 132 — and so are
all 13 mate claims. The stored captions came from 40 different code versions
and those two defects belong to code that no longer exists. Only a re-render
clears them.

What current code still got wrong, and what this change fixes:

| | before | after |
|---|---|---|
| says the game is a draw | 1 / 132 | 132 / 132 |
| implies play continues | 75 / 132 | 0 / 132 |

`Rb2 misses a forced win. You get another chance. Use that chance to make your
king safe.` There is no next move. The game ended on Rb2.

## Why the obvious fix does not work

The first attempt added a predicate to `R12_blunder.json`. Under current code
that rule produces 4 of the 132; `R01_mate` produces 124. Patching one rule
file is a zero-delta change on almost all of them.

A second attempt guarded the forced-mate block so a stalemating move could not
be called "allows mate in N". **It moved 0 of 132 and was removed.** All 132
carry an *empty* `pv_after_played` — the game ended, so the engine returned no
line — which means `allowed_forced_mate` cannot be built for them at all. The
guard was unreachable. `TestWhyNoMateGuardHere` records this so it is not
added back on the strength of the stored captions.

## What was built

Stalemate is a property of the board after the move, not of a rule. It is
decided by `board.is_stalemate()`, needs no engine, and it overrides every
claim about what follows. So it sits at the one funnel every rule passes
through, above the final verify, so the sentence is held to the same truth
check as every other caption.

Two facts in `caption_facts.py`, both mover-relative so one fact serves both
sides:

- `played_is_stalemate`
- `played_stalemate_threw_away_win` — the above, and the mover's eval before
  the move was at or above +300. Separate because stalemating a dead position
  saves half a point and is not a mistake, and because a *losing* player who
  stalemates has rescued the game.

`_lead_with_the_stalemate` in `caption_pipeline.py` puts one plain sentence in
front:

- the user gave it away: *"You had this won. Your opponent was left with no
  legal move, so the game is a draw by stalemate."*
- the opponent gave it away: *"Your opponent was winning. Rb2 leaves you with
  no legal move, so the game is a draw by stalemate. Keep playing when you are
  losing. Your opponent can still go wrong."*

Two things it does on purpose:

- **Leads.** It is the headline, and the 60-word cap cuts from the end, so
  what gets dropped is the less important half.
- **Names the move once.** All 68 user-side tails already open with the played
  move, so naming it in the lead too said it twice. The lead names it only
  when nothing after it will.

The tail is kept only when it names the better move. Everything else on these
cards is floor text written because nothing better had fired — the open file,
the calm position, the tidy king — and on the move that ended the game it
reads as praise.

## Result on all 132

| check | result |
|---|---|
| says the game is a draw | 132 / 132 |
| passes the final truth check | 132 / 132 |
| lost a better move it used to name | 0 |
| played move named twice | 0 |
| over the 60-word cap | 0 |
| empty caption | 0 |
| user who gave the win away told so | 68 / 68 |
| user who escaped told so, not blamed | 64 / 64 |

Regressions: none. 635 passed across the caption suites; the 3 failures
(`test_aligned_payoff_caption_authorization`,
`test_simple_hang_caption_authorization`,
`test_mistake_why_and_coherence`) fail identically on the clean tree, and the
24 errors are dev-login 404s that need a running server.
`scripts/pwc_coaching_lint.py`: CLEAN.

## What this does not do

- **Nothing reaches a reader until the stored cards are re-rendered.** The
  code fix alone leaves all 132 as they are.
- It does not find the 562 positions where a stalemating move was *available*
  and avoided. Warning someone off a move they did not play is a different
  feature and needs its own evidence that people want it.
- It does not re-score the 64 opponent moves. They still carry `cp_loss` 0,
  because opponent moves hold no engine truth. This gives them a true
  headline; it does not give them an evaluation.

## Checks

`backend/tests/test_stalemate_threw_away_the_win.py`, 27 tests. Every fixture
is a real position out of the 132, or that position mirrored, and each is
verified against `board.is_stalemate()` inside the test. The first draft used
two hand-built FENs and both were wrong — one of the moves was not even legal
in the position it was written for.

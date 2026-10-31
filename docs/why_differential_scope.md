# Why button, differential engine — scope

Written 2026-10-31 for Mohit, who asked for these changes after run 5 of the
why-engine regression set, and for whoever maintains the why button next.

## What it will be when done

A player clicks "Why was this bad?" on a move in their game review. Within a
few seconds the card shows one or two short sentences in plain English that
say what the move changed and what that let the opponent do, or what the
better move would have done. Every chess fact in the sentence comes from the
engine and the board. The words come from gpt-6-luna, which is given the
facts and nothing else, and is refused if it adds a move, a piece or a square
the facts do not contain. When no mechanism can be shown, the card says so
and names the engine's preferred move, nothing more.

## What changes, in the order it runs

1. **Both branches are measured.** The reply locator Codex built is run on the
   branch after the played move and on the branch after the better move. The
   played-branch drop against the eval gap sorts the move into a family:
   punished (one reply carries the gap), missed (the better move's own line
   carries it) or mixed. A move with no gap is the engine's own choice and
   gets no sentence.
2. **Punished: backwards from the reply.** The reply's footprint (check,
   capture, attack, line opened) is computed after the played move and after
   the better move; only what exists on the played branch is a cause. A piece
   the mover just moved is never its own reason, and a capture both branches
   allow is the exchange, not the reason.
3. **Missed: the better move's first forcing consequence**, read along the
   engine line by the existing resolver, or a double attack the better move
   creates and the played move does not.
4. **Words.** `services/why_words.py` turns the facts into English with
   gpt-6-luna behind `WHY_WORDS_ENABLED`; the deterministic sentence ships
   when the layer is off or refuses.

## Where it lives

- `backend/services/reasoning/differential.py` — the engine work.
- `backend/services/why_differential.py` — the button's budget and the
  response shape, behind `WHY_DIFFERENTIAL_ENABLED` (default off).
- `backend/routes/coach.py` `GET /api/coach/why/{game_id}/{move_number}` —
  differential first, then the existing `why_on_demand` path unchanged.
- `frontend/src/components/GameDecryptionV5.jsx` `WhyThisWasBad` — shows the
  sentence, the better move, and the honest no-reason state.

## How it is judged

The fixed regression set in `docs/qa/why_engine_regression_set.json`, graded
by hand against Stockfish 19 at depth 20, as in every earlier run. The bar
for calling the quality better: the mechanism row rises above 7 of 25 bad
moves on the original 33, no new sentence on the eight good moves, and no
number in any sentence.

## Not in this scope

Changing how the card's severity label is computed; changing the stored
analysis; explaining moves outside the game review page; any sentence that
is not backed by a relation the board shows or a line the engine searched.

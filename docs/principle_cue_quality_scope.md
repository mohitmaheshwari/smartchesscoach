# The teaching cue: what ships today, and the three things wrong with it

Mohit, 2026-10-10, on wanting players to improve from every angle. The honest
finding after two days of measurement is that **the mechanism for this already
exists and already reaches players** — so this is not a build, it is a repair.

## What already works

`principle_cue` is chosen by a fired failure-mode predicate, validated against
an anchor square, stored on the move card, and rendered on the review page as
its own italic line under the diagnosis — unconditionally, no flag:

```
GameDecryptionV5.jsx:2669   {move.principle_cue && (
    "Teaching cue — named-principle habit reminder."
```

**I was wrong twice about this before checking.** I reported the mechanism as
dead because the `_SHELL_RE` gate in `caption_pipeline` matches 0% of cards —
that gate only controls appending the cue *into the caption text*, a secondary
path, and the cue reaches the player through its own field. And I reported 66%
coverage; it is **34%**, because I had conflated `principle_cue` with
`caption_facts_principles_violated`.

A module I wrote to add grounded habits (`grounded_habits.py`) was deleted
rather than committed: its two base-rated habits turned out to be, almost word
for word, the two cues that already dominate this corpus. The base-rating work
survives as the thing that proved what good looks like — and killed two shapes
on the way: a cramped-king shape at **0.97x** and the biggest-share
piece_safety shape at **1.36x**.

## Problem 1 — the same line, over and over, in one game review

This is the biggest and it is not visible in corpus-wide counts.

Of 771 game reviews that show any cue:

| | |
|---|---|
| cue shown once | 214 (28%) |
| the same cue repeated 2–4 times | 407 |
| the same cue repeated 5+ times | 94 |
| worst case | **the same line 24 times in one game** |

**72% of game reviews repeat a cue.** A habit reminder read once is coaching;
read six times in twenty minutes it is a tic, and it teaches the player that
the line is generated rather than meant.

The cause is concentration: 28 distinct strings, and two of them are 85% of all
instances —

```
633  Forcing move available — check, capture, or threat.
469  Watch the loose piece — yours or theirs. Count attackers and defenders
     before deciding.
```

**Fix:** per-game dedupe in the decryption loop, where the cue is already being
validated against its anchor square. Show a given cue at most once (or twice)
per review; suppress the rest. No new mechanism, no new content, and it works
on the strings that exist today.

## Problem 2 — a quarter of what players read uses a term we never defined

Of 7,100 cue instances actually shown, **1,722 (24%)** contain a term that a
600–1500 player has not been taught:

| term | where |
|---|---|
| "loose piece" | the 469-instance cue — the second-most-read sentence in the product |
| "bad bishop" | *"your bad bishop is locked behind pawns and needs a reroute or trade"* |
| "rim" | *"This rim move works here"* |
| "doubling that file" | *"they recapture with a pawn, doubling that file"* |
| "the opposition" | *"Take the opposition"* |
| "Tarrasch's rule" | *"Rook behind the passed pawn — Tarrasch's rule"* — names a person |

**Fix:** rewrite in place. Same predicate, same trigger, plainer words. "Loose"
becomes "a piece nothing of yours is guarding". Tarrasch's name goes.

## Problem 3 — coverage, and it is the least urgent

`principle_cue` is on **34%** of mistake cards (1,296 of 3,762). Two thirds get
a good diagnosis and no habit.

This is listed last on purpose. Raising coverage while 72% of reviews already
repeat themselves would make the repetition worse, not better. **Dedupe first,
then widen.**

## Smaller, and real

**Provenance leaks into the lesson** — 184 instances (3%): *"Push the passed
pawn. Engine agrees"*, *"Castle now. Best move — O-O is the top engine pick"*.
A coach does not cite his tools. I originally called this the most systematic
problem; measured, it is the smallest of the three. Cheap to fix and worth
doing while the strings are open.

**Hedged openers** — 325 instances (5%): *"Other plans this move. Generally —
endgames need an active king"*. The hedge reads as a non-sequitur before the
teaching arrives.

**One predicate, two strings** — `OP_F2_F7_STRIKE` ships both *"f7 (or f2) is
defended only by the king in the opening. Take it when you can win material"*
and *"Capture on f7 — defended only by the king."* Same for `OP_TRAPPED_KNIGHT`
and `TAC_TRAPPED_PIECE`. Harmless, but it means the corpus is larger than the
authored intent.

## What this needs from Mohit

The 28 strings are player-facing text, so the keep / rewrite / drop call is
his. The full list with instance counts and predicate ids is in the session
record; the ones I would argue for regardless are the six jargon terms above
and the "Engine agrees" family, because both are wording fixes with no
detection risk.

## How we will know it worked

A player finishing a game review should not be able to recall the cue wording
because they saw it repeatedly. Measured: the share of reviews showing the same
cue more than twice, which is 50% today and should be near zero.

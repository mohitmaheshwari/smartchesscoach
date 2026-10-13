# One why, both sides — Scope (plain English)

> Status: **DRAFT, awaiting Mohit's sign-off.** No code until he agrees §2.
> Written 2026-10-13 after he said "why for user should work same as why
> for opponent", then chose **A — unfork** over reviving the dead
> opponent branch.

## 0. The one idea

**There is one question — "why was this move bad?" — and it should have
one answer, with the voice chosen at the end.**

Today the same question is answered by two separate machines that share
nothing. Which side moved decides which machine runs, and one of the two
has never produced a word.

## 1. What is actually there now

Measured, not assumed. All figures from the current code.

| | user side | opponent side | shared |
|---|---|---|---|
| why clauses | 39 | 23 | **0** |
| failure-mode clauses | 10 | 11 | 0 |
| fact keys those clauses read | 36 | 32 | **0** |

28 of the opponent side's 32 fact keys are just the user idea with an
`opp_` prefix in front of it. The duplication runs the whole depth of
the stack: **detector → fact → clause → variant → template.**

Only one concept exists on both sides at all (`knight_on_rim`), and it
is written out twice.

**And the opponent half has never run.** `R12_blunder` — the rule that
says "X is a mistake. Y was better — it {why}" — writes **83.7% of the
user's cards and about 0% of the opponent's**. So those 23 clauses, 11
failure modes and 28 facts have never reached a reader.

## 2. THE DECISION Mohit is being asked to make

**One set of why-logic for both sides. The side picks the wording at
render time, nothing else.**

- one detector per chess idea, not one per idea per side
- one fact key per idea (`hanging`, not `hanging` + `opp_hanging`)
- one clause list
- the only thing that branches on who moved is the sentence: "you" vs
  "they", "your knight" vs "their knight"

Everything in §5 follows from this. If he disagrees, the rest does not
matter.

## 3. Why the fork is the thing generating the bugs

Every opponent-card defect found on 2026-10-12/13 was the same shape —
one side had something the other did not:

- opponent cards explained nothing: **0 of 2,739** stated a why, while
  the fact was already computed on 63.4% of them
- opponent **inaccuracies** named no better move: **2,934 of 2,936**
- `_better_suffix` opened with `if not mover_is_user: return ""`
- the say-better backstop carried `and inputs.mover_is_user`
- the reply-why never passed `mover_is_user`, so it spoke in the
  neutral voice
- possessives were literal: "your knight" on **288 of 2,739** opponent
  cards, in two separate places
- a **316cp blunder** rendered as "a calm move that keeps their
  position solid"

Each was fixed one at a time. The fork is why there was a queue.

## 4. The root cause under all of it

`facts["cp_loss"]` means **the user's loss**. On an opponent card it is
`0`. Five separate layers read it as though it meant "how bad was this
move":

1. the rule triggers — 8 of 28 rule files gate on `cp_loss`
2. the dict `caption_rules.py` hand-builds for the trigger
3. R12's suppression rules (`cp_loss < 250` is always true at 0)
4. `severity_practical`, derived from the user's loss, so every
   opponent move reads "good"
5. rule selection, which still did not pick R12 after 1–4 were patched

Patching 1–3 in one sitting on 2026-10-13 revealed 4 and then 5, and
briefly took `R12_blunder` from 83.7% of user cards to zero. That was
reverted. **A rename cannot fix this; the layers have to learn whose
move they are describing.**

## 5. The order of work

Each step ends with the regression control green (§6).

1. **Carry the mover's own loss end to end.** One field, set once, read
   by every layer that asks "how bad was this move". `cp_loss` keeps
   its current meaning for the 31 readers that genuinely want the
   user's loss.
2. **Make severity side-aware.** `severity_practical` for the move's
   own mover, so a 303cp opponent move stops reading "good".
3. **Merge one concept end to end as a pilot** — `knight_on_rim`, the
   only idea already written twice. One detector, one fact, one clause,
   voice at render. Prove the pattern on the smallest possible case.
4. **Merge the rest**, lowest-traffic first, deleting each `opp_` twin
   as its concept lands on the shared path.
5. **Delete the dead opponent branch** once nothing references it.

Steps 1 and 2 are worth doing even if §2 is rejected: they remove the
"calm move on a 316cp blunder" class on their own.

## 6. How we will know it worked

- **Regression control, every step:** `R12_blunder` writes **83.7%** of
  user cards and the user fact rates do not move. This already caught
  one bad change in minutes.
- **The gap closes:** opponent cards reach the same rule mix as user
  cards, rather than falling to the describe-only tiers.
- **No new silence:** the share of cards carrying a reason does not
  drop on either side (user 65.8%, opponent 63.7% today).
- **Verification unchanged:** the per-FEN claim verifier passes at the
  same rate it does now (551/551 on the sample measured).
- **Count goes down:** 60 clause variants and 68 fact keys become one
  set. If the merge does not reduce the count, it is not a merge.

## 7. Risks

| risk | what we do about it |
|---|---|
| a merged clause is right for one side and wrong for the other | the pilot (§5.3) is a concept that already exists on both sides, so the two authored versions can be diffed before merging |
| the user side regresses while chasing the opponent side | the 83.7% control runs on every step, and it is the number that caught the last attempt |
| voice leaks — "your knight" about their piece | already has a source-level test that scans every returned string for a literal possessive |
| a fifth layer appears, as it did on 2026-10-13 | each step is shippable alone and reverts alone |
| the opponent branch holds a lesson the user side lacks | before deleting any `opp_` clause, check whether its concept exists on the user side; if not, it moves over rather than being dropped |

## 8. Out of scope

Re-analysis of pre-2026-09-25 games (a Stockfish cost, already
measured), the shadow-graded principle catalog, and the board-state
filler sentence — which is **load-bearing**, since removing it silently
downgrades the verdict tier, and needs its own decoupling first.

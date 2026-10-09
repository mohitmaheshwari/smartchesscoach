# Teaching the three gaps — scope

Mohit, 2026-10-09: *"I need users to really see an amazing product that helps
them improve overall from each perspective — from what they know but keep
making issues, from what they don't know, from all perspectives."*

Those are two different problems that need opposite treatments, and the product
currently does one of them at enormous scale and the other barely at all.

## The asymmetry, measured

| | |
|---|---|
| ways to **practise** | **52,341** drill positions + **47,071** puzzles |
| things that **teach** | **54** endgame lessons across 6 topics, **26** teachable openings of 79, ~**60** opening traps |
| the pattern catalog | 35 entries, median **78 characters** each, and **0 of 35** carry a showable position |

And the gaps with the most authored content are the ones users need least. Over
7,795 user moves in 1,500 analysed games:

| gap | share of all mistakes | what teaches it |
|---|---|---|
| `king_safety` | **27.8%** | nothing |
| `piece_safety` | **27.1%** | nothing |
| `missed_tactic` | **23.6%** | nothing |
| `opening_knowledge` | 11.3% | 26 teachable openings |
| `endgame_technique` | 8.6% | 54 lessons, 6 topics |
| `tactical_oversight` | 1.6% | nothing |

**78.5% of every mistake our users make has unlimited practice and nothing that
teaches the idea.** The two gaps with real content are the smallest two.

**A correction to an earlier draft of this finding.** I first measured "zero
teaching content for the top three gaps" from a probe that silently failed to
parse `pattern_catalog.json` and returned an empty table. There *is* content.
It reads like this:

> `missed_mate` — "There was a forced mating sequence — every opponent reply
> loses."

That names a pattern. It does not teach anyone to see one, and with
`example_fen: null` on all 35 it cannot even be shown. So the honest statement
is **thin and unshowable**, not absent.

## 1. Find out which axis the problem is. This comes first and costs almost nothing.

`user_misconceptions`: **0 rows.** `home_today_answers`: **0 rows.**

The question shipped yesterday — *"before I tell you anything, what were you
checking?"* — is the only instrument in the product that can tell the two
problems apart. A hanging piece looks identical whether the player knows the
rule or has never heard it; only the player can say which.

- picks the **right** belief and was still wrong → they know it, the count
  slipped → **interrupt it in the moment**
- picks a **wrong** belief → they never knew → **teach it**

Nobody has answered it yet, because it lives on one card for one topic. Put the
same ask on the **review path**, where players already sit looking at their own
mistakes, and read the split.

Until that number exists, "they know it but keep slipping" is our assumption,
not a measurement — and it decides whether the next quarter is content or
interruption. This is the highest-value cheap thing available.

## The gap labels are buckets. Measured, with base rates.

Before authoring anything I measured what each gap's mistakes actually ARE, and
then -- after getting it wrong once -- what share of *all* moves share the same
shape. Only the ratio means anything.

### king_safety: nothing teachable found. My first answer here was wrong.

1,272 mistakes. No shape above 15% in combination. The largest single fact was
"the king had two or fewer safe squares" at 55%, rising to 62% including kings
with none, and **I reported that as the dominant teachable case, wrote a lesson
for it and built a detector on it.**

The control killed it:

| | fires on king_safety mistakes | fires on all moves |
|---|---|---|
| king has two or fewer safe squares | 57% | **59%** |

**0.97x -- it fires more often on ordinary moves than on mistakes.** Obvious
afterwards: a castled king has its own pawns on the squares in front of it, so
cramped is the normal state of a *safe* king. 8,305 of the fires were at
exactly two squares.

So there was no finding, and the detector had no discriminating power. It is
deleted rather than left in the tree, and this note exists so nobody rebuilds
it. **The 21% pawn-push slice I originally drafted a lesson for was a minority
case picked from intuition**, which is why the draft read like filler.

`king_safety` gets no lesson until something in it survives a base rate.

### missed_tactic: real signal, and one lesson worth writing

1,118 mistakes, every shape base-rated against 27,324 user moves:

| shape | in the gap | everywhere | ratio |
|---|---|---|---|
| the best move was a **check** | 39% | 10% | **4.09x** |
| it was mate | 3% | 1% | 3.30x |
| a capture | 30% | 11% | 2.69x |
| one move hit two pieces | 13% | 5% | 2.57x |
| a free piece was sitting there | 24% | 11% | 2.05x |

**When a player misses a tactic, the move they missed is a check four times
more often than chance.** That is the one lesson this measurement supports:
*look at every check first.* It covers two in five missed tactics and it is
about as teachable as chess advice gets.

### piece_safety: three causes, roughly equal, no single lesson

1,222 mistakes: moved a piece that was guarding something 32%, moved it onto an
undefended square 31%, left another piece loose 31%, none of the above 23%.
Three crisp and separately nameable errors rather than one idea. Not base-rated
yet -- and on this page's record, that must happen before any of them is called
a finding.

## 2. Author one lesson, not three

One real lesson each for king safety, piece safety and missed tactics. Three
pieces of content covering 78.5% of mistakes. Not a curriculum — one page each
that a 1200 player finishes and remembers.

### The rejected draft, kept as a record

Mohit on the king-safety draft below: *it does not make sense, it is not easy
language*. He was right, and the cause was method rather than wording. It
stacked a metaphor (a hole is a door) on top of a chess term, and it taught a
21% slice chosen from intuition. The base rate later showed the 62% condition
it rested on was not a condition at all. Kept because the failure is more
instructive than the text.

### What one looks like (draft, for your voice call)

The card is the product, so here is the literal thing before any schema:

> **The move you missed was a check**
>
> When you are looking for a strong move, look at every check you can give
> first. Not because checks are always good. Because a check forces them to
> answer, so there is a short list of replies and you can see to the end of it.
>
> Most of the time you will look at a check and find it leads nowhere. That is
> fine. It costs you a few seconds and it is the cheapest way to find the moves
> that win.
>
> When you miss something in your games, it is a check more often than anything
> else.
>
> **The habit: before you move, name every check you have. Then decide.**

Short sentences, one idea each, no jargon, a principle at the end they can
carry into a game.

**One lesson, not three.** king_safety has nothing that survives a base rate,
and piece_safety has three equal causes and has not been base-rated yet. This
is the only one the measurement supports today, and it is worth more than three
written on confidence.

### And give the 35 catalog entries a position

`example_fen` is null on every one. A pattern you cannot be shown is not
taught. This is the smallest possible fix with the largest reach, because the
catalog is already wired into coach memory and the concept bridge.

## 3. Build no new surfaces

This is a constraint, not a nicety. In one day of work on this codebase:

- the home page redesign was built into `CurriculumHome`, which **0 of 128
  users** reach
- `assign_strength()` had **zero callers** anywhere, so every stored strength
  was 97 days old
- `focus_outcome_loop` measured 53 focuses daily and **discarded every result**
- `played_at_utc` was repaired and decayed within hours because nothing kept it

Reach is the constraint, not supply. Every item above shipped, worked, and
reached nobody.

## Out of scope, named so it is not lost

- **The milestone chain as a page section.** Built and tested
  (`services/progress_chain.py`), but it reaches 20 of 128 users with a settled
  verdict and those verdicts are mostly "did not move" and "got worse". A list
  of those is a failure scoreboard. One line, gated per user, when it ships.
- **More drill supply.** There are 99,412 positions. Adding any is work that
  cannot help.
- **Any claim that we caused an improvement.** The within-user
  difference-in-differences exists and finds no detectable effect, which is
  expected while the product is not yet live.

## How we will know it worked

Not engagement. Whether the answer split in step 1 moves: if players who were
taught a gap stop picking the wrong belief about it, the teaching landed. That
is measurable per player, needs no cohort, and cannot be faked by someone
scrolling.

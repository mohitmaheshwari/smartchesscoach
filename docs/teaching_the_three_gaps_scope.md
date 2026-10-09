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

## 2. Author for three gaps, not thirty

One real lesson each for king safety, piece safety and missed tactics. Three
pieces of content covering 78.5% of mistakes. Not a curriculum — one page each
that a 1200 player finishes and remembers.

### What one looks like (draft, for your voice call)

The card is the product, so here is the literal thing before any schema:

> **Why your king keeps getting caught**
>
> Your king is not in danger because it is in the middle. It is in danger when
> the squares around it are empty and theirs are not.
>
> Look at the three squares in front of your king. If you have moved those
> pawns, there is a hole, and a hole is a door. One piece cannot use a door.
> Two can.
>
> So before you push a pawn in front of your king, ask what gets in behind it.
> If you cannot see anything, push it. If you can see one of their pieces that
> could sit there, that pawn is doing a job where it is.
>
> **The habit: count their attackers near your king before you move a pawn in
> front of it.**

Short sentences, one idea each, no jargon, a principle at the end they can
carry into a game. Same shape for the other two:

- **piece safety** — how to check the square you are landing on, and why the
  piece under attack is usually not the one in danger
- **missed tactics** — where tactics come from: two of their pieces on a line,
  a piece with nothing behind it, a king with few squares

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

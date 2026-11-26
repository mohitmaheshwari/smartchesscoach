# Why ChessGuru

What we do that no other chess product does, and the evidence for each claim.

Written 2026-11-26. Companion to [human_coach_gap_map.md](human_coach_gap_map.md),
which establishes the gaps. This document is the other half: why we are the
ones who can close them.

Every number here was measured. Where something is not built, it says so.

---

## Two front doors, one engine

ChessGuru is entered two ways, and who sees what differs.

**An academy signs up.** The academy has students. The human coach stays in
the loop and is the one the parent trusts. The coach receives the student's
behaviour reports and the week's teaching material. We make that coach able
to handle more students without working more Sundays.

**A player signs up on their own.** There is no human coach, so the AI is the
coach. Same engine, same lessons, no reports to a third party.

The distinction matters most for the third pillar below: **behaviour is always
measured and tracked for everyone, but the reports are saved and surfaced for
academy users only.** A direct user is not having a file kept on them for
someone else to read.

---

## 1. The coach teaches the games where only one move won

**What it is.** We search a player's own games for a position where exactly
one move wins and every other legal move draws or loses. Those positions are
where a lesson has a sharp edge: there is a right answer, there is a reason,
and the student can be asked before being told.

The coach then produces a script in the shape a person actually teaches in —
the tempting move dismissed in a sentence, then the whole of the time spent on
the win, with the opponent fighting back and getting smarter.

**Why nobody can be wrong about it.** This is the part that matters, and it is
the reason we start in the endgame.

Every AI chess coach today is an *opinion engine*: an engine evaluation,
rephrased by a language model. That rephrasing is unreliable, and the whole
field has the problem — a published review caught DecodeChess explaining that
a queen on c7 guarded g3 when the queen was on d8 and g3 was empty. We have
the same problem when we work that way: 87 of our own model-written captions,
read by hand, came out 32 true, 22 weak, **33 wrong**.

You cannot prompt your way out of that. So we changed the content instead.

In a king-and-pawn endgame with few pieces, the position can be solved
**exhaustively** — every move played to the end. The answer is not an
evaluation, it is a proof. For example, pawn on a5 against a white king on e4,
every king move solved to termination:

```
Kd3  Kd4  Kd5  Ke3  Ke5   HOLDS  (the king catches the pawn)
Kf3  Kf4  Kf5             LOSES  (the pawn queens)
```

No engine, no score, no opinion. A lesson built on that cannot be 38% wrong.

Above that size we use search, and a position only becomes a lesson if one
move clears a clear winning bar *and the second-best falls well below it*. A
choice between +600 and +580 is rejected rather than sold as an "only move".

**Maia tells us what this player would actually have played.** Not what
Stockfish prefers — what a human at their rating reaches for. On one real
position, a 1400-rated player:

| Move | % of 1400s who play it | Truth |
|---|---|---|
| **Ne6+** | **67.0%** | **wins** |
| a5 | 17.9% | draws |
| Nd5+ | 8.6% | draws |
| Ne8 | 3.8% | draws |

**33% throw the win away**, and we know exactly which moves they throw it away
with. So the script opens on the move the student was about to play, not on
the solution.

**The discipline: a model never chooses a move.** The search produces a tree —
the only move, the alternatives ordered by how likely this rating is to play
them, the defender's tries each with our answer and whether it is forced, the
main line. A language model turns that tree into sentences and decides nothing.
If a sentence cannot be traced to a field of the tree, it does not ship.

**Status: built and running.** The generator, the exhaustive solver and the
coach-facing skill are live in the repo. A real generated script, start to
finish, with no human author:

> You are Black, and you are winning. There is exactly one move that keeps it.
>
> The move that will occur to you is **a5**. About 18 in 100 players rated 1400
> play it here. It only draws.
>
> Strip the board down to the king and the running pawn and count: the king is
> in time.
>
> The move is **Ne6+**. It is the only move on the board that wins.
>
> If they try **Ke3** → you answer Nxg5. `2...Nxg5 3.h6+ Kxh6 4.Kd3 Ne6 5.Kc4 Nc7`
> If they try **Ke4** → be careful: Nxg5+ is the only reply of 14 that still wins.
> If they try **Kg4** → you answer a5. `2...a5 3.g6 a4 4.Kf5 a3 5.Kxe6 a2 6.Kd5 a1=Q`

That last branch is worth noticing: the generator found the pawn queening
because the king strayed — the rule of the square, returning as the winning
idea. Nobody wrote that. Search produced it.

---

## 2. The coach works out what you already understand

**What it is.** Before teaching a concept, find out whether the student
already has it. When we are not sure, **ask** — show a position of the same
type and let them answer. Right, we move on. Wrong, that is the moment to
teach, because they now want to know.

**Why asking is safer than telling.** When we show a position and ask "what is
the move?", the engine knows the answer. We cannot be wrong about the grading.
Our unreliability lives entirely in the *explanation*, and in this design the
explanation only fires after the student is already wrong and already curious.
It is the first product shape that routes around our real weakness instead of
walking into it.

**One right answer is not understanding.** A single correct answer is
recognition, or luck. So a correct answer earns a second question on a related
position **where the answer is different**. A student who guessed the same way
twice is caught; a student who counted gets both. Two correct answers with
opposite outcomes is the bar for "they know this".

**It has to be ordered.** A course that teaches an opening on Monday and an
advanced endgame on Tuesday is not teaching, it is shuffling. Every concept
sits behind its prerequisites, and the coach will not offer one until the
student is ready for it.

**Status: scoped, not built.** The substrate exists and is real — a per-user
per-concept mastery machine with 4,224 rows across 76 users, a question bank of
11,812 positions drawn from real games with their own explanations, and a
curated diagnostic pool with frozen grading so a score cannot drift between
versions.

What does not exist, and is the actual work:

- **No ordering.** There is no prerequisite or difficulty field anywhere on a
  concept today. This is the piece that makes it a course instead of a pile.
- **The teaching text is broken.** `concept_text` is the sentence we would say
  to a student, and 1,297 concept ids carry more than one conflicting version
  of it. It is being rewritten before anything speaks to a student.
- **We start with the 15 concepts whose answers are provable** — 5 endgame and
  10 tactical. The 20 positional ones ("bad bishop", "pawn break") have no
  provable answer and wait until the format has earned trust.

Scope and open questions: [guided_concept_curriculum_scope.md](guided_concept_curriculum_scope.md).

---

## 3. Behaviour detectors — always measured, reported to academies

**What it is.** Not just what the student played, but how they decided:
whether they unravel after a mistake, whether their thinking collapses late in
the game, whether they rush the one move that mattered.

These run for every player, always. **The reports are saved and shown for
academy users** — the coach and, through the coach, the parent. A player who
signed up on their own is measured so the coaching can adapt, but no file is
kept for anyone else to read.

**What we actually found, including what we disproved.** Measured on 8 players
with 300+ analysed games each, using only timestamps, results, rating gaps and
the clock — nothing that moves when a detector version changes.

The signal is **inside** the game, not between games:

| Reading | Result |
|---|---|
| Lost over the 3 moves after a **big error** | **85.1 cp** (n=7,008) |
| Lost over the 3 moves after a **good move** | 53.2 cp (n=75,880) |
| **Ratio** | **1.60×** |
| Big errors followed by three rushed moves | **33%** |

And by phase:

| Phase | Mean cp lost | Big errors | Median think |
|---|---|---|---|
| moves 1–15 | 39.3 | 3.7% | 3.0s |
| moves 16–30 | 71.4 | 10.0% | 5.7s |
| moves 31+ | 59.1 | **8.3%** | **2.9s** |

That last row is the most coachable fact we hold: after move 30 the student is
still making big errors at more than twice the opening rate, while thinking for
half as long as they did in the middlegame. A coach says that in one sentence
and it changes how the child plays.

**What we disproved, and will not sell:**

- **Tilt, as everyone describes it, is not in our data.** Accuracy after a loss
  is 62.7 against 62.4 after a win. After *three straight losses*, 73% played on
  anyway — and that next game scored **63.2**, above their own average.
- **Endurance barely moves**: game 1 of a sitting 63.3, game 6+ 62.0.
- **A detector we already ship does not work.** `rushed_critical` fires on
  11.5% of games and the accuracy is 59.5 when it fires against 59.3 when it
  does not. No difference. It is being fixed or retired before any report
  quotes it.

We publish the ones that survived and drop the ones that did not. That is the
difference between a report a coach can defend to a parent and a horoscope.

### On "brain development"

We do not claim chess builds your child's brain. The research is mixed — a 2025
Spanish study of 8–12 year olds found **no** improvement in working memory,
planning, flexibility or initiative. The first informed parent who checks will
find that.

What we do claim is narrower and true: **we measure how your child makes
decisions under time pressure in their own games, and we report what changed.**

---

## What this is worth to an academy

A coach's unpaid hours are spent reading games and writing reports. We read
every game and hand them: these four students all lost the same way this week,
here are the positions, here is Saturday's opener. The coach keeps the
judgement and the relationship. The parent keeps the coach they trust.

A coach writing thirty reports costs the same again for the thirty-first
student. Ours does not.

---

## What is true today, plainly

| | |
|---|---|
| Only-move lessons | **Built.** Generator, exhaustive solver and coach skill all running |
| Maia-conditioned scripts | **Built.** Verified at 1100–1500 |
| Behaviour measurement | **Measured.** Not yet surfaced in a report |
| Concept course | **Scoped.** Ordering and teaching text are the open work |
| Academy reports | **Not built** |

**The limits we would rather you hear from us:**

- **Yield is low on purpose.** About one teachable position per 50 games,
  because we only accept positions whose answer can be proved. A player's own
  games seed the lessons; generated position ladders supply the volume.
- **Nothing positional yet.** No provable answer, and that is exactly where our
  text has been unreliable.
- **We have no outcome evidence.** Aimchess cites a 12-week randomised trial
  claiming 31% faster rating gain. We cannot match that claim today, and
  measuring whether our approach works is part of the build rather than a
  later phase.
- **We are not live at scale.** Roughly 120 registered users, most predating
  these features.

---

## The one-sentence version

Every AI chess coach is an opinion engine that rephrases an evaluation and is
wrong often enough to matter. We teach the positions whose answers can be
*proved*, we know which wrong move this player would have chosen, and we ask
before we tell — so the coach is right by construction rather than by luck.

---

## Appendix — defending each claim

| Claim | Where it came from |
|---|---|
| 33 of 87 captions wrong | hand-read of model-written captions, 2026-11-13 |
| Exhaustive king-move solve | full game-tree search, no engine |
| Ne6+ unique winner, others 0.00 | Stockfish depth 40, every legal move scored |
| Maia percentages at 1100–1500 | Maia-2 `0.11.0:rapid`, run per rating |
| 1.60× after a big error | 8 users, 954 games, ~36,000 of their own moves |
| Phase table | same sample |
| Tilt and endurance flat | 8 users, 300+ analysed games each |
| `rushed_critical` no difference | 1,514 games where it fires vs a 4,000-game comparison |
| 36 concepts, no ordering field | prod schema, 2026-11-26 |
| 1,297 conflicting `concept_text` | prod scan, 2026-11-26 |
| ~1 lesson per 50 games | live generator run |
| Competitor claims | Chessiro's and Aimchess's own pages, read 2026-11-26 |
| Spanish executive-function study | published 2025; summary read, not full text |

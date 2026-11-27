# The coach: what it must do, and where each piece actually is

The standing record of Mohit's product decisions for the coaching product,
so nothing is lost between sessions. Last updated 2026-11-27.

**Read the status column honestly.** "Built" means the code exists and runs.
It does not mean a user can see it. Today **nothing in this document is
visible to a user.**

---

## 0. The rule that sits above everything

> A mistake is one of two completely different things, and they need
> opposite responses.

**Mohit, 2026-11-26:** *"Even best players like Magnus can sometimes let a
piece undefended. Giving somebody who is good at chess practice for
undefended piece is not going to have him use the site… human coaches don't
give you exercise when you blunder something from eyesight, because they know
you know this."*

| The mistake was | The right response |
|---|---|
| **A knowledge gap** — they did not know it | Teach it. An exercise is correct. |
| **An execution failure** — they knew it and missed it | **No exercise.** Name the real cause: the clock, where their attention was, which part of the board. |

Handing a competent player a drill for something they already know is the
single fastest way to lose them. Every other product treats every mistake as
a training gap; that is the thing we are not doing.

**This is upstream of everything below.** Pillar 1 as built today does not do
it, which means the one piece that is built is built wrong in the way that
matters most.

**Supporting measurement we already had and then ignored** (player-causes
work, 2026-11-10): tactical failures at these ratings are *blindness* —
the patterns are known by everyone — while development correlated at r 0.89
as the genuine knowledge axis.

### The drill rule and the behavioural reading — BUILT 2026-11-27

**Mohit's rule, in his words:** *"it should be counted by opportunity exists
vs opportunity taken... if a one move blunder exists and if that is 25%,
player still need to do the drill. If that's less than 25%, then we would try
to understand why this error existed, was this a time pressure thing, was
this an eye sight or was player distracted, not focused... chess is just not
calculation and tactics, chess is also focus and behavioral tactics, so
that's what we want to track."*

A rate over his last ten games, not a count. At or above 25% he drills; below
it the step is withheld and the player is owed a circumstance.
`RATE_WINDOW_GAMES = 10`, `DRILL_RATE = 0.25`, `MIN_OPPORTUNITIES = 20`.

Verified on prod through the real build path, 63 users: **48 have a withheld
step, 4 drill** (45%, 35%, 32%, 27%). 102 tests pass.

**Ten games is enough for this and not for other questions.** Proving a big
difference is cheap; proving absence is expensive. The window holds a median
of 44 opportunities, so the bar is ~11 fires against ~3 for a typical player.
By contrast `player_coach_habit.change_state` cannot declare a habit GONE for
any habit rarer than about one game in nine, because its 20-game window
cannot clear a one-sided p<0.10 — see §4.

#### What the behavioural reading may say

`services/player_behaviour_reading.py`. A cause counts only if it is commoner
among the errors than among the SAME opportunities that went fine. Measured
over 1,200 games and 5,466 eligible decisions, base rate 8.29%:

| signal | n | with | without | lift |
|---|---|---|---|---|
| time pressure (<60s left) | 218 | 14.68% | 8.05% | **1.82x** |
| unravelling (big error in last 3) | 1,539 | 10.14% | 7.56% | **1.34x** |
| late game (move 31+) | 672 | 10.42% | 7.99% | **1.30x** |
| snap move (<= 1/3 his pace) | 382 | 6.02% | 8.49% | **0.71x** |

**The commonest reason a piece gets hung is that a mistake was just made** —
unravelling covers 34.4% of errors, more than everything else together.

**Refused, and guarded by a test:**

- **Moving fast is not a cause; it is protective** (0.71x). "Eyesight" and
  "he rushed" are the same guess, and the data has now refused it three
  times — the teaching triage's `rushed` rule was backwards too.
- **Tilt**: dead. **Board region**: dead.

**The ceiling, which stays visible:** at least one signal covers 49.7% of
errors and **nothing covers the other 50.3%**, so `not_explained` is a
first-class answer. A cause is never claimed when it covers fewer errors than
"we cannot say" does.

#### Still missing

- **Exactly one detector carries a `quality_id` AND an opportunity count**
  (`destination_safety_exact`), so the whole rule applies to piece safety
  only. `ignored_king_attack` and `missed_fork` — the steps plans actually
  show — have none. **This is the next build step.**
- **Do not let other detectors get opportunity counts before the reading
  covers them**, or a 25% bar suppresses nearly every drill at once.
- A step withheld with **zero** errors in the window is not the same as one
  withheld with few: the first means he appears to have stopped, and deserves
  saying so rather than a reading. Not built.
- `piece_safety_decision` is eligible 4,318 times and has **never fired**.
  Dead detector; same shape as `missed_free_piece`.

### The earlier percentile gate (superseded 2026-11-27)

Signed off by Mohit 2026-11-27 ("stop drilling what they know" as the release
scope). `own_reliability` / `already_reliable` in
`backend/services/player_coach_plan.py`, fed by `_reliability_pipeline` in
`player_coach_file.py`; 75 tests pass and the real `build_file` was run
against prod.

**What changed on Mohit's own live plan:** step three
(`gap:piece_safety:destination_safety_exact`, stake +0 over 0 games) is gone.
A step with no affected game in the window is no longer shown while an
evidenced step survives.

**What did NOT change, and must not be oversold:**

- **The reliability gate is a no-op on his account.** Measured over 400,000
  observations, 37 users with 200+ opportunities ran min 0.9%, p25 3.8%,
  median 6.0%, p75 10.7%, max 30.4%. He is at 4.1% — roughly the 30th
  percentile, not mastery. An absolute "90% correct" bar would have withheld
  the step for 26 of those 37, so the bar is the measured best quartile per
  detector, and he sits outside it.
- **Exactly one detector in the system carries a `quality_id` AND an
  opportunity count**: `destination_safety_exact`. The two steps his plan
  actually shows — `gap:king_safety:ignored_king_attack` and
  `gap:missed_tactic:missed_fork` — have no structured verdict, so the gate
  cannot evaluate them at all. For the things we recommend, we still cannot
  tell whether he already knows them.
- `piece_safety_decision` is eligible 4,318 times and **has never fired
  once**, on the identical denominator where `destination_safety_exact` fires
  177 times. That is the positive control: a dead detector, same shape as
  `missed_free_piece`.

**So the next build step is not the gate — it is opportunity counts.** Give
the king-safety and missed-tactic detectors an `eligible`/`fires` verdict with
a `quality_id`, and the gate starts working where it matters.

---

**Status: BUILT 2026-11-27.** `triage()` in
`backend/services/teaching_script_builder.py`, wired at
`backend/scripts/build_teaching_scripts.py:233` -- an `execution_failure`
verdict short-circuits before the expensive branches and is written as a
behaviour row instead of a lesson. The gate is described in §6.

It has produced **zero** behaviour findings so far, because only one
position in ~100 games has reached it. Built is not the same as exercised.

---

## 1. Two front doors

| Entry | Who coaches | Who sees the reports |
|---|---|---|
| **Academy signs up** → academy → students | The human coach stays in the loop, and is who the parent trusts | The coach, and through them the parent |
| **Player signs up alone** | The AI is the coach | Nobody. No file is kept for a third party. |

Same engine underneath. The difference is who receives what.

**Status: not built.** Academy collections exist from the older pilot,
verified in prod 2026-11-27: `academies` 1, `academy_students` 2,
`academy_staff` 1, `academy_batches` 1, `academy_class_sessions` 10,
`academy_student_weeks` 8, `academy_class_games` 1,
`academy_homework_attempts` 1, `academy_parent_reports` 1.

---

## 2. Content from games where only one move won

**Mohit:** *"Games with only 1 move, else other moves were drawable or
losing, our coach picks up those games and teach those concepts well, Claude
will write down coach script with Maia moves."*

- Find a position in the player's own game where exactly one move wins and
  everything else draws or loses.
- Maia supplies the candidate moves **at that player's rating** — what they
  would actually have reached for, not what Stockfish prefers.
- The script is written from the computed tree, in the shape a coach talks:
  the tempting move dismissed in a sentence, then the win, with the opponent
  fighting back and getting smarter.

**Why it is safe:** in king-and-pawn endgames with few pieces the position is
solved **exhaustively** — the answer is a proof, not an evaluation. Above that
size, one move must clear a winning bar *and* the runner-up must fall well
below it.

**Status: BUILT, AND NOTHING CAN READ IT.**
`backend/services/teaching_script_builder.py`,
`backend/scripts/build_teaching_scripts.py`, skill
`.claude/skills/build-teaching-scripts/`. The §0 triage gate is now in place.

The decisive fact, checked 2026-11-27: the string `teaching_scripts` appears
in **exactly one file in the repository -- the script that writes it.** No
endpoint serves it, no frontend file mentions it, and the collection does not
exist in prod. This is not a deployment gap waiting on a load command. There
is no reader to load it for. **The missing piece is a surface, not content.**

**Throughput is unmeasured.** Two attempts on 2026-11-27 both died -- one
when a second Stockfish and a second Maia model were run beside it, one when
the owning session exited. The same first 50 games took 215s in one run and
1514s in the other, 7x apart, so no rate from either is trustworthy.

**What the content looks like so far (n=1, do not characterise from it):**
one lesson, on a position where 61.8% of the player's own rating band already
finds the move, which the player **played correctly himself**, proved by
engine search rather than exhaustively. It does not survive any cut-off
tighter than 75%. This is the shape §7 question 3 is about.

---

## 3. Concepts: find out what they already understand

**Mohit:** *"It will try to figure what concepts user already understands, if
it's confused, it will ask user to confirm, asking a puzzle of similar types
and if user answers correctly good, otherwise it teaches those concepts."*

- Work out what the student already has.
- When unsure, **ask** — show a position of the same type.
- Correct → move on. Wrong → *that* is the moment to teach.
- A correct answer earns a **second question on a related position where the
  answer is different.** One right answer is recognition or luck; two with
  opposite outcomes is understanding.

**Asking is not only good teaching — it is the triage mechanism of §0.** It is
the only way to tell a knowledge gap from an execution failure.

**Everything must be sequenced.** Nothing is taught before its prerequisites.
An opening on Monday and an advanced endgame on Tuesday is shuffling, not
teaching. The student should feel **guided**, not handed a buffet.

**Status: scoped, not built.**
See [guided_concept_curriculum_scope.md](guided_concept_curriculum_scope.md).

What exists: 36 named concepts, a mastery machine with 4,224 rows across 76
users, 11,812 question-and-explanation positions, a 388-position diagnostic
pool with frozen grading.

What does not: **any ordering at all** (no prerequisite or difficulty field
exists), and the teaching text is broken — 1,297 concept ids carry more than
one conflicting version of `concept_text`.

**Blocked on Mohit:** the order of the 15 computable concepts (5 endgame, 10
tactical). It is a coaching judgement and should not be invented.

---

## 4. Behaviour detectors

**Mohit:** *"Behavioral detectors are always required, and tracked and these
reports need to be saved for chess academy users, not direct users."*

- Run for **every** player, always.
- **Reports are saved and surfaced for academy users only.**

### What to detect, per §0

The point of these is not a dashboard. It is to answer *"why did I play
that?"* when the student already knew better:

- **Time pressure at the moment of the move** — clock remaining, think time
- **Where on the board** — left, right, centre; and whether the error was far
  from where the action had been
- Unravelling after an error, and thinking collapsing late

### What we measured, and what we killed

Measured on 8 players with 300+ analysed games each, from timestamps,
results, rating gaps and the clock only — nothing that moves when a detector
version changes.

**Real:**

| Reading | Result |
|---|---|
| Lost over the 3 moves after a big error | **85.1 cp** |
| Lost over the 3 moves after a good move | 53.2 cp |
| Ratio | **1.60×** |
| Big errors followed by three rushed moves | 33% |
| Moves 31+: big errors / median think | **8.3% / 2.9s** (vs 10.0% / 5.7s at moves 16–30) |

**Dead — do not sell these:**

- **Tilt is not in our data.** After a loss 62.7 vs 62.4 after a win. After
  *three straight losses* they scored **63.2**, above their own average, and
  73% played on.
- **Endurance barely moves**: game 1 of a sitting 63.3, game 6+ 62.0.
- **`rushed_critical`, which we already ship, does not work** — 59.5 accuracy
  when it fires against 59.3 when it does not. Fix or retire before anything
  quotes it.

### Measured 2026-11-26, and two ideas died

**Board geometry is dead.** The hypothesis was that errors cluster where the
player stopped looking. Split by phase, the effect vanishes exactly where it
was supposed to matter:

| | queenside a-c | centre d-e | kingside f-h |
|---|---|---|---|
| opening | 5.70% | 5.58% | 7.17% |
| middlegame | 11.26% | 11.15% | 11.83% |
| endgame | 10.80% | 10.78% | 10.76% |

Distance from the opponent's last move is not monotonic either (near 13.88%
against across-the-board 14.44%). The one clean gap — adjacent moves at
10.45% — is recaptures and forced replies being mechanically safe. Only the
opening shows a region effect, and that is opening theory, not attention.
**Do not build "all on the queenside while the game was on the kingside".**

**"Rushed" is dead, and it was backwards.** Over 44,580 big errors carrying a
`missed_pattern`, split into blindness (`piece_safety`, `king_safety`,
`missed_tactic`, `tactical_oversight`) against knowledge
(`opening_knowledge`, `endgame_technique`):

| think time | blindness | knowledge gap |
|---|---|---|
| 0–1s | 78.3% | **21.7%** |
| 1–3s | 83.1% | 16.9% |
| 3–10s | 87.6% | 12.4% |
| 10–30s | 91.3% | 8.7% |
| 30s+ | 93.2% | **6.8%** |

A fast error is **three times more likely** to be a genuine knowledge gap.
Moving instantly means not noticing there was anything to think about, which
is not knowing. The triage briefly suppressed lessons on quick moves, which
would have withheld teaching from the players who needed it most. Removed.

**Clock remaining survives** and is the one time signal that holds: 13.37%
big errors with under 15 seconds left, against 7.94% at 3–10 minutes.

**Already in the data and unused:** `move_observations.time_flag` already
classifies `snap_decision`, `time_pressure_blunder` and `slow_paralysis`.
`slow_paralysis` fires on 6.3% of errors where the player thought 30s or
more — a real detector nobody has surfaced.

**A near miss worth recording:** `missed_free_piece` reads 0 across all
63,965 big errors because it is never populated. A dead field returns a
clean zero that looks exactly like a finding.

**Status: researched, not built.** No detector runs in production. No report
exists.

---

## 5. Standing rules

- **The chess is computed. The model writes English and chooses nothing.** If
  a sentence cannot be traced to a field of the computed tree, it does not
  ship. This is why this content type is safe where our captions were not —
  87 model-written captions read by hand came out 32 true, 22 weak, 33 wrong.
- **Start where truth is provable.** Endgames and forced tactics. The 20
  positional concepts wait until the format has earned trust.
- **Nothing reaches a student unreviewed.** Generated scripts land as
  `status: "draft"`.
- **Accuracy is the bar, not coverage.** Do not widen a gate to raise yield.
- **Lichess attribution stays where it is a fact about the player's own
  account**: that the game is rated on their real Lichess rating, that they
  need a Lichess account, and that the coach goes quiet because Lichess
  forbids outside help. Elsewhere it can go. Chessiro — the product we are
  benchmarking — names Lichess twice on its own search screen.
- **No "brain development" claim.** The research is mixed; a 2025 Spanish
  study found no gains in working memory or planning. We claim only what we
  measure: how the child decides under time pressure in their own games.

---

## 6. The triage gate — BUILT 2026-11-27

Before any lesson is generated from a mistake, decide which kind it was.

**Evidence that the player already knew it** (we store all four):

1. **Clock** — how much time they had at that move. Almost none is strong
   evidence of execution failure, not ignorance.
2. **Maia band** — does their own rating band find this move easily?
3. **Their own history** — did they get materially similar positions right in
   other games?
4. **Teaching history** — have we taught them this concept before, and did
   they pass the check?

**If the evidence says they knew it:** generate **no lesson**. Produce a
behaviour finding instead.

**If it says they did not:** the §2 lesson is legitimate, and §3's question
confirms it before teaching.

This is a filter on the existing generator, not a rebuild. It landed before
any script reached prod, which was the point.

**Of the four kinds of evidence, two are wired:** the clock (1) and the Maia
band (2). The player's own history (3) and our teaching history (4) are not
consulted. So the gate catches time pressure and already-known-at-this-level,
and cannot yet catch "he got this right in three other games".

### And the signal kind 3 would read has stalled (verified 2026-11-27)

The data exists at scale -- `user_concept_understanding` 5,424 rows over 76
users, `move_observations` 765,721, `puzzle_attempts` 811. Clean games are
still being credited. **What stopped is the step from a clean streak to
`mastered_at`: not one concept, for any user, has been mastered since
2026-09-17.**

Positive control, so this is a break and not missing input: games analysed per
month went 3,178 (Sep) -> 3,261 (Oct) -> 3,894 (Nov), while clean-game credit
went 443 -> 11 -> 27. Daily, the drop is 2026-09-19/20: 15/50/61/38 rows a day
through the 19th, then a flat 1-3 a day ever since, including today.

**Cause not established.** Also not established: whether the pre-20-September
rate was organic at all -- the day shape (four busy days, then five silent
ones) looks like a batch. The relevant history is that the 2026-06-04 backfill
wrongly stamped 749 of 763 `mastered_at` values, `cleanup_artifact_mastery.py`
correctly stripped them on 2026-06-06 on the promise that "live game events
from this point forward will re-master legitimate concepts organically", and
832 rows did re-master between June and September before it stopped.

**What this costs, on Mohit's own account:** 1,039 games, 1,032 analysed, 120
concept rows. 42 of them carry a clean streak of 20 to 329 games and are still
not flagged mastered -- six endgame principles sit at 329 clean games each.
Every one is a concept he demonstrably has, which the system has never
concluded he has. That is the Magnus case precisely, and it is live.

A restore path already exists:
`backend/scripts/restore_concept_mastery_snapshot.py`, against the snapshot
`cleanup_artifact_mastery.py` always writes before applying. Restoring would
re-grant the wrong stamps though -- the fix is the granting step, not the
snapshot.

**The band cut-off is now one number.** It was two that disagreed: `triage()`
hardcoded 75% while `build_tree` gated on `max_band_solve` (0.90), so
anything 75-90% passed the first and was thrown out by the second -- the flag
was dead across the range that mattered and the effective cut-off was always
75%. `MAX_BAND_SOLVE` is now 0.75, the runner's flag defaults to it, and the
bar is passed into `triage()`. **Effective behaviour is unchanged**; this
wrote down what was already being enforced rather than re-choosing it. A test
asserts the flag is not dead across 75-90%. Still not locked against a
measured distribution -- see section 7 question 4.

---

## 7. Open decisions — Mohit's, not mine

1. **The order of the 15 concepts.** Fifteen index cards, one sitting. Blocks
   §3 entirely.
2. **Signoff on [guided_concept_curriculum_scope.md](guided_concept_curriculum_scope.md).**
3. **Does §2 fire only when the player did not know it?** Or are only-move
   positions intrinsically worth teaching regardless? These build differently.
4. **The band-solve cut-off** is now a single number, 75% (it was two that
   disagreed; see section 6). Still not locked against a measured
   distribution. `/lock-via-data` before anyone reads meaning into it. The
   build writes `human_pct` on every row so the distribution can be read off
   real output; `teaching_out/distribution.py` prints it, including the
   population rejected above the bar, which lands in the behaviour rows.
5. **The Lichess de-branding pass** — approved in principle, not done.
6. **The player-count line** ("Searching among N users"). Available only by
   presenting as Lichess's own web client; not done, and not recommended.

---

## 8. Honest status of everything above

| Item | Status |
|---|---|
| §0 triage (knowledge vs execution) | **Built 2026-11-27.** Wired, and has fired zero times |
| §1 two doors | Not built |
| §2 only-move content | **Built. No reader exists anywhere in the repo.** 1 lesson, not in prod |
| §3 concept check and sequencing | Scoped. Blocked on the ordering |
| §4 behaviour detectors | Researched. Not built. Geometry measured and dead |
| §4 academy reports | Not built |
| §5 standing rules | In force |
| §6 triage gate | **Built.** 2 of its 4 evidence kinds wired |

**Two of seven built. Still nothing visible to a user** -- and for section 2
that is now known to be a missing *surface*, not a missing deploy: the only
mention of `teaching_scripts` in the entire repository is the script that
writes it.

**The one thing blocking value is not engineering.** Section 7 question 3 --
whether a lesson may be built on a position the player already played
correctly -- is unanswered, and the single lesson built so far is exactly that
case. A longer build run mostly produces more of it.

---

## Related

- [why_chessguru.md](why_chessguru.md) — the case for someone outside.
  **Out of date: it predates §0 and does not carry the triage.**
- [human_coach_gap_map.md](human_coach_gap_map.md) — what a human coach does
  that no AI coach does, measured against competitors' own pages.
- [guided_concept_curriculum_scope.md](guided_concept_curriculum_scope.md) —
  §3's scope and open questions.

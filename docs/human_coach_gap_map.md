# What a human coach does that no AI chess coach does

Research, 2026-11-26. Written as input to a build strategy, not as a plan.

Every claim below is marked. **Verified** means I read it today, from the
source named. **Inference** means I reasoned to it and it could be wrong.
**Not verified** means I could not check it from here and who could.

---

## 0. What I actually checked

**Verified — competitors, read from their own pages today (2026-11-26):**

- `chessiro.com/faq` and `chessiro.com/blog/inside-chessiro-game-review`
  (that blog page states "Last updated August 5, 2026").
- `aimchess.com/` homepage. Their `/explore`, `/about` and `/try` returned
  HTTP 200 but only the 8 characters "Aimchess" — JS shells, no readable
  content. So the homepage is the only Aimchess source here.

**Verified — read today via web search result text, not the vendor's own page
(weaker, treat as second-hand):** Chess.com star-voice coaches and Play Coach;
ChessKid Report Cards; Noctie; DecodeChess.

**Not verified:** Lichess Insights. `lichess.org/page/insights` and
`lichess.org/faq` both returned HTTP 403 to automated fetching. Lichess is the
one free product that already holds deep per-move clock data, so its feature
list matters to this analysis and is a hole in it. Settling it takes one person
opening that page in a browser and listing the dimension and metric labels.

**Verified — our own prod corpus (`chess_coach`, read-only, today):** counts
and field coverage as cited inline.

---

## 1. The decomposition

Thirteen things a human coach does. For each: what the human does, what the
best AI tool does today, and whether we could do it.

### 1. Selects, and throws the rest away

A coach reads 40 moves and teaches one. The other 39 are deliberately not
mentioned.

- **Today:** every tool classifies every move. Chessiro's own blog states the
  coach shows a training prompt when "a move points at a recurring weakness"
  (verified) — so there is selection, but the full classified move list is
  still the main surface.
- **Gap:** small. This is the one thing the field does reasonably.
- **Us:** already built. Coach's Pick + the decay model.

### 2. Asks before telling

"What were you thinking here?" — and the next thing the coach says depends on
the answer.

- **Today:** Chessiro's own FAQ and blog describe the player asking the coach
  ("Ask it anything about the position", "Suggested follow-up questions" like
  *why was this a blunder*). **Both pages are silent on the coach ever asking
  the player anything** (verified). Aimchess's homepage describes no
  conversational feature at all (verified). Chess.com's Play Coach offers
  real-time hints (second-hand, not verified at this level of detail).
- **Gap: large, and this is the clearest verified gap in the whole field.**
  Every product is a one-way explainer. The direction of the question is the
  difference between a tutor and a reference book.
- **Us:** partly built — the review tap reflection (board taps + cause reply,
  commit 67329306). Unverified whether it is live for anyone but admins.

### 3. Diagnoses the belief, not the move

The coach does not conclude "you played Nf3". They conclude "you think a knight
on the rim is safe because nothing is attacking it yet" — a wrong rule in the
student's head, which will produce a different wrong move next week.

- **Today:** every tool explains the position. None of the pages I read claim
  to model what the student believes.
- **Gap: large.** This is the actual content of coaching.
- **Us:** this is exactly what the why-engine is for. Honest status: 87
  model-written captions hand-read at 32 true / 22 weak / 33 wrong
  (from memory note `project_model_captions_38pct_wrong`, not re-verified
  tonight). So the ambition is right and the execution is not there.

### 4. Withholds the answer

A coach lets you sit in the position. The silence is the teaching.

- **Today:** every tool reveals instantly. That is the product.
- **Gap: large, and nearly free to build.** It is a UI decision, not a model
  capability.
- **Us:** not built.

### 5. Remembers the last lesson, and checks it in the next games

"Two weeks ago we said check what his last move changed. You didn't, here,
here and here."

- **Today:** Chessiro's FAQ states a skill profile "across" games,
  recency-weighted, and says it tracks "which concepts keep recurring across
  your games" (verified). That is a statistic that moves. **Their pages are
  silent on the coach remembering previous conversations** (verified).
  Aimchess is silent on any "you fixed this" view (verified).
- **Gap: large.** Nobody closes the loop between *what was said* and *what
  happened next*. A moving statistic is not the same as being held to a
  specific instruction.
- **Us:** the substrate exists — 170,680 rows in `user_pattern_events`
  (verified). `coach_memory` holds 2 documents, i.e. effectively unused
  (verified in CLAUDE.md and consistent with prod counts).

### 6. Sequences, and says "not yet"

A coach decides this term is endgames, and deliberately does not teach the
thing the student is curious about, because they are not ready.

- **Today:** Aimchess states a "Weekly personalized study plan" (verified).
  Chessiro's blog says lessons are "coming soon" (verified).
- **Gap: medium.** Plans exist. Readiness judgement and deliberate refusal to
  teach something do not appear anywhere I read.
- **Us:** not built.

### 7. Reads the room and adjusts live

Frustration, boredom, a student nodding along without understanding.

- **Today:** nobody.
- **Gap: total — and we cannot close it.** We have no affect signal. We have a
  clock. Claiming to read a child's emotional state from move times would be
  the kind of claim that destroys trust the first time a parent tests it.
- **Us:** should not attempt.

### 8. Installs habits, not facts

"Before every move, say out loud what his last move changed." A coach trains a
procedure and then checks the procedure, not the answer.

- **Today:** Aimchess's Time Trainer drill is the nearest thing — "know when
  to calculate and when to simply play a good enough move" (verified). It is a
  drill, not a tracked habit.
- **Gap: large.**
- **Us:** `thinking_scores` exists (31 docs per CLAUDE.md, not re-verified).
  Missions exist. Neither is wired to a habit the coach asked for.

### 9. Watches behaviour, not just chess

Rushing, tilting, playing twelve games at midnight, avoiding strong opponents.

- **Today:** Aimchess scores **Time management** as one of six areas and gives
  an example insight, "you're behind on the clock for 78% of your moves"
  (verified, their homepage). Chessiro's blog describes, **per game**, a time
  graph coloured by move quality, "average time spent on accurate moves versus
  inaccurate ones", "Your longest think", and accuracy-and-time by game phase
  (verified). Chessiro's own words: "Long think, bad move, repeatedly, is a
  different problem from moving too fast."
  **Both are silent on tilt after a loss, on playing many games in a row, and
  on time of day** (verified).
- **Gap:** real but **much narrower than it looks**, and the obvious version
  of it does not work. See section 3 — I measured it.
- **Us:** the inputs are all there (section 3).

### 10. Tells the parent the truth

"He has plateaued, and it is because he will not study endgames."

- **Today:** ChessKid Report Cards show games played, puzzles completed,
  lesson progress (second-hand, from their own article text via search).
  That is **activity**, not judgement. No product I read offers a parent an
  assessment with a cause in it.
- **Gap: large, and commercially the most valuable one.**
- **Us:** blocked on reliability, not on data. A wrong cause sent to a parent
  is worse than no report.

### 11. Prepares for the actual next opponent

- **Today:** nothing for amateurs that I found.
- **Gap: medium.** Mostly irrelevant online, relevant for academy kids playing
  rated tournaments.
- **Us:** we hold 25,620 games with opponent names and ratings (verified).

### 12. Holds the student accountable

Homework was set. Was it done. Did it change anything.

- **Today:** streaks and daily sessions. Nobody I read checks whether the
  prescribed work changed the subsequent games.
- **Gap: large.** This is #5 from the other end.
- **Us:** not built.

### 13. Decides when to change the repertoire

- **Today:** opening trainers everywhere, including Chessiro's 2.9M-game
  opening database (second-hand) and Aimchess's Opening Improver (verified).
- **Gap: small.**
- **Us:** weakened by a known data hole — 0 of 2,013 Lichess imports carried
  an opening (memory note `project_lichess_import_never_asked_for_opening`,
  not re-verified tonight).

---

## 2. The three gaps that are clear across every page I read

Stated as the verified claim, not stronger:

1. **No product asks the student a question and branches on the answer.**
   Chessiro's and Aimchess's own pages are silent on it; Chessiro's pages
   describe the opposite direction explicitly.
2. **No product connects an instruction to the games that follow it.** Skill
   profiles move; nothing says "we told you this, and here is what you did
   next."
3. **No product gives a third party — parent, coach, academy — an assessment
   with a cause in it.** Aimchess has a coach *pitch* (see below) and ChessKid
   has activity reports.

One important correction to something I said earlier in this session:
**Aimchess already pitches to coaches.** Their homepage has a section headed
"A chess coach's dream — reduce preparation time and improve your session
productivity", with a testimonial from GM Ankit Rajpara: "The option to
generate a list of mistakes and blown positions from a student's recent games
allows me to more spend more time on instructive moments and less time
reviewing games manually" (verified, their homepage).

But: the call to action is "Contact us to get started" pointing at a mailto
address, and their pages are **silent on multi-student views, rosters, schools
and academies** (verified). The only sharing described is a Premium feature,
"Share data & lessons with your coach" — student-initiated, one student at a
time. **Inference:** the coach-facing product is a sales conversation, not a
shipped surface. That is a real opening, but it is an opening next to a
competitor who has already thought of it, not virgin ground.

Also worth knowing, because we have no equivalent: Aimchess's homepage claims
"personalized puzzles increase your rating 31% faster than standard tactics
puzzles", footnoted to "a 12 week randomized field experiment conducted by
researchers at the University of British Columbia" (verified as a claim on
their page; I have not seen the study). We have no outcome evidence of any
kind. In a sale to an academy, they can show a number and we cannot.

---

## 3. What I measured in our own corpus — and the surprise

All of the below is **verified today**, read-only, from `chess_coach`. Crucially
it uses only *when a game was played, its result, the rating gap, the stored
per-game accuracy, and the clock*. No detector, no caption, no
`cognitive_gap` — so none of it moves when a detector version bumps.

**The corpus:** 25,620 games, 23,572 analysed. `played_at_utc` on 25,622 rows,
25,346 of them sourced from `pgn_utc_headers`. `opponent_rating` on 98.9%,
`rating_gap` present. Per-game `stockfish_analysis.accuracy` on 23,572 games.
27 users with 200+ games; the largest has 2,359 analysed. Per-move
`time_spent_seconds` present in 37 of 40 sampled analyses.

### Between-game behaviour is nearly flat

Eight users, 300+ analysed games each. A session = games under 30 minutes
apart.

| Reading | Result |
|---|---|
| Accuracy after a loss vs after a win | 62.7 vs 62.4 (n=3,962 / 4,031) |
| Restarting under 3 min after a loss vs waiting over 6 min | 61.1 vs 63.3 |
| Game 1 of a sitting vs game 6+ | 63.3 vs 62.0 |
| Accuracy of the game played right after **three straight losses** | **63.2** — above their own average |
| Outrated by 25-99 vs favoured by 100+ | 61.0 vs 65.4 |

Per user, the immediate-restart penalty ran from **-2.6 to +0.3** accuracy
points, and two of the eight did not have enough paired games to measure.

**So: "your child tilts" is not supported by our data.** 73% of the time, after
three losses in a row, they played on anyway — and that next game was slightly
*better* than their average. The whole folk model of tilt, which the coaching
blogs repeat, does not show up in 8 users and ~13,000 games.

The rating-gap effect (4.4 points) is the largest between-game number, and it
is **confounded**: facing a stronger opponent means facing better moves, which
mechanically lowers your accuracy. It is not evidence of fear.

The time-of-day spread was 60.8 to 64.1 across UTC hours, but UTC pools players
across time zones so the pooled number is close to meaningless. We do not store
a user's local time zone — that is a real gap if this matters.

### Within-game behaviour is large

Same 8 users, 954 games, ~36,000 of their own moves.

| Reading | Result |
|---|---|
| Mean cp lost over the 3 moves after a **big error** | **85.1** (n=7,008) |
| Mean cp lost over the 3 moves after a **good move** | **53.2** (n=75,880) |
| Ratio | **1.60×** |
| Big errors followed by three rushed moves (median ≤3s) | **33%** (820 of 2,454) |

And by move number:

| Phase | Mean cp lost | Big errors | Median think |
|---|---|---|---|
| moves 1-15 | 39.3 | 3.7% | 3.0s |
| moves 16-30 | 71.4 | 10.0% | 5.7s |
| moves 31+ | 59.1 | **8.3%** | **2.9s** |

**That last row is the single most coachable fact in this document.** After move
30 they are still making big errors at more than twice the opening rate, and
they are thinking for half as long as they did in the middlegame. A human coach
says that in one sentence and it changes how the student plays.

### The behaviour flag we already ship does not work

`move_time_stats.rushed_critical` exists on 13,199 games and fires on 1,514
(11.5%).

| | rushed the critical move | took time on it |
|---|---|---|
| Mean accuracy | 59.5 | 59.3 |
| Win rate (decisive games) | 46.1% | 50.1% |

**No accuracy difference at all.** A 4-point win-rate gap is the only signal,
and the comparison group was an unmatched 4,000-game sample, so even that is
soft. A detector named "rushed_critical" that does not predict a worse game is
a liability the moment someone reads it on a parent report.

Separately: stored `stockfish_analysis.avg_cp_loss` came back at 396-416 for
those groups, while per-move mean `cp_loss` for the same population is 53-85.
Those cannot both be a mean in the same units. **Not diagnosed** — flagging it
because any surface quoting `avg_cp_loss` may be quoting something other than
what its name says.

### The conclusion that changes the build

**Behaviour signal lives inside the game, not between games.** The things a
parent intuitively asks about — tilt, late nights, too many games — are flat or
confounded in our corpus. The things that are large are move-level: unravelling
after a mistake (1.60×), and the collapse of thinking time in the phase where
errors are still frequent.

That is good news. It is cheaper, it is already stored, and it does not need a
single new detector.

---

## 4. On "brain development" as a claim

Searched the research today. The evidence that chess training improves
executive function in children is **mixed and mostly weak**:

- A 2025 cross-sectional study of 88 children aged 5-6 found higher
  visuospatial working memory in chess players — but comparing existing groups
  cannot show chess caused it.
- An Indian intervention study (88 vs 90 children) reported significant working
  memory gains; sources describe it as both one-year and two-year, so the design
  is unclear from the summaries.
- A Spanish quasi-experimental study (ages 8-12) found **no improvement** in
  flexibility, initiative, planning and organisation, or working memory.
- A 2025 preprint states the literature is mixed with small to moderate effects.

I read summaries, not full texts. **Inference, stated as such:** we should not
build the pitch on "chess develops your child's brain". It is contestable, and
the first informed parent who checks will find the Spanish result.

What we *can* say honestly is narrower and, I think, more saleable: we measure
how the child makes decisions under time pressure in their own games, and we
report what changed. That is a measurement claim about chess behaviour, not a
neuroscience claim about brains.

---

## 5. What this implies

Not a plan — the input to one.

1. The buildable, defensible layers are **#2 (ask before telling)**,
   **#5/#12 (connect an instruction to the games that followed it)** and
   **#4 (withhold the answer)**. All three are verified silent across the pages
   I read, all three are interaction design rather than model capability, and
   none of them needs the caption engine to get better first.
2. The behaviour layer should be **within-game**, starting with the two
   measured effects above. The between-game version should be dropped, and
   `rushed_critical` should be fixed or retired before anything reads it.
3. **#10 (the honest parent report)** is the commercial prize and is blocked on
   caption reliability, not on data or ideas. Nothing that reaches a parent
   should go out at 38% wrong.
4. We have no outcome evidence and a competitor cites an RCT. Whatever gets
   built, the measurement of whether it worked is part of it, not a later phase.

---

## 6. What I could not verify

- **Lichess Insights' feature list.** 403 to automated fetch. This matters:
  Lichess holds per-move clock data on millions of games and gives analysis
  away free. Anyone can settle it by opening `lichess.org/page/insights`.
- **Chess.com's current Game Review and Play Coach feature set** at the level
  of detail above. Everything I have is third-party review text. Their own help
  pages would settle it.
- Whether the Aimchess coach offering is a product or a sales conversation.
  Marked as inference above. A single email to `support@aimchess.com` as a
  prospective academy would settle it.
- Whether our review-tap reflection (#2) is live for anyone beyond admins.
  Checkable in this repo; I did not check it tonight.
- The memory-sourced claims I reused without re-checking: the 38% caption
  figure, `thinking_scores` at 31 docs, and the Lichess opening-import hole.

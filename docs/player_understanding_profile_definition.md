# Player understanding profile — definition and evidence requirements

Status: DEFINITION for sign-off, before any feature is chosen. Read-only
investigation; no code, data or flag changed. Measured 2026-10-15 against
live production (`chess_coach`: 20,297 games, 128 users, 631,818 move
observations) through the SSH tunnel on port 27018.

Companion to [player_understanding_measurement_map.md](player_understanding_measurement_map.md)
(what the data can support) and [corrections_p1_p3_plan.md](corrections_p1_p3_plan.md)
(the three corrections in flight).

---

## 1. The claim we want to be able to make

> "They recognise this idea with a prompt, struggle to calculate the reply
> independently, and retain it after this kind of practice."

That one sentence needs four separate observations about **the same player and
the same idea**:

| Slot | What it asserts | Store today | Field | Values |
|---|---|---|---|---|
| prompted | shown it, responded | `user_concept_understanding` | `concept_id` | 218 |
| independent, succeeded | did it unaided in a game | `move_observations` | `concept_used` | 14 |
| independent, failed | tried unaided and missed | `move_observations` | `missed_pattern` / `subtype` | 6 / 26 |
| retained | met it later, still right | `user_concept_understanding` | `streak_clean`, `mastered_at` | — |

**The sentence is not currently sayable about any player, for any idea.** Not
because the data is thin. Because of §2.

## 2. The blocker: five concept vocabularies, no shared key

| Role | Source | Ids | Examples |
|---|---|---|---|
| taught / prompted | `user_concept_understanding.concept_id` | **218** | `back_rank_weakness`, `blocked_bishop`, `DEF_TRADE_ATTACKERS`, `golden_endgame_principle_103` |
| independent success | `move_observations.concept_used` | **14** | `center_control`, `bishop_development`, `best_under_pressure`, `check_given` |
| independent failure | `move_observations.missed_pattern` | **6** | `piece_safety`, `missed_tactic`, `king_safety`, `endgame_technique` |
| independent failure, finer | `move_observations.subtype` | **26** | `destination_safety_exact`, `early_flank_pawn_move` |
| detector pattern names | `backend/data/pattern_catalog.json` | **35** | `missed_mate`, `queen_fork`, `knight_outpost`, `un_developing` |

Measured intersection of the prompted side (218) and the independent-success
side (14): **zero**. The catalog contains none of the other four sets' ids
either — I checked all 14 independent ids and all 6 missed_pattern ids against
its 35.

So: **cells with both prompted and independent evidence: 0. With retention
too: 0.** There are 3,242 cells with prompted evidence and 743 with
independent evidence, and they cannot meet.

The one bridge that exists (`pattern_catalog._doc.coach_memory_bridge`) maps a
*sixth* vocabulary — `coach_memory.learning.skills` — onto the curriculum ids,
and documents its own trap: lesson records are *attendance*, not evidence the
player holds the concept. Correct principle, wrong pair for this job.

One structural consequence worth stating plainly: **`concept_used` is written
only on good moves** (`move_observation_deriver` sets it only when
`evaluation in best/excellent/good/brilliant`, from the v5 `concept_applied`
field). So the independent side can say "they did it right" and can never say
"they tried and failed". "Struggles independently" has to come from
`missed_pattern` / `subtype`, which is a different vocabulary again. This is
the same shape as the known finding that concept detectors only congratulate
(1,639 "applied" against 5 "wrong").

**This is the decision in front of us, and it is subtractive, not additive.**
Before any new instrument, the product needs one concept identity that all
evidence sources write. Memory already carries the rule; this is the largest
live violation of it.

## 3. The six questions, measured

### Q1 — What are they trying to achieve?

*Partly exists, barely used.* `users.player_motivation` is populated on **12 of
128** (values: `compete`, `fun`, `improve`, `learn`), `skill_level` on 52,
`focus` on 68. Nothing records **practice time** or **preferred games** — the
two things that would change what we prescribe. `users.coaching_profile` is on
128 of 128, but its contents are defaults, not measurements
(`total_training_hours: 0`, `engagement_score: 50`).

Supports: a coarse motivation tag for 9% of users. Needs: time available and
game-type preference, asked once. Cannot infer: intention from behaviour —
playing 60 blitz games does not reveal whether they want to compete or relax.

### Q2 — What chess knowledge do they have?

*The instrument exists and almost nobody finishes it.* `diagnostic_service` is
a 20-puzzle stratified probe, no clock, no gamification, explicitly designed to
cover breadth rather than mistakes — exactly this question. Production:
**45 sessions, 31 users, 2 marked complete, and exactly one session reached all
20 attempts.** 19 of 45 sessions have **zero** attempts recorded.

Worse for our purposes, it is scoped to onboarding and then discarded by
design: its own docstring says "after 10+ real-game analyses land, real-game
data supersedes this." So the only breadth probe we have is thrown away
precisely when a player becomes worth profiling.

Supports: nothing today. Needs: completion, and a decision to *retain* the
breadth result instead of superseding it. Cannot infer: knowledge of ideas
their games never present — which is the whole point of asking.

### Q3 — How do they approach a position?

*Built, wired, unused.* `calculation_test` grades a **line**, not a move, on
three axes kept deliberately apart: `found_the_idea`, `sound_through`,
`judged_the_end`, plus `stopped_early` and `required_depth`. Route →
`CalculationTest.jsx` → `App.js`, all live. Production:
**4 attempts, 1 user, one day (2026-10-02).**

This is your "choose a move, predict the reply, show a continuation before
revealing feedback", already implemented. The gap is entirely that nobody has
been asked.

Supports: nothing at n=4. Needs: asking. Cannot infer: depth of calculation
from game moves — the record shows where the punishment landed, not how far
they looked.

### Q4 — Why does performance break down?

*The strongest real-behaviour evidence we have.* Clock is on **79.4%** of
631,818 observations (`time_spent_seconds`) and **82.0%** (`time_left_seconds`),
from `%clk` in 86% of PGNs. Engine-independent, genuinely behavioural.

But `time_flag` fires on **0.4%** of moves — the threshold was never calibrated
against the distribution, so the signal is there and the switch is off.
Comparison *without* time pressure needs a no-clock condition, which is what
Q2's and Q3's instruments are.

Supports: same-player comparison of accuracy against time remaining, today.
Needs: a calibrated flag, and paired positions across conditions. Cannot infer:
*what they noticed* — and your instruction to ask rather than infer is the
right call; nothing in the schema currently stores a "what did you see" answer
(`user_misconceptions` and `home_today_answers` both hold 0 rows).

### Q5 — What can they do independently?

*The distinction is already in the schema.* `learning_sessions.highest_earned_state`
has exactly four values — **`can_do_alone`, `can_do_with_help`, `learning`,
`remembered`** — and `events` record `help_requested` with timestamps and
`item_id`. That is assisted-versus-independent, recorded separately, as you
asked.

Volume is the problem. Of 323 sessions across 38 users:

| State | Sessions | Users who ever reached it |
|---|---|---|
| `can_do_with_help` | 223 | — |
| `learning` | 55 | — |
| no state recorded | 43 | — |
| **`can_do_alone`** | **3** | **2** |
| `remembered` | 1 | — |

So the independent-ability signal that the target sentence turns on exists for
**two players**. Also: the `lesson_result.v2` events carry an `application`
slot whose outcome reads `not_measured`, i.e. the transfer-to-real-games field
exists and is empty.

### Q6 — What teaching works for them?

*Substrate exists, comparison does not — and the framing needs changing.*
`display_stage` has seven values that map well onto your four modalities:
`explain`, `activity`, `contrast`, `notice`, `flash`, `diagnose`, `retain`.
Distribution across 323 sessions: `contrast` 154, `retain` 111, `diagnose` 3,
`explain` 2, `activity` 2, `notice` 2, `flash` 1.

Two or three observations per modality cannot support a comparison for anyone.
And see §4.1 — I think the question should be asked differently.

## 4. Three places I would push back on the framing

### 4.1 Q6 as worded is learning-styles-shaped

"Observe whether an explanation, demonstration, guided attempt, or repeated
practice leads to independent success" slides easily into "this player is a
practice learner" — a per-person learner type. That idea is one of the most
thoroughly tested and unsupported claims in education research, and matching
teaching to a supposed style reliably fails to beat teaching the content well.

The codebase already took the right side of this, deliberately:
`personal_teaching_profile.py` says it "adapts delivery, never chess truth…
stores **no permanent learner type**." I would keep that.

It also already contains the trap:
`users.coaching_profile.preferred_learning_style` is on **128 of 128** users
with the value `"practice"` — a stored default, never measured, that looks
exactly like a finding. If anything reads it as one, that is a bug waiting.

The defensible version of Q6 is **per concept, not per person**: "for *this
idea*, the guided attempt produced independent success where the explanation
did not." That is a statement about the idea's instructional sequence, it
generalises to other players, and it is measurable with the
`display_stage` × `highest_earned_state` pair already in the schema.

### 4.2 Comparing modalities is an experiment, not an observation

Q6 and Q4 both ask us to compare conditions — with and without a hint, with
and without the clock, explanation versus guided attempt. You cannot get that
by watching, because which condition a player meets is currently decided by
the curriculum, not varied. 154 of 323 sessions are a single stage.

So answering those two questions means **deliberately assigning conditions**:
the same idea presented two ways to comparable players, or the same player
given paired positions under different conditions. That is a modest,
legitimate design — but it is a different kind of work from everything in this
product so far, and it should be named as such before it is scoped.

### 4.3 Asking is the scarce resource, and we are already failing at it

Five of your six questions require the player to answer something. The two
instruments built for exactly that purpose have **4 attempts (one user)** and
**one completed 20-puzzle session**. 19 of 45 diagnostic sessions recorded zero
answers.

So the binding constraint is not instrument design — we have good instruments —
it is **asking capacity and completion**. A profile defined as "ask six
questions" will return six empty answers. The definition therefore needs an
**asking budget**: at most one question per session, chosen by what the profile
most lacks, and a completion measurement for every probe. If we cannot get a
20-puzzle diagnostic finished by more than one person, a six-part battery is
not the next thing to build.

## 5. Evidence requirements

The profile should state a claim at the strongest grade its evidence supports,
and say **"not known"** otherwise. "Not known" will be the honest answer for
most cells for a long time, and the profile must read well when it is.

| Grade | Claim shape | Minimum evidence |
|---|---|---|
| **D — not known** | nothing said | default; always available |
| **C — observed once** | "came up once; too early to say" | 1 observation, any source |
| **B — pattern** | "this keeps happening" | ≥3 independent observations of the same idea, across ≥3 games, within a bounded window |
| **A — conditional** | "recognises with a prompt, not yet alone" | B on the independent side **plus** ≥1 prompted observation of **the same idea** (needs §2 fixed) |
| **A+ — retained** | "holds it now" | A **plus** ≥2 later clean independent encounters after the teaching |

Four rules the grades must obey, each one a lesson already paid for:

1. **One shared concept identity.** A claim may only combine evidence that
   names the same idea under the same id. No fuzzy matching.
2. **Opportunity-adjusted, never raw.** A rate is measured against the chances
   the position actually offered, not against move count.
3. **Bounded windows.** Both sides of any before/after comparison are the N
   games either side of the event — the current unbounded split reaches 1,588
   games on one side.
4. **Assistance recorded separately, never netted.** A success with a hint and
   a success alone are different observations and may not be summed.

And one voice rule, since this profile will be read by the player: every claim
in plain English, no numbers, no failure scoreboard.

## 6. What I would do first

Ordered by what unblocks the most, and all of it consolidation rather than new
features:

1. **Pick one concept identity and make every source write it.** Start with the
   ~48 ids that are real rather than the 218 or the 238. This is the only item
   that turns the target sentence from unsayable into sayable, and it deletes
   vocabularies rather than adding one.
2. **Give the independent side a failure branch.** `concept_used` records only
   good moves, so "struggles alone" is unsayable from it today.
3. **Stop discarding the breadth probe**, and measure why 19 of 45 diagnostic
   sessions record no answer at all. Fixing completion is worth more than any
   new instrument.
4. **Ask the calculation test of real users.** It answers Q3 as specified and
   has four attempts.
5. **Calibrate `time_flag` from the distribution** of 501,863 `time_spent_seconds`
   values. Q4's data is present and its switch is off.
6. **Ask Q1's two missing fields once** — time available, preferred games — and
   do not infer them.
7. **Reframe Q6 per concept**, and treat any modality comparison as a designed
   experiment with its own scope.

Nothing here needs a new detector, a new scoring engine, or a homepage change.

## 7. Open questions for you

1. **Concept identity is the gate.** Do you want this profile defined on top of
   one consolidated vocabulary — which means a consolidation project before any
   profile feature — or should I define the profile against today's five
   vocabularies and accept that its strongest grade is B?
2. **Do you accept the per-concept reframing of Q6** (§4.1), and should
   `coaching_profile.preferred_learning_style` be removed given it is an
   unmeasured default on every user?
3. **Asking budget** — is one question per session the right ceiling, and
   which question gets priority when the profile is empty?
4. **This player.** You asked me to investigate the missed-mate, capture-
   consequence and clock hypotheses while also checking what the games have not
   exposed. The first three are answerable from data in hand; the fourth needs
   him to finish a diagnostic and a calculation test. Shall I run the three and
   report, or wait until the profile is defined?

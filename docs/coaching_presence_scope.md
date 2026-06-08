# Coaching Presence — Product Scope

_Status: DRAFT for sign-off. Locked before any colors, sidebars, dark mode, or
animation work. (Mohit, 2026-06-08.)_

_This doc separates **what we build now (v1, feelable on Day 1, needs no behavioral
history)** from **the roadmap (multipliers that only pay off once data exists)**._

---

## North Star

**"A coach that teaches you how to think."**
Not: _"A coach that tells you the best move."_

The moment the coach feeds you moves, it becomes a **tutor**. The moment it helps you
think, it becomes a **coach**. We build the entire premium experience around that line.

The feature that makes someone say _"I can't play without ChessGuru anymore"_ is not
candidate moves, dark mode, or prettier UI. It is the coach feeling **present and
personal**. The endgame is a user who says _"my coach thinks I'm an impatient
attacker"_ instead of _"my accuracy is 72%."_ That is the crossover from analytics
software into something hard to replace.

This is the same law we already enforce in captions — **people remember patterns, not
moves** — promoted to the whole product. See [memory/feedback_users_remember_patterns_not_moves].

---

## What we are NOT building

- **Not** candidate-move multiple-choice as the default play experience. (It turns the
  coach into a tutor and the game into a scripted lesson.)
- **Not** a scripted lesson flow as the default.
- **Free play is preserved and primary.** The user plays their own moves, freely,
  against the live engine. The coach sits beside them — it does not drive.

---

# PART 1 — Premium PWC v1 (Day 1, buildable now)

This is the committed scope. Everything here is feelable **immediately** and needs
**no months of behavioral data**. It is already significantly ahead of what most
chess products offer.

### The six v1 capabilities
1. **Session Goal** — the coach opens with one thing to work on today ("today, let's
   not lose a piece in the first 10 moves").
2. **Pre-move coaching** — the coach occasionally speaks _before_ you move, to shape
   _how_ you think (never to hand you the move). The single biggest shift.
3. **Focus Areas** — the one or two things the coach is working on with you right now.
4. **Accountability** — the coach remembers today's goal and holds you to it.
5. **Post-game Story** — the game told back as **one lesson**, not an analysis report.
6. **Early Profile (low confidence)** — a few honest observations with a confidence
   label ("Aggressive · comfortable attacking · often rushes development — Confidence:
   Low"). The honest seed of the future theory engine; it matures without a rewrite.

### The honest Day-1 → Week-1 warmth gradient (read this before promising "personal")
Half of v1 is feelable on **literal game 1** with zero user data; the other half only
becomes **personal** after a few games. Don't promise day-1 personalization we can't
deliver until ~game 5.

| Feelable on game 1 (no data) | Becomes personal ~game 3–5 (needs early profile) |
|---|---|
| Pre-move coaching (position/goal-triggered) | Session Goal *for this user* (game 1 = band-generic) |
| Accountability (pure session state) | Focus Areas *for this user* |
| Post-game Story (about *this* game) | Early Profile (empty on game 1 → fills over week 1) |

On game 1, "today we work on development" can only be **band-generic** ("for a 600,
let's keep pieces safe") — still good ("the coach has a plan"), but the **"for me"
warmth ramps over week 1** as the early profile fills.

### The spine: three of the six are one arc (build this first)
**Session Goal → Accountability → Post-game Story** is one emotional loop — _set an
intention → live it → reflect on it against that intention_ — and it is **100% pure
session state, no behavioral history.** Highest-feel, lowest-risk, fully Day-1. Build
this arc end-to-end first; it proves the entire premium feeling in a single sitting.

**Concrete copy — the 600 arc (illustrative; terser/rarer as rating rises):**

- **Goal-set (session start):**
  > _"Before we play — one thing today. You've been dropping pieces by moving fast. So
  > one rule this game: before every move, a quick look — can anything of mine be
  > taken? That's the whole goal. Ready?"_
  > _(Game 1, no data: "Today, let's keep your pieces safe — a quick check before each
  > move: is anything of mine hanging? Ready?")_

- **Mid-game (pre-move, rare, goal-tied):**
  > _"Hold on — before you move. Remember today's rule. Look at my last move: what does
  > it attack?"_

- **Accountability (in the moment):**
  > _"That's three moves in a row you checked first — exactly today's goal. Good."_
  > _or_ _"Careful — that's the fast kind of move we said we'd slow down on today."_

- **Post-game Story (end — one lesson, not a list, ends with a forward promise):**
  > _"Good game. Today wasn't really about the result — it was the safety check. You
  > did it well for 15 moves, then on move 18 you moved fast and dropped the knight.
  > That one move is the whole lesson. Tomorrow: same rule, one more game."_

Pre-move coaching layers on top of this arc; the early profile accumulates underneath.

### v1's risk and dependency (stated honestly)
- **Pre-move coaching is the highest-risk item — and it's a *trigger-precision* problem,
  not a data problem.** It's a new computation path (judge "is this position worth a
  word *before* the move?"). Fire on every position and it becomes the every-5th-move
  habit-prompt nag we already ship and both dislike. **Prototype it first to de-risk** —
  if it feels naggy or dumb on move 1, the premium illusion dies immediately.
- **The Post-game Story is only as good as the analysis feeding it.** We are still
  hardening per-move quality (over-flagged fine moves, empty blunder captions in the
  fallback, the `piece_activity` leak — all found 2026-06-08). **v1 is not free of that
  work**; the story sits directly on top of it. Finishing the caption hardening is part
  of shipping v1 honestly.

---

## The two hard constraints (apply to all of v1)

### 1. Never make a personal claim without evidence (TRUTH)
A wrong personal claim is **worse than silence**. The Early Profile's "Confidence: Low"
label exists precisely so we can be honest while the data is thin. We do not fire
"you usually X" off one or two data points. See [memory/feedback_threshold_before_distribution_is_sin].

### 2. Speak rarely (RESTRAINT)
A coach who talks every move is not present — he is annoying. Quiet by default; speaks
when it has something specific and true. The existing every-5th-move habit-prompts are
the named **anti-pattern**. See [memory/feedback_principle_bank_is_filler]. How rare
"rare" is depends on the band — see "How much the coach talks".

---

## Coach Voice

**Simple English. Always.** No Hinglish ("arre", "beta", "haan"), no chess jargon for
the 600–1500 audience (name the square instead), short and human (one or two sentences).
**No new skill** — the discipline already exists: `/check-voice` (audit),
`/rewrite-for-1200` (rewrite), and the banned-jargon hit-list in
`docs/simple_english_captions_scope.md`. All coaching text routes through that gate.
Building a parallel voice skill would duplicate it (see
[memory/feedback_check_for_existing_ui_before_building_offline]).

---

## The coach across skill levels (600 / 1200 / 1600+)

The north star is constant; **what we teach them to think about, and how much
scaffolding, scales with the band** — riding the existing `RATING_BANDS`.

| | **600 (beginner)** | **1200 (intermediate)** | **1600+ (advanced)** |
|---|---|---|---|
| **Thinking we install** | The **safety scan** — notice a threat _exists_ | **Judgment** — is the threat real, or overestimated? | **Meta-patterns** — my own tendencies |
| **How concrete the prompt** | Name the piece + square | Name the tension | Name the _type of moment_ |
| **What "knows you" sounds like** | "You've hung a piece three games running — always attacking." | "You miss the second threat when there are two." | "You rush in sharp positions." |

A 600 is different **in kind**: they often don't perceive the threat at all, so we
teach them to _look_, not to _evaluate_. **The premium bet: the coach's job at 600 is
to make itself unnecessary** — install the routine, then fade. The metric the north
star implies is _"does the user still hang pieces after a month with us?"_

---

## How much the coach talks (cadence scales inversely with skill)

The lower the rating, the more the coach involves itself; the higher, the more it gets
out of the way. **Restraint is a function of the band, not a single number.**

| Band | How often it speaks | About what |
|---|---|---|
| **600** | Most often — instructive | The ONE focus habit (the safety scan). Frequent on one theme — **not** every mistake (a 600 makes too many; commenting on all drowns them). |
| **1000–1200** | Sometimes | The focus area + genuinely instructive moments |
| **1400** | Rarely — mostly just play | Only a real blunder or a real, evidenced pattern |
| **1800+** | Almost silent | Only the rare insight they couldn't see themselves |

A 600 coach is **frequent but narrow**; a 1400+ coach is **rare but broad**. Constant
across both: it never feeds the move, and never speaks to fill space.

---

# PART 2 — Roadmap (multipliers, data-gated)

These make the coach feel _human_, but they only pay off once enough per-user data
exists. They are **deferred, not dropped.** Crucially, **they are not seven independent
features — they are one keystone plus a stack that hangs off it.**

### The keystone: Theory of You
A player **identity**, not a stat list ("you're an attacker whose mistakes come from
forcing play when the position needs patience"). **Everything below derives from it** —
so if the theory is wrong, everything above inherits the error. Validate it before
building on it. The v1 Early Profile is its honest seed; it grows confidence over games.

### Derived from the theory (in roughly this build order)
- **Confidence tracking** — "Areas you can trust / Areas to double-check." Mostly a
  *reframe* of data we already have (`pattern_decay` ACTIVE vs FADING). Lowest-risk
  multiplier; a good first step toward the keystone.
- **Coach Journal** — a diary, 2–3 sentences per game, narrating growth over months
  ("two months ago you'd have rushed the kingside"). The emotional retention layer.
  Great LLM job. Degrades gracefully (session notes now → growth narrative later).
- **Prediction of mistakes** — pre-mistake, not post ("positions like this tempt you to
  attack early"). The "damn, it knew" moment. **Highest reward, highest risk** — only
  magic when right; wrong = the coach looks blind instantly. Favor precision hard.
- **Learning transfer** — collapse many mistakes into one root cause ("this was
  attacking-before-developing again"). What actually creates improvement.
- **Coach Interventions** — rare (~every 10 games), a meta zoom-out ("stop — let's not
  talk about this game, let's talk about your last 20"). Remembered for months *because*
  it's rare and right.
- **Plateau diagnosis** — the final synthesis: what's actually capping your rating.

### Two rules for the whole roadmap
1. **The truth-bar escalates up the stack** — "you're an attacker" wrong breaks trust at
   the identity level; a wrong live prediction looks blind in the moment. Higher
   features need more data and more validation. Data-sufficiency gates the build order.
2. **A confidence-aware, self-revising theory** — the coach knows _how well it knows
   you_, says so, and updates ("I had you as an impatient attacker; your last five games
   are changing my mind"). This turns the cold-start weakness into a feature and is the
   antidote to the wrong-identity risk. Revision itself is a magic moment.
3. **The LLM narrates; the engine decides.** The theory, patterns, and predictions are
   deterministic and evidence-based. The LLM turns them into human sentences — it
   **never invents a theory.** ("Fix framing, not detection," one level up.)

### Adaptive guidance (roadmap — trigger needs data, rails already exist)
When the coach detects recurring per-user trouble tied to an opening ("the Italian keeps
going wrong ~move 6"), it **offers** a guided opening — opt-in, never forced — deep-
linking into PWC via the **existing** `?opening=` / `?focus=` query params + `guidedMode`
toggle, `opening_curriculum_engine`, and `opening_mastery_tracker`. The launch rails are
built; the **detection trigger** is the new (data-gated) work.

---

## What already exists (build on, do not rebuild)

- **`coach_memory`** — persistent per-user weaknesses / strengths / patterns
- **`pattern_decay_service`** — recency-weighted ACTIVE / DECLINING / FADING states
- **`thinking_scores`** — habit scores per game (likely home for a "rushing" signal)
- **cognitive gaps + `behavioral_missions`** — weakness taxonomy + per-user focus
- **`opening_curriculum_engine`** + `opening_library_service` — curriculum + live opening ID
- **`opening_mastery_tracker`** + `get_user_opening_progress` — per-user opening strength
- **`?opening=` / `?focus=` / `guidedMode`** — guided-opening launch rails (CoachPlay.jsx)
- **rating-aware feedback** — classification already varies by band

---

## The data check (informs the ROADMAP, not v1)

v1 needs no behavioral data. Before we build any **roadmap** layer, one investigation:
**do users have detectable, stable, evidenced player identities — and at what data
volume do they become honest?** That answer decides which multipliers we can build
truthfully *now* vs. which must wait. (Per [memory/feedback_threshold_before_distribution_is_sin]
and `/lock-via-data`.) If the signal is thin, the honest first version is retrospective
("across your last 10 games I'm starting to see…") until it's strong enough to go
pre-move and confident.

---

## Open questions / Needs Mohit

- **Visual adoption** — the Claude Design system (warm-dark, single amber accent, left
  icon rail, dark-default) is strong and we want much of it. Deferred on purpose:
  **product direction locks first**, visuals second.

_Resolved 2026-06-08:_ **Voice** = simple English, no Hinglish/jargon, via existing
`/check-voice` + `/rewrite-for-1200` (no new skill). **Cadence** = inverse with rating.
**Scope split** = v1 (Part 1, build now) vs. roadmap multipliers (Part 2, data-gated).

---

## Definition of done for THIS doc

Signed off when Mohit blesses: the north star, the **v1 scope (Part 1)** including the
warmth gradient and the spine arc, the two constraints, voice, the rating-band model,
and the **roadmap split (Part 2)**. No implementation begins before that. **First build
when greenlit: the spine arc (Goal → Accountability → Post-game Story)** — pure Day-1
state, zero engine risk — with **pre-move coaching prototyped next to de-risk it.**

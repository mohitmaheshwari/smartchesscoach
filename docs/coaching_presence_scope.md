# Coaching Presence — Product Scope

_Status: DRAFT for sign-off. Locked before any colors, sidebars, dark mode, or
animation work. (Mohit, 2026-06-08.)_

---

## North Star

**"A coach that teaches you how to think."**
Not: _"A coach that tells you the best move."_

The moment the coach feeds you moves, it becomes a **tutor**. The moment it helps
you think, it becomes a **coach**. We build the entire premium experience around
that distinction.

The single feature that makes someone say _"I can't play without ChessGuru
anymore"_ is not candidate moves, not dark mode, not prettier UI. It is the coach
saying something like:

> _"Pause. This is exactly the type of position where you usually rush."_

That feels personal, useful, and is hard for a competitor to copy. It is the moat.

This is the same law we already enforce in captions — **people remember patterns,
not moves** ("I got my piece chased," not "I played Nxe5") — promoted from the
caption layer to the whole product. See
[memory/feedback_users_remember_patterns_not_moves].

---

## What we are NOT building

- **Not** candidate-move multiple-choice as the default play experience. (Explicitly
  rejected — it turns the coach into a tutor and the game into a scripted lesson.)
- **Not** a scripted lesson flow as the default. The Claude Design prototype's
  hardcoded Ruy Lopez is a beautiful _film_, not our product.
- **Free play is preserved and primary.** The user plays their own moves, freely,
  against the live engine. The coach sits beside them — it does not drive.

---

## The Six Pillars

Each pillar is defined as **a behavior the user feels**, not a screen.

1. **Pre-move coaching prompts** — the coach occasionally speaks _before_ you move,
   to shape _how_ you think about the position (never to hand you the move).
2. **Personal focus areas** — the coach is working on one or two specific things
   with you right now, and you both know what they are.
3. **Principle-level memory, not move memory** — the coach remembers _"you hang
   pieces when attacking,"_ not _"on move 14 of game 7 you played Nxe5."_
4. **Session goals** — a session opens with intent ("today, let's just not lose a
   piece in the first 10 moves") and closes against it.
5. **Pattern detection across games** — the coach connects today's mistake to the
   same mistake three games ago. Provenance is the point.
6. **Short, human coaching feedback** — one or two sentences, plain, warm. Never a
   data dump.

---

## The Two Hard Constraints (first-class rules, not afterthoughts)

These two rules outrank every feature. A feature that violates either is wrong, no
matter how good it looks.

### 1. Never make a personal claim without evidence (TRUTH)
_"You usually rush here"_ only lands if it is **true** and **backed by instances**.
A wrong personal claim is **worse than silence** — the moment the user thinks _"no
I don't,"_ the coach becomes a fraud and the whole illusion collapses. We do not
fire "you usually X" off one or two data points. We check the distribution first
(see [memory/feedback_threshold_before_distribution_is_sin]).

### 2. Speak rarely (RESTRAINT)
A coach who talks every move is not present — he is annoying. The coach is **quiet
~95% of the time** and speaks once, when it has something specific and true. The
existing habit-prompts (_"Pause, what is your opponent threatening?"_ every 5th
move, position-blind, on a timer) are the **anti-pattern** — the filler version of
this product. The premium version is their opposite: rare, specific, evidenced.
See [memory/feedback_principle_bank_is_filler]. **How rare "rare" is depends on the
band — see "How much the coach talks" below.**

---

## Coach Voice

**Simple English. Always.** No Hinglish ("arre", "beta", "haan"), no chess jargon
for the 600–1500 audience (no "fianchetto", "zwischenzug", "prophylaxis" — name the
square instead), short and human (one or two sentences). This is the same voice we
already enforce in captions.

**We do not need a new skill for this.** The discipline already exists:
- `/check-voice` — audits text against the voice rules
- `/rewrite-for-1200` — rewrites a snippet into the 1200-friendly voice
- the simple-English banned-jargon hit-list in `docs/simple_english_captions_scope.md`

All coaching-presence text routes through that existing gate. Building a parallel
"coach voice" skill would duplicate what we have (see
[memory/feedback_check_for_existing_ui_before_building_offline]).

---

## The Coach Across Skill Levels (600 / 1200 / 1600+)

The north star is constant. **What we teach the player to think _about_, and how
much scaffolding we give, scales with the rating band** — riding the
`RATING_BANDS` the app is already built on.

| | **600 (beginner)** | **1200 (intermediate)** | **1600+ (advanced)** |
|---|---|---|---|
| **Thinking we install** | The **safety scan** — notice a threat _exists_ at all | **Judgment** — is this threat real, or am I overestimating it? | **Meta-patterns** — my own recurring tendencies |
| **How concrete the prompt is** | Name the piece + square ("look at my bishop — is anything of yours it can take?") | Name the tension ("your knight's attacked — in danger, or not?") | Name the _type of moment_ ("this kind of position") |
| **What "knows you" sounds like** | "You've hung a piece three games running — always when attacking." | "You miss the second threat when there are two." | "You rush in sharp positions." |

**The 600 is different in kind, not just degree.** A 600 often doesn't even perceive
that a piece is attacked, so we don't ask them to _evaluate_ a threat — we teach
them to **look**. The whole early curriculum is essentially one habit: the piece-
safety scan (their dominant cognitive gap, 600–1200).

**The premium bet, stated precisely:** at 600, _"teach him to think"_ and _"tell him
the move"_ look almost identical in any single position — both lead to the same
move this turn. The difference is invisible in one position and **everything over
fifty games**: the told player still hangs pieces at game 50; the thinking-trained
player has internalized the scan and **no longer needs us**. So:

> **The coach's job at 600 is to make itself unnecessary.** A tutor creates
> dependence; a coach builds a routine and then fades. The metric the north star
> implies is _"does the user still hang pieces after a month with us?"_ — and no
> competitor's puzzle-grinder optimizes for that.

**Data note:** counter-intuitively, "knows you" is _easier_ to reach for a 600 — they
hang a piece almost every game, so a credible pattern emerges in 3–4 games, not 30.
For a 600 we won't be _guessing_ at thin patterns; we'll be _choosing which loud
pattern to coach first_ (and coaching only one at a time — a 600 drowns in more).

---

## How much the coach talks (cadence scales inversely with skill)

The lower the rating, the more the coach involves itself; the higher the rating,
the more it gets out of the way and lets the player play. **Restraint is not a
single number — it is a function of the band.**

| Band | How often it speaks | What it speaks about |
|---|---|---|
| **600** | Most often — instructive, hands-on | The ONE focus habit (the safety scan). Frequent reinforcement of a single theme — **not** commentary on every mistake (a 600 makes too many; commenting on all of them drowns them). |
| **1000–1200** | Sometimes | The focus area + genuinely instructive moments |
| **1400** | Rarely — mostly just play | Only a real blunder or a real, evidenced pattern. They want to play, not be lectured. |
| **1800+** | Almost silent | Only the rare, high-value insight they couldn't see themselves |

Two dimensions move together: a 600 coach is **frequent but narrow** (one theme,
often); a 1400+ coach is **rare but broad** (anything significant, seldom). The
constant across both ends: it never feeds the move, and never speaks just to fill
space.

---

## Adaptive Guidance — the coach reaches for tools when the data says they'll help

Free play is the default. But a coach who _knows you_ does more than comment — when
it spots recurring trouble, it **offers** a more structured path. This is **coach-
initiated, opt-in remediation**, not a forced mode. It is how the "guided opening"
idea fits the north star without becoming the multiple-choice tutor we rejected.

**The flow:**
1. The coach detects, across the user's games, a recurring weak spot tied to a
   specific opening (e.g. _"the Italian keeps going wrong around move 6"_, or _"you
   lose the thread in the English"_).
2. Mid-session or post-game, it _offers_ — never forces:
   > _"You've drifted into trouble in the Italian three games in a row, always
   > around the same moment. Want me to walk through it with you?"_
3. If the user says yes, we **deep-link into Play with Coach focused on that opening
   and that weakness** — using the rails that **already exist**:
   - `?opening=<key>` and `?focus=<area>` query params on the Play page
   - the `guidedMode` toggle ("Guide Me" / "I Know It")
   - `opening_key` + `guided_mode` already flow to the session-start endpoint
4. **Escalation:** repeated trouble in the same area → the coach can propose more
   guided games on that theme, increasing structure only as long as the user keeps
   struggling, then backing off (consistent with "make itself unnecessary").

**What's new vs. what exists:** the _trigger_ — detecting per-user opening/pattern
trouble and surfacing the offer at the right moment — is the new work. The
_launch mechanism_ (guided opening with a focus) is already built.

---

## What already exists (build on, do not rebuild)

The raw material for "knows me" is largely in place; the gap is the **junction** —
wiring it into a pre-move, position-aware, evidenced moment.

- **`coach_memory`** — persistent per-user weaknesses / strengths / patterns
- **`pattern_decay_service`** — recency-weighted "is this pattern active or fading"
- **`thinking_scores`** — habit scores per game (likely home for a "rushing" signal)
- **cognitive gaps + `behavioral_missions`** — weakness taxonomy + per-user focus
- **`opening_curriculum_engine`** + `opening_library_service` — curriculum keyed by
  opening; identifies the opening live from the position
- **`opening_mastery_tracker`** + `get_user_opening_progress` — per-user opening strength
- **`?opening=` / `?focus=` / `guidedMode`** — the guided-opening launch rails
- **rating-aware feedback** — classification already varies by band

---

## The One Proof Feature (build first, data-first)

Before building broad, we build the **single feature that proves the north star**:
the **pre-move, pattern-aware nudge** — _"Pause. This is the kind of position where
you usually rush."_

**Built data-first** (per [memory/feedback_threshold_before_distribution_is_sin] and
the `/lock-via-data` discipline):

1. **First, query the real games** — do users actually have detectable, repeatable,
   evidenced patterns we could credibly surface? How many instances per user? At
   what rating bands does the signal exist?
2. **Only then** design the trigger (what "this type of position" means, how many
   instances make "usually" honest, how rarely it fires).
3. If the signal is too thin for a band, the honest first version is **retrospective**
   ("across your last 10 games, here's a pattern I'm starting to see") until there's
   enough evidence to go pre-move and confident.

We do not ship a coach that guesses.

---

## Open questions / Needs Mohit

- **Visual adoption** — the Claude Design system (warm-dark, single amber accent,
  left icon rail, dark-default) is strong and we want much of it. Deferred on
  purpose: **product direction locks first**, visuals second.

_Resolved 2026-06-08:_
- **Voice** = simple English, no Hinglish, no jargon — routed through the existing
  `/check-voice` + `/rewrite-for-1200` skills. No new skill.
- **Cadence** = scales inversely with rating (600 frequent-but-narrow → 1800+
  almost silent) — see "How much the coach talks".

---

## Definition of done for THIS doc

This document is "done" when Mohit signs off on: the north star, the six pillars,
the two hard constraints, the rating-band calibration, the adaptive-guidance flow,
and the data-first proof-feature plan. No implementation begins before that.

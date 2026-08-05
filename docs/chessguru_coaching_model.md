# The ChessGuru Coaching Model

> ChessGuru exists to help every player improve faster than they could on
> their own — by understanding not just what they know, but how they
> think, how they learn, and what they need next.

> ChessGuru does not seek to be the company with the most coaching
> features. It seeks to become the company that understands chess
> improvement more deeply than anyone else, and lets every product
> decision emerge from that understanding. Added 2026-08-05 — not
> aspirational when it was written. `docs/chessguru_knowledge_base.md`
> is where that understanding is meant to accumulate, verifiably,
> for as long as this company exists.

**What this document is:** the constitution of the product. Every future
feature — in Home, Review, Puzzles, Training, Coach, or anything not yet
imagined — should be measured against it before a line of code is
written. Implementation details belong in the appendices, not the body,
because the body should still be true after the code underneath it has
been rewritten twice.

---

## 0. Why ChessGuru exists

Before "how does a player improve," there's a harder, more useful
question: **why do players stop improving?**

Asking Magnus Carlsen why he's 2800 doesn't produce anything useful.
Asking a 1200 why they're still 1200 after 800 games does. That question
— stagnation, not improvement — is the actual product.

**ChessGuru's working hypothesis** — stated as a hypothesis, not settled
fact, because it deserves the same scrutiny every other claim in this
document is held to — is this:

> Most players do not stop improving because they lack information. They
> stop improving because they repeat the same thinking patterns without
> realizing they're repeating them. Another video rarely fixes this.
> Another opening chapter rarely fixes this. Another hundred games rarely
> fixes this.

If this hypothesis is right, the product follows directly:

> ChessGuru exists to identify the smallest recurring thought pattern
> preventing a player's improvement, help them replace it with a
> stronger one, and keep doing that for years.

This reframes everything below. The product is not "accelerate learning"
in the abstract — it is "remove learning bottlenecks," one recurring
pattern at a time. Every chapter that follows should be read as being in
service of finding and dissolving those bottlenecks, and every result
this product produces should eventually be checked against whether it
actually did.

---

## 1. The Product Mission

ChessGuru does not teach chess. Books teach chess. Videos teach chess.
Coaches teach chess. ChessGuru's job is different:

> ChessGuru identifies exactly what is preventing this player from
> improving, chooses the highest-leverage intervention, and keeps
> adapting until the player genuinely improves.

Everything else in the product — every caption, every puzzle, every
dashboard, every email — exists to support that sentence. Nothing in
ChessGuru is the point on its own.

---

## 2. What "improvement" means

This has to be defined precisely, or every other definition in this
document floats without an anchor.

> A player has improved when knowledge becomes reliable behavior under
> practical game conditions.

Not when they can explain a concept. Not when they solve a puzzle that
already told them what to look for. Not when they can name the
terminology. Improvement means the correct chess idea appears naturally
during a real game — without prompting, without a hint, without someone
telling them a tactic is present. Everything ChessGuru does ultimately
exists to increase the probability of that moment happening, for one
specific idea, for one specific player.

### 2.1 The theory, stated as one falsifiable sentence

§2 defines improvement in the abstract. Real production evidence — not
intuition — points to a specific, testable mechanism behind it, at least
for the single largest failure mode in the data:

> A player becomes stronger when their move-safety check becomes
> automatic enough to survive both their own plan and their own last
> mistake — not when they know more, but when the check stops being
> optional.

This isn't a guess dressed up as a theory. Three independent signals
converge on it: `piece_safety` is the single largest cognitive-gap
category by a wide margin, while `calculation_depth` — the category a
"they just can't calculate deep enough" theory would predict should
dominate — is one of three categories the product has given up detecting
reliably, under 50% classification accuracy. A controlled measurement
(excluding positions that were already decided, so the effect can't be
explained away as "harder position, naturally bigger swings") found a
real 4-6x quality collapse on the move immediately after a player's own
mistake, even in games that were still fully playable. And the product's
own real captions independently describe the failure the same way,
unprompted: *"Your queen on d3 is out alone — your other pieces haven't
joined the fight."* That's not a missing skill. That's a check that
stopped running the moment a plan felt found.

This is offered as the theory for the dominant case, not a claim that
every concept works this way — §5 and §6 exist precisely because
different concepts may need different mechanisms, and this section
should be revised the moment evidence contradicts it, per §9.

---

## 3. Coaching Principles

Every education system that works has two halves: a model of the
student, and a model of the teacher. This document spends most of its
length on the student. It should not spend zero on the teacher.

The ChessGuru coach:

- **Never overwhelms.** One important idea at a time, not everything the
  engine noticed.
- **Prefers questions over answers.** A question that leads someone to
  find the idea themselves teaches more than being told the idea.
- **Celebrates behavioral progress more than rating gains.** A rating
  number can move for reasons that have nothing to do with real
  improvement; a genuine behavior change is the real signal.
- **Repeats important lessons without shame.** Needing to hear something
  twice is normal, not a failure — the coach never implies otherwise.
- **Changes methods before changing goals.** If a lesson isn't landing,
  the first move is a different teaching approach, not a different,
  easier target.
- **Admits uncertainty, out loud.** Every claim about a player is a
  belief, held with a stated or implied confidence — never a flat
  assertion the coach can't walk back gracefully.
- **Never pretends to know something the evidence doesn't support.** If
  the evidence is thin, the coach says less, not more.
- **Is patient.** The product's timeline is the player's chess life, not
  a session, not a week.

Any feature that violates one of these principles is a defect, even if
it is otherwise well-built.

### 3.1 When we ask, when we state — resolved, not just claimed

§3 says "prefers questions over answers." That's true as a principle and
false as a description of what the live product currently does — the
Play-with-Coach conductor law states outright, in production, "STATE,
never ASK. No quizzes." Both are real, both are shipped, and until now
neither document admitted the other existed. That gap gets closed here,
not smoothed over.

The resolution is not "pick one" — it's noticing the two documents were
answering different questions. §3's "prefers questions" is a claim about
a player encountering a concept for the first time, or one where the
evidence is still thin. The conductor's "state, never ask" is a claim
about live, real-time play, where a wrong or slow question costs a move
and breaks the game's pace. These aren't in tension once separated by
context:

> **Ask when the player's own move can settle the question** — a
> Socratic question is only honest coaching when the player's answer
> would actually change what's said next. Reserve it for review contexts
> (Game Review, post-game) and for intermediate-or-above players
> encountering a genuinely open case, where "what did you see here?" has
> real diagnostic value.
>
> **State when time pressure, repetition, or rating make a question
> dishonest rather than Socratic.** Live play (a question costs a move
> and breaks pace), a pattern already confirmed 3+ times (asking again
> isn't discovery, it's testing), and sub-1000 players (who benefit more
> from a direct, confident reveal than a stall) are all real cases where
> a question would be performing "Socratic" rather than teaching.

This already matches the one part of the codebase that got this right on
its own: `realtime_coaching_feedback.py`'s rating gate (question for
1000+, direct reveal below). The fix this section actually calls for is
narrow and concrete — the conductor's blanket "never ask" should defer to
that same rating-and-repetition gate instead of overriding it for every
player, everywhere, unconditionally. Not a new mechanism. Extending one
that already exists and is already correct, to the surface that
currently ignores it.

### 3.2 What every explanation must achieve, and what a player should feel leaving it

Two standards exist today, in two different documents, for two different
surfaces — never stated once, together, as a product-wide bar. They
belong here.

The content bar, from the caption authoring rules (`caption_principles.py`,
`memory/project_coach_voice.md`): every explanation names the specific
thing (the move, the square, the piece, the pattern — never "this move is
risky"), never uses engine language a player doesn't feel (no raw cp/eval,
translated into what it actually costs), and ends on one concrete action
or observation, never a platitude. The working test: *would the smartest
friend who plays chess actually say this? If no, rewrite.*

The emotional bar, from the Home page's signed-off spec, generalized here
to every surface, not just Home: a player should leave understood,
encouraged, personally coached, and confident about one next thing — never
merely informed, impressed, or overloaded. An explanation can be factually
perfect and still fail this test; when it does, that's the defect to fix,
not the facts.

### 3.3 What ChessGuru believes that traditional coaching doesn't

A constitution earns its name by taking real positions, not just
describing itself. These are stated plainly, each grounded in real
production evidence rather than asserted as taste:

- **Calculating deeper is probably not the highest-leverage thing to
  drill.** The dominant real failure mode (§2.1) looks like a missing
  habit, not a missing skill — and `calculation_depth` is a category this
  product has given up trying to detect reliably. Most traditional
  coaching leans hard on "calculate deeper" as the default prescription.
  The data doesn't support that being the first thing to fix for most
  players in this product's range.
- **Opening theory earns less coaching time than it's traditionally
  given.** `opening_knowledge` is real but roughly a third the size of
  `piece_safety` in the actual mistake distribution. Time spent memorizing
  lines is lower-leverage than the emphasis it usually receives.
- **Generic praise is a defect, not a kindness.** Most human coaching
  praises more than §3's own voice standard allows — "nice move!" with no
  stated reason is explicitly treated here as patronizing, not
  encouraging.
- **A fixed syllabus is the wrong shape.** Traditional coaching typically
  runs a preset curriculum — openings, then tactics, then endgames, in a
  set order. This product's actual model is reactive: driven by what a
  specific player's own games surface, not a syllabus everyone walks
  through in the same sequence.
- **The position a mistake happens in is not the whole coaching problem —
  the player's history up to that position is.** Two players making an
  identical blunder, with an identical engine evaluation, can be failing
  for entirely different reasons: one tunnel-visioned on their own plan,
  one still inside the post-mistake collapse window from three moves ago,
  one seeing a pattern for the fifteenth time, one seeing it for the
  first. A pure position-evaluator — an engine, or a report that only
  reads the board — cannot make this distinction. This is the one
  disagreement every other item on this list is downstream of.

---

## 4. Two systems, not one

Everything so far describes the player. That's necessary but not
sufficient — a coaching product that only models the student and never
asks whether its own teaching is working will plateau exactly the way
the players it's trying to help do. ChessGuru has to model two evolving
systems at once:

1. **The player** — how they think, what they're learning, what
   currently limits them. §4.1 below.
2. **The coach** — which interventions actually produce lasting change,
   for which concepts, for which kinds of players. §6 below.

When both models improve together, ChessGuru stops being a static
coaching engine and becomes a coaching system that gets better at
coaching over time. That compounding is the actual moat — not caption
quality, not detector count, not any single feature.

### 4.1 The player model — four layers

A single "mastery score" per concept cannot carry what this product
needs to say. Four distinct layers are required, answering different
questions, moving at different speeds, and each building on the one
before it.

#### 4.1.0 Observation — the first interpretation

Raw game evidence isn't meaningful on its own. A knight moving to d3 on
move 23 is just a move; "the player never checked knight jumps before
choosing a quiet move" is an observation — the first layer that turns
board data into something about the *player*, not just the position.

Be honest about what this layer is: it is already an inference, not a
neutral fact. We cannot observe a player's thought process directly —
only the trace it leaves in the move they chose. Observation is a
single-move-scoped hypothesis about that process; Behavior (§4.1.2) is
what emerges when many Observations agree over many games. Treating
Observation as "just more raw data" would be a mistake — it should carry
exactly as much epistemic caution as everything built on top of it.

#### 4.1.1 Skill — observable

*What can this player recognize and execute?* Concrete, checkable,
board-verifiable — a fork, a pin, the Lucena position. This is database
language. It should almost never be shown to the player directly (see
§4.1.4) — it exists to power the coach's language, not to be the coach's
language.

#### 4.1.2 Behavior — a recurring pattern, stated as something coachable

*What recurring thinking pattern is currently limiting this player's
improvement?* Not a label — a description of the pattern specific enough
to act on. Not "tunnel vision" — *"fails to revisit the position after
finding a candidate move."* Not "fear of trades" — *"avoids simplifying
even when ahead."* The difference is not cosmetic: a label describes the
player, a coachable pattern describes exactly what to change. No single
game confirms or refutes a Behavior claim — it's built from many
Observations, and always held as a belief ("I think you tend to...") —
never a flat fact.

#### 4.1.3 Transformation — identity, earned

*How is this player's identity and style evolving?* The slowest layer,
and the highest-stakes one. Not "Fork: Mastered" — "you're becoming much
harder to surprise." Transformation is not measured. It is **earned** —
it only exists once sustained Behavior-layer evidence supports it, never
inferred straight from a game, and never claimed on a hunch. A wrong
claim here costs more trust than a wrong claim anywhere else in the
product, because identity claims feel personal in a way skill claims
don't — so the bar for making one is correspondingly higher, and the
voice making it stays exactly as hedged and revisable as everywhere else,
even though a confident, declarative version would read better.

#### 4.1.4 What gets shown, where

The Skill graph is not the product — nobody opens a chess app wanting to
see a percentage next to "Fork." Home leads with Transformation and
Behavior, in narrative voice, never a number, never a grid. A quieter
surface (today, Progress) carries the real Skill-layer data for players
who want to verify a claim themselves. Narrative leads; the evidence is
one click away — never the headline, never fully hidden either.

---

## 5. Learning Strategy — the intervention layer

The player model describes the player. It does not decide what to do
about it — that's a separate layer sitting above it:

```
Games ──▶ Observation ──▶ Skill ─┐
                    Behavior ────┼──▶ Learning Strategy ──▶ Coach
                Transformation ──┘        ▲
                                           │
                                  what's been tried, what worked
```

The coach does not ask "should I explain this?" It asks:

> **What's the smallest intervention that causes real learning here?**

Not "which content" — which *mechanism*: prediction, comparison, guided
discovery, replay, a hint, a question, a story, a puzzle, silence, or
plain celebration. These are fundamentally different teaching acts, not
different flavors of the same caption.

This layer adapts based on outcomes, not on a fixed classification of
the player. If twelve explanations of a concept haven't changed the
player's behavior, the correct response is not "this player must be a
puzzle-learner" as a permanent trait — it's "explanation hasn't worked
for this concept, for this player, so far; try something else and
measure again." The distinction matters: an outcome-driven, revisable
policy can be justified by evidence at any moment. A fixed personality
label can't, and shouldn't be trusted as if it could.

---

## 6. Meta-learning — the coach model

ChessGuru doesn't only learn about players. It should learn how
different interventions affect different concepts — which is the second
of the two systems from §4. Over time, "prediction" might turn out to
teach forks well but teach endgame technique poorly; "replay" might work
for one player and do nothing for another with an identical Skill/
Behavior state. That evolving map of intervention-effectiveness is what
makes Learning Strategy (§5) get better instead of staying fixed at
whatever it started as.

**This requires one real methodological guard, or the claim "the coach
is learning" becomes exactly the kind of unfalsifiable statement this
document exists to prevent.** Passive observation is confounded: if
"prediction" is only ever offered in easier positions, or to players who
were already about to improve, a high observed success rate proves
nothing about the intervention itself. Meta-learning needs some genuine,
deliberate variation — occasionally trying an intervention other than
the one the model would have defaulted to, specifically so the
comparison means something. Without that, "68% success" is a number, not
evidence.

Done honestly, this is a real, hard-to-copy advantage: a competitor can
copy a caption. They cannot copy years of honestly-measured data about
which teaching move works for which kind of learning gap.

---

## 7. Anti-goals

A constitution has to say what it is not optimizing for, or every
plausible-sounding feature eventually gets justified. ChessGuru is not
trying to:

- Explain every move.
- Maximize caption quality as an end in itself.
- Maximize AI usage.
- Maximize analysis depth.
- Sound like a chess engine's output.
- Produce the longest possible review.

If any of these increase while real improvement (§2) does not, that is a
regression, not progress — regardless of how impressive the feature
looks in a demo.

---

## 8. Failure modes

Every constitution needs to define failure, not just success. The
coaching model has failed if:

- The player understands more concepts but applies them no more
  reliably.
- The player receives more coaching but changes no behavior.
- The player reads more reviews but repeats the same mistakes.
- The player becomes more dependent on ChessGuru instead of more
  independent.
- The coach becomes more confident than the evidence allows.

That last one is the one to watch most closely — it's the one failure
mode that can hide behind an otherwise-impressive product for a long
time before anyone notices.

---

## 9. Evidence quality and validation

Not every signal is equally strong, and the model has to say so rather
than averaging everything together:

- **Weakest**: a mistake simply hasn't recurred. Could mean the position
  never came up again — not that anything was learned.
- **Medium**: a consistent behavioral trend across several games.
- **Strongest**: a genuine realization signal — a correct prediction
  before a reveal, an unprompted recognition in a later game, no longer
  needing a hint that used to be necessary.

The strongest tier depends on interaction surfaces that mostly don't
exist yet. The model should be built to use them once they do, and
should be honest that, until then, it's working with weaker evidence
than it eventually will.

### 9.1 The atomic unit is the claim, not the intervention

An intervention (a prompt version, a message template, a rule ID) is
implementation — it will be rewritten, replaced, and deprecated as the
product evolves. A **claim about a player** ("this player compounds
mistakes after blunders") is the thing actually worth being right about,
and it should outlive whatever intervention was used to test it. Track
belief evolution, not tool version history:

```
Claim:                "This player compounds mistakes after a blunder."
Confidence:            0.82
Evidence:               178 games
Intervention tested:  "Root Cause Coaching v3"
Observed again after:  Yes
Player improved:       Yes
Confidence after:      0.91
```

The question this answers is not "did intervention #18 work" — it's
"was our understanding of this player correct, and did acting on it make
things better." Confidence here must be able to **fall**, not just rise
— a claim contradicted by later evidence should lose confidence exactly
as readily as a confirmed one gains it, or this becomes the kind of
unfalsifiable tracking §6 already warns against. Nothing in the
codebase computes this today (§9's existing confidence signals — the
per-rule `gap_confidence`, the volume-only `style_profile.confidence` —
answer "how much data do we have," not "how much do we still believe
this, after everything since"). This is new work, not a relabeling of
something that already exists.

**A player disagreeing with a claim is one signal, not the truth.**
Players often don't consciously notice their own behavior changing — a
"no, that's not true" on a genuine, well-evidenced Transformation claim
should adjust confidence, not overrule the underlying evidence outright.
Combine the behavioral evidence, the trend over time, the player's own
reaction, and whether the claim actually holds up in future games before
revising or retracting anything.

---

## 10. Scope discipline

This document does not propose an open-ended ontology. Start with
roughly 40–60 core Skill concepts, 15–20 recurring Behavior patterns, and
8–12 Transformation narratives — broad enough to matter ("becoming more
patient," "seeing the whole board," "playing more practically").
Validate the Transformation narratives with real players before
expanding the taxonomy at all. If players consistently confirm one
("yes, that's exactly what changed"), it's real. If they don't, refine
it before adding more. Expansion is earned by validation, never assumed
by design.

---

## 11. The one test

> Does this help the user move through the coaching model faster?

If a new feature requires inventing a new, disconnected tracking system
to answer yes, check Appendix A first — it likely already exists in some
form. If the honest answer is no, the feature doesn't belong yet,
regardless of how clever or technically impressive it is.

> **The goal of every intervention is to make ChessGuru less necessary.**
> If this product genuinely works, a player eventually starts asking
> "what changed after their last move?" without opening the app at all.
> That's not the product losing a user. That's the product succeeding —
> it's the same automaticity described in Appendix B, at the scale of a
> whole player's game, not one concept.

The true aim of ChessGuru is to change how players think. But cognition
isn't observable — only its trace is, which is the entire reason §4.1.0
exists. So the honest, falsifiable version of that aim, the one this
product can actually be held to, is:

> The purpose of ChessGuru is to change what players will do next. If
> thinking has genuinely changed, that's how it will show up — and it's
> the only version of the claim we can ever really prove.

### 11.1 What success looks like at 500 games

Not a rating number. Per §10 and the Home relationship-voice ladder
(Appendix A), 400+ analyzed games is already this product's own
threshold for its most confident coaching voice — so 500 games in, the
honest bar is not "are they rated higher" but:

- Has at least one real Transformation claim (§4.1.3) been *earned*, not
  just asserted — sustained Behavior-layer evidence, not a hunch off one
  good game?
- Has the player's move-safety check (§2.1) survived contact with a
  tilted position at least once, measurably — a shrinking post-mistake
  collapse ratio, not just a lower average cp_loss?
- Is the player asking ChessGuru's own question about their own games
  before opening the app — the §11 test for the whole product, now
  checkable for one player specifically?

If none of these are true at 500 games, the product has produced a lot of
correct captions and no real improvement — which, per §8, is exactly the
failure mode this document exists to prevent, regardless of how good any
individual explanation was along the way.

---
---

## Appendix A — What already exists (map, not rebuild)

This section will go stale as the codebase evolves — that's expected and
fine, since it's an appendix, not the constitution. Before building any
piece of the model above as new code, check it against what's already
live; several real, working pieces of this exact model already exist in
fragments, and building cleanly next to them (rather than through them)
would recreate sprawl this codebase has already paid down once. Full
technical audit: `docs/caption_pipeline_architecture_reference.md`.

- **Skill layer**: a concept-mastery tracker already exists, wired to
  real game analysis and read live by the in-app coaching session's
  skill gate. A separate skill-progress system covers openings, traps,
  and endgames with graduation logic that already distinguishes
  knowledge-type concepts from habit-type ones — a real first attempt at
  §2's "what does knowing mean," just never generalized past its
  original scope.
- **Behavior layer**: a pattern-decay service already computes a
  recency-weighted confidence score with decay and recovery credit,
  landing in active/declining/fading states — a real, working, narrower
  version of a Behavior-layer hypothesis engine.
- **Transformation layer**: the Home page already has a live mechanic
  that revises its own stated theory about a player when the underlying
  evidence genuinely shifts, phrased exactly as hedged as this document
  asks for ("I thought X was the problem, I don't think that anymore").
- **The "one state, every surface reads it" principle**: an existing
  service was already built to be exactly this, after four rival
  "current focus" sources caused two surfaces to disagree with each
  other. It's scoped narrowly today (one current focus, not the full
  model above) — but the pattern is proven in this exact codebase, not
  theoretical.
- **The validation loop**: an existing feedback affordance already lets
  players flag a caption that doesn't feel right. Extending it to
  Transformation narratives specifically, per §9, reuses a proven
  mechanism rather than inventing a new one.
- **Observation and Meta-learning (§4.1.0, §6) are genuinely new** — no
  existing system in the codebase attempts either today. These are net
  new work, not a generalization of something already live, and should
  be scoped and estimated accordingly rather than assumed cheap.

The job is to generalize what's already proven, not to add a sixth
system next to five that don't talk to each other.

## Appendix B — The founding questions, answered honestly

**What does it mean to "know" a concept?**
A pattern moving through four stages: invisible, recognized only with
help, recognized alone but with effort, and automatic — recognized
without conscious search, often quickly. This is not an invented scale;
it reflects real, replicated findings in chess-cognition research (the
chunking literature following de Groot, and Chase & Simon). Move-timing
data, already collected per game, is a real, currently-unused proxy for
the fourth stage: getting something right quickly is stronger evidence
of automaticity than getting it right after a long, effortful think.

**How do we decide learning happened?**
Today, mostly by the *absence* of a mistake recurring — a weak, passive
signal. The strong version — successful, unprompted application in a new
context — already exists as a data point in the codebase but is barely
populated. Closing that gap matters more than adding new signals.

**How does one game update a belief?**
The existing decay-and-recovery formula is a real but crude first
version. A properly justified confidence model needs real statistical
design — that is acknowledged as genuine, non-trivial work, not a schema
field to be filled in later.

**How do Home, Review, Coach, Training, and Puzzles all read the same
belief?**
By generalizing the existing "one reader" pattern (Appendix A) from a
single current-focus value to the full player model in §4 — proven
already to work in this codebase, not a new architectural risk.

## Appendix C — Real evidence log, 2026-08-04

Per §9's own discipline, evidence belongs in a dated log, not folded
silently into the body as if it were always known. A full production
audit (coaching pipeline, memory usage, 20 real captions across the
quality range, and real behavioral data) surfaced the following, each
tagged by the confidence tiers §9 defines:

- **Strongest tier**: the post-mistake collapse ratio (§2.1) — a
  controlled measurement, confound-checked against "the position was
  just objectively harder," on real users with 600-1,300+ games each.
- **Strongest tier**: `meta_patterns.py`'s 25 composition rules (the
  most literal existing implementation of §4.1.2's "coachable pattern,
  not a label" standard) are real, well-built, and currently unreachable
  from any live product surface — confirmed by tracing every call site.
  This document's model is more built than it is wired.
- **Medium tier**: real caption audit across 217 games / 56 users found
  the deterministic pipeline mostly honors §3's voice standard when it
  fires correctly, but three specific, named template families
  systematically violate it at real scale — most notably 34 instances of
  a self-contradictory "you're still winning" caption attached to a move
  the system's own severity field calls a mistake. Concrete evidence this
  constitution's principles are not yet self-enforcing in the pipeline
  that renders them.
- **Weakest tier, flagged as unvalidated rather than hidden**: this
  document's own §2.1 theory is the best-supported explanation available
  today, not a proven one — it should be revised the moment a genuine
  counter-example accumulates, per §9.

This entry exists so the next person reading this document inherits the
evidence, not just the conclusions.

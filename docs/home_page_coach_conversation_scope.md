# Home Page — Coach Conversation — Scope Document

**Status:** SIGNED OFF by Mohit. All four open questions resolved below.
Remaining pre-code work: the theory-of-why belief bank (§7).

---

## The one sentence every engineer should hold

> If a sentence exists because data was computed, it probably belongs on
> Progress. If a sentence exists because a coach would naturally say it after
> watching hundreds of games, it belongs on Home.

Every other rule in this document is downstream of that one. When in doubt
during implementation, this is the test — not the section list below it.

## Emotional goal

This comes before "what it is" on purpose: the emotional outcome is the
actual target, and rendering/hierarchy/mission are just how we get there.

When the user closes the Home page, they should not remember a statistic.
They should remember one thought their coach shared. They should leave
feeling:

- **understood**
- **encouraged**
- **personally coached**
- **confident about today's one mission**

If instead they feel *informed*, *impressed by the AI*, or *overloaded with
analysis*, the page has failed — regardless of how accurate or well-designed
it is. This is the actual pass/fail test for everything below, including
things that look correct on paper.

## Relationship principle — trust grows over time

The coach should never sound like the same person forever. The voice itself
carries the relationship's depth, on a real ladder:

- **Week 1:** *"I'm still learning how you play."*
- **Month 3:** *"I'm starting to see your habits."*
- **Month 6:** *"I know what usually causes your losses."*
- **One year:** *"I already know what will be hard for you, before it
  happens."*

The exact tenure boundaries that trigger each stage are an open question
(§6) — resolved from real data, not guessed — but the ladder itself, and the
fact that the coach's confidence and familiarity visibly deepen over the
relationship, is locked.

## Plain English, for every English speaker

This is separate from avoiding chess jargon (already a standing rule
elsewhere in this codebase) — it's about the English itself. The coach must
read clearly to someone who learned English as a second language, not just
to a fluent native reader. Concretely:

- Short sentences. One idea per sentence. Prefer two simple sentences over
  one sentence with a comma and a subordinate clause.
- Common, concrete words. "Plan," "move," "board," "safe," "win," "check" —
  not "instinctively," "composure," "unfamiliar," "carelessness," or
  "judgment."
- Simple tenses. Mostly simple present and simple past. Avoid stacked
  conditionals ("would have," "might have been").
- Avoid idioms and phrasal verbs where a plainer word says the same thing
  ("stop" instead of "cut it out," "find" instead of "come across").

Every piece of coach-voice copy in this document — the mockups, the
identity table, the theory-of-why bank — is written to this standard below.
This is now a permanent constraint on all Home page copy, not a one-time
pass.

## Identity over skill

The coach describes the player, not the chess concept. This reframing
applies to every one of the six cognitive-gap categories with real signal
today:

| Chess-concept framing (avoid) | Identity framing (use) |
|---|---|
| "Improve piece safety." | "We're making you a player who keeps pieces safe without thinking about it." |
| "Fix king safety." | "We're making you a player who stays calm when the king is under attack." |
| "Improve calculation / reduce tactical oversights." | "We're teaching you to slow down before you move." |
| "Study your openings more." | "We're building your confidence in positions you don't know yet." |
| "Improve endgame technique." | "We're teaching you to stay careful even when you are already winning." |
| "Reduce missed tactics." | "We're training you to check your opponent's plan, not just your own." |

This table is the identity-label layer. The full belief bank — one real
theory-of-why per category, not just a relabeled identity — is below.

### The theory-of-why bank (pre-code requirement, §7)

Each entry: the identity frame, then the hedged causal theory the coach
actually says. All six are written to the same test as the §2 mockups —
would a real coach say this after watching hundreds of games, not "does
this sound insightful."

**piece_safety** — *"We're making you a player who keeps pieces safe
without thinking about it."*
> "I don't think you are careless. I think when you find a plan, you stop
> looking at the whole board again. You trust it looks the same as before.
> But it changes every move."

**king_safety** — *"We're making you a player who stays calm when the king
is under attack."*
> "I think you like making threats more than staying safe. Castling can
> feel like a slow move. But it is often the most important move you can
> make."

**missed_tactic** (forks / pins / skewers) — *"We're training you to check
your opponent's plan, not just your own."*
> "I don't think you cannot see the tactic. I think you look for your own
> plan first. You check your opponent's plan second — or not at all."

**tactical_oversight** — *"We're teaching you to slow down before you
move."*
> "I think you stop thinking as soon as you find a move that looks good.
> Not because you cannot think further. Finding a good move feels like the
> job is already done."

**opening_knowledge** — *"We're building your confidence in positions you
don't know yet."*
> "I don't think you dislike opening theory. I think when a position looks
> new to you, you trust your own idea more than what you learned before."

**endgame_technique** — *"We're teaching you to stay careful even when you
are already winning."*
> "I think when you are clearly winning, you relax. It feels like the hard
> part is over. But that is exactly when careful play matters most."

---

## 0. Existing surfaces audit

**Path chosen: EXTEND existing, not replace.** The Home page already has
several pieces built with the right instinct. The work is subtraction,
relocation, and one new piece of wiring — not a rebuild from zero.

| Existing piece | What it renders today | Verdict |
|---|---|---|
| `game_mirror.py` → "Since you last played" | Coach-voice paragraph anchored to one real move (`"Move 23 of the loss: Nxd3 left a piece undefended..."`) | **Keep, extend.** Already the right voice; becomes one beat in the conversation, not a boxed card. |
| Coach Opening prescription card | *"Coach: 'This week we're fixing one thing... For the next seven days, I only want you to focus on...'"* | **Keep, extend.** Already first-person, already one-thing-at-a-time. |
| "Who you are as a player" (identity trajectory) | Archetype + narrative summary | **Keep, extend.** The seed of the relationship-stage idea already exists here. |
| `session_greeting_service.py` | *"Welcome back — day 4 of your king-safety focus. Last game you handled 3/5 focus moments cleanly."* — real, working, continuity-across-sessions memory | **Reuse.** Currently wired to Play with Coach only. This is the actual "remembers what I worked on last week" mechanism — it already exists, it's just never been surfaced on Home. Note: its own phrasing ("3/5 focus moments") is itself a count and will need the same identity/voice pass before reuse, not a direct port. |
| `pattern_decay_service.py` (ACTIVE / DECLINING / FADING states, clean-streak credit) | Backend state only, not directly user-facing on Home | **Reuse as backend signal only.** Powers "the coach noticed something changed" and the "coach revises a theory" idea — but the streak/count itself is never exposed in the coach's voice (see §3, and the "what to remove" note below). |
| `CoachRecommendationsGrid` | *"Confidence 85%"*, *"+75 elo (Realistic: 85% improvement)"*, *"12 mistakes · 68% confidence"* | **Remove from Home entirely.** Direct violation — literally every term Mohit named lives in this one component. |
| "You're improving" section | *"23% fewer events per game"* | **Remove from Home.** Raw percentage as the entire message. |
| "What your games show" (strength profile) | *"Rated around 1340"*, expandable 6-domain numeric score grid | **Remove from Home.** Rating numbers and a literal stat grid. |
| Diagnostic CTA | *"Take a 25-puzzle diagnostic"* | **Reframe or relocate.** Puzzle-count framing is a minor version of the same problem. |

**The structural problem is bigger than wording.** Today's page stacks up to
ten sections concurrently. Rewriting each sentence into coach voice without
changing that structure still fails the mission — ten things at once is not
"one conversation."

## 1. What it is

The Home page stops being a dashboard that reports on the user's chess and
becomes a single continuous conversation with a coach who has watched
hundreds of their games and has formed real opinions about them — not just
their chess, but their habits, tendencies, and the psychology behind both. It
answers exactly three questions: **where am I in my improvement journey,
what does my coach want me to focus on now, and what should I do next.**
Anything that doesn't answer one of those three belongs on Progress, Lab, or
Insights instead. The coach doesn't just describe *what* the player does —
it speculates about *why*, out loud, in hedged language ("I think...", "my
current theory is..."), and describes the player's identity taking shape,
not a skill score improving. The page reads top to bottom like something a
person would say out loud: a greeting, a callback to what they've been
working on, a belief about why a pattern exists, today's one mission,
encouragement, and one clear action. No percentages, confidence scores,
mistake counts, ELO predictions, streak counts, or dashboards anywhere on it
— including inside the prose.

## 2. What the user sees

A real mockup, using the app's actual data shapes — not placeholder text.
Note what's *not* here: no exposed streak count, and the belief goes past
relabeling the observation into an actual theory of cause:

> Good evening, Mohit.
>
> We have worked on piece safety for 9 days now. I see you protect your
> pieces better now. You don't even have to think about it. That is a good
> habit forming.
>
> But last night's loss made me think. I thought you were just playing fast
> in hard positions. I watched your last ten games again. Now I think it is
> something else. When you find a plan you like, you stop checking what
> your opponent wants to do. This is not carelessness. You are just
> looking in the wrong place.
>
> So today, just one thing: before you move, ask "what does their last
> move want?" Ask this before you ask "is my move good?" That is your only
> job today.
>
> I will tell you how it went tomorrow.
>
> **[ Play with Coach → ]**

**A deeper relationship, later** (illustrating the staged voice, not a
separate template):

> Six months in, I know what usually causes your losses before they happen.
> You get excited when you see a chance to attack. Then you stop checking
> your move once you decide to play it. Tonight was clean until move 31,
> and that same excitement is what got you there. Same job as this week:
> check every capture all the way to the end before you play the first one.

**One year in** (a single illustrative line, completing the ladder from the
Relationship Principle above):

> I already knew this was coming. Every time you are a piece up and the
> board gets simple, you relax half a move too early. Let's catch it
> before it costs you tonight.

Nothing above is a stat, a count, or a percentage — including the "9 days"
and "move 31" references, which anchor the story in something real and
specific without being a metric the user is meant to track.

## 3. In scope (V1)

- A mission gate applied to every existing element on Home: keep only what
  answers "where am I / what's the focus / what's next" — everything else is
  relocated (destination TBD, §6) or deleted.
- `CoachRecommendationsGrid`'s confidence%, elo-gain, and mistake-count
  rendering removed from Home. If the underlying plan-picker is still useful
  elsewhere, it moves to Progress or Lab — not V1's problem to solve.
- The "You're improving" raw-percentage section and the "strength profile"
  rating/domain-score grid removed from Home.
- `session_greeting_service` (or an equivalent continuity read) wired onto
  Home for the first time, with its own count-exposing phrasing ("3/5 focus
  moments") rewritten to match this spec before reuse.
- The ten-section stack replaced by one continuous narrative render:
  greeting → continuity callback → belief-with-a-why → today's one mission →
  encouragement → one action.
- **No internal counters exposed in the coach's voice, ever** — clean
  streaks, mistake tallies, puzzle counts, and session counts are backend
  signals that decide *what* the coach says, never words the coach says out
  loud. ("I've started seeing the habit stick," not "3 clean games.")
- A curated belief layer, one per confirmed-signal cognitive-gap category
  (the six in the Identity table above), each authored as a *theory of why*
  — not a relabeled observation — always hedged ("I think...", "my current
  theory is...") and always identity-framed per §"Identity over skill."
- A staged voice keyed to relationship tenure on the Week 1 / Month 3 /
  Month 6 / One year ladder, with exact boundaries resolved as an open
  question (§6) rather than guessed.
- A "coach revises a theory" narrative moment, firing only when a real,
  already-tracked signal changes (a flagged pattern's decay state flips, or
  its dominant sub-cause changes) — never on a timer or at random.
- Every sentence that ships passes three literal tests during copy review:
  the engineer's sentence at the top of this document, the emotional-goal
  test (does this produce *understood / encouraged / personally coached /
  confident*, or does it produce *informed / impressed / overloaded*), and
  "would Magnus's coach actually say this out loud to his student?"

## 4. Explicitly out of scope (V1)

- Redesigning Progress/Lab/Insights to absorb the relocated stat content — a
  follow-on scope once §6's open question on destination is resolved, not V1.
- A general-purpose belief-generation system for arbitrary claims. V1's
  interpretive layer is a small, hand-authored set of belief phrasings tied
  to the six categories with real signal today — not open-ended generation,
  and not extended yet to the four categories without confirmed signal.
- New chess-analysis detectors or signals. V1 is a narrative/rendering layer
  on top of data that already exists (pattern decay, cognitive gap, focus
  tracking) — it does not add new engine analysis.
- A/B-testing infrastructure for measuring trust. V1 ships qualitatively
  gated (§5) — a real quantitative trust experiment is a later project.
- Mobile-specific layout work beyond what the conversation model needs by
  default.

## 5. Success criteria

This page is explicitly not optimizing for engagement in the usual sense —
the brief itself rejects "more information shown" as a win condition — so
the primary gate is qualitative, with quantitative signals as secondary
confirmation, not the headline:

- **Primary (ship gate):** every sentence on the shipped page passes the
  emotional-goal test and the engineer's-sentence test in a full read-through
  Mohit does before launch — a literal line-by-line pass/fail.
- **Automated regression:** zero renders of a raw `%`, "confidence", "elo", a
  bare rating number, or an exposed count (streak, mistake tally, puzzle
  count) anywhere on the Home route — a real, checkable assertion in the
  style of the existing `pwc_coaching_lint.py` pattern.
- **Behavior, secondary:** Day-2 return-visit rate on Home post-launch vs. a
  pre-launch baseline pulled before shipping.
- **Behavior, secondary:** click-through rate on the single end-of-page
  action vs. the current page's blended CTR across its ~6 competing CTAs
  today.

## 6. Open questions — RESOLVED

- **Relationship-stage boundaries.** Real production data (pulled July 30,
  2026) showed calendar tenure is unreliable for most of the current user
  base — ~40 of 62 active accounts share a `created_at` clustered at almost
  exactly 100–102 days regardless of real activity (1 to 1,281 games
  analyzed), consistent with a bulk backfill/migration event rather than
  organic signup timing. **Resolved: the ladder is keyed to `games_analyzed`
  (how many games the coach has actually watched), not calendar time** —
  which also matches Mohit's own framing ("after watching hundreds of
  games") better than a date ever would:
  - Week 1 voice: < 20 games watched
  - Month 3 voice: 20–150 games watched
  - Month 6 voice: 150–400 games watched
  - One year voice: 400+ games watched

  Calendar-stage labels ("week 1," "six months in") stay as prose flavor
  only — never a literal claim the data can't back up.

- **"Coach revises a theory" trigger.** Resolved: fires when a gap category
  that was the *headline* pattern in a prior Home narrative later
  transitions from `pattern_decay_service`'s ACTIVE state to DECLINING or
  FADING, **and** a different category has since become the new headline.
  A real, already-tracked state change — never a timer, never random.

- **Where relocated stat content goes.** Resolved: a **new Insights
  surface** — not Progress, not deleted. Building that surface is its own
  follow-on scope (§4); Home V1 removes the content from Home regardless of
  that surface's build timeline.

- **Whether the multi-plan picker stays on Home.** Resolved: it does not,
  in any form — no picker, no quiet "work on something else" link. It
  relocates to Progress/Lab. On Home, the coach assigns the one focus.

## 7. Pre-code requirements

- ✅ Mohit has explicitly signed off on this full scope document.
- ✅ Real tenure-vs-games-analyzed distribution pulled from production —
  resolved open question 1, and changed its answer from what was assumed.
- ✅ Trigger condition for "coach revises a theory" defined against data
  that already exists — resolved open question 2.
- ✅ Destination for relocated stat content decided — resolved open
  question 3.
- ✅ One-action-vs-plan-picker decided — resolved open question 4.
- ✅ The theory-of-why belief bank drafted for all six confirmed-signal
  categories (see "The theory-of-why bank" above) — needs Mohit's read for
  voice/accuracy before code, but the authoring gate itself is satisfied.

**All pre-code requirements are now met pending Mohit's review of the
theory-of-why bank's wording.** Next step: `/audit-pre-code`, then the
first file.

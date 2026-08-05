# RFC: Longitudinal Evidence Pilot

**Status:** RFC — a research question, not an implementation spec. No
code should be written against this document until it's explicitly
signed off, per `/scope-driven-development`. If signed off, Phase 0
(the aggregation layer, §4) gets its own scope doc before anything
else is built.

**The question this RFC exists to answer:** do we have enough evidence
to justify building longitudinal coaching as a distinct capability? Not
"should we build Monthly MRI" — that's the user-facing artifact, and a
downstream question. This is upstream of it.

---

## 1. Problem

Coaching today is almost entirely episodic — a move, a game, a session,
graded against itself. `docs/chessguru_knowledge_base.md` Observation
#005 already confirmed this at the caption level (0% of 140 real
captions gave any next-game/cross-game action framing). This RFC asks
the same question one level up: not "does a caption reference the
past," but "does ChessGuru have the machinery to say something true
about a player that only 6+ months of history could reveal, and is
that population large enough to matter?"

We have rich per-game historical data. We do not have an aggregation
layer capable of turning it into a time-windowed comparison.

## 2. Evidence

Checked directly, 2026-08-05, not assumed:

- `thinking_scores` contains **12,751 real documents** — per-game habit
  scores (`threat_awareness`, `tactical_vision`, `move_verification`,
  `king_safety`, `patience`), each with a `calculated_at` timestamp and
  worked examples. (Correction to CLAUDE.md, which lists 31 docs — that
  figure is stale.) This is a genuinely strong raw ingredient: real,
  per-concept, per-game, timestamped.
- **No month-over-month or time-windowed aggregation exists anywhere in
  the backend.** Grepped for `last_month`/`this_month`/`month_over_month`/
  week-over-week comparison logic — zero matches. The data to compute
  "41% in March, 72% in August" exists; the code that would compute it
  does not.
- **The eligible population is small and sharply tiered**, not "existing
  users" broadly (63 users have ≥1 game):
  - 1300+ games: **1 user**
  - 700+ analyzed games: **5 users**
  - 300+ analyzed games: **14 users**
  - 100-299 analyzed games: 12 users
  - This reframes the project's justification. It is not a retention
    initiative (it can't meaningfully touch most users today). It is an
    R&D initiative — the honest claim is *this produces the evidence
    that improves tomorrow's product*, not *this improves today's
    users' experience at scale*.
- **A real experiment-contamination risk exists in this exact
  population**: `user_614cc832fc89` (560 analyzed games, comfortably
  pilot-eligible) is simultaneously enrolled in Experiment #1's Cohort A
  (the live Habit Coach reminder holdout). See the new standing policy
  in `docs/chessguru_research_ledger.md`.

## 3. Scope

Pilot only. Eligible users:

- ≥300 analyzed games
- Not currently enrolled in any active coaching experiment's cohort
  (checked against the Research Ledger's running experiments at
  pilot-run time, not a one-time check)

At today's numbers, that's roughly 13 of the 14 users with 300+ analyzed
games (14 minus the 1 contaminated by Experiment #1).

## 4. Deliverable

**Phase 0 — the aggregation layer.** Without this, the pilot cannot
exist regardless of narrative quality:

```
thinking_scores (per-game, per-concept, timestamped)
        ↓
time-window aggregation (group by calendar month or rolling N-day window,
        per user, per concept — does not exist today)
        ↓
behavior comparison (window A vs. window B, same concept)
        ↓
coach narrative (stated in coaching voice, not a stats dump)
        ↓
Monthly MRI (the user-facing artifact)
```

**Phase 1 — one report, one insight, per pilot user. Not ten.** Example
shape (illustrative, not a template to fill mechanically): *"Threat
awareness improved 27 percentage points between April and July."*
Nothing more per user in this pilot — the question is whether the
aggregation layer can produce *one* trustworthy insight, not whether it
can produce a dashboard.

**Every insight must also answer:** *"What should the player do
differently because of this?"* An insight that only says "you've
improved" is satisfying but inert. A longitudinal insight that doesn't
point to an action is graded the same as a caption with no why — not
acceptable, per `docs/chessguru_knowledge_base.md` Observation #005's
own finding.

## 5. Vision and success — kept deliberately separate

**Vision (inspirational, not testable on purpose):** *Deliver coaching
that would have been impossible six months earlier, because it depends
on longitudinal evidence no snapshot could produce.*

**Acceptance criteria (testable, the thing an insight is actually
graded against):**

- A longitudinal coaching insight is valid only if it compares at least
  two measured time windows separated by **≥60 days**, and the
  comparison **cannot be computed from either window alone**.
- **The literal test:** *could this insight have been generated using
  only the last 30 days of data?* If yes, it doesn't belong in this
  pilot — reject it, however well-written. If no, it's a real
  longitudinal insight.
- Success for the pilot as a whole is not engagement, not retention,
  not a satisfaction score. Success is: **did the aggregation layer
  produce at least one insight, for at least one real user, that passes
  the 30-day test and names an action?** If yes, longitudinal coaching
  is proven as a capability, even before it's proven as a growth lever.

## 6. Risks

- **Experiment contamination** — addressed in §3 and the new Ledger
  policy; must be re-checked at pilot-run time, not just at design time,
  since Experiment #1's cohort composition can change.
- **Insufficient history** — the eligible population is 13 users today.
  A pilot this small can demonstrate the capability exists; it cannot
  demonstrate the capability generalizes. Don't let a good result here
  get reported as "users love this," only as "this is buildable and
  produces a real insight."
- **Aggregation complexity** — `thinking_scores`' per-game grouping is
  real but uneven (game frequency varies wildly per user; a calendar-
  month window may contain 2 games for one pilot user and 40 for
  another). The aggregation layer needs to handle sparse months
  honestly (state "not enough games this window" rather than force a
  comparison), not paper over it.
- **Narrative quality** — a correct number ("27 percentage points") is
  not automatically a good caption. This pilot inherits every lesson
  already logged about caption tone, the action requirement (§4), and
  verifying every claim per-position before it ships — the same
  discipline as every other coaching surface, not a new set of rules.

## 7. Future — conditional, not committed

If the pilot produces at least one insight that passes §5's acceptance
criteria: consider expanding eligibility to 100-game and then 50-game
users, **only if** the aggregation layer still produces meaningful
signal at that lower game count (sparser history could mean the 60-day
window comparison becomes noise, not signal — that's an open question,
not an assumption either way). If the pilot produces zero passing
insights: that's a real result too — it means either the aggregation
layer needs more work before judging the capability, or the capability
doesn't hold up even in the best-case population, and the honest next
step is naming that in `docs/chessguru_graveyard.md`, not quietly
retrying.

---

*This RFC does not authorize writing the Phase 0 aggregation layer.
Signoff on this document authorizes writing `docs/longitudinal_evidence_pilot_scope.md`
(the actual pre-code scope doc, per `/scope-driven-development`) — not
code directly.*

# Experiment #1 — Universal Habit Coach Holdout, Scaled

**Status:** DRAFT — pre-registered before any new assignment happens, per
the rule agreed 2026-08-04: *no experiment starts until this document
exists.* Requires an explicit decision on §1 (eligibility) before
implementation begins — flagged there, not assumed.

**Belief under test** (Research Ledger row): *the in-game habit reminder
(Universal Habit Coach) causally reduces the targeted mistake.* Current
confidence: Low-Medium, from a real but tiny 4-vs-4 holdout (68% vs. 48%
clean-game rate).

**Cost if wrong:** Low — cheap to scale, cheap to abandon if the effect
doesn't replicate at a larger N. This is exactly why it's Experiment #1
and Root-Cause Coaching (Very High cost if wrong) is #2.

---

## 0. Mechanism, unchanged

Nothing new is being built. `services/focus_engine.py`'s `reminder_enabled`
field already implements a real randomized holdout: `True` = treatment
(gets the in-game "before you move — anything hanging? any threats?"
reminder), `False` = control (measured identically, never reminded).
`services/focus_measurement.py`'s `measure_user()`/`heartbeat()` already
compute `games_with_focus`, `clean_games`, and `targeted_mistakes` per
user, live, on every analyzed game. This experiment scales who's
enrolled — it does not touch the mechanism itself.

## 1. Eligibility — the real decision, surfaced honestly

Checked directly against production before writing this: **only 8 of the
62 currently-focused users actually carry `habit == "threat_scan"` (the
universal habit this experiment measures) — the exact 4-vs-4 already
running.** The other 54 have a real, active focus assignment, but it's a
*personalized* weakness (whatever their own games surfaced), not the
universal habit.

This means "expand to the eligible population" has two genuinely
different meanings, and picking the wrong one either produces a
much smaller experiment than intended or silently overrides 54 real
users' current coaching without them being told anything changed:

- **Option A — reassign the 54.** Replace their current personalized
  focus with the universal `threat_scan` habit, randomly split into
  treatment/control. This is what the original Universal Habit Coach
  scope actually specifies (*"set every focused user's focus to the
  fixed universal habit"*) and produces the statistically meaningful N
  this experiment needs. Real cost: for 90 days, these 54 users stop
  being coached on their own surfaced weakness and start being coached
  on threat-scanning instead, whether or not that's their actual
  biggest leak.
- **Option B — grow only from new assignments.** Only newly-onboarded
  users (or users about to get their first focus assigned) get enrolled
  in the universal-habit holdout; the 54 already on a personalized focus
  keep it. Gentler, no disruption to existing users, but the eligible
  pool grows slowly — at recent signup rates, reaching a statistically
  useful N could take months, defeating the point of picking this as
  the fast, cheap Experiment #1.

**This document does not pick one.** That's a product call, not an
engineering one, and it's the single most consequential fact this
pre-registration surfaced that wasn't visible before checking. Recommend
Option A given the explicit 90-day window and Low cost-if-wrong, but
flagging rather than deciding unilaterally.

## 2. Primary outcome

**Targeted clean-game rate**: `clean_games / games_with_focus`, per
user, exactly as already computed by `focus_measurement.measure_user()`
— no new metric invented.

## 3. Baseline and outcome periods

- **Baseline window**: the 10 analyzed games immediately *before*
  `assigned_at` (or first-ever games for brand-new users with no prior
  history — flagged as a real asymmetry, see §6).
- **Outcome window**: the 10 analyzed games immediately *after*
  `assigned_at`, measured **relative to each user's own `assigned_at`,
  never a shared calendar cutoff** — the staggered-entry fix already
  agreed. A user assigned this week and a user assigned in week 6 are
  each compared to their own 10-before/10-after, not pooled by date.

## 4. Eligibility criteria

- At least 10 analyzed games before `assigned_at` (excluded otherwise —
  no real baseline to compare against).
- At least 10 analyzed games after `assigned_at` by analysis time (a
  user with only 4 post-assignment games isn't ready to analyze yet —
  wait, don't force it).
- Real games only — `core_habit.is_real_game()`'s existing filter
  (already excludes abandoned coach-play stubs).

## 5. Exclusion rules

- Internal/admin accounts (`role` in `admin`, `super_admin`) — excluded
  regardless of focus status.
- A user manually changing their own focus mid-experiment (if that's
  possible via any UI) exits the analysis at the point of change — their
  partial data isn't discarded, but nothing after the change counts
  toward this experiment's outcome window.

## 6. Analysis method

**Intention-to-treat**: every user assigned to treatment counts as
treatment for the full outcome window, whether or not the reminder
actually fired for them on every eligible move (e.g. a rendering
failure, a session that ended early). This is the honest, conservative
choice — per-protocol analysis (only counting users who *actually*
received every reminder) would inflate the apparent effect by dropping
exactly the cases where the intervention didn't reach the player.

## 7. What result would change confidence — decided before seeing data

- **Increases confidence** (row moves toward Medium-High): treatment
  arm's mean clean-game-rate improvement (outcome vs. baseline) exceeds
  control arm's by a real margin, consistent in direction with the
  existing 8-user data, on a sample large enough that the gap isn't
  plausibly noise (rough gut-check: an effect size similar to the
  existing 20-point gap, on 20+ users per arm, not 4).
- **Reduces confidence** (row moves toward Low): treatment and control
  arms show statistically indistinguishable improvement, or control
  outperforms treatment.
- **Inconclusive** (confidence unchanged, more data needed): wide
  variance, small effect in the right direction but not clearly beyond
  noise, or a large chunk of either arm fails the eligibility bar in §4
  and the usable N ends up too small to say anything.

## 8. Threats to Validity

Required per the ledger's standing rule — a real skeptic, in writing,
before data comes in:

- **Regression to the mean.** A user whose baseline window happened to
  be an unusually bad stretch will show "improvement" in the outcome
  window regardless of the reminder. Mitigated by having both a
  treatment and control arm — both are equally exposed to this, so a
  *differential* improvement (treatment beating control, not just both
  improving) is the real signal, not either arm's raw improvement alone.
- **Non-random confound in who reaches `threat_scan` focus.** If Option A
  (§1) is chosen, the 54 users being reassigned already have an existing
  personalized focus — some may be actively engaged with and responding
  well to that focus already. Randomizing *which* of them get the
  reminder controls for this only if reassignment itself is applied
  uniformly, not selectively.
- **Reminder fatigue.** If the same reminder text repeats identically
  across many games, its effect may decay over the outcome window
  rather than stay constant — the ledger already flags "reminder cards
  lose effectiveness after N repetitions" as a real open question this
  experiment could accidentally speak to, even though it isn't the
  primary outcome.
- **Baseline asymmetry for brand-new users** (§3): a user with no
  pre-assignment history has no real baseline, only a first-10-games
  proxy — noisier than an established player's baseline, and could bias
  the pooled result if new users are disproportionately treatment or
  control.
- **The existing 8-user result may not generalize.** The current 68%
  vs. 48% gap came from whichever 8 users happened to be assigned first
  — if that assignment wasn't truly random (worth confirming how the
  original 4-vs-4 was chosen), the promising signal itself could be a
  selection artifact this larger run would correct.

## 9. What ships after this

If confidence rises, this becomes the first real causal-intervention
data point feeding the Evidence Board's decision column for Universal
Habit Coach. **Whether Experiment #2 (Root-Cause vs. Move-Specific
coaching) launches regardless of this result, or waits on it, was
flagged as an open decision earlier and has not actually been answered
yet** — noting that plainly here rather than assuming an answer, since
this is exactly the kind of gap this discipline exists to catch before
it becomes an improvised call three weeks from now.

# The ChessGuru Research Ledger

**What this is:** a living record of product beliefs, separated honestly
into what we know, what we believe, and what we're still trying to
discover. Not for investors. For us — so no coaching philosophy becomes
permanent because it "sounds right." Every belief here earns its
confidence from evidence, and loses it the same way.

**How this works, per `docs/chessguru_coaching_model.md` §9.1:** the row
is the claim, not the intervention that tested it. When an intervention
changes (a new prompt, a new rule version), the row does not reset — it
updates. Confidence moves up on confirming evidence, down on
disconfirming evidence, and a claim with no real evidence stays at Low
no matter how design-obvious it feels.

**Cadence:** reviewed monthly at the Friday research review. Every row
needs a real "next experiment," not just a hope one exists. A row that's
sat at the same confidence for 3+ reviews with no new evidence is a
flag, not a stable fact.

**Mean Time to Belief Revision (MTBR) — an internal question, not a
dashboard KPI, added 2026-08-05, definition corrected same day.** Not
"time since evidence first appeared" — that would reward flipping on
the first noisy data point, exactly the regression-to-the-mean failure
mode this ledger already exists to catch. The precise definition:
**time from the evidence bar actually being met (sample size, Threats
to Validity, the Exit Criteria's own minimums) to the organization
actually changing what it does.** This preserves the distinction
between waiting responsibly for enough evidence and ignoring evidence
once the bar has already been cleared — those are different behaviors,
and only the second one should count against you. A short MTBR measured
this way is a real signal; a short gap measured from "evidence first
appeared" is not — it's indistinguishable from thrashing.

**One experiment at a time.** ChessGuru runs exactly one active
product-learning experiment at any given time, unless two are proven
orthogonal (different users, different mechanisms, genuinely
non-interacting). Decided 2026-08-04, after nearly running the Habit
Coach holdout and Root-Cause Coaching test concurrently on a population
where only 16 users have 200+ games. With that little data, an
overlapping second experiment doesn't add a second data point — it
poisons the first one, since neither outcome can be attributed to
either intervention. This is standing policy, not a one-time call.

**No user-facing longitudinal feature may be enabled for users
participating in an active coaching experiment, unless the experiment
explicitly includes that feature as a controlled variable.** Added
2026-08-05, not hypothetically — checked and found real: `user_614cc832fc89`
(560 analyzed games) is simultaneously eligible for the Longitudinal
Evidence Pilot (`docs/rfc_longitudinal_evidence_pilot.md`) and enrolled
in Experiment #1's Cohort A (the Habit Coach reminder holdout). Shipping
a longitudinal feature to that user while the holdout is active makes
any behavior change unattributable to either intervention — the same
contamination the one-experiment-at-a-time policy below exists to
prevent, just arriving through a different door (a shipped feature
rather than a second experiment). Every new longitudinal or coaching-
narrative feature must check its eligible population against every
currently-running experiment's cohorts before rollout, not assume
"different team, different feature" means "safe to run alongside."

**Threats to Validity, required for every experiment, no exceptions.**
No experiment starts until its analysis document exists, and no analysis
document is complete without this section, answered before data comes
in: What could fool us? What confounds exist? What assumptions are we
making? How could this result be wrong? A good experiment deserves its
own skeptic — this is that skeptic, on paper, in advance.

**Exit Criteria, required for every experiment, no exceptions.** Not
just what success looks like — what failure and "inconclusive" look
like too, and what happens next in each case, decided before data comes
in. The "next action" for an inconclusive result matters most: without
one written down in advance, an inconclusive result quietly becomes a
launch decision after the fact, which is exactly the failure mode this
rule exists to prevent. See
`docs/experiment_01_habit_coach_scaleup_preregistration.md` §9 for the
template this follows.

**Monthly ritual, separate from the weekly research review: "What did
we stop believing?"** Not what did we learn — what belief actually
died this month. Learning is easy to claim; a killed belief is the real
signal that the ledger is doing its job rather than just accumulating
rows that never move.

**Cost of being wrong.** A belief's confidence alone doesn't say how
carefully to treat it. A Medium-confidence belief that's cheap to be
wrong about can ship on that confidence. A Medium-confidence belief that
would distort the whole curriculum if wrong needs far more scrutiny
before anything is built on top of it — same confidence, very different
risk.

---

## Active beliefs

| Belief | Confidence | Evidence | Counter-evidence | Cost if wrong | Next experiment |
|---|---|---|---|---|---|
| **Players compound mistakes after a blunder, even in positions that are still fully playable** (the tilt/collapse effect — `chessguru_coaching_model.md` §2.1) | **Medium-High** | Controlled measurement (confound-checked against "position was just objectively harder") across 3 high-volume users, 2026-08-04: a consistent 4-6x cp_loss elevation on the move immediately after a self-inflicted mistake, isolated to positions that hadn't already been decided by the mistake itself. | Not yet replicated on a wider sample; the effect size hasn't been checked against player rating or time control. | Medium — feeds coaching timing, not the whole curriculum | Extend the same controlled measurement to all 16 users with 200+ games; check whether effect size correlates with rating or game speed. |
| **The in-game habit reminder (Universal Habit Coach) causally reduces the targeted mistake** | **Low-Medium** | A real, live randomized holdout: 4 users receiving the reminder vs. 4 held-out controls, 68% vs. 48% average clean-game rate. | N=4 per arm — no adjustment for each user's baseline skill, high variance risk, not remotely enough to call proven. | Low — cheap to scale, cheap to abandon if it doesn't replicate | Scale the existing holdout (mechanism already built, `focus.reminder_enabled`) from 8 assigned users to the full 62 focused users. Near-zero new engineering cost. |
| **Root-cause coaching (pointing back to an earlier move: "the real fix was move 6") teaches more durably than move-specific coaching** | **Low-Medium** | A real, deterministic mechanism exists and fires in production (`caption_pipeline.py`'s turning-point callback — confirmed real examples: *"This spot got hard a few moves ago, around move 48... the real fix is earlier"*). Reads as a genuine differentiator against a pure per-move report. | Zero outcome data. Nobody has measured whether a player who gets a root-cause caption actually retains the lesson longer than one who gets a move-specific one. | **Very High** — if true, it should reshape captions, review, coach, and puzzles; if false and adopted anyway, that's a lot of surface area rebuilt on nothing | A/B test: for a matched set of players hitting the same mistake type, randomly show root-cause vs. move-specific framing, track whether the *same* mistake recurs in the next 10 games. |
| **A 1200's core deficit is a missing automatic safety-check reflex, not shallow calculation** | **Medium** | Three converging signals (2026-08-04): `piece_safety` dominates the mistake distribution by a wide margin; `calculation_depth` is one of three categories the product has given up detecting reliably (under 50% accuracy); real captions independently describe the failure the same way, unprompted ("your other pieces haven't joined the fight"). | Convergent, not causal — all three signals could share a common confound (e.g. the classifier itself is simply better at detecting piece_safety than calculation errors, which would inflate the former's apparent dominance without it being true). | **Very High** — this is the load-bearing claim behind §2.1 of the constitution and the entire curriculum-priority argument; if wrong, the product is drilling the wrong bottleneck | Have a human reviewer blind-code a random sample of "mistake" moves for the *true* underlying cause (rushed vs. plan-tunnel-vision vs. genuinely didn't calculate deep enough), compare against the classifier's own labels. |
| **Socratic questioning ("what did you see here?") produces better learning than direct statement, for players 1000+** | **Low** | Design rationale only — the rating gate is real and live in code, but no outcome data exists comparing the two. This is currently a belief encoded as a feature, not a tested claim. | None collected either way. | Medium — affects voice for a large share of users, but reversible per-message, not structural | Randomized: for matched 1000+ players hitting the same mistake type, alternate Socratic vs. direct delivery, measure recurrence rate of that specific mistake over the next N games. |
| **Generic, unspecific praise reduces coaching trust/effectiveness** | **Low** | Stated as design conviction in the voice rules (`coach_voice_prompt.py`, `memory/project_coach_voice.md` — praise without a stated reason is explicitly called "patronizing"). No player-facing test of this claim exists. | None collected. | Low — a voice-rule tweak, not structural | Genuinely hard to test cleanly without risking real user trust during the trial — flagging as a belief worth holding but not yet worth actively disproving with live users. |
| **The "STATE, never ASK" conductor law is correct for live play but was applied too broadly, overriding the rating/repetition gate that should govern it** (`chessguru_coaching_model.md` §3.1) | **Medium** | The rating-gated ask/state split in `realtime_coaching_feedback.py` was independently built and is internally coherent; the conductor's blanket override wasn't a deliberate decision to supersede it — no doc argues for the override on its own merits. | None found supporting the blanket override as intentional rather than incidental. | Medium — affects every live PWC message, but a config-level fix, not a rebuild | Not really an experiment — a design decision to make. Flagged here because "we assumed this was decided when it wasn't" is itself worth tracking. |
| **Longitudinal coaching insights (comparing time windows ≥60 days apart) can be computed from data ChessGuru already has, and can be made actionable** (`docs/rfc_longitudinal_evidence_pilot.md`) | **Low** | `thinking_scores` has 12,751 real per-game, timestamped, per-concept records — a genuinely strong raw ingredient. No aggregation or comparison code exists yet, so the claim is entirely untested, not just unconfirmed. | None yet — this is Untested, not Low-confidence-from-mixed-evidence; the RFC's whole purpose is to produce the first evidence either way. | Low-Medium — a bounded 13-user pilot, not a broad rollout; contained by design (§3/§7 of the RFC) | The RFC's own Phase 0 (build the aggregation layer) + Phase 1 (produce one insight per pilot user, graded against the RFC's §6 acceptance criteria). Approved 2026-08-06 as an R&D pilot, not a product commitment. |

## Known, not belief (structural facts, included for contrast)

These aren't claims needing confidence — they're verified facts as of
2026-08-04, kept here so the table above doesn't get confused with
things that are simply true:

- `meta_patterns.py`'s 25 composition rules are real, well-built, and
  currently unreachable from any live product surface.
- Zero live LLM calls occur anywhere in the current coaching hot path —
  a deliberate 2026-05-27 decision, not a gap.
- Only 16 users in the entire database have 200+ analyzed games — any
  claim's evidence base should be read against this ceiling.
- A real, reproducible caption bug ("X is fine — you're still winning"
  attached to a flagged mistake) occurs at least 34 times across 15+
  users — a known defect, not a hypothesis.
- **Measured, 2026-08-05, n=140 real captions across 49 users/76 games**:
  35% explain what happened, 50.7% explain why, 12.9% teach a
  transferable principle (from a narrow, ~dozen-line fixed bank, not
  freshly composed), **0% give any next-game/cross-game action framing.**
  Not a hypothesis anymore — the true, confirmed gap for the next Game
  Review design effort.

## The recall metric (added 2026-08-05, Session 3b — Game Review)

Game Review shouldn't optimize for information delivered — it should
optimize for information retained. Standing metric, not a one-off
survey: one hour after finishing a review, ask *"Without opening
ChessGuru, what is the one lesson you remember from your last review?"*
A real answer (even paraphrased) is success. "I don't remember" or a
move number instead of a lesson is the failure mode this exists to
catch — the same shape as the constitution's own §2 definition of
improvement, applied to a single review instead of a whole game.

---

*Next review: add a row before deciding, not after. If a product
decision is being made and there's no row for the belief behind it,
that's the signal to write one first.*

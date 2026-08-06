# The ChessGuru Decision Log

**What this is, and how it differs from the other two governance docs**:
the Research Ledger tracks belief confidence over time. The Evidence
Board tracks system status (built/live/measured/decision). Neither
captures *why a specific call was made, with what was actually known at
the time.* Two years from now, "why did we do this" should be
answerable by reading a row here, not by reconstructing it from memory
or a chat log.

**Format, one entry per major decision:**

```
Date:
Decision:
Why:
Evidence available then:
Alternatives rejected:
Who decided:
Expected outcome:
When we'll revisit:
```

**Scope note**: this log starts now, from this governance cycle
forward. It does not attempt to backfill every decision in the
project's history (e.g., the 2026-05-27 "no LLM in coaching" call
predates this log and is referenced elsewhere, not re-entered here).
Older decisions can be added retroactively if they'd genuinely inform a
future call — that's a judgment call each time, not a rule to backfill
everything.

---

### 2026-08-05 — Freeze coaching-quality engineering work

**Decision:** Stop spending engineering time on caption/coaching-pipeline
quality for launch. Rolling QA only.

**Why:** The dimension is no longer the limiting factor on launch
readiness — activation is.

**Evidence available then:** 120-game re-render (7,778 moves): 0%
silent moves, 100% of user blunders captioned, 0 render failures, 0
surface violations. `cognitive_gap` misclassification fixed
(33.6%→0.8%). Very High confidence, per the Launch Readiness Report.

**Alternatives rejected:** Continue caption refinement — rejected
specifically because Activation (3.0) is now the dimension actually
holding growth back, not Coaching Quality (8.0).

**Who decided:** Mohit, based on the Launch Readiness Report.

**Expected outcome:** Engineering effort redirects to Activation/Trust
without a corresponding drop in coaching quality, since the pipeline is
verified to already be strong.

**When we'll revisit:** If the per-caption depth gap (0% next-game
action framing, measured 2026-08-05) turns out to matter once actually
tested — not before.

---

### 2026-08-05 — Reject full-population expansion of Experiment #1; adopt 3-cohort gradual rollout

**Decision:** Scale the Universal Habit Coach holdout via Cohort B (the
next 12-15 users reaching first-focus-assignment, randomized) — not by
reassigning all 62 currently-focused users to the universal habit.

**Why:** Only 8 of 62 focused users actually carried the universal
`threat_scan` habit; the other 54 have real, active personalized focus
assignments. Reassigning all 54 would simultaneously change coaching
focus, priority, and intervention frequency for every one of them — any
outcome would be unattributable to the reminder specifically.

**Evidence available then:** Direct production query confirming the
8-vs-54 split; the existing 4-vs-4 holdout's 68%/48% clean-rate gap
(Low-Medium confidence, N too small to trust alone).

**Alternatives rejected:** Full reassignment of all 62 (faster N, fully
confounded). Doing nothing beyond the original 8 (clean, but too slow
to produce a useful result this quarter).

**Who decided:** Mohit.

**Expected outcome:** A real, attributable causal read on the reminder's
effect within a defined outcome window, at the cost of a slower ramp.

**When we'll revisit:** When Experiment #1 reaches Success, Failure, or
Inconclusive per its pre-registered Exit Criteria.

---

### 2026-08-05 — Institute one-experiment-at-a-time as standing policy

**Decision:** ChessGuru runs exactly one active product-learning
experiment at a time, unless two are proven orthogonal.

**Why:** Nearly ran the Habit Coach holdout and Root-Cause-vs-Move-
Specific coaching concurrently before catching that both would compete
for outcome-window data from the same tiny population.

**Evidence available then:** Only 16 users in the entire database have
200+ analyzed games — the ceiling any experiment's real evidence base
has to work within.

**Alternatives rejected:** Running both experiments in parallel to move
faster — rejected because neither result would be attributable to its
own intervention.

**Who decided:** Mohit.

**Expected outcome:** Slower experiment throughput, but every result
that does land is actually attributable to its own cause.

**When we'll revisit:** When the qualifying population (200+ game
users) grows large enough that concurrent experiments wouldn't
meaningfully share outcome-window data — no specific number set yet;
flagging that as itself an open decision, not deferring it silently.

---

### 2026-08-05 — Do not trim `dashboard-v2`'s unused fields yet

**Decision:** Keep computing all 11 `dashboard-v2` fields (8 currently
unread by the frontend) until each has either a named target surface
within 90 days or an explicit Retire call.

**Why:** Deleting unused computation without evidence risks cutting
something that was quietly about to matter (`chess_dna` may be the real
answer to "who are you becoming," a question raised independently in
the same session) — ownership-before-deletion applied to code the same
way it's applied to product beliefs.

**Evidence available then:** 8 of 11 fields computed, 3 read. No
field's future home was yet decided with real evidence.

**Alternatives rejected:** Trim immediately for engineering cleanliness.

**Who decided:** Mohit.

**Expected outcome:** Each field gets a real Keep/Retire decision,
several already recommended on the Evidence Board (`accuracy`→Progress,
`training_ready`→Training, `one_thing_to_fix`→likely retire as
superseded by the Coach Conversation's `one_action`).

**When we'll revisit:** Once the ownership table's recommendations are
either confirmed or overridden — not yet scheduled.

---

### 2026-08-05 — Gate the gold-caption tester tool to reviewer/admin, merge immediately

**Decision:** `GET /decryption/gold/{game_id}` and `POST
/decryption/gold/prefer` now require reviewer/admin role, not just an
authenticated session.

**Why:** Confirmed live, not hypothetical — one real, non-admin user's
game already had gold-tester data attached, meaning internal QA tooling
could have reached a real customer. Data absence (most games lack gold
data) had been standing in for access control.

**Evidence available then:** `gold_tester_captions` had 194 real docs
across 4 games; one game belonged to a real user with no admin role.

**Alternatives rejected:** None — treated as a defect requiring no
debate, explicitly distinct from the architecture-level decisions
above.

**Who decided:** Mohit ("merge immediately, no discussion").

**Expected outcome:** Zero real users can see internal tester tooling
regardless of whether their specific game happens to be gold-baked.

**When we'll revisit:** Not a reversible bet — closed. Worth a
follow-up check for the same "data absence as authorization" pattern
elsewhere in the codebase, not yet done.

---

### 2026-08-05 — Split "Product Quality" into System Quality / Experience Quality / Launch Readiness

**Decision:** Report three separate axes in the Launch Readiness Report
instead of one blended score. Experience Quality set at 4.0, not the
6.5 first proposed.

**Why:** A single number was averaging "is the engine good" with "does
a stranger get the experience," which the report's own evidence
directly contradicts doing (Coaching Quality 8.0 vs. Trust/Activation/
First Session at 3.0/3.0/3.5). A 6.5 would have softened exactly the
severity the report exists to name.

**Evidence available then:** The dimension-by-dimension scorecard
itself — no new data, a re-reading of data already gathered.

**Alternatives rejected:** Keep the single 7.5. Average all five
experience-adjacent dimensions evenly to 6.5.

**Who decided:** Joint — Mohit proposed splitting the axis; I pushed
back on the specific 6.5 number; Mohit signed off on 4.0 after seeing
the reasoning.

**Expected outcome:** P0 in the priority list becomes unambiguous
(Activation) instead of diluted by an averaged score that reads as
"pretty good, needs polish."

**When we'll revisit:** Next full report cycle, once Activation work
has shipped and Experience Quality can be re-measured against a new
baseline.

---

### 2026-08-05 — Resolve the ask-vs-state contradiction in coaching philosophy

**Decision:** Ask (Socratic) belongs in review contexts, for 1000+-rated
players, on genuinely open cases. State directly in live play, on
3+-repeated patterns, and for sub-1000 players. The live Conductor's
blanket "STATE, never ASK" should defer to the existing rating/
repetition gate rather than override it unconditionally.

**Why:** The coaching constitution said "prefers questions"; the live
Conductor law said "state, never ask" — two real, shipped systems
disagreeing, unnoticed until this cycle's audit.

**Evidence available then:** `realtime_coaching_feedback.py`'s rating
gate was already correctly built; no document anywhere argued for the
Conductor's blanket override on its own merits — it reads as
incidental, not deliberate.

**Alternatives rejected:** Delete one law and keep the other without
reconciling why. Leave the contradiction undocumented (the state before
this cycle).

**Who decided:** Documented into the constitution (§3.1) as a
recommendation — **flagging honestly that this is a case where the
resolution was written by Claude and is pending Mohit's explicit
review, not yet a fully joint decision the way the others above are.**
The code itself (the Conductor's actual override behavior) has not been
changed yet either — this is a documented resolution, not an
implemented one.

**Expected outcome:** Once implemented, the live Conductor path respects
the same gate the review path already does correctly.

**When we'll revisit:** When Mohit reviews §3.1 directly, and again
once the Conductor's code is actually changed to match.

---

---

### 2026-08-06 — Approve the Longitudinal Evidence Pilot RFC as an R&D pilot

**Decision:** Approve `docs/rfc_longitudinal_evidence_pilot.md` — not as
a commitment to ship Monthly MRI, but as authorization to write Phase
0's scope doc (the aggregation layer) and run a bounded pilot. Condition:
remains an R&D pilot until it proves it should become a product
capability.

**Why:** The RFC reframed "existing users deserve more engineering" from
a retention argument (weak — only 5-14 users have enough history to
matter today) into an R&D argument (strong — this generates evidence
about whether longitudinal coaching is buildable at all, which the
company doesn't currently have).

**Evidence available then:** `thinking_scores` (12,751 real per-game
docs, correcting CLAUDE.md's stale 31); zero month-over-month
aggregation code anywhere in the backend; the eligible population
sharply tiered (1 user at 1300+ games, 5 at 700+, 14 at 300+); one
confirmed experiment-contamination case (`user_614cc832fc89`, in both
the pilot's eligible pool and Experiment #1's Cohort A).

**Alternatives rejected:** Treating this as a feature spec ("build
Monthly MRI") rather than a research question — rejected because it
would have skipped the actual open question (can this be demonstrated
at all) in favor of assuming the answer. Expanding scope to all
"existing users" — rejected given the real population numbers above.

**Who decided:** Mohit, reviewing the RFC as an approver — added
Opportunity Cost, Kill Criteria, and Graduation Criteria sections before
approving, plus the top-level Research Question framing.

**Expected outcome:** Phase 0's scope doc gets written next
(`docs/longitudinal_evidence_pilot_scope.md`), not code directly. The
pilot either produces at least one insight passing the ≥60-day/
can't-derive-from-30-days acceptance test (§6 of the RFC) — evidence the
capability is real — or it doesn't, in which case it's logged to
`docs/chessguru_graveyard.md`, not quietly retried.

**When we'll revisit:** When the pilot reaches a result against its own
Kill Criteria (§7) or Graduation Criteria (§8) — whichever comes first.

**Update, same day — deferred pending capacity, not reopened:**
Reason for deferment: *deferred because higher-priority evidence
currently blocks more product decisions than this pilot does. Approval
does not imply immediate execution.* Status changed to "Approved —
Waiting for Capacity" rather than "Active." Applied the Research
Priority by Decision Dependency test (new standing policy, Research
Ledger): the Activation watch, Cohort B, and Trust Sprint work all block
decisions covering essentially the whole next quarter (onboarding,
diagnostic, first session, trust, activation); this pilot blocks only
Monthly MRI / longitudinal-coaching decisions, which aren't on the
launch-critical path. Trigger to resume drafting `docs/longitudinal_evidence_pilot_scope.md`
is explicit and three-part (RFC §Status) — this is not an indefinite
shelving, and no one should feel pressure to progress it before the
trigger fires.

---

---

### 2026-08-06 — Activate Experiment #1 Cohort B enrollment

**Decision:** Deploy the Cohort B enrollment mechanism to the local
backend container (real production data, restarted to load it) so it
actually starts randomizing real users. Not treated as automatic once
the code was written — flagged explicitly as a distinct decision from
implementation, given upfront to Mohit before proceeding.

**Why:** Unlike the Longitudinal Evidence Pilot's deferred evidence
(which doesn't decay while waiting), Cohort B's enrollment opportunity
does — it only fires at a user's genuine first-ever focus assignment;
every real user who reaches that moment while inactive is permanently
missed, and activating costs no ongoing engineering time, so it doesn't
compete with Priority 1/3 for capacity under the Research Priority by
Decision Dependency policy.

**Evidence available then:** Code syntax-checked and logic-reviewed;
`l4_pilot_monitor.py` extended to report both cohorts; mechanism reuses
the existing `db.l4_pilot` schema Cohort A already uses, no new data
model introduced.

**Alternatives rejected:** Leaving it implemented-but-inactive until
Priority 1/3 resolve, by direct analogy to the RFC deferral — rejected
specifically because the analogy doesn't hold: the RFC's evidence
doesn't decay with time, Cohort B's enrollment opportunity does.

**Who decided:** Mohit, via explicit confirmation after the
irreversibility and the decay-asymmetry argument were raised directly
(not inferred from a general "do what you recommend").

**Expected outcome:** Cohort B accumulates toward its 12-15 target as
real users naturally reach first-focus-assignment; `l4_pilot_monitor.py`
is the way to check progress.

**When we'll revisit:** When Experiment #1 reaches Success, Failure, or
Inconclusive per its pre-registered Exit Criteria (§9), same trigger as
already defined — this decision doesn't add a new one.

---

*Add a new entry above whenever a major decision is made — not after
the fact, when someone's already forgotten the alternatives that were
actually on the table.*

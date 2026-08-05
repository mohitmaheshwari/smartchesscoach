# The ChessGuru Knowledge Base

**What this is:** not documentation. Knowledge — what ChessGuru has
actually learned about how people improve at chess, independent of any
one feature or intervention. If an engineer in 2028 asks *"why does
ChessGuru teach this way,"* this is what they should read, not five
scattered docs.

**How this relates to the Research Ledger**: the Ledger is the working
set — live, open beliefs still being tested, with a next experiment
attached. This is what graduates out of it — an observation stated as
settled fact once it's confirmed (or, for a few entries below, because
it was already self-evidently true and never needed to be an open
question). A "Testing" or "Unknown" entry here still points back to its
live Ledger row; a "Verified" entry doesn't need one anymore.

**The metric this document exists to grow**: not users, not model
quality. How many things does ChessGuru know about learning chess that
nobody else has proven. Every verified observation is an asset. Every
disproven belief is an asset. Every failed experiment is an asset —
competitors can copy a feature; they cannot copy years of accumulated
findings.

---

### Observation #001 — Players remember ideas and geometry, not notation

**Status:** Verified

**Evidence:** Never formally an open experiment — a design constraint
recognized directly from user feedback and held as non-negotiable since.
The Home Mirror describes "one move in the middlegame dropped material,"
never "Rf1 on move 16" — a deliberate 2026-06-01 decision, explicit in
the code: *"a 1200 doesn't anchor memory on 'Rf1 on move 16' — that
belongs on the game review page where the board is right there."*

**Used in:** Home (the Mirror), caption voice rules across the whole
product.

---

### Observation #002 — The dominant failure mode is a fragile safety-check, not shallow calculation

**Status:** Verified, Medium confidence

**Evidence:** Three converging signals: `piece_safety` dominates the
real mistake distribution by a wide margin; `calculation_depth` is one
of three categories the classifier has given up detecting reliably
(under 50% accuracy); a controlled, confound-checked measurement found a
real 4-6x quality collapse on the move immediately after a player's own
mistake, even in positions that were still fully playable.

**Used in:** The constitution's Theory of Improvement (§2.1); the Home
Coach Conversation's tilt overlay (`_get_tilt_overlay()`), already
appending this theory onto the base explanation for real users.

---

### Observation #003 — Root-cause explanation may retain better than move-specific explanation

**Status:** Testing, Low-Medium confidence — [Research Ledger row]

**Evidence so far:** A real, already-shipped mechanism (`caption_pipeline.py`'s
turning-point callback: *"this spot got hard a few moves ago, around
move 48... the real fix is earlier"*) reads as a genuine differentiator.
Zero outcome data yet on whether it's actually remembered longer.

**Experiment:** Queued as Experiment #2, blocked behind Experiment #1 per
the one-experiment-at-a-time policy.

---

### Observation #004 — An in-game habit reminder may causally reduce the targeted mistake

**Status:** Testing, Low-Medium confidence — [Research Ledger row]

**Evidence so far:** A real 4-vs-4 randomized holdout: 68% vs. 48%
average clean-game rate. Promising, not remotely enough N to trust
alone.

**Experiment:** Running now — Cohort B expansion (12-15 new
first-focus-assignment users, randomized), pre-registered.

---

### Observation #005 — ChessGuru explains what and why well; it does not yet teach a standing habit

**Status:** Verified (measured, not inferred)

**Evidence:** n=140 real captions, 49 users, 76 games, hand-classified:
35% explain what happened, 50.7% explain why, 12.9% teach a
transferable principle (from a narrow, ~dozen-line fixed bank, not
freshly composed), **0% give any next-game or cross-game action
framing.** Not a hypothesis — a confirmed, empty bucket.

**Used in:** The starting point for the upcoming Move Coaching deep
review — the gap is named and measured before any redesign begins.

---

### Observation #006 — One uncanny-specific truth may build more trust than five generic ones

**Status:** Unknown

**Evidence so far:** None collected. The Launch Readiness Report's own
Trust section states this plainly: *"Time-to-Trust is correctly not yet
a named metric — we don't know what creates trust."* Named as a belief
here specifically because it's the kind of thing worth stating even
before evidence exists, so it doesn't get silently assumed true later.

**Experiment:** The "Trust Moment" work in the Launch Readiness
Report's Success Criteria — not yet run.

---

### Observation #007 — Coaching confidence should scale with games watched, not calendar time

**Status:** Verified

**Evidence:** A real production pull (2026-07-30) found ~40 of 62 active
accounts shared a `created_at` clustered at almost exactly 100-102 days
regardless of real activity (1 to 1,281 games analyzed) — a bulk-backfill
artifact, not organic signup timing. The relationship-voice ladder
(`home_coach_conversation.py`) is keyed to `games_analyzed` instead, and
the four real stage-opener strings were confirmed live against real
accounts, not just read from source.

**Used in:** Home's coach-conversation voice, all users, live today.

---

*Promote a Ledger row here once it's confirmed (or disproven — a
disproven belief is still knowledge, log it as Verified-False with the
evidence, don't delete it). Add a new Unknown the moment someone
notices an assumption nobody's actually tested, per Observation #006 —
naming an unknown early is itself valuable, not just resolving one.*

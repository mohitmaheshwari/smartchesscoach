# The ChessGuru Graveyard

**What this is:** failed beliefs, not failed features. A third state,
distinct from the other two governance docs on purpose: the Research
Ledger is the live working set (still deciding); the Knowledge Base is
the current best model (what we believe now); this is what we used to
believe and have since disproven, kept so the same debate never has to
happen twice.

**Why this exists separately, not as a "Verified-False" tag inside the
Knowledge Base:** that document's whole value is being a clean current
snapshot — a new engineer in 2028 should be able to read it start to
finish and know what's true *today*. Mixing in retired beliefs, however
well-labeled, turns that into an archive someone has to filter while
reading. This is where "we already tested that, here's why it failed"
lives instead — so the answer to a re-proposed idea is a link, not a
re-litigation.

**Format:**

```
Belief:
Status: Retired
Why it died:
Evidence:
What replaced it:
Decision affected:
```

---

### Belief #001 — A single gut-read number can represent launch readiness

**Status:** Retired

**Why it died:** An initial 6.5 assessment was itself an unverified
gut-read, not anchored to a specific check. It didn't survive contact
with actual verification work.

**Evidence:** A 120-game caption re-render, a `cognitive_gap` accuracy
backfill, and an Activation Timeline built from real signups all
produced numbers that didn't match the 6.5 — some dimensions (Coaching
Quality) verified meaningfully higher, others (Activation) confirmed
as genuinely severe rather than assumed moderate.

**What replaced it:** A dimension-by-dimension scorecard (12 named
dimensions, each with its own evidence and confidence), first
consolidated into a single "Product Quality: 7.5."

**Decision affected:** The first version of the Launch Readiness
Report.

---

### Belief #002 — A single "Product Quality" score can represent both the engine and the experience

**Status:** Retired

**Why it died:** The report's own evidence directly contradicted the
number it was producing — Coaching Quality at 8.0 (Very High
confidence) sat in the same average as Trust/Activation/First Session
at 3.0/3.0/3.5 (the three actual launch blockers), and the resulting
7.5 read as "pretty good, needs polish" instead of naming the real,
severe front-door problem underneath it.

**Evidence:** The scorecard itself, re-read as two different questions
rather than one — "is the engine good" and "does a stranger get the
experience" move independently and the single number couldn't say so.
An intermediate proposal (Experience Quality = 6.5, an average across
five dimensions) was itself rejected in the same conversation for the
same reason: it re-diluted the three worst, most decision-relevant
scores by averaging in two milder ones.

**What replaced it:** Three separate axes — System Quality (8.0),
Experience Quality (4.0), Launch Readiness (6.0) — each independently
scored and independently confidence-rated.

**Decision affected:** The Launch Readiness Report's entire structure,
and the P0 priority (Activation) that became unambiguous once the
number stopped hiding it.

---

*Add an entry the moment a belief is actually retired — not when it's
merely doubted. A belief still being argued about belongs in the
Ledger; only move it here once something (an experiment, a
re-verification, a direct contradiction in the evidence) actually
killed it.*

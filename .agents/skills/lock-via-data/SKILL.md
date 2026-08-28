---
name: lock-via-data
description: Force data-driven decisions when about to lock a numeric threshold, ranking formula, severity weight, or any pick-from-multiple-candidates architectural choice. Prevents the "pick from gut, get surprised by the histogram" anti-pattern that bit ChessGuru three times in one design session (FEN-cluster thresholds, concept cp_loss filter, ranking formula). Trigger whenever a design decision involves picking between numeric options OR multiple candidate formulas.
---

# Lock Via Data, Not Vibes

Built 2026-06-05 after a design session where intuition was wrong every time it was tested. The PersonalConceptCard scope produced this rule the hard way:

- Proposed threshold "recurrence ≥ 3, median cp_loss ≥ 200" → expected ~70% activation → actual 14%
- Proposed concept filter "median ≥ 150" → would mislabel catastrophic-outlier patterns (DEF_WALK_KING median=134, p75=1000)
- Proposed ranking formula by principle (Formula D) → Mohit refused, demanded bake-off across 4 candidates

Each surprise reset the architecture. This skill prevents that.

## When to invoke

- Before locking ANY threshold (cp_loss cutoff, recurrence floor, accuracy minimum, recency weight)
- Before picking ANY formula from multiple candidates (ranking, scoring, prioritization)
- Before claiming "activation will be X%" or "this filter produces Y entries"
- When the design decision is "which number" or "which formula" rather than "which architecture"
- When Mohit says "let's lock this" and the locking requires numeric choices

Do NOT invoke for:
- Inheriting an already-locked constant from an existing system (e.g. reuse `pattern_decay_service.DECAY_RATE=0.85` — locked elsewhere, reuse is fine)
- Architectural choices that don't reduce to a number (e.g. "should we have one collection or three?" — that's a different skill: `/audit-pre-code`)
- Trivial defaults where the cost of measurement exceeds the cost of being wrong

## Required input

- The decision: what's being locked
- The candidates: 2-4 concrete options with their numeric values or formulas
- The corpus to measure against (typically the production mongo at the time of the decision)

## The 5-step process

### 1. State the decision concretely

Write down what's being locked and what each candidate looks like. Examples:
- "Concept eligibility threshold: A=(r≥3, median≥200) vs B=(r≥5, median≥150) vs C=(r≥5, median≥150 OR p75≥300)"
- "Ranking formula: A=Σ(cp×decay) vs B=recency×median vs C=recency×max(median,p75/2) vs D=recency×log(1+median)"

Vague decisions ("we need some kind of threshold") get rejected — clarify first.

### 2. Identify the discriminating data

What measurement would actually distinguish the candidates? Common forms:
- For thresholds: histogram of the quantity being filtered (activation per threshold, distribution percentiles)
- For formulas: top-N output per formula on the same input, compared side-by-side
- For sources: per-user signal volume per source

If you can't name a measurement that would change the answer, the decision isn't measurable and shouldn't go through this skill.

### 3. Run the measurement

Use `Workflow` or a single mongo query (whichever is cheaper). Read-only. Output a structured report — histogram, percentiles, top-N per candidate, whatever the discriminating measure is.

For threshold decisions: bucket users by threshold combo, show activation %.
For formula decisions: run each formula on 5-10 stratified users, show top-3 outputs side by side.

### 4. Look at the distribution, find the cliff

Pick the threshold AT THE CLIFF (sharp drop-off) not from intuition.
Pick the formula whose outputs feel most like the goal (typically Mohit's "this is exactly me" criterion for coaching surfaces).

If the distribution is flat (no cliff) → that's a finding. Either every threshold is acceptable, or none is — surface this honestly.

### 5. Lock with explicit data citation

The lock writeup must include:
- The chosen value
- The exact data point that justifies it (e.g. "median ≥ 150 OR p75 ≥ 300 picked because combo 6 retained 296 user-concept pairs vs combo 4's 292, while catching 3 catastrophic-tail concepts the median-only filter missed")
- The other candidates and why they lost

A lock without data citation is gut-lock and gets re-opened the next time Mohit asks "why this number?"

## Output format

A short structured note:

```
DECISION LOCKED: {what was decided}

VALUE: {final picked value/formula}

EVIDENCE:
  - {data point 1 that justifies the choice}
  - {data point 2}

REJECTED CANDIDATES:
  - {candidate A}: {why it lost in the data}
  - {candidate B}: {why it lost}

MEASUREMENT METHOD: {what query/workflow produced the evidence}
```

This note goes into the PR / spec doc / commit message so the decision is auditable.

## What NOT to do

- Don't propose a number with "I think this is reasonable" — that's gut, not data.
- Don't run the measurement and then ignore it because the result was inconvenient.
- Don't run a measurement scoped to one user when the decision affects all users.
- Don't pick a candidate without explicitly stating WHY it beat the others.
- Don't skip the measurement because "we'll just A/B test in production" — that's how unmeasured assumptions ship.

## Notes

- Pair with `/audit-pre-code` — `/lock-via-data` produces the numbers; `/audit-pre-code` verifies they're locked before coding starts.
- The 5-step process maps to: state → identify measurement → measure → interpret → lock with citation.
- Mongo intermittency (port 27018 dropping) is the known operational risk for this skill. If mongo is down, the skill should not proceed — surface the blocker, don't fall back to vibes.
- See [[threshold-before-distribution-is-sin]] in memory for the principle this skill operationalizes.

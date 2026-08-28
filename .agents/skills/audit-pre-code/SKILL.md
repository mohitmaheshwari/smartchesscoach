---
name: audit-pre-code
description: Pre-flight checklist invoked BEFORE writing the first line of code on a new feature. Catches the recurring traps from the PersonalConceptCard scope: schema-before-mockup, move-led-narrative, instrument-before-validate, forecasted-bottleneck, deferred-now-quietly-undeferred. Trigger when Mohit says "let's code it" / "start building" / "ship V1" — or when you're about to write a new file in a feature flow.
---

# Audit Before Code

Built 2026-06-05 to enforce the design discipline Mohit has called out repeatedly. Multiple times in one session I caught myself one keystroke away from writing schema/collection/query code before the user-facing surface was even decided. This skill is the stop sign.

## When to invoke

- About to create a new file (`services/foo.py`, `frontend/src/components/Bar.jsx`, etc) for a feature
- Mohit says "start coding" / "ship it" / "build V1"
- Spec discussion is winding down and implementation is about to begin
- New PR / branch being created for a feature

Do NOT invoke for:
- Bug fixes to existing code paths
- Refactors / renames within a feature already shipped
- Test additions
- Documentation / spec writing

## The 6-point checklist

Each item is a hard gate. If any fails, **stop and resolve before continuing.**

### 1. Does a literal UI mockup exist?

The mockup is the contract. Schema, queries, ranking — all downstream of what the user sees. Without a mockup, you're guessing about which fields the schema needs.

- ✅ Pass: there's an ASCII mockup or wireframe with literal narrative text in the spec doc / scope discussion
- ❌ Fail: only schema fields are written down ("we'll need a `cp_loss` field on the card document...")

Anti-pattern: jumping to data model before knowing what the card says. See [[card-is-the-product]].

### 2. Is the headline pattern/geometry, not SAN-move-notation?

For any coaching surface that references past games, the narrative HEADLINE must be the pattern (geometry, tactical idea, named concept). The SAN move is footer evidence at most.

- ✅ Pass: *"You keep getting forked when your knight jumps to the rim. Seen 7 times."*
- ❌ Fail: *"May 22 vs killerknight24 — you played Nxe4 (-380cp)."*

Mohit corrected this 3 times in one session. See [[users-remember-patterns-not-moves]].

### 3. Are all thresholds derived from data, not vibes?

Every numeric value (cp_loss cutoff, recurrence floor, recency weight) must have a data citation. "I think 150 is reasonable" is not a citation.

- ✅ Pass: each threshold has a measurement that justifies it (cite the workflow / query / histogram)
- ❌ Fail: thresholds appear in the spec with no measurement behind them

Use `/lock-via-data` before this gate. See [[threshold-before-distribution-is-sin]].

### 4. Is the success metric behavior-changing, not vanity?

Metrics like "activation %" (does any user see the feature) and "aggregate CTR" can be tautological or vanity. The real metric for a coaching feature is whether it CHANGES BEHAVIOR.

- ✅ Pass: per-source CTR on the action the feature is trying to drive (e.g. "review-game clicks per impression")
- ❌ Fail: "activation rate" as the primary metric; or aggregate metrics that average across the only active source

Earlier in this session I caught the aggregate-CTR-of-single-source tautology. See the metrics_explicitly_dropped section in scope deliverable docs.

### 5. Are deferred items still deferred (no scope creep)?

If the discussion deferred Outcome Tracker, Auto-gen tooling, Priority Engine, etc — they should NOT show up in the V1 code. The audit verifies that deferred items have NOT been silently smuggled back in.

- ✅ Pass: V1 spec items match what's actually about to be coded; deferred items are absent
- ❌ Fail: code is about to be written for a deferred item ("just stub it in"), or a deferred item is on the critical path

Anti-pattern: "while we're here, let's also add..."

### 6. Has Mohit explicitly signed off on the spec?

The audit doesn't replace Mohit. It complements him. The final gate is his explicit "yes, code this."

- ✅ Pass: there's a clear signoff in the conversation history ("lock this and code")
- ❌ Fail: design discussion is still active, or signoff is implicit ("sounds good" — that's not signoff for code)

When in doubt, ask. The cost of asking is one message; the cost of coding the wrong thing is days.

## Output format

If all 6 gates pass:

```
PRE-CODE AUDIT: PASS
Feature: {name}
Spec: {link or summary}
Proceeding to implementation.
```

If any gate fails:

```
PRE-CODE AUDIT: BLOCKED
Failed gates:
  - {gate N}: {what's missing, what to do to unblock}
DO NOT WRITE CODE until resolved.
```

Surface the failure to Mohit. Don't quietly work around it.

## What NOT to do

- Don't run this skill on a feature you're actively shipping if it ALREADY started — too late, you'll just argue with yourself. Run it BEFORE the first file.
- Don't soften the gates ("the mockup is sort of implied by the schema") — that's how the discipline erodes.
- Don't run this for trivial changes (bug fixes, renames) — it's for new features only.
- Don't pretend a gate passed when it didn't. The audit only works if it's honest.

## Notes

- The 6 gates correspond to recurring traps Codex fell into during the 2026-06-04/05 design session.
- Each gate's anti-pattern has a memory entry. The skill is the per-task enforcement of those memory rules.
- Pair with `/lock-via-data` — that skill sets thresholds; this skill verifies they were set before coding.
- When mongo is down (intermittent 27018 issue), gate 3 cannot be verified — surface this as a blocker, don't fall back to gut-locked thresholds.

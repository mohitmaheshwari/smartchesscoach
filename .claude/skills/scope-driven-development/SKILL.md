---
name: scope-driven-development
description: Before coding any new product or feature for ChessGuru, create a scope document in plain English describing what the product WILL BE at the end. No code starts until the scope is on the table and Mohit has signed off. Trigger when Mohit describes a new product/feature, or types "let's build X", "ship Y", or any "start coding" intent. This skill is the parent discipline; /lock-via-data and /audit-pre-code are downstream enforcers.
---

# Scope-Driven Development

Built 2026-06-05 after Mohit caught me trying to skip the discipline repeatedly during the PersonalConceptCard scope discussion. The whole session was him forcing this practice; this skill codifies it.

**The rule, in one sentence:** No code starts until a scope document exists at `docs/<feature_name>_scope.md`, written in plain English, and Mohit has explicitly signed off.

## When to invoke

- Mohit describes a new product, feature, surface, or system
- Mohit types "let's build X" / "ship Y" / "start coding Z"
- Discussion has produced enough design conversation that "what is this thing?" is answerable
- Before any commit that adds a new feature's first file

Do NOT invoke for:
- Bug fixes to existing code
- Refactors / renames within a feature already shipped
- Test additions
- Documentation-only changes
- Trivial config updates (env vars, feature flag toggles for already-built features)

## Required input

- The feature name (used as `docs/<name>_scope.md` filename)
- A rough description from Mohit of what the product should do

## The 7-section template

Every scope document has exactly these 7 sections. Don't add more. Don't skip any.

### 1. What it is

One paragraph. Plain English. No schema. No engineering jargon. The audience is a non-engineer who needs to understand what they're getting.

**Pass:** "PersonalConceptCard shows users a pattern they keep falling for, anchored by recent examples from their own games. The card reads like a coach speaking, not a database report."

**Fail:** "PersonalConceptCard surfaces a top-N ranking of qualifying user_concept_understanding rows filtered by a recurrence-and-cp_loss-disjunction gate."

### 2. What the user sees

Literal mockup. ASCII is fine. Show the actual narrative text — not placeholder lorem ipsum. If the headline matters (it usually does), the headline is in the mockup.

This section is the **product contract.** Backend / schema / queries are all downstream of this.

If the feature has no UI surface (e.g. a behind-the-scenes infra fix), state "no UI change" and describe the user-facing effect instead.

### 3. In scope (V1)

Bullet list. Concrete. Each bullet should be checkable as done/not-done.

**Pass:**
- ConceptPatternSource active with combo-6 eligibility
- One-card-per-family cap enforced
- Variable 0-3 cards per user, never padded
- Per-source CTR metrics tracked

**Fail:**
- "Implement personalization" (too vague — what does done look like?)
- "Best-in-class card UI" (no measurable definition)

### 4. Explicitly out of scope (V1)

Bullet list of what V1 does NOT deliver. This catches scope creep before it starts.

Examples that belong here:
- "PositionPatternSource rendering (it runs in shadow mode but is NOT shown)"
- "TrapPatternSource (disabled until data accumulates)"
- "Theme classifier rules (cards ship without theme labels in V1)"
- "Outcome Tracker (deferred until engagement validates the feature)"
- "Auto-gen tooling for openings (forecasted bottleneck, not observed)"

Every "deferred" item from the design discussion goes here, with the reason.

### 5. Success criteria

How will we know if V1 worked? Must be **behavior-changing**, not vanity.

**Pass:** "Per-source review-game CTR >= 25% on ConceptPatternSource within 2 weeks of launch"

**Fail:** "Users see cards" (activation isn't success)
**Fail:** "Increase engagement" (which engagement? by how much?)

### 6. Open questions

What's not yet decided + how each gets resolved.

Format per question:
- **Question:** (concrete, answerable)
- **Why unresolved:** (data missing? Mohit signoff pending?)
- **Unblocking step:** (run histogram / 30-min meeting / Mohit input)

### 7. Pre-code requirements

What MUST be true before the first line of code is written. Each item is a hard gate.

Examples:
- Mongo on port 27018 is reachable (bake-off can run)
- Ranking formula bake-off has returned a winner
- Frontend route is chosen
- Theme classifier rules table is authored (if theme labels are part of V1)
- Mohit has explicitly signed off on the full scope document

## Steps to run this skill

1. Identify the feature name (use snake_case, e.g. `personal_concept_card`).
2. Confirm the file path: `docs/<feature_name>_scope.md`.
3. Write the document using the 7-section template above.
4. **Surface the document to Mohit for signoff.** Either paste it inline or push it as a PR. Do not assume signoff.
5. Wait for explicit signoff ("locked", "ship it", "yes go").
6. ONLY THEN hand off to `/lock-via-data` (for numeric thresholds) and `/audit-pre-code` (pre-code checklist).

## Output format

The deliverable is the scope document itself, plus a confirmation message:

```
SCOPE DOCUMENT WRITTEN: docs/<feature_name>_scope.md

Sections covered:
  ✅ What it is
  ✅ What the user sees (mockup)
  ✅ In scope (V1)
  ✅ Explicitly out of scope
  ✅ Success criteria
  ✅ Open questions ({N})
  ✅ Pre-code requirements

AWAITING MOHIT SIGNOFF before any code is written.
After signoff, run /lock-via-data on the numeric decisions, then /audit-pre-code before the first file.
```

## What NOT to do

- **Don't skip a section.** Each one catches a real anti-pattern. "Out of scope" prevents creep. "Open questions" forces honesty about what's unresolved.
- **Don't write the scope document in engineer voice.** If a non-engineer can't read it and understand what they're getting, it's wrong.
- **Don't fill in answers for open questions.** Open means open. If you knew the answer, it wouldn't be there.
- **Don't proceed to code on implicit signoff.** "Sounds good" is not signoff. "Looks fine" is not signoff. Explicit "ship it" / "locked" / "go code" is signoff.
- **Don't bypass this skill for "small" features.** Features that feel small usually have hidden scope. The discipline applies regardless of perceived size.
- **Don't merge scope and architecture into one document.** Scope = what the product is. Architecture = how it's built. Different documents, different audiences, different timing.

## Notes

- This is the PARENT skill. After signoff:
  - `/lock-via-data` handles numeric threshold locks
  - `/audit-pre-code` runs the pre-code checklist (which verifies the scope was followed)
- The three skills compose: scope → lock numbers → audit before code → write code
- The scope document lives in the repo (`docs/`) so it's reviewable and historical
- Mohit's signoff is the final gate. Without it, no code, regardless of how thorough the document is
- See [[scope-driven-development]] memory note for the rule and [[card-is-the-product]] for the mockup principle

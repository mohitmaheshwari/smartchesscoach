---
name: draft-feature-spec
description: Write a feature spec in the chessguru convention (docs/<name>_spec.md) following the established 10-section template + the default-off env flag rollout pattern (A/B → 10% → 100% → delete legacy). Trigger when the user describes a non-trivial feature or rewrite that needs design before code, or types /draft-feature-spec, or says "write a spec for X" / "let's design X first".
---

# Draft a feature spec

When a feature is bigger than a half-day or has architectural blast radius, write a spec first. This skill captures the structure we've used across [docs/why_played_wrong_spec.md](docs/why_played_wrong_spec.md), [docs/pwc_skills_aware_coaching.md](docs/pwc_skills_aware_coaching.md), [docs/pwc_realtime_opening_guidance.md](docs/pwc_realtime_opening_guidance.md), and [docs/pwc_central_caption_migration.md](docs/pwc_central_caption_migration.md). Same shape every time so Mohit knows what to expect and future-me knows where to look.

## When to invoke

- User describes a feature that affects ≥1 file beyond a single function-level edit
- Architectural change (parallel engines, schema, data model)
- Anything that touches the central caption pipeline, PWC, or paid-tier features
- User types `/draft-feature-spec` or says "spec this" / "design first"
- Before committing to phase 2 of any migration (per [memory/feedback_one_source_of_truth] — sign-off-gated work needs a doc)

Do NOT invoke for: a contained bug fix, a single config change, a one-line voice rewrite, a tooling probe script.

## Required input

- **Feature name** in kebab-case (e.g. `pwc-skills-aware-coaching`, `why-played-wrong`)
- **Motivation** — what's broken / missing now, with the user-flag evidence if applicable (feedback IDs, observed behaviour, audit findings)
- **Blast radius** — which files / users / surfaces are affected
- **Rollback path** — feature flag name + revert plan

If any of these are unclear, ASK first (one to three short questions). Don't make them up.

## Steps

1. **Pick a doc path.** `docs/<feature_name>_spec.md`. Filename uses snake_case for grep convenience.

2. **Write the 10 sections, in order:**

   ```
   # <Feature Name> — Spec

   **Status:** DRAFT v1 — awaiting Mohit sign-off.
   **Version:** v1 (YYYY-MM-DD).
   **Scope:** <smallest|medium|largest> of <set>; ~<half-day|day|multi-day> to ship.

   ---

   ## 1. The problem
   <motivation, evidence (feedback IDs, audit findings), why the current state is wrong>

   ## 2. The shape — N outcomes
   <state → caption shape table, OR architecture diagram, OR before/after example>
   <if multiple outcomes (PASS/DOWNGRADE/ESCALATE-style), enumerate them>

   ## 3. Schema / files touched
   <specific files + line ranges; new fields/keys; renamed things>

   ## 4. New facts / data the system needs
   <if a fact extractor or data-authoring pass is needed>

   ## 5. Gating — preventing the "X" trap
   <the failure mode this design specifically defends against, with named gates>

   ## 6. Test strategy
   <Phase 1: stateless probe. Phase 2: boundary suite. Phase 3: snapshot. Phase 4: Mohit/Parth eyeball.>
   <reference [memory/feedback_fast_testing_strategy]>

   ## 7. Risk + rollback
   <blast radius, failure modes enumerated, env flag name, revert command>

   ## 8. What this spec does NOT cover
   <out-of-scope items; "filed as follow-up X">

   ## 9. Implementation order
   <numbered phases, each with concrete steps + expected commit titles>
   <follow the A/B → 10% → 100% → delete-legacy convention for risky migrations>

   ## 10. Decisions / Open questions for Mohit
   <DRAFT mode: open questions that block sign-off>
   <SHIPPED mode: list answers Mohit gave + commit hash where the decision landed>
   ```

3. **Embed the env-flag rollout convention.** Any non-trivial change goes behind `${PROJECT}_${FEATURE}_ENABLED` env var (or similar), default-false on ship. The spec §9 implementation order must include:
   - "Ship default-off (flag false)"
   - "Mohit + Parth A/B for one week with flag on"
   - "10% rollout, monitor for one week"
   - "100% rollout"
   - "Delete legacy code after two weeks clean at 100%"

   Skip the rollout phases only when the change is purely additive with zero existing behaviour replaced.

4. **Embed sign-off gates.** §10 must list open questions Mohit needs to answer before §9 phase 2 starts. Don't ship "phase 1 + sketch of phase 2" without an explicit gate. Memory rule: [feedback_one_source_of_truth] says no parallel paths without sign-off.

5. **Track v1 → v2 → vN in the status banner.** When the spec is revised post-ship (we did this for SUPPRESS → DOWNGRADE in `60eceb2e`), update the banner to `SHIPPED v2 — <change> per Mohit YYYY-MM-DD (commit <hash>)`. Don't delete v1's reasoning; cite it as historical context. See [docs/pwc_skills_aware_coaching.md](docs/pwc_skills_aware_coaching.md) for the v1→v2 pattern.

6. **Commit the spec separately from the implementation.** Spec lands in its own commit titled `docs(spec): <feature_name> v1 — <one-line summary>`. Implementation lands in follow-up commits that reference the spec by path. Never bundle spec + first phase of implementation in one commit — reviewer should be able to read the spec alone.

## Output format

Write directly to `docs/<feature_name>_spec.md`. After writing:

1. Print a 3-bullet summary of what the spec proposes
2. Highlight the §10 open questions that block sign-off
3. Print the recommended next command (commit + push the spec)

Do NOT commit the spec automatically — Mohit reviews before commit. The skill outputs the file, not the git ops.

## What NOT to do

- Don't write more than 250 lines for §1-9. If the spec needs more, the feature is too big for one spec — split it (we did this for PWC: 3 separate specs instead of one mega-doc).
- Don't write the implementation in the spec. The spec describes the SHAPE; the code lives in the actual modules.
- Don't fill in §10 with "all decisions made — proceed." Open questions are MANDATORY in a v1 DRAFT. If you don't have any, you haven't thought hard enough about the failure modes.
- Don't skip §7 (risk + rollback). Even small specs need the env flag name and revert command on paper.
- Don't pre-commit to phase 2 in §9. List the phases but explicitly gate each on Mohit's sign-off in §10.
- Don't make up motivation. If the user hasn't given concrete evidence (feedback IDs, audit findings, user reports), ask before writing.

## Notes

- Memory rules that almost always apply:
  - [feedback_one_source_of_truth] — no parallel coaching/caption paths
  - [feedback_no_hardcoded_debug] — no `if move_san == 'X'` debug code in specs
  - [feedback_fix_framing_not_detection] — fix templates, not detectors
  - [feedback_caption_voice_avoid_chess_jargon] — apply to any user-facing wording in the spec
- Existing spec docs to mirror voice + structure from: see the 4 listed in the description.
- After the spec is signed off, the matching implementation can use `/scaffold-skill-drill`, `/author-r12-predicate`, or whatever skill fits the feature type. The spec is the "what"; the skills are the "how."

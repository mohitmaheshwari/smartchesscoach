# Personal Curriculum — Pre-Code Audit

**Status:** PASS FOR PHASE 3 — 2026-08-28. Mohit explicitly said “start phase 3,” deferring the live visual audit to the Phase 4 user-facing gate.

## Gate results

| Gate | Result | Evidence |
|---|---|---|
| 1. Literal UI mockup | **Pass** | `personal_curriculum_scope.md` and `personal_curriculum_route_ux_contract_2026_08_28.md` contain literal Home, Learn, lesson, and completion copy. |
| 2. Pattern-led headline | **Pass** | Headlines name teachable ideas such as Rule of the Square and piece safety; SAN is lesson evidence, not the product headline. |
| 3. Data-derived thresholds | **Pass** | Five-game personalization floor, recurrence 3, topic support 4, named-only selection, a three-measured-game review, and a 21-day check-in backstop are locked from versioned aggregates. |
| 4. Behavior-changing success | **Pass** | Scope requires independent attempt, delayed recall, reduced assistance, and verified application; lesson views alone do not count. |
| 5. Deferred work remains deferred | **Pass** | Full curriculum authoring, premium packaging, social features, and unsupported application claims remain out of V1. |
| 6. Mohit technical sign-off | **Pass** | Mohit approved the route, Explore, plan-reference, and Rule-of-the-Square recommendations on 2026-08-28. The route/UX contract records the locked decisions. |

## Completed measurement for review `N`

### Decision

Candidates measured:

- A: review after **1 game**;
- B: review after **2 games**;
- C: review after **3 games**;
- D: review after **5 games**.

**Winner: C — review after 3 measured games.** It is the first candidate where
99.05% of all rolling windows and 94.74% of 0–999 windows contain at least six
comparable decisions. Overall p25 is 12.5 decisions and measured-user reach is
75%. Removing the largest measured user leaves the conclusion unchanged.

The 21-day calendar backstop remains a check-in or resume prompt, not an
evidence verdict.

### Canonical filter

Use `move_observations` with:

```text
schema_version >= 16
piece_safety_decision.version == "piece_safety.d_live.v1"
piece_safety_decision.derivation_status == "ok"
piece_safety_decision.eligible == true
```

Use only games where every current-schema user-move observation carries the
exact D_live version as the measured game denominator, including games with
**zero** eligible D_live decisions. A schema-16 game with no D_live fact is
**not measured**, not a zero. Group by `user_id` and `game_id`; order with
the real game event time, not backfill time. Report missing/mixed timestamps
separately rather than silently ordering them.

### Discriminating output

For each candidate N, form consecutive per-user N-game windows and report:

- number of users and windows;
- p25, median, p75, and p90 eligible decisions per window;
- percentage of windows with 0, fewer than 6, at least 6, at least 10, and at least 12 decisions;
- percentage of users who reach a review window within their observed history;
- same output with the single 1,510-game outlier user removed;
- rating-band split when rating exists.

Choose the smallest N at the distribution cliff that produces enough comparable decisions for an honest check without delaying the daily player. Do not lock N from the global average of decisions per game.

### Offline artifact

Write the raw aggregate only to:

`backend/data/corpus_snapshots/personal_curriculum_review_opportunities_2026-08-28.json`

Update the existing selection lock with the chosen N, evidence, and rejected candidates. No credentials or raw user/game identifiers enter the snapshot.

## Technical decisions locked

The signed answers are documented in `personal_curriculum_route_ux_contract_2026_08_28.md`:

1. `/learn` is canonical; `/games` is the player-facing Game Review
   index. `/lab` remains a legacy mixed learning route until redirect
   evidence exists.
2. Explore does not replace the coach plan automatically.
3. Persist only a compact active-plan reference in `coach_memory.learning`.
4. Rule of the Square is the first lesson-contract slice; suppress real-game mastery claims until its detector is Plan-grade.

## Lesson readiness dependency

`personal_curriculum_v1_lesson_audit_2026_08_28.md` proves that none of the proposed knowledge lessons currently supports a full real-game learning claim. The first slice may implement controlled lesson evidence through Can do alone. “Used in games” and “Reliable” remain gated by detector-quality promotion.

## Phase boundary

Phase 3 may add only default-off, non-user-visible composition contracts,
stateless probes, and ownership guards. It may not add the Learn route, change
navigation, write curriculum progress, expose new coaching copy, or make
real-game mastery claims.

**Attempted 2026-08-28:** the in-app browser runtime failed before connecting
to a tab because the Windows sandbox launcher returned OS error 206. This is an
environment failure, not visual evidence. Mohit explicitly deferred that audit
by directing Phase 3 to start. Re-run it before Phase 4, together with current
analytics baselines and representative-player mockup testing.

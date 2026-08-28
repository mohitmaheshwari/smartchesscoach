# Personal Curriculum — Phase 4 Pre-Code Audit

**Status:** PHASE 4 VALIDATION RUNNING; PRODUCTION CODE BLOCKED — 2026-08-28.
The user-facing Home/Learn implementation must not begin until the remaining
evidence gates pass.

Mohit's “go next” authorizes advancing the Phase 4 process. It does not silently waive the signed pre-code requirements in `personal_curriculum_scope.md`.

## Six audit gates

| Gate | Result | Evidence |
|---|---|---|
| 1. Literal UI mockup | **Pass** | The signed scope and route/UX contract contain literal Home, Learn, Explore, lesson, completion, and mobile states. |
| 2. Pattern or geometry leads the teaching | **Pass** | Player-facing lesson headlines name useful chess ideas such as Rule of the Square and early castling. Internal IDs and move notation remain evidence, not the headline. |
| 3. Numeric choices are data-derived | **Pass for the pre-code boundary; rollout still gated** | Phase 3 selection and review thresholds are locked. The signed mockup protocol is qualitative and deliberately has no invented numeric pass bar. Contaminated pre-launch PostHog history is ineligible. Rollout and rollback thresholds must be locked from the clean treatment before cohort expansion, not used to block recruitment or manufacture a legacy engagement baseline. |
| 4. Success changes behavior | **Pass as a product definition; unmeasurable today** | The signed criteria require independent attempt, less help on review, delayed recall, and verified application rather than page views. The instrumentation gap prevents measuring the comparison but does not weaken the definition. |
| 5. Deferred work remains deferred | **Pass** | Full curriculum authoring, premium packaging, hard locks, unsupported real-game claims, route deletion, and “Make this my focus” remain outside the first slice. |
| 6. Mohit technical sign-off | **Pass for the Phase 4 process** | Mohit signed the route/UX contract and instructed the work to continue. No sign-off has been recorded for invented thresholds or skipping representative-player validation. |

All six core audit gates now pass for the signed design boundary. Product code
still has no pre-code pass because the separately signed representative-player
session requirement remains incomplete.

## Additional signed pre-code requirements

| Requirement | Result | Evidence / next action |
|---|---|---|
| Route and content ownership | **Pass** | `/learn` is canonical, `/lab` remains the legacy Game Review/Lab surface during migration, and existing detail routes are preserved. |
| V1 lesson audit | **Pass for controlled evidence only** | Rule of the Square may teach through Can do alone; Used in games and Reliable remain suppressed until detector authorization. |
| Evidence ownership and state translation | **Pass for Phase 4 read-only slice** | Phase 3 contracts derive decisions and lesson states without creating another mastery store. |
| Sparse, stale, conflicting, and no-opportunity behavior | **Pass for Phase 4 read-only slice** | Phase 3 decision/result contracts encode the signed honesty constraints. |
| Migration and deep-link preservation | **Pass on paper; runtime verification pending** | The route contract preserves `/lab`, `/training/*`, `/openings/*`, and `/endgames/*`; runtime parity is still required after implementation. |
| Structural reach for recruitment | **Pass** | `backend/data/corpus_snapshots/funnel_and_recruitment_2026-08-28.json` records 45 users with at least five analysed games: 8 at 600–899, 8 at 900–1199, 7 at 1200–1499, plus adjacent cohorts. It is server truth used only to establish recruitable reach, never engagement. |
| Representative-player mockup validation | **Blocked; recruitable pool known** | The protocol exists and the structural pool is sufficient, but no 600–900, 1000–1200, 1300–1500, or browse-first session has been observed. |
| Product-owner desktop/mobile visual audit | **Pass** | Mohit reviewed the interactive Home/Learn/Explore/lesson-return prototype, including mobile mode, and responded: “I love it, please move forward.” Authenticated runtime checks remain implementation QA, not a substitute for player sessions. |

## Completed instrumentation prerequisite

An **instrumentation-only run-in** was separately audited, implemented, and
deployed without changing player-facing recommendation, curriculum state,
navigation, copy, or lesson behavior.

That slice must:

1. register events centrally in `frontend/src/lib/analytics.js`;
2. add semantic events to existing surfaces without changing their presentation;
3. exclude FENs, PGNs, personal data, raw database IDs, and free-form coaching text;
4. validate event names and required dimensions with automated contract tests;
5. preserve all existing analytics calls;
6. document the observation window before looking at results; and
7. produce a second aggregate-only snapshot used to lock Phase 4 rollout thresholds.

The run-in is not used to rehabilitate contaminated pre-launch behavior as an
engagement baseline. The dated server snapshot supplies the structural reach
needed for recruitment. Real representative-player sessions remain the only
pre-code blocker.

## Exit conditions

Change this audit to PASS FOR PHASE 4 product code only when:

- representative sessions cover 600–900, 1000–1200, 1300–1500, and a
  browse-oriented participant, with any failed contract retested; and
- the audit is rerun immediately before the first user-facing implementation
  change.

Before any cohort expansion, preregister a clean treatment interval and lock
numeric rollout, rollback, and behavior-success thresholds from that treatment.
Do not derive them from pre-launch PostHog history.

Until then, do not add `/learn`, change the Home recommendation, change navigation, or expose the Personal Curriculum flag to users.

## Run-in update — 2026-08-28

The separately authorized instrumentation-only slice is deployed and verified
at the public HTTP boundary. It changed no UI or curriculum state. Live-event
inspection remains useful operational QA, but it is not a mockup-validation
data gate and cannot turn pre-launch history into an engagement baseline.

## Phase 4 start update — 2026-08-28

Mohit explicitly instructed: “I would love you to run phase 4.” This is
technical sign-off to execute the signed Phase 4 process, not permission to
invent thresholds or skip its player-validation gates.

The unchanged-UX instrumentation release is now live in production as
`static/js/main.c35c6cf9.js`, with
`instrumentation_version=personal_curriculum.baseline.v1`. Public Home,
Learn/Lab, login, JavaScript, CSS, and API health checks are green. Live
PostHog event-inspector verification, test-account exclusions, and a fixed UTC
observation interval remain pending.

A reviewable interactive prototype now covers the literal signed states:

- Home with one primary lesson and one short review;
- Learn with Learning now, Keeping fresh, Naturally next, and Explore;
- Explore lesson continuity that preserves the coach recommendation;
- lesson completion returning through Back to your plan; and
- a mobile mode that puts the reason and primary action before the library.

This prototype is validation material outside the product repository. It does
not add `/learn`, change production navigation, or count as a representative
player session. Gate 1 is stronger, but the representative-player and live
desktop/mobile gates remain open until observed people complete the signed
protocol.

Current pre-code verdict:

```text
PRE-CODE AUDIT: BLOCKED
Passed: literal UI contract, teaching headline, behavior-changing definition,
        deferred-scope control, explicit Mohit authorization
Blocked: representative-player sessions
DO NOT WRITE PRODUCT CODE until resolved.
```

## Mohit visual approval update — 2026-08-28

Mohit reviewed the interactive desktop/mobile Phase 4 prototype and responded:
“I love it, please move forward.” This closes the product-owner visual-contract
approval for the signed Home, Learn, Explore continuity, lesson-return, and
mobile hierarchy.

It does not count as the representative-player cohort required by the signed
protocol, and it does not create a behavioral baseline. A fresh attempt to
open the production journey through the supported browser failed before a tab
opened with the same Windows sandbox launcher OS error 206. Tool discovery
found no PostHog connector, and only environment-variable names were inspected;
no PostHog query credential is configured.

The PostHog access issue is not a mockup-validation blocker. The dated
server-side snapshot is the structural-reach source; historical client behavior
remains excluded. The sole external pre-code unblocker is observed sessions
covering 600–900, 1000–1200, 1300–1500, and a browse-oriented participant.

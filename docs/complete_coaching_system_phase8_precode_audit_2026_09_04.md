# Complete Coaching System Phase 8 Release Rescue — Pre-Code Audit

**Status:** APPROVED FOR PREREQUISITE IMPLEMENTATION; ENROLLMENT DATA-LOCKED
**Date:** 2026-09-04
**Audited base:** `origin/working-code` at `fbe6514c2e222b84c523d63bbcec330387d63d2b`
**Addendum:** `docs/complete_coaching_system_phase8_release_rescue_addendum.md`

## Six gates

| Gate | Result | Evidence |
|---|---|---|
| 1. Literal UI mockup exists | **Pass** | Addendum §2 specifies Home, lesson before/after grading, completion, Review and all three Progress outcomes in player-visible language. |
| 2. Headline is the chess idea, not SAN | **Pass** | “Keep every piece safe” leads; move notation appears only as evidence inside an authorized explanation. |
| 3. Thresholds come from data | **Pass with enrollment hold** | The approved amendment supersedes `10 of 67` after production showed zero active non-admin focus bundles and only 5.6% detector-field coverage. Ten is provisional. Addendum §4A requires full stored-evidence reconciliation and focus-bundle dry-runs before the eligible denominator and absolute target are frozen. No enrollment may precede that lock. |
| 4. Success changes behavior | **Pass** | The product gate requires a later unassisted comparable game opportunity and a served verdict. Deployment correctness and lesson completion are necessary but cannot substitute for transfer measurement. |
| 5. Deferred work remains deferred | **Pass** | New detectors, 3A.6, Shadow promotion, Stockfish reruns, Elo promises, 100% enrollment, legacy deletion and new pages remain out of scope. |
| 6. Mohit explicitly approved this exact addendum | **Pass** | Mohit explicitly approved both Phase 8 documents on 2026-09-04 with a binding data prerequisite, six-week review rule and mid-journey rollback requirement. Those amendments are incorporated in the addendum. |

## Existing-system audit

- The routed surfaces already exist: Home/Activation, Training, `LabV2` → `GameDecryptionV5`, and `UnifiedProgress`.
- The explicit move-verdict frontend fix is already live at `cf7892ab`; rebuilding it would be duplicate work.
- The current integration registry contains one Plan-grade and six Caption-grade authorizations. It also contains 41 Shadow and five Disabled detectors that must remain invisible.
- Product reach is divided across role gates and feature flags. The central Complete Coaching System flag currently enables internal machinery, not one coherent user cohort decision.
- `scripts/deploy.sh` proves source revision, build success and health but does not invoke the strict authenticated verifier or prove the coaching journey.
- `verify_deployment.py` can require existing checks, but its current canonical contract check only proves a V5 response shape. It does not prove Home → interactive grading → stored evidence → Review → Progress.
- The 11 local-only commits have been resolved explicitly in addendum §3. Three are patch-equivalent; seven are integrated/superseded upstream; one deletion is a no-op because the malformed files are absent. No whole commit should be replayed.
- The existing `caption_concept_id` reconciliation has already populated 6,495 records from a prior zero baseline. Phase 8 must classify current/stale/missing rows and be idempotent rather than replaying it indiscriminately.
- The production prerequisite audit found 446,495 move observations but only 24,817 (5.6%) carrying the relevant detector field; zero non-admin analyzed-game users had an active focus bundle. This makes stored-evidence coverage and focus-bundle creation prerequisites to a valid reach denominator.

## Canonical ownership before implementation

| Concern | Owner after Phase 8 | Prohibited duplicate |
|---|---|---|
| Cohort eligibility | One complete-coaching access resolver | Page-specific role/cohort lists |
| Focus and instruction | `user_active_focus` through `focus_bridge` | Direct surface reads or copied focus text |
| Chess truth | Stored engine/tablebase facts plus authorized deterministic verifier | Client grading or LLM chess authority |
| Surface authorization | `detector_quality.py` | UI-maintained detector allowlists |
| Lesson lifecycle | `teaching_engine` | New Phase 8 lesson engine |
| Attempt evidence | `learning_evidence_ledger` / verified attempt chokepoint | Reach-counter writes that impersonate learning evidence |
| Learner verdict | Canonical mastery reducer | Progress-page calculation from raw counters |
| Captions | Central caption pipeline and stored authorized event contracts | A Phase 8 caption renderer |
| Deploy reach | `verify_deployment.py`, invoked by `scripts/deploy.sh` | One-off manual-only smoke script |

## Failure-first acceptance matrix

| Scenario | Required result |
|---|---|
| Master flag off | All Phase 8 surfaces preserve current behavior; no cohort data leaks. |
| Non-admin not enrolled | No personal Phase 8 projection, even when subsystem flags are enabled. |
| Non-admin enrolled, subsystem unsafe/off | The affected surface fails closed or uses the approved legacy fallback; central access never overrides truth safety. |
| Authorized Plan focus | Same focus/instruction identity reaches Home, lesson, Review and Progress. |
| Caption-grade event present | Review surfaces it with the authorized board facts. |
| Shadow/Disabled event present | It remains absent from player output. |
| Lesson move correct | Explicit server-owned success, one evidence row, next position unlocked. |
| Lesson move incorrect | Explicit server-owned miss, legal retry, no fabricated explanation. |
| Duplicate submission | Same response/evidence identity; no duplicate ledger row. |
| No later opportunity | Progress says not enough evidence; never failure or improvement. |
| Later handled opportunity | Canonical reducer can report getting more reliable only under the existing transfer contract. |
| Later miss | Focus remains active and copy says still recurring. |
| Reconciliation rerun | Zero new writes after a successful apply. |
| Stored detector field already current | Preserve it; do not duplicate or rewrite historical evidence. |
| Stored detector field missing | Dry-run classifies it; apply uses only the existing Plan-grade detector and stored facts. |
| Focus bundle already current | Preserve it; denominator repair never replaces a valid focus. |
| Eligible user missing a focus bundle | Dry-run explains eligibility; approved apply creates it through the canonical focus authority. |
| Deploy verification lacks token/fixture | Hard failure, not SKIPPED or success. |
| Frontend bundle stale | Deploy fails even if backend health is 200. |
| API works but route/component is absent | Deploy fails the bundle/route reach contract. |

## Pre-enrollment ordering check

The stored-evidence and focus-bundle prerequisite precedes denominator locking. The denominator lock precedes baseline capture. Baseline capture precedes every user-access mutation. A cohort enrollment command must refuse to run when the target is still provisional or the candidate user lacks a Phase 8 baseline row at the same contract version and earlier cutoff time. This prevents a deploy operator from inventing the denominator after outcomes or destroying the pre-period by reversing commands.

Deployment has one bootstrap constraint: the strict live journey check cannot
pass until its dedicated non-admin verifier already has a frozen target,
baseline and existing per-user enrollment. Therefore Claude builds the
candidate image without restarting production, runs the prerequisite tools in
one-off candidate containers, captures and enrolls only the verifier, and only
then invokes `scripts/deploy.sh`. The script remains the sole service-restart
and frontend-publication path.

## Measurement boundary

Server-side journey evidence is the authority for completion. Client analytics remain useful for UX diagnostics but cannot prove that a lesson was graded, an attempt persisted or a later opportunity was measured. The real-user gate counts distinct users from server-owned facts; it does not add client event counts.

## Operational test boundary

- Unit: access resolution, reconciliation categories, baseline immutability, idempotency, authorization filtering and journey reducer.
- Integration: seeded non-admin account crosses Home, Training, Review and Progress through actual route functions with a disposable database.
- Browser contract: Home CTA opens the canonical training route; board is interactive; verdict renders; Review and Progress consume returned contracts.
- Deployment: `scripts/deploy.sh` invokes strict verification and rejects any skipped required reach check.
- Production pilot: read-only baseline first, then explicit enrollment, then one manual non-admin pass by Claude/Mohit before inviting additional users.
- Real-user review: evaluate the frozen journey target 42 calendar days after first enrollment. A shortfall keeps the pilot incomplete and produces a step-by-step inactivity-versus-product-failure report; it never silently lowers the gate.

## Verdict

```text
PRE-CODE AUDIT: APPROVED FOR IMPLEMENTATION

All architecture, UI, data, migration and test gates are defined. Mohit approved
the addendum and this audit with the §4A data prerequisite. Implementation may
begin. Production enrollment remains blocked until the prerequisite dry-run and
approved apply produce the denominator and the final absolute target is frozen.
```

# ChessGuru coaching room — implementation spec

**Status:** DRAFT v1 — visual direction/all-page coverage approved; pilot gate mechanism decided 2026-09-22 (§5); detailed scope and implementation boundaries awaiting sign-off.
**Version:** v1, 2026-09-22.
**Scope:** Full existing frontend, delivered as verified slices; not a single CSS-only change or a new application.

## 1. The problem

The user-approved design raises the presentation standard beyond the current large-hero/text-card screens. The source audit records 66 routes, mixed styling and motion, misleading empty/error states and feedback timing issues. Existing implementation and prior scopes must be extended, not replaced blindly. See `coaching_ux_polish_existing_surfaces_audit_2026_09_22.md`, `coaching_room_all_pages_scope.md` and the approved reference at `design/chessguru-atelier.html`.

## 2. The shape — six presentation outcomes

| Page role | Presentation | Existing authority |
|---|---|---|
| Direction | One current task with relevant evidence and start/resume | Curriculum recommendation and current enrollment |
| Activity | Board, current prompt, feedback, line controls and deliberate finish | Existing lesson/review/game controller |
| Discovery | Scan-friendly board previews and short labels | Existing catalog/repertoire and admitted content |
| Evidence | Recorded activity versus later-game change, with exact unavailable states | Current progress contracts and baselines |
| Utility | Compact form, submitting/error/success, useful next action | Existing account/import/payment endpoints |
| Operations/document | Dense evidence/table/editor or readable article | Existing admin permissions, document content and SEO |

Extend the current `Layout` and visual primitives. Do not create six routers or six state stores. Preserve the shared consumer navigation names and deep links.

## 3. Schema / files touched

No DB schema or chess-service change is planned. Expected frontend touchpoints, subject to per-slice source verification:

- `src/index.css`, `tailwind.config.js`, `src/lib/motion.js`, `src/lib/experience.js`: canonical tokens, typography, role layouts, motion and presentation rollout. Remove conflicting touched rules rather than append unbounded overrides.
- `src/components/Layout.jsx`, `src/App.js`: shared shell, mobile navigation, accessible states and verified link recovery. Existing route guards, `MotionConfig`, auth callback and `ViewAsBanner` remain authoritative.
- `src/pages/PersonalCurriculum.jsx`, `src/components/curriculum/CurriculumHome.jsx`, `CurriculumPrimary.jsx`: compact headers, recommendation composition and optional safe preview. Preserve `eventProps`, decision IDs, analytics and destinations.
- `src/components/training/PersonalizedLessonWorkspace.jsx`, `src/pages/PrescribedTraining.jsx`, `DiagnosticPuzzles.jsx`, other drill/geometry owners: presentation states and explicit continuation. Preserve attempt schema and puzzle/admission contracts.
- `src/pages/AllGames.jsx`, `LabV2.jsx`, current `GameDecryptionV5` host and `CoachReplay.jsx`: review composition and actual/alternative line presentation. Do not create a second replay engine.
- Current opening/endgame library and lesson components: card hierarchy and verified board previews; existing `InlineBoardPreview` is a reuse candidate, not assumed universal.
- `src/pages/CoachPlay.jsx` and existing setup/board/sidebar children: layout only around existing controllers and critical-message rules.
- `UnifiedProgress.jsx`, `ImportGames.jsx`, `Settings.jsx`, arrival/public/internal page owners: their role-specific treatments from the route audit.
- `frontend/package.json` and lockfile: self-hosted **Instrument Serif** (headings) and **Manrope** (interface). Both are SIL OFL, so no licence purchase is needed. The reference's `fonts.googleapis.com` and mutable `lichess-org/lila@master` piece-image requests must not ship; the app keeps its existing bundled piece assets.
- `backend/routes/auth.py` only: the single presentation-gate boolean on the existing `/auth/me` response, plus its allowlist env var. No other backend file is in scope. Per project instructions this requires `backend/tests/test_all_flows.py` to be run and its exit recorded.

Route inventory and render/test evidence belong in documentation or QA fixtures, not a new runtime duplicate of `App.js`.

## 4. New facts / data the system needs

None may be invented. Existing payloads must supply the title, reason, position, solution-safe preview, legal line, result and completion state that the UI displays. Do not fetch an answer-bearing lesson merely to decorate Home.

The prototype's rook position, simplified input and local completion flag are design-only. For missing preview data, use the approved compact text variant. Missing durable resume or missing explanation is a named dependency, not a client-side inference. New evidence APIs are outside this change unless separately approved; the presentation-gate boolean in §5 is the one approved exception and carries no evidence.

## 5. Gating — preventing another last-wire failure

- Reuse existing rendering and data owners; preserve flag and permission checks for learning content.
- **Gate mechanism, decided 2026-09-22 (Mohit): runtime per-account, not build-time.** A CRA `REACT_APP_*` value is substituted into one bundle at build time and therefore cannot serve two accounts differently on one deployment. A build-time flag was rejected for exactly that reason.
- The gate is one additional boolean on the **existing** `/auth/me` response, which `App.js` already fetches once at startup. No new endpoint, no second fetch, no new client state store, no DB schema change. Server side it is driven by an explicit allowlist (env-var list of `user_id`s) read in `backend/routes/auth.py`; absent or unmatched means false.
- This one backend field is the sole approved exception to the no-backend-change boundary, authorised by that decision. It carries no chess, evidence or curriculum data and must never gate anything but presentation.
- Default is false for every account, including admins, until a `user_id` is explicitly listed. Build capability alone must not expose the redesign. `EXPERIENCE_V1_ENABLED` currently defaults **true** and is not isolation for this pass.
- The same field carries the later 10% and 100% stages, so no second mechanism is built later.
- Public pages can be evaluated in local/staging builds before any public activation. Do not infer anonymous rollout permission from an admin pilot.
- Missing content, transport failure and unavailable evidence are separate states. Feedback errors cannot become chess judgments.
- Board previews and hints cannot leak diagnostic answers. Admission, Shadow restrictions and blinded reviewer choices remain unchanged.
- No timer may dismiss a final teaching result before deliberate continuation. Preserve game clocks and scripted opponent reply sequencing.
- Retain existing production gates. Add route/action/asset/render checks for this change; a build success is not proof that a non-admin can experience it.

## 6. Test strategy

**Baseline:** record current revision, installed dependencies, targeted tests, build status and representative task journeys. Compare new failures against that same baseline; do not reuse historical totals.

**Components:** shared style/flag contract, menu/keyboard behavior, loading/error/retry, relevant preview/no-preview, correct authorised destinations, assistance/attempt state, retained verdict and deliberate Next. Board tests cover orientation, promotion, legal input, highlights and unmount cleanup.

**Integration:** recommendation → real lesson → attempt → explanation → completion → return; selected game → chapter → alternative line → actual game; imports with a partial response or failed refresh; PWC resume/reconnect/postgame. Validate no duplicate submissions or extra engine calls caused by rerenders.

**Rendered QA:** each changed route and major query mode with supported ready/loading/empty/error/partial/resume states. Use representative small phone, tablet and desktop viewports, both themes, zoom, reduced motion, keyboard and measured contrast. Controls and essential teaching text must not clip; long prose and opening names must reflow. Preserve native/browser focus behavior.

**Authenticated acceptance:** at least one non-admin supported account plus admin, enabled/disabled curriculum and new-player states in a safe environment. Production writes, real-game submissions, payments or invitations are not an automatic part of UI QA.

**Commands/evidence:** targeted frontend test commands, full relevant regression suite, production build and `git diff --check`; store actual exits. If a backend change is separately approved, run focused tests plus `backend/tests/test_all_flows.py` per project instructions. An unavailable environment is unrun, not pass.

## 7. Risk + rollback

- Highest risks: broad CSS specificity; touch overlays blocking board input; re-rendered boards; changed query/return state; hidden critical messages; theme contrast; answer leakage; previous work overwritten during integration.
- Preserve existing build behavior when the new presentation flag is false. A presentation-off build must remove the new styling and composition, not just the sidebar colour. Use shared data logic rather than duplicating controllers across variants.
- CRA flags are substituted at build time. Rollback requires rebuilding/redeploying the known-good artefact or switching to its preserved image; changing an environment value in a running container alone is insufficient.
- No data migration is planned, so presentation rollback must not modify stored evidence or sessions. Document exact last-known-good commit/image in Claude's release handoff, not a guessed production revision.
- Stop expansion for any new broken core journey, leaked answer, false success, lost session, inaccessible board/control, unauthorised exposure or critical console/network error attributable to the change. Revert affected presentation exposure and preserve evidence for diagnosis.

## 8. What this spec does NOT cover

New chess reasoning, grading, detectors, ranking, backend performance algorithms, teacher content, community matching, PWC controller activation, pricing or baseline migration. Not an app rewrite or a promise that a better appearance guarantees retention. Missing protocol capabilities become explicit follow-ups instead of hidden implementation work.

## 9. Implementation order

0. **Before any implementation, and before the current UI changes:** (a) ~~land the approved reference~~ — **done**, at `docs/design/chessguru-atelier.html` with `docs/design/README.md`; (b) record representative baseline journeys at `3df9ab99`, because §5 of the scope compares task completion against the current experience and that comparison is unrecoverable once slice 1 lands.
1. After scope approval, commit the scope/spec/reference separately: `docs(spec): coaching room all-page UX contract`. No implementation bundled into that commit.
2. Foundation plus Learn slice: `feat(ux): coaching room foundation and guided lesson presentation`. Preserve existing shared owners, provide safe no-preview variant, test the whole lesson round trip. Gate: rendered product-owner approval and same-baseline regression evidence.
3. Arrival/Home/import: `feat(ux): coherent arrival and account connection journey`. Gate: supported diagnosis/import handoffs and failures, no real-account mutation during mock QA.
4. Libraries/review/specialist learning: `feat(ux): board-led libraries and guided review`. Gate: deep links, query modes, actual/counterfactual labels and answer safety.
5. PWC/progress/settings: `feat(ux): coaching and evidence presentation`. Gate: active/resumed game, failure and postgame states, same progress assertions.
6. Public/legal/contact/pricing/internal/legacy completeness: `feat(ux): complete route-family polish`. Gate: every route row has a treatment and recorded check; unchanged redirects explicitly tested.
7. Ship through Claude only after handoff, with the allowlist empty so no account is exposed. Then add Mohit's and Parth's `user_id`s for one week; then 10%; then 100%; delete superseded presentation code after two clean weeks at 100%. Each exposure increase requires sign-off and observed journeys, not merely elapsed time. These are rollout stages, not learning/retention targets.

Each slice has an explicit review boundary; approval to implement the scoped redesign is not permission to enable all accounts. No slice counts as an app-wide finish.

## 10. Decisions / Open questions for Mohit

- **Approved:** latest ivory/forest/serif board-led visual direction and all-page coverage. Existing routes and product capabilities remain the base.
- **Recommended boundary requiring scope sign-off:** full customer presentation; efficient internal-tool polish; compatibility for aliases/legacy; no chess/data/controller changes. Accept the compact no-preview state rather than adding facts to fill the design.
- **Before first rollout:** choose the explicitly isolated pilot accounts and approve the authenticated visual assignment mechanism. Do not silently use a role-wide/global flag as founder-only isolation.
- **Before later stages:** review rendered real pages and acceptance evidence for each slice. Claude remains responsible for push and production deployment.

Pre-code audit status: mockup PASS; pattern-led headlines PASS; new chess thresholds NOT APPLICABLE; behavior-based acceptance SPECIFIED/BASELINE PENDING; deferred work preserved PASS; detailed scope sign-off PENDING. No application code changes until the final gate is satisfied.

# QA Gate — Frontend Experience V1

**Repo:** `smartchesscoach`  
**PR / Branch:** `working-code` (frontend redesign file set only; not the entire dirty worktree)  
**Engineer:** Codex  
**Date:** 2026-08-28  
**Mode:** Production

---

## Prototype vs Production

Production. The proposed verification deploy changes real user-facing routes. The redesign is protected by the CRA build-time flag `REACT_APP_FRONTEND_EXPERIENCE_V1_ENABLED`, whose code fallback is `false`.

## Component(s) touched

No repository `qa-plan.md` was found, so the actual frontend modules are named below.

| Component | Files / paths touched |
|---|---|
| Experience flag and route families | `frontend/src/lib/experience.js`, `frontend/src/App.js` |
| Global visual system and responsive layout | `frontend/src/index.css`, `frontend/src/components/Layout.jsx` |
| Chess-board presentation | `frontend/src/components/CoachBoard.jsx`, `frontend/src/components/LichessBoard.jsx`, `frontend/src/components/coach/CoachPlayBoard.jsx` |
| Routed product screens | Routed components under `frontend/src/pages/` |
| New experience UI | `frontend/src/components/experience/` |

Static route coverage audit: all 51 imported routed page components are assigned an experience class, covering all 57 route declarations through explicit page or route-family styling.

## Layer 1 — Unit tests

- [ ] New visual/routing behavior has dedicated automated assertions
- [ ] Full frontend unit suite passes
- [ ] Confirmed no unrelated tests broke against a clean base run

Evidence actually run:

```text
yarn test --watchAll=false --runInBand src/lib/motifDrill.test.js src/lib/repView.test.js

Test Suites: 2 passed, 2 total
Tests:       24 passed, 24 total
```

The full frontend test command was also attempted. The two suites above passed, but `CoachingPrescriptions.test.jsx` could not start because `@testing-library/react` is not installed. This means the full unit gate is not green.

Build evidence:

```text
yarn build

Compiled with warnings.
Exit code: 0
```

Warnings include the existing missing `node_modules/src/chess.ts` source map, stale Browserslist data, React hook dependency warnings, and bundle-size warnings. The successful production build is useful evidence but does not replace unit coverage.

## Layer 2 — Integration tests

- [ ] A defined integration suite covers route rendering, navigation, responsive layout, and the redesign flag
- [ ] Integration suite passes
- [ ] New visual failure modes are covered

No repository `qa-plan.md` or dedicated frontend integration pair was found. No automated browser integration run is available for this change.

## Layer 3 — End-to-end

- [ ] A staging or isolated production run exercised the affected routes
- [ ] Screenshots or execution evidence are attached

Not complete. The supported in-app browser could not start because the Windows sandbox helper failed with OS error 206 (`The filename or extension is too long`). No visual E2E result is being inferred from the production build.

Required manual evidence before public rollout:

1. Deploy a clean frontend-only build to a preview/staging or otherwise isolated production slot.
2. Build with `REACT_APP_FRONTEND_EXPERIENCE_V1_ENABLED=true`.
3. Verify desktop and mobile navigation, overflow, dialogs, loading/empty/error states, chess-board sizing and interaction, and the primary guided CTA on each route family.
4. Capture screenshots for representative public, core, review, learning, setup, recovery, legal, and admin routes.
5. Confirm rollback by rebuilding with the flag unset or `false`.

## Engineer's self-declaration

This document reflects the commands and results actually observed. Unchecked items are explicit release gaps. The current worktree contains many unrelated frontend and backend edits, so it must not be deployed wholesale as the Frontend Experience V1 artifact.

**Signed:** Codex  
**Date:** 2026-08-28

---

## Mohit's gate — QA lead, fills in last

**Verdict:** ☐ Approved   ☐ Approved with follow-up   ☐ Rejected — needs rework

**Notes:**

**Follow-up items (if any):**

| Item | Owner | Due |
|---|---|---|
| | | |

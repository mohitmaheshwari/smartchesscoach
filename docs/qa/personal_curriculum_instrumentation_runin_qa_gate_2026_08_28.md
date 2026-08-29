# QA Gate — Personal Curriculum Instrumentation Run-In

**Repo:** `smartchesscoach`  
**PR / Branch:** `working-code` dirty worktree; proposed release must be isolated from production commit `33dfa9dbcf8bbb6b3dd139e1985b4b680cb80196`  
**Engineer:** Codex  
**Date:** 2026-08-28  
**Mode:** Production

---

## Prototype vs Production

Production. Although this slice changes no visible UX or curriculum state, it
adds analytics calls to real user paths and sends new interaction events to
PostHog after deployment.

No repository `qa-plan.md` was found, so the actual touched modules are named
instead of a C1–C6 taxonomy.

## Component(s) touched

| Component | Files / paths touched |
|---|---|
| Canonical event registry and privacy boundary | `frontend/src/lib/analytics.js` |
| Registry/privacy behavior test | `frontend/src/lib/analytics.test.js`, `backend/tests/test_analytics_event_registry.py` |
| Recommendation impressions and actions | `frontend/src/pages/HomePageNew.jsx`, `frontend/src/pages/Dashboard.jsx` |
| Browse and progress impressions | `frontend/src/pages/OpeningsOverview.jsx`, `frontend/src/pages/UnifiedProgress.jsx` |
| Lesson and attempt funnels | `frontend/src/pages/OpeningLesson.jsx`, `frontend/src/pages/EndgameLesson.jsx`, `frontend/src/pages/PrescribedTraining.jsx`, `frontend/src/components/openings/InteractivePractice.jsx`, `frontend/src/components/openings/TrapPractice.jsx` |
| Analytics ownership and run-in records | `docs/product_analytics_source_map.md`, Personal Curriculum Phase 4 documents and aggregate snapshot |

## Layer 1 — Unit tests

- [x] New analytics boundary has focused behavior tests.
- [ ] Full frontend unit suite passes.
- [ ] Confirmed no unrelated tests broke against a clean base run.

Focused frontend evidence:

```text
npm test -- --runInBand --watchAll=false src/lib/analytics.test.js

PASS src/lib/analytics.test.js
Test Suites: 1 passed, 1 total
Tests:       3 passed, 3 total
```

Canonical registry evidence:

```text
python -m pytest backend/tests/test_analytics_event_registry.py -q

.... [100%]
4 passed in 0.34s
```

Full frontend evidence:

```text
npm test -- --runInBand --watchAll=false

Test Suites: 1 failed, 9 passed, 10 total
Tests:       40 passed, 40 total

FAIL src/components/__tests__/CoachingPrescriptions.test.jsx
Cannot find module '@testing-library/react'
```

The failure occurs before that pre-existing suite can run because its imported
test dependency is absent from `frontend/package.json`/the installed tree. It
does not exercise this analytics slice, but the full-suite checkbox remains
honestly unchecked.

Production-build evidence:

```text
npm run build

Compiled with warnings.
Exit code: 0
```

The first build found a new Home hook-stability warning; the decision object
was memoized and the final build no longer reports that warning. Remaining
warnings are pre-existing: missing chess.js TypeScript source map, stale
Browserslist data, existing hook-dependency warnings, and bundle size.

`git diff --check` is clean. Static search found no raw PostHog call outside
the canonical module and no raw-string `trackCurriculum()` emitter.

## Layer 2 — Integration tests

- [ ] A defined integration suite covers page action → analytics helper → PostHog capture.
- [ ] Integration suite passes.
- [x] The new privacy failure mode is covered at the helper boundary.

No repository `qa-plan.md` or existing PostHog integration pair was found.
The unit test exercises the real `trackCurriculum()` path with a mocked
`window.posthog.capture` and proves that FEN, coaching text, nested objects and
unknown fields are removed. This is useful boundary evidence, but it is not a
live PostHog integration run.

## Layer 3 — End-to-end

- [ ] A staging or isolated production run exercised the affected journey.
- [ ] Live PostHog event-inspector evidence is attached.

Not complete. The supported in-app browser still fails before opening a tab
because the Windows sandbox launcher returns OS error 206. No browser or live
event result is inferred from unit tests or a successful build.

Required post-deploy canary evidence:

1. Keep the Personal Curriculum UI flag off.
2. Verify one Home/Learn visible recommendation impression and click.
3. Verify one Study browse event and one lesson/practice attempt.
4. Confirm `instrumentation_version=personal_curriculum.baseline.v1` and
   `flag_state=legacy_control`.
5. Confirm no FEN, PGN, move, coaching text, personal identifier, game ID or
   session ID property appears.
6. Record the deployment UTC timestamp, release identifier and test-account
   exclusions before the fixed observation interval is locked.

## Release isolation and rollback findings

- Production checkout: clean `working-code` at
  `33dfa9dbcf8bbb6b3dd139e1985b4b680cb80196`.
- Local `origin/working-code`: `b4ab6768f62e3d665f875c371897046c323ac380`,
  24 commits ahead of the live checkout.
- Local working tree: many unrelated tracked and untracked changes.
- Therefore **do not** deploy the local `frontend/build`, run `git pull` on
  production, or stage whole modified files as this release.
- `frontend/publish.ps1` is unsafe for this release: it deletes/uploads
  `/var/www/html/SMART_CHESS_COACH`, while nginx actually serves
  `/var/www/chessguru.ai`.
- Current live bundle: `static/js/main.b29efb1b.js`.

Safe release method:

1. Create an isolated release worktree from the exact live commit.
2. Apply only the reviewed instrumentation changes, adapting them to that
   base where current local files depend on later unrelated commits.
3. Rerun focused tests and production build in the isolated worktree.
4. Upload to a new release directory, never delete the live root first.
5. Preserve the current directory as the rollback release.
6. Atomically switch the served directory only after the new index and assets
   are complete; verify the new bundle ID and HTTP health.

## Production deployment record

- Approval: Mohit approved with the documented browser/PostHog follow-up.
- Isolated release base: `33dfa9dbcf8bbb6b3dd139e1985b4b680cb80196`
  (the exact frontend commit previously live in production).
- Isolated instrumentation commit: `235e0700` (`feat: instrument personal
  curriculum baseline`). The commit exists locally; its branch push was not
  permitted by the environment's sensitive-egress approval guard.
- Release directory:
  `/var/www/chessguru.ai.releases/20260828T152011Z-235e0700`.
- Full rollback backup:
  `/var/www/chessguru.ai.rollback.20260828T152011Z-b29efb1b`.
- Activated at approximately `2026-08-28T15:26:31Z`.
- Live frontend bundle: `static/js/main.c35c6cf9.js`.
- Instrumentation identity in the built artifact:
  `personal_curriculum.baseline.v1`.

The first index activation was immediately rolled back after public checks
returned HTTP 500 for the homepage and HTTP 403 for static assets. Diagnosis
showed that rsync had preserved Windows-created directory mode `700` under the
served root; nginx requires directory traversal. The known-good index was
restored, directory modes under the exact web root were returned to `755`
(matching the verified backup), and the old homepage/bundle were confirmed
healthy before retrying. The release index was then staged explicitly as
`0644` and activated atomically.

Post-retry production evidence:

```text
GET/HEAD https://chessguru.ai/                              200
HEAD     https://chessguru.ai/home                          200
HEAD     https://chessguru.ai/login                         200
HEAD     /static/js/main.c35c6cf9.js                        200
HEAD     /static/css/main.553d4d47.css                      200
GET      https://chessguru.ai/api/health                    healthy; database connected
nginx error log after the retry                             no new errors
```

The supported browser smoke runner was retried after deployment and still
failed before opening a tab with Windows sandbox launcher OS error 206.
Therefore rendered authenticated journeys, live PostHog event-inspector
evidence, test-account exclusions, and the observation-window lock remain
explicit follow-up work; none is inferred from HTTP health.

## Engineer's self-declaration

This document reflects commands and results actually observed. The focused
logic, isolated production build, artifact identity, public routes, static
assets and backend health are green. The full frontend suite and rendered/live
analytics E2E layers remain incomplete for the reasons recorded above.

**Signed:** Codex  
**Date:** 2026-08-28

---

## Mohit's gate — QA lead, fills in last

**Verdict:** ☐ Approved   ☒ Approved with follow-up   ☐ Rejected — needs rework

**Notes:** Approved by Mohit on 2026-08-28; production activation completed
with immediate rollback/recovery capability preserved.

**Follow-up items (if any):**

| Item | Owner | Due |
|---|---|---|
| Rendered authenticated canary and live PostHog privacy/property inspection | Codex / Mohit | Before locking the observation interval |
| Resolve or work around desktop browser sandbox launcher OS error 206 | Codex | Follow-up |
| Add missing `@testing-library/react` dependency and rerun the full frontend suite | Engineering | Follow-up |

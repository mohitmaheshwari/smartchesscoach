# QA Gate — Personal Curriculum Phase 4

**Repo:** smartchesscoach
**PR / Branch:** `codex/personal-curriculum-phase4`
**Engineer:** Codex
**Date:** 2026-08-29
**Mode:** Production

---

## Prototype vs Production

This is Production mode because it adds an authenticated API, persists a
compact curriculum continuity reference, and changes Home, Learn, and
navigation for eligible production users. The rollout remains default-off and
restricted to configured roles.

## Components touched

| Component | Files / paths touched |
|---|---|
| Curriculum contracts and adapter | `backend/services/personal_curriculum.py` |
| Canonical knowledge and endgame routing | `backend/services/today_composer.py`, `backend/services/endgame_theory_service.py` |
| Coach-memory continuity | `backend/services/coach_memory.py` |
| Authenticated API and legacy consumers | `backend/routes/coach.py`, `backend/routes/home.py`, `backend/routes/training_advanced.py`, `backend/home_intelligence_service.py` |
| Home, Learn, Explore, and navigation | `frontend/src/pages/HomePageNew.jsx`, `frontend/src/pages/PersonalCurriculum.jsx`, `frontend/src/components/curriculum/`, `frontend/src/components/Layout.jsx`, `frontend/src/App.js` |
| Analytics contract | `frontend/src/lib/analytics.js`, `frontend/src/lib/analytics.test.js` |

No repository `qa-plan.md` was present, so the components above use their
actual module names rather than a C1-C6 mapping.

## Layer 1 — Unit tests

- [x] New and changed curriculum logic has focused unit coverage.
- [ ] The repository-wide unit suites are fully green.
- [ ] A clean base-commit comparison run is available.

Focused backend contracts and adapter:

```text
python -m pytest tests/test_personal_curriculum_contracts.py tests/test_personal_curriculum_adapter.py -q
43 passed in 0.42s
```

Canonical focus, endgame, and coach-memory regressions:

```text
python -m pytest tests/test_engine2_recording.py tests/test_endgame_opposition.py tests/test_endgame_lucena.py tests/test_endgame_philidor.py tests/test_focus_sync.py tests/test_coach_memory_velocity.py -q
44 passed, 18 skipped in 13.94s
```

Focused frontend behavior, analytics, copy, and Explore routes:

```text
npm test -- --watchAll=false --runInBand src/lib/analytics.test.js src/lib/personalCurriculum.test.js src/components/curriculum/CurriculumPrimary.test.jsx
Test Suites: 3 passed, 3 total
Tests:       7 passed, 7 total
```

Production bundle:

```text
npm run build
Compiled with warnings.
exit code 0
```

The warnings are existing source-map, hook-dependency, and bundle-size
warnings. The earlier repository-wide frontend run had 8 suites / 38 tests
pass, but one unrelated legacy suite failed at collection because
`@testing-library/react` is not declared or installed. The full backend suite
was not rerun because its current collection includes live-service
requirements; no clean base comparison is claimed.

## Layer 2 — Integration tests

- [x] The adapter is exercised with database-shaped fakes through selection,
  role gating, evidence thresholds, compact persistence, and endgame routing.
- [x] Existing focus, endgame, and coach-memory integration-facing regressions
  pass in the focused suite above.
- [ ] A live ASGI + Mongo integration run is attached.

The local Python environment cannot import the full auth router because
`bcrypt` is not installed locally; it is pinned in
`backend/requirements.txt`. Local Mongo and the API process are not running,
so no live endpoint call was simulated or redirected to production.

## Layer 3 — End-to-end

- [ ] A staging end-to-end curriculum journey has been exercised.
- [ ] Screenshot or execution evidence is attached.

The production bundle was prepared and a localhost browser fixture was started,
but the Codex browser launcher failed before opening a tab with Windows OS
error 206. This is launcher/path-length infrastructure evidence, not a product
pass or failure. Mohit's final desktop/mobile audit with representative
600-1500 players and coaches remains the acceptance evidence before the role
cohort is expanded.

## Engineer's self-declaration

I confirm the evidence above reflects commands that actually ran. Unchecked
items are explicit: repository-wide green, live ASGI/Mongo integration, and
staging/manual E2E are not claimed.

**Signed:** Codex
**Date:** 2026-08-29

---

## Mohit's gate — QA lead, fills in last

**Verdict:** ☐ Approved   ☐ Approved with follow-up   ☐ Rejected — needs rework

**Notes:** Default-off deployment can be reviewed independently from enabling
the role cohort. Do not expand the cohort until the representative-player and
coach sessions are recorded.

**Follow-up items:**

| Item | Owner | Due |
|---|---|---|
| Desktop/mobile representative-player and coach acceptance | Mohit + coaches | Before cohort expansion |
| Live post-deploy smoke test with flag off, then configured test role | Deployment owner | Deployment window |

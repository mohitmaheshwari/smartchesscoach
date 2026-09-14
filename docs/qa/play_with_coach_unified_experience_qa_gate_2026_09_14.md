# QA Gate — Unified Play with Coach experience

**Repo:** smartchesscoach
**PR / Branch:** `codex/play-with-coach-unified-experience-scope` at `ddc8e984`
**Engineer:** Codex
**Date:** 2026-09-14
**Mode:** ☒ Production   ☐ Prototype

---

## Prototype vs Production — pick one

This is a real user-facing coaching path, protected by a default-off rollout flag. The full three-layer gate applies.

---

## Result

- **Isolated staging feature verdict:** PASS.
- **Production deployment verdict:** HOLD.
- **Why production is held:** the pre-existing combined production Compose project is invalid, remote post-deploy smoke testing has not run, and human UAT has not signed off.
- **Data boundary:** the validation database was synthetic and explicitly tagged as containing no real player state. No production data or PII was copied.
- **Branch integrity:** rebased after `origin/working-code` advanced during QA; final divergence was `0 behind / 6 ahead` before this evidence-only commit.

## Component(s) touched

| Component | Files / paths touched |
|---|---|
| PWC rollout and API contracts | `backend/services/pwc_experience.py`, `backend/routes/coach_play.py`, Compose environment wiring |
| Personal coaching context | `backend/services/focus_bridge.py`, session context projection |
| Unified live decisions and postgame | `backend/services/unified_pwc_coaching.py`, PWC session model and observability |
| Two-mode frontend journey | `frontend/src/pages/CoachPlay.jsx`, `frontend/src/components/coach/*`, `frontend/src/coachFlow/*` |
| Responsive presentation | `frontend/src/styles/pwc-theme.css`, activation/setup styling |
| Automated staging canary | `frontend/scripts/validate-pwc-unified-staging.mjs` |

---

## Defects found during staging and fixed

| Defect | Resolution and proof |
|---|---|
| Rollout flags were not passed into deployed services | Added default-off Compose pass-through and contract coverage. |
| Production app service dropped canonical coaching-context flags | Added both context flags to the production service contract. |
| Existing users with a missing `role` could be eligible for PWC but receive no coaching context | Normalized a blank role to ordinary `user`; regression test and live API verification pass. |
| Legacy setup flashed while the experience contract loaded | Replaced it with a neutral “Preparing your game…” state; component test passes. |
| Light-mode activation contrast was broken | Corrected light background, shell, and secondary surfaces; browser capture reviewed. |
| Unified postgame showed duplicate actions | Board remains visible but its legacy postgame controls are suppressed; browser gate requires exactly one panel action. |
| Resignation showed a generic toast competing with the coach | Suppressed the legacy resignation toast only for unified sessions. |
| A resumed-session toast could linger into a unified postgame | Suppressed that legacy toast for unified sessions; lifecycle regression passes. |
| Resignation dropped the player's active focus from postgame | Both natural endings and resignation now use the same deterministic summary builder; backend regression and live journey pass. |
| Generated copy read “a clear keep the piece…” | Replaced label interpolation with plain, honest evidence language. Voice audit: no unexplained jargon, no evaluation/material confusion, reusable instruction remains visible, and no new parallel caption path was added. |
| Mobile coach sheet could briefly cross the fixed navigation during entrance animation | Removed the mobile shell transform that changed the fixed containing block; CSS contract passes and the browser journey passed twice consecutively before the final rebase and once again after it. |

---

## Layer 1 — Unit tests

- [x] New/changed logic has unit tests covering it.
- [x] Full frontend unit suite passes.
- [ ] A separate clean-base suite was not rerun. Instead, the full feature-branch frontend suite and the broad backend suite including every test touched by the two newly rebased base commits were run. No test failed in either run.

**Post-rebase backend command + real output:**

```text
docker run --rm -v C:\Users\MIISCO\smartchesscoach\_pwc_scope_audit:/app \
  -w /app/backend smartchesscoach-backend:latest \
  python -m pytest \
  tests/test_unified_pwc_coaching.py \
  tests/test_pwc_analysis_completion.py \
  tests/test_pwc_first_session_funnel.py \
  tests/test_pwc_gap_enrichment.py \
  tests/test_pwc_skill_gate.py \
  tests/test_pwc_unified_background_contract.py \
  tests/test_pwc_unified_experience_contract.py \
  tests/test_pwc_unified_observability.py \
  tests/test_coaching_context_contract.py \
  tests/test_coaching_context_validation_seed.py \
  tests/test_free_capture_recapture.py \
  tests/test_review_truth_layer.py \
  tests/test_coach_memory_concept_bridge.py -q

148 passed, 3 warnings in 39.36s
```

The three warnings are dependency deprecations (`python_multipart`, `crypt`, and Pydantic class configuration), not test failures.

**Post-rebase frontend command + real output:**

```text
CI=true npm test -- --watchAll=false

Test Suites: 65 passed, 65 total
Tests:       288 passed, 288 total
Snapshots:   0 total
```

**Production build command + real output:**

```text
CI=true npm run build

Compiled with warnings.
The build folder is ready to be deployed.
```

Build warnings are the existing `chess.js` source-map lookup, stale Browserslist data, and bundle-size advisory.

---

## Layer 2 — Integration tests

- [x] Frontend ↔ API, API ↔ isolated MongoDB, rollout ↔ coaching-context, end-session ↔ unified-summary, and responsive shell ↔ fixed navigation are covered.
- [x] Integration and live API flows pass.
- [x] Newly found failure modes have regression coverage.

**Isolated staging topology:**

```text
Frontend: http://127.0.0.1:3001
API:      http://127.0.0.1:8010
MongoDB:  chessguru_pwc_stage on an isolated Docker network
Flags:    PWC_UNIFIED_EXPERIENCE_V1_ENABLED=true
          COACHING_CONTEXT_V1_ENABLED=true
```

The API health endpoint returned:

```json
{"status":"healthy","database":"connected","git_commit":"unknown"}
```

No `ERROR`, traceback, or exception appeared in the API logs during the final 15-minute inspection window.

**Dedicated live API flow:**

```text
docker exec -e REACT_APP_BACKEND_URL=http://127.0.0.1:8002 \
  chessguru-pwc-stage-api python tests/test_coach_play_flow.py

ALL TESTS PASSED
```

This exercised start, real moves, engine reply, live feedback, opening guidance, position reading, resignation, Italian curriculum detection, and wrong-move feedback.

**Repository-mandated full-flow script:**

```text
RESULTS: 34 passed, 2 failed
COACH PLAY (core): 9/9 checks passed
```

The two failures are outside this PWC change and are recorded rather than waived silently:

1. `Coach review` expects an endpoint that intentionally returns HTTP 410 because it was retired.
2. `Has positions` expects seeded community training data; the deliberately empty isolated database contains zero positions.

---

## Layer 3 — End-to-end

- [x] A real browser drove the isolated staging frontend and API at desktop and mobile sizes.
- [x] Screenshots and a repeatable canary script are attached.

**Final post-rebase command + real output:**

```text
PWC_STAGING_EXPECTED_FOCUS="Keep the piece you move safe" \
PWC_STAGING_EXPECTED_INSTRUCTION="Before you move a piece, check whether it can be captured on its new square." \
node scripts/validate-pwc-unified-staging.mjs

{"status":"pass", "mobile":{"viewport":"390x844"}, "desktop":{"viewport":"1440x1000"}}
```

The canary used headless Chrome and real board clicks. It verified:

- exactly two setup modes, with Coach defaulted and no legacy flash;
- a real `e4` move and engine reply in Coach mode;
- “Explain their move” works without a second coaching surface;
- Play mode remains silent: no Ask Coach action and no live teaching;
- the same exact focus and instruction appear in setup, live play, and postgame;
- resignation keeps the board visible and presents exactly one next action;
- no horizontal overflow or mobile navigation overlap;
- no uncaught browser error, console error, or `/api/coach/play/*` response at 400 or above.

**Visual evidence:**

- [Desktop setup](pwc-unified-staging-setup-desktop.png)
- [Desktop live Coach](pwc-unified-staging-live-coach-desktop.png)
- [Desktop postgame](pwc-unified-staging-postgame-desktop.png)
- [Desktop Play mode](pwc-unified-staging-live-play-desktop.png)
- [Mobile setup](pwc-unified-staging-setup-mobile.png)
- [Mobile live Coach](pwc-unified-staging-live-coach-mobile.png)
- [Mobile postgame](pwc-unified-staging-postgame-mobile.png)
- [New-player setup](pwc-unified-staging-new-player-desktop.png)

The final desktop and mobile postgame captures were also inspected visually after the automated run. The coaching copy, focus continuity, action hierarchy, board visibility, and mobile navigation clearance were all acceptable.

---

## Release blockers and required next validation

1. **Production Compose is invalid.** `docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet` fails with `service "frontend" has neither an image nor a build context specified`. The `frontend` service is present on `origin/working-code`, so this was not introduced by the PWC branch. The base Compose file validates successfully with synthetic required variables.
2. **Remote post-deploy smoke has not run.** This was an isolated local staging canary; no remote deployment was performed.
3. **Human UAT is not complete.** A real player must verify that Coach mode feels helpful, Play mode truly feels uninterrupted, and the postgame recommendation feels earned.
4. **No load/performance or formal accessibility audit was performed.** The gate covers functional, responsive, network, console, and visual behavior.

The rollout flags remain default-off, so these blockers do not expose unvalidated behavior to users.

---

## Engineer's self-declaration

I confirm the above reflects what actually ran, and every unchecked or failing item has a stated reason. I do not recommend a production deployment until the production Compose project validates and post-deploy smoke plus human UAT are complete.

**Signed:** Codex  **Date:** 2026-09-14

---

## Mohit's gate — QA lead, fills in last

**Verdict:** ☐ Approved   ☐ Approved with follow-up   ☐ Rejected — needs rework

**Notes:**

**Follow-up items (if any):**

| Item | Owner | Due |
|---|---|---|
| | | |

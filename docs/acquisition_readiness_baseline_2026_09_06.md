# ChessGuru Acquisition Readiness — Frozen Baseline

**Baseline date:** 2026-09-06

**Status:** FROZEN BEFORE IMPLEMENTATION

**Product source:** `origin/working-code` at `8b6e5ac34580e63d971e359eb18e911ff993f9a4`

**Production source:** `/api/health` returned healthy, database connected and commit `900f6d0cf152196ce595252a198b2fa1b1fc5407` at 2026-09-06 12:20 UTC

**Scope:** `docs/acquisition_readiness_program_scope.md`

**Retention snapshot:** `backend/data/corpus_snapshots/acquisition_retention_baseline_2026-09-06.json`

This document prevents the program from forgetting an uncomfortable finding, changing a denominator after seeing results, or raising a score because code was written. A finding closes only when its named closure evidence exists and an independent reviewer accepts that evidence.

## Evidence states

- **VERIFIED CURRENT:** reproduced against the canonical source or live production during this baseline.
- **REPRODUCED WITH CAVEAT:** the number or behavior reproduced, but the cohort, authority or interpretation is not clean enough for a product claim.
- **HISTORICAL VERIFIED:** supported by an earlier dated artifact and preserved, but must be rechecked before a current release claim.
- **PENDING REPRODUCTION:** credible lead that cannot yet change a score.
- **CLAUDE LANE:** Claude is implementing the explicitly assigned fix; Codex must independently review it.
- **OPEN:** verified problem with no accepted closure evidence.

## Frozen scores — never averaged

### Codex acquisition review, 2026-09-06

| Lens | Score | Meaning |
|---|---:|---|
| Technology potential | 8.5/10 | The underlying evidence, deterministic coaching and closed-loop direction are unusually strong. |
| Current player product | 5.5–6/10 | Valuable capabilities exist, but coherence, reach, first value and ordinary-user completion are incomplete. |
| Acquisition diligence readiness | 3/10 | Security, privacy, billing, repository, dependency, licensing and reproducibility gaps block serious diligence. |
| Overall product | approximately 5.5/10 | Useful technology is not yet equivalent to a complete, trusted product. |

### Claude independent review, 2026-09-06

| Lens | Score | Meaning |
|---|---:|---|
| Engineering craft | 9/10 | Strong implementation and defensive evidence practice. |
| Evidence and verification discipline | 9/10 | Fail-closed grading and adversarial evidence are real strengths. |
| Architecture | 8/10 | Correct foundations, with integration and distribution debt. |
| Value delivered to actual users | 2/10 | Most coaching work does not reach ordinary players. |
| Release readiness | 3/10 | Last-wire failures and disabled/restricted value dominate. |
| Effort allocation | 3/10 | Detector refinement has outpaced distribution and product learning. |
| Overall as a product | 4/10 | Engineering quality materially exceeds demonstrated user value. |

These are different rubrics, not competing attempts at one number. Future reviews must score the same named lens against its own frozen meaning.

## P0 — live safety, truth and commercial survival

| ID | Finding and current evidence | State / owner | Closure proof |
|---|---|---|---|
| AR-SEC-001 | `backend/server.py:512` defines allowed origins, but line 525 configures `allow_origins=["*"]` with credentials. Live preflight from `https://evil.example` returned `200`, reflected that origin and allowed credentials. | **VERIFIED CURRENT · CLAUDE LANE** | Source uses one authoritative allowlist; unit/integration tests reject unknown origins; live evil-origin preflight has no readable credentialed permission; approved web/mobile origins still work. |
| AR-SEC-002 | `GET /api/admin/feedback/download/{filename}` has no auth dependency. A live unauthenticated request for a nonexistent filename returned file-state `404`, proving routing occurs before authorization. | **VERIFIED CURRENT · CLAUDE LANE** | Route requires admin auth before file lookup, traversal tests pass, unauthenticated live request returns `401/403`, authorized export still works, access is auditable. |
| AR-SEC-003 | Tracked `cohort.json` contains 45 unique email addresses and 45 names. `dq_report.json` is also tracked and needs direct-identifier disposition even though the current email regex finds zero addresses there. | **VERIFIED CURRENT · CLAUDE LANE** | Forward HEAD contains no unapproved direct identifiers; replacement evidence is anonymized; secret/PII scan passes; history rewrite versus retained-history risk is a separately approved decision. |
| AR-SEC-004 | Live HTML advertises `Server: nginx/1.24.0 (Ubuntu)` and returned none of the required HSTS, CSP, content-type, frame, referrer or permissions headers in the baseline HEAD request. | **VERIFIED CURRENT · CLAUDE LANE** | Live HTML and API header matrix passes at the authoritative nginx/app layers, server version is suppressed, and CSP is compatible with necessary assets without unsafe expansion. |
| AR-REPO-001 | Remote default is `origin/main`; it points to `8460f4e6` from 2026-02-11 and is 2,168 commits behind `origin/working-code`. | **VERIFIED CURRENT · CLAUDE LANE** | Hosting-provider default points to canonical current lineage; fresh clone checks out documented current product; branch protections and deployment source agree. |
| AR-COM-001 | The commercial retention signal is severe, but current authorities disagree. Narrow auth-session return shows 110/124 accounts with no later-day session. `last_login` shows only six recent accounts but exists for 38/125 users. Direct action sources show 32 recent accounts and lack uniform internal/test provenance. | **REPRODUCED WITH CAVEAT · CODEX** | One canonical server-observed user-action contract with actor/environment provenance; fresh-cohort D1/D7 baseline; target selected through data lock; no PostHog/pre-launch contamination; reviewer reproduces the query. |
| AR-COM-002 | 134/294 mature non-admin Play-with-Coach sessions (45.58%) contain fewer than two player moves. The reported 2.6% win rate reproduces only as 3/116 all-account games with at least ten player moves; that cohort includes internal/admin activity. A stricter non-admin/non-testish comparison records 0/18 wins and is too small for a rate claim. | **REPRODUCED WITH CAVEAT · CODEX** | Session provenance separates customers/internal automation; first/second/fifth-move survival is measured on a fresh cohort; opponent difficulty and resignation causes are observable; humane-game acceptance test and player-session evidence pass. |
| AR-BILL-001 | `billing.py` creates a one-time Razorpay order and then writes permanent `users.plan="pro"`. Terms and Refund promise recurring charges, cancellation, retries, paid-through access and expiry. The approved recurring scope confirms the lifecycle does not yet exist. | **VERIFIED CURRENT · CODEX, MOHIT DECISION REQUIRED** | Mohit chooses disable, relabel or recurring implementation. Pricing, checkout, entitlement, Terms, Refund and Settings then agree in source and live test mode; no browser request grants entitlement. |

## P1 — security, privacy and supply chain

| ID | Finding and current evidence | State / owner | Closure proof |
|---|---|---|---|
| AR-AUTH-001 | Browser routing accepts session tokens from query parameters and stores them in `localStorage`; backend register/login responses also return session tokens despite issuing cookies. URL/history, script compromise and persistent browser storage expand token exposure. | **VERIFIED CURRENT · CODEX** | Web auth uses secure HttpOnly/SameSite cookies; URL token exchange is one-time and immediately scrubbed where unavoidable; no normal web token persists in localStorage or JSON responses; mobile flow remains explicitly separated. |
| AR-PRIV-001 | PostHog uses identified profiles and session recording in `frontend/public/index.html`; public privacy text does not clearly disclose the processor/recording behavior or prove export, deletion and withdrawal workflows. | **VERIFIED CURRENT · CODEX + COUNSEL** | Data map and policy name the processor, purposes, retention and controls; masking/consent configuration is tested; export/deletion/withdrawal paths are implemented or claims corrected; counsel reviews final wording. |
| AR-SUPPLY-001 | Earlier scans reported 60 npm vulnerabilities (2 critical, 29 high) and 113 Python findings across 17 packages. Current canonical counts were not re-run with registry metadata during this baseline. | **PENDING REPRODUCTION · CODEX** | Pinned CI scans produce machine-readable current reports; each critical/high item is upgraded, removed or documented with exploitability, compensating control, owner and deadline; independent rerun agrees. |
| AR-LIC-001 | Maia2, Otter, Fathom, Stockfish, Syzygy/tablebase data, third-party chess content, community games and generated assets/code do not yet have one buyer-ready provenance and distribution record. | **OPEN · CODEX INVENTORY, COUNSEL DECISION** | Version, source, license, modification/distribution obligations, data rights and product-use decision exist for every material external asset; counsel resolves bounded unknowns. |
| AR-INFRA-001 | The canonical compose file now binds Mongo to `127.0.0.1`, while `docs/production_db_access.md` still states the public bind is live. This is documentation drift, and production closure evidence is not attached to the current baseline. | **HISTORICAL RISK / CURRENT CODE FIXED · CLAUDE LIVE PROOF** | Live port/firewall test proves Mongo is unreachable publicly, authenticated locally, and the document is updated with dated closure evidence. |

## P1 — reach, player experience and chess value

| ID | Finding and current evidence | State / owner | Closure proof |
|---|---|---|---|
| AR-REACH-001 | Historical runtime configuration limited major personalized surfaces to admin/super-admin/validation roles. Repository defaults still do not prove the current secret production manifest. | **HISTORICAL VERIFIED / CURRENT PENDING · CODEX + CLAUDE RUNTIME** | Credential-free runtime manifest, access decision and real non-admin journey prove who can reach Home → evidence → lesson → verdict → progress. |
| AR-REACH-002 | Phase 8 found zero non-admin active focus bundles before backfill despite 64 analyzed-game users, and only 12 with any Plan-grade firing evidence. The approved remedy is full stored-observation evaluation, eligible focus creation and denominator re-derivation. | **HISTORICAL VERIFIED · CODEX** | Deterministic dry-run/apply report classifies current/partial/missing/stale/ineligible/invalid; focus isolation holds; eligible denominator is frozen; ten full journeys complete. |
| AR-UX-001 | `App.js` exposes more than fifty routes, including overlapping game, review, training, opening, progress and legacy paths. The sidebar and deep-link structure do not consistently express one five-destination product. | **VERIFIED CURRENT · CODEX** | Home, Review, Learn, Play and Progress are the canonical destinations; legacy routes redirect or are contextual; navigation and browser-history E2E tests pass on desktop/mobile. |
| AR-UX-002 | Capabilities exist across Home, Review, lessons and progress, but first personal value is not one dependable golden path. Last-wire defects have included inert records, role gates and an interactive lesson board that did not return a verdict. | **HISTORICAL VERIFIED · CODEX** | A normal non-admin completes connect/import → verified finding → two personal examples → interactive lesson → explicit verdict → recorded attempt → honest progress without manual repair. |
| AR-UX-003 | Responsive and accessibility quality has not passed a complete current audit; browser automation is vulnerable to the Windows OS 206 runner failure, and earlier evaluation relied partly on source/screenshots. | **OPEN · CODEX + HUMAN UAT** | Keyboard, focus, contrast, zoom, screen-reader labels, board interaction and representative mobile breakpoints pass automated and manual evidence; browser runner or alternate environment is reproducible. |
| AR-UX-004 | Onboarding calls the documented but nonexistent `POST /api/games/sync`, discards the guaranteed failure, and continues as if linked games were imported. The actual registered importer is `POST /api/import-games`. | **VERIFIED CURRENT · CODEX** | Onboarding calls the existing importer with every verified account, stops visibly on import failure, emits the canonical privacy-safe import-complete event only after success, and component/static/live tests prove no silent path remains. |
| AR-CHESS-001 | Canonical reports contain many Shadow detectors and only a small Caption/Plan subset. Engineering inventory is materially larger than player-authorized value. | **VERIFIED CURRENT STRUCTURE · CODEX** | Every authorized detector has a named player consumer and reach counter; unused authorization is wired or intentionally retired; Shadow inventory has promotion/retirement decisions, not count-based progress. |
| AR-CHESS-002 | Hidden Opportunities has deterministic proof families, population evidence and Shadow runtime, but player interaction and later learning/transfer are incomplete. Target-line history contains critical truncation/quiet-check counterexamples that must remain regressions. | **VERIFIED CURRENT · CODEX** | Blinded promotion gate passes with zero critical false claims; try → hint → reveal → replay → recognition is player-ready; assisted/unassisted history and later-game transfer connect to the canonical ledger. |
| AR-CHESS-003 | Game Review often describes played moves but does not consistently teach the strongest memorable possibilities: opening ideas, opponent plans, traps, geometry, positional transformations, endgame facts and good decisions. Generic or terse captions remain possible. | **VERIFIED PRODUCT GAP · CODEX** | Stratified real-game review compares rendered output to engine/tablebase facts and coach rubric; key alternatives are verified and teachable; captions explain why and what to remember; no unsupported line reaches players. |
| AR-COACH-001 | Practice and progress machinery can record activity, but the complete loop is not yet proven for ordinary users from diagnosis through later unassisted transfer. | **VERIFIED PRODUCT GAP · CODEX** | Same focus/instruction across all five surfaces; assistance-aware checkpoint; later comparable decisions; `improving`, `still recurring` or `insufficient evidence`; ten-user Phase 8 gate. |

## P1 — engineering, operations and diligence

| ID | Finding and current evidence | State / owner | Closure proof |
|---|---|---|---|
| AR-QA-001 | Current CI directly invokes a pytest test requiring the `monkeypatch` fixture, and the broader backend run previously produced 26 failures and 24 errors before stopping. Some are live-server collection problems; others are genuine coaching assertions. | **VERIFIED CURRENT / RE-RUN REQUIRED · CODEX** | Fresh-checkout unit/integration/E2E commands are explicit; environment-dependent tests are provisioned or selected; no unexplained failures; CI executes the same commands. |
| AR-QA-002 | Frontend canonical dependencies now declare `@capacitor/core`, but earlier local full-suite execution failed because installed modules did not match the lockfile. CI covers only a narrow test subset. | **CURRENT MANIFEST FIXED / COVERAGE OPEN · CODEX** | Clean install from lockfile; all intended frontend suites pass; component/security/accessibility/E2E layers are named and enforced in CI. |
| AR-QA-003 | CI previously invoked the caption-source guard in warning mode and discarded its status. The source change now strictly scans changed backend Python files and propagates violations; the measured 176-line legacy inventory remains explicit migration debt. | **SOURCE + INDEPENDENT REVIEW COMPLETE · CODEX · CI RUN PENDING** | Guard returns meaningful status and blocks the release when its governed changed-file contract fails; intentional exceptions are explicit and tested; an actual CI run passes. |
| AR-ARCH-001 | The repository contains oversized orchestration and fact modules, duplicated/legacy routes and hundreds of services. Prior scan found 48 source files above 1,000 lines, including `coach_play.py`, `caption_facts.py` and `GameDecryptionV5.jsx`. | **HISTORICAL VERIFIED · CODEX** | Buyer-facing architecture map identifies authorities and boundaries; selected high-change chokepoints are decomposed with characterization tests; dead paths are removed only with usage evidence. |
| AR-REPO-002 | The original checkout is dirty and 133 commits behind canonical origin; the machine carries dozens of worktrees and branches, some with unique historical evidence. | **VERIFIED CURRENT · CODEX INVENTORY, CLAUDE PUSH** | Commit/file-level disposition ledger; no unknown unique changes; current clean worktree; obsolete worktrees pruned only after evidence; setup docs point to canonical branch. |
| AR-OPS-001 | Deployment script has strong commit/build/bundle/health/journey checks, and manual backups have been restore-tested. Automated offsite backup, RTO/RPO, SLO, alert, incident and capacity evidence is incomplete. | **PARTIAL STRENGTH / OPEN · CODEX + CLAUDE** | Recovery objectives are named; scheduled backup/restore evidence, alert test, rollback drill, capacity/cost measurement and incident runbook exist and are independently exercised. |
| AR-ACQ-001 | No single buyer-ready evidence room currently ties architecture, security, privacy, billing, licenses, metrics, operating procedures, model boundaries and known risks to reproducible artifacts. | **OPEN · CODEX** | Indexed, dated evidence room; no unsupported claims; one complete trace from stored chess fact to player result; independent technical reviewer can reproduce the central assertions. |

## What is already strong and must not regress

- Stockfish/tablebase truth is separated from interpretation and wording.
- Detector authorization fails closed and preserves historical evidence.
- Blinded and adversarial review is used for high-risk chess claims.
- Production credentials are read from the runtime environment rather than versioned files.
- `scripts/deploy.sh` stops on failed fetch, non-fast-forward state, failed builds, bad health and failed ordinary-user journey verification.
- Backups used for risky data changes have been restore-tested rather than merely created.
- The landing page clearly targets plateaued 600–1500 players and avoids a guaranteed rating claim.
- The intended coaching product is already locked: one coach, one focus authority, evidence before claims and later-game behavior before improvement.

## Findings discovered after the freeze

These findings were not used to lower the frozen score retroactively. They are
added here so later work cannot erase them.

| ID | Finding and current evidence | State / owner | Closure proof |
|---|---|---|---|
| AR-QA-004 | `package.json` declared Yarn and production built with Yarn, but the repository had no `yarn.lock`; its tracked npm lock both conflicted with React 19 through unused `react-day-picker@8.10.1` and was not consumed by production. The source now has one exact frozen Yarn authority across Docker, CI and the tracked publish path. | **SOURCE + INDEPENDENT REVIEW COMPLETE · CODEX · DEPLOYED PROOF PENDING** | The unused incompatible dependency is removed; one Yarn lock is versioned as the sole resolution authority; every tracked build path uses `--frozen-lockfile`; an empty-directory frozen install, all 30 frontend suites / 162 tests, the production build and independent review pass; deployed bundle proof remains. |
| AR-QA-005 | Phase 8's deployment verifier sent its ordinary web session as `Authorization: Bearer`, contradicting the mobile-only bearer boundary. The source now exercises every protected verifier route with the `session_token` cookie and no Authorization header. | **SOURCE COMPLETE · CODEX · LIVE/INDEPENDENT PROOF PENDING** | All verifier HTTP calls exercise the `session_token` cookie boundary; no Authorization header is sent; the preferred secret/CLI name says session cookie; the former secret/CLI input is accepted only as a temporary value alias; tests prove cookie-only requests and the strict deploy script forwards the cookie credential; independent and live strict-gate proof pass. |
| AR-QA-006 | The ordinary production frontend build succeeds with warnings, but the same build under `CI=true` fails on 71 `react-hooks/exhaustive-deps` findings across core Review, Play-with-Coach, board, opening and navigation surfaces. This debt predates the dependency-lock repair and may include stale-closure behavior, not just style noise. | **VERIFIED CURRENT · CODEX** | Review each finding behaviorally; fix or narrowly justify it; make the CI production build pass without globally suppressing the rule; rerun all frontend tests and interactive golden journeys. |
| AR-AUTH-002 | Google OAuth previously used unsigned request-derived state. The source now authenticates expiring state, binds it to an HttpOnly initiator nonce and permits only safe local redirect paths. | **SOURCE COMPLETE · CODEX · LIVE/INDEPENDENT PROOF PENDING** | Tampered, expired, missing-cookie and mismatched state fail before provider exchange; web and mobile return paths pass; independent review and live provider proof remain. |
| AR-AUTH-003 | `POST /api/auth/demo-login` previously lacked a `DEV_MODE` gate and could reuse a real account identity. The source now rejects production before database access and derives isolated non-email demo identities. | **SOURCE COMPLETE · CODEX · LIVE/INDEPENDENT PROOF PENDING** | Production returns `403` before database access; dev-only demo identities use a non-email hashed `demo_` id and cannot alias real accounts; any returned credential is explicitly mobile-only; security tests, independent review and live proof pass. |

## Score-change rule

For every future score:

1. The same lens and rubric are used.
2. The reviewer receives the frozen baseline, scope, diff and raw evidence, but not the implementer's desired score.
3. A fixed issue must have its named closure proof.
4. New regressions can lower a score even if planned work passed.
5. Claude reviews Codex changes; Codex reviews Claude's emergency lane; Mohit/coaches review player usefulness and chess teaching.
6. Deployment is not evidence of reach. A real ordinary-user journey is required.
7. Code volume, detector count and test count alone never raise product or value-delivery scores.

## Immediate execution order

1. Claude emergency lane: AR-SEC-001 through 004 and AR-REPO-001, with Codex independent review.
2. Metric authority: resolve AR-COM-001 and session provenance needed by AR-COM-002.
3. Billing truth decision: AR-BILL-001.
4. Reproducible security/dependency/CI baseline: AR-AUTH-001, AR-PRIV-001, AR-SUPPLY-001, AR-QA-001 through 003.
5. Phase 8 reach and golden journey: AR-REACH-001/002, AR-UX-001/002, AR-COACH-001.
6. Chess value and memorable Review: AR-CHESS-001 through 003.
7. Operations, architecture and buyer evidence room: AR-ARCH-001, AR-REPO-002, AR-OPS-001, AR-LIC-001, AR-ACQ-001.

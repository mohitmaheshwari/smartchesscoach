# QA Gate — Unified Coaching State production API E2E

**Date:** 2026-09-01  
**Mode:** Production  
**Production commit:** `a6caea2f87cb5437e060220216f18e024184a0e2`  
**Account:** `bhutramohit@gmail.com` (identity verified; credentials and private game data omitted)  
**Gate owner:** Mohit — this report does not self-approve rollout.

## 1. Scope

Validate the deployed exact destination-safety focus end to end for the enrolled account: authentication, Home, Learn/curriculum, all four canonical coaching contexts, prescribed training, PIC lesson grading, and blinded V5 Game Review.

Components exercised:

- FastAPI authentication and authorization
- Home dashboard and active-focus APIs
- canonical coaching-context projection
- personal curriculum selection
- exact-focus prescribed puzzle supply
- PIC lesson start/read/grade/idempotency
- V5 review regeneration and blinded A/B projection
- MongoDB v18 observation and exact-detector evidence

## 2. Layer 1 — unit evidence already run for this change

- Exact-focus backend group: **70 passed**
- Adjacent non-live backend group: **270 passed**
- Frontend exact-focus/experience group: **24 suites, 88 tests passed**
- Frontend production build: **passed** (pre-existing warnings only)
- Changed Python files: **34 compiled successfully**

These are the implementation-run results for the code deployed in the release. This production pass did not rerun the full repository suite.

## 3. Layer 2 — integration evidence

The deployment and backfill sequence had already proven:

- database backup restore-tested before mutation;
- code deployed before v18 backfill/migration;
- only the enrolled account migrated to the exact focus;
- read-only post-migration audit passed;
- `--all` deliberately not run.

The current production read found:

- **19,076** move observations, all schema v18 and all carrying `piece_safety.destination_safety_exact.v1`;
- **735** analyzed games represented;
- **2,883** exact eligible decisions;
- **193** exact detector fires.

This corrects the earlier deployment narration of “20,181 observations written.” The live collection contains 19,076. The 20,181 figure was a scanned/written-reporting mismatch, not the post-deploy stored count.

## 4. Layer 3 — production E2E API evidence

### Read-oriented flow

All expected HTTP contracts passed:

| Check | Result |
|---|---:|
| Health | 200 |
| Authenticated identity | 200, requested account verified |
| Home dashboard | 200 |
| Active focus | 200 |
| Personal curriculum | 200 |
| Home coaching context | 200 |
| Training coaching context | 200 |
| Play-with-Coach coaching context | 200 |
| Review coaching context | 200 |
| Prescribed exact training | 200 |
| No active PIC session | 404, correct fail-closed state |
| Unknown coaching surface | 404 |
| Anonymous active-focus request | 401 |

Contract findings:

- Home, Training, Play with Coach, and Review all returned the single Plan-authorized quality id `gap:piece_safety:destination_safety_exact`.
- All four surfaces returned one identical surviving instruction.
- Active focus returned the same exact quality id.
- Curriculum routed to piece-safety training.
- Public puzzle payloads exposed no solution, accepted move, best move, or admission-proof internals.

Two initial harness assertions were intentionally discarded as schema mistakes, not product defects:

- Home consumes focus through `/api/coach/active-focus`; `dashboard-v2` does not duplicate the quality id.
- `verified_admission` is deliberately stripped from the pre-attempt public puzzle payload, so per-puzzle quality ids cannot be asserted client-side.

### Reversible PIC lesson flow

A disposable production lesson was started, read, graded with a stored verified answer, replayed with the same idempotency key, and deleted.

- Start: 200
- Proof detector: `piece_safety.destination_safety_exact.v1`
- Public item hid private/internal ids
- Correct answer: 200, `correct=true`, `quality=best`, index advanced exactly once
- Duplicate submission: returned the same result and did not advance twice
- QA lesson record deleted
- QA authentication session deleted

### V5 Game Review flow

One real analyzed game was regenerated at current V5 version 140, because no current-version review existed for the account. The generated review is intentionally retained as user-visible product data.

- Generation completed after 3 API polls; all HTTP responses were 200
- Both blinded variants completed
- Both variants returned **71/71 captioned moves**
- Exactly one variant carried the personalized teaching plan
- Personalized projection contained **11 teachable events** and **11 structured reflection prompts**
- Both variants carried validation packets
- The A/B-to-mode mapping was not printed or disclosed
- Temporary QA authentication session deleted

## 5. Real defect found

### P1 user-value / coverage defect — exact training supply is artificially thin

Requesting 10 prescribed exact-focus puzzles returned **4**. Starting a five-position PIC lesson also returned **4**.

This is not a lack-of-evidence problem: the account has 193 exact fires across 735 analyzed games. The selection service only scans the latest 20 analyzed games when building own-game puzzles, so most verified opportunities are unreachable. Correctness is preserved, but the user gets less practice than the system already knows how to provide.

Required resolution before cohort rollout:

- page or index across verified exact opportunities instead of hard-limiting source analyses to 20;
- preserve solved filtering, current admission re-verification, answer redaction, and own-game priority;
- add a production-contract test that five requested PIC positions yields five whenever at least five unsolved verified exact fires exist.

## 6. Non-blocking gaps

- Play-with-Coach session start/move was not executed to avoid consuming or perturbing the account's daily coached-session entitlement. Its canonical context endpoint passed, but the live board/session loop still needs Mohit's manual pass.
- This API run proves delivery, consistency, authorization, grading, and structure. It does not replace human judgment of visual UX or whether every caption teaches well.
- The full repository test suite was not rerun in this production pass.

## 7. Engineer declaration

**API implementation score: 8.6/10.**

The core loop is real and coherent: one exact weakness, one instruction across four surfaces, verified answer grading, idempotency, answer privacy, and a functioning personalized review projection. It is not yet a 9/10 release because verified evidence is being stranded by the latest-20 puzzle query, producing four positions where the account has enough historical evidence for substantially more.

**Ready for Mohit's manual account pass:** Yes.  
**Ready for `--all` cohort migration:** No — resolve or explicitly accept the exact-training supply limitation first.

## 8. Mohit QA gate

- [ ] APPROVED FOR COHORT ROLLOUT
- [ ] FIX TRAINING COVERAGE AND RE-RUN
- [ ] HOLD

Decision / notes:


# QA gate and Claude handoff: frontend coaching journey

Repo: ChessGuru. Branch: codex/frontend-journey-integration-v1.
Engineer: Codex. Date: 2026-09-15. Mode: Production.
Runtime candidate: 8b95b280. Base: a979a691e110454f02c43a7301ebd2dc890591dc.

## Decision

Local integration passes. Authenticated E2E remains OPEN; this is not production acceptance.
Nothing pushed, deployed, enabled, migrated or written to production.
Claude retains push/deployment responsibility. Mohit's final QA approval remains pending.

## Isolation

Use this branch, NOT codex/frontend-coaching-room-v3 wholesale: that source branch
also contains separate community-study work outside this release.

| Source commit | Clean equivalent |
| --- | --- |
| cb4983fa | 4b94a7fd |
| 96061552 | a108287a |
| b242584b | 8b95b280 |

The only cherry-pick conflict was the community-only LabV2CommunityStudy test,
absent on the production base. It was excluded, not its underlying feature deleted.
The original remains in the source branch. Equivalent successful/failed personal
review save tests were added to LabV2KeyboardEffects.test.jsx.
LabV2's runtime diff is exactly a curriculum-cache import and invalidation after
successful persistence. No community runtime, detector, authorization or backend changes.

## Components

| Component | Change |
| --- | --- |
| Layout and index.css | Contrast, spacing, responsive layout, focus/skip navigation, reduced motion |
| AllGames and CurriculumHome | Consistent layout and landmark hierarchy |
| PersonalizedLessonWorkspace | Preserve final verdict; fresh next plan; retry and safe pause |
| UnifiedProgress | Distinguish fetch failure from insufficient evidence; preserve partial evidence |
| UnifiedCoachPanel | Keep action label and destination together; invalidate stale postgame plan |
| LabV2 | Invalidate plan only after successful review save |

## Layer 1: actual full-suite comparison

- [x] Changed behavior has tests.
- [x] Full frontend suite passes.
- [x] Compared with a freshly run clean baseline.

PowerShell, from frontend:

    $env:CI='true'
    npm.cmd test -- --watchAll=false --runInBand --json --outputFile=../frontend-candidate-test-results.json

Clean base: 66 suites passed; 302 tests passed; exit 0.
Candidate: 66 suites passed; 317 tests passed; exit 0.
No failed tests in either run. Name comparison: 16 additions and one replaced
broad postgame test, net +15. The replacement checks action destinations explicitly.
Raw JSON and candidate console log remain local at the worktree root, untracked.

## Layer 2: mocked integration

- [x] Affected component pairs have frontend integration coverage.
- [x] Integration tests pass as part of the full suite.
- [x] Failure paths exercised.

Lesson -> curriculum: completion refreshes stale plan and follows exact destination;
negative final verdict survives; failed next-plan request retries.
Lesson -> pause endpoint: HTTP/network failures keep the learner in the lesson.
Progress -> evidence/curriculum: HTTP/network/malformed responses show errors rather
than false learning judgments; partial evidence survives curriculum failure.
PWC summary -> navigation/cache: labels do not borrow unrelated destinations;
game end and arriving summary invalidate old plans.
Review -> save/cache: real completion button invalidates only after successful save;
failed save leaves the review open.
Layout -> navigation: named controls and skip destination.

These use mocked endpoints. They do not prove live backend behavior.

## Build

npm.cmd run build: exit 0.
JS: main.ae3bcd35.js. CSS: main.ba4efcc1.css.
Warnings: outdated browserslist data, missing dependency chess.ts source map,
and oversized main bundle (568.4 kB gzip). No dependency upgrade attempted.
git diff --check against origin/working-code: clean.

## Layer 3: authenticated E2E -- OPEN

- [ ] Real/staging end-to-end journey completed.
- [ ] Authenticated screenshots and request evidence attached.

Browser tool initialization failed (sandbox helper OS error 206).
Local database tunnel was reachable but the narrow account query returned Mongo
code 13, authentication required. No account documents were returned. No credentials
were extracted and no learning history was altered.
Earlier source-branch synthetic screenshots are not evidence for this account
or this integrated build.

## Handoff: remaining acceptance

1. Re-check current working-code before integration; preserve any newer work.
2. Independently review the three clean commits above. No flags or data jobs required.
3. Exercise on authenticated staging first, using an authorized test account:
   lesson move -> verdict remains visible -> completion -> exact next-plan destination;
   pause -> resume; review save -> refreshed plan; PWC end -> correctly labelled action;
   Progress error -> retry -> restored evidence.
4. Check mobile and desktop, light/dark, keyboard navigation and reduced motion.
5. Complete Mohit's account walkthrough with consent for any attempt writes;
   do not fabricate progress, mark a production lesson done, or auto-play on his behalf.
6. Only after acceptance, Claude can follow the normal deployment gate.
   Verify shipped assets and the actual authenticated route, not just build logs.
7. Roll back if verdicts disappear, navigation lands on a mismatched action, or failed
   requests look like learning judgments. This frontend release requires no DB rollback.

## Engineer declaration

Codex, 2026-09-15: the checked evidence above reflects actual local runs.
The unchecked E2E gate is explicitly unrun, not a passing inference.

## Mohit's gate

- [ ] Approved
- [ ] Approved with follow-up
- [ ] Rejected

Follow-up owner: Claude for independent integration review and authenticated E2E;
Mohit for real-user acceptance. Due: before production acceptance.

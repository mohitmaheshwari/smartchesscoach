# Acquisition Readiness Phase 6 - React Hook Behavior Final Evidence

**Date:** 2026-09-07

**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`

**Integrated range:** `0a932dc9..b0c89279`

**Status:** SOURCE AND INDEPENDENT REVIEW APPROVED - deployed browser proof pending

## Outcome

The strict inventory is reduced from 71 `react-hooks/exhaustive-deps`
findings across 30 source files to zero. This was not a mechanical dependency
addition. Each slice characterized the request, timer, listener, board, or
derived-state owner and then preserved that behavior with a focused test.

The work also closed concrete user-visible lifecycle failures discovered while
removing the warnings:

- an old route, account, game, position, opening lesson, or coach session can
  no longer publish a late response into the replacement view;
- Game Review actions and unsaved drafts stay with their exact game while an
  A/B variant reload remains safe;
- Reflect never asks a newly selected game about the prior game's move and
  never paints a late diagnosis into that game;
- Lab Classic navigation and autoplay use the currently parsed game, while
  analysis completion publishes one coherent replacement state; and
- Play with Coach timers and listeners call the latest committed handlers;
  evaluations, move commits, coach-response polls, active-session discovery,
  and reflection cards cannot cross a session replacement; and trap deep
  links start lessons only for the committed session;
- Lab Classic has one re-analysis poll owner, recognizes the backend's real
  `queued` / `already_queued` contract, and publishes completion only when
  both the analysis and Lab payload refresh successfully.

No ESLint rule or build configuration was weakened. A mechanical diff scan of
`frontend/src` across the integrated range found no added `eslint-disable` or
`exhaustive-deps` suppression.

## Final automated evidence

```text
focused CoachPlay lifecycle:      2 suites / 9 tests passed
focused Reflect lifecycle:        1 suite / 5 tests passed
focused Lab Classic lifecycle:    1 suite / 6 tests passed
cross-surface lifecycle matrix:  21 suites / 66 tests passed
complete frontend suite:         51 suites / 228 tests passed
strict CI production build:       exit 0 / 0 hook findings
ordinary production build:        exit 0
git diff --check:                 pass
added lint suppressions:          0
```

Both production builds retain one dependency-source-map notice for
`node_modules/src/chess.ts` and the existing bundle-size advisory. Neither is
a React hook finding or an application-source compilation failure.

## Discrimination and review

- Game Review correction `82239628` is independently approved. Its focused
  tests fail on the pre-correction source for the reviewed defects.
- Reflect correction `c3a98e3f` is independently approved. Its five-test
  suite produces three failures on exact parent `6f8f6531`: wrong-game move
  detail, stale gap continuation, and stale submission paint.
- The first independent review withheld Lab Classic `6f8f6531` and Play with
  Coach `1f95efb7` for unowned re-analysis, move-evaluation, move-commit,
  response-poll, active-discovery, and reflection paths. Correction
  `7d2ddf93` added exact-owner guards and discriminating delayed-response
  tests. Re-review then found that the backend's real `queued` response was
  outside the poll-state vocabulary; `b0c89279` normalizes both real queued
  states and proves the positive completion path.
- Final independent re-review approved exact tip `b0c89279`: CoachPlay's two
  focused suites pass 9/9 and Lab Classic passes 6/6. Transplanting the new
  high-risk tests to their pre-correction parents fails the old-evaluation,
  late-active-discovery, late-coach-response, stale-reanalysis,
  false-completion, and queued-contract cases. The reviewer found no remaining
  blocking source defect in the requested lifecycle corrections.

## Boundary before external testing

The existing legacy Playwright files hardcode a remote preview host and create,
move, resign, and clean up real coach sessions. They were not treated as a
safe local gate for this source branch. The deterministic React journey matrix
above covers the changed lifecycle boundaries without external writes.

After Claude integrates and deploys the reviewed commits, the remaining gate
is a real browser pass on the exact deployed bundle: route changes, account
changes, game replacement, Review navigation, Reflect game switching, Lab
autoplay, Play-with-Coach resume, and trap deep-link entry. That deployed
ordinary-user evidence is separate from source completion and remains required
before acquisition-readiness or reach scores change.

No backend, database, production flag, push, deployment, or product-score
change is included in Phase 6.

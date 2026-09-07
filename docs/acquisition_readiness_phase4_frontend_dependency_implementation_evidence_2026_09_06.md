# Acquisition Readiness Phase 4 — Frontend Dependency Implementation Evidence

**Date:** 2026-09-06

**Program:** `docs/acquisition_readiness_program_scope.md`

**Status:** SOURCE + INDEPENDENT REVIEW COMPLETE — deployed build proof pending

## Outcome

The frontend now has one reproducible dependency authority:

- `package.json` continues to declare Yarn 1.22.22;
- the first `yarn.lock` is versioned;
- the contradictory npm lock is removed;
- every tracked frontend Docker install path uses `yarn install --frozen-lockfile`;
- GitHub CI caches that same lock and installs/tests/builds with Yarn;
- the tracked legacy PowerShell publish path installs from that same frozen
  lock and rebuilds before any upload;
- the unused React-18-only `react-day-picker@8.10.1` dependency is removed;
  and
- its unreachable `src/components/ui/calendar.jsx` wrapper is removed.

No player-facing application behavior was intentionally changed.

## Why the implementation changed from the first pre-code hypothesis

The initial audit treated the npm lock as canonical because a clean `npm ci`
was the visible failure. Repository inspection then proved:

1. `package.json` explicitly declares `yarn@1.22.22`;
2. all three production Docker paths install with Yarn;
3. no `yarn.lock` existed; and
4. the npm lock was never the production resolution authority.

Keeping both locks would preserve two contradictory dependency truths. The
pre-code record was corrected before this implementation was finalized.

## Version selection

An unconstrained first Yarn resolution selected newer Radix minor versions.
`@radix-ui/react-avatar@1.2.6` imports the conditional
`@radix-ui/primitive/is-development` subpath, which the repository's Jest 27
resolver could not load. One suite failed before running its tests.

Every directly declared dependency is pinned to the exact version in the
previously passing committed npm graph, except the intentionally removed
`react-day-picker`. This includes the 27 Radix packages. The independent
review caught that the first draft preserved Radix but still allowed 15 other
direct packages—including React, the router, Recharts and Framer Motion—to
resolve newer. That draft was rejected before handoff.

These exact pins are not package upgrades. They prevent the new Yarn authority
from changing the already-tested direct dependency set while it is introduced.

## Verification

### Frozen install from empty state

A temporary directory inside the isolated worktree received only
`package.json` and `yarn.lock`. The generated `node_modules` in the source
tree was also removed after an absolute-path containment check, then rebuilt
with the exact Docker install command so the functional tests did not reuse
the former npm-installed tree.

```text
yarn install --frozen-lockfile --ignore-engines --non-interactive
Done in 190.13s.
exit 0
```

The resolved temporary path was checked to remain inside the isolated
worktree before recursive cleanup.

### Complete frontend test suite

```text
yarn check --integrity
success Folder in sync.

Test Suites: 30 passed, 30 total
Tests:       162 passed, 162 total
exit 0
```

### Production build

The same command used by production, without `CI=true`, completed:

```text
Compiled with warnings.
main JavaScript: 543.11 kB gzip
main CSS:         45.48 kB gzip
exit 0
```

The warnings include the existing chess.js source-map issue, Hook dependency
warnings and bundle size. They are not represented as green quality evidence.

### Strict CI probe

Running the build with `CI=true` fails on exactly 71
`react-hooks/exhaustive-deps` warning lines. That is recorded separately as
`AR-QA-006`; it is not caused by removing the unused calendar package.
Globally disabling the rule is not an accepted fix.

### Static and patch checks

- no `react-day-picker` reference remains in the frontend manifest, lock or
  source;
- production Dockerfiles no longer refer to `package-lock.json`;
- the tracked `frontend/publish.ps1` path cannot resolve an npm graph or upload
  a build without first running the frozen Yarn install and a fresh build;
- the removed calendar wrapper had no source import; and
- eight repository contract cases lock the single Yarn authority, exact direct
  version pins, removed
  dependency, all three frozen Docker install paths and the CI install path;
  and
- `git diff --check` is required immediately before the local commit.

## Remaining proof

1. Claude's deployment lane must prove the image builds from the committed
   lock and that the deployed bundle is produced by the expected commit.
2. The supply-chain phase must inventory and disposition the frozen graph;
   a successful install is not a vulnerability or license clearance.
3. `AR-QA-006` remains open and must be remediated in bounded behavioral
   groups.

## Change control

- no production write;
- no push;
- no deployment;
- no acquisition score increase; and
- no claim that dependency vulnerabilities are resolved.

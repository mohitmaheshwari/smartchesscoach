# Acquisition Readiness Phase 4 — Frontend Dependency Pre-code Audit

**Date:** 2026-09-06

**Program:** `docs/acquisition_readiness_program_scope.md`

**Status:** PASS — bounded dependency cleanup may begin

## Bounded slice

Make the canonical frontend reproducibly installable with the package manager
declared by `package.json` and used by production:

- remove `react-day-picker@8.10.1` from `package.json` and the lockfile;
- remove `src/components/ui/calendar.jsx`; and
- establish `yarn.lock` as the only dependency lock, remove the conflicting
  npm lock, and require frozen Yarn installs in every production Docker build;
  and
- make no React, router, build-system, component-library or application-source
  migration.

## Gate 1 — Verified current failure

**PASS.** A clean `npm ci` fails because `react-day-picker@8.10.1` declares a
React peer range ending at React 18 while ChessGuru declares and installs
React 19. `npm ls` reports the graph invalid for that exact peer edge.

Further inspection found the underlying reproducibility defect: `package.json`
declares Yarn 1.22.22 and production installs with Yarn, but no `yarn.lock`
exists. The tracked npm lock is therefore not the production resolution
authority, and npm and production resolve different trees. This is the broader
root cause behind `AR-QA-004`.

## Gate 2 — Reach and history evidence

**PASS.** Repository search finds `react-day-picker` only in the dependency
manifests and `src/components/ui/calendar.jsx`. No source file imports that
wrapper. The two `Calendar` icons found elsewhere are Lucide icons, not the
date-picker component.

Git history shows React 19 and react-day-picker 8 entered together in the
initial frontend commit; later Capacitor work did not introduce the mismatch.
The current installed graph shows React 19 support across the active UI
dependencies, with react-day-picker as the single invalid peer.

Therefore:

- downgrading React would be a broad unsupported product migration;
- upgrading react-day-picker would migrate an unreachable component and add
  maintenance without player value; and
- pinning `legacy-peer-deps` would conceal rather than resolve the invalid
  graph.

Removal is the smallest truthful repair.

## Gate 3 — Source-of-truth and numeric discipline

**PASS.** No domain authority or product threshold is added. `package.json`
already declares `yarn@1.22.22`, and all production Dockerfiles already invoke
Yarn. A generated `yarn.lock` therefore becomes the single resolved graph;
the unused npm lock is removed rather than maintained as a contradictory
second authority.

## Required verification

1. static search finds no `react-day-picker` or date-picker wrapper reference
   outside historical/evidence text;
2. a clean `yarn install --frozen-lockfile --ignore-engines` succeeds;
3. every production Docker build uses that same frozen lock;
4. the complete frontend test suite passes from that install;
5. the production build exits zero;
6. `git diff --check` passes; and
7. independent review confirms no reachable calendar UI was removed.

## Deferred work

This phase does not deliberately upgrade React, CRA, CRACO, router, Capacitor
or other direct packages; run a vulnerability remediation; redesign any page;
change runtime behavior; deploy; or raise a product/acquisition score. The
first Yarn lock necessarily freezes the versions resolved from the already
declared semver ranges; that complete graph is evidence for the later
supply-chain phase, not proof that the graph is vulnerability-free.

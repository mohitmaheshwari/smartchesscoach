# Acquisition Readiness Phase 5 — Caption Guard Pre-code Audit

**Date:** 2026-09-06

**Program:** `docs/acquisition_readiness_program_scope.md`

**Status:** PASS — bounded prevention gate may be implemented

## Bounded slice

Make the existing caption-source guard capable of blocking new or edited
parallel chess-caption paths in CI.

This slice may:

- run the existing guard in `--strict` mode against backend Python files
  added, copied, modified or renamed by the push or pull request;
- remove the CI-level `|| true` that currently discards its status;
- fetch enough Git history to determine the changed-file boundary;
- add unit/runtime tests that prove the Git boundary, a governed violation's
  non-zero result and the workflow's status propagation; and
- correct stale acquisition-baseline states already proven by earlier phases.

It may not migrate existing caption engines, widen the guard's prose
heuristics, add blanket allowlists, suppress a failure, change player-facing
copy, deploy, or raise a score.

## Current evidence

`python backend/scripts/check_caption_sources.py --strict` currently finds
**176 lines** across legacy backend paths. Therefore a whole-tree strict flip
would make every build fail before those paths are migrated.

The current workflow is weaker in two independent ways:

1. it does not pass `--strict`, so the script returns zero on findings; and
2. it appends `|| true`, so even a future non-zero result is discarded.

## Options considered

### A. Whole-tree strict now

Rejected. It is mathematically guaranteed to fail on the measured 176-line
legacy inventory and would encourage blanket exemptions.

### B. Version a baseline fingerprint for all 176 findings

Rejected for this slice. A generated exception ledger would silently bless
unreviewed legacy prose and become a second architecture authority.

### C. Strictly scan changed backend Python files

Selected. It prevents the detected inventory from growing, forces an explicit inline
exception when a changed file legitimately owns prose, and leaves the existing
debt measurable rather than hidden.

### D. Keep warn-only behavior

Rejected. It does not close `AR-QA-003` and provides no release protection.

## Acceptance contract

1. CI checks out full history so its comparison base exists.
2. Pull requests compare with the PR base SHA; pushes compare with the event's
   before SHA.
3. An absent, all-zero or unavailable base compares Git's canonical empty tree
   with the head snapshot so even a one-commit/orphan lineage is fully scanned;
   an invalid or unavailable head fails closed. With the known legacy
   inventory, that full-tree comparison is intentionally red rather than
   silently under-scanning a new lineage.
4. Only added/copied/modified/renamed `backend/**/*.py` paths are passed.
5. No matching path is an explicit pass, not a fallback whole-tree scan.
6. A violating changed file makes the step and job fail.
7. A clean changed file passes.
8. `|| true` is absent from the governed invocation.
9. Unit/runtime tests lock base resolution, path discrimination, exit status
   and workflow wiring, and CI executes those tests on every run.
10. The 176 existing findings stay recorded as migration debt; this slice
    claims prevention, not architectural completion.

## Forecasted bottleneck

The first legitimate edit to a legacy caption-heavy file may fail because its
old lines are scanned together with the new change. The developer must then
centralize the prose or add narrowly reviewed line-level
`# allow-noncentral-caption` annotations. Broad file allowlisting is not an
accepted shortcut.

## Evidence required before commit

- focused guard tests pass;
- workflow YAML parses;
- a synthetic violating file produces exit 1 in strict mode;
- a synthetic clean file produces exit 0;
- the current whole-tree strict count remains reported as 176;
- an all-zero base against a one-commit repository selects its root files and
  blocks a governed violation;
- `git diff --check` passes; and
- independent review confirms the workflow cannot discard the guard result.

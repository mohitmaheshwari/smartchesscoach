# Acquisition Readiness Phase 5 — Caption Guard Implementation Evidence

**Date:** 2026-09-06

**Program:** `docs/acquisition_readiness_program_scope.md`

**Scope:** `docs/acquisition_readiness_phase5_caption_guard_precode_audit_2026_09_06.md`

**Status:** SOURCE COMPLETE — CI execution and independent review pending

## Outcome

The caption-source guard can now fail CI when a changed backend Python file
adds or carries chess-teaching prose outside the governed central caption
layer.

The workflow now:

- checks out full Git history;
- uses the pull-request base SHA or push `before` SHA;
- falls back to the repository root commit for an invalid or all-zero base;
- selects added, copied, modified or renamed `backend/**/*.py` paths;
- explicitly passes when that set is empty;
- invokes the existing guard with `--strict`; and
- does not discard the command status with `|| true`.

This is a prevention boundary, not a claim that caption architecture is fully
centralized.

## Data-locked boundary

Whole-tree strict mode currently returns exit 1 for exactly **176 lines** of
legacy prose outside the central caption layer. Making that inventory a
permanent allowlist or immediately blocking every build on it was rejected.

Strict changed-file scanning prevents the inventory from growing while
keeping the legacy debt visible. A touched legacy file may require
centralization or a narrowly reviewed line-level exception before it can
merge.

## Verification

Focused Phase 5 behavior and workflow tests plus the adjacent frontend
dependency workflow contract:

```text
13 passed in 0.50s
```

The five Phase 5 cases prove:

- noncentral chess-teaching prose is detected;
- an explicit line exception is narrow;
- strict mode returns 1 on a finding;
- warning mode is not confused with the CI contract; and
- workflow YAML parses and contains full-history, diff-bound, strict,
  non-discarding wiring.

Direct probes:

```text
strict scan of backend/tests/test_caption_source_guard_ci.py: exit 0
whole backend strict scan: exit 1, 176 findings
workflow YAML parse: OK
git diff --check: pass
```

## Remaining proof and debt

1. The actual GitHub CI job must execute on the committed branch and prove a
   clean changed-file set passes.
2. Independent review must challenge the base-SHA, path-selection and failure
   propagation logic.
3. The 176 legacy lines remain an explicit architectural migration backlog.
4. The existing guard intentionally uses tight heuristics, including the
   `import chess` signal; this phase does not claim that every possible prose
   bypass is recognized.

## Change control

- no player-facing copy changed;
- no production write;
- no push;
- no deployment; and
- no acquisition score increase.

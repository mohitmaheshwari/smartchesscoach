# Personalized Curriculum — push and deployment handoff

Date: 2026-08-30  
Branch: `codex/personal-curriculum-phase4`  
Worktree: `C:\Users\MIISCO\smartchesscoach\_phase4_worktree`

## Release state

- Development is complete in the isolated worktree.
- The branch is based on the local `origin/working-code` reference: **0 behind,
  3 committed changes ahead**, plus the completed uncommitted Phase 4 work.
- Nothing in this handoff is deployed.
- Do not collect files from the separate main working tree.
- No MongoDB migration is required. `learning_sessions` is written lazily.

## Rollout flags

The experience is intentionally default-off and requires both flags plus an
allowed role:

```text
PERSONAL_CURRICULUM_ENABLED=true
PERSONALIZED_TEACHING_ENABLED=true
PERSONAL_CURRICULUM_ROLES=admin,super_admin
```

Keep the role list restricted for the first invited validation. Add another
role only when every account with that role is intended to receive the feature.

Rollback is immediate: set either feature flag to `false` and restart the
backend. Existing learning-session evidence can remain stored; flag-off callers
return the legacy experience.

## What ships

- One board-first personalized workspace for verified openings, traps,
  endgames, and supported concepts.
- Three help choices: show it on the board, ask one question, or let the player
  try. A successful help choice is remembered for that concept only.
- Diagnose, notice, contrast, guide, recall, transfer, and retain delivery,
  while evidence credit remains tied to the underlying verified stage.
- Server-owned move and reason grading; answers remain private and transfer
  positions never reveal them.
- Honest states through `Can do alone`; no `Reliable` claim.
- Reviews after three newly analyzed games, with a 21-day check-in backstop.
- The same curriculum state on Home, Learn, Game Review, Progress, Lab, and
  Play with Coach.
- Offline truth gates for all **37 openings, 23 traps, and 20 endgames**.
- Fried Liver defense content repaired and mate-pattern skill visibility
  preserved through the canonical endgame owner.

## Verified before handoff

- Backend personalized/canonical/Engine 2 gate: **122 passed**.
- Adjacent offline opening/trap/endgame suites: **82 passed, 8 skipped**.
- Legacy async opening lesson suite: **5 passed**.
- Frontend focused suites: **5 suites, 11 tests passed**.
- Production frontend build: **succeeded**. Existing repository hook and source
  map warnings remain; no new file was named in those warnings.
- Modified Python modules compile successfully.
- Assembled FastAPI application imports successfully.
- `git diff --check`: clean except Windows LF/CRLF notices.
- Both changed JSON files parse successfully.

The repository's live HTTP `test_all_flows.py` was not pointed at production.
This Windows host has no MongoDB listening on `127.0.0.1:27017`; using the
production database to compensate would not test an isolated deployment and
would violate the release boundary. Route contracts and application assembly
were verified locally.

## Push/deploy sequence

1. Work only from the Phase 4 worktree above.
2. Review `git status --short` and commit the complete scoped change together;
   do not omit untracked validators, tests, components, snapshots, or docs.
3. Push `codex/personal-curriculum-phase4`.
4. Deploy backend and frontend from that exact commit with both flags enabled
   only for the invited role list.
5. Verify backend health and that a flag-off/non-allowed account still receives
   the legacy experience.
6. Verify an allowed account can open the recommended lesson, choose a reason,
   request each help type, complete a transfer item, and see the same state on
   Learn, Game Review, Progress, Lab, and Play with Coach.
7. Hand the deployed build to Mohit and the invited coaches for the final human
   coaching audit.

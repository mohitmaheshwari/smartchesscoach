# Personalized Curriculum — screenshot hotfix deployment handoff

Date: 2026-08-30
Branch: codex/piece-safety-lesson-hotfix
Worktree: C:\Users\MIISCO\smartchesscoach\_phase4_worktree

## Release state

- The original Phase 4 curriculum is already merged into working-code and
  deployed.
- This screenshot-driven correction is complete locally but is not pushed or
  deployed.
- The hotfix branch is based exactly on current origin/working-code: **0
  behind, 1 verified commit ahead**, with a clean working tree.
- Do not merge or redeploy the older codex/personal-curriculum-phase4
  branch. Push and deploy this hotfix from current working-code only.
- No MongoDB migration is required. A stored v1 lesson is retained as
  superseded; the next lesson start creates the corrected v2 session.

## Production defect reproduced

The reported position is:

    r1bq1rk1/bppp1pp1/p4nnp/8/1PBNP3/P1N2Q2/2P2PPP/R1B2RK1 w - - 0 1

White's knight on d4 is attacked by Black's bishop on a7 and has no defender.
The deployed lesson hid that concrete relationship behind generic answer
choices and always placed the correct generic answer first.

## What the hotfix changes

- Uses the existing shared find_hanging_pieces geometry; no second
  piece-safety detector or chess-truth source is introduced.
- Admits a piece-safety position only when it contains one verified hanging
  piece and the known solution actually resolves that danger.
- Asks the player to identify the exact piece and square before moving.
- Shows side to move, move number when known, source, and position count.
- Makes board help name and highlight both sides of the relationship:
  knight on d4 and bishop on a7 for the reported position.
- Accepts a move only when it resolves the named danger and remains
  engine-acceptable.
- Orders choices deterministically per position and never puts the expected
  answer first.
- Converts stored misconception codes to natural coaching language.
- Bumps the adapter to v2 and safely supersedes an active v1 session so Mohit's
  account does not keep receiving the stale screen after deployment.

## Rollout flags

The existing rollout flags remain unchanged:

    PERSONAL_CURRICULUM_ENABLED=true
    PERSONALIZED_TEACHING_ENABLED=true
    PERSONAL_CURRICULUM_ROLES=admin,super_admin

## Verified before handoff

- Self-contained backend curriculum/hotfix gate: **111 passed**.
- Focused frontend workspace test: **1 passed**.
- Production frontend build: **succeeded**. Only pre-existing repository
  source-map, hook-dependency, browser-data, and bundle-size warnings remain.
- Modified Python modules compile successfully.
- git diff --check: clean except Windows LF/CRLF notices.
- The screenshot FEN is a locked regression case, including d4/a7 help,
  non-first correct choice, mismatched-position rejection, move grading, and
  v1-session supersession.

Three unrelated test_pic_teaching_engine.py tests require a pytest async plugin
not installed on this Windows host. The repository's live HTTP
test_all_flows.py also requires a running local backend and stopped at its
first connection attempt. Neither failure executed hotfix code; both are
recorded as environment-inconclusive, not green.

## Push/deploy sequence for Claude

1. Use codex/piece-safety-lesson-hotfix in the worktree above.
2. Confirm git status --short is empty and the head commit is
   “Fix personalized piece-safety lesson diagnosis.”
3. Push the hotfix branch and merge that one commit into current working-code.
4. Deploy both backend and frontend from that exact merged commit. Both are
   required: the backend supplies the position-specific contract and the
   frontend presents it.
5. Keep the existing Phase 4 flags and invited role list unchanged.
6. Verify Mohit's URL starts a v2 session instead of resuming the stale v1
   session.
7. For the reproduced position, verify the page says White to move, asks which
   piece needs attention, does not put the knight answer first, and board help
   identifies the knight on d4 and bishop on a7.
8. Return the deployed commit and health-check result to Mohit for manual
   coaching validation.

Rollback remains immediate: disable either existing feature flag and restart
the backend. Superseded lesson history can remain stored.

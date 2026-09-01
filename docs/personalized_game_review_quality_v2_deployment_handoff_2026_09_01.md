# Personalized Game Review Quality V2 — Deployment Handoff

**Prepared:** 2026-09-01  
**Source worktree:** `C:\Users\MIISCO\smartchesscoach_quality_v2`  
**Branch:** `codex/personalized-review-quality-v2`  
**Base:** `7bc99da4ee61542ca9050dc7b698368045d07835`  
**State:** intentionally uncommitted; Codex did not push or deploy

## What this release changes

- Builds one typed chess cause from the legal board or from complete stored
  Stockfish continuations. It does not run Stockfish again and does not use an
  LLM as chess truth.
- Explains the concrete consequence in simple language, frames whether the
  game actually changed, and derives threat/safe-move/opportunity arrows from
  the same cause object.
- Asks reflection questions through stable option IDs, with labels naming the
  exact pieces and squares from the player's game.
- Keeps opening knowledge as enrichment; it cannot overwrite a concrete move
  explanation.
- Authorizes the new cause family for Caption only. It cannot claim recurrence,
  mastery, a knowledge gap, or prescribe a plan.
- Bumps `V5_COACHING_VERSION` from 138 to 139.

## Evidence gate

`backend/data/detector_gold/verified_single_game_cause_promotion_v1.json`
contains 70 manually accepted fires and 30 manually accepted abstentions over
44 games from the explicitly authorized account. It contains no email,
username, raw account ID, credential, engine run, LLM output, or database write.

Canonical-JSON SHA-256:
`ec8657bd04df24ed3ded49a981141c4c4d326889131eaa0f089cc51fdc2cba94`

## Verified test evidence

- Final consolidated backend gate: **245 passed**.
- Full mapped backend comparison: **324 passed, 7 failed**. The seven failures
  are the exact same failures on clean deployed commit `7bc99da4`: six broken
  historical caption-boundary fixtures and one async test with no
  `pytest-asyncio` plugin. Quality V2 adds no failure.
- Personalized-review generation/storage/route/rollback gate: **52 passed**.
- Frontend: **24 suites, 88 tests passed**.
- Production frontend build: **completed successfully**. Existing source-map,
  bundle-size and hook-dependency warnings remain warnings.
- `python tests/test_all_flows.py`: inconclusive because it requires a running
  localhost HTTP server; it failed on the first connection attempt.
- `test_adaptive_decryption_v5.py`: 145 neighboring tests passed; its 15 cases
  errored because `BASE_URL` was empty and it tried `/api/auth/dev-login`.
- `test_whats_running.py`: collection is environment-dependent and could not
  import `bcrypt` in the Windows runtime.
- Python compile, `git diff --check`, canonical evidence hash and sensitive-data
  scan all passed.

## Required release order

1. Review the diff from this worktree against `7bc99da4`; do not copy whole
   files from any older worktree.
2. Commit and push this isolated branch.
3. Deploy the code and set this flag in the same backend restart:

   ```ini
   PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED=true
   ```

   Keep the existing master and rollout values:

   ```ini
   PERSONALIZED_GAME_REVIEW_COACH_ENABLED=true
   PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT=validation
   ```

4. Confirm the existing validation enrollment still contains only the approved
   account. Do not broaden the cohort.
5. Open or call the V5 review endpoint for the approved account's reference
   games. The first read may return `generating`; poll until complete. Do not
   bulk-regenerate the full historical corpus.
6. Verify in storage for a regenerated reference game:

   - `decryption_v5_version == 139`;
   - `game_teaching_plan.formula_id == "E_transition_then_teaching"`;
   - `game_teaching_plan.deriver_identity` equals the current identity;
   - V2 events contain matching `cause`, `practical`, teaching fingerprint and
     relationship arrows;
   - unsupported moves fall back or remain silent without removing the whole
     review.

7. Run the blinded A/B review for the approved account and then begin Mohit's
   manual coach review. The player-facing score is not considered validated
   until that human pass is complete.

## Rollback

Set `PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED=false` and restart the backend.
Stored V2 events are rejected immediately. On the next enrolled-account read,
the route sees the formula mismatch, clears the stale caption/plan pair and
lazily regenerates the V1 plan. No database restore or code rollback is needed.

## Explicit non-actions

- No production deploy, restart, commit or push was performed by Codex.
- No production database write was performed.
- No fresh Stockfish evaluation or runtime LLM chess judgment was used.
- The temporary production validation overlay
  `/tmp/chessguru_quality_v2_validation_20260901` is confirmed absent.


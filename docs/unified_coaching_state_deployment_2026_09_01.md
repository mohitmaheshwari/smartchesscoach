# Unified coaching state — production handoff (2026-09-01)

## What this release changes

For an eligible player, one exact fact now drives the entire piece-safety loop:

- diagnosis: `piece_safety.destination_safety_exact.v1`;
- plan: one instruction — “After choosing your move, ask: can they take the piece I just moved?”;
- Learn/Training: only puzzles carrying `gap:piece_safety:destination_safety_exact`;
- Play with Coach: comparable destination-safety decisions use the same exact exchange result;
- Focus Game and later-game measurement: v18 exact decisions, misses, and handled decisions;
- rating: median of the last three chronologically parsed games on the player's explicitly selected platform.

No new Stockfish analysis is run. The v18 backfill re-derives deterministic facts from already-stored FENs, moves, cp-loss values, and stored continuations.

## Locked evidence

- Exact detector: 200/200 reviewed precision, Wilson lower bound 98.12%, 165/200 recall, 60/60 true negatives, 0/60 adversarial critical errors.
- Corpus: 166,681 observations scanned; 1,896 diagnostic fires; 2,320 independent positive opportunities.
- Mohit: enough exact own-game evidence to fill a five-position lesson without broad-topic filler.
- Rating bake-off: a three-game median had median next-game error 8 rating points and p90 error 18; longer windows were worse.

Evidence files:

- `backend/data/corpus_snapshots/destination_safety_exact_plan_promotion_2026-09-01.json`
- `backend/data/corpus_snapshots/canonical_rating_resolution_2026-09-01.json`
- `docs/destination_safety_exact_plan_promotion_2026_09_01.md`
- `docs/canonical_coaching_rating_lock_2026_09_01.md`

## Deployment order — do not reorder

Production currently has no v18 observations. Therefore the migration dry-run is meaningful only after the one-user v18 backfill has been applied.

1. Create and restore-test a backup containing at least `move_observations`, `user_active_focus`, `learning_sessions`, and `games`.
2. Deploy this code with the existing rollout flags unchanged. Confirm `/api/health` is 200.
3. Inside the new backend container, dry-run Mohit's observation backfill:

   ```bash
   cd /app/backend
   python scripts/backfill_move_observations.py --user-id user_8b599930d7ef
   ```

4. Inspect the dry-run, then write only Mohit's v18 observations:

   ```bash
   python scripts/backfill_move_observations.py --user-id user_8b599930d7ef --apply
   ```

5. Dry-run the focus migration. It must report exactly one scanned focus, one eligible user, at least three exact fires, and more than zero exact decisions:

   ```bash
   python scripts/migrate_destination_safety_focus.py --email bhutramohit@gmail.com
   ```

6. Only if step 5 satisfies those invariants, apply the migration:

   ```bash
   python scripts/migrate_destination_safety_focus.py --email bhutramohit@gmail.com --apply
   ```

7. Run the bounded read-only audit:

   ```bash
   python scripts/audit_unified_coaching_state.py --email bhutramohit@gmail.com
   ```

8. Do not run `--all` yet. Mohit and the coaches complete the manual product pass first. Cohort backfill/migration is a separate rollout decision.

## Required post-deploy invariants

The audit and authenticated API checks must agree on all of these:

- canonical rating reports `source=recent_game_median`, `platform=chess.com`, and `sample_games=3`, not Lichess or the stale player profile;
- active focus quality ID is `gap:piece_safety:destination_safety_exact`;
- focus kind is `piece_safety/destination_safety_exact`;
- proof detector is `piece_safety.destination_safety_exact.v1`;
- Home, Review, Training, and Coach Play all return the same primary focus ID and instruction;
- `/api/coach/personal-curriculum` selects that repair, not an unrelated endgame;
- `/api/training/prescribed/piece_safety?num_puzzles=10` returns no puzzle whose `verified_admission.quality_id` differs from the exact quality ID;
- `/api/training/pic/session/start` reports the exact proof detector and never resumes a legacy broad session;
- Play mode exposes no coaching context; Coach mode does;
- no other user is migrated or newly enrolled during this one-account pass.

Useful authenticated reads:

```text
GET /api/coach/active-focus
GET /api/coach/coaching-context/home
GET /api/coach/coaching-context/review?game_id=<latest_analyzed_game_id>
GET /api/coach/coaching-context/training
GET /api/coach/coaching-context/coach_play
GET /api/coach/personal-curriculum
GET /api/training/prescribed/piece_safety?num_puzzles=10
POST /api/training/pic/session/start        {"limit": 5}
```

## Rollback

If any invariant fails, stop before cohort work. Restore the four backed-up collections or revert only Mohit's `user_active_focus` and v18 `move_observations` from the tested backup, then redeploy the previous application commit. Do not “fix” a failed rollout by lowering the detector-quality gate or allowing broad puzzle fallback.

## Verification completed before handoff

- Backend non-live adjacent regression: 270 passed.
- Unified exact focus contract set: 70 passed.
- Frontend: 24 suites, 88 tests passed.
- Production frontend build: completed successfully (existing repository warnings only).
- Changed Python files: 34 compiled successfully.
- `git diff --check`: clean.

The legacy HTTP test modules still require a running `BASE_URL`; their missing-URL failures are environmental and were not counted as release evidence.

# Phase 8 Release Rescue+�u���T deployment handoff

Date: 2026-09-04
Owner of push and production deployment: Claude
Owner of implementation and tests: Codex

This is an operational runbook, not authorization to mutate production. Each
apply step remains a separate explicit decision. Do not combine the apply
commands into one script and do not use `--all` where the command requires an
exact user or game.

## Release invariants

- Start from a clean server checkout fast-forwarded to `origin/working-code`.
- Backup and restore-test MongoDB before the first write.
- Build candidate images without restarting the current production services.
- Keep `COMPLETE_COACHING_SYSTEM_V1_ENABLED=false` until the target, verifier
  baseline, verifier enrollment and fixture are ready.
- No Stockfish run, detector change, model call or unrelated learner-state
  write is part of reconciliation.
- No admin or super-admin account may satisfy the non-admin journey check.
- The eligible denominator comes only from full-corpus, post-apply,
  idempotency reports.
- Ten is provisional. Freeze no absolute target until Mohit sees the measured
  denominator and explicitly confirms or restates the number.
- A passing build or HTTP 200 is not a release. `scripts/deploy.sh` must finish
  all strict checks with zero failures and zero required skips.

## 1. Backup, restore proof and clean checkout

Use the already-proven production backup procedure in
`docs/production_db_access.md`. Record the backup path, document counts and
restore-test result. A dump that exists but has not restored documents into a
scratch database is not a verified backup.

Stop if:

- restore reports zero documents or any failure;
- the scratch counts do not reconcile with the dump;
- the server worktree has tracked changes;
- fast-forward to `origin/working-code` fails.

After Claude pushes the reviewed Phase 8 commit:

```bash
git fetch origin
git merge --ff-only origin/working-code
git status --short
export GIT_COMMIT="$(git rev-parse HEAD)"
```

`git status --short` must be empty. Preserve the verified backup until the
pilot has passed manual review.

## 2. Build candidate images without deploying

Confirm the server configuration still has:

```text
COMPLETE_COACHING_SYSTEM_V1_ENABLED=false
PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT=validation
CAUSAL_PERSONAL_CAPTIONS_ENABLED=0
```

Then build only:

```bash
docker compose build backend analysis-worker frontend-builder
```

Do not run `docker compose up` and do not run `frontend-builder` yet. The
currently running backend, worker and public bundle must remain unchanged
during the prerequisite work.

Create a protected evidence directory outside the checkout:

```bash
export PHASE8_EVIDENCE_DIR="/root/phase8_release_evidence_$(date -u +%Y%m%d_%H%M%S)"
install -d -m 700 "$PHASE8_EVIDENCE_DIR"
```

All JSON files below are aggregate artifacts and contain no user, email, game,
PGN, FEN, credential or answer identifiers.

## 3. Reconcile stored destination-safety observations

Full-corpus dry run:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/backfill_move_observations.py \
  --all --report-json /evidence/observations-pre.json
```

Inspect `observations-pre.json`. It must say:

- `full_corpus: true`;
- `mode: dry_run`;
- current schema, fact version and quality ID;
- `errors: 0`;
- current, stale and missing storage counts separately;
- eligible, ineligible and invalid decision counts separately.

After separate approval, apply:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/backfill_move_observations.py \
  --all --apply --confirm phase8-observations \
  --report-json /evidence/observations-apply.json
```

Immediately rerun the dry run:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/backfill_move_observations.py \
  --all --report-json /evidence/observations-post.json
```

`observations-post.json` must have `writes_required: 0` and `errors: 0`.
Invalid positions may remain invalid; a valid missing or stale decision may
not remain unwritten.

## 4. Create valid missing focus bundles

Dry run the full non-admin cohort:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/migrate_destination_safety_focus.py \
  --all --report-json /evidence/focus-pre.json
```

Inspect the reason counts. `multiple_active_focuses` and
`invalid_existing_exact_focus` are stop-and-investigate states; the migration
does not hide them by selecting an arbitrary record. `active_focus_conflict`
is an honest exclusion and must not be overwritten merely to enlarge the
denominator.

After separate approval, apply only the reported eligible changes:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/migrate_destination_safety_focus.py \
  --all --apply --confirm phase8-focus-bundles \
  --report-json /evidence/focus-apply.json
```

Then prove idempotency:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/migrate_destination_safety_focus.py \
  --all --report-json /evidence/focus-post.json
```

Required postconditions:

- `full_cohort: true` and `non_admin_only: true`;
- `eligible: 0` on the post-apply dry run;
- `valid_bundles_after_run > 0`;
- the denominator includes only current, structurally valid,
  Plan-authorized exact-focus bundles whose users still have qualifying
  evidence.

## 5. Freeze the denominator and absolute target

First run the lock command without `--apply`, using the provisional candidate
of ten only to validate feasibility:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/lock_phase8_reach_target.py \
  --coverage-report /evidence/observations-post.json \
  --focus-report /evidence/focus-post.json \
  --completion-target 10 \
  --source-commit "$GIT_COMMIT" \
  --report-json /evidence/target-lock-dry.json
```

If the denominator is below ten, this command fails by design. If it is ten or
more, it still does not authorize the write. Send Mohit the measured
`eligible_denominator`, `qualifying_evidence`, proposed absolute target and
rationale. Wait for explicit confirmation of the final integer.

Only after that decision, rerun with the confirmed number and then apply it:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/lock_phase8_reach_target.py \
  --coverage-report /evidence/observations-post.json \
  --focus-report /evidence/focus-post.json \
  --completion-target <CONFIRMED_INTEGER> \
  --source-commit "$GIT_COMMIT" \
  --apply --confirm phase8-target-lock \
  --report-json /evidence/target-lock-applied.json
```

The lock is immutable. An existing different lock is a hard failure, not an
update opportunity.

## 6. Inventory and reconcile Game Review records

Full read-only inventory:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/reconcile_phase8_review_records.py \
  --report-json /evidence/review-reconciliation-all-pre.json
```

The six `game_states` must sum exactly to `games_inspected`. Inspect game and
move counts separately. `no_authorized_evidence` is not regenerated. Neither
are invalid or unowned rows.

Apply is deliberately scoped. Reconcile the dedicated verifier game first,
and later each explicitly selected pilot user or game, only after approval:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/reconcile_phase8_review_records.py \
  --game-id "$DEPLOY_VERIFY_GAME_ID" \
  --apply --confirm phase8-review-reconciliation \
  --report-json /evidence/review-verifier-apply.json

docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/reconcile_phase8_review_records.py \
  --game-id "$DEPLOY_VERIFY_GAME_ID" \
  --report-json /evidence/review-verifier-post.json
```

The scoped post-run must have `writes_required: 0`. Reconciliation uses stored
engine analysis and the canonical V5 generator, but explicitly disables LLM
polish, concept counters and pattern-memory replacement. It updates only the
current V5 review and teaching-plan fields in `game_analyses`.

## 7. Prepare the dedicated non-admin verifier

This must be a purpose-built non-admin verification account, not Mohit's
account and not a real learner. It must already own:

- a valid exact focus bundle from the preceding reconciliation;
- a reviewed game whose routed response contains at least one event with
  `display.authorized: true`;
- a stable piece-safety practice position with a known legal correct UCI move;
- a valid session token supplied only through server secrets.

If that fixture does not exist, stop and seed it deliberately. Do not point the
gate at an admin or a real learner to make deployment pass.

Capture one cutoff and reuse it for dry run and apply:

```bash
export VERIFY_CUTOFF="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/capture_phase8_baselines.py \
  --email "$DEPLOY_VERIFY_EMAIL" --cutoff "$VERIFY_CUTOFF" \
  --source-commit "$GIT_COMMIT" \
  --report-json /evidence/verifier-baseline-dry.json
```

After separate approval:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/capture_phase8_baselines.py \
  --email "$DEPLOY_VERIFY_EMAIL" --cutoff "$VERIFY_CUTOFF" \
  --source-commit "$GIT_COMMIT" \
  --apply --confirm phase8-baselines \
  --report-json /evidence/verifier-baseline-apply.json

docker compose run --rm backend \
  python scripts/configure_phase8_pilot.py \
  --email "$DEPLOY_VERIFY_EMAIL"
```

Inspect the enrollment dry run. Then, after separate approval:

```bash
docker compose run --rm backend \
  python scripts/configure_phase8_pilot.py \
  --email "$DEPLOY_VERIFY_EMAIL" \
  --apply --confirm phase8-pilot
```

The verifier fixture secret must be a JSON object matching the exact Home
destination and the selected board, for example:

```json
{"content_kind":"concept","content_id":"piece_safety","skill_id":"piece_safety_simple_hang","move":"<CORRECT_UCI>","game_id":"<OWNED_GAME_ID>"}
```

Do not commit the email, token, game ID or fixture JSON.

## 8. Enable composition and deploy through the only deploy path

Preserve the existing subsystem flags and role allowlists. Ensure server
configuration contains:

```text
PERSONAL_CURRICULUM_ENABLED=true
PERSONALIZED_TEACHING_ENABLED=true
PERSONALIZED_GAME_REVIEW_COACH_ENABLED=true
PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT=validation
COMPLETE_COACHING_SYSTEM_V1_ENABLED=true
CAUSAL_PERSONAL_CAPTIONS_ENABLED=0
```

Export the three verifier secrets in Claude's shell, then run:

```bash
export DEPLOY_VERIFY_AUTH_TOKEN='<SECRET_SESSION_TOKEN>'
export DEPLOY_VERIFY_GAME_ID='<OWNED_GAME_ID>'
export PHASE8_VERIFICATION_FIXTURE_JSON='<JSON_OBJECT>'
./scripts/deploy.sh
```

The deploy script must prove commit, public frontend bundle, health, auth,
canonical review, queue health, failure rate and the non-admin journey. The
journey checks the real serialized Home fields (`lesson_kind`, `lesson_id`),
starts that exact lesson, submits the same interaction twice, proves one stored
correct result, requires only authorized routed Review events and requires
Progress to keep practice separate from transfer.

Any FAIL or required SKIPPED result means the release is not live.

## 9. Bounded real-user pilot

Only after the strict deploy gate is green:

1. Choose the bounded pilot explicitly.
2. Reconcile each selected user's review records in an approved user-scoped
   run and prove the same scope has zero remaining writes.
3. Capture each baseline at one pre-enrollment cutoff.
4. Inspect baseline dry runs.
5. Apply baselines with `--confirm phase8-baselines`.
6. Enroll the exact emails with `configure_phase8_pilot.py`; dry run first,
   then `--apply --confirm phase8-pilot`.
7. Verify one real non-admin account manually before inviting the remainder.

An `insufficient_pre_period` user may receive coaching, but the reducer is
locked to `insufficient_evidence`; it cannot claim improvement without a
comparable pre-period.

Generate the identifier-free reach report at any time:

```bash
docker compose run --rm \
  -v "$PHASE8_EVIDENCE_DIR:/evidence" \
  backend python scripts/report_phase8_release.py \
  --report-json /evidence/reach-report.json
```

The first formal review is 42 calendar days after first enrollment. A
shortfall reports `pilot_incomplete`, keeps the absolute target unchanged and
separates user inactivity from product-path and evidence failures.

## 10. Manual product verification

For Mohit and the invited coaches, confirm:

- Home shows one personal focus and its CTA opens the exact assigned lesson;
- the board is interactive and every legal submitted move receives an
  explicit server verdict;
- refreshing or retrying does not duplicate evidence;
- Game Review shows authorized teaching moments and never Shadow facts;
- Progress distinguishes completed practice from later-game transfer;
- solving a lesson alone never says the weakness is fixed;
- an earlier unrelated Review visit does not permanently prevent a later
  valid chronological journey from completing;
- disabling Phase 8 shows the saved-work pause message rather than making the
  journey disappear.

## 11. Rollback

The fastest broad rollback is to set
`COMPLETE_COACHING_SYSTEM_V1_ENABLED=false` and restart only the backend. This
is an intentional rollback exception to the strict deploy gate, because the
gate correctly cannot pass while the feature is disabled. Existing baselines,
attempts, reviews and later-game evidence remain intact, and enrolled users
receive:

> Your lesson and progress are saved. Your coach is preparing the next step.

To pause exact accounts instead, dry-run and then apply:

```bash
docker compose run --rm backend \
  python scripts/configure_phase8_pilot.py \
  --email "$PILOT_EMAIL" --disable

docker compose run --rm backend \
  python scripts/configure_phase8_pilot.py \
  --email "$PILOT_EMAIL" --disable \
  --apply --confirm phase8-pilot
```

Never delete the target lock, baselines, lesson events or journey records as a
rollback mechanism. Use the verified Mongo backup only if a production write
violates the postconditions above.

## 12. Evidence to return after deployment

Return to Codex/Mohit:

- deployed commit and live bundle name;
- verified backup path and restore counts;
- observation pre/apply/post aggregates;
- focus pre/apply/post aggregates;
- measured denominator and the explicitly approved frozen target;
- six-way Game Review reconciliation counts and scoped post-apply proof;
- strict deploy summary with all eight checks;
- one real non-admin manual journey result;
- path to the identifier-free 42-day report artifact.

Only sanitized aggregate JSON may be copied into a later versioned evidence
commit. Keep all secret-bearing shell history and verifier identifiers out of
the repository.

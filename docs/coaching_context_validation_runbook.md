# Coaching Context V1 — Isolated Reviewer Runbook

Status: validation only. This is not a production rollout instruction.

## 1. Safety boundary

The reviewer database is exactly `chessguru_validation`. The seeder refuses
every other name, including `test_database` and `chess_coach`. It never reads
another database, and every mutable fixture document carries:

```text
validation_fixture_set = coaching_context.v1.2026-08-28
```

The reset path deletes only documents carrying that exact tag. It never drops
a collection or database. The fixture validator refuses credential, external
chess-account, OAuth, and payment identity fields.

Do not point the validation backend at the production application database.
Do not use a production player's user ID as `DEV_USER_ID`.

## 2. Scenarios

| Synthetic user | Expected coaching state | Reviewer question |
|---|---|---|
| `validation_ctx_no_focus` | `no_focus` | Does the coach admit it needs evidence instead of guessing? |
| `validation_ctx_primary` | `primary_only`; Review `observed` | Is one instruction identical across Home, Review, Training, and Coach Mode? |
| `validation_ctx_no_opportunity` | primary focus; Review `not_observed` | Does the coach avoid calling an untested game an improvement? |
| `validation_ctx_unauthorized` | `no_focus` | Does a Shadow detector fail closed? |
| `validation_ctx_missing_instruction` | `evidence_pending` | Does the coach avoid inventing teaching text? |

The corresponding game IDs are `validation-game-no-focus`,
`validation-game-primary`, `validation-game-no-opportunity`,
`validation-game-unauthorized`, and `validation-game-missing-instruction`.

## 3. Snapshot before a validation run

The database contains synthetic fixtures only, but take a recoverable snapshot
before changing them:

```bash
docker exec chess-coach-mongodb mongodump \
  --db chessguru_validation \
  --archive=/backup/chessguru_validation_before_context_v1.archive
```

If inspection is needed, restore into a separate name instead of overwriting
the validation database:

```bash
docker exec chess-coach-mongodb mongorestore \
  --archive=/backup/chessguru_validation_before_context_v1.archive \
  --nsFrom='chessguru_validation.*' \
  --nsTo='chessguru_validation_restore_20260828.*'
```

## 4. Seed and verify

Run these inside the backend container from `/app/backend` (or pass the same
Mongo URL to a local backend environment):

```bash
python scripts/seed_coaching_context_validation.py --dry-run
python scripts/seed_coaching_context_validation.py \
  --db-name chessguru_validation
python scripts/verify_coaching_context_validation.py \
  --db-name chessguru_validation
```

The verifier must report nine passed contract checks. It exercises real Mongo
queries through the canonical context builder; it does not mock the focus or
Review evidence collections.

If the marker is absent on a brand-new isolated database, initialize it once:

```bash
python scripts/seed_coaching_context_validation.py \
  --db-name chessguru_validation \
  --initialize-boundary
```

This command is still guarded by the exact-name allowlist.

## 5. Dedicated reviewer backend

Run a separate backend process/container. It must not replace the live backend.
Use these environment values:

```text
DB_NAME=chessguru_validation
DEV_MODE=true
DEV_USER_ID=validation_ctx_primary
COACHING_CONTEXT_V1_ENABLED=true
COACHING_CONTEXT_V1_ROLES=admin,super_admin
DETECTOR_QUALITY_GATE_ENFORCED=true
DIGEST_EMAILS_MODE=dry
OPENAI_API_KEY=
GOOGLE_CLIENT_SECRET=
SMTP_USER=
SMTP_PASSWORD=
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
```

Keep its port and frontend API URL separate from production. The fixture users
have no external usernames, email addresses, OAuth IDs, or payment IDs, so
import, mail, and billing workflows have no target. Do not run background sync,
analysis-queue, email, or payment jobs against this reviewer process.

To switch scenarios, restart only the reviewer backend with a different
synthetic `DEV_USER_ID`. Do not edit the fixture user into a real user.

## 6. Browser review matrix

For each scenario, first confirm:

```text
GET /api/coach/coaching-context/home
GET /api/coach/coaching-context/review?game_id=<synthetic-game-id>
GET /api/coach/coaching-context/training
GET /api/coach/coaching-context/coach_play
```

Then review the actual surfaces:

1. Home (`/home`): one primary focus; no rival recommendation.
2. Game Review (`/game/<synthetic-game-id>`): exact move match or an explicit
   “not observed” state; never an improvement claim from absence.
3. Training (`/training`): assignment repeats the same instruction and links to
   `/training/pattern/piece_safety`.
4. Coach Mode (`/play-with-coach?mode=coach`): context may be visible and teach.
5. Play Mode: coaching context, focus, greeting, goal, and mission scoreboard
   are absent from the browser session payload.

For `validation_ctx_primary`, the expected instruction everywhere is:

> Before you move, check whether every piece you leave behind is safe.

The Review evidence is move 1, `f3`, from `validation-game-primary`.

## 7. Human reviewer verdict

Record a pass/fail and a short reason for each item:

- The same current job appears everywhere.
- The wording sounds like one coach, not five features.
- Review connects only verified matching moves.
- Training is an assignment, not an unlimited library.
- Coach Mode can guide; Play Mode remains uninterrupted.
- Missing or unauthorized evidence produces an honest empty state.
- No surface claims improvement without comparable later opportunities.

Any failure keeps the rollout flag off. Fix the shared builder or adapter;
do not patch a one-off rival caption into an individual page.

## 8. Reset

Reset is tag-scoped and requires the database name twice:

```bash
python scripts/seed_coaching_context_validation.py \
  --db-name chessguru_validation \
  --reset \
  --confirm-reset chessguru_validation
```

The boundary marker and any untagged data remain untouched. Re-run the seed
command to restore the deterministic fixture set.

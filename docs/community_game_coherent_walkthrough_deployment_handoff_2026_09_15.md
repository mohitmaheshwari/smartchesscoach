# Community Game Coherent Walkthrough — Review and Deployment Handoff

**Date:** 2026-09-15
**Owner boundary:** Codex builds and verifies. Claude pushes and deploys.
**Current release state:** implementation complete; both runtime flags remain default-off; player visibility is blocked until the independent v3 review and admission dry-run pass.

## 1. What this release changes

The canonical Game Review flow can now fall back to one licensed, anonymous community game when no suitable personal game is available. The coach selects two or three chronological, non-repeating teaching chapters near the learner's rating band. On the existing review board the learner must:

1. predict the important idea;
2. optionally request one bounded hint;
3. reveal the verified explanation;
4. watch the legal line;
5. replay the key move;
6. complete the study and follow the coach-authored next action.

Personal review always wins. Shadow studies cannot be served. Only independently admitted studies can enter a player response. Initial study payloads exclude the correct answer, hint text, explanation and demonstration. Completion records assisted learning only; it cannot claim application, retention or transfer.

## 2. Isolation and flags

Both flags are declared in `docker-compose.yml` and default to `false`:

```ini
COMMUNITY_GAME_STUDY_SHADOW_ENABLED=false
COMMUNITY_GAME_STUDY_VISIBLE_ENABLED=false
```

Visibility requires all of the following:

- the global Shadow flag;
- the global Visible flag;
- canonical Complete Coaching access for that account, including its existing personalized-review enrollment, locked target and immutable baseline;
- role `admin` or `super_admin`.

The role check only narrows visibility. It never bypasses canonical access. There is no community-study email or user-id allowlist. Production currently has exactly three admin/super-admin accounts, so ordinary users remain mechanically excluded even when both community flags are on.

## 3. Frozen artifacts

Give the independent reviewer **only** this blinded packet:

```text
backend/data/detector_gold/community_game_study_neutral_review_v3.json
SHA-256: 67454bad5f352c6420ff515ba5df3ade51016a748e1db7ea0286e89576abe0ed
cases: 32
```

Do **not** give the reviewer this sealed, answer-bearing admission packet:

```text
backend/data/corpus_snapshots/community_game_study_admissions_v3.json
SHA-256: 47810489c4fe7da7a08e7a01ffcd28bce5bc5f45daa4a356651beaac1b1f3c88
records: 32
```

The reviewer must write a separate copy named:

```text
backend/data/detector_gold/community_game_study_neutral_review_v3.reviewed.json
```

They must fill exactly one `reviewer_response` per case and add the packet-level `independent_review` attestation. They must not open the sealed admission packet, the packet builder, the admission script, the runtime service or an answer key before freezing their review.

## 4. Independent quality gate

The admission command recomputes every locked gate. No total score can hide a weak axis. It refuses unless all of these hold:

- zero `incorrect_or_overclaimed` chapters;
- zero critical false claims;
- every displayed demonstration legally proves its visible claim;
- `correct_and_teachable` rate strictly exceeds 71.8%, with numerator and denominator shown;
- every headline is pattern-, geometry- or idea-led;
- zero studies repeat a primary principle as separate chapters;
- coherent-story rate strictly exceeds 9.8%;
- assignment-worthy rate strictly exceeds 48.8%;
- every admitted study is individually coherent, assignable, fully teachable, legally demonstrated and headline-compliant.

If any gate fails, keep both flags off and return the feature to Shadow. Do not lower a threshold or edit the review.

## 5. Exact release order

### Step A — integrate and deploy code dark

Integrate the Codex branch onto the then-current `working-code`, rerun the tests in section 8, and deploy with both community flags false. Confirm inside the running backend container that both values are false. This deploy must not change any user's recommendation.

### Step B — freeze the independent review

Have the reviewer produce the reviewed copy described in section 3. Recompute and record its SHA-256. Preserve both the original blinded packet and the reviewed packet; never overwrite the source packet.

### Step C — admission dry-run

Run inside the backend container so Mongo credentials come only from its environment:

```bash
cd /app/backend
python scripts/admit_reviewed_community_game_studies.py \
  --source-review-packet data/detector_gold/community_game_study_neutral_review_v3.json \
  --reviewed-packet data/detector_gold/community_game_study_neutral_review_v3.reviewed.json \
  --admission-packet data/corpus_snapshots/community_game_study_admissions_v3.json \
  --expected-source-sha256 67454bad5f352c6420ff515ba5df3ade51016a748e1db7ea0286e89576abe0ed
```

Record the full quality-gate output and `plan_fingerprint`. A dry-run that reports zero admitted studies is not an operable release and must stop visibility.

### Step D — backup and restore proof

Before applying the plan, dump the complete `community_game_studies` collection using the credentials already present in the production container/environment. Restore the dump into a scratch database and prove document counts and zero restore failures. Drop only the verified scratch database afterward. Record the exact rollback command and backup path.

### Step E — apply the exact frozen plan

Repeat the Step C command with:

```bash
  --apply \
  --confirm community-game-study-v3-admission \
  --confirm-plan <exact-plan-fingerprint-from-step-C>
```

The script replaces only the 32 named anonymous study ids, preserves terminal quarantine/withdrawn/stale states, refuses an admitted-to-Shadow demotion and performs no deletes.

Re-run the dry-run afterward. Counts, hashes and quality-gate values must reconcile exactly with the applied plan.

### Step F — Shadow first

Set:

```ini
COMMUNITY_GAME_STUDY_SHADOW_ENABLED=true
COMMUNITY_GAME_STUDY_VISIBLE_ENABLED=false
```

Restart the backend and verify:

- personal recommendations are byte-equivalent to the flags-off result;
- aggregate Shadow events are written without user, email, game or source identity;
- Shadow rows never appear in any player payload;
- malformed, stale, withdrawn and quarantined studies abstain.

### Step G — provision the remaining admin validators through canonical access

Do not edit Mongo manually and do not use `configure_phase8_pilot.py`, which correctly excludes admins from the real-user measurement cohort.

For each intended admin that lacks a Phase 8 baseline, choose an honest cutoff immediately before enrollment and run one account at a time:

```bash
cd /app/backend
python scripts/capture_phase8_baselines.py \
  --email <exact-admin-email> \
  --include-admin \
  --cutoff <utc-cutoff> \
  --source-commit <deployed-git-commit>
```

Inspect the dry-run. It must resolve one exact account, find a current exact Plan focus and report no invalid or immutable conflict. Then repeat with:

```bash
  --apply --confirm phase8-baselines
```

Enroll that same exact account through the existing personalized-review authority:

```bash
python scripts/configure_personalized_review_validation.py \
  --email <exact-admin-email>
```

After the dry-run resolves exactly one account and zero missing accounts, repeat with:

```bash
  --apply --confirm phase6-validation
```

Verify exactly three admin/super-admin accounts now have canonical Complete Coaching access. Do not manufacture a baseline for an ineligible account, change the cutoff after seeing outcomes, or include these admins in real-user effect metrics.

### Step H — enable the isolated visible cohort

Only after Steps B–G pass, set:

```ini
COMMUNITY_GAME_STUDY_SHADOW_ENABLED=true
COMMUNITY_GAME_STUDY_VISIBLE_ENABLED=true
```

Restart the backend. Confirm both values inside the running container. Verify with:

- all three admin accounts;
- one ordinary account that already has Complete Coaching access;
- one ordinary account without Complete Coaching access.

The ordinary accounts must never receive a community prescription. An admin must still fail closed when its baseline or enrollment is absent. A personal eligible game must still beat a community study for every account.

## 6. Required real-user journey

On an eligible admin account with no suitable personal fallback:

1. open `/games` and see one coach-chosen community study;
2. start it and confirm the initial payload does not reveal the answer, hint, explanation or line;
3. request a hint and confirm only the bounded hint appears;
4. choose both a correct and incorrect answer on different chapters;
5. watch each legal line to completion;
6. replay the key move on the same board; try one wrong legal move first and confirm it is rejected without recording completion;
7. refresh mid-study and confirm only already-earned hint/reveal/progress returns;
8. finish only after every chapter has predict, reveal, watch and replay evidence;
9. confirm the completion language says assisted learning recorded and real-game application/retention not measured;
10. follow the server-authored next action and confirm that event is recorded;
11. verify another admin cannot open the first admin's prescription id;
12. verify source usernames, ids, URLs and game identity never appear in network payloads or UI.

Required server events are: `community_review_started`, `community_review_predicted`, `community_review_hint_used`, `community_review_revealed`, `community_review_line_watched`, `community_review_key_move_replayed`, `community_review_completed`, `community_review_next_action_linked`, and `community_review_next_action_followed`.

## 7. Rollback

Immediate rollback is:

```ini
COMMUNITY_GAME_STUDY_VISIBLE_ENABLED=false
```

Restart the backend and confirm the value inside the container. Active community studies then fail closed; the canonical review selector returns to personal review or the existing empty state. Interaction and learning evidence remain stored. Do not delete it and do not relabel it as transfer.

Set `COMMUNITY_GAME_STUDY_SHADOW_ENABLED=false` as well if Shadow measurement itself is implicated. Restore the collection backup only if the admission data—not the UI or access gate—is corrupt.

## 8. Verification already completed locally

```text
Backend expanded focused suite: 147 passed
Frontend focused suite: 4 suites, 17 tests passed
Frontend production build: exit 0
Python compileall: passed
git diff --check: passed (line-ending warnings only)
```

The mandatory `python tests/test_all_flows.py` could not execute locally because it immediately attempted live HTTP against a backend that was not running and raised `httpx.ConnectError`. That is **inconclusive**, not green. Claude must run it against the deployed candidate or a local backend and record the actual result before enabling visibility.

## 9. Stop conditions

Keep or return visibility to false on any incorrect/overclaimed chess claim, illegal or mismatched demonstration, answer leakage, identity leakage, repeated principle presented as a separate chapter, incomplete/inescapable interaction, ordinary-user exposure, changed personal recommendation while the feature is off, assisted-practice mutation of transfer, missing server event, failed core suite, or non-restorable backup.

Ordinary-user rollout is outside this release. It remains blocked until the isolated cohort creates server-side behavior evidence and a separate, data-locked expansion threshold is approved.

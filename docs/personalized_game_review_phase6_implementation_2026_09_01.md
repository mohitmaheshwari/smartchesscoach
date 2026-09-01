# Personalized Game Review Coach — Phase 6 validation harness

Date: 2026-09-01

## Outcome

Phase 6 is implemented as a private, blinded old/new validation harness on the canonical `/game/:gameId` review. It does not expose the experiment to ordinary users and it does not create another coaching pipeline.

Approved validators see **Review A** and **Review B**. The backend deterministically counterbalances which letter means legacy versus personalized for each reviewer/game pair. The UI, URL, scorecard request and PostHog event never disclose that mapping. The private stored scorecard retains the real mode so the result can be analyzed later.

## Rollout boundary

The effective decision has two levels:

1. `PERSONALIZED_GAME_REVIEW_COACH_ENABLED` is the emergency master switch. False always wins.
2. With `PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT=validation` (the fail-closed default), only users with both of these existing user-document flags are enabled:

```json
{
  "feature_flags": {
    "personalized_game_review_coach": {
      "enabled": true,
      "validation_compare": true,
      "cohort": "phase6_validation_2026_09"
    }
  }
}
```

`PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT=all` is reserved for a later approved rollout. It enables the personalized review for authenticated users but does not grant the internal A/B toolbar; comparison still requires the per-user validator flag.

The same account gate protects the reflection-submission endpoint. A direct URL or API request cannot opt an account into validation.

## Blinded comparison

- The query is `review_variant=a|b`, never `review_mode=legacy|personalized`.
- A/B mapping is a stable backend hash of reviewer ID, game ID and protocol version.
- Each mapping contains exactly one legacy and one personalized version.
- A game is scoreable only if its personalized version has a complete verified plan. Otherwise both variants are blocked and the UI says the comparison is not ready.
- Normal validators may review their own games. Existing `is_reviewer` access remains the only authority for coach-reviewers who need cross-user games.
- The existing Claude-gold tester panel is suppressed whenever this validation harness is active, preventing benchmark contamination.

## Canonical scorecard

The backend owns and sends all dimension and option labels:

- Chess truth
- Moment choice
- Explanation clarity
- Personalization
- Reflection value
- Story coherence
- Next-action quality

Every dimension must receive exactly one server-issued option. `critical_truth_failure` is derived by the backend from the chess-truth answer; the client cannot set it. The scorecard is idempotently stored by reviewer, game, variant, true mode, V5 version and plan ID.

Stored validation evidence contains rubric IDs, optional reviewer note, reviewer/game references, version and plan identity. It contains no FEN, PGN, caption body, detector ID, reflection answer or community data. The public re-entry projection omits the hidden legacy/personalized mode.

## Instrumentation

Existing review events continue to measure start, reflection, visual inspection, completion and next-action start. Phase 6 adds:

- `review_validation_mode_changed`
- `review_validation_submitted`

The dedicated analytics helper allowlists only `presentation_variant` and `critical_truth_failure`. Game IDs, reviewer notes, captions and arbitrary properties are discarded before PostHog capture.

MongoDB stores the human scorecard as server truth. A unique `review_id` index prevents duplicate scorecards, and a compound lookup index supports refresh/re-entry.

## Safe deployment sequence for Claude

1. Commit and deploy the code with the master switch still false.
2. In the deployed backend container, dry-run exact account enrollment:

```bash
python scripts/configure_personalized_review_validation.py \
  --email bhutramohit@gmail.com \
  --email <coach-one-email> \
  --email <coach-two-email>
```

3. Confirm that exactly the intended three accounts are matched and none are missing.
4. Apply the exact updates:

```bash
python scripts/configure_personalized_review_validation.py \
  --email bhutramohit@gmail.com \
  --email <coach-one-email> \
  --email <coach-two-email> \
  --apply --confirm phase6-validation
```

5. Set these backend environment values and restart the backend:

```text
PERSONALIZED_GAME_REVIEW_COACH_ENABLED=true
PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT=validation
```

6. Verify an unlisted account sees the unchanged legacy review and receives 403 for an explicit `review_variant` request.
7. Verify each listed account sees Review A/Review B, can save both scorecards, refresh them, and cannot score an incomplete comparison.

Rollback is immediate: set `PERSONALIZED_GAME_REVIEW_COACH_ENABLED=false` and restart. No database rollback is required. To remove account enrollment as well:

```bash
python scripts/configure_personalized_review_validation.py \
  --email <email> --disable --apply --confirm phase6-validation
```

## Trial report

After or during the one-week review, run inside the backend container:

```bash
python scripts/report_personalized_review_validation.py
```

The read-only report returns submission counts, paired/unpaired reviewer-game counts, rubric distributions by the hidden true mode, and critical truth blockers. It intentionally excludes reviewer notes.

## Verification evidence

- Phase 6 focused backend boundary: **70 passed**.
- Complete Phase 1–6 personalized-review backend regression: **171 passed**.
- Phase 5/6 review UI and analytics: **14 passed across 3 suites**.
- Backend syntax compilation: passed.
- Production frontend build: passed in the repository's normal build mode. The new component's initial hook warning was removed; remaining warnings are the repository's pre-existing source-map, hook, browserslist and bundle-size warnings. A separate strict `CI=true` build remains red because that mode promotes all of those standing warnings to errors.
- Repository-mandated live-HTTP `tests/test_all_flows.py`: inconclusive because no backend server was listening; it stopped at the first connection attempt before executing a product assertion.

## Handoff state

No commit, push, deployment, environment change, account enrollment, production database write or production feature enablement was performed. Claude owns those deployment operations. Mohit and the two coaches provide the external one-week evaluation; any critical false chess claim blocks Phase 7.

# Progress unavailable-state repair and open account diagnosis

Branch: codex/progress-unavailable-state-v1.
Base: origin/working-code 11d3184e.
Status: local code/tests complete; NOT pushed or deployed.

## Confirmed defect

UnifiedProgress rendered "I'm not ready to claim a change yet" whenever
journey.enabled was not true. That includes disabled access, a missing baseline,
missing enrollment provenance, and (on this base) failed HTTP/network requests.
It then displayed an empty lesson/evidence checklist and "Continue my lesson".
Those are not supported conclusions about the user's chess.

The exact live account reason is NOT established by the screenshot.
Previously reported baseline_missing is a lead, not a current finding.

## Fix

- Disabled access has an explicit unavailable view and preserves the backend
  reason in expandable tracking status.
- Missing baseline/enrollment provenance is explained as setup, not poor progress.
- HTTP/network/malformed responses have a separate error state with retry.
- Unavailable states do not render empty evidence boards, unchecked practice
  milestones or an instruction to finish a lesson.
- Buttons lead to imported games and import management, without claiming imports
  are fresh or complete.
- Enabled transfer verdicts and paused-state behavior are preserved.
- No access gate, baseline, enrollment, detector, threshold or mastery rule changes.

This is NOT an implementation of broader organic-improvement tracking and NOT
proof that account sync/analysis is healthy.

## Verification

Full frontend suite: 66 suites / 310 tests passed, exit 0.
Eight added interaction cases cover five disabled reasons, HTTP error, network
error and malformed response; retry restores actual evidence. The old disabled
copy expectation was updated. Existing 302 tests passed in the initial run;
new tests initially failed due to placement outside their DOM fixture, corrected.
Production build: exit 0. Existing warnings: stale browserslist, dependency
source-map warning and bundle size. git diff --check: clean.
Browser tool failed to initialize; no authenticated visual acceptance claimed.
Operational copy checked against check-voice: no chess diagnosis or invented
improvement claim, no parallel caption generator.

## Account inspection attempted, not completed

No credentials configured in the original integration worktree/process.
The main project's existing backend .env does exist; a narrow read-only account
lookup using that configuration failed with ServerSelectionTimeoutError.
No documents were returned. Credentials were not printed or copied.
Browser inventory also failed to initialize.
No account data, baselines or enrollment changed.

## Claude: read-only account checks still required

For Mohit's existing account, report only necessary counts/timestamps/statuses:

1. Identify the configured Lichess connection. Last successful sync, most recent
   imported Lichess date_played/imported_at, and latest available upstream game
   date if already known. Distinguish no sync from analysis pending.
2. Count recent imported Lichess games, completed analyses and pending/failed queue
   entries. Verify account ownership/source keys; do not mix PWC and imported games.
3. Resolve get_complete_coaching_access against current flags/user enrollment,
   locked target and existing immutable baseline. Then check phase8_enrolled_at,
   since projection can return enrollment_provenance_missing even after access.
   Prefer read-only service/database inspection: the HTTP progress GET itself can
   record a reach event when enabled.
4. Compare latest move_observations against active focus's pinned detector version;
   distinguish absent analysis, absent detector observations and incompatible versions.
5. Check existing later-game evidence and practice separately. Absence of lesson
   completion does not prove absence of natural improvement.
6. Report the first broken link and its evidence before any backfill or migration.

Do NOT create a today's-data "pre-enrollment" baseline, rewrite the historical
cutoff, enroll the account, replay attempts or change detector pins to green the UI.
Those require a separately justified data repair and approval.

## Integration caution

The earlier codex/frontend-journey-integration-v1 branch also edits this component
for loading errors and layout. Reconcile overlapping hunks; do not copy whole
files over newer changes or ship both implementations of error handling.
No migrations/flags required for this frontend-only repair.

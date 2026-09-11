# Coach-Selected Game Review — Data Lock

**Status:** LOCKED
**Date:** 2026-09-11
**Snapshot:** `backend/data/corpus_snapshots/coach_selected_game_review_formula_bakeoff_2026-09-11.json`

## Decision locked

The V1 selector uses this order:

1. resume an existing started prescription;
2. prefer a candidate whose authorized events match the player's active focus;
3. prefer the candidate with more already-authorized `GameTeachingPlan` chapters;
4. break remaining ties by game recency.

Eligibility is not based on raw stored plans. A game must pass the same public projection used by Game Review under the current environment and contain at least one selected, player-authorized chapter.

## Evidence

- Production contained 605 stored plans, but only 53 plans across 13 users survived the exact player-facing projection. Designing against all 605 would overstate supply by more than ten times.
- Three eligible users had at least one focus-aligned candidate.
- Newest-first selected a focus-aligned game for 0 of those 3 users.
- Focus-first selected a focus-aligned game for 3 of 3 users without reducing mean selected chapters: both newest-first and focus-first selected 2.23 chapters on average.
- Richness-first selected a focus-aligned game for 2 of 3 users and gained only 0.08 mean chapters (2.31 versus 2.23). That tiny richness gain is not worth disconnecting the review from the coaching plan.
- Four of 13 users had exactly one eligible game. A guessed dismissal cooldown would therefore recreate the reported repetition for those users. V1 keeps the dismissal and reports an exhausted queue honestly.

## Rejected candidates

- **A — newest eligible:** rejected because it missed every available focus-aligned candidate.
- **C — richness before focus:** rejected because it broke focus alignment for one of three eligible users for only 0.08 additional mean chapters.
- **Source-first:** not locked because every eligible candidate was an imported game; production supplied no discriminating data.
- **Pain/loss-first:** rejected before bake-off because result and centipawn loss do not establish authorized teaching value and conflict with the approved product scope.

## Threshold decisions

- No new moment cap: the selector renders the chapters already capped by the measured `GameTeachingPlan` authority.
- No new event-count threshold beyond the structural requirement that a safe plan contain a chapter.
- No timed dismissal cooldown.
- No broad rollout percentage is locked by this evidence; rollout remains account-isolated.

## Measurement method

A read-only script ran inside the production backend container using its existing environment. It queried Mongo without printing credentials and projected every candidate through `maybe_attach_phase5_review_fields`. Output was aggregate-only: no user IDs, game IDs, emails, FENs, moves, PGNs or credentials were emitted or versioned. Production was not written.

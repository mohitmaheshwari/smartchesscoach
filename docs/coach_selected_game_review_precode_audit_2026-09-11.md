# Coach-Selected Game Review — Pre-Code Audit

**PRE-CODE AUDIT: PASS**
**Feature:** Coach-Selected Game Review
**Scope:** `docs/coach_selected_game_review_scope.md`
**Data lock:** `docs/coach_selected_game_review_data_lock_2026-09-11.md`

## Six hard gates

1. **Literal UI mockup — PASS.** The approved scope contains literal new, resumed, dismissed, completed, empty-supply and archive states.
2. **Pattern/idea headline — PASS.** The recommendation explains the lesson and relationship; SAN and opponent metadata remain evidence, never the headline.
3. **Data-derived choices — PASS.** The formula bake-off locks focus → authorized chapter richness → recency. Existing `GameTeachingPlan` owns its measured cap. No dismissal duration, new cp-loss threshold or source weight is invented.
4. **Behavior-changing success — PASS.** The primary behavior is starting, resuming and completing the prescribed review, followed by a canonical next action. Review completion is explicitly not transfer; only later comparable unassisted game evidence can prove change.
5. **Deferred work stays deferred — PASS.** No detector, caption engine, community full-game pool, Home/Progress redesign, LLM selector or Shadow promotion enters V1.
6. **Mohit sign-off — PASS.** Mohit explicitly instructed “go and fix” after receiving the complete scope.

## Single-source-of-truth lock

| Concept | Canonical owner after V1 | Rule |
|---|---|---|
| Chess teaching inside a game | Existing `GameTeachingPlan` and projected `TeachableEvent` | Selector reads the safe public projection; it never interprets FEN, cp loss or detector output. |
| Detector visibility | Existing `detector_quality.py` authorization | Shadow and stale facts cannot create eligibility or preview copy. |
| Current coaching focus | Existing active-focus authority | Prescription stores only the referenced focus identity used at selection time. |
| Pattern state | Existing `pattern_decay_service.py` | No copied score or second decay formula. |
| Review prescription lifecycle | New `game_review_prescriptions` rows | This is genuinely missing. It alone owns recommended/started/dismissed/completed/superseded state and resume position. |
| Historical reviewed compatibility | Existing `games.reviewed`, `reviewed_at`, `review_stats` | Kept as a compatibility projection; it does not select the next game. |
| Selection | New prescription service using the locked formula | Every route calls it; no route carries a private fallback selector. |
| Rollout | Existing complete-coaching access decision | No new cohort list or independent account gate. |
| Community fallback | Existing verified training supply/admission | V1 links to training; it does not copy positions or call them full games. |

## Forecasted bottleneck

Authorized supply, not game volume, is the bottleneck: 14,905 analyzed games reduce to 53 current player-safe review plans. V1 must therefore make the empty state first-class and must never widen eligibility to make the page look busy.

Proceeding to implementation.

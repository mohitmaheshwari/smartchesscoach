# Coach-Selected Game Review — Product Scope

**Status:** APPROVED — Mohit explicitly approved implementation on 2026-09-11
**Date:** 2026-09-11
**Parent product authority:** `docs/personalized_game_review_coach_scope.md`
**Decision:** Extend the existing Personalized Game Review Coach with one canonical, persistent game-selection journey. Replace the archive-first `/games` landing experience and consolidate the competing selectors; do not rebuild the game-review board or create another review product.

## 0. Existing surfaces audit

### What already exists

| Need | Current owner | Decision |
|---|---|---|
| Player-facing Game Review destination | `/games`, rendered by `frontend/src/pages/AllGames.jsx` | **REPLACE THE LANDING EXPERIENCE.** It is currently an archive with expandable rows and asks the player to choose a game. Keep the archive, but move it below a coach-selected prescription. |
| Coach-selected game | `GET /api/lab-coach-pick` in `backend/routes/training_advanced.py` | **CONSOLIDATE.** The response already calculates a top-level decay/focus-aware `pick`, but separately builds `coaching.priority_game`. There must be one selector and one result. |
| Existing Coach's Pick UI | `/lab`, rendered by `frontend/src/pages/Dashboard.jsx` | **MIGRATE THEN RETIRE.** The page currently renders `coaching.priority_game`, not the smarter top-level `pick`. During migration it must consume the canonical prescription; after the `/games` journey is proven, the duplicate hero is removed. |
| Full board review | `/game/:gameId` and `/lab/game/:gameId`, rendered by `LabV2` / `GameDecryptionV5` | **KEEP AND EXTEND ONLY AT THE BOUNDARY.** This is the existing personalized review, reflection and teaching surface. The selector opens it with prescription identity; it is not rebuilt here. |
| Verified review content | `game_teaching_plan`, `teachable_events`, the central caption pipeline and detector-quality authorization | **REUSE.** Selection consumes current, player-authorized evidence. It never reinterprets a FEN, engine score or Shadow detector. |
| Current completion state | `games.reviewed`, `reviewed_at`, `review_stats`; `POST /api/lab/{game_id}/complete-review` | **EXTEND.** A completed boolean cannot distinguish recommended, opened, continued, skipped and completed. Preserve it for compatibility while adding one canonical prescription lifecycle. |
| Current next-game behavior | `complete-review` selects the newest unreviewed game by `imported_at` | **REPLACE.** Completion, dismissal and refresh must all use the same canonical selector. |
| Current caching | five-minute `coaching_cache` | **FIX AT THE OWNER.** Prescription mutations invalidate or version the relevant recommendation result immediately. A stale cache may never resurrect a completed or dismissed game. |
| Personal learning direction | active focus, pattern decay, authorized `GameTeachingPlan`, personal curriculum and learner evidence | **CONSUME.** These remain the authorities for what matters and what may be claimed. The selector adds no duplicate learner profile. |
| Community material | `community_puzzles` and `community_training_positions` | **POSITION FALLBACK ONLY.** The repository has verified community positions, not a canonical anonymized full-game review pool. V1 may offer a clearly labelled practice position when no personal game is eligible; it may not present it as a community game review. |
| Reviewer-only queue | `/review` and `/review/authoring` | **DO NOT TOUCH.** These are internal content-quality surfaces, not the player's Game Review. |

### The current failure

The product presently has three incompatible meanings of “the next game”:

1. the top-level `pick` uses active focus and pattern decay;
2. the rendered Lab hero uses `coaching.priority_game`, which ranks a narrower problem-game list;
3. review completion returns the newest unreviewed game.

Opening a recommendation is only a browser navigation and creates no durable server state. Returning to Game Review therefore shows the same game as a new recommendation. Only one reviewed game is currently recorded for Mohit's account despite hundreds of analyzed games, so the repeated recommendation is expected behavior, not a rendering accident.

### Overlap decision

**EXTEND + CONSOLIDATE + PARTIAL REPLACE.** Extend the approved Personalized Game Review Coach. Add one selection/lifecycle layer above its existing `GameTeachingPlan`; replace only the archive-first `/games` landing experience; consolidate every next-game consumer behind one server authority; retire the duplicate Lab selector after parity. No second game-review board, detector, caption engine, learning store or community-game database is created.

## 1. What it is

Coach-Selected Game Review is the front door to Game Review. It feels as though a private coach has watched the player's available games, chosen the one that can teach the most useful lesson now, and remembered whether the player has started, skipped or completed it.

It does not say “pick any game.” It says which game to review, why that game matters to this player, what kinds of verified learning are inside it, and what the coach wants the player to do next. The archive remains available for deliberate browsing, but it is secondary to the coach's recommendation.

## 2. What the user sees

### A. A new recommendation

```text
GAME REVIEW

I picked one game for you today.

vs Arjun · Rapid · Lost

You had the right attacking idea, but this game contains the same
piece-safety decision we are working on. It also has one move where
you handled the danger correctly.

WHAT THIS GAME CAN TEACH YOU

✓ Something you already understood
  You moved an attacked piece before starting your own plan.

● Your current lesson in a real game
  Later, one rook move left another piece without a usable defender.

◆ A possibility worth discovering
  I found a verified continuation the game never reached.

[ Review this game with me ]     [ Show me another ]

Why this one?
It connects today's lesson to a decision from one of your own games.
```

The preview lists only chapter types backed by current player-facing evidence. It does not promise a hidden opportunity, opening lesson, trap or endgame lesson unless the stored plan actually contains an authorized event of that type. It never pads the card with generic copy to make it look complete.

### B. The player has opened but not completed it

```text
GAME REVIEW

Let's continue the game we started.

You stopped after the position where your rook moved to d2.
I saved your place and your answer.

[ Continue with your coach ]     [ Leave this for later ]
```

Returning to the page does not present the game as a fresh recommendation. The same stable prescription resumes at the last server-recorded chapter or position.

### C. The player asks for another game

```text
Okay — we will leave that one for later.

I picked a different game because it shows the same lesson more clearly.

[ Review this game with me ]
```

“Show me another” is a server action, not a local shuffle. The dismissed prescription cannot reappear as new on refresh. V1 does not force the player to explain the dismissal.

### D. The player completes the review

```text
We finished this review.

You found the safer move with one hint. That is useful practice,
but it does not prove the habit is automatic in a real game yet.

I will watch for the same kind of decision when your next games arrive.

[ See what I picked next ]       [ Return home ]
```

Completion records what was actually attempted and what assistance was used. It never turns “reviewed” into “learned” or “improved.” The next recommendation is selected by the same canonical selector.

### E. No personal game is honestly eligible

```text
I am still looking for the right game to review.

Your games are analyzed, but I do not yet have a current verified
teaching plan I can stand behind. I will not invent one.

Here is a verified practice position for your current lesson while I wait.

[ Practise this position ]       [ Browse all my games ]
```

If no authorized personal game and no verified position fallback exist, the page says it needs another analyzed game and offers import or Play with Coach. It does not silently fall back to the most recent loss.

### F. The archive

Below the prescription, a quiet “All my games” section preserves imported games and Play-with-Coach games. Archive rows show review state—`Not reviewed`, `In progress`, `Completed` or `Left for later`—and never compete visually with the coach's one recommended action.

## 3. In scope (V1)

- Make `/games` the canonical player-facing Game Review landing route and preserve `/game/:gameId` as the canonical full review.
- Add one server-owned review prescription contract with a stable prescription ID, user ID, game ID, source teaching-plan identity/version, recommendation reason references, lifecycle state and timestamps.
- Support the lifecycle `recommended → started → completed`, plus explicit `dismissed` and system-owned `superseded` transitions. Transitions are idempotent and auditable.
- Persist review start before navigation succeeds. Reopening the page returns `Continue`, not a new-looking copy of the same recommendation.
- Store the last server-confirmed chapter/position needed to resume. Browser-only state is not the authority.
- Make completion atomically mark the prescription complete, preserve compatible `games.reviewed` fields, invalidate the old recommendation and obtain the next prescription through the same selector.
- Make “Show me another” atomically dismiss the current prescription and return a different eligible result. Refresh, another tab and stale cache cannot resurrect the dismissed result.
- Use one canonical selection service for `/games`, the migration version of the Lab hero and the completion response.
- Require an analyzed player-owned game and a current review contract with at least one visible, fully verified, player-authorized teaching event. Shadow/Disabled detector output is never an eligibility shortcut.
- Prefer an unfinished started prescription over every new candidate so the coach remembers the ongoing lesson.
- Rank new candidates using existing authoritative evidence: current focus alignment, pattern state, authorized teaching-plan value, successful as well as missed ideas, useful contrast with recent reviews, source/freshness and whether the game is the player's own unassisted game or Play-with-Coach practice.
- Treat selection as a learning decision, not a “largest centipawn loss” or “most painful loss” contest. A win, draw or quiet game can be selected when it contains the better verified lesson.
- Generate “why this game” and preview bullets from the selected `GameTeachingPlan`/`TeachableEvent` references. The selector and frontend cannot create chess claims from raw game fields.
- Preserve the distinction between Caption-grade explanation and Plan/Mastery-grade recurrence, prescription or transfer claims. The card may preview a position-level Caption fact, but personal recurrence wording requires the stronger authorization already defined by the parent scope.
- Preserve positive evidence. When authorized, the preview includes what the player handled well, not only mistakes.
- Allow a clearly labelled verified community **position** as a fallback action only when no personal game is eligible. It remains training, not a completed game review, and cannot update game-review completion.
- Keep the full game archive below the recommendation with review-state labels and direct access to any game the player chooses.
- Instrument prescription served, started, resumed, dismissed, superseded, completed, no-eligible-game, fallback offered and next prescription served.
- Add a default-off, account-isolated rollout path so Mohit and coach validators can test the complete journey before broader release.

## 4. Explicitly out of scope (V1)

- Rebuilding `LabV2`, `GameDecryptionV5`, captions, detectors, reflection questions or the approved `GameTeachingPlan` architecture.
- Creating another game-level planner, another focus calculation, another learner profile or another review-completion store.
- Promoting Shadow detectors or displaying Hidden Opportunities that have not earned player-facing authorization.
- Using an LLM to select games, invent a selection reason, summarize unsupported chess ideas or decide whether evidence is correct.
- Treating raw `cp_loss`, accuracy, result, emotional “pain” or newest-game order as sufficient learning value.
- Calling an anonymized puzzle or FEN a “community game.” A future community full-game feature requires its own privacy, provenance and reviewability contract.
- Showing a fixed number of chapter previews by padding with generic material.
- Claiming learning, mastery or improvement because a review was opened or completed.
- Automatically replacing an in-progress prescription when a new game is imported or the focus changes. It may be marked stale for an explicit server-approved reason, but the player's work is preserved.
- Deleting legacy fields or the Lab hero before response parity, migration telemetry and rollback are proven.
- Redesigning Home, Learn, Progress, Play with Coach or the inner review chapters as part of this scope.
- Bulk production mutation, deployment or broad rollout without the later approved migration and deployment handoff.

## 5. Success criteria

- A player opening Game Review sees one clear coach-selected action before the archive, with a truthful explanation of why that game matters now.
- The game rendered on `/games`, the game returned after completion and the migration Lab hero all come from the same prescription identity and selector version.
- Opening the selected review and returning produces `Continue with your coach` at the saved place; it never masquerades as a new recommendation.
- Dismissing the selection returns a different eligible prescription immediately and the dismissed one stays dismissed across refresh, logout/login, another browser and cache expiry.
- Completing a review never returns that game as the next new selection. Compatible historical `reviewed` state remains correct.
- Every visible preview sentence traces to the current stored teaching plan, an authorized event and its evidence identity. A stale, missing or Shadow-only plan produces silence or the honest fallback state.
- Selection includes wins/draws and positive play when they contain higher verified learning value; it is not structurally biased toward the most painful loss.
- The player can still browse and open every available own game from the archive without disturbing the active prescription.
- The system never counts an opened, dismissed or completed review as proof of real-game transfer. Later comparable unassisted opportunities remain the only transfer authority.
- The selection endpoint and all state transitions are idempotent, user-isolated and safe under concurrent tabs and request retries.
- A production-base E2E for Mohit's account proves: recommendation served → start → saved resume → dismiss → distinct replacement → start → complete → distinct next recommendation → archive state preserved.
- A stratified offline bake-off shows that selected games contain more player-authorized teaching value than the current selectors without increasing unsupported-claim exposure. The exact release threshold is locked from that measurement, not chosen in this scope.
- Mohit and at least two coaches can answer, without opening the archive: “Why this game?”, “What will it teach this player?” and “What happens after they finish?” Any critical chess-truth error blocks rollout.

## 6. Open questions

- **How should eligible games be ranked?** Candidate features are known, but their ordering/weights are not. Run the same candidate pool through multiple deterministic formulas over a versioned corpus, compare selection quality blindly with current `pick` and `priority_game`, and lock the formula through `/lock-via-data`.
- **How many preview chapters should appear?** The card should reveal enough value without spoiling the review or becoming homework. Measure the distribution of authorized chapter types per eligible game and validate candidate caps with Mohit and the coach group; do not pad sparse games.
- **How long should a dismissed game stay out of the queue?** This is a behavioral threshold. Measure candidate-pool depth per eligible player before choosing a cooldown. If the pool is shallow, preserve the dismissal and show “No different game is ready” rather than quietly returning the same game.
- **When may a recommendation be superseded?** A new active focus or corrected teaching-plan version may make the current recommendation stale, but an in-progress review should be preserved. The technical spec must enumerate exact stale reasons and whether each can replace `recommended` versus `started` state.
- **What is the minimum review-plan evidence for selection?** One authorized event may be truthful but not worth a full review. Measure eligible-plan richness and coach judgments before locking a threshold; no raw event count becomes a proxy without validation.
- **Should Play-with-Coach games rank differently from imported games?** They are real practice evidence but assisted. Compare learning quality and completion while keeping source visible; never present assisted play as an organic transfer example.
- **What should the no-game fallback prioritize?** Verified own positions should precede anonymous community positions when both exist, but the exact supply ladder must reuse the canonical training selector and admission gate.

## 7. Pre-code requirements

- Mohit explicitly signs off this scope document.
- Run `/audit-pre-code` against the current `origin/working-code` base and record the file/contract plan before editing implementation.
- Run `/single-source-of-truth` and name one owner each for: prescription state, game eligibility, selection, review completion, resume position and training fallback. Existing `GameTeachingPlan`, detector authorization, active focus, pattern decay and learner evidence remain referenced rather than copied.
- Produce a versioned, anonymized selection packet from existing stored evidence. It must contain candidate features and current-selector outcomes without user IDs, emails, PGNs or credentials.
- Use `/lock-via-data` to compare deterministic ranking formulas, eligible-pool depth, authorized-event richness, dismissed-pool behavior and source mix before locking weights, caps, cooldowns or release thresholds.
- Freeze current responses from `GET /api/lab-coach-pick`, `/games` rendering and `POST /api/lab/{game_id}/complete-review` so the consolidation proves intentional changes and no accidental loss of archive/review behavior.
- Write a technical spec defining the prescription schema, transition table, concurrency/idempotency rules, selector inputs/outputs, stale-plan behavior, cache invalidation, backward-compatible `games.reviewed` projection and migration/deletion order.
- The technical spec must use the existing central `GameTeachingPlan` and player-facing detector authorization as the only chess-content input. It must include a guard test that the selector imports or receives these contracts rather than interpreting raw FEN/cp loss.
- Add a default-off, per-account rollout gate. Flag-off must preserve the current `/games`, Lab and completion responses until migration parity is approved.
- Build contract, integration, frontend and E2E tests before any player-visible enablement. Tests must cover refresh, multiple tabs, retries, stale cache, new-game import, focus change, corrected plan version, empty supply, dismissed pool exhaustion and rollback.
- Run a blinded coach-selection comparison on the locked packet. Any selected game with an unsupported preview claim fails the candidate formula regardless of aggregate preference.
- Claude remains responsible for push and production deployment. Codex produces tested commits and a deployment handoff; no production write or flag change is authorized by this scope sign-off.

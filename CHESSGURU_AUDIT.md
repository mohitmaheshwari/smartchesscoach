# ChessGuru — Codebase Audit

**Date:** 2026-10-14 · **Method:** read-only inspection of code, the production database (`chess_coach`), deployed environment variables, and the repo's own instrumentation. No code was modified. Figures are from production unless stated.

---

## 1. Executive summary

ChessGuru is not an early prototype. It is a large, working engine-backed coaching system — 46 route modules, 373 services, 64 page components, 126 production collections, 4.1M Lichess puzzles, 20,197 imported games and 19,474 analysed. The chess truth layer is genuinely strong: Stockfish analysis, a central caption pipeline that every coaching surface routes through, and a per-claim verifier that checks sentences against the board.

The problem is not missing capability. It is **delivery**. Features are built, merged, flag-gated, and then not reached. The repo's own `scripts/what_a_real_user_sees.py`, run today, shows the Progress page alive for **3 of 8** ordinary users and the coach conversation for **5 of 8**, while every surface works for the admin account. Five users past the 15-game entry bar were never enrolled in the Progress cohort because "enrolment ran once by hand and nothing runs it again". Two significant subsystems — `COACHING_CONTEXT_V1` and `PWC_UNIFIED_EXPERIENCE_V1` — are gated to `admin,super_admin` in production, so staff see a different product from users.

Coaching quality has a measurable ceiling. Over 2,383 engine-flagged moves across 100 games, the engine's own line explains 28%, deterministic board families could explain a further 40.5%, and **31.5% have no explanation available at all**. Of the cards that describe only the better move, **79.9% have no computed fact about the played move** — so the caption layer is not choosing badly, it has nothing to choose from.

Community is **absent**, not partial. No matchmaking, human chat, friends, groups or tournaments. The only multi-person code is an admin waitlist.

Reuse potential is high. Priorities: make what exists reach users, close the explanation gap, then build community on top.

---

## 2. Existing feature inventory

### Scale

| | Count |
|---|---|
| Backend route modules / registered routers | 46 / 44 |
| Backend services | 373 |
| Backend scripts | 444 |
| Test files | 534 |
| Frontend page components / all components | 64 / 260 |
| Frontend routes in `App.js` | 68 |
| Production collections | 126 |

### Largest production collections (evidence of what is really used)

```
4,110,434  lichess_puzzles              627,468  move_observations
  144,683  user_pattern_events           71,706  pwc_session_traces
   53,774  community_training_positions  51,227  community_puzzles
   29,974  user_teaching_memory          20,197  games
   19,474  game_analyses                 19,355  detector_claims
   19,407  thinking_scores               16,972  notifications
   11,812  onboarding_puzzles             8,757  coaching_summaries
      498  coach_sessions                   128  users
```

### Complete and in use

- **Game import and analysis** — `journey_service.py`, `analysis_worker.py` (2 worker replicas in `docker-compose.yml`), Chess.com and Lichess APIs. 20,197 games imported, 19,474 analysed.
- **Game review (V5)** — `services/game_decryption_v5_service.py` calling `services/caption_pipeline.build_move_teaching_decision`. Rendered by `GameDecryptionV5.jsx` at `/game/:gameId`.
- **Play with Coach** — `routes/coach_play.py` plus the `coach_play/` subsystem. 498 sessions, 71,706 `pwc_session_traces`.
- **Puzzle and training supply** — 51k community puzzles, 53k training positions, 11.8k onboarding puzzles. The real-user report shows lesson supply alive for **8 of 8** users, the only surface with full reach.
- **Billing** — `routes/billing.py`, a real Razorpay client, `/config`, `/create-order`, `/verify-payment`. 3 `payment_intents` rows.
- **Auth** — email/password, Google OAuth, dev mode, invite-gated pre-launch.
- **Admin tooling** — 10 admin routes including caption authoring, detector review, geometry gaps, reason judging.

### Partial — built but not reaching users

- `COACHING_CONTEXT_V1_ENABLED=true` but `COACHING_CONTEXT_V1_ROLES=admin,super_admin`.
- `PWC_UNIFIED_EXPERIENCE_V1_ENABLED=false`, roles `admin,super_admin`. A QA gate (`docs/qa/play_with_coach_unified_experience_qa_gate_2026_09_14.md`) records **staging PASS / production HOLD**, held on three process gates — no remote staging environment, no post-deploy smoke test, no human UAT — with zero code defects.
- Progress cohort: 49 enrolled, 5 eligible users never enrolled, enrolment is manual.

### Unused

- **12 of 373 services are referenced nowhere**, including by tests and scripts: `authored_templates_parth`, `blunder_anatomy`, `coach_review_service`, `depth_explanations`, `deterministic_principle_caption_generator`, `explanation_templates`, `human_coach_integration`, `opening_deviation_detector`, `position_explainer`, `principle_caption_bridge`, `static_board_lessons`, `teaching_depth_pilot`.
- **13 collections exist with zero rows**: `mistake_cards`, `mistake_patterns`, `puzzles`, `concept_tests`, `concept_test_results`, `reflection_results`, `user_misconceptions`, `move_self_ratings`, `home_today_answers`, `game_review_validation_reviews`, and three embedding collections — `analysis_embeddings`, `game_embeddings`, `pattern_embeddings`. The embeddings trio suggests a semantic-search capability that was modelled and never built.
- **3 unrouted pages**: `EndgameLesson`, `LabClassic`, `TrainingNew`.
- Roughly 20 `*_backup_*` collections from past migrations still sit in the production database.

---

## 3. Coaching intelligence assessment

### How it works

Stockfish (`PUNISHMENT_DEPTH 18`, `PUNISHMENT_PV_PLIES 12` in `services/stockfish_service.py`) produces per-move `cp_loss`, best move and principal variations, stored in `game_analyses.stockfish_analysis.move_evaluations`. `services/caption_facts.extract_facts` derives deterministic board facts. `services/caption_pipeline.build_move_teaching_decision` is the single composition point, and 28 authored rule files in `backend/data/captions/*.json` hold the sentence templates, selection conditions and teaching principles.

**Verified:** Play with Coach routes through the same function (`services/realtime_coaching_feedback.py`, `routes/coach_play.py`), so live coaching and game review share one truth layer. This is the system's best architectural decision.

### Verification

`services/caption_claim_verifier.py` and `services/caption_verifier.py` check rendered claims against the position. A pre-commit hook in `.githooks/pre-commit` blocks coaching prose written outside the central layer.

**Gap:** `POST /coach/play/chat` calls `generate_response_to_user` then `call_llm` directly and never routes through `build_move_teaching_decision`. It is the one coaching surface with **no per-FEN verification** — an LLM discussing a position with nothing checking its claims.

### Memory and personalization

Real and populated: `coach_memory` (126 rows against 128 users), `user_teaching_memory` (29,974), `user_pattern_events` (144,683), `user_pattern_decay` (128), `focus_history` (62). Weakness tracking and recency decay are genuinely implemented, not stubbed.

### Quality ceiling — the central finding

Measured over 2,383 engine-flagged moves, both sides of 100 games, from `both_sides_analysis` (a fixed collection, so reproducible):

```
the engine's own line explains it          667   28.0%
a deterministic board family could          966   40.5%   <- built, not wired
nothing available                           750   31.5%

by severity        explained   family   nothing
  blunder              321       109        69
  mistake              199       290       194
  inaccuracy           147       567       487
```

And of cards that explain only the recommended move, sampled at 1,236:

```
a played-move fact existed but was unused    249   20.1%
no played-move fact existed at all           987   79.9%
```

**The caption layer is not selecting badly — for four cards in five there is nothing to select from.** Stockfish says a move cost 150cp and no detector can say why.

### Unverified

- Whether LLM narration (`v5_llm_narrator.py`, `v5_llm_polish.py`) is active for ordinary users in production was not traced end to end.
- `DISTILLED_CAPTIONS_ENABLED=1` in production overwrites rule output; its effect on the figures above was not isolated.

---

## 4. Current player journey

```
/  landing  ->  /invite (invite-gated pre-launch)  ->  /login
   ->  /welcome  ->  /onboarding  ->  /diagnostic  ->  /home
```

`/home` renders `HomePageNew.jsx`, which mounts `CurriculumHome` when `PERSONAL_CURRICULUM_ENABLED` is set. It is now `true` in production, although a code comment at `HomePageNew.jsx:435` still states it "is not set on prod at all". The comment is stale; which variant an ordinary user actually sees was not re-verified in a live session.

From `/home` the surfaces are `/play-with-coach`, `/lab` and `/game/:gameId` for review, `/learn` and `/training/*`, `/progress`, and `/journey`.

### Where it fragments — measured, not asserted

`scripts/what_a_real_user_sees.py`, run today against 8 ordinary accounts plus the admin:

```
home dashboard       alive for 6 of 8
coach conversation   alive for 5 of 8
active focus         alive for 5 of 8
progress             alive for 3 of 8
lesson supply        alive for 8 of 8
[admin]              alive for 5 of 5
```

Three distinct failures are visible in one table. Users with 0 or 1 analysed games get a dead home. Users with no usable focus get no coach conversation. Progress is off for 5 of 8 because cohort enrolment is manual. **Every gate fails closed and silently, and the admin account is exempt from most of them**, so none of this is visible from a staff login.

---

## 5. Community readiness

**Nothing exists.** This is the clearest finding in the audit.

An endpoint scan across all 46 route modules for social concepts returns only:

```
/admin/waitlist/invite, /admin/waitlist/uninvite   admin gating, not social
/chat                                              LLM coach, not human chat
/gamification/leaderboard                          solo scoreboards
/training/puzzle-leaderboard
/training/tricks/{trap_key}/leaderboard
/habit-challenge, /habit-challenge/check           self-challenge
/openings/match                                    opening matching, not matchmaking
```

No matchmaking, no human-versus-human play, no friends, no groups, no tournaments, no shared analysis, no mentor model. The `/challenge` frontend route is a habit challenge, not a player challenge.

A keyword grep appears to show social features — 77 backend files match "group", 52 match "friend" — but inspection shows these are substring matches on "grouped", "befriend" in coaching text and similar. The endpoint scan above is the reliable measure.

**Infrastructure that could support community:** user accounts and roles, a notifications system with 16,972 rows, `product_events` telemetry, Razorpay billing for paid tiers, and a mature puzzle and position corpus that would make shared training material cheap to produce. There is no websocket or realtime layer, so live human play would need one.

---

## 6. Architecture and integration findings

**Stack.** FastAPI with motor/MongoDB; React (CRA) with Tailwind; Stockfish at `/usr/games/stockfish`; Docker Compose running backend, mongodb and 2 analysis workers; nginx serving the built frontend from `/var/www/chessguru.ai`.

**External integrations.** Chess.com API, Lichess API, Anthropic API, Google OAuth, Razorpay.

**Background work.** `analysis_worker.py` at 2 replicas against `analysis_queue` (20,019 rows); cron entries for a daily-fix reminder (20:00), focus assignment (03:00) and backups (02:20).

### Limitations and risks

1. **Duplication by accumulation.** 33 services with "opening" in the name, 48 with "coach", 22 with "caption". The project's own notes record an openings sprawl of three lists and five recognizers.
2. **Two writers, one field.** `coaching_decisions` carries both a real event record and a debug log; 1,007 of 1,022 production rows have `outcome: null` and can never be resolved. The same shape appears in `decryption_v5_generated_at` versus `decryption_v5_regen_at`, which disagree on 16% of rows.
3. **Stale analysis data.** Roughly 8,657 of 8,776 flagged user moves still carry 4-ply principal variations written before `PUNISHMENT_PV_PLIES` was raised to 12. One card in eight has its material verdict *inverted* by that truncation.
4. **Documentation drift.** `CLAUDE.md` states `DB_NAME="test_database"`. Production is `chess_coach`. `test_database` exists and is empty, so a query against it returns a confident zero rather than an error — a trap that has already produced wrong measurements.
5. **No frontend error boundary** existed until 2026-10-13; any render crash blanked the entire page with the reason only in the browser console.
6. **No remote staging environment**, which is what holds `PWC_UNIFIED_EXPERIENCE_V1`.
7. **534 test files, but uneven coverage.** Tests pin code behaviour; very few assert rendered output against real data, which is where this product's defects actually live.

---

## 7. Gap analysis

| Capability | Status | Evidence |
|---|---|---|
| Engine analysis of real games | **Implemented** | 19,474 analyses, 2 workers |
| Single coaching truth layer | **Implemented** | review and PWC share `build_move_teaching_decision` |
| Per-claim verification | **Implemented** | `caption_claim_verifier.py`, pre-commit hook |
| Weakness memory and decay | **Implemented** | `user_pattern_events` 144k, `user_pattern_decay` |
| Puzzle and training supply | **Implemented** | alive for 8 of 8 users |
| Billing | **Implemented** | Razorpay, live client |
| Explaining *why* a move was wrong | **Needs improvement** | 31.5% have nothing; 79.9% of alt-only cards have no fact |
| Positional explanation families | **Partially implemented** | `services/blunder_families.py` exists, not wired to captions |
| Reaching ordinary users | **Needs improvement** | Progress 3 of 8; two subsystems admin-gated |
| Cohort enrolment | **Partially implemented** | manual; 5 eligible users missed |
| Chat claim verification | **Missing** | `/coach/play/chat` bypasses the pipeline |
| Remote staging and UAT | **Missing** | holds a finished subsystem |
| Semantic search / embeddings | **Missing** | 3 embedding collections, all empty |
| Human community | **Missing** | no endpoints of any kind |
| Realtime infrastructure | **Missing** | no websockets |

---

## 8. Top 10 recommendations

1. **Wire `blunder_families.py` into captions.** The detection exists and is measured; only the caption wiring and a priority order are missing. Addresses roughly 966 of 2,383 flagged moves — the single largest quality win available, and mostly reuse.
2. **Automate cohort enrolment.** Five eligible users are excluded because a manual step never ran again. A cron entry beside the existing 03:00 focus assignment.
3. **Make `what_a_real_user_sees.py` a release gate.** It already exists and already finds these failures. Nothing should ship while a surface is alive for 3 of 8 users.
4. **Ungate the two admin-only subsystems, or delete them.** `COACHING_CONTEXT_V1` and `PWC_UNIFIED_EXPERIENCE_V1` are finished code that staff see and users do not. The PWC hold is three process gates, not engineering.
5. **Route `/coach/play/chat` through the verification layer**, or label it clearly as unverified. It is the only coaching surface that can state unchecked claims to a player.
6. **Re-analyse the back catalogue at 12 plies.** Roughly 97,360 moves, on the order of 18 engine-hours across two workers. One card in eight currently carries an inverted material verdict.
7. **Stand up a remote staging environment.** It is the blocking dependency for UAT and for anything that cannot safely be tested in production.
8. **Add a `source` field to every multi-writer event record**, starting with `coaching_decisions`. 1,007 unresolvable rows is the cost of not having had one.
9. **Consolidate the opening services** (33 files) behind the canonical recognizer before adding more opening content, and do the same for the caption services.
10. **Treat community as a new build, not an extension.** Nothing exists to reuse except accounts, notifications and the puzzle corpus. The first decision is whether human play requires realtime infrastructure; shared analysis, study groups and mentor review of a saved game can all be built asynchronously on what is already there.

---

## Method and limits

Figures come from the production database `chess_coach`, deployed container environment variables, and `scripts/what_a_real_user_sees.py`. Caption-quality figures come from `both_sides_analysis`, a fixed 100-game collection, so they are reproducible. Figures derived from unsorted `.limit()` scans over `game_analyses` are indicative rather than exact and are marked "roughly".

Not inspected: the 444 scripts individually, mobile and Capacitor behaviour, the gamification and streak subsystems in depth, and whether LLM narration is enabled for ordinary users in production.

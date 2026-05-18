---
name: play-with-coach-teaching-integration
description: Design doc — port the V5 teaching layer (28 principles + 24 shape patterns + named-rule anchors + LLM polish + Parth-bug fixes) into Play with Coach so the lesson lands LIVE during the game, not retroactively in review. Major architectural integration; written 2026-05-18 as a deep plan, not yet implemented.
metadata:
  type: project
---

## The gap (problem statement)

Every teaching improvement of the last two months — V5 caption pipeline, 28 caption_principles, 24 shape_patterns, named-rule anchors, LLM Tier-1 polish, Parth's bug-fix sweep (pin/skewer, hanging perspective, free-piece eval gate, fork filter, engine-meta sweep), endgame principles (RULE_OF_SQUARE, OPPOSITION) — all ship to `/lab` (the game-review surface).

**They do NOT ship to `/play-with-coach`** (the live-game surface). Play with Coach uses `realtime_coaching_feedback.py`, a separate path with its own per-move message generation. A player at 1200 plays a live game and the coach says *"Hmm, Nc4 lost about 6 pawns. Ke3 was better."* Then they open the same game on /lab and suddenly see *"Rule of the Square — Their pawn on g3 runs to promotion. Your king on d4 is too far. e3 catches it in time."*

The lesson lands in the WRONG place. The named pattern matters most when the player JUST made the mistake and the board is still in front of them — not 30 minutes later in review.

## Goal

A live player in a Play with Coach game sees the SAME named-pattern teaching as in review, at the moment it's most actionable: right after their move.

## Non-goals (this design)

- Replacing the realtime layer's voice/tone work entirely. Rating-aware classification ("for 1200 this is inaccuracy, for 1900 this is blunder") and silence rules stay.
- Building a new Socratic-questioning layer. That's a separate product direction.
- Wiring `coach_memory` or `player_identities` collections (those are future work and don't gate this integration).
- Frontend redesign — sidebar layout stays; only the content it renders changes.

## Current architecture (both paths)

### Review (`/lab` → `/game/:gameId`)

```
analysis_worker.py
    ↓ Stockfish per move at depth 18 → eval, best_move, PV
    ↓ writes game_analyses.stockfish_analysis
routes/coach.py per-move read endpoint
    ↓ lazy regen if decryption_v5_version < V5_COACHING_VERSION (=16)
game_decryption_v5_service.generate_game_decryption_v5(pgn, user_color, move_evals, user_id, db)
    ↓ per move:
    ↓   caption_facts.extract_facts(fen_before, played_san, best_move_san, eval_before_cp,
    ↓                                eval_after_cp, cp_loss, pv_after_played, pv_after_best,
    ↓                                move_history_san, mover_is_user)
    ↓   → facts dict with 28 principles' evidence + shape patterns + threats + alignments
    ↓ caption_rules._render_caption_dict(facts) → renderer-rule caption text
    ↓ V5 wiring applies once_per_game suppression (line 3186-3218)
    ↓ writes decryption_v5_data per move: caption, principle_id_used, principle_cue,
    ↓   rule_name, shape_pattern_id/name, etc.
llm_caption_generator.generate_caption_for_move(move) [optional, run separately by regen_pilot]
    ↓   resolve_priority(move) → anchor_name, anchor_detail, allowed_moves, protected_entities
    ↓   build_polish_prompt(decision) → LLM gpt-4.1-mini
    ↓   verify_caption(raw, decision) → preserved entities
    ↓ writes decryption_v5_data[i].caption_llm

Frontend reads decryption_v5_data per move; renders caption / caption_llm / principle_cue.
```

Latency-tolerant: lazy regen is ~1-3 min per game, run once on first view.

### Live (`/play-with-coach`)

```
routes/coach_play.py POST /api/coach/play/move
    ↓ Stockfish per move at depth (variable, ~12-18) → eval, best_move, PV
    ↓ realtime_coaching_feedback.generate_move_feedback(...)
    ↓   _classify_move_quality(cp_loss, user_rating) → rating-aware quality label
    ↓   builds MoveFeedback dataclass:
    ↓     - user_move_quality (excellent/good/inaccuracy/mistake/blunder)
    ↓     - best_move + brief why
    ↓     - coach's counter-move + brief why
    ↓     - Socratic question if mistake/blunder
    ↓   message body composed in-line with hardcoded strings + a few patterns
    ↓ writes coach_messages collection
Frontend polls GET /api/coach/play/move-feedback/{session_id} every ~1s.
```

Latency-sensitive: user expects feedback within ~2-3s of their move.

### What's MISSING in the live path

- No call to `extract_facts` → no principle detection, no shape detection, no aligned-pieces evidence, no SEE-based threat extraction.
- No call to `resolve_priority` → no anchor_name / anchor_detail.
- No call to `generate_caption_for_move` → no Tier-1 polished caption with protected entities.
- No clickable rule name (because `principle_id_used` and `rule_name` never get set on live moves).
- No coexistence between Phase 2-5 endgame principles (RULE_OF_SQUARE, OPPOSITION) and the live message.

Result: ~6 months of teaching work invisible to the primary training surface.

## Design options

### Option A — Parallel surfacing (lowest-risk wedge)

The live coach_play route additionally calls `extract_facts → resolve_priority → generate_caption_for_move` after the existing realtime feedback. Two coaching strings come back: the realtime message AND the V5 named-pattern caption.

Sidebar renders both, stacked. The realtime message keeps its current voice ("Hmm — that hung your knight"). The V5 caption surfaces underneath with the clickable anchor name ("Loose piece on the board — Your knight on e5 has no defender.").

**Pros:**
- Minimal change to realtime path; no regression risk.
- All V5 surface area immediately exposed to live play.
- Clickable rule name lands here naturally.

**Cons:**
- Wordy when both fire on the same move. ("Hmm — that hung your knight. ... Loose piece on the board — Your knight on e5 has no defender.")
- Doubled latency: realtime + V5 + LLM polish.
- Two voices competing on the same move feels patched.

### Option B — Direct replacement

Drop realtime message generation entirely. V5 caption becomes the only coaching string per move. Realtime layer keeps only `_classify_move_quality` (silence-vs-speak decision based on user_rating + cp_loss).

**Pros:**
- Cleanest architecture; one teaching surface.
- No voice duplication.

**Cons:**
- Throws away tuned realtime voice (rating bands, Socratic question generation, coach-counter-move explanation).
- Risk of regression for established users.
- V5 captions are short (≤18 words); realtime is more conversational. Tone shift may feel cold.

### Option C — Unified decision service (cleanest long-term, biggest refactor)

New service: `coaching_message_service.coaching_decision_for_move(move_data, user_rating, surface, suppression_state) → CoachingDecision`.

Both review and live call this same service. It internally calls extract_facts + resolve_priority + (optionally) generate_caption_for_move, and additionally encapsulates:
- Rating-aware silence/speak decision.
- Voice tone selection (calm / urgent / praise / critique).
- Suppression-state update (per-game, per-principle-state-key).
- Coach-move teaching (when coach plays, surface its principle hits).

Both `/lab` per-move endpoint and `/play-with-coach` per-move route consume the same decision shape. Frontend renders consistently.

**Pros:**
- Single source of truth for coaching content across both surfaces.
- Future-proof for Socratic mode, coach_memory, identity work.
- Eliminates the dual-pipeline problem permanently.

**Cons:**
- Significant refactor; both surfaces churn.
- Mid-state risk during migration.
- LLM polish cost/latency tradeoff still needs solving.

### Option D — Phased wedge → unified (recommended)

**Phase 1** (Option A wedge, ~1-2 weeks):
- Add V5 calls to coach_play live path.
- Surface V5 caption alongside realtime message in the sidebar.
- LLM polish is async: show deterministic draft immediately, swap to polished when LLM returns.
- Ship to a feature flag first; validate live UX.

**Phase 2** (consolidation, ~2-4 weeks):
- Extract a `coaching_decision_for_move` service.
- Migrate review path to it.
- Migrate live path to it (drop the Phase-1 parallel surfacing in favor of the unified output).
- Centralize suppression state.

**Phase 3** (silence + voice tone, ~1-2 weeks):
- Move rating-aware silence decision into the unified service.
- Refactor voice tone selection (composes named-pattern caption with appropriate tone for blunder/inaccuracy/positional).

**Phase 4** (deprecate realtime path, ~1 week):
- realtime_coaching_feedback.py becomes a thin shim or is removed.
- All live coaching flows through the unified service.

**Pros:**
- Shipping value at every phase.
- Backout possible at any phase.
- Architectural cleanup done in a controlled way.

**Cons:**
- Live in dual-state for ~6-8 weeks total.
- More commits/PRs than option C in one shot.

## Recommended path: Option D, leaning hard on Phase 1 first

Get the teaching layer VISIBLE in live play as fast as possible. Defer architectural cleanup until we've validated the live UX is right.

## Open questions for Mohit

1. **Latency budget.** Is 2-3s acceptable for the polished caption to appear? Or should the live surface always use the deterministic draft (sub-second) and skip LLM polish?

2. **Composition rule when realtime + V5 both speak.** If realtime says "Hmm, that hung your knight" and V5 says "Loose piece on the board — Your knight on e5 has no defender", which is primary? Some options:
   - Realtime above, V5 below as a "lesson" sub-block.
   - V5 only when there's a named-pattern hit; realtime fallback otherwise.
   - Compose into one string: "Hmm — Loose piece on the board. Your knight on e5 has no defender."

3. **Coach's move (live).** Should V5 fire when the COACH plays? E.g., coach plays Bg5 setting up a pin. Should the sidebar say "Coach plays Bg5 — Two pieces on a line. Watch out for the pin"? That's a teaching opportunity that doesn't exist anywhere today.

4. **Silence rules.** Should V5 captions respect the realtime silence rule (don't talk after every move for 800-rated)? Or always speak when a principle fires?

5. **Suppression state across sessions.** Currently V5 suppression is per-game-record. In Play with Coach, the same player has many session games. Should suppression be per-session or per-player or per-game? If per-player, the same lesson never repeats across all their training games — too aggressive. If per-game, fine.

6. **Pre-existing live features.** Teaching modes (traps/endgames), escape squares quiz, pre-move guardian — how do they interact with V5 captions? Likely independent (different triggers, different surfaces) but worth confirming no conflict.

7. **Feature flag scope.** Roll out per-user, per-game, or globally? Per-user feature flag is safest.

## Risks

- **Latency regression.** Live coaches must respond fast. Adding V5 + LLM polish can push past 3-5s if not handled carefully (async polish, deterministic-first).
- **Voice collision.** Two systems generating coaching text on the same move can feel discordant if not composed thoughtfully.
- **Suppression bug surface.** Today the `once_per_state_entry → once_per_game` collapse (Mohit flagged this 2026-05-18 as foundational) is a known limitation. Live play makes it more visible — a player plays many games per session, same lesson can repeat.
- **Coach memory / identity wiring.** Not in scope here, but the unified service is where they'd plug in. Designing the service to accommodate them is a forward-looking concern.

## Dependencies & related memories

- `[[endgame-principles-backlog]]` — Phases 4-5 will benefit from this integration immediately.
- `[[clickable-rule-names]]` — the live surface is where clickable rules have most leverage.
- `[[named-rule-real-game-examples]]` — pairs naturally; live game becomes the source of examples.
- `[[teaching-not-reading]]` — the new live captions must obey the same voice rules.
- `[[sub1500-memory-anchors]]` — the entire point of moving teaching to live play.
- `[[no-yes-man]]` — when implementing, verify each integration point against actual user-visible output, not just the V5 data layer.
- `[[v5-caption-rewrite-no-patches]]` — applies; this is integration, not patching V5. But the live path will need its own careful audit before shipping.
- `[[v5-lazy-generation-mechanic]]` — review uses lazy regen; live needs synchronous regen per move. Different mechanism.

## What I'm NOT proposing (yet)

- A specific schema for the unified `CoachingDecision` dataclass.
- A specific feature flag implementation.
- LLM-polish-vs-draft policy details.
- Frontend component changes (left to UI iteration after Phase 1 lands).
- Storage schema changes for coach_messages collection.

These belong in the implementation design doc once you sign off on the high-level direction.

## Next step

Mohit reviews this plan. Open questions (latency, composition, coach-move, silence, suppression scope, pre-existing-features interaction, flag scope) get answered. Then I write the Phase 1 implementation design and start coding behind a feature flag.

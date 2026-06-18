# Consequence-Detector Teaching Run — Scope

**Status:** Draft for sign-off. The ~$1k one-time Opus spend happens only after approval.
**Date:** 2026-06-18
**Goal:** use a **one-time, offline Opus run on ~500 games** to TEACH the free deterministic caption system — specifically to build a **verified consequence-detector library** (the lever we proved works). Opus is the *teacher*, never the live server; the live site stays free + 0-lie.

## Why consequence-detectors, NOT another template re-distill (proven this session)
- We re-distilled the move-type templates from a diverse Opus corpus → fixed the *voice*, but the gap held at **23–53**. Reason (measured): the residual is **composition/judgment**, which templates can't learn no matter how much gold you distill into them. Adding more content (slot-composer) went **flat/worse** (verbose, repetitive).
- The ONE thing that produced a **gold-equal** caption was building a **consequence detector**: the pawn-chase detector made `Bg5` match gold (and beat it on the better-move). Each consequence-type we cover = another batch of moves that go gold-equal.
- So the corpus's highest-value use is **mining the consequences Opus explains → building a verified detector per common type.** That climbs the free system systematically; re-distilling templates does not.

## Generation method (decided 2026-06-18): WHOLE-GAME, not per-position
Send each COMPLETE game to Opus in one call (`whole_game_gold.py`) — Opus sees the full
arc and produces **cross-move narrative** captions (tracks a hanging piece / a pin /
a plan across moves). Measured on 3 games: **$0.57/game (100 games ≈ $57), 92% verified-kept**,
and dramatically better context than per-position batching (which was $1.39/game). Fewer
calls = less Claude-Code per-call overhead = cheaper AND better.
**Caveat:** the cross-move narrative is gold/benchmark/cache value — per-move deterministic
detectors can't replicate "your bishop can still win that rook from 3 moves ago." Detector-
mining still extracts the per-move consequences; the narrative is the LLM-only residual.

## Plan
1. **Generate Opus gold for ~500 games** (offline). Easy-English prompt + the narrator verifier + correct-loop (only verified golds kept). Two outputs:
   - the **teaching corpus** (input to mining), and
   - a **cached gold store** (serve directly where positions recur — openings especially).
2. **Mine the corpus for consequence-patterns** (data-first; like `mine_gold_concepts.py` but for *consequences*): chase-a-piece, hangs-a-piece, allows-a-fork, opens-a-file-against-you, traps-a-piece, overloads-a-defender, allows-a-passed-pawn, wins-a-tempo, weakens-the-king… Rank by frequency.
3. **Build a verified detector per common consequence-type** — each like `chase_consequence`:
   - board/PV check (engine-true), **negative tests** (must-not-fire cases), an **approved snippet**, a **consequence-keyed lesson**, a confidence/gate. Verifier authored FIRST (per `verify-detectors-first`).
4. **Wire each into the slot-composer** (the existing `bake_slot_composed`), gated by cp-class. Each detector → more gold-equal moves.
5. **Cache the 500 games' gold** for direct serving on covered positions.

## Cost (one-time, offline)
From a 5-game sample (311 moves) → exact per-game cost, extrapolated to 500. Ballpark **~$1k (≈$800–1,500)**. Live serving cost stays **$0** (deterministic, cached).

## Acceptance
- Each detector: 0 board-lies, passes its negative tests, fires only where the consequence is real.
- Aggregate: lift the demo game (and a held-out game set) on the blind harness from **~27%** toward a target we set after the first 3–4 detectors prove their per-type lift. **Measure per detector; keep the ones that lift.**
- 0 board-verified false claims maintained throughout.

## Honest ceiling (stated up front)
Truly-quiet positional moves with **no computable consequence** stay below gold (composition is LLM-shaped — proven). For the 500 corpus games, the **cached gold** covers those; for *new* games they get the capped free system. So this maximizes the free system + gives a gold cache, but does not make the *free* path equal Opus on quiet moves.

## Ties
[[project_user_games_gold_detector_loop]] (teach detectors from user-game gold; detectors assert engine-confirmed facts) at corpus scale · [[project_why_now_coach_layer]] (the slot-composer + verifier-first spine) · `bake_slot_composed.py` (chase_consequence = the template) · `distill-caption-template` / `verify-detectors-first` skills.

---
name: worker-side-detector-migration
description: Hybrid model — cheap geometric detectors stay lazy on-read; expensive Stockfish-dependent detectors (TAC_LEGAL and sisters) are born worker-side. NOT a wholesale migration.
metadata:
  type: project
---

**Revised 2026-05-18 after architectural pushback from Mohit ([[no-yes-man]]).**

The earlier version of this memo proposed migrating all 52 existing V5 detectors from lazy on-read regeneration ([[v5-lazy-generation]]) into `analysis_worker.py`. **That was over-engineered.** This memo captures the correct hybrid model.

**The decision rule:**
- Detector needs only FEN + geometry to fire → **stay lazy**.
- Detector needs Stockfish during its own check (e.g. forcing-continuation probe, multi-ply tactical verification) → **born worker-side**.

**Why lazy is correct for cheap detectors:**
1. **Version-churn cost.** `V5_COACHING_VERSION` bumped 22 times in ~3 weeks during active build-out. Worker-side = 4400 games × ~5s = 6 hours of compute per bump. Lazy = free (next read picks up).
2. **Bug self-healing.** Per [[design-clean-code-leaky]] — implementation leaks bugs. Lazy regen is the de facto safety net; bad caption ships → fix code → next page load is correct. Worker-side persists bugs as DB rows until backfill.
3. **Iteration speed.** Edit → push → next read picks up vs Edit → push → backfill → wait → verify.
4. **Latency budget.** 28 principles + 24 shape patterns are FEN-only, <100ms per game on read. Lab page already loads 200KB of analysis JSON — sub-100ms detector work is invisible.

**Why worker-side is correct for expensive detectors:**
- TAC_LEGAL_PATTERN's forcing-continuation probe = ~2s per candidate × N candidates. Unacceptable on read path.
- Same will apply to BODEN / SMOTHERED / GRECO / FRIED_LIVER and any future Stockfish-dependent detector.

**Implementation pattern for worker-side detectors:**
1. Detector runs in `analysis_worker.py` AFTER the Stockfish per-move pass completes.
2. Output is a list of fires persisted as a NEW field on `game_analyses` (e.g. `tac_legal_fires`, `tac_boden_fires`).
3. The V5 caption pipeline (lazy reader) checks the field; if present, uses pre-computed fires; if absent (older games before detector shipped), runs detector inline as fallback.
4. A separate backfill script can re-run the detector over historical games when needed (but only when the detector logic actually changes — not on every V5 version bump).
5. Each worker-side detector gets its own version field (e.g. `tac_legal_version`) independent of `V5_COACHING_VERSION` so cheap-detector bumps don't trigger expensive backfills.

**Current detector inventory:**

| Detector class | Cost per game | Location |
|---|---|---|
| 28 V5 principles (incl. 5 endgame: SQUARE_RULE, OPPOSITION, ROOK_BEHIND_PASSER, PASSED_PAWN_KING_ACTIVE, ACTIVE_KING) | <50ms | **Stays lazy** |
| 24 shape patterns | <50ms | **Stays lazy** |
| 3 Phase-6 cross-opening (BISHOP_TRADE_DOUBLES_PAWN, F2_F7_STRIKE, TRAPPED_KNIGHT) | <50ms | **Stays lazy** |
| TAC_LEGAL_PATTERN ([[tac-legal-geometry-detector]]) | ~2s × N | **Born worker-side** |
| Sister tactical traps (BODEN, SMOTHERED, GRECO, FRIED_LIVER) | 2-10s | **Born worker-side** |

**When to revisit:**
- If lazy-side read latency ever exceeds ~500ms p95 → migrate the heaviest cheap detectors to worker.
- If V5 detector churn slows down (post-build-out, maintenance mode) → reconsider full migration since the backfill cost is amortized over fewer version bumps.
- For now (active build-out phase) the hybrid model wins.

**Companion memories:** [[v5-lazy-generation]], [[tac-legal-geometry-detector]], [[design-clean-code-leaky]], [[geometric-recognition-over-named-sequences]].

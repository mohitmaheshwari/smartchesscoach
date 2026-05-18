---
name: worker-side-detector-migration
description: Phase-7 backlog — migrate V5 caption detectors (named principles + tactical traps) from lazy on-read regeneration into analysis_worker.py so they run once per game and persist on game_analyses docs.
metadata:
  type: project
---

Phase-7 backlog: migrate V5 caption detectors from lazy on-read regeneration (current state, [[v5-lazy-generation]]) into `analysis_worker.py` so they run once per game and persist on the game_analyses doc.

**Current state (locked truth, [[no-yes-man]]):**
- `decryption_v5_data` is regenerated lazily in `routes/coach.py` on every read, gated by `V5_COACHING_VERSION`.
- All Tier-1 endgame principles (Phases 2-5), all 23 shape patterns, and the 3 Phase-6 cross-opening detectors run on-read.
- Mohit and I have **discussed** moving to worker-side, but no migration code exists yet (confirmed 2026-05-18).

**Why migrate:**
1. Detectors are growing too expensive for read-time. The forthcoming TAC_LEGAL_PATTERN detector ([[tac-legal-geometry-detector]]) needs a 3-ply Stockfish forcing-continuation probe per fire — unacceptable latency on the dashboard/Lab read path.
2. Play-with-Coach live coaching needs pre-computed fires for instant lookup, not a re-run of detectors per move.
3. Same outputs every time → caching them is "free" reliability.
4. Decouples ship cadence: detector logic changes no longer require version bumps + cold cache pain on every page load.

**How to apply:**
- Add a `v5_decryption` field to game_analyses documents written by analysis_worker.py
- Run all 28 V5 principles + 24 shape patterns + 3 Phase-6 detectors + future TAC_LEGAL etc. inside the worker after Stockfish analysis completes
- Keep `V5_COACHING_VERSION` for migration gating: if doc.v5_coaching_version < current → re-run on read OR queue a re-analysis job
- routes/coach.py reads from the persisted field, falls back to lazy generation only when missing or stale
- Add a backfill script that re-runs detectors over the existing 4400+ analyzed games in batches

**Risks:**
- Worker latency grows. Current Stockfish pass is ~5-15s per game; detectors add ~1-3s; TAC_LEGAL forcing-probe adds another ~3-10s per candidate position.
- Version-mismatch handling needs robust fallback to lazy regen to avoid blank captions while backfill runs.

**Ship order (proposed):**
1. Migrate the 28 deterministic V5 principle detectors first (cheapest, no Stockfish dependency in detector layer beyond what's already in worker).
2. Migrate the 24 shape patterns next.
3. Migrate the 3 Phase-6 cross-opening detectors.
4. THEN ship TAC_LEGAL_PATTERN directly into the worker (skip the lazy stage entirely).
5. Repeat for sister tactical detectors (BODEN, SMOTHERED, GRECO, FRIED_LIVER).

**Why this order:** prove the migration mechanics on cheap detectors before introducing the expensive ones.

# Motif Strength/Weakness Profile — Backlog

**What this is:** a two-sided, engine-gated profile of *which tactical motifs the player is good at executing and bad at avoiding* — fork / pin / skewer / discovered attack, in both directions (you EXECUTE it = strength, you ALLOW it = weakness). The mirror/sibling of the existing domain-level `strength_profile_service`, but at motif granularity.

Status: **BUILT 2026-06-21→23** (this backlog was written before discovering the work already landed). Core is shipped — `backend/services/motif_profile_service.py` (two-sided fork/pin/skewer: made_sound/made_tunnel/got), wired at analysis time (`analysis_worker.py:533` → `player_profiles.motif_profile`/`.motif_recognition`), endpoints `/motif-profile` `/motif-recognition` `/motif-drill/{motif}` (`routes/player.py:840+`), engine-verified (fork 100% / pin 100% / skewer 87%), thresholds locked-via-data. See [[project_motif_profile_backlog]] memory. Only the items under "Deferred" below remain.

---

## The load-bearing rule (do not violate)
**Geometry is never credited without Stockfish grading the MOVE first.** Two gates, always:
1. **Geometry gate** — the fork/pin/skewer is real (the verified primitives below).
2. **Move-quality gate** — the engine grades the move itself (`cp_loss ≈ 0` / `evaluation ∈ {best, excellent, brilliant}`).

Three real signals fall out of the two gates:
| Geometry | Move grade | Meaning |
|---|---|---|
| motif you made | good (cp_loss≈0) | ✅ strength — "you find forks/pins" |
| motif you made | blunder (cp_loss high) | ⚠️ **tunnel vision** — "you saw the fork, missed the bigger threat" |
| motif you allowed | blunder | ❌ weakness — "you walk into forks/pins" |

Fork winnability is part of gate 1: a fork must hit ≥2 pieces it can actually *win* (SEE/undefended), not just "hits 2." A pin is high-value-behind-low on a **rank, file, or diagonal**, and only real if the front piece can't slide away.

---

## What already EXISTS (verified, reuse — don't rebuild)
- **Fork geometry, winnability-checked:** `caption_facts.py:665` `_multi_target_attack_evidence` ("separately-winning threats" via `see_cp`) + `:716` `_filter_king_defended_overvalue_targets`.
- **Pin/skewer geometry, all 3 directions + value ordering + escape check:** `caption_facts.py:810` `_aligned_pieces_evidence` — diagonal/file/rank, `front_value_vs_rear` (lower=pin, higher=skewer), `front_can_move_along_line`, `rear_is_king`.
- **Discovered attack:** `caption_facts.py:925` `_discovered_attack_evidence`.
- **Fork-as-WEAKNESS, already shipping + engine-gated:** `failure_allows_fork` in `data/captions/R12_blunder.json`, gated by `_opp_reply_forks` (`caption_claim_verifier.py:152`).
- **Move-quality gate already enforced on strength side:** `strength_profile_service.py:143-174` only counts `evaluation ∈ {brilliant,best,excellent}`.
- **`extract_facts` is a pure function** (no DB) reading only fields `game_analyses.move_evaluations` already stores (fen, played/best move, pv, cp_loss).

## What is MISSING (the actual build)
1. **Weakness-side predicates for pin / skewer / discovered** (only fork-allowed exists). Mirror `failure_allows_fork`; each gated on a real engine verifier (pin verifier is the hard part — x-rays, pawn-front false pins). Gate via `/author-r12-predicate`, **≥2 clean examples required** (corpus-probe first — NOT yet run).
2. **The motif aggregator** (the new layer): per game, gate geometry + move-quality, tally per motif/direction, write a `motif_profile`. Two-sided. Reuses the `strength_profile_service` loop pattern.

---

## Hook points
- **NOW: analysis layer.** `analysis_worker.py` does NOT call `extract_facts` today (grep = 0). The aggregator hooks right next to the existing strength-profile call (`analysis_worker.py:1374`): reads stored `game_analyses.move_evaluations`, runs `extract_facts` itself (pure fn), applies both gates, writes `motif_profile`. Once per game, at analysis time.
- **LATER (BACKLOGGED): live play with Coach.** The same two-sided motif detection should also run during a live coach game so the coach can react in-the-moment and feed the profile from coach games too. Deferred — `coach_play.py:3370` already calls `extract_facts` live, so the wiring point exists; this is the *aggregation + profile-write from live sessions* that's deferred, not the detection.

## Open design choice (lock later via `/lock-via-data`, not now)
Persist motif tags into `move_evaluations` during analysis (heavier write, but caption layer reuses them → kills recompute-every-render waste) **vs.** standalone aggregator re-deriving geometry from stored analyses (zero hot-path change). Both sound.

---

## Deferred items (the queryable list) — what's LEFT after the 2026-06-21→23 build
- [ ] **Enable the frontend** — the motif card is built in `frontend/src/pages/UnifiedProgress.jsx` but DISABLED behind `false &&`. Product decision to flip on.
- [ ] **Discovered-attack motif** — only fork/pin/skewer wired; `discovered` noted "to add after its audit" in motif_profile_service.py. Needs the audit + wiring.
- [ ] **Live-play-with-Coach motif profiling** — analysis-time path done; running the detection live + feeding `motif_profile` from coach sessions is still deferred. (Detection wiring exists at `coach_play.py:3370`.)

## DONE (was deferred, now shipped)
- [x] Two-sided fork/pin/skewer aggregator, engine-verified — `motif_profile_service.py`.
- [x] **Tunnel-vision signal** (motif made + cp_loss high) — shipped as `made_tunnel`.
- [x] Pin/skewer detection both sides — shipped (pin 100%, skewer 87% audited).

_Append new deferred items here. When Mohit asks "do we have anything in backlog?" — check this file._

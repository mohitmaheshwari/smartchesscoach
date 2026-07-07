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
- [ ] **Discovered-attack motif** — see scope below (2026-07-07).
- [ ] **Loose-piece motif** — see scope below (2026-07-07).
- [ ] **Live-play-with-Coach motif profiling** — analysis-time path done; running the detection live + feeding `motif_profile` from coach sessions is still deferred. (Detection wiring exists at `coach_play.py:3370`.)

---

## Scope — discovered-attack + loose-piece (2026-07-07)

**Signed off by Mohit:** _pending_ · **Author:** Claude · **Origin:** conversation 2026-07-07 after the openings-fix session

### What this is (plain English)

Extend the two-sided motif profile from three motifs (fork / pin / skewer) to five (+ discovered attack, + loose piece). Same shape as the existing card — for each motif, show what the user is good at executing and bad at avoiding, engine-gated on both sides. No new UI: the existing motif card in `UnifiedProgress.jsx` renders whatever `MOTIFS` contains.

### Why (data — sample: 5,290 user moves, 8 top users, 20 games each)

| Motif | Rate at 600-1500 | Verdict |
|---|---|---|
| discovered_attack (offensive) | **4.59%** of user moves | Ideal motif frequency — ships |
| loose piece — offensive (spot enemy free piece) | 20.4% opportunity, **49% recognition rate** | Novel gap not tracked anywhere today — ships |
| loose piece — defensive (Stockfish-gated hang) | 1.83% of user moves | Ships (see redundancy note below) |
| trapped rook / knight / bishop (existing detectors) | **0.00%** | Existing detectors too narrow — DROP for now |

**Redundancy note (defensive loose piece):** 97.5% of loose-piece hangs also carry `cognitive_gap = piece_safety`. That's OK — the motif card is a different diagnostic lens (pattern recognition) from the gap category (mistake type). We deduplicate at the coaching-message layer: when both fire on the same session, prefer the motif framing (more concrete) and suppress the category message. Same events, single surface.

### Motif #4 — discovered_attack

**Definition:**
- **Offensive:** you play a move whose engine grade is `∈ {brilliant, best, excellent}` AND `_discovered_attack_evidence` fires on the move (own sliding piece uncovers attack on an enemy piece).
- **Defensive:** opponent's engine-refuted move (cp_loss high on your immediate blunder) exploits a discovered attack you allowed.
- **Tunnel-vision:** you played a discovered attack but missed a bigger threat (mirrors existing fork/pin `made_tunnel`).

**What already exists (reuse — don't rebuild):**
- Detector: `caption_facts.py:989` `_discovered_attack_evidence` — verified, has feedback-driven bug fixes (fb_a6f596afbba0 etc.)
- Motif profile shell: `motif_profile_service.py` — same two-gate pipeline as fork/pin/skewer
- Hook point: `_move_motifs()` line 296 — one-line extension consumes the existing fact

**What is missing (the actual build):**
1. Add `"discovered"` to `MOTIFS` list (line 24) — one line
2. Extend `_move_motifs()` to emit `discovered` when `f.get("discovered_attack_evidence")` — 2 lines
3. Extend the R12_blunder failure-mode predicate for the defensive side — `_opp_reply_discovers` verifier (mirrors `_opp_reply_forks` at `caption_claim_verifier.py:152`); needs ≥2 clean corpus examples per `/author-r12-predicate`
4. Backfill: run `regen_motif_profiles_with_opp_creating_move.py` for all users after ship

**Acceptance:**
- Corpus-probe against 50-game sample: discovered_attack precision ≥90% (engine-verified — the played move's cp_loss ≈ 0 AND the geometry check passes)
- Card renders on `/progress` for a user with any discovered attacks in last 40 games
- No regression on fork/pin/skewer rates (backfill re-runs them; numbers should match pre-ship)

### Motif #5 — loose_piece

**Definition:**
- **Offensive (recognition):** enemy has a piece with `attackers ≥ 1, defenders == 0` before your move, and you either
  - (a) captured it with `cp_loss < 50` → `made_sound`
  - (b) played a different move with `cp_loss ≥ 100` → `missed` (the recognition-failure signal)
- **Defensive (hanging):** after your move, one of YOUR pieces has `attackers ≥ 1, defenders == 0`, and Stockfish's PV first-move captures that loose piece, and `cp_loss ≥ 150`.

**What already exists (reuse — don't rebuild):**
- Undefended-piece geometry: `caption_facts.py:603` `_pieces_now_undefended` — pure function, already returns the exact shape needed
- Static exchange evaluation (SEE): `coach_play/coach_blunder_guard.material_hung_after` — for handling piece-defends-piece cases where a naive attackers/defenders count over-fires
- Piece_safety gap tag: `cognitive_gap.piece_safety` — the redundant category we dedupe against

**What is missing (the actual build):**
1. New helper `_loose_piece_events(fen_before, played_san, pv_after_played, mover_is_user)` in `caption_facts.py` — returns `{offensive: bool, defensive: bool, target_square, target_piece}`. Reuses the geometry from `_pieces_now_undefended` + adds the PV-captures-loose check for defense.
2. Add `"loose"` to `MOTIFS` list
3. Extend `_move_motifs()` to emit `loose` when the offensive gate fires
4. Extend R12_blunder for defensive side: `failure_allows_loose_hang` variant with the deduplication gate that suppresses the `piece_safety` message when this fires
5. **Frontend microcopy:** copy for the loose-piece card must NOT say "your piece safety needs work" (that's the piece_safety category's job) — must say "You take free pieces X% of the time" (offense) and "You leave pieces undefended in X% of your losses" (defense). Different framing on purpose.

**Acceptance:**
- Corpus-probe: offensive recognition-rate at 50 games matches the 8-user probe (~50%, engine-verified via cp_loss on capture move)
- Defensive precision ≥95% (Stockfish PV backs up every claim)
- Coach never surfaces both piece_safety category message AND loose-piece defensive message on the same session

### What we deliberately DROP from this batch

- **Trapped piece.** Existing detectors (`trapped_rook_square`, `trapped_knight_square`, `trapped_bishop_square`) fire 0× across 5,290 moves. They exist for very narrow gates (opening-phase knight-on-rim, specific rook-in-corner shapes). Building a broader trapped-piece detector — one that catches "knight on h5 has nowhere to run after g4" and "queen wandered into enemy camp, can't get back" — is genuinely new work: 3-4 hour scope, needs its own audit, and belongs in its own scope doc. Refile as a separate item, don't cram into this batch.

### Order of work

1. Discovered attack (existing detector → 1-day scope)
2. Loose piece (new helper reusing existing geometry → 2-day scope)
3. Backfill motif profiles across the 43-user cohort — verify no regression on fork/pin/skewer
4. Frontend copy pass on the loose-piece card (different framing from piece_safety)
5. Flip `false &&` gate on the frontend motif card if it hasn't been already

### Data locks (per lock-via-data)

Thresholds already picked from data, not gut:
- Offensive recognition: `cp_loss < 50` (capture is engine-approved)
- Offensive miss: `cp_loss ≥ 100` (playing something else was clearly worse)
- Defensive hang: `cp_loss ≥ 150` AND PV first move captures the loose piece (Stockfish confirms the specific loss)

These match the existing fork/pin/skewer gates for consistency.

## DONE (was deferred, now shipped)
- [x] Two-sided fork/pin/skewer aggregator, engine-verified — `motif_profile_service.py`.
- [x] **Tunnel-vision signal** (motif made + cp_loss high) — shipped as `made_tunnel`.
- [x] Pin/skewer detection both sides — shipped (pin 100%, skewer 87% audited).

_Append new deferred items here. When Mohit asks "do we have anything in backlog?" — check this file._

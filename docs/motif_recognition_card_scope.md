# Motif Recognition Card — Scope

**Status:** awaiting sign-off · **Date:** 2026-06-22 · **Supersedes:** the count-based motif card (v1)

## Why
The v1 motif card scored "weakness" off a *per-game count* (got-forked N times) against a
*relative per-game threshold*. It showed Mohit — a 561-game user — **nothing** (no strength, no
weakness), because counts have no denominator of opportunity. The fix (proven this session) is a
**per-opportunity recognition rate**: when a motif was the engine's best move, did the player play
it? That single change:
- distinguishes a **fundamental weakness** (low rate when opportunity is present) from a **blind
  spot** (rare lapse) — Mohit's exact ask;
- surfaces **strengths** the count hid (Mohit ranks 96th/89th/62nd percentile on fork/pin/skewer).

## What it is (the card — this is the product)
```
YOUR TACTICS  ·  last 15 days (114 games)
────────────────────────────────────────────
Forks      ●●●●●●●●●○   you spotted 66% of your fork chances
           Top 4% of players — a real strength.
Pins       ●●●●●●●●●○   47%  ·  better than 89% of players — a strength.
Skewers    ●●●●●●○○○○   42%  ·  around average (62nd pctile) — closest to work on.
```
- One row per motif (fork, pin, skewer).
- **Headline rate = last 15 days** (windowed by the now-backfilled `date_played`).
- **Verdict + percentile = all-time sample** (stable label that doesn't wobble on a thin 15-day n).
- Verdict bands (lock-via-data, from the 45-user baseline this session):
  - **strength** = ≥ population p75 · **average** = p25–p75 · **work-on** = < p25
  - fork median 41% / p75 52%; pin median 40% / p75 45%; skewer median 39% / p75 44%.

## The metric (verified, single-source)
- **Available** (denominator): the engine's `best_move` creates the motif — detected by the SAME
  verified detectors as everywhere else: `multi_target_attack_evidence` (fork, winnability-checked)
  + `_classify_aligned(aligned_pieces_evidence)` (pin/skewer). `caption_facts.extract_facts`. No new
  detector (single-source-of-truth).
- **Found** (numerator): the player's actual move was a *sound* (`cp_loss ≤ 40`) instance of the
  same motif.
- **Recognition = found / available**, per motif.
- **Honesty constraint shipped in the copy:** fork is winnability-verified → trustworthy absolute %.
  Pin/skewer "available" includes some incidental aligned geometry → the card frames them as **rank
  vs peers** (consistent detector across all users), not a precise absolute. Trust the rank.

## Data flow (no live LLM, no live heavy compute)
Recognition needs `extract_facts` over every move (~11s/150 games) — **too heavy for a live request.**
So, mirroring how `motif_profile` is built:
1. **`analysis_worker`**: when a game is analyzed, compute per-game `{date_played, avail{f,p,s},
   found{f,p,s}}` and append to `player_profiles.motif_recognition.games[]` (small: 7 ints + date).
2. **Read endpoint** `GET /api/motif-recognition`: sum games where `date_played ≥ now−15d` →
   headline rates; sum all games → verdict/percentile. Pure arithmetic at read time.
3. **Backfill**: one script recomputes the per-game tallies for existing analyzed games (reuses the
   baseline script's core). Windowing already works (dates backfilled this session: 411/483 for Mohit).

## Population breakpoints (locked-via-data, v1)
Stored as constants next to `WEAKNESS_RATE`/`STRENGTH_RATE` in `motif_profile_service.py`
(`RECOGNITION_PCTILE = {fork:{p25,med,p75}, pin:{...}, skewer:{...}}`), refittable as the user base
grows. From baseline: 45 users, 120-game samples, ≥8 opportunities/motif.

## Out of scope (v2)
- **Defense / avoidance rate** ("when a fork was threatened, did you stop it?"). Blocked: stored
  evals have no opponent-move entries, so the *threatened* denominator needs per-position threat
  re-derivation. Deferred; card v1 is **offense recognition only**.
- Discovered-attack as a 4th motif.

## Verification (before it reaches a user)
- Re-run the per-FEN claim discipline: spot-check 15 "available" detections per motif against the
  board (is it really a fork/pin/skewer best move?).
- Confirm 15-day sum == direct recompute for Mohit; confirm percentile reproduces (fork 96th).
- `pwc_coaching_lint` on the card copy (no jargon, audience 600-1500).
- Browser-verify the rendered card (Playwright, once session reloads).

## Rollout
Default-off flag `MOTIF_RECOGNITION_CARD`; A/B on `/progress`; backfill recompute; flip after
user-satisfaction sign-off (deploy is gated). Legacy count-card removed once this is live.
```

# Motif Strength/Weakness Profile — Scope (DRAFT, awaiting sign-off)

*Created 2026-06-20. Scope-Driven Development: no code until Mohit signs off. Research +
verified primitives live in [motif_profile_backlog.md](motif_profile_backlog.md).*

## What it will be (in plain English)
A per-user profile that says, for each tactical motif (**fork, pin, skewer, discovered
attack**), whether the player is **good at executing it** and whether they **keep walking
into it** — both directions, scored from their real games. Example output a user would feel:

> *"You find forks well (executed 8, all sound). But you walk into skewers — you've been
> skewered 5 times this month. And twice you played a fork but missed a bigger threat."*

It's the motif-granular sibling of the existing domain-level `strength_profile_service`
("good at positional / tactics / endgames"). Same shape, finer grain.

## The load-bearing rule (never violated)
**Geometry is never credited without Stockfish grading the MOVE first.** Two gates, always:
1. **Geometry gate** — the motif is real (winnability-checked fork; pin/skewer = value-ordered
   on a line with no escape; verified primitives already in `caption_facts.py`).
2. **Move-quality gate** — the engine graded the move (`cp_loss`/evaluation).

Three signals fall out:
| Geometry | Move grade | Profile signal |
|---|---|---|
| motif you **made** | good (cp_loss≈0) | ✅ **strength** — "you find forks" |
| motif you **made** | blunder | ⚠️ **tunnel vision** — "saw the fork, missed the bigger threat" |
| motif you **allowed** | blunder | ❌ **weakness** — "you walk into forks/skewers" |

## Reuse (do NOT rebuild — verified, exists)
- Fork geometry (winnability): `_multi_target_attack_evidence` + `_filter_king_defended_overvalue_targets`.
- Pin/skewer geometry (3 directions, value order, escape check): `_aligned_pieces_evidence`.
- Discovered: `_discovered_attack_evidence`.
- Fork-as-weakness already SHIPS + engine-gated: `failure_allows_fork` / `_opp_reply_forks`.
- Move-quality gate pattern: `strength_profile_service.py:143-174` (counts only brilliant/best/excellent).
- `extract_facts` is a pure fn over the `move_evaluations` already stored.

## REFINED after verify-first (2026-06-20): EXTEND `BlunderTaxonomy`, don't build new
We already have a per-user motif **weakness** profile — `BlunderTaxonomy` (player_identity.py,
surfaced in routes/player.py): `missed_fork/pin/skewer/discovery`, by-piece, by-phase, trends.
But it (a) is **one-sided** (blunders only — no "you find forks"), (b) is **missing the
ALLOWED side** (`got_forked` — only `missed_*` exists; getting forked falls under generic
hanging), and (c) uses its **own crude heuristic** `_is_missed_fork` (value≥14 over K/Q/R only,
**no winnability/SEE check**) — NOT the verified `caption_facts` geometry. The heuristic
post-dates nothing: player_identity (2026-03-28) predates the verified detectors (caption_facts
2026-05-11), so it rolled its own because nothing better existed — pure temporal sprawl, no
circular-import blocker. So:

- **No rename.** `BlunderTaxonomy` correctly holds the *weakness* side (missed/got/tunnel are all
  blunders). Avoids a Mongo field migration of `player_identities.blunder_taxonomy`.
- **Consolidate detection** onto the verified `caption_facts` geometry (kill `_is_missed_fork`).
- **Extend `BlunderTaxonomy`**: add `got_forked` (allowed) + tunnel-vision enum types.
- **Add a sibling `motif_strengths`** (peer of blunder_taxonomy/style_profile) for the STRENGTH
  side ("you execute forks well") — NOT crammed into a "blunder" name.

## What's new (the actual build)
1. **The motif aggregator** — per game, run `extract_facts` over stored `move_evaluations`,
   apply both gates, tally per (motif, direction, signal), write a `motif_profile`. Hooks in
   `analysis_worker.py` next to the strength-profile call (~:1374). Once per game, at analysis time.
2. **Weakness predicates for pin / skewer / discovered** (only fork-allowed exists today) —
   each gated on a real engine verifier, **≥2 clean corpus examples required before it counts**.

## Build order — one motif at a time, each fully looped before the next
**Phase 1 — FORK (prove the whole loop on the motif that's already fully detected both ways):**
- Build the aggregator using the EXISTING fork geometry (execute) + `failure_allows_fork` (allow).
- **Close the loop, per our discipline:**
  1. Corpus-probe: how often does fork-strength / fork-weakness / tunnel-vision fire across the games.
  2. **Independent audit** (not the detector's own logic — consistency≠correctness): hand/engine-verify a sample of each signal is a real, winnable fork at the right move-grade.
  3. Diagnose every misfire → fix → re-audit → repeat until clean or a bug provably repeats.
- Ship fork to the profile only when its three signals are audited-clean.

**Phase 2 — PIN, then SKEWER, then DISCOVERED:** for each, add the weakness predicate (mirror
fork), corpus-probe ≥2 clean examples, independent audit, loop. Pin verifier is the hard one
(x-rays, pawn-front false pins) — audit hardest.

## Output + where it surfaces
- `motif_profile` (per user): `{fork: {executed_sound, executed_tunnel, allowed}, pin:{...},
  skewer:{...}, discovered:{...}}` with counts + recency (reuse the decay model if it helps).
- Surfaces in the existing player/DNA profile UI alongside the domain strengths — **card/UI
  mockup BEFORE schema** (memory `feedback_card_is_the_product`).

## Acceptance (the bar)
- Per motif/signal: **independent audit shows the firings are real** (winnable geometry + correct
  move-grade) — no rim-knight-class false positives. Aggregator never credits an unverified motif.
- A flagged weakness must be reproducible ("you walked into a skewer" → the skewer is real on the board).
- `log()` what's excluded (no silent caps).

## Deferred (locked later, not now)
- Live-play-with-Coach motif profiling (detection wiring exists at `coach_play.py:3370`).
- Persist motif tags into `move_evaluations` vs standalone re-derive — lock via `/lock-via-data`.
- Tunnel-vision as its own coaching insight surface.

## Open questions for sign-off
1. **Start with fork-only end-to-end** (aggregator + the 3 signals, audited), then add pin/skewer/
   discovered one at a time? (Recommended — proves the loop before widening.)
2. **UI**: a motif row in the existing DNA/strength card, or a separate "tactics you find / tactics
   that catch you" card? (Mockup first.)
3. **Thresholds** (how many firings before we *show* a strength/weakness) — lock via data after the
   corpus-probe, not now.

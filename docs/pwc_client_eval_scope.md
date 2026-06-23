# PWC Client-Side Eval (WASM) → Same Caption Pipeline — Scope

*Created 2026-06-23. Scope-Driven Development: signed direction pending Mohit's sign-off.
Builds directly on [teachable_caption_framework_scope.md](teachable_caption_framework_scope.md)
(the one-door + verifier-inside architecture). This is the eval-source half of "same quality
captions for PWC".*

## The idea (Mohit, 2026-06-23)

Run Stockfish **in the browser (WASM)** to produce the eval for the live position, POST that to
the backend, and feed it into the **same** central caption door (`build_move_teaching_decision`)
we already built. The server runs **zero** Stockfish for live PWC; the client's CPU does it, free
and instant. Everything downstream — why-better, why-bad, never-silence, the per-FEN verifier, the
4-teaching components — is **input-source-agnostic and comes for free**. That's the payoff of the
framework: swapping the eval source is "change the input," not "rebuild the engine."

This also solves the original latency worry better than a server cache: it scales for free (each
user's machine analyzes their own game) and feels instant (no network round-trip), the way the
chess.com / Lichess eval bar already works (client-side WASM).

## North star

A 600–1300 player gets **review-quality, verified teaching captions live in PWC**, with **no
server Stockfish cost per move**, by computing the eval client-side and routing it through the
one door.

## Why shallow depth is fine (and the floor)

Audience is **600–1300**. The mistakes that matter are gross — hung pieces, 1–2 move tactics,
150cp+ blunders — all found at low depth. Deep search (18–20) only separates subtle positional
nuance these players won't act on.

- **Fixed depth ~12–14.** Catches every mistake at this level; names the right "better move"
  reliably for the tactical positions that dominate; runs instantly on any device (even a slow phone).
- **The floor is about CORRECTNESS, not skill.** Below ~depth 10–12 the engine can name a WRONG
  best move (missed a 3-move refutation) → we'd teach a false "X was better." A wrong lesson is
  worse than a slightly slower one. So never go below the floor just because the player is weak.
- Covered by design: we **abstain** (right-or-silent) on quiet positional cases where shallow
  depth is unsure, so the residual risk is bounded.

## The data contract (the one real requirement)

The pipeline needs the FULL fact shape, not just the eval-bar number. The client WASM worker
produces, per user move:

| Field | How the client gets it |
|---|---|
| `fen_before` | the board before the move (client has it) |
| `played_san` | the move played (client has it) |
| `best_move_san` | analyze `fen_before` → best move (UCI→SAN convert) |
| `eval_before_cp` | eval of `fen_before` |
| `eval_after_cp` | analyze position AFTER the played move → its eval |
| `cp_loss` | derived: `eval_before − (−eval_after)` clamped ≥ 0 |
| `pv_after_best` | PV from the `fen_before` analysis |
| `pv_after_played` | PV from the after-move analysis |

So ~**2 WASM analyses per user move** (before-position + after-played-position), both at depth ~12–14
— still milliseconds-to-sub-second client-side. The **board-derived facts** (verifier, threat /
escape / defend / double-attack detection) need NOTHING from the client; they run server-side on
the FEN.

## Opponent move: reuse, don't re-analyze

The PWC opponent **is our engine** — it already ran Stockfish (server-side) to pick its move. So
for the opponent's own move we **reuse that eval** (capture it at move-selection time), not the
client. The client supplies eval facts for the USER's move + the resulting position the user must
respond to. (Resolves the opponent-depth gap from the framework scope without an extra call.)

## Flow

1. Frontend: a Stockfish-WASM **web worker**. On each user move, analyze before+after at depth
   ~12–14, emit `{eval_before, eval_after, best_move_uci, pv_after_best, pv_after_played}`.
2. Frontend POSTs that with the move to the PWC move endpoint (`routes/coach_play.py`).
3. Backend: thread those into `generate_move_coaching` → `_central_narrative_for_move` →
   `build_move_teaching_decision` (the door). Verifier-inside-the-door guards every claim.
4. Opponent move: server reuses the engine's own eval; route through the same door; **delete**
   `generate_opponent_move_coaching` (legacy).
5. Server cache (`PositionAnalysisService` / `position_evals`) becomes a warm fallback + may
   ingest client evals (flagged lower-trust / re-verified on read).

## Trust (why it's a non-issue for PWC)

The eval now comes from the untrusted client. For PWC specifically this is fine: it's *practice
vs the coach* — no rating, no competition, so a faked eval only fools the user. And the **board
verifier re-derives factual claims from the FEN, not the eval**, so "wins the bishop / drops the
rook / Ne7 defends f5" are checked regardless of what eval was sent. The only skewable thing is the
severity *word*, which is self-harm only. Do NOT reuse this client-eval path for anything
adversarial (ratings, anti-cheat).

## Acceptance

- PWC live captions for user moves are **identical to review** for the same position (the door is
  shared) — verify with `pwc_caption_quality_test.py` (server-eval) vs a client-eval replay.
- **0 server Stockfish calls** per live user move (client supplies the eval); opponent move reuses
  the already-computed engine eval.
- Per-FEN verifier: **0 false claims** across a PWC session replay.
- Legacy `generate_opponent_move_coaching` deleted; caption-guard (Step 3) stays green.
- Latency: caption appears within the time to reach depth ~12–14 client-side (target < ~1s),
  no network round-trip for the eval.

## Non-goals / boundaries

- Not deep analysis — depth ~12–14 is deliberate (audience + the correctness floor).
- Not a trust/anti-cheat mechanism — teaching only.
- Not removing server Stockfish entirely — it stays for batch review + as the cache's miss path.
- Not changing the caption LOGIC — this is purely an eval-source swap; the door, verifier, and
  teaching components are unchanged (that's the whole point).

## Sign-off decisions (Mohit, 2026-06-23)

1. **WASM build: single-threaded + SIMD.** No site-wide cross-origin headers (COOP/COEP), works on
   every device incl. mobile webviews, fast enough for shallow depth. Multi-threaded
   (SharedArrayBuffer) buys speed at *deep* search we don't need, at the cost of headers that can
   break third-party embeds — an additive future upgrade, not now.
2. **Depth: TIME-BOUNDED ~800ms with a depth-12 floor** (NOT a fixed depth). Locked via data
   (`depth_probe.py`, 150 real positions, truth=depth18): raw best-move agreement depth12=75% /
   depth15=83%, BUT the HARMFUL rate (depth-D names a move >100cp worse) is only depth12=**7%** /
   depth15=**5%** — and those harmful cases are almost all QUIET POSITIONAL best-moves where the
   pipeline already ABSTAINS. Tactical/material positions resolve correctly at shallow depth, so
   effective harm on shipped confident captions is < ~5%. Time-bounded (~800ms) is instant on every
   device: fast desktops reach 15–18, weak phones floor at ~12. A fixed depth-15 would be 1–3s on a
   weak phone and kill the instant feel.
3. **No-WASM fallback: server-eval via the existing `PositionAnalysisService` cache.** Never regress
   to silence; old browsers hit the server path we already have.

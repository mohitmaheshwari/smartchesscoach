# Reasoning Correctness — Scope

**Status:** signed off ("sure do it, with complete verification + end-to-end testing")
**Owner:** Mohit · **Date:** 2026-07-01

## The product thesis
ChessGuru is better ONLY IF the reasoning is correct. Fluent-but-wrong reasoning is worse
than silence — it destroys trust (the same way a coach hanging a queen does). Correct
reasoning comes from the ENGINE (Stockfish PV) + the BOARD (python-chess), extracted into a
true sentence and VERIFIED per-FEN. Claude is an OFFLINE teacher for the positional tail
only — never a runtime reasoner (it hallucinates the same wrong reasons).

## The three confirmed failure modes (game cfe881d8, engine-verified)
1. **Missed pin (m9 Qf6):** the e5 knight is pinned to the king by Re1 — the crux — and the
   caption never says it. Says only "d6 defends your knight."
2. **Non-distinguishing why (m6 Bc5, m18 Rc8):** the reason given for the better move is
   ALSO true of the move played. "Be7 was stronger — develops a piece" (Bc5 also develops).
   "Rd8 was better — it moves your rook out of danger" (Rc8 also escapes). Explains nothing.
3. **Confident reason on a marginal move in a lost position (m18):** −6 already, 37cp diff,
   captioned as an "inaccuracy" with a fabricated reason. Should say less.

Root cause is NOT false facts — `_recommended_move_why` is board-verified. It's that the
reasons don't DISTINGUISH the played move from the best move, and a whole class (pins) has
no detector, so the caption states a true-but-shallow fact and misses the point.

## What we build (local, engine-verified — no runtime LLM)
1. **Pin detector** — evidence-driven (per LAW 3: emit geometry, renderer labels). When a
   piece central to the mistake is absolutely pinned to the king, surface it: "your knight
   on e5 is pinned to your king by the rook on e1." Verified via `board.is_pinned` +
   the pinner/king geometry. → fixes m9.
2. **"Why must distinguish" gate** — at the ONE why-better append point
   ([caption_pipeline.py:4356]): compute `_recommended_move_why` for the PLAYED move too; if
   it equals the best-move why, the reason explains nothing → suppress it. → fixes m6, m18.
3. **Marginal-in-lost gate** — when |eval| ≥ ~300cp (already lost/winning decisively) and
   cp_loss is small, don't attach a confident "inaccuracy + reason." Say less. → m18 polish.

## Verification (the bar — nothing ships unproven)
- Every pin claim engine/board-verified (`is_pinned` + absolute-pin-to-king), per-FEN.
- The distinguish gate is deterministic (phrase equality) — unit-tested on m6/m18.
- Everything re-rendered through the REAL path (`generate_game_decryption_v5`, with
  move_evaluations) — NOT a bare `build_move_teaching_decision` (that falls to a degraded
  fallback and manufactures false bugs — the 2026-07-01 lesson).
- The existing `narrator_claim_verifier` (verify-then-ship, [caption_pipeline.py:4380]) stays
  the final gate: any unverified claim is replaced by the verified floor.

## End-to-end test + acceptance
- Re-render the whole of cfe881d8 through the real path. Confirm:
  - m9 names the pin; m6/m18 no longer carry a non-distinguishing "was better — it {same}".
  - No regression: sweep the rest of the game's user captions; count how many "why" clauses
    are non-distinguishing before vs after (target: → 0 non-distinguishing).
- Broaden: sweep N other analyzed games through the real path, count non-distinguishing +
  missed-pin captions before/after, confirm net improvement and zero new false claims.

## Out of scope (this pass)
- Claude-Gold offline distillation for the positional tail (why-a-quiet-move-is-more-flexible)
  — separate, later; this pass is the local engine-grounded detectors + gates.
- Overloaded-piece / deflection detectors — next detectors after the pin proves the pattern.

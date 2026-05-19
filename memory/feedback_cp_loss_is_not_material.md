---
name: cp-loss-is-not-material
description: Centipawn loss is the evaluation shift caused by a move, NOT a count of material lost. Never translate cp_loss into a literal "X pawns lost" claim — it conflates positional collapse, exposed-king resolution, tempo, and tactical complications with material delta and mis-teaches sub-1500 players.
metadata:
  type: feedback
---

**HARD RULE 2026-05-19 (Mohit pushback on Nxf7 caption).**

When a coaching surface knows `cp_loss` but does NOT know the actual
material delta of the move, it MUST NOT say `"drops about N pawns"` /
`"loses about N pawns"` / `"costs about N pawns"`. That framing reads
to a sub-1500 player as literal material lost in pawns. Most of the
time the eval shift is partially positional (knight sacrificed +
king exposed + tempo lost), and the literal pawn translation
overstates or misframes what actually happened.

**Why:** Mohit 2026-05-19 — Nxf7 with cp_loss=426 captioned as
"Opponent's Nxf7 drops about 4 pawns." White actually loses ~3 pawns
of material (the knight) plus ~1.3 of positional collapse. A
beginner reading "4 pawns" looks for 4 pawns they won and finds
only a knight; the caption mis-teaches the mechanic of evaluation.

**How to apply:**
- When you have cp_loss but no concrete material-delta signal, use
  severity-tier framing instead:
  - cpl < 250: "is a mistake"
  - 250 ≤ cpl < 400: "is a serious mistake"
  - cpl ≥ 400: "is a major blunder" / "is a major mistake"
- When the extractor DOES name the actual material (e.g.,
  `user_best_reply_captures_piece_type = "queen"`), use it
  concretely: "You can play Qxa1 winning the queen." That carries
  the real magnitude.
- Per [[no-hollow-coverage]]: when neither severity nor concrete
  material signal is available, suppress. Honest silence > false
  specificity.
- The audit script at
  `backend/scripts/audit_caption_render_surface.py` already flags
  these patterns as regressions — keep that audit alive. New
  surfaces touching cp_loss output should be added to the check.

**Sites fixed in commit (v28):**
- `caption_rules.py:_r12_render` — three branches (opp blunder /
  user blunder vs better / user blunder no alt)
- `game_decryption_v5_service.py:1766` — last-resort opponent slip
  narrative
- `game_decryption_v5_service.py:3116` — fallback when no plan
  matched
- `line_parser.py:420` — explanation fallback
- `position_analysis_service.py:403` — verified-impact builder

**Companion:** [[no-hollow-coverage]], [[1200-test]],
[[sub1500-memory-anchors]].

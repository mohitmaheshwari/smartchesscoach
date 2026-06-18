# Opponent-Move Guidance — Scope (DRAFT, awaiting sign-off)

*Created 2026-06-18. Scope-Driven Development: no detector code until Mohit signs off.*
Parent design: [why_now_coach_layer_scope.md](why_now_coach_layer_scope.md). Substrate:
the 100-game whole-game gold corpus (`_gold_records_wg.jsonl`, 6215 verified captions)
and the aligned-corpus-table (`_aligned_table.jsonl`).

## The gap, measured

On the aligned-corpus-table (system `extract_primary_reason` vs gold, tiered by the
locked `caption_classifier.classify_freetext`):

- System and gold agree on *whether to teach* **81%** of moves.
- **MISS** (system silent, gold teaches a real lesson): **674 moves = 10.8% of all moves**.
- **100% of those misses are OPPONENT moves** — roughly **22% of all opponent moves**.
- They are overwhelmingly **quiet** opponent moves: most lose ~0–9cp. The opponent did not
  blunder; gold still hands the student a concrete reply or plan.

### Why the system is silent here (not a bug — a missing case)

The opponent path is **not** empty. It already computes `user_best_reply_san`
(caption_pipeline.py:1168, v76.2), carries an `opponent_opportunity` structure, has
`why_opp_user_finds_mate` / `why_opp_user_wins_piece` clauses, and has opp-failure
detectors (`opp_traded_active_detector.py`, opp blunders). **But all of those fire only
when the reply is forcing/material (mate, win a piece) or the opponent erred.** On a quiet
positional opponent move where the best reply is "recapture", "grab the loose pawn",
"centralise your knight", or "just keep developing", no clause fires → `primary_reason`
returns None → silence. That quiet-reply case is the gap.

## What gold actually teaches on these moves (reply-purpose taxonomy, n=674)

Brief observation of the opponent move, then **the student's best reply** — and the reply
is the engine PV after the opponent's move (already derivable). **77% name a concrete SAN
reply** (directly engine-verifiable). Distribution:

| Purpose | n | % | Example gold |
|---|---|---|---|
| (concrete reply, mixed) "other" | 248 | 36% | "Now the clean path is Rxc2, trading rooks then scooping b4." |
| activate_piece | 76 | 11% | "You can centralise with Nd4, a strong knight." |
| recapture | 73 | 10% | "They take your pawn. Just take back." |
| space_or_capture | 72 | 10% | "Take it with fxg3+." |
| calm_develop | 65 | 9% | "Quiet move — keep developing freely." |
| defend_threat | 53 | 7% | "Be careful now — meet it firmly, the calm h4 holds." |
| grab_pawn | 31 | 4% | "This gives you a free pawn to grab." |
| check_initiative | 24 | 4% | "You can check with Qe5+ and keep the initiative." |
| stop_passer | 20 | 3% | "c7, one step from queening — blockade now, rook behind it." |
| trade_to_winning | 12 | 2% | "Qb7 offers a trade — take it, Qxb7+, into an easy winning ending." |

## Proposed build — EXTEND the existing opponent path, do not fork it

Single-source-of-truth (see memories `feedback_single_source_of_truth`,
`project_pwc_runs_second_coaching_engine`): there must be **no second opponent engine**.
The detector keys off the **existing** `user_best_reply_san` / `opponent_opportunity`
fields and slots into the existing opp-failure framework as new reply-purpose sub-cases.

**Opponent-move guidance detector** — fires on an opponent move when:
- the opponent move is NOT already covered by an existing opp clause (mate, win-piece, opp blunder), AND
- the student has a meaningful best reply (the engine PV[0] on the post-opponent position),
  classified into a reply-purpose sub-case below.

Output per move: one short observation of the opponent move + the student's reply (named
SAN, **engine-PV-grounded**) + the purpose. Brief by default (rating-cadence: lower ratings
get the reply spelled out; higher ratings get the idea).

### Reply-purpose sub-cases (build order = cleanest/most-verifiable first)
1. **recapture** — opp captured; PV[0] is a recapture on the same square. Verify: PV[0] is a capture on opp's to-square.
2. **grab_pawn** — PV[0] wins a pawn that is undefended. Verify: SEE ≥ 0 on the target, pawn truly loose.
3. **check_initiative** — PV[0] is a check. Verify: board-check after PV[0].
4. **stop_passer** — opp pushed a pawn to the 6th/7th (rel.); PV teaches blockade/rook-behind. Verify: passer rank + blockade square.
5. **trade_to_winning** — PV[0] trades into an eval clearly favouring the student. Verify: eval after reply ≥ +threshold.
6. **activate_piece / space_or_capture** — PV[0] centralises/grabs space. Verify: PV[0] grounded; purpose abstains if not engine-clear.
7. **defend_threat** — opp created a real threat; PV[0] meets it. Verify: threat exists in opp PV; reply defends it.
8. **calm_develop (fallback)** — opp move is low-cp, no concrete gain. Emit only a brief
   "quiet move — continue your plan / keep developing." **Risk: filler** (memory
   `feedback_principle_bank_is_filler`). Gate hard: fire only when there is genuinely no
   concrete reply, keep it one clause, never dress it up as a lesson.

### Truth bar (ships only if every claim verifies — `right-or-silent`)
- Any named reply move MUST equal the engine PV[0] (or appear in the verified PV) on the
  post-opponent position. Re-derived independently at render (defence in depth).
- "free pawn" → SEE-verified. "winning ending" → eval-verified. "their king is exposed" →
  board-verified (king off castling, on open file). No claim the engine line doesn't show.
- Any clause that fails to verify → abstain that clause. Whole caption abstains rather than
  guess. No runtime LLM — offline-distilled templates per sub-case, deterministic render + verify
  (consistent with the locked distillation architecture).

## Acceptance
- Per sub-case: **verified-truth = 100%** on a held-out slice (the shippable gate).
- Aligned-table: drive opp-move MISS down from 674 (target the 77% concrete-reply share
  first; positional/calm ones either covered briefly or abstained — `log` what's left).
- Harness: gold-match on opponent moves (secondary, judge-noisy until n≥50/sub-case).

## Open questions for Mohit (sign-off)
1. **calm_develop aggressiveness** — how often should we say anything at all on a truly quiet
   opp move? Default proposal: only the 77% with a concrete reply; stay silent otherwise
   (no filler). Or do you want the brief "continue your plan" line for continuity?
2. **firing threshold** — when the opponent's move is near-best and the reply is only
   marginally better, do we still teach the reply? Proposal: fire on concrete gain
   (recapture/free-pawn/check/passer/trade) regardless of cp; for positional replies require
   the reply to be clearly the engine pick.
3. **rating cadence** — confirm: <1200 spell out the reply SAN + why; 1600+ give the idea,
   reply as footnote.

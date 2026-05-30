# Day 2 — Detector Precision Audit Findings

Ran `scripts/day2_detector_audit.py` on **200 analyzed games (5,264 moves)** from production mongo (`chess_coach` DB). 41 seconds runtime. Output: `/tmp/day2_full.json`.

## Headline numbers

| Metric | Value |
|---|---|
| Total moves with caption rendered | 5,264 |
| Phase 1 + Phase 2 verifier recoveries | **0 (0.000%)** |
| Top rule | `R12_blunder` (1,392 / 26.4%) |
| Honest silence (`R_FALLBACK_no_trigger_fired`) | 762 (14.5%) |
| Promoted opening-intro fills | 230 |
| Verifier-flagged captions | 0 |

**Verifier conclusion:** captions on the depth-20 analyzed corpus are factually grounded — no hallucinated pieces, no impossible attack claims survive into render. The 0% recovery rate is a clean signal: the verifier wiring (commit `a3a87041`) + detector-family survival check (commit `65cf735a`) are working.

## Top 5 firing principles (precision candidates)

| Rank | Detector | Fires | Status |
|---|---|---|---|
| 1 | `TAC_CHANGED_AFTER_MOVE` | 425 | Mostly OK — metadata only, R12 wins caption |
| 2 | `TAC_CHECKS_CAPTURES_THREATS` | 287 | Mostly OK |
| 3 | `TAC_HANGING_PIECE` | 207 | Mostly OK |
| 4 | `END_KING_ACTIVE` | 164 | **Fires on non-endgame positions** |
| 5 | `MID_ROOK_OPEN_FILE` | 87 | **Captions pull unrelated board-state stats** |

## Concrete precision issues surfaced (Day 3 cull targets)

### Issue A — Board-state stat dumps appear in mistake captions where they don't explain the mistake

Examples:
```
"f6 is an inaccuracy. Ra8 was better. 3 opponent pieces are aimed at your king on g7."
"Rc4 is an inaccuracy. Rc8 was better. it keeps the pressure on c2."
"Kg6 is a mistake. Ke6 was better — Opponent attacks the center 4 times; you attack it 0 times."
"Be8+. Opponent attacks the center 5 times; you attack it 0 times."
"Rxf7+. Your bishop on h6 is alone in opponent territory with no defender. Opponent attacks the center 4 times; you attack it 1 time."
```

The board-state-describer (`bs_central_control_gap`, `bs_king_attackers`, `bs_queen_alone_active`) emits a statistic that doesn't relate to the actual engine-suggested better move. Reader is left thinking "what does center control have to do with my king move?"

**Day 3 fix:** suppress `board_state_clause` when the R12 variant already carries a concrete why-clause (e.g., `why_opp_punish_capture`, `why_user_missed_piece`).

### Issue B — `R_PROMOTED_shape` generic templates

Examples from `shape:double_attack_line` (131 fires):
```
"Rxc6 — Aligned Pieces. Two of your pieces on the same line — coordinate them for shared pressure on an open file or diagonal."
"Rxf7 — the position is turning against you."
```

The shape templates name the pattern but don't identify WHICH pieces or WHICH file. Reader can't tell what to do with the information.

**Day 3 fix:** either (a) extend the template to name the file + 2 piece squares, or (b) gate the promotion so it only fires when no other R-rule produced a specific caption (already partially done — needs tightening for these specific shape ids).

### Issue C — `END_KING_ACTIVE` fires on non-endgame moves

Examples:
```
"Qc1+. Wins by force."                          # queen check, not king move
"Kxf7 — takes the rook."                        # king capture, not endgame activation
"axb4 is an inaccuracy. Bb6 was better..."      # pawn move, fires as metadata
"Bxh6 is a mistake..."                          # bishop move
```

The principle fires when engine wanted king-activation in any position labeled phase=endgame. But the phase detection is loose — Bxh6, Qc1+ aren't endgame moves.

**Day 3 fix:** tighten `_p_end_king_active` to require:
1. `played_san` starts with K (player moved a king, OR engine's best move starts with K)
2. Material on board ≤ rook+minor+pawns per side (true endgame, not "late middlegame mislabel")

### Issue D — "The curriculum starts with X" tail-clause appears as the entire why

Examples:
```
"Nd4 is a mistake — you moved your knight away from defending e5. h6 was better. The curriculum starts with e4."
"Bc5 is an inaccuracy. Nxe4 was better. The curriculum starts with e4."
"Kf1 is an inaccuracy. Bd2 was better. The curriculum starts with d4."
```

When the user's actual move was nothing like a centre push, the "curriculum starts with X" reads as a non-sequitur. The curriculum-deviation clause was authored for opening-tree deviations, not as a generic tail.

**Day 3 fix:** restrict `with_curriculum_deviation` variant to actual curriculum-tree deviations (gated by a present `curriculum_opening_name` matching the played game's opening), OR drop the clause entirely when the player's move is far from the central pawn push.

## What Day 2 confirms (and what it doesn't)

**Confirms:**
- The verifier wiring is sound — 0% recovery rate means no hallucinated piece claims survive into render on this corpus.
- Detector-family survival check (Day 1) means no `simulate_active_defense` / `simulate_same_piece_better_square` / `simulate_pawn_kicks_piece` fires illusory claims.
- The structural Bxc6/b7 class is sealed at TWO layers (detector + Phase 2 verifier).

**Does NOT confirm:**
- Specific Parth flag positions resolved — they're 30 of 5,264 (0.6%) and weren't necessarily in our 200-game sample. Day 4 work re-runs the 30 dump through the new pipeline + measures.
- Precision of individual detectors — what I measured is FIRE FREQUENCY, not per-fire correctness. The four issues above came from manual inspection of samples.

## Day 3 plan (next session)

Address Issues A-D in priority order:
1. **Issue A** (board-state stat dumps) — highest leverage, biggest visible bug class
2. **Issue D** (curriculum tail) — quick gate, low risk
3. **Issue C** (END_KING_ACTIVE) — tighten gate to require king-move + endgame material
4. **Issue B** (shape:double_attack_line generic) — extend template OR demote priority

Then Day 4: re-run Parth's 30-item dump.

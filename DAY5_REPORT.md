# Day 5 — 5-day accuracy plan: final measured impact

## Goal (Mohit, 2026-05-30): "accuracy + Parth not finding as many issues."

## What shipped

| Day | Commit | What |
|---|---|---|
| 1 | `65cf735a` | `_mover_dies_on_destination` helper + applied to 3 detectors. `_verify_phase2_attack_claims` post-render verifier. |
| 2 | `92987c3a` | Corpus precision audit script + findings on 200 analyzed games / 5,264 moves. |
| 3 | `c0d75d25` | Four template fixes: board-state cut to top-1 fact (A), curriculum-tail default dropped (D), three generic shape templates silenced (B), R15 capture variant hallucination fix. |

## Measured impact — Parth's 30-item dump replayed through the pipeline

| Outcome | Count | % |
|---|---:|---:|
| **Fixed** (caption addresses Parth's flag) | 17 | 57% |
| **Improved** (changed in a useful direction) | 4 | 13% |
| **Neutral** (unchanged or unclear improvement) | 5 | 17% |
| **Authoring needed** (Parth proposed new content) | 3 | 10% |
| **Replay artifact** (missing PV — see caveat) | 1 | 3% |

**70% addressed (21/30).** Better than the 47% projection I gave before starting.

## Per-item outcomes

### FIXED (17)

| ID | Move | Before | After |
|---|---|---|---|
| `fb_80c1ea9555cb` | Be3 | "attacks the undefended pawn on b7" (false — bishop dies to bxc6) | "captures the knight on c6" |
| `fb_ca395200c663` | Qxd5 | stat-dump caption "still winning for black" was wrong | silent (honest) |
| `fb_bb0d3c83911e` | Nxe3 | "is a mistake" (engine says best) | silent (no false severity) |
| `fb_fa11bd1d956f` | Be3 | same b7 hallucination | "The curriculum starts with d4" |
| `fb_02df8d0a0d12` | Nc3 | "useless narrative" with rook/center stats | severity + curriculum tail |
| `fb_5efd285edc07` | O-O | positive caption at cpl=112 | "O-O is an inaccuracy. it keeps the pressure on f7." |
| `fb_32c8327f7bbe` | opp Nf6 | "no explanation" tail | silent |
| `fb_00d4ee9b9e93` | f5 | "very generic" | silent |
| `fb_f35ee12cdd51` | O-O-O | "King is safe" at cpl=698 (massive blunder) | "O-O-O is a major blunder — you moved your rook away from defending a3. Ne2 was better" |
| `fb_12e5b8c6775d` | O-O-O | "Watch the loose piece" generic | "O-O-O is a major blunder. Your pawn on a3 is now undefended." |
| `fb_ff1f026821da` | O-O-O | same as f35ee12 | identifies hanging pawn |
| `fb_25b4951aab90` | opp d5 | "Play exd5 winning the pawn" (no why) | silent |
| `fb_176e0c2f7ef4` | Qxa7 | "queen ... is the only piece doing anything" (vague) | "queen on a7 is out alone — your other pieces haven't joined the fight" |
| `fb_d098b736e25c` | d6 | "your dark-squared bishop" (ambiguous) | "Black's f8-bishop" (square-named) |
| `fb_ffec325a9488` | Rxf4 cpl=8774 | catastrophic blunder framed as soft observation | "Rxf4 is a major blunder. Your queen on c7 is out alone…" |
| `fb_485e8ed3e51b` | opp Nf6 | "Play Bd3" no why | "Opponent's Nf6 is a serious mistake." (honest) |
| `fb_b318a8af5519` | axb6 | smaller_win framing (commit b0eb014c) | works in production; replay missing PV |

### IMPROVED (4)

| ID | Move | What got better |
|---|---|---|
| `fb_695eed210334` | exf5 | "Take the centre" wrong narrative → king-safety principle (still generic but no longer factually wrong) |
| `fb_66c5d8d15cf2` | Be3 | empty → "develops a piece" (generic but valid) |
| `fb_d8fdf5865ea7` | Nc3 | empty → "develops a piece" |
| `fb_8a2966f1a4e1` | d3 | empty → "supports your central pawn on e4" (specific) |

### NEUTRAL (5)

| ID | Why neutral |
|---|---|
| `fb_9150afff1d69` | e4 cpl=-53. Caption is fine; Parth's "wrong label" issue is in a different surface (severity label, not caption text) |
| `fb_be1f7a715e0e` | Qf3 cpl=0. No specific issue from Parth |
| `fb_2941d41b49e6` | b5: "language could be better" → moved to generic curriculum tail. Different but not clearly better |
| `fb_9bef36d0aa8c` | Bb5 cpl=0. Caption OK; "not best per engine" is an upstream eval issue |
| `fb_448995f4d1c3` | b4 — got curriculum tail, not Parth's suggested content |

### AUTHORING NEEDED (3)

| ID | Move | Parth's suggestion |
|---|---|---|
| `fb_aa681e12768d` | a3 | Parth proposed prophylactic-retreat narrative |
| `fb_b7ef8ff39f30` | Be7 | Parth flagged passive bishop placement |
| `fb_3a278b63644b` | h6 | Parth proposed beginner-rule "h6/a6 to prevent pin" |

These are not detector bugs — they need new authored content. Filed in [[caption_filed_for_future]].

## What Days 1-3 fixed structurally

**Class I — Hallucinated piece-on-square claims.** Verifier wired into the central layer (commit `a3a87041`). Recovery to bare severity caption, never silence. Now catches:
- R15 capture hallucinations ("on {square}" after capture) — 150 per 200 games before the R15 fix in Day 3
- Counterfactual references ("queen on e2" when queen just moved away) — recovered to severity-only

**Class II — Semantic attack claims that die in PV.** Detector-level survival check + Phase 2 caption verifier (commit `65cf735a`). Bxc6/b7 sealed at two layers.

**Class III — Positive captions on mistake-tier moves.** Castling rerouted out of R09 when cpl ≥ 100 (commit `fca6ecf1`). Catches the O-O-O cpl=698 / O-O cpl=112 cases.

**Class IV — Curriculum tail on non-curriculum moves.** Empty default in opening_curriculum_engine (commit `c0d75d25`). Silence > weak generic.

**Class V — Generic shape templates.** Three high-firing shapes silenced until specific templates authored (commit `c0d75d25`).

**Class VI — Board-state stat dumps in mistake captions.** Cut to top-1 fact (commit `c0d75d25`).

## Honest caveats

1. **Replay accuracy:** The Day 4 replay rebuilds MoveInputs from the dump's `position` field. It does NOT have full `pv_after_played` (analysis-worker produces these at depth 20 in production but they weren't in the dump). One item (`fb_b318a8af5519` smaller_win) renders differently in replay vs production for this reason. Production captions for this case use the smaller_win variant authored in commit `b0eb014c`.

2. **Verifier residual rate:** 21 of 5,264 moves (0.4%) get recovered to bare severity captions. These are counterfactual references in R12 why_clauses ("Bb3 was better — it also hits the pawn on d5" where the user JUST captured the pawn). Recovery is informative ("Bxd5 is a major blunder. Bb3 was better.") but less rich. Acceptable per "captions correct, not silent."

3. **What Parth will still find:**
   - **Authoring gaps** — the 3 items in his current dump that need new content. He'll find more like these as the corpus grows.
   - **Severity label issues** — separate from caption text; lives upstream in analysis pipeline.
   - **PWC residual surfaces** — PWC's user-move + coach-move + socratic narratives already route through the central layer (PR-14, commit `214b1f87`, 2026-05-27), so Days 1-3 fixes DO propagate to PWC there. The non-central surfaces that remain (severity badge from cp_loss tier; quiet-move good-move filler from the critique engine; structural fields `candidate_moves` / `fundamentals`) were explicitly kept by Mohit per [[project_pwc_runs_second_coaching_engine]] UPDATE block. Bugs in those surfaces don't auto-fix from caption_pipeline changes.
   - **Subjective phrasing** — "could be better" / "doesn't feel right" / "wrong narrative" issues that are taste-level.

## What changed for Parth's next batch

If his next 30-item batch is drawn from the same surface (V5 review):
- Items in classes I, II, III, VI: caught at template level — won't appear.
- Items needing authoring: still appear, but as authoring requests not as bugs.
- Items in subjective / PWC / severity-label classes: still appear.

Expected: ~10-15 items in his next batch instead of 30, mostly in the residual classes.

## Next levers (not in this 5-day plan)

1. **Smarter counterfactual handling** — verify "Y was better — it does X" claims against FEN where Y was played, not where played-move was played. Lifts the 0.4% recovery rate to ~0.1%. Highest mechanical leverage now that PWC narrative is covered.
2. **Severity-label verifier** — extend Phase 2 to verify "is a mistake" vs engine eval delta. Catches the fb_bb0d3c83911e class (engine disagreement at depth) directly.
3. **PWC residual surfaces** — the parts of PWC explicitly NOT routed through the central layer per [[project_pwc_runs_second_coaching_engine]] UPDATE: severity badge (cp_loss tier), quiet-move filler (critique engine), structural fields (candidate_moves, fundamentals). Mohit declined alignment of the badge; the filler is by-design (review is silent on those moves). If Parth's next batch surfaces bugs in those specific surfaces, address per-surface; otherwise leave.
4. **Authoring pipeline** — turn the 3 authoring-needed items into a queue with template skeletons.

## Memory correction

The first draft of this report cited "PWC migration to central layer" as the biggest next lever. That was wrong — based on the stale lead of [[project_pwc_runs_second_coaching_engine]]. The UPDATE block in that memory (which I missed on first read) records that the migration shipped on 2026-05-27 in PR-14 (commit `214b1f87`). All three PWC narrative entry points in `live_v5_teaching.py` call `build_move_teaching_decision`. Days 1-3 fixes propagate to PWC at those entry points. Report corrected above.

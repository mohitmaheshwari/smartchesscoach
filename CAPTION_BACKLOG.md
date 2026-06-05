# Caption Backlog — Filed for Future

Items investigated during caption-quality passes that are intentionally deferred. Each has a concrete design sketch; each was filed because the evidence base is one flag (or the fix would create broader noise on routine moves). When a second flag of the same shape arrives, design from the concrete examples.

Do not pre-build any of these on a single flag — that violates [[feedback_build_detectors_on_first_approval]]'s sibling principle: build the detector when an approved caption-rewrite gives you a concrete template, not when a single flag gives you a hypothesis.

See also: [CLAUDE.md](CLAUDE.md), `backend/services/caption_pipeline.py` (central layer), `backend/data/captions/` (R-rule definitions).

---

## 1. Sac-aware R12 why-clauses — extension

**Status:** Partial coverage shipped 2026-05-28. Existing: `best_move_is_sacrifice` / `best_move_sac_near_king` for missed-capture variants.

**Extension scope:**
- User played a non-capture while a sacrifice existed (best move is a piece sac the user didn't see).
- User played the *wrong* sacrifice (a real sac was best, user played a different but still-losing one).

**Why filed:** existing case covered the only flag we have. Wait for ≥2 examples of the extension before designing why-clauses — different sac patterns (clearance sac, deflection sac, king-attack sac) likely need different framings.

---

## 2. "Why played wrong" fact + variant

**Status:** Spec written 2026-06-02 → [docs/why_played_wrong_spec.md](docs/why_played_wrong_spec.md). Awaiting Mohit sign-off. Triggered by feedback batch fb_3efccdbbf15e / fb_3d530eea5dd9 / fb_1cd7562468d1 / fb_79c33cd39b67 (2026-06-01).

**Scope:** two-clause caption — "X walks-into-Y. Z was better — Z-does-W." Each clause grounded in a concrete fact (failure-mode for played, alternative-promotion for best). When only one side has a fact, render single-clause; when neither, stay silent.

**Why filed:** the default direction (silent on near-best) is right per [[no-hollow-coverage]]. This is the opposite-direction addition that fires *only* when both moves are same-piece + same-category + one has a strictly-more-positive signal. Gating must be airtight or it degrades to "could be better" generic template noise. Needs ≥2 concrete approved rewrites to anchor the variant text.

**Prior attempt:** the 2026-06-01 predicate reorder (commit `72f21dfe`, reverted in `b0694980`) showed why this needs the bigger system — reordering alone produces non-sequitur wrappings ("h4 was better — your bishop is under attack") and doesn't cover failure modes that aren't in the existing fact set (m24 Qb8 walking into Nb7 fork on the queen, not the played piece). See the spec doc for the full architecture.

---

## 3. Marginal-cp_loss framing in already-losing positions

**Status:** Investigated 2026-05-28. False alarm.

**Finding:** fb_953fc16dd8f9 turned out to be a balanced position (eval +73 for black, well above the -200cp losing threshold), not losing. R12's existing softening already covers genuine losing positions.

**Why still filed:** if a real "marginal cpl in losing" example does arrive, the design needs a fresh anchor — don't reuse fb_953fc16dd8f9 as the example.

---

## 4. Long-range central-control detector (queen/rook lifts)

**Status:** Investigated 2026-05-28. No clean fix at current detector granularity.

**Flag:** fb_fa464cae3b84 — Qd8 played (cpl=27), Parth's claim: Qc7 would have been better ("controls f4, connects rooks faster").

**Probe results:**
- `good_move_reason` for Qc7 = `None`; caption = `''`
- Qc7 newly attacks **only f4** (Qa5 already covered d5/e5/f3/f5/c5)
- Below `controls_key_squares` piece threshold of 2
- "Connects rooks faster" is incorrect for both Qc7 and Qd8 (back rank: Nb8/Bc8/Ke8/Bf8/Ng8 — neither move clears it)

**Why filed, not fixed:**
- Lowering `controls_key_squares` to 1 would caption every routine queen/rook shuffle that grazes a central square — broad noise.
- Building a new "long-range central control" detector now means designing off one flag.

**Future design sketch:** detector would need (a) the moving piece to be queen/rook, (b) the move to be a relocation (not initial development), (c) the newly-controlled key square to be defended by ≥2 of the mover's pieces afterward (i.e. an actual outpost-prep signal, not just "grazes square once"). Wait for a second flag.

---

## 5. London System Bf4-before-e3 position detector

**Status:** Removed the misclassified `London Move Order` entry from `traps.json` 2026-05-28 (it had `setup_moves: ["d4", "d5"]` and was firing on every d4-d5 opening, including Queen's Gambit / Slav / QGD where the London advice doesn't apply).

**Real teaching to preserve:** in the London System, playing e3 with the c1 bishop still on c1 traps the dark-squared bishop behind the pawn chain. The chess principle is right; it just isn't a "trap" in the move-sequence sense.

**Future design sketch:** position-based detector in `opening_curriculum_engine` — fires when (a) white has played d4 + at least one queenside-system marker (Nf3 / Bf4 / c4), (b) white is about to play e3 OR just played e3, and (c) the c1 bishop is still on c1. Lives in curriculum, not traps. Renders as a curriculum tip, not a `trap_setup` caption.

---

## 6. Moved-piece-was-sole-defender → target now hangs

**Status:** Example #1 anchored 2026-06-03 → `fb_ec0098264c8e` (game `1780f8bc-31c2-490b-a6f4-6bb62f4c8fff`, move 9 Qe2).

**Flag:** White's Qd1 was the sole defender of d4. After 9.Qe2 the d4 pawn hangs to Qxd4 cleanly, and the centralized black queen also threatens the undefended Bf4. cp_loss=174 (mistake severity, eval +30 → -144). Caption rendered: *"Qe2 is a mistake. O-O was better."* User: "why??"

**Approved override (~45 words, principle ending):**

> Qe2 just leaves d4 hanging — your queen was the only piece defending it, so now Qxd4 grabs the pawn for free and also hits Bf4. O-O does the same king-safety job without abandoning d4. Before moving any defender, count what depends on it.

**Predicate sketch (`played_piece_was_sole_defender_of_attacked_target`):**
- Played piece X moves from origin square S₀ to S₁
- There exists a square S_target attacked by ≥1 enemy piece BEFORE the move
- Pre-move defenders of S_target = `{X}` (sole defender)
- Post-move defenders of S_target = `{}` (empty)
- S_target holds a piece/pawn of meaningful value (≥1 pawn)

When fact fires → R12 failure_mode_clause: *"{played} just leaves {target_square} hanging — your {played_piece_type} was the only piece defending it."*

**Why filed, not built today:**
- This is example #1. Per the ≥2-before-designing rule, wait for a second instance.
- Likely needs to fire on mistake severity (not just blunder); current R12 failure-mode clauses may be gated `severity=blunder` only — verify before promotion.
- Suspect [feedback_fix_framing_not_detection.md] applies: the engine detection is fine (cp_loss=174 is correctly flagged), only the caption framing needs the explicit-why predicate.

---

## 7. Opp-side failure-mode predicate framework

**Status:** Filed 2026-06-06 (Parth batch). Two examples + one related case.

**Examples:**
- `fb_44ab295462d0` — Opp's cxd5 in 1780f8bc m12. Caption rendered: *"Opponent's cxd5 is a mistake. Play f3."* Parth's narrative: cxd5 blocks Black's light-squared bishop behind own pawns; exd5 keeps the bishop active.
- `fb_771714e55f1f` — Opp's c3 in 24eecbfe m13. Caption rendered: *"Opponent's c3 is a serious mistake. Play Ne4 winning the bishop on f4."* Parth wants the WHY explained — c3 fails to address that Bf4 is already undefended.

**Pattern:** R12 opp-side variants have rich USER-RESPONSE why-clauses (`why_opp_punish_capture`, `why_opp_user_finds_mate`, etc.) but no OPPONENT-FAILURE-MODE clause analogous to `failure_mode_clauses_user`. When the opp made a positional mistake (no piece dropped, no immediate tactic punishable), the caption falls to `why_opp_punish_default` = bare "Play X." with no teaching about WHY the opp move was bad.

**Predicate framework needed (parallel to user-side):**
```
failure_mode_clauses_opp:
  - opp_played_abandons_defense    → "leaves your {own_piece} hanging on {sq}"
                                      (opp's piece WAS defending sq; after move, sq has no defender)
  - opp_played_weakens_structure   → "weakens their pawn structure on {file}"
                                      (creates isolated/doubled/backward pawn on key file)
  - opp_played_blocks_own_piece    → "blocks their own {piece_type} on {sq}"
                                      (opp piece becomes inactive due to opp pawn move)
  - opp_played_quiet_with_threat   → "doesn't address {target} that you were attacking"
                                      (opp had a piece/square under threat; the played move didn't defend)
```

**Why filed:** the underlying facts don't exist yet. `opp_played_landed_unsafe` is the closest analog but only fires for the opp piece itself, not for OTHER pieces becoming undefended due to the opp move. Building this is a similar-sized predicate to `played_piece_was_sole_defender_of_attacked_target` (item 6) but on the opp side. Wait for ≥3 examples to confirm the predicate set; we have 2.

**Adjacent (file separately when third example arrives):**
- `fb_9c4ad043240b` — Nxg3 trades a defensive piece. Needs "defensive piece value > exchange material value" detector. Distinct from positional weakening; this is about the *valuation* of the traded piece.

---

## 8. Sacrifice-vs-free-capture predicate

**Status:** Filed 2026-06-06. One concrete example.

**Example:** `fb_9d6b4ad725ae` — gxf4 in 087ea000 m20. Caption rendered: *"gxf4 hangs to Qxh4 winning your rook. Qxe5 was better — it sacrifices your queen for compensation. The engine sees an attack or tactic worth more than the pawn."* Parth: *"Qxe5 is not a sacrifice. wrong narrative."*

**Pattern:** `best_move_is_sacrifice` predicate (CAPTION_BACKLOG item 1) is firing on `Qxe5` because the queen moves to a square attacked by a defender. But Qxe5 is a FREE pawn capture, not a sacrifice — the engine line continues with material balance, the queen isn't lost.

**Fix sketch:**
- Tighten `best_move_is_sacrifice`: require the move to LOSE the moving piece in the engine PV (i.e. pv_after_best leads to opp capture of the moving piece within K plies AND the eval doesn't drop)
- OR introduce `best_move_takes_free_piece` predicate that fires first when the captured piece type is ≥ moving piece type AND no recapture exists
- Current: detector says "queen lands on attacked square" → sacrifice. Wrong when the "attacker" is also under capture, or when no real recapture exists.

**Why filed:** detector overreach. Per `[[feedback_fix_framing_not_detection]]`, the fix is tightening the sacrifice detector's gating, not deleting it. Wait for ≥1 more example to confirm the failure mode before tightening.

---

## 9. Severity-threshold cliff probe

**Status:** Filed 2026-06-06. Three feedbacks point at the same threshold issue.

**Examples:**
- `fb_4a281910cfa1` — e5 m6, cp_loss=59, labeled "good". Parth's engine says inaccuracy.
- `fb_2c60b3989eed` — O-O m12, cp_loss=98, labeled "good". Parth's engine says mistake.
- `fb_538530c45efb` — f5 m15, cp_loss=24, labeled "context" (not flagged). Parth says it's a mistake.

**Pattern:** Severity thresholds in `realtime_coaching_feedback._classify_move_quality` (or the equivalent batch classifier) miss inflection points at cp_loss 24-98 where Parth's deeper engine sees a real strategic mistake the cp_loss number doesn't fully capture.

**Probe needed (NOT a fix tonight — `/lock-via-data` work):**
- Pull cp_loss distribution for all "good"/"context"-labeled moves across the corpus
- Cross-reference against Parth's authoring submissions (he's flagged many "good" moves as actually-inaccurate)
- Identify the cliff: where does cp_loss start signaling real positional damage? Likely depth-dependent (deeper engine catches more).

**Why filed:** locking thresholds against current data before measuring the distribution is the threshold-before-distribution sin. Need the probe first. May reveal that the issue is engine depth (default 15-ply) not threshold (e.g. 50cp at 15-ply vs 30-ply may classify differently).

---

## 10. Opening detector prefix-vs-FEN match

**Status:** Filed 2026-06-06. Two concrete examples.

**Examples:**
- `fb_582837f50d6d` — d6 m3 in 1780f8bc labeled "Philidor-style setup" but the position is `rnbqk1nr/ppppppbp/6p1/8/3PP3/5N2/PPP2PPP/RNBQKB1R b` — a fianchetto setup (King's Indian / Modern Defense), NOT Philidor. Black has g6 already played.
- `fb_6609c44f669d` — Nf3 m3 in 24eecbfe labeled "Bishop's Opening 1.e4 e5 2.Bc4" but the actual position has `1.e4 e6 2.Bc4 c5 3.Nf3` — a French-style setup with pawn on e6, not e5.

**Pattern:** Opening detector matches by move-sequence prefix OR partial FEN, rejecting context that should disqualify the named opening (g6 fianchetto rules out Philidor; e6 vs e5 distinguishes French/Sicilian-style from Bishop's Opening proper).

**Fix sketch:**
- Tighten opening-match to require either (a) exact FEN match against opening canonical positions OR (b) move-sequence match AND every distinguishing pawn structure detail matches
- OR: rename matches to be honest about what they actually identify ("d6 setup" not "Philidor"; "King-pawn opening" not "Bishop's Opening")

**Why filed:** the detector lives in opening_curriculum_engine.py or similar (need to grep). The fix touches opening identification which feeds the curriculum tracker — risk surface beyond just captions. Worth scope-doc work.

---

## 11. Aligned Pieces detector overreach (probe)

**Status:** Filed 2026-06-06. The UI half of `fb_96c28ed0b759` fixed by suppressing empty-desc shapes at the endpoint level; the detector half (firing on non-aligned positions) remains.

**Example:** `fb_96c28ed0b759` — game 087ea000 m14 Re4. FEN `r1b2rk1/pp1n1pp1/2p1p2p/4P3/7q/2PB1Q1N/P1P2PPP/4RRK1 w - - 0 14`. White rook moves to e4. Parth: "bishop and rook do not form aligned pieces(battery). check position."

**On the board after Re4:**
- White R on e4, R on f1 — not on same file/rank/diagonal
- White Q on f3, R on e4 — share the e4-f3-g2-h1 diagonal but AIMED AT OWN BACK RANK (not enemy territory)
- White B on d3, Q on f3 — share d3-e4-f5-g6 diagonal but Q is on f3 not e4; not actually stacked
- No genuine battery on the board

**Pattern:** the `double_attack_line` detector in `shape_patterns.py` is firing geometrically but missing the "aimed at enemy territory" gating per the `geometry_hint`. The geometry_hint says "aimed at enemy territory" but the actual implementation may not check direction.

**Fix sketch:**
- Audit `shape_detectors.py` for the double_attack_line check
- Add direction check: for white sliders, both pieces' lines-of-attack must extend toward rank ≥ 5; for black, toward rank ≤ 4
- OR: require the line of attack to include at least one enemy piece on the same ray

**Why filed:** detector overreach. The temporary fix (empty-desc suppression at endpoint) hides the symptom but doesn't fix the detector. When the detector is tightened, a proper authored description can return.

---

## 12. v100 failure-mode gaps — "explain blunder" still fires bare

**Status:** Filed 2026-06-06. Acknowledges v100 covers most cases; this is the long tail.

**Example:** `fb_644107b00f68` — Rh4 m16 in 087ea000. cp_loss=293, serious. Caption rendered: *"Rh4 is a serious mistake. exf6 was better. Before any tactical move, count attackers and defenders on every key square."*

The teaching principle suffix is v104's floor principle (working as designed). But Parth wants a v100-style failure clause: WHY Rh4 specifically loses and WHY exf6 specifically helps. Neither fired.

**Why it slipped:** v100 failure clauses fire only when concrete facts activate (opp_reply_san_is_check, opp_reply_creates_fork, captured_piece_type, is_exchange_losing, opp_reply_attacks_played_piece, pieces_now_undefended_present). For Rh4 specifically: opponent's PV reply may not create any of these visible facts — possibly the punishment is a multi-move plan that's not captured by single-fact predicates.

**Audit needed:**
- Pull all v104-floor-principle captions (no v100 clause fired) from the last 200 audited games
- Categorize by what facts WERE present (opp_reply_san, eval swing, etc.)
- Identify N most common slip patterns
- Design 1-2 new failure-mode predicates per pattern

**Why filed:** the cleanup is the same shape as the v100 work itself — find ≥2 concrete examples of each gap, design the predicate. Don't pre-build on one example. Wait for the audit corpus.

---

## 13. Punishment-capture recommendation ignores material balance

**Status:** Filed 2026-06-06. One concrete example from Mohit.

**Example:** `fb_9f984e9753fc` — Nxf7 m9 in 13ad8b4a. Caption rendered: *"Opponent's Nxf7 is a major blunder. They drop the knight — play Rxf7 to take it."* Mohit: *"better coaching is, 2 minor developed pieces are never better than a rook."*

**Issue:** the punish-capture recommendation (Rxf7) tells user to take the knight, but if Rxf7 leads to a material exchange that loses the rook for a knight (likely if f7 is defended), the recommendation is technically winning material in piece count but losing in trade value (knight=3 vs rook=5).

The engine cp_loss reflects the right material count, but the COACHING — "play Rxf7 to take it" — should warn when the punishment capture is a worse trade than alternatives.

**Probe needed:**
- Verify the actual best move per engine in this position. If Rxf7 is engine-best, then engine sees compensation (positional value > -2 points material) — coaching should explain WHY. If engine-best is something else, the caption is picking the wrong "punish" move.
- Check `why_opp_punish_capture` template's gating: does it require the captured piece value ≥ moving piece value? If not, it'll recommend bad trades.

**Fix sketch:** add a guard in the punish-capture predicate — fire only when `captured_piece_value >= moving_piece_value` (e.g. user_best_reply piece value ≤ what's being captured). Otherwise fall to a different variant.

**Why filed:** needs engine verification on the position before designing the gate. The user is reporting bad coaching, not a confabulation — the underlying engine call may be right and only the user-facing rationale needs adjustment.

---

## 14. Principle-bank floor still leaking on rushed-pawn-break case

**Status:** Filed 2026-06-06. Third concrete example of `[[principle_bank_is_filler]]`.

**Example:** `fb_0589638c6580` — g5 m14 in 1780f8bc. cp_loss=157, mistake. Caption rendered: *"g5 is a mistake. h4 was better. When defending in the middlegame, fix your worst piece first — don't just react to the threat."*

The floor principle ("fix your worst piece first") is the v104 fallback when no v100 failure clause fires. Parth's narrative: g5 is premature; Black plays Nh5 and locks the position, neutralizing the attack. The real teaching is "before pushing a pawn break, consider opponent's best defensive response."

**Pattern:** v100 failure-mode predicates don't cover "rushed pawn break that fails to its defensive refutation." v104 floor principle fires generic-but-wrong-flavor teaching.

**Fix sketch (predicate):**
- `played_is_pawn_break_with_defensive_refutation`: played move is a pawn push to a square that creates a structural break, AND opp's best reply locks the structure (e.g. opp knight reaches a strong outpost that the played pawn can no longer kick).
- Predicate text: "{played} is a rushed pawn break — Black's {opp_response_piece} {opp_response_san} locks the structure and your break loses its punch."

**Why filed:** specific to pawn-break-locking, needs ≥2 concrete examples before predicate work. Third confirmation of the v104-floor-principle gap shape but the SPECIFIC predicate is unique to this case.

---

*Last updated: 2026-06-06*

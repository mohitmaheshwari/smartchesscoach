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

**Status:** BUILD-READY as of 2026-06-10. Filed 2026-06-06 (Parth batch, 2 examples); the 2026-06-10 Mohit batch supplied the ≥3 needed. The dominant variant is `opp_played_abandons_defense` (3 of 5 examples).

**Examples:**
- `fb_44ab295462d0` — Opp's cxd5 in 1780f8bc m12. Caption rendered: *"Opponent's cxd5 is a mistake. Play f3."* Parth's narrative: cxd5 blocks Black's light-squared bishop behind own pawns; exd5 keeps the bishop active.
- `fb_771714e55f1f` — Opp's c3 in 24eecbfe m13. Caption rendered: *"Opponent's c3 is a serious mistake. Play Ne4 winning the bishop on f4."* Parth wants the WHY explained — c3 fails to address that Bf4 is already undefended.
- `fb_69096be0ece2` — Opp's Qg5 in 98c0c27f m18 (cp_loss 609, eval −479→+130). Caption: *"Opponent's Qg5 is a major blunder. Play Rxe2."* Engine-verified: Qg5 stopped defending the e2 bishop, so Rxe2 wins it. The WHY (`abandons_defense`) is exactly what's missing. Mohit: *"why? it is important to know for a 1200."*
- `fb_78a839dd8931` — Opp's Rxd6 in a19ec007 m32 (opp_inaccuracy). Caption gave the user's recapture but no opp-why. (Also has a confabulated target clause — see #19.)
- `fb_f64573d24a1b` — Opp's Bxc3 in 98c0c27f m7 (opp_inaccuracy). No opp-why. (Also has a confabulated Qxd7+ clause + a same-move dup-SAN templating bug — see #19.)

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

**Why filed:** the underlying facts don't exist yet. `opp_played_landed_unsafe` is the closest analog but only fires for the opp piece itself, not for OTHER pieces becoming undefended due to the opp move. Building this is a similar-sized predicate to `played_piece_was_sole_defender_of_attacked_target` (item 6) but on the opp side. **Now have 5 examples (≥3 met) — `opp_played_abandons_defense` is the clear first variant to build.**

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

**Addendum (2026-06-11, Parth re-triage batch).** Two more mislabels of the same shape:
- `fb_d0454a4088f3` — Nf3 m3 in af668c65 labeled *"Réti Opening"* but White's pawns are already advanced (a King's Gambit structure, `1.e4 e5 2.f4 …`). Réti requires the un-committed-pawn setup; the label ignores the actual pawns.
- `fb_26deef7b13b1` — Nc6 m2 in 75afffcf labeled a *"deviation"* (*"book continues with d6"*) when Nc6 is **exact** Accelerated-Dragon theory (1.e4 c5 2.Nf3 Nc6 …). False-deviation flag on a book move — same "label ignores context" root.

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

## 15. Opp failure-mode: traded_active_for_inactive (Nxf7 class)

**Status:** Filed 2026-06-06. The opp-side failure-mode framework shipped with 2 of 4 scoped variants (`missed_capture`, `missed_mate` — see v110). This is the 3rd.

**Example:** `fb_9f984e9753fc` — Nxf7 m9 in 13ad8b4a. Opponent (White) sacrifices Nxf7. Engine confirms Rxf7 wins (eval -1.94 for Black). The WHY (Mohit-authored, engine-verified): "White traded their two developed pieces — the knight on g5 and bishop on c4 — for your rook that was sitting on f8 doing nothing yet. A sacrifice only works when it removes your active pieces, not the opponent's inactive ones."

**Why deferred from v110:** unlike `missed_capture` (clean: best_move is a capture), this needs:
1. Classify each traded piece as active (off home rank AND attacks ≥1 square in opp half) vs inactive
2. Walk the forced recapture chain (Nxf7 Rxf7 Bxf7+ Kxf7) to identify which pieces leave the board on each side
3. Detect the asymmetry: mover's active pieces traded for defender's inactive pieces
This is materially more complex than the 2 shipped variants and was building-tired-at-5am risk. The override (CAPTION_BACKLOG-adjacent) already handles this specific position.

**Predicate sketch (`opp_failure_traded_active_for_inactive`):**
- Played move is a capture by a piece off its home rank (developed)
- pv_after_played shows a forced recapture sequence
- Net material across the sequence is ~equal (within 1 pawn) BUT mover loses ≥2 developed minors while defender loses an undeveloped rook/piece + pawn
- Fire clause: "{played} trades their {dev_piece_1} and {dev_piece_2} for your {inactive_piece} that wasn't doing anything yet"
- Principle ending: "A sacrifice only works when it removes your active pieces, not the opponent's inactive ones."

**When to build:** next focused session, alongside variant 4 below. Both need the recapture-chain + activity-classification machinery.

## 16. Opp failure-mode: quiet_when_threatened (4th variant)

**Status:** Filed 2026-06-06. 4th of the scoped opp-failure variants.

**Pattern:** opponent had a piece/square under attack and played a quiet move that didn't address it, when the engine's best move was the defensive line.

**Predicate sketch (`opp_failure_quiet_when_threatened`):**
- Before opp's move, opp had a piece attacked by the user (or a square under pressure)
- Opp's played move is NOT a defense of that piece (doesn't move it, doesn't add a defender, doesn't capture the attacker)
- Engine's best_move WAS the defensive line
- **Gating (scope Q3):** require the threat be punishable-by-user — don't fire "opp ignored the attack" when the user can't actually win the piece (it's defended enough)
- Fire clause: "they left the {threatened_piece} on {square} hanging — {best_move_san} was the defense"

**When to build:** next session, with variant 3 above.

---

*Last updated: 2026-06-10*

---

## 17. Promote high-value tactical shape patterns to PRIMARY caption prominence

**Status:** Filed 2026-06-06. `fb_eb62358ce3b3` (game cc02e327, m37 hxg3, opp_blunder cp_loss=9457).

**The complaint (NOT correctness):** the "In-Between Move — Before recapturing, you have a check or bigger threat first. Play that first." caption is *correct and valuable* — it's telling Black (the user), after White's blundering hxg3, *don't auto-recapture on g3; play Rh2+ first* (the mating zwischenzug; engine confirms forced mate). But it renders as the **small teal secondary badge**, and the user wants it as the **main caption**:
> "this was showing as in-between, but with smaller texts, this is actually a great lesson and should be part of caption"

**Root cause (verified):**
- `in_between_move` is a real shape (`shape_patterns.py:302`).
- `promotion_ladder.json` makes shapes **Tier 2 — fill only `when caption_empty=true`**, and they render via the small teal `shape_pattern_name`/`shape_pattern_desc` sub-line (`GameDecryptionV5.jsx:~1586`), never as the primary caption.
- So even a decisive tactical shape (zwischenzug at a 9457-cp_loss moment) is visually demoted to a footnote.

**The decision needed (product, not a guess):**
Which shapes deserve PRIMARY prominence vs staying secondary?
- **Tactical/decisive** (promote to primary): `in_between_move`, `back_rank_trap`, `h7_attack`, `queen_knight_mate`, pin/skewer/fork shapes — these ARE the lesson.
- **Positional/ambient** (stay secondary): `aligned_pieces`, `weak_squares`, `strong_knight_square` — context, not the headline.

**Build sketch (after the decision):**
1. Tag each shape in `shape_patterns.py` with a `prominence: "primary" | "secondary"` field.
2. Promotion ladder / V5 render: when a `primary` shape fires, render it as the main caption (or merge into it), not just the teal badge.
3. Frontend `GameDecryptionV5.jsx`: primary shapes use the main caption styling, not the small teal sub-line.

**Why filed not built:** needs the which-shapes-promote product decision (subtractive/additive at 1200-1500 — don't drown the headline) + frontend rendering work. Recurring (every in_between_move badge), so a one-off override is wrong. Pairs with the eval-bar/review polish.

---

## 18. Opening moves mislabeled "inaccuracy" when severity=good (caption text vs severity-field mismatch)

**Status:** Filed 2026-06-06. `fb_d524596d3894` (game c99c480f, move 1 b3).

**The bug:** caption read *"b3 is an inaccuracy. e4 was better. The curriculum starts with d4."* — but the move record's `severity=good` (cp_loss=63). The caption text **contradicts its own severity field**: it derived "inaccuracy" from raw cp_loss tiers instead of deferring to the canonical `severity` (which already accounts for opening/practical context and says *good*).

**Why it's wrong (3 layers):**
1. **Text vs severity mismatch** — `severity=good` but text says "inaccuracy." Caption must defer to the canonical severity word, not recompute from cp_loss.
2. **Move-1 engine preference ≠ inaccuracy** — at move 1 there are ~5 equally sound first moves (e4/d4/c4/Nf3/b3). A 63cp gap vs the engine's #1 is *preference*, not an error. b3 = Nimzo-Larsen, a real opening.
3. **Self-contradicting recommendation** — "e4 was better" AND "curriculum starts with d4" stapled together (engine #1 vs curriculum line — which is it?).

**Recurring:** any early move (move 1-3) that isn't the engine's top pick gets the same false "inaccuracy" treatment.

**Fix sketch (gating, not a one-off override):**
- Caption layer must NOT emit "X is an inaccuracy/mistake" when canonical `severity ∈ {good, best, excellent}`. The severity WORD in the caption must come from the canonical severity field, never re-derived from cp_loss.
- For early-opening curriculum nudges, reframe neutrally: NOT "b3 is an inaccuracy, e4 was better" but "Our curriculum focuses on d4 openings — b3 (Nimzo-Larsen) is perfectly sound if you prefer it." Curriculum guidance ≠ error labeling.
- Drop the "{engine_best} was better" clause for move-1 alternatives entirely (no first move is "better" than another sound one).

**Related:** CAPTION_BACKLOG #9 (severity-cliff probe) is the INVERSE (good labeled, should be mistake). Both are caption-text-vs-canonical-severity consistency issues — likely worth one unified pass: "the caption's severity word is ALWAYS the canonical severity field, never re-derived from cp_loss."

**Addendum (2026-06-10 batch):**
- `fb_bbfe9b9510ab` — m2 e4 (cp_loss 10), caption rendered **empty** on a routine opening move. Mohit: *"do we need any commentary here?"* No. Routine low-cpl opening moves should render no caption, and the empty-string render itself is a bug. Same family as this entry's "early move shouldn't be error-labeled" — extend the suppression to "no caption at all on routine opening moves," and fix the empty-render.

**Addendum (2026-06-11, Parth re-triage batch) — over-eager variation naming:**
- `fb_b711b4f50735` — c6 m1 in 1b196a4f labeled *"Caro-Kann Advance Botvinnik-Carls Defense"* at **move 1**. At 1…c6 only "Caro-Kann" is known; the Advance/Botvinnik-Carls sub-variation hasn't been determined. Over-specify the variation too early. Pair with the depth-confidence gate (the `depth>=3` rule used for *detection* should also gate the *label* text).
- `fb_39f14438b76d` — same Advance label **re-printed at m17 (endgame)**. The opening name should stop rendering after the opening phase, not repeat every move into the middle/endgame.

---

## 19. Confabulated target/tactic — caption names a gain that isn't on the board

**Status:** Filed 2026-06-10 (Mohit batch). THREE engine-verified examples — designable now.

**The failure:** the why-clause asserts a concrete tactical result (a won piece, an attacked enemy pawn, a follow-up check) that Stockfish does not see on the actual board. Distinct from #8 (sac mislabel) and #13 (bad-trade valuation) — those are *valuation* errors on a real move; this is *hallucinated geometry*: the named target/tactic does not exist.

**Examples:**
- `fb_4c4187178e98` — a4 in a19ec007 m26. Caption: *"Rd1 was better. it wins the rook."* Engine: `Rd1 = +356` (Rd1 only hits the d6 **pawn**; no rook is won — a won rook would be ~+500 more). "Wins the rook" is invented. Mohit: *"it wins the rook??? how?"*
- `fb_78a839dd8931` — Rxd6 in a19ec007 m32. Caption: *"attacks their undefended pawn on f6."* User is Black; **f6 is the user's OWN pawn**. The enemy pawn the rook actually hits on rank 6 is b6. Wrong square + wrong ownership. *(Ownership inferred from FEN + `severity=opp_inaccuracy` + side-to-move; `user_color` not readable at triage time — verify on build.)*
- `fb_f64573d24a1b` — Bxc3 in 98c0c27f m7. Caption: *"opens the line so your queen can play Qxd7+ to chase their king."* `Qxd7+` drops the queen (d7 defended by Ke8, Qd8, Bc8). Pure confabulation. **Also**: the same move is labeled both *"Opponent's Bxc3"* and *"Play Bxc3"* — a same-move dup-SAN templating bug worth fixing alongside.

**Pattern:** the why-target render (the "{move} — {what it does}" clause and the alternative-promotion clause) emits a stated target/follow-up without verifying it against the post-move board. Three failure shapes: (a) claims material won that isn't (`it wins the rook` at +356), (b) names the wrong square / mis-attributes ownership (own pawn called "their pawn"), (c) suggests a follow-up that loses material (`Qxd7+`).

**Fix sketch (guard, not delete — per [[feedback_fix_framing_not_detection]]):** before rendering any "wins/attacks/then play X" clause, verify it on the board:
- "wins the {piece}" → require the eval delta or a forced win of that piece type in the PV; otherwise drop the clause.
- "attacks their {pawn/piece} on {sq}" → require {sq} to actually hold an *enemy* piece that the moved piece attacks post-move.
- "so you can play {follow_up}" → require {follow_up} to be in the engine PV (not eval-losing).
When the claim fails verification, fall back to the plain severity line — silence beats a fabricated target.

**Why filed not built:** 3 clean examples but the guard touches the shared why-clause renderer (broad surface). Needs a scope pass + a probe of how often these clauses fire unverified across the corpus before tightening.

**Addendum (2026-06-11, Parth re-triage batch).** Four more engine-/board-verified confabulations, all on *below-band* moves (cp_loss ≈ 0 — which is the signature: the move is fine, the caption invents a tactic about it):
- `fb_a906eb9a84fc` — Qxd2 m14 in 1b196a4f. Caption: *"Qxd2 — Skewer. It hits the queen on d2…"* It's a plain **recapture of a bishop**; no skewer on the board.
- `fb_e152cc7e8056` — Bxf3 m12 in 1b196a4f. Caption: *"Bxf3 — clean pin on their knight."* It's a **capture**, not a pin.
- `fb_39f14438b76d` — exd6 m17 in 1b196a4f. Caption: *"They won a pawn with that capture."* It won the **exchange** (rook for knight), not a pawn — material-delta miscount (same family as the "it wins the rook"/+356 example above).
- `fb_b137c10813b9` — bxc6 m5 in 75afffcf. Caption: *"Nothing recaptures, so it's free."* The move **was** the recapture; nothing is "free."

Confirms the fix sketch: gate tactic-name + material-gain clauses on the actual board (a "skewer"/"pin" needs its geometry; "won a {piece}" needs the real material delta). The geometric-gating half overlaps #11 (shape-detector overreach).

---

## 20. Disconnected "reason" clauses — engine-correct move, unrelated rationale

**Status:** Filed 2026-06-10 (Mohit batch). Two examples. Same shape as #14 ([[principle_bank_is_filler]]) but the move recommended is engine-correct — only the *reason* is filler.

**Examples:**
- `fb_971847cddbde` — Qc2 in a19ec007 m14. Engine best = `Qd1` ✓ (matches recommendation), but reason given is *"your bishop on e2 is passive"* — unrelated to why Qd1 beats Qc2. Mohit: *"Qd1 doesn't relate to bishop."*
- `fb_b68bbeb1bf25` — Bd2 in 98c0c27f m7. Engine best = `Bd3` ✓, reason *"6 of your pieces are still on your side of the board"* — generic development count, not the actual Bd2-vs-Bd3 difference. Mohit: *"don't think the reason is correct."*

**Pattern:** the alternative is correctly identified, but `good_move_reason` falls back to a generic positional principle that doesn't explain *why this alternative over the played move*. Reads as confident-but-wrong teaching.

**Fix sketch:** when the alternative-promotion clause can't produce a reason tied to the *delta* between played and best (what best does that played doesn't), drop the reason rather than stapling a generic principle. Folds into the #14 / #2 "why-better must be delta-grounded" work.

**Note (item 8, `fb_896762a9722b`):** Qb3 in a19ec007 m10 — a **−59cp inaccuracy** (engine best `Nxe5`; eval +19→−44) rendered as a positive *"Hidden Attack"* shape badge. Shape detector fires on a move that's actually bad → sibling of #11 (shape-detector overreach: gate shapes on the move not being an inaccuracy/mistake). Logged here; investigate under #11.

---

## 21. "Only move" / "forcing move available" template overclaims

**Status:** Filed 2026-06-11 (Parth re-triage batch). Three examples. The template asserts uniqueness/forcing-ness without checking the engine.

**Examples:**
- `fb_f49d896177d8` — exd5 m3 in e2815608. Caption: *"exd5 — only move."* Parth: not the only move (e5, Nc3, Nd2 all playable).
- `fb_0bc718b251da` — Qxc4 m14 in e2815608. Caption: *"Qxc4 — only move."* Parth: alternatives exist.
- `fb_dab0594291ec` — Bf4 m9 in 0a5af44c. Caption: *"Forcing move available — check, capture, or threat. Strongest move here."* No forcing move exists, and Bf4 isn't best (engine top-2 = Nc3 / f3). cp_loss 46.

**Pattern:** the "only move" and "forcing move available / strongest" clauses fire on a label/heuristic, not on the eval gap to the 2nd-best move (and not on whether a check/capture/threat actually exists).

**Fix sketch:** only emit "only move" when engine #2 is losing by a real margin (e.g. ≥ the band blunder_cp); only emit "forcing move available" when a check/capture/material-threat is on the board; never call a non-#1 move "strongest."

**Why filed:** recurring template overclaim, ≥2 examples. Gating is a clean engine-gap check; no per-position prose. Worth a small predicate-gate pass.

---

## 22. False positional cue — caption asserts a wrong positional fact (not just filler)

**Status:** Filed 2026-06-11 (Parth re-triage batch). Five examples. Distinct from #14/#20 ([[principle_bank_is_filler]]): there the reason is *generic*; here the asserted positional fact is *false*.

**Examples:**
- `fb_2db2e2ce5429` — Nf3 m7 in 1b196a4f. Caption: *"doesn't claim the center."* Nf3 does influence d4/e5.
- `fb_235ae451cb7f` — Nc3 m10 in 1b196a4f. Caption: *"doesn't control the center effectively."* Misses that Nc3 **threatens to win the isolated d5 pawn** — the actual point of the move.
- `fb_37c24d0e2723` — Bd2 m11 in 1b196a4f. Caption: *"develops but blocks the bishop."* Bd2 **breaks a pin** on the c3 knight; doesn't block.
- `fb_abc1b9a602a0` — g6 m2 in 4ec5dfca. Caption: *"Pushing pawns near your king before castling weakens it."* g6 is a **fianchetto**, the standard not-weakening setup. Wrong cue.
- `fb_c71898c82f58` — Nf6 m3 in af668c65. Caption: *"Nf6 mirrors White's approach."* Nf6 is actually a **blunder** in that position — "mirrors" mischaracterizes it.

**Pattern:** generic positional cues ("doesn't control the center", "pushing pawns near the king weakens it", "blocks the bishop", "mirrors") fire from a template without reading the board, and assert something the position contradicts.

**Fix sketch:** suppress each cue unless the position actually matches — exempt fianchetto pawns (g6/b6/g3/b3) from the king-weakening cue; don't emit "doesn't control/claim the center" when the piece hits central squares or makes a central threat; don't say "blocks the bishop" when the move breaks a pin / opens a line. Where no verifiable positional fact applies, fall to the plain severity line.

**Why filed:** ≥2 examples, recurring. Touches the positional-cue templates broadly (probe how often each fires unverified before tightening).

---

## 23. Caption references the wrong move / asserts false engine-disagreement

**Status:** Filed 2026-06-11 (Parth re-triage batch). Correctness bug (not wording). Two+ examples.

**Examples:**
- `fb_bf79c3079b95` — m3 in de3e0756. The move **played was Nc3**, but the caption says *"Played Bg5 — book continues with e3."* Names the wrong move (and a line not in the position). Likely a move-reference / indexing mismatch.
- `fb_4d29ff16e253` — Rxd6 m16 in 1b196a4f. Caption: *"Engine wants something else."* But Rxd6 **is** the engine-best move (Parth + engine confirm). False engine-disagreement.
- (Related) `fb_0c47660461f0` — Qxd4 m20 in 1b196a4f rendered as an inaccuracy when it's the best move — overlaps #18 (caption severity word vs canonical severity).

**Pattern:** (a) the captioned SAN ≠ the move actually played, or (b) an "engine wants other / inaccuracy" clause fires when the played move IS engine #1.

**Fix sketch:** assert `captioned_san == played_san` before render (catch the indexing bug); only emit "engine wants something else" / inaccuracy framing when `played_san != engine_best` AND canonical severity is not in {good, best, excellent}.

**Why filed:** correctness, not style — a caption tied to the wrong move or contradicting its own engine-best is the most damaging class. Engine-verify the indexing path on build.

---

## 24. Failure-mode "you lose/hang the {piece}" mis-frames check-sacs and recapture-trades

**Status:** RESOLVED 2026-06-13 (Lane B) — corpus + engine came up, both mechanisms validated against 3000 games / 33,624 blunder captions. **(a) check-sac: NOT observed → closed (do not build).** **(b) recapture-trade: BUILT** — the even-trade gate now ships in `_verify_blunder`. (Originally filed 2026-06-12 when the engine was unreachable.) See the **Resolution** block below.

**Two candidate mechanisms (validate separately — each needs its own ≥2):**

- **(a) check-sac mis-framed as a hang.** When `played_san` is a CHECK (e.g. `Bxf7+`), the `is_exchange_losing` / `opp_reply_attacks_played_piece` clauses can read "you lose the bishop" — but a check-sac is an intentional idea (tempo/initiative), not a hang. The geometric claim (the piece is taken) verifies, yet "you hung it" misreads the move.
  - *Verifier-gate sketch (right-or-silent):* if `played_san` is a check (ends `+`/`#`, or a `played_is_check` fact), the bare "you lose/hang your {piece}" framing is **unverified as a clean loss** → abstain (the narrator carries the sac nuance) UNLESS the engine confirms it is simply losing (a bad sac, no compensation) AND ≥2 clean examples justify a dedicated `check_sac_unsound` clause.

- **(b) recapture-trade mis-framed as a clean loss.** When `played_san` is itself a CAPTURE (e.g. `Qxf3` taking a piece, then recaptured), the `opp_reply_recaptures_on_played_square` / `opp_reply_captures_piece_type` clause says "they take your queen" as if it were a clean loss — but the queen **captured first**, so the net is a trade/recapture (net = captured value − recaptured value), not a hang.
  - *Verifier-gate sketch (right-or-silent):* if `played_san` is a capture (or `material_delta_played_cp` shows the played move won material back), the "you lose your {piece}" framing must **net the captured material** — it is a trade, not a clean loss → abstain or reframe as a trade, UNLESS the net is genuinely losing AND ≥2 clean examples justify a `down_trade` clause.

**Code-path confirmation (2026-06-12, Stockfish up / corpus down — confirmed by reading `_verify_blunder`):** the gap is a real, locatable code path, not a hypothesis.
- **(a)** `_verify_blunder` (caption_claim_verifier.py:133-169) has **no branch** for `is_exchange_losing` or `opp_reply_attacks_played_piece` and never inspects whether `played_san` is a check. Given `cp_loss≥30` + a legal `best_move`, it returns `(True, "blunder_pv_verified")` — so an unsound check-sac ships the "you lose the bishop" framing unconditionally.
- **(b)** `_opp_reply_is_capture` (lines 120-130) confirms the opponent's reply **is** a capture but **never nets `material_delta_played_cp`** — so "they take your queen" ships even when `Qxf3` won equal-or-more material first (a trade, not a loss).

So the build is purely an **added gate** in `_verify_blunder` (Lane-B-owned, geometric, no gateway). What is still missing is the **≥2 clean real examples** that prove the clauses actually fire on check/capture played moves in production — that needs the corpus scan.

**Why filed (not built) [original]:** building without ≥2 engine-verified examples risks a phantom-gap predicate (cf. the piece_safety "had none — don't force it" note).

---

### Resolution (2026-06-13, Lane B — corpus + Stockfish 17.1 up)

Scanned 3000 games (33,624 user blunder captions ≥100cp). Verdicts:

**(a) check-sac mis-framed as a hang — NOT OBSERVED → closed.** Every check-played blunder caption that mentions losing/hanging actually routes to a *different* template — defeatism ("you were already losing"), king-shelter ("lost 2 of its pawn shelter"), or "position is lost." **Zero** frame a check-sac as "you hung your {piece}." The phantom-gap concern was correct; no gate built. Do not build on a future singleton without the same ≥2-clean bar.

**(b) recapture-trade mis-framed as a clean loss — BUILT.** The real shape is narrower and sharper than first sketched: not "queen took a knight, net still losing," but **even trades framed as hangs**. 53 moves (of 110 recapture-on capture-blunders) where the user captured and the forced recapture nets **even material (net 0)** — `Nxf5`/`exf5`, `Bxd5`/`cxd5`, `Nxc6`/`dxc6`, `Bxg2`/`Kxg2`… — yet the caption says "**hangs your {piece} — opponent recaptures on {sq}**". The move IS a mistake (cp_loss 105–400+) but for a **positional** reason; "hang" is a false material claim. 14/14 engine-PV-verified; the gate's even/loss split confirmed across all 110 (53 fire, 57 real losses net≤−2 kept).

*Gate (shipped):* `caption_claim_verifier._played_capture_net()` + a branch in `_verify_blunder`'s recapture block — when the recapture clause fires AND the played move was a capture netting **≥ −1** (even-or-better), return `(False, "blunder_recapture_even_trade")` → **abstain** → the narrator explains the positional why. Geometric (material arithmetic), **no gateway, no runtime Stockfish** — consistent with the module contract. Real losses (knight-for-pawn etc., net ≤ −2: `Nxe5`, `Qxa6` −4, `Nxf2`, `Nxe6`) are **untouched** — their "you lose material" framing is fair. Takes effect on the next caption render after deploy (bump `V5_COACHING_VERSION` / `refresh-v5-captions`).

---

*Last updated: 2026-06-13 (Lane B — #24 RESOLVED: (a) check-sac not observed → closed; (b) recapture-trade even-trade gate BUILT in `_verify_blunder`, 53/110 mis-frames suppressed, 14/14 engine-verified, real losses untouched).*

---

### #25 — Beginner captions are truthful-but-GENERIC vs gold (Shobhit report card, 2026-06-14, from Lane C/D)

**Source:** judge_vs_gold against a new 71-move engine-verified gold set for Shobhit (600, beginner; `db.gold_captions` tag `gold_shobhit`). Detector FIRED on 49/71, abstained on 22. Of the 49 judged vs gold: **MATCH 10, PARTIAL 36, MISS 3.** So R12 is *truthful* (3 wrong) but *generic* — 73% PARTIAL, consistently weaker/less position-specific than the gold. NOT a detection problem; a FRAMING problem (`feedback_principle_bank_is_filler`, `feedback_mistake_must_explain_why`).

**Generator trace (all R12; `caption_rules.py:434 _r12_render` → `R12_blunder.json`):**
- **P1 rigid template:** `user_with_failure_and_alternative` (`R12_blunder.json:248/:275`) = `{played} {failure_clause}. {best} was better — {why_clause}`. `failure_walks_into_check` (:283) renders only "loses to {opp_reply}" (no consequence); `why_user_defensive_pawn_push` (:311) appends a **positionless principle** "— In the opening, don't waste tempo…". → "g4 loses to Bxf2+. Qg3 was better — In the opening, don't waste tempo…" (reproduced live).
- **P2 defeatism:** `why_user_position_already_losing_since_known` (:320) → "You were already in trouble since move 8. Kc2 only slows it." (sibling :321). Fact from `eval_trajectory.py:114-115`.
- **P3 calc-over-principle:** `why_user_missed_piece` (:294) — truthful but no transferable idea.

**Proposed minimal fixes (pure template/selection; right-or-silent preserved; all use EXISTING facts):**
- **(B) BIGGEST LEVER — drop the generic-principle tail when a concrete failure clause already fired.** In `select_variant`, when `failure_clause` present AND the only why is a positionless-principle variant (`why_user_defensive_pawn_push`/`_un_developing`/`_knight_on_rim`), route to `user_with_failure_and_best` (`:276`, "{played} {failure_clause}. {best} was better.") instead of `…_and_alternative`. No detection lost; the tactic stays.
- **(C) kill the 2 defeatist variants (:320–321)** → neutral forward framing, e.g. "{best} holds better — it keeps your pieces defending each other." (`position_was_already_losing` DETECTION stays; only wording changes.)
- **(A) `failure_walks_into_check` (:283) name the consequence** using existing `opp_reply_captures_*` facts → "lets {opp_reply} — the check wins material" when the check also wins material.

**Engine-verified before→after (Stockfish d18-20, real FENs):**
- g4 `rnb3r1/pp3kpp/2p5/q1b1Qp2/2P5/2N5/PP3PPP/R1B1KBNR w KQ - 1 12` (Bxf2+ check, +359→−273): → "g4 is a mistake — Bxf2+ comes with check and wins material. Qg3 keeps your king safe."
- h3 `1k5r/1p1b1p2/7p/4n3/3pP1nb/1P1P4/P2KB2P/2R3R1 w - - 2 29` (−569 before, Bg5+ check): → "h3 lets Bg5+ — the check drives your king off and costs your rook. Kc2 keeps your pieces defending each other."

**Recommendation:** Lane B template fix, **no new predicate** — B and C are pure JSON variant/selection edits; A is a one-fact sub-variant split. ⚠️ Line numbers are from `working-code` before Lane B's latest even-trade/assessment-conflict commits — reconcile `select_variant` ordering before applying.

---

## Focus-area tags in review captions (2026-07-03 request, Mohit) — SHIPPED

**Status:** ✅ SHIPPED as commit `05c861e2` (2026-07-03).

**What actually shipped:**
- Emoji badge chip row rendered above the review caption per mistake move
  (see `frontend/src/components/GameDecryptionV5.jsx`). Multi-tag
  supported — a fast mistake near the king gets ⏱ + 👑 both.
- Backend: new `GET /games/{game_id}/focus-badges` in
  `backend/routes/games.py` reads `move_observations` (v9+ schema) and
  returns the chip data per move.
- Badge inclusion rules tightened over rounds R1–R13 of the audit-loop
  session — final state passes 3 consecutive 9.0/10 audits on
  Parth+Mohit+Shobhit (commit `fcffe6ef`) and 43-user auto-audit avg
  9.75/10, 42/43 users ≥9 (2026-07-04).
- Blockers pre-ship (all cleared before ship):
  1. PWC coach messages cover all 10 topics live → done by `d93ef75d`
     (`services/focus_move_coaching.py`).
  2. Subtypes ≥85% verified-true → v9 audit confirmed for piece_safety;
     v11–v15 tightenings for king_safety, backward_pawn, threat_ignored,
     quiet_blunder.

**Kept below as historical spec / design record.**

---

**Original spec (below is the 2026-07-03 filing — kept for future
reference on how the design started):**

Filed, not started. Requested after the coaching-spine work
lands (34575cb5 / 7b0fb11e / 5b739fff / 9ad53cb0). Depends on the
subtype classifiers already shipped in `move_observation_deriver.py` +
`cognitive_gap_subtypes.py` (schema v9).

**The ask:**
Every mistake move in the game-review caption should surface which
FOCUS-AREA tag(s) it belongs to. Right now the review reads *"Bh6 was
a mistake (-180cp)"* and stops there. The user has no way to see this
mistake maps to their `time_management` or `king_safety` focus.

The user should see the *categories* their mistakes cluster into — not
just what went wrong on this one move.

**Design sketch:**
- The observation record ALREADY carries `missed_pattern`, `subtype`,
  `severity`, and `time_flag` per user move (v9 schema).
- Extend `caption_pipeline.build_move_teaching_decision` (or its
  downstream renderer) to fetch the observation for the same
  `(game_id, move_number)` and prepend a small badge/prefix to the
  caption when a non-null tag exists.

**Caption prefix rules (single tag):**
- `time_flag = impulsive_critical` → *"⏱ **Time issue** — you played
  {move} in {time_spent}s. {existing_caption_text}"*
- `missed_pattern = king_safety, subtype = ignored_king_attack` →
  *"👑 **King safety** — {existing_caption_text}"*
- `missed_pattern = piece_safety, subtype = simple_hang` →
  *"🎯 **Piece safety** — {existing_caption_text}"*
- ...etc, one per (topic, subtype) pair from
  `primary_weakness_picker._CLOSING_BY_SUBTYPE`

**Caption prefix rules (multi-tag on same move):**
A fast Bh6 that also weakened the king shelter tags BOTH
`time_management.impulsive_critical` AND
`king_safety.weakened_shelter`. Show both:
*"⏱ **Time issue** + 👑 **King safety weakening** — you played Bh6
in 1.5s and it opened the h-file to your king. {existing_caption_text}"*

**Non-goal for v1:**
- Don't rewrite the existing caption body — just prepend the badge/tag
- Don't tag routine-good moves; silence on non-mistakes preserved
- Don't invent tags — only ship badges for subtypes that have ≥85%
  verified-true classification (i.e. the ones already board-verified
  in the v9 corpus audit)

**Why it matters:**
Connects individual mistakes to the user's KNOWN pattern areas.
Currently the review is per-move; the user has to mentally aggregate
"oh this is another king safety mistake." The tag makes the pattern
visible per-move. Compounds well with FocusCard's histogram +
day-grid — the review page becomes the "why my focus is what it is"
receipt trail.

**Dependency:**
Do not start until:
1. The 8 non-time non-piece-safety subtypes have topic-specific live
   PWC coach messages wired (the audit in this session found only
   time_management + piece_safety are complete).
2. Subtypes with `verified-true < 85%` are either tightened or
   labeled `unverified_hint` (mostly done in v8, some soft buckets
   remain — those should NOT be surfaced as tags in the review).

Otherwise the review page will contradict itself vs the FocusCard
histogram, and users will see tags for patterns the coach can't
actually help them with yet.

**Owner:** unassigned. File closed as "spec-ready" — build when the
PWC intervention loop closes across all topics.

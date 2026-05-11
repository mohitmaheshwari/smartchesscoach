# V5 Caption Pipeline — Design Doc

**Status:** DRAFT v2 — review feedback applied. Awaiting user sign-off before code.
**Version:** v2 (2026-05-11). v1 was reviewed; user flagged 4 critical fixes
+ 2 deferred items. All 4 critical fixes applied in this version (see §16).
**Locked rule (memory):** `feedback_v5_caption_rewrite_no_patches.md` — no template patches in V5 caption code until this pipeline ships.

---

## 1. Goal

Replace the V5 dispatcher (which routes captions by `piece.piece_type` and `to_square`, producing fluffy templates like *"Bishops love open diagonals!"*) with a 3-stage pipeline where **every word in every caption traces back to a function that read the FEN**. Hallucination becomes structurally impossible by construction, not by post-hoc filtering.

The bar is set by Parth Gilda (chess coach, beta reviewer):

> *Chess is maths. Accuracy is very very high here, from both board, position and commentary and teaching. No compromises on teaching and just can't say any random shit.*

---

## 2. Why this rewrite (the bug pattern that motivates it)

The current V5 generator has separate **rule-based voices** that run independently:
- A king-safety nudge that fires whenever the user is uncastled (says "castle right away" regardless of what move was played)
- A "look for checks" tip
- A book-theory lookup running on stale move history
- A vacuous filler library ("position is balanced", "improve your worst piece")
- A pattern-history claim ("7 of your last 20 games") that fires generically
- An engine layer (Stockfish multi-PV) producing candidate moves

These voices **don't talk to each other**. The engine voice says "the best move is dxe6, winning a pawn." The teacher voice says "castle right away." Both render onto the same card. The user reads contradictions.

Today's source patches address individual templates but the **architecture keeps producing new bugs** because the dispatcher (piece-type routing) has no idea what the engine wants. The only fix is to make the engine the single source of truth and have the renderer explain THAT — nothing else.

---

## 3. Architecture

```
move
  → fact_extractor.extract(
      board_before, move, board_after,
      eval_before, eval_after, cp_loss,
      best_move, pv_after_played, pv_after_best,
      move_history_san, full_move_number,
      opening_info
    )
  → facts: dict  (deterministic, FEN-derived)
  → rule_renderer.render(facts)
  → CaptionOutput {
      caption: str,            # ≤25 words
      highlight_squares: [str],
      arrows: [(from, to, color)],
      rule_name: str           # which rule fired (for debugging)
    }
```

The dispatcher is GONE. No more "if piece is bishop, call bishop template." The extractor produces facts; the renderer picks a rule whose trigger matches those facts; the rule fills its template from the facts.

**Three files:**
- `backend/services/caption_facts.py` — fact extractor
- `backend/data/caption_rules.py` (or .json) — rule library
- `backend/services/caption_renderer.py` — picks rule, fills template, returns output

**Files deleted from V5 service:**
- `recognize_good_move()` — the cheesy "Bishop on an active diagonal" branches
- `_explain_opponent_move_with_context()` — "Pawn advances to e5. They want the center!"
- `_generate_generic_plan()` piece-type fallback — "puts your bishop where pawns block..."
- `_analyze_opponent_mistake()`, `_analyze_opponent_slip()` — hardcoded "fun" text
- The post-emission filter pass (`vacuous_text_detector` + `coaching_text_guard`) becomes redundant because the new pipeline can't hallucinate by construction

---

## 4. Fact Extractor spec

A pure function. Same inputs → same outputs. No side effects, no LLM, no random.

```python
{
  # ─── Engine truth (already stored in move_evaluations) ────────────
  "cp_loss": int,                      # always >= 0
  "eval_before_cp": int,
  "eval_after_cp": int,
  "best_move_san": str,
  "played_san": str,
  "played_is_best": bool,
  "pv_after_played": [san, ...],       # up to 8 plies
  "pv_after_best": [san, ...],

  # ─── Position facts (python-chess on board_after) ─────────────────
  "is_check": bool,
  "is_capture": bool,
  "captured_piece_type": "queen|rook|bishop|knight|pawn" | None,
  "is_forced_recapture": bool,         # only legal response after opp capture
  "is_castling": bool,

  # ─── Attack/defense math on the move's target square ──────────────
  "target_square": str,                # square the move went to
  "attackers_on_target": [(sq, piece_type), ...],  # opp pieces attacking it AFTER move
  "defenders_on_target": [(sq, piece_type), ...],
  "attacker_count": int,               # kept for context but NOT used as trigger
  "defender_count": int,

  # ─── Static Exchange Evaluation (the real exchange truth) ─────────
  # Raw attacker/defender counts are misleading: a pinned defender doesn't
  # defend, an x-ray attacker doesn't attack right now, and exchange order
  # by piece value matters. SEE walks the full capture sequence with
  # cheapest-piece-first recapture rules and returns the net material
  # outcome. Use this — NOT raw counts — to decide whether a capture or
  # piece placement loses material.
  "see_played_capture_cp": int | None,  # if move is a capture: SEE result for that capture
  "see_target_square_cp": int | None,   # SEE on the move's target square with opp to capture next
                                        # (relevant for non-capture moves that walk into attacks)
  "is_exchange_losing": bool,           # see_played_capture_cp < -50 OR target en prise per SEE
  "exchange_loss_cp": int,              # magnitude of the material loss (signed cp)

  # ─── What the move now threatens or stops defending ───────────────
  "threats_created": [{"target_sq": str, "piece_type": str, "value_cp": int}, ...],
  "pieces_now_undefended": [(sq, piece_type), ...],   # by leaving the from_square

  # ─── Tactic detection (from PV walks; Phase 1 has 5 patterns) ─────
  "tactic": "fork|pin|skewer|discovery|deflection" | None,
  "tactic_targets": [(sq, piece_type), ...],
  "missed_tactic": str | None,         # if pv_after_best reveals a tactic

  # ─── Material accounting (walk the PV) ────────────────────────────
  "material_delta_played_cp": int,     # what playing this yields after PV resolves
  "material_delta_best_cp": int,       # what best would have yielded
  "free_capture": bool,                # 0 recapture in PV after this capture

  # ─── Opening match (uses existing detect_opening_from_moves) ──────
  "opening_name": str | None,          # e.g. "King's Pawn Opening"
  "opening_variation": str | None,     # e.g. "Accelerated Dragon Exchange"
  "is_book_move": bool,
  "book_continues_with": str | None,
  "move_index": int,
  "phase": "opening|middlegame|endgame",

  # ─── Position-state flags ─────────────────────────────────────────
  "user_is_winning": bool,             # eval favours user by >2 pawns
  "user_is_losing": bool,
  "uncastled": bool,
  "queen_out_early": bool,             # from visual_shapes.queen_too_early
  "opponent_queen_out_early": bool,

  # ─── Pawn structure facts (Phase 1 minimal) ───────────────────────
  "is_pawn_move": bool,
  "is_pawn_break": bool,               # pawn move that captures or pushes into opp pawn chain
  "pawn_recapture_choice_toward_center": bool,
  "central_square_captured": bool,     # capture lands on d4/d5/e4/e5

  # ─── Acknowledgement flags ────────────────────────────────────────
  "played_is_best_AND_has_alternatives": bool,  # true ⇒ "Great move"-worthy
  "played_develops_minor": bool,       # opening-phase developing move
}
```

**Implementation note:** every field is computed by a small helper in `caption_facts.py`. The function returns the dict directly — no objects, no classes. Easy to inspect, easy to unit-test, easy to extend.

---

## 5. Rule Library — Phase 1

20 rules in your voice, drawn from the 20 new Parth bugs (2026-05-10). Each rule:

- `trigger`: boolean predicate over `facts`
- `priority`: tie-breaker when multiple rules match (higher fires)
- `template`: ≤25 words with named `{variables}`
- `highlights`: which fact-keys to surface as board highlights
- `arrows`: arrows to draw

The renderer evaluates triggers in priority order, fires the first match, and returns. If no rule matches → `caption = ""` (silence). **Silence is preferred over filler.**

### 5.1 Tactical rules (priority 100)

**R01 — Free material captured**
- *trigger:* `played_is_best AND is_capture AND free_capture`
- *template:* `"Free material — {played} captures the {captured_piece}, nothing recaptures."`
- *highlights:* `[target_square]`
- *arrows:* `[(from, target_square, "green")]`

**R02 — Material loss verified by SEE**
- *trigger:* `cp_loss >= 100 AND is_exchange_losing`  (SEE-based, not count-based)
- *template:* `"{played} loses material in the exchange — {best_attacker} captures, the recapture line costs you {exchange_loss}. {best_move} avoids the trade."`
- *highlights:* `[target_square]` + the leading attacker square + the leading defender square (only those that matter in the SEE sequence — pinned/x-ray pieces are excluded)
- *arrows:* leading attacker → target (red), best_move from → to (green)
- *Why SEE not counts:* counts miss pinned defenders (don't really defend), x-ray defenders (don't defend right now), pinned attackers (can't attack legally), and value imbalance (Q defended by P with R attacking still loses Q). SEE handles all of these correctly because it simulates the actual capture sequence with cheapest-first recapture rules.

**R03 — Fork**
- *trigger:* `tactic == "fork"`
- *template:* `"{played} forks the {target_a} and {target_b}. You win material."`
- *highlights:* tactic_targets
- *arrows:* moved piece → target_a (red), moved piece → target_b (red)

**R04 — Pin / Skewer**
- *trigger:* `tactic in ("pin", "skewer")`
- *template:* `"{played} {tactic}s the {front_piece} against the {back_piece}. The front piece can't move."`
- *highlights:* front_sq, back_sq
- *arrows:* moved piece → back_sq (red)

**R05 — Discovered attack**
- *trigger:* `tactic == "discovery"`
- *template:* `"{played} uncovers an attack on the {target_piece}. {result}."`

**R06 — Check + extra attack**
- *trigger:* `is_check AND threats_created != []`
- *template:* `"{played} — check, and attacks the {threat_target} too. King has to move first; the {threat_target} is yours next."`

**R07 — Plain check**
- *trigger:* `is_check AND threats_created == []`
- *template:* `"{played} — check. King has to move or block."`

**R08 — Missed tactic (Socratic)**
- *trigger:* `severity in ("mistake", "blunder") AND missed_tactic`
- *template:* `"There's a {missed_tactic} here. Can you find it? Look at {hint_square}."`
- *Geometric guarantee:* the detector only returns a named pattern when the geometry IS present. No false positives by construction.

### 5.2 Material / capture rules (priority 80)

**R09 — Free pawn taken, but better existed**
- *trigger:* `free_capture AND NOT played_is_best AND material_delta_best > material_delta_played`
- *template:* `"{played} wins the pawn, but {best_move} was stronger — {best_reason}."`

**R10 — Forced recapture**
- *trigger:* `is_forced_recapture`
- *template:* `"{played} — only move. Takes back the {captured_piece}."`

**R11 — Central pawn capture**
- *trigger:* `is_capture AND central_square_captured`
- *template:* `"{played} takes in the centre. You now control {center_squares_controlled} — they control {their_count}."`
- *No abstract claims.* The "you control 2 central squares, they control 1" framing is concrete and visible on the board.

**R12 — Recapture toward centre**
- *trigger:* `pawn_recapture_choice_toward_center`
- *template:* `"{played} — recapture toward the centre. Pawn now defends {defended_squares}."`

### 5.3 Opening rules (priority 70)

**R13 — Named opening / variation match**
- *trigger:* `is_book_move AND opening_variation`
- *template:* `"{played} — {opening_variation}. {one_concrete_idea}."`
- `one_concrete_idea` MUST be a specific consequence — a piece going to a square, a pawn break prepared, a diagonal opened. Examples: "Bishop heads to g7", "Prepares the d4 break", "Opens the long diagonal for Bb7". Forbidden: "stakes a central claim", "controls the center", "flexible play."

**R14 — First-move opening intro**
- *trigger:* `move_index == 0`
- *template:* `"{opening_name}. {what_it_opens}."`
- `what_it_opens` names which own pieces gain mobility from this move. Concrete examples:
  - e4 → "Opens the bishop on f1 and the queen on d1."
  - d4 → "Opens the bishop on c1, controls e5."
  - c4 → "Attacks d5 with the c-pawn before committing the d-pawn."
  - Nf3 → "Develops the knight, controls e5 and d4."
- *arrows:* common black responses (e4 → e5 blue, e4 → c5 blue, e4 → e6 blue) — visual is the lesson, not the prose.

**R15 — Developing move with purpose**
- *trigger:* `phase == "opening" AND played_develops_minor`
- *template:* `"Develops the {piece} to {to_square}. {what_it_does_now}."`
- `what_it_does_now` MUST name a specific board fact: a square it attacks, a square it defends, a pawn break it supports, a king-side or queen-side it points at. Forbidden generic fillers: "active piece", "good square", "natural development", "controls the centre" (without naming which square).
- Examples:
  - Nf3 → "Develops the knight to f3. Attacks e5, prepares castling kingside."
  - Bg5 → "Develops the bishop to g5. Pins the knight on f6 to the queen."
  - Ne7 → "Develops the knight to e7. Supports a d5 break."

**R16 — Early queen sortie (self)**
- *trigger:* `queen_out_early AND played_is_queen`
- *template:* `"Queen out too early. Develop a minor piece first. {best_move} was stronger."`

**R17 — Early queen sortie (opponent)**
- *trigger:* `opponent_queen_out_early AND severity == "context"`
- *template:* `"They brought the queen out early. Develop a piece AND attack her — win tempo."`

### 5.4 Positional rules (priority 60)

**R18 — Passive when winning**
- *trigger:* `user_is_winning AND cp_loss < 50 AND NOT played_is_best AND best_move_is_active`
- *template:* `"When ahead, keep pressing. {played} gives them time. {best_move} keeps pressure on {target}."`

**R19 — Pawn break**
- *trigger:* `is_pawn_break`
- *template:* `"{played} — pawn break. {what_it_weakens_or_opens}."`

### 5.5 Quality acknowledgement (priority 50)

**R20 — Best move played, objective acknowledgement**
- *trigger:* `played_is_best AND has_extractable_reason`
- *template:* `"Best move. {played} {primary_reason}."`
- The acknowledgement word comes from a small fixed set, chosen on objective criteria — NOT emotional. Banned: "Great", "Excellent", "Amazing", "Nice find", "Well done".
  - `cp_loss == 0 AND played_is_best AND tactic_present` → **"Precise."** (tactical accuracy)
  - `cp_loss == 0 AND played_is_best AND material_delta_played > 100` → **"Strong."** (wins material)
  - `cp_loss == 0 AND played_is_best AND other` → **"Best move."** (engine's #1)
  - `cp_loss <= 20 AND NOT played_is_best AND played_is_reasonable` → **"Solid."** (close to best, not best)
- *Reason source:* `extract_primary_reason(facts)` — see §5.7. The reason is ONE fact, not three.
- *No emotional words.* If Stockfish later disagrees with a "Great move" call, user trust collapses. Objective wording survives engine disagreement because it makes a factual claim, not an emotional one.
- *If no extractable reason* (forced recapture / only-move): fall through to R10.
- *If reason but cp_loss > 0:* `"Best per engine. {played} {primary_reason}."` (factual, no praise word).

### 5.6 Fallback

**R-FALLBACK** — no rule matched. Return `caption = ""`. Silence. The frontend has the severity badge and move SAN — that's enough when we have nothing concrete to add.

### 5.7 `extract_primary_reason(facts)` — single-reason scoring layer

A move can satisfy many "good reasons" simultaneously: develops, defends, attacks, supports a break, prepares castling, joins a battery. Listing all of them produces bloated captions and recreates the old V5 problem. The pipeline must pick **one** reason, the most important one.

The scoring layer is **deterministic priority order** — no fuzzy weighting, no LLM judgment. Higher priority always wins; only one reason returns.

**Priority order (highest first):**

1. **Tactic in this move** — `fork | pin | skewer | discovery | deflection` is present. Reason text names the tactic concretely.
2. **Material gain** — `material_delta_played_cp > 100` or `free_capture`. Reason text names what was won.
3. **Check or mate threat** — `is_check AND threats_created` OR mate in PV.
4. **King safety** — castling, or move that defends against a mate threat.
5. **Concrete defensive duty** — defends an attacked own piece worth more than the moving piece.
6. **Threat creation** — `threats_created` is non-empty; reason names the attacked piece.
7. **Pawn structure win** — recapture toward centre, creates passed pawn, breaks opponent pawn chain.
8. **Development with concrete next-step** — minor piece reaches square that supports a named pawn break, defends a key square, or prepares castling. The "concrete next-step" is required; bare "develops the piece" does NOT qualify and falls through to (10).
9. **Activity gain** — attacks a previously undefended high-value square.
10. **Cosmetic / generic** — engine ranks the move best but no factual hook can be extracted. Returns `None`. Caller renders no reason, just the move.

```python
def extract_primary_reason(facts) -> Optional[str]:
    if facts.get("tactic"):
        return _format_tactic_reason(facts)              # priority 1
    if facts.get("free_capture") or facts.get("material_delta_played_cp", 0) > 100:
        return _format_material_reason(facts)            # priority 2
    if facts.get("is_check") and facts.get("threats_created"):
        return _format_check_plus_attack_reason(facts)   # priority 3 (check)
    if _move_defends_against_mate(facts):
        return _format_mate_defense_reason(facts)        # priority 3 (mate defense)
    if facts.get("is_castling"):
        return "your king is now safe"                   # priority 4
    defends = _move_defends_attacked_higher_piece(facts)
    if defends:
        return f"defends the {defends.piece} on {defends.square}"  # priority 5
    if facts.get("threats_created"):
        return _format_threat_reason(facts)              # priority 6
    if facts.get("pawn_recapture_choice_toward_center"):
        return "healthier pawn structure"                # priority 7
    if _creates_passed_pawn(facts):
        return f"creates a passed pawn on the {facts['file']} file"
    if facts.get("played_develops_minor") and _has_named_next_step(facts):
        return _format_development_with_target(facts)    # priority 8
    if _attacks_undefended_high_value(facts):
        return _format_attack_reason(facts)              # priority 9
    return None                                          # priority 10 → caller renders no reason
```

**Why priority and not weighted scoring:** weighted scoring requires tuning, and tuning drifts. Hard priority is predictable, debuggable, and explainable to the user when they ask "why did the caption say X and not Y?"

**Used by:** R20 (best move ack), R09 (alternative-was-better), and any rule that needs a "WHY" clause.

---

## 6. Concept Library

Separate from tactic/mistake rules. **Concept rules attach lessons to positions where a positional feature exists, regardless of whether the move was a mistake.** They fire on top of (or alongside) the main rule when the feature is present.

Phase 1 — small set, all mechanical:

**C01 — Open file rook**
- *trigger:* `rook_move AND target_file_has_no_pawns`
- *attach:* `"+ Open file — your rook dominates this column."`

**C02 — Passed pawn**
- *trigger:* `pawn_move AND becomes_passed_pawn(target_square)`
- *attach:* `"+ Passed pawn — no opposing pawn can stop it."`

**C03 — Bishop pair advantage gained/lost**
- *trigger:* `is_capture AND opponent_loses_bishop_pair OR own_bishop_pair_traded`
- *attach:* `"+ You {have/lost} the bishop pair — favours open positions."`

**C04 — Doubled pawn created (self)**
- *trigger:* `pawn_recapture AND creates_doubled_pawn`
- *attach:* `"+ Doubled pawns — weakness, but you opened a file."`

**C05 — Trade decision**
- *trigger:* `voluntary_piece_trade AND opponent_piece_more_active`
- *attach:* `"+ Trade only when it helps you — they lose more from this exchange than you do."`

**Rule:** concept fragments append (with `+ ` prefix) to the base rule's caption ONLY IF total stays ≤ 25 words. If it would exceed, concept is dropped — base caption stands alone.

---

## 7. Renderer voice spec

- **Hard limit:** ≤25 words total per caption.
- **Structure (when applicable):** `{Rule/Statement}. {Concrete consequence or math}. {Better move + brief reason}.` — at most three sentences.
- **Vocabulary:** 1200-level. **Banned words:** outpost, fianchetto, controls, activates, minority attack, luft, repositions, breakthrough (as a noun), maneuver, prophylactic.
- **Voice:** factual, short. Memorable rule first when applicable. **No "fun" voice** (no "horsey hops", "chomp", "they want the center").
- **Every variable** in a template MUST be filled by a fact returned by the extractor. If a fact is `None`, the rule's trigger fails — fall through to next rule.
- **Acknowledgement requires a reason.** Never bare "Great move."
- **Silence over filler.** When no rule fires, return `""`.

---

## 8. Output contract

The move record in `decryption_v5_data` becomes:

```json
{
  ...existing fields (move_number, move_san, fen_before, fen_after, severity, cp_loss, eval_*, etc),
  "narrative": "≤25 word caption",
  "rule_name": "R02",
  "highlight_squares": ["d5", "b7", "c4"],
  "arrows": [
    {"from": "b7", "to": "d5", "color": "red"},
    {"from": "c4", "to": "b3", "color": "green"}
  ],
  "plan": null     // delete the ChessPlan dict; everything is in caption + highlights + arrows
}
```

**Deleted fields** (not regenerated): the `plan` dict (current_problem, consequence, better_approach, transferable_learning) — those become part of the narrative or arrows.

**Migration consideration:** old data has `plan` populated. The frontend currently reads `plan.current_problem` separately. Either:
- (a) Drop frontend's plan-rendering, the narrative replaces it (clean), OR
- (b) Keep plan rendering, but populate `plan.current_problem = caption` for backward compat during transition.

My recommendation: (a). The narrative + highlights + arrows is the single source. Cleaner.

---

## 9. Frontend change

`GameDecryptionV5.jsx`: add reading of `arrows` array alongside the existing `highlight_squares`:

```jsx
useEffect(() => {
  const m = decryptionData[currentMoveIndex];
  setHighlights(m.highlight_squares ?? []);
  setArrows((m.arrows ?? []).map(a => [a.from, a.to, a.color]));
}, [currentMoveIndex, decryptionData]);
```

That's the only frontend change. `LichessBoard` already renders both natively.

---

## 10. Migration plan

1. **Build `caption_facts.py`** with the fact extractor. Inline unit tests for each fact (smoke-test on 5 known positions).
2. **Build `caption_rules.py`** with the 20 Phase 1 rules + concept library.
3. **Build `caption_renderer.py`** — picks rule, fills template, returns output dict. Falls back to `""` on no match.
4. **In V5 main loop** (`game_decryption_v5_service.py`): replace the dispatcher branches with a single call:
   ```python
   facts = extract_facts(...)
   output = render_caption(facts)
   move_output["narrative"] = output.caption
   move_output["rule_name"] = output.rule_name
   move_output["highlight_squares"] = output.highlights
   move_output["arrows"] = output.arrows
   move_output["plan"] = None
   ```
5. **Delete:** `recognize_good_move`, `_explain_opponent_move_with_context`, `_generate_generic_plan` piece branches, `_analyze_opponent_mistake`, `_analyze_opponent_slip`. The post-emission vacuous/hallucination filters can stay (defence in depth) but should never fire.
6. **Frontend:** add `arrows` reader in `GameDecryptionV5.jsx`.
7. **Run** `regen_v5_decryption.py --game-id d7ce40cf-2856-4f1f-b61b-29167deef219` → review every caption with user.
8. **If captions are right:** run on full 137-bug corpus. Confirm no regressions. Re-run on 500 games for reviewer queue.
9. **Memory rule retires** once user signs off on game `d7ce40cf` output.

---

## 11. Test cases — the 20 Parth bugs, expected captions

For each flagged bug, the rule that should fire + what the caption should say.

| # | feedback_id | move | Parth's complaint | Rule | Expected caption |
|---|-------------|------|-------------------|------|------------------|
| 1 | fb_00ab945df727 | Qb5 #30 | passive when winning, labeled good | R18 | "When ahead, keep pressing. Qb5 gives them time. {active_alt} keeps the pressure on white's weak {square}." |
| 2 | fb_891fe0276d3a | e3 #28 | pawn break needs purpose | R19 | "e3 — pawn break. Weakens white's kingside, opens lines for your bishops." |
| 3 | fb_ffaa587d4104 | Qxb2 #25 | won pawn but engine prefers e3 | R09 | "Qxb2 wins the pawn, but e3 was stronger — pawn break that hits {target}." |
| 4 | fb_f92cf2cbd602 | Be5 #24 | system caption hallucinates Na5 response | R02 | "Be5 attacks the rook defending the knight. After they move it, the knight falls." |
| 5 | fb_4d3f804ee559 | Be5 #24 | same — engine choice was Be5 not e3 | (engine data fix — separate from caption design) |
| 6 | fb_eb293e01bd1f | Qh3 #20 | Socratic about skewer needed | R08 | "There's a skewer here. Can you find it? Look at the {file} line." |
| 7 | fb_30b4c7e1c948 | d4 #18 | wants alternative explanation | R19 + alt | "d4 — pawn break. Hits their bishop on e3. Qb8 or Qc7 was sharper — queen-bishop battery." |
| 8 | fb_35be7e75b130 | Rd8 #17 | "Reasonable" too thin | R20 (or alt) | "Rd8 is solid. Nf5 was stronger — develops and attacks the bishop." |
| 9 | fb_5a4a62c689cc | Be6 #15 | positive ack missing | R20 | "Great move. Be6 defends d5, develops, connects your rooks." |
| 10 | fb_6b4018248a75 | Bd6 #14 | trade-decision lesson | C05 | "Bd6 keeps your bishop. Trade only when it helps — your dark-squared bishop is too active to swap." |
| 11 | fb_9c45fbf6f817 | d5 #11 | "Better late than never" too thin | R15 | "Develops the pawn to d5 — stakes a central claim, opens lines." |
| 12 | fb_328a99f35870 | Ne7 #10 | missing "supports d4 break" | R15 | "Develops the knight to e7. Supports a d4 break later, prepares castling." |
| 13 | fb_de35be76965d | Qb6 #8 | early queen mislabeled good | R16 | "Queen out too early. Develop a minor piece first. Nc6 was stronger." |
| 14 | fb_19bbdd4bfe0b | f6 #6 | better was Nc6 | R20 (with alt) or R09 variant | "f6 holds the rook, but Nc6 was stronger — develops AND defends in one move." |
| 15 | fb_921d9590fe08 | Qd4 #6 (opp) | generic "queen harassable" | R17 | "They brought the queen out early. Develop a piece AND attack her — win tempo." |
| 16 | fb_b137c10813b9 | bxc6 #5 | recapture-toward-centre teach | R12 | "bxc6 — recapture toward the centre. Healthier structure, more central control." |
| 17 | fb_a00fc52f6f7f | g6 #4 | wants Dragon name | R13 | "g6 — Sicilian Dragon setup. Bishop heads to g7, pressures the long diagonal." |
| 18 | fb_fda81a78abdb | cxd4 #3 | wants centre-control teach | R11 | "cxd4 takes in the centre. You now have two centre pawns; white has one." |
| 19 | fb_26deef7b13b1 | Nc6 #2 | book detector falsely says deviation | (detector fix — separate from caption design, but: needs deeper book matching) |
| 20 | fb_09a03b362b1e | e4 #1 (context) | wants arrows for responses | R14 | "King's Pawn Opening. White stakes a central claim." + ARROWS: e5, c5, e6, c6, d5 |

**Two bugs are NOT pure caption issues:**
- #5 (Be5 vs e3) — engine choice at depth 12 disagrees with deeper analysis. Separate concern (analysis depth, not rendering).
- #19 (Nc6 in Dragon) — opening detector doesn't match deep variations. Separate from caption pipeline; needs work on opening detection layer.

**18 of 20 bugs covered by Phase 1 rules.** The remaining 2 are upstream data issues that the rule library can't fix on its own.

---

## 12. Appendix A — Extended Tactic & Concept Library (Phase 2-4)

Phase 1 ships with 5 tactic patterns. This appendix lists the ~20 additional patterns to add in Phase 2/3/4. Order: easy → hard.

### Phase 2 — Pure geometric patterns (~1 day each)

All mechanical: look at the board after the move and check a condition.

- **Discovered check** — `board_after.is_check()` AND the checking piece is NOT the moving piece. Identifies the uncovered attacker.
- **Double attack (non-fork)** — two separate threats created by the move that aren't a fork (e.g., line cleared so another own piece now attacks something).
- **Battery** — two own pieces on the same file/rank/diagonal, both bearing on the same opponent piece or square. Walk the line.
- **X-ray attack** — sliding piece's ray passes through an opponent piece to another opponent piece behind it.
- **Overloaded defender** — one opponent piece is the defender for ≥2 of its own pieces, both under attack.
- **Back-rank weakness** — opponent king on back rank with no pawn escape; own rook/queen reaches the back rank.
- **Trapped piece** — opponent piece has 0 legal squares that don't lose material.

### Phase 2 — Multi-ply PV walks (~2-3 days each)

Walk the engine's PV, check conditions across moves.

- **Zwischenzug (in-between move)** — `pv_after_best[0]` is a forcing move (check/capture) before the "obvious" recapture/block; the obvious move appears at PV index 2 or 3.
- **Removing the defender** — PV move 1 captures a piece P; PV move 3 captures a piece Q that was previously defended by P.
- **Decoy** — PV move 1 is a sacrifice or forcing move that draws an opponent piece off-square; PV move 3 wins material at the square the forced piece left.
- **Pawn breakthrough** — pawn capture/push leads to a passed pawn reaching 7th/8th rank within 4 plies.
- **Perpetual check** — PV shows ≥3 consecutive checks with king cycling between 2 squares.

### Phase 3 — Positional concepts (~1 week)

These become **concept rules**, not tactic rules. They attach `+ ` fragments to base captions.

- **Zugzwang (endgame)** — every legal move has cp_loss ≥ threshold; tunable per phase.
- **Stalemate trap** — opponent has no legal moves and isn't in check.
- **Open file dominance** — own rook on a file with no pawns (already in concept library C01).
- **Passed pawn** — pawn with no opposing pawn on its file or adjacent files (C02).
- **Doubled pawns** (C04).
- **Isolated pawn** — pawn with no friendly pawns on adjacent files.
- **Backward pawn** — pawn can't safely advance.
- **Bishop pair** (C03).

### Phase 4 — Skip until users specifically need them

- **Fortress** — drawn despite material deficit. Hard.
- **Triangulation** — king tempo-losing maneuver. Hard.
- **Outflanking** — king-and-pawn endgame technique. Hard.

### Implementation order

1. **Phase 1** (this doc — main rule library)
2. **Phase 2 geometric** (~1 week sequential or 2-3 days parallel)
3. **Phase 2 PV walks** (~2 weeks)
4. **Phase 3 concept library** (~1 week)
5. **Phase 4** skipped until specifically needed

Total: ~5 weeks for the full library if everything ships sequentially. Phase 1 alone covers the 18 of 20 current Parth bugs.

### Detection guarantee

For every pattern (Phase 1 through 3), the detector either:
- Confirms the pattern is **geometrically present** in the position → fact is returned
- Doesn't fire → fact is None → caption doesn't reference the pattern

**The detector cannot falsely name a pattern that isn't there.** False NEGATIVES (missing a tactic) are possible — the library is incomplete — but false POSITIVES are geometrically impossible.

---

## 13. Locked decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | R20 (best move ack) | Objective wording (Best move / Strong / Precise / Solid) — NOT emotional ("Great"). Always paired with a single primary reason from `extract_primary_reason(facts)`. See §5.5. |
| 2 | R08 (Socratic on missed tactics) | Fire whenever the detector returns a named pattern. No hedging — detector is geometrically deterministic; false positives are structurally impossible. |
| 3 | Pattern history claim | Dropped for v1. |
| 4 | Forced recaptures | One-line factual ("Only move. Bxe6 takes back.") — R10. |
| 5 | Opponent moves | Caption when there's something to teach (tactic, queen-out-early, book deviation). Otherwise silent. |
| 6 | Visual layer | Existing infrastructure works. Add `arrows` to the move output dict; frontend reads them next to `highlight_squares`. No new component, no new library. |
| 7 | First deliverable | This design doc (now). After user sign-off → build the three modules end-to-end and run on game `d7ce40cf-2856-4f1f-b61b-29167deef219`. Only then any other code. |
| 8 | Attacker/defender math | SEE (Static Exchange Evaluation), not raw counts. Counts miss pinned defenders, x-ray defenders, value imbalance. SEE handles all correctly by simulating cheapest-first recapture sequence. See §4 and R02. |
| 9 | Primary-reason selection | Single reason via `extract_primary_reason(facts)` with hard priority order (tactic > material > king safety > defense > threat > pawn structure > development > activity > none). No weighted scoring. See §5.7. |
| 10 | Opening language | Concrete consequences only. "Opens the bishop on f1 and the queen on d1" — NOT "stakes a central claim." Rules R11-R15 explicitly forbid abstract filler. See §5.3. |
| 11 | "Great move" wording | Replaced by objective wording: Best move / Strong / Precise / Solid. Emotional praise dies if Stockfish later disagrees; objective claims survive engine drift. See §5.5. |

---

## 14. Proof gate (the contract for unlocking the memory rule)

Before the memory rule (`feedback_v5_caption_rewrite_no_patches.md`) retires, the new pipeline must:

1. Process game `d7ce40cf-2856-4f1f-b61b-29167deef219` (the inspector's reference game).
2. Produce a caption for every move (or silence — both acceptable per design).
3. User reviews every caption. **User approves.**
4. Re-run on the 20 Parth bugs (2026-05-11). At least 16 of 18 caption-fixable bugs produce the expected caption from the test table in §11.
5. Re-run on the 117 older bugs. No regressions where a previously-working caption now fails.

If steps 1-5 all pass → memory rule retires, normal work resumes. Any patches to old templates between now and that gate are forbidden.

---

## 15. What this design does NOT solve

Being honest about boundaries:

- **Engine depth.** If Stockfish at depth 12 picks the wrong best_move (deeper search would prefer something else), this pipeline renders the depth-12 choice. Fixing engine depth is a separate problem.
- **Pattern history.** Specific per-mistake-type history claims need an aggregation layer not built here. Dropped for v1.
- **Decryption voice / situational tone.** This pipeline produces neutral, factual coaching. Tone variations (urgent vs calm vs punishment) per `project_situational_personality.md` are a separate render layer that wraps these captions — not built here.
- **Re-analysis at deeper depth on flagged moves.** If a user flags a caption claiming the move is best when it isn't, we may need to re-analyze that position at depth 20+ to confirm. Out of scope.
- **Opening book completeness.** Phase 1 uses existing `detect_opening_from_moves`. The Accelerated Dragon Exchange wasn't recognised (Parth bug #19). Opening detector improvements are a parallel effort.

### Known limitations of Phase 1, deferred to later phases

These were flagged in the v1 review as architectural concerns that are real but not v1 blockers. Documented here so they aren't forgotten.

- **Rule priority collisions (Phase 1.5).** Today the rule library uses *first-match-wins on a priority-sorted list*. This is sufficient for the 20 Phase 1 rules but will collide once we add Phase 2 tactics. A position can simultaneously contain: a check, a tactic, a free capture, an opening book match, and a positional concept. Suppressing all but the highest-priority loses information. **Future architecture:** a primary rule fires (the main caption), then optional decorator rules append qualifying details if they fit the 25-word budget (concept library already works this way per §6 — extend the same pattern to tactic decorators). Defer until Phase 2 tactics land and collisions actually appear.

- **Template repetition fatigue (Phase 1.5+).** Phase 1 emits captions with fixed sentence shapes. Across 100 games, a user will see the same grammar repeatedly (`"X attacks Y. Z wins material."`) and perceive the system as robotic — even though every caption is true. **Future architecture:** introduce syntactic variants per template (e.g., 3-4 phrasings per rule, picked deterministically by a hash of the position so it's reproducible), and add optional-clause omission ("the {Y} too" → omit when caption is already near 25 words). NOT a v1 blocker — truth > variety, but variety becomes important once truth is stable. Track frequency-of-repetition per user; address when it becomes a complaint.

---

## 16. Review feedback applied (v1 → v2 changelog)

The v1 of this doc was reviewed by the user; six issues were raised. Four were critical (blocking implementation); two were deferred as known future work.

### Critical issues fixed in v2

**Issue 1 — `attacker_count > defender_count` is insufficient.** Raw counts miss pinned defenders, x-ray attackers, value imbalance. **Fixed:** §4 facts dict now includes SEE-based fields (`see_played_capture_cp`, `see_target_square_cp`, `is_exchange_losing`, `exchange_loss_cp`). R02 trigger rewritten to use SEE.

**Issue 2 — No "one reason" extraction layer.** Without it, captions would either pick reasons arbitrarily or bloat by listing several. **Fixed:** §5.7 adds `extract_primary_reason(facts)` with a hard priority order (tactic > material > king safety > defense > threat > pawn structure > development > activity > none). Used by R20 and any rule needing a "WHY" clause.

**Issue 3 — Opening language is still abstract ("stakes a central claim").** **Fixed:** §5.3 rules R11, R13, R14, R15 now require concrete consequences. Examples: e4 → "Opens the bishop on f1 and the queen on d1." Banned filler explicitly listed.

**Issue 4 — "Great move" is emotional and fragile.** If Stockfish later disagrees, trust collapses. **Fixed:** R20 in §5.5 now uses objective wording (Best move / Strong / Precise / Solid) chosen on hard criteria (cp_loss, tactic presence, material gain). "Great" and other emotional praise explicitly banned.

### Deferred issues acknowledged in §15

**Issue 5 — Rule priority collisions.** First-match-wins is sufficient for Phase 1 (20 rules) but will collide once Phase 2 tactics land. Future: primary + decorator architecture. Tracked in §15.

**Issue 6 — Template repetition fatigue over many games.** Phase 1 captions will feel robotic over 100+ games. Future: per-template syntactic variants, optional-clause omission. Tracked in §15. Truth > variety for v1.

### The architectural principle confirmed

> *"Every word in every caption traces back to a function that read the FEN."*

This is the load-bearing sentence. v2 strengthens it by:
- Adding SEE so exchange claims are mechanically correct (not count-based)
- Adding `extract_primary_reason` so the "why" claim is one fact from a deterministic source
- Tightening opening language so abstract filler can't drift back in
- Replacing emotional praise with objective claims that survive engine drift

The geometric guarantee from v1 still holds: false positives are structurally impossible. v2 extends it to include exchange evaluation correctness.

---

## 17. Why this isn't really a "caption" pipeline

A second-order observation that emerged during v1→v2 review: the architecture we've built is bigger than captions.

```
extractor   →   reasoning   →   compressed teaching
   (facts)        (rules)         (≤25-word render)
```

The **extractor layer is the canonical chess-understanding layer for the whole product.** Captions are just the first renderer that sits on top. Future surfaces that can plug into the same facts dict:

- **Play with Coach commentary** — live move-by-move using the same extractor on each new position
- **Postgame review** — same facts, different aggregation
- **Puzzle explanations** — when the user solves/fails a puzzle, render why using the same extractor on the puzzle position
- **Plateau Breaker captions** — when emitting "you've made this mistake before," ground each instance in extractor facts
- **"Why not this move?" tutor** — when the user clicks an alternative, run the extractor on the alt's resulting position and explain
- **Tactical quiz feedback** — same facts, simpler render
- **Adaptive lesson narration** — pick examples from games where specific facts are present (e.g., positions where SEE > 0 to teach "free piece" lessons)

This means the extractor is **load-bearing for the entire coaching stack**, not just for captions. Investing extra rigor here pays compounded dividends. Specifically:

- Every new fact added to the extractor automatically becomes available to all renderers.
- Every renderer is bound by the same law (§13.11, memory: `feedback_renderer_never_computes_chess_meaning.md`): never compute chess meaning, only select and compress facts.
- The renderer-vs-extractor split is not a caption-pipeline detail — it's a product-wide architectural law.

**Implication for the build:** prioritize extractor correctness and field-completeness over rule-library size. A small rule library on a strong extractor will outperform a big rule library on a thin extractor.

---

## 18. Implementation watchlist (non-blocking, must monitor)

These are real risks that don't block v1 but require discipline during build. Documented so they aren't forgotten when the work intensifies.

### 18.1 SEE edge cases

SEE handles exchange evaluation correctly for the common case — capture sequences, pinned defenders, value imbalance, x-ray defenders. But SEE alone won't catch:

- **Trapped-piece compensation** — a piece captured on a square it couldn't escape from anyway. SEE thinks the capture loses material, but the piece was going to die regardless. (Rare; affects ~1% of captures.)
- **Mating attack value** — a piece sacrifice that delivers mate. SEE says -9 (queen sac), but the position is winning. Mate detection must take priority over SEE in the rule trigger order.
- **Long tactical sequences** — SEE walks only the immediate capture chain. A 6-ply combination that finally wins material isn't caught by SEE; needs PV-based material delta (`material_delta_played_cp`) instead.
- **Positional sacrifices** — giving material for long-term positional gain (open file, weakened king). SEE says loss; the position is actually equal or better.

**Mitigation:** use SEE as the primary trigger for R02 (material loss), but the rule's priority is below tactics (R03-R06) and below check-with-mate. If the engine's PV after the move shows a winning sequence despite SEE-negative on the immediate capture, defer to `material_delta_played_cp`. The trigger logic for R02 becomes:

```python
def r02_trigger(facts):
    if facts["tactic"] is not None: return False    # tactic rule fires instead
    if facts["delivers_mate"]: return False         # mate rule fires instead
    if facts["material_delta_played_cp"] > 0: return False  # PV says we're winning
    return facts["cp_loss"] >= 100 and facts["is_exchange_losing"]
```

### 18.2 Rule explosion

The phased plan grows from 20 rules (Phase 1) to ~40 (Phase 2 geometric) to ~50 (Phase 2 PV walks) to ~60 (Phase 3 concepts). Without discipline this becomes unmaintainable.

**Mitigation built into the build:**
- **Flat rule files.** No nested conditionals, no rule-of-rules. Each rule is one entry with `trigger`, `priority`, `template`, `highlights`, `arrows`. If a rule needs branching, split it into two rules.
- **One file per rule category.** `caption_rules/tactical.py`, `caption_rules/material.py`, `caption_rules/opening.py`, `caption_rules/positional.py`. Each file imports facts type and exports a list of rules.
- **Unit test per rule.** Every rule ships with at least one inline smoke test: a FEN + facts dict + expected caption. The rule registry validates that every rule has tests on load.
- **No dynamic rule generation.** Rules are static Python objects (or static JSON). No metaprogramming.
- **Triggers are one-liners.** If a trigger is more than 80 characters, the logic belongs in the extractor (add a fact), not in the rule.

### 18.3 Primary reason extraction quality

The `extract_primary_reason(facts)` layer (§5.7) is the hidden soul of the system. Bad primary reasons are technically true but emotionally wrong:

> *"Best move. Defends b2."* — when the real reason was *"Threatens mate in 3."*

The priority order in §5.7 is a first approximation. It will need tuning based on real Parth feedback.

**Mitigation built into the build:**
- The `extract_primary_reason` function returns BOTH the reason text AND the priority level that produced it. Captions carry the priority in their debug output (not user-visible).
- During regression review, every caption Parth flags as "wrong reason" gets the priority and the alternative reasons logged. Patterns emerge ("you keep picking development over threat" → adjust priority order).
- The priority order is a single sorted list at the top of `caption_facts.py`. Reordering it is a one-line change. No code dependencies on specific priorities.
- A future enhancement: contextual priority adjustments (e.g., in endgames, king safety drops below pawn structure). Not Phase 1; track if Phase 1 reviews reveal need.

### 18.4 The renderer-never-computes law (mechanical enforcement)

Per memory `feedback_renderer_never_computes_chess_meaning.md`: the renderer must not compute chess meaning. The implementation enforces this mechanically.

**Grep-test at CI / before each commit:**
```bash
# These commands must return ZERO lines from caption_rules.py and caption_renderer.py:
grep -E "import chess|chess\\.Board|\\.parse_san|\\.attacks\\b|\\.piece_at|engine\\.analyse" \
  backend/services/caption_renderer.py backend/data/caption_rules/*.py
```

If anything matches, the rule file has reached past the facts dict into chess logic. Move the logic to `caption_facts.py` and re-run.

---

End of design doc.

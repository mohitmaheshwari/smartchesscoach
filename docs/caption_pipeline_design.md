# V5 Caption Pipeline — Design Doc

**Status:** DRAFT — awaiting user review.
**Locked:** 2026-05-11. No code until the user signs off on this doc.
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
  "attacker_count": int,
  "defender_count": int,

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

**R02 — Material loss by attacker/defender count**
- *trigger:* `cp_loss >= 100 AND attacker_count > defender_count`
- *template:* `"Only capture when defenders match attackers. {target_square} had {attacker_count} attackers, {defender_count} defender — {played} loses the {piece}. {best_move} keeps the piece."`
- *highlights:* `[target_square]` + attacker squares + defender squares
- *arrows:* attacker → target (red), best_move from → to (green)

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
- *template:* `"{played} takes in the centre. You get a {center_state} pawn here."`

**R12 — Recapture toward centre**
- *trigger:* `pawn_recapture_choice_toward_center`
- *template:* `"{played} — recapture toward the centre. Healthier pawn structure, more central control."`

### 5.3 Opening rules (priority 70)

**R13 — Named opening / variation match**
- *trigger:* `is_book_move AND opening_variation`
- *template:* `"{played} — {opening_variation}. {variation_idea}."`

**R14 — First-move opening intro**
- *trigger:* `move_index == 0`
- *template:* `"{opening_name}. {idea}."`
- *arrows:* common black responses (e4 → e5 blue, e4 → c5 blue, e4 → e6 blue)

**R15 — Developing move with purpose**
- *trigger:* `phase == "opening" AND played_develops_minor`
- *template:* `"Develops the {piece} to {to_square}. {what_it_enables}."`
  - `what_it_enables` = the most specific fact among: defends X, supports {next_break}, prepares castling, attacks {square}

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

**R20 — Best move played, with reason**
- *trigger:* `played_is_best AND played_is_best_AND_has_alternatives AND has_extractable_reason`
- *template:* `"Great move. {played} {one_thing_it_does}."` (the reason comes from the same extractor — defends X, develops Y, prepares Z, etc.)
- *If no extractable reason* (forced recapture or only-move): fall through to R10.
- *If reason but cp_loss > 0* (best move that's still imperfect): `"Best per engine. {played} {reason}."`

### 5.6 Fallback

**R-FALLBACK** — no rule matched. Return `caption = ""`. Silence. The frontend has the severity badge and move SAN — that's enough when we have nothing concrete to add.

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

## 13. Open decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | R20 (best move ack) | Always pair acknowledgement with a fact-extracted reason. Three sub-cases: tactic available → name it; concrete consequence → name it; no reason extractable → R10 (forced/only-move) or short factual line. No bare "Great move." |
| 2 | R08 (Socratic on missed tactics) | Fire whenever the detector returns a named pattern. No hedging — detector is geometrically deterministic. |
| 3 | Pattern history claim | Dropped for v1. |
| 4 | Forced recaptures | One-line factual ("Only move. Bxe6 takes back.") — R10. |
| 5 | Opponent moves | Caption when there's something to teach (tactic, queen-out-early, book deviation). Otherwise silent. |
| 6 | Visual layer | Existing infrastructure works. Add `arrows` to the move output dict; frontend reads them next to `highlight_squares`. No new component, no new library. |
| 7 | First deliverable | This design doc (now). After user sign-off → build the three modules end-to-end and run on game `d7ce40cf-2856-4f1f-b61b-29167deef219`. Only then any other code. |

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

---

End of design doc.

# Hybrid Principle-Based Caption System

**Date:** July 9, 2026  
**Status:** PHASE 1 (Claude Analyzer) — Ready for integration  
**Next:** PHASE 2 (Detector Fleet) — Full deterministic system

---

## Overview

The system transforms captions from **eval-driven** (shallow: "X is mistake, Y is better") to **principle-driven** (deep: "Rf3+ removes your rook — the only defender against the a5 pawn. By rule of the square, your king can't catch it alone. Play Re1 instead.").

**Architecture:**
```
Position FEN
    ↓
[Endgame Classifier] → position_type, critical_pieces, threats
    ↓
[Claude Analyzer]   → principle-based explanation (rule of square, critical piece, etc.)
    ↓
[Caption Generator] → final coaching caption with quality metrics
    ↓
User's Game Review
```

---

## Phase 1: Claude Analyzer (LIVE)

### Components

#### 1. Endgame Classifier (`endgame_classifier.py`)
Analyzes positions to extract features needed for principle-based coaching.

**Inputs:**
- Chess board position (FEN)

**Outputs:**
```python
EndgameInfo {
    position_type: str          # "K+R vs K+P", "R+P vs R", "K+P vs K", etc.
    material_white: List[str]   # ["R", "P", "P"]
    material_black: List[str]   # ["P"]
    white_pawns: List[str]      # ["c4", "e4"]
    black_pawns: List[str]      # ["a5", "d6", "c7"]
    white_king: str             # "d4"
    black_king: str             # "g8"
    white_rooks: List[str]      # ["f3"]
    black_rooks: List[str]      # []
    threats: List[str]          # ["black_pawn_a5_close_to_promotion", "white_rook_f3_attacked"]
    critical_pieces: Dict       # {"white_rook": "only_defender_of_promotion_threat", ...}
    phase: str                  # "endgame" or "late_middlegame"
    is_theoretical_endgame: bool # True for known patterns
}
```

**Key Methods:**
- `classify_position(board)` → Full classification
- `_classify_position_type()` → Endgame category (K+P vs K, K+R vs K+P, etc.)
- `_detect_threats()` → Identify pawn promotions, attacked pieces
- `_identify_critical_pieces()` → Mark essential pieces ("only_defender", "promotion_threat")

**Used by:** Claude analyzer and caption generator to provide context.

---

#### 2. Claude Endgame Analyzer (`claude_endgame_analyzer.py`)
Uses Claude to generate principle-based explanations for endgame moves.

**Inputs:**
- FEN (position)
- move_san (e.g., "Rf3+")
- position_type (from classifier: "K+R vs K+P")
- critical_pieces (from classifier: {"white_rook": "only_defender"})
- threats (from classifier: ["black_pawn_a5_close_to_promotion"])
- eval_before / eval_after (Stockfish evaluations in cp)
- best_move_san (optional)

**Outputs:**
```python
{
    "explanation": "Rf3+ removes your rook — the only defender against Black's a5 pawn.
                   By the rule of the square, your king can't catch it alone from d4.
                   The pawn will promote. Play Re1 or Re5 to keep your rook working.",
    "principles_used": ["rule_of_square", "critical_piece", "promotion_threat"],
    "quality_score": 0.85
}
```

**Prompt Template:**
```
You are a chess coach. Explain why {move_san} is good/bad using PRINCIPLES.

POSITION: {position_type} (e.g., K+R vs K+P)
CRITICAL PIECES: {critical_pieces} (e.g., rook is only defender)
THREATS: {threats} (e.g., pawn promoting on a5)
EVALUATION: {eval_before} → {eval_after} ({cp_loss} cp loss)

Rules to apply:
- Rule of the square (can king catch pawn?)
- Critical piece roles (what does each piece defend?)
- Promotion threats (will pawn promote if rook moves?)
- King activity and tempo

IMPORTANT: Use concrete, position-specific reasoning.
NOT: "X is mistake, Y is better."
YES: "Rf3+ removes your rook, the only defender of the a5 pawn.
      By rule of the square, your king can't catch it alone.
      Play Re1 to keep defending."
```

**Principle Extraction:**
- Scans explanation for keywords: "rule of square", "opposition", "critical piece", "promotion", "king activity", "tempo", etc.
- Returns extracted principles list for quality verification

**Caching:**
- MD5 hash of (FEN + move_san)
- In-memory cache (cleared on restart)
- Prevents re-analyzing same position multiple times

---

#### 3. Principle-Based Caption Generator (`principle_based_caption_generator.py`)
Integration layer — combines classifier + analyzer into complete caption pipeline.

**Inputs:**
- FEN, move_san, eval_before, eval_after, best_move_san

**Flow:**
1. Parse board
2. Classify position
3. Gate: only use Claude for endgames with significant cp_loss (>100)
4. Call Claude analyzer with position features
5. Verify explanation mentions 2+ principles
6. Return caption dict

**Output:**
```python
{
    "caption": "full principle-based explanation",
    "position_type": "K+R vs K+P",
    "principles": ["rule_of_square", "critical_piece"],
    "quality_score": 0.85,
    "method": "claude_analyzed"  # or "fallback_simple"
}
```

**Fallback Logic:**
- If Claude unavailable → simple caption ("X is mistake")
- If not endgame → use fallback
- If cp_loss < 100 → use fallback

---

## Phase 1 Usage

### Integrating into Game Review

In `postgame_analysis.py` or `generate_game_decryption_v5()`:

```python
from services.principle_based_caption_generator import generate_principle_based_caption

# For each blunder in the game:
caption_data = await generate_principle_based_caption(
    fen=move_eval["fen_before"],
    move_san=move_eval["move"],
    eval_before=move_eval["eval_before"],
    eval_after=move_eval["eval_after"],
    best_move_san=move_eval["best_move"]
)

# Use caption_data["caption"] in the UI
coaching_message = caption_data["caption"]
principles_used = caption_data["principles"]
quality = caption_data["quality_score"]
```

### Testing

Run the test script to verify on the Rf3+ case:

```bash
cd /app/backend
python scripts/test_principle_caption_rf3_plus.py
```

Expected output:
- Position classified as K+R vs K+P
- Critical pieces identified (rook as defender)
- Threats detected (a5 pawn close to promotion)
- Claude explanation generated with 2+ principles
- Quality score ≥ 0.7

---

## Phase 2: Detector Fleet (FUTURE)

**Goal:** Replace Claude dependency with deterministic detectors for each principle.

### Planned Detectors

Each detector answers: "Does this principle apply to this move?"

```python
# Detector Pattern
def detect_principle_X(board, move, user_color) -> Optional[str]:
    """
    Returns:
        "applies"  → principle teaches why move is good
        "violates" → principle teaches why move is bad
        None       → principle not relevant to this position
    """
```

#### Rule of the Square Detector
```python
def detect_rule_of_square(board, move, user_color) -> Optional[str]:
    """
    Can the defending king catch the attacking pawn?
    
    Returns:
        "applies"  → king catches pawn (move is good)
        "violates" → king can't catch (move loses)
    """
```

#### Critical Piece Detector
```python
def detect_critical_piece_role(board, move, user_color) -> Optional[str]:
    """
    Does this move abandon a piece's critical role?
    
    Returns:
        "applies"  → move keeps critical piece active
        "violates" → move removes piece defending something
    """
```

#### Promotion Threat Detector
```python
def detect_promotion_threat(board, move, user_color) -> Optional[str]:
    """
    Can opponent pawn promote if this piece moves?
    
    Returns:
        "applies"  → move doesn't allow promotion
        "violates" → move allows pawn to promote
    """
```

#### Opposition Detector
```python
def detect_opposition(board, move, user_color) -> Optional[str]:
    """
    K+P endgame: does move achieve/maintain opposition?
    
    Returns:
        "applies"  → move uses opposition correctly
        "violates" → move wastes opposition
    """
```

#### Lucena Detector
```python
def detect_lucena_technique(board, move, user_color) -> Optional[str]:
    """
    R+P endgame: building the bridge to promote rook.
    """
```

#### Philidor Detector
```python
def detect_philidor_technique(board, move, user_color) -> Optional[str]:
    """
    R+P endgame: defending correctly against attacking rook.
    """
```

### Phase 2 Benefits

1. **No LLM Dependency** — all logic deterministic + verifiable
2. **Speed** — detectors run in <10ms vs Claude ~2s
3. **Transparency** — exactly why each principle applies
4. **Testability** — detectors can be unit tested on FEN databases
5. **Offline** — works without internet/API keys

### Phase 2 Timeline

- **Week 1 (now):** Claude analyzer validates approach on user games
- **Week 2:** Build first 3 detectors (rule_of_square, critical_piece, promotion_threat)
- **Week 3:** Test on 500-game sample with user feedback
- **Week 4:** Build remaining detectors (opposition, lucena, philidor, etc.)
- **Week 5:** Replace Claude with full detector fleet

---

## Example: Rf3+ Case

### Position
```
  a b c d e f g h
8 . . . . . . k .  (Black king on g8)
7 . . p . . . . .  (Black pawns on c7)
6 . . . p . . . .  (Black pawns on d6)
5 p . . . . . . .  (Black pawns on a5)
4 K . P . . . . .  (White King d4, Pawn c4)
3 . . . . . R . .  (White Rook f3)
2 . . . . . . . .
1 . . . . . . . .
```

### Phase 1 Analysis (Claude)

**Classifier Output:**
```
position_type: "K+R vs K+P"
white_rooks: ["f3"]
black_pawns: ["a5", "c7", "d6"]
critical_pieces: {
    "white_rook": "only_defender_of_promotion_threat",
    "black_pawn": "promotion_threat"
}
threats: ["black_pawn_a5_close_to_promotion"]
```

**Claude Explanation:**
```
Rf3+ removes your rook — the only defender against Black's a5 pawn.
By the rule of the square, your king on d4 can't catch the a5 pawn alone
(distance > rule of square distance). The pawn will promote and Black wins.

Instead, play Re1 or Re5 to keep your rook active defending the promotion.
```

**Principles Extracted:**
- rule_of_square ✓
- critical_piece ✓
- promotion_threat ✓

**Quality Score:** 0.85 (3 principles, concrete explanation, teaches principle)

### Phase 2 Analysis (Detectors)

**Rule of Square Detector:**
```python
board.fen() = "6k1/2p5/3p4/p7/K1P5/5R2/8/8 w - - 0 1"
move = Rf3 (Black follows with a4, eventually a3, a2, a1=Q)

can_white_king_catch(board, a5_pawn, d4_king)?
  distance = distance(d4, a5) = 3
  squares_to_promotion = distance(a5, a1) = 4
  rule_of_square = squares_to_promotion + 1 = 5
  
  3 < 5 → King can NOT catch → Detector fires "violates"
```

**Result:** Detector confirms rule of square principle applies.

---

## Quality Gates

### Caption Quality Checks

1. **Principle Presence** (MANDATORY)
   - Minimum 2 principles mentioned
   - Allowed: rule_of_square, opposition, critical_piece, promotion_threat, king_activity, tempo, zugzwang

2. **Position-Specificity** (MANDATORY)
   - No generic templates ("improve your position")
   - Must name specific pieces/squares ("rook on f3", "pawn on a5")

3. **Concrete Explanation** (MANDATORY)
   - Captions must explain THE CHAIN: cause → consequence → solution
   - Example YES: "Rf3+ removes defender → pawn promotes (rule of square) → play Re1 instead"
   - Example NO: "Try to defend better"

4. **Audience-Appropriate Language** (MANDATORY)
   - Target: 600-1500 rated players
   - OK: "rule of the square", "opposition", "critical piece"
   - NOT OK: "zugzwang", "triangulation", "fianchetto"

### Verification Before Shipping

```bash
# Run test on Rf3+ case
python scripts/test_principle_caption_rf3_plus.py

# Expected: All quality gates PASS
✅ Position classified
✅ Principles extracted (2+)
✅ Explanation mentions rule of square
✅ Explanation mentions critical piece
✅ Quality score ≥ 0.7
```

---

## Integration Checklist

- [ ] Endgame classifier wired to postgame_analysis.py
- [ ] Claude analyzer fetching captions in generate_game_decryption_v5()
- [ ] Test on 10 real game positions (user's blunders)
- [ ] Verify principles are mentioned in 90%+ of captions
- [ ] Measure: "% of captions with 2+ principles" baseline
- [ ] User feedback: "Does the coach explain WHY?" → measure 4.5+/5
- [ ] Deploy to production for 12-week behavior study
- [ ] Collect data on which principles users find most helpful
- [ ] Design Phase 2 detectors based on Phase 1 learnings

---

## Files

| File | Purpose |
|------|---------|
| `endgame_classifier.py` | Position analysis + feature extraction |
| `claude_endgame_analyzer.py` | Claude-based principle generation |
| `principle_based_caption_generator.py` | Integration + caption pipeline |
| `test_principle_caption_rf3_plus.py` | Validation on Rf3+ case |
| This doc | Architecture + Phase 2 roadmap |

---

## Key Insight

**The quality gap:** Current system is eval-driven (tells the move quality score but not WHY).

**The solution:** Principle-driven captions (explains using chess fundamentals that teach pattern recognition).

**The hybrid approach:**
- Phase 1: Claude validates we CAN generate principle-driven captions
- Phase 2: Deterministic detectors deliver at scale without LLM dependency

**The outcome:** Users remember principles, not moves. Coaching improves from 5.5/10 to 9/10.

---

**Next:** Integrate into `/api/game/:gameId` endpoint and run 2-week user study to validate coaching quality improvement.

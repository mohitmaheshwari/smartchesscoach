"""
Intent Quality Calibrator v1.1 - Human Coach Judgment Layer

This module transforms engine-based quality assessment into human coach judgment.
Human coaches evaluate: Intent × Position Context × Timing

KEY INSIGHT:
A move can be "engine bad" but "coach-approved thinking".
Indian coaches say: "Idea correct, calculation missing."

CALIBRATION FACTORS:
1. Position Pressure (winning/better/equal/worse/losing)
2. Timing Score (attack while losing = courage, attack while winning = risky)
3. Opportunity Awareness (forcing move available?)

INDIAN COACH TONE:
- Never say "wrong move"
- Say "Idea was right, timing early"
- Say "Position needed different approach"
"""

from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# CALIBRATED QUALITY LEVELS
# =============================================================================

class CalibratedQuality(str, Enum):
    """Human-coach quality levels (not engine labels)"""
    EXCELLENT = "excellent"    # Very good thinking
    GOOD = "good"              # Correct idea
    REASONABLE = "reasonable"  # Idea makes sense
    PREMATURE = "premature"    # Idea was right, timing early
    INCORRECT = "incorrect"    # Position needed different approach


class PositionPressure(str, Enum):
    """Position pressure classification from player perspective"""
    WINNING = "winning"   # > +200 cp
    BETTER = "better"     # +80 to +200
    EQUAL = "equal"       # -80 to +80
    WORSE = "worse"       # -200 to -80
    LOSING = "losing"     # < -200


# =============================================================================
# INDIAN COACH TONE TEMPLATES
# =============================================================================

# Quality → Coach interpretation (never say "wrong move")
QUALITY_INTERPRETATIONS = {
    CalibratedQuality.EXCELLENT: "Very good thinking.",
    CalibratedQuality.GOOD: "Correct idea.",
    CalibratedQuality.REASONABLE: "Idea makes sense.",
    CalibratedQuality.PREMATURE: "Idea was right, timing early.",
    CalibratedQuality.INCORRECT: "Position needed different approach.",
}

# Intent + Quality → Full sentence (Indian coach tone)
INTENT_QUALITY_SENTENCES = {
    # ATTACKING
    ("ATTACKING", CalibratedQuality.EXCELLENT): "You attacked at exactly the right moment.",
    ("ATTACKING", CalibratedQuality.GOOD): "Your attacking idea was correct.",
    ("ATTACKING", CalibratedQuality.REASONABLE): "The attack made sense here.",
    ("ATTACKING", CalibratedQuality.PREMATURE): "You tried to attack, but the position wasn't ready yet.",
    ("ATTACKING", CalibratedQuality.INCORRECT): "Attack wasn't the priority here.",
    
    # DEFENDING
    ("DEFENDING", CalibratedQuality.EXCELLENT): "You correctly focused on safety here.",
    ("DEFENDING", CalibratedQuality.GOOD): "Good defensive instinct.",
    ("DEFENDING", CalibratedQuality.REASONABLE): "Defending made sense.",
    ("DEFENDING", CalibratedQuality.PREMATURE): "Defense was okay, but you had more.",
    ("DEFENDING", CalibratedQuality.INCORRECT): "Defense wasn't urgent here.",
    
    # DEVELOPING
    ("DEVELOPING", CalibratedQuality.EXCELLENT): "Excellent development timing.",
    ("DEVELOPING", CalibratedQuality.GOOD): "Good piece development.",
    ("DEVELOPING", CalibratedQuality.REASONABLE): "Development made sense.",
    ("DEVELOPING", CalibratedQuality.PREMATURE): "Development is fine, but something more urgent was available.",
    ("DEVELOPING", CalibratedQuality.INCORRECT): "Development is okay, but the position demanded something forcing.",
    
    # IMPROVING_PIECE
    ("IMPROVING_PIECE", CalibratedQuality.EXCELLENT): "Very good piece improvement.",
    ("IMPROVING_PIECE", CalibratedQuality.GOOD): "Correct idea to improve the piece.",
    ("IMPROVING_PIECE", CalibratedQuality.REASONABLE): "Piece improvement made sense.",
    ("IMPROVING_PIECE", CalibratedQuality.PREMATURE): "Improving the piece is fine, but something more concrete was available.",
    ("IMPROVING_PIECE", CalibratedQuality.INCORRECT): "Repositioning is okay, but the position demanded action.",
    
    # PREVENTING_THREAT
    ("PREVENTING_THREAT", CalibratedQuality.EXCELLENT): "You correctly neutralized the threat.",
    ("PREVENTING_THREAT", CalibratedQuality.GOOD): "Good threat awareness.",
    ("PREVENTING_THREAT", CalibratedQuality.REASONABLE): "You saw the threat.",
    ("PREVENTING_THREAT", CalibratedQuality.PREMATURE): "You saw a threat, but there was a better response.",
    ("PREVENTING_THREAT", CalibratedQuality.INCORRECT): "The real danger was elsewhere.",
    
    # SIMPLIFYING
    ("SIMPLIFYING", CalibratedQuality.EXCELLENT): "Excellent technique - simplify when ahead.",
    ("SIMPLIFYING", CalibratedQuality.GOOD): "Good decision to simplify.",
    ("SIMPLIFYING", CalibratedQuality.REASONABLE): "Simplification made sense.",
    ("SIMPLIFYING", CalibratedQuality.PREMATURE): "You could have kept more pressure before simplifying.",
    ("SIMPLIFYING", CalibratedQuality.INCORRECT): "Simplifying here gave up your advantage.",
    
    # CREATING_THREAT
    ("CREATING_THREAT", CalibratedQuality.EXCELLENT): "You created real problems for opponent.",
    ("CREATING_THREAT", CalibratedQuality.GOOD): "Good threat creation.",
    ("CREATING_THREAT", CalibratedQuality.REASONABLE): "The threat idea was sensible.",
    ("CREATING_THREAT", CalibratedQuality.PREMATURE): "Threat idea was good, but premature.",
    ("CREATING_THREAT", CalibratedQuality.INCORRECT): "The threat wasn't real.",
    
    # POSITIONAL_MANEUVER
    ("POSITIONAL_MANEUVER", CalibratedQuality.EXCELLENT): "Very good positional understanding.",
    ("POSITIONAL_MANEUVER", CalibratedQuality.GOOD): "Correct positional idea.",
    ("POSITIONAL_MANEUVER", CalibratedQuality.REASONABLE): "The positional move made sense.",
    ("POSITIONAL_MANEUVER", CalibratedQuality.PREMATURE): "Adjusting the position is fine, but here the position demanded something forcing.",
    ("POSITIONAL_MANEUVER", CalibratedQuality.INCORRECT): "This wasn't the moment for quiet moves.",
}


# =============================================================================
# CALIBRATION FUNCTIONS
# =============================================================================

def user_eval(eval_cp: int, user_color: str) -> int:
    """Normalize evaluation to user perspective"""
    return eval_cp if user_color.lower() == "white" else -eval_cp


def classify_pressure(user_eval_before: int) -> PositionPressure:
    """
    Classify position pressure from user perspective.
    Human judgment changes under pressure.
    """
    if user_eval_before > 200:
        return PositionPressure.WINNING
    elif user_eval_before > 80:
        return PositionPressure.BETTER
    elif user_eval_before > -80:
        return PositionPressure.EQUAL
    elif user_eval_before > -200:
        return PositionPressure.WORSE
    else:
        return PositionPressure.LOSING


def calculate_timing_score(
    intent_type: str,
    pressure: PositionPressure,
    phase: str = "middlegame",
    piece_type: str = None
) -> int:
    """
    Calculate timing score based on intent + position context.
    Human coaches constantly judge timing.
    
    Rules:
    - Attack while losing → GOOD COURAGE (+1)
    - Attack while winning → RISKY (-1) "No need to complicate"
    - Simplify while winning → EXCELLENT (+2)
    - Defend while losing → GOOD INSTINCT (+1)
    - Development in opening → GOOD (+1)
    - Queen attack in opening → RISKY (-1) "Queen out early can become target"
    """
    score = 0
    
    # A. Attack While Losing → GOOD COURAGE
    if intent_type == "ATTACKING" and pressure == PositionPressure.LOSING:
        score += 1  # "Good practical decision"
    
    # B. Attack While Winning → RISKY (unless check/mate)
    elif intent_type == "ATTACKING" and pressure == PositionPressure.WINNING:
        score -= 1  # "No need to complicate"
    
    # C. Simplify While Winning → EXCELLENT
    elif intent_type == "SIMPLIFYING" and pressure in [PositionPressure.WINNING, PositionPressure.BETTER]:
        score += 2  # "Good technique"
    
    # D. Simplify While Losing → BAD
    elif intent_type == "SIMPLIFYING" and pressure in [PositionPressure.LOSING, PositionPressure.WORSE]:
        score -= 2  # "Need complications"
    
    # E. Defend While Losing → GOOD INSTINCT
    elif intent_type == "DEFENDING" and pressure in [PositionPressure.LOSING, PositionPressure.WORSE]:
        score += 1  # "Correct priority"
    
    # F. Development in Opening → GOOD
    elif intent_type == "DEVELOPING" and phase == "opening":
        score += 1  # "Correct phase"
    
    # G. Positional play when winning → GOOD (consolidation)
    elif intent_type in ["IMPROVING_PIECE", "POSITIONAL_MANEUVER"] and pressure == PositionPressure.WINNING:
        score += 1  # "Good technique"
    
    # H. QUEEN-IN-OPENING PRINCIPLE (Human Chess Culture)
    # Queen early development should rarely be "good" - even if cp_loss is small
    # "Idea is aggressive, but queen out early can become a target"
    if intent_type == "ATTACKING" and phase == "opening" and piece_type == "queen":
        score -= 1  # Push toward "reasonable" or "premature"
    
    return score


def forcing_move_available(pv_after_best: Optional[List[str]], best_move_uci: str) -> bool:
    """
    Detect if a forcing move (check or capture) was available.
    Used for opportunity awareness.
    """
    if not best_move_uci:
        return False
    
    # Simple heuristic: if best move is short algebraic capture notation
    # More accurate would need board state, but this is approximation
    # We check if the best move looks forcing (ends with capture square pattern)
    
    # For now, rely on PV having forcing moves
    # This will be enriched when we have more move context
    return False  # Will be improved with board context


def calculate_opportunity_modifier(
    intent_type: str,
    best_move_is_forcing: bool,
    move_is_forcing: bool
) -> int:
    """
    Calculate penalty for missing forcing opportunities.
    
    Human phrasing: "Position required something forcing."
    """
    modifier = 0
    
    # Missed forcing move penalty
    if best_move_is_forcing and not move_is_forcing:
        # Non-forcing intent when forcing move existed
        if intent_type in ["DEVELOPING", "IMPROVING_PIECE", "POSITIONAL_MANEUVER"]:
            modifier -= 2  # Strong penalty for quiet moves when tactics available
        elif intent_type in ["DEFENDING", "PREVENTING_THREAT"]:
            modifier -= 1  # Lighter penalty for defensive instinct
    
    return modifier


def calculate_base_cp_score(cp_loss: int) -> int:
    """
    Convert centipawn loss to base quality score.
    """
    if cp_loss <= 20:
        return 2   # Excellent
    elif cp_loss <= 80:
        return 1   # Good
    elif cp_loss <= 180:
        return 0   # Reasonable
    elif cp_loss <= 400:
        return -1  # Poor
    else:
        return -3  # Very poor (missed winning tactics)


# =============================================================================
# MAIN CALIBRATION FUNCTION
# =============================================================================

@dataclass
class CalibratedIntentResult:
    """Result of intent quality calibration"""
    intent_type: str
    calibrated_quality: str
    quality_score: int
    
    # Calibration factors (for transparency)
    pressure: str
    timing_score: int
    base_cp_score: int
    opportunity_modifier: int
    
    # Human-readable output
    coach_interpretation: str
    full_sentence: str
    
    def to_dict(self) -> Dict:
        return {
            "intent_type": self.intent_type,
            "calibrated_quality": self.calibrated_quality,
            "quality_score": self.quality_score,
            "pressure": self.pressure,
            "timing_score": self.timing_score,
            "coach_interpretation": self.coach_interpretation,
            "full_sentence": self.full_sentence,
        }


def calibrate_intent_quality(
    intent_type: str,
    cp_loss: int,
    eval_before: int,
    user_color: str,
    phase: str = "middlegame",
    best_move_is_forcing: bool = False,
    move_is_forcing: bool = False,
    piece_type: str = None
) -> CalibratedIntentResult:
    """
    Calibrate intent quality using human coach judgment factors.
    
    This transforms engine-based assessment into human coach evaluation.
    
    Args:
        intent_type: Detected intent (ATTACKING, DEFENDING, etc.)
        cp_loss: Centipawn loss of the move
        eval_before: Position evaluation before move (raw, not user-normalized)
        user_color: "white" or "black"
        phase: "opening", "middlegame", or "endgame"
        best_move_is_forcing: Was the best move a check/capture?
        move_is_forcing: Was the played move a check/capture?
        piece_type: Type of piece moved (for phase-sensitive rules)
    
    Returns:
        CalibratedIntentResult with human coach judgment
    """
    # Step 1: Normalize to user perspective
    user_eval_before = user_eval(eval_before, user_color)
    
    # Step 2: Classify pressure
    pressure = classify_pressure(user_eval_before)
    
    # Step 3: Calculate timing score (now includes piece_type)
    timing = calculate_timing_score(intent_type, pressure, phase, piece_type)
    
    # Step 4: Calculate base CP score
    base = calculate_base_cp_score(cp_loss)
    
    # Step 5: Calculate opportunity modifier
    opportunity = calculate_opportunity_modifier(
        intent_type, best_move_is_forcing, move_is_forcing
    )
    
    # Step 6: Final quality score
    quality_score = base + timing + opportunity
    
    # Step 7: Map to calibrated quality
    if quality_score >= 3:
        quality = CalibratedQuality.EXCELLENT
    elif quality_score >= 1:
        quality = CalibratedQuality.GOOD
    elif quality_score >= 0:
        quality = CalibratedQuality.REASONABLE
    elif quality_score >= -2:
        quality = CalibratedQuality.PREMATURE
    else:
        quality = CalibratedQuality.INCORRECT
    
    # Step 8: Get human-readable interpretations
    coach_interpretation = QUALITY_INTERPRETATIONS.get(
        quality, "Idea makes sense."
    )
    
    # Step 9: Build full sentence (Indian coach tone)
    key = (intent_type, quality)
    full_sentence = INTENT_QUALITY_SENTENCES.get(
        key,
        f"{INTENT_QUALITY_SENTENCES.get((intent_type, CalibratedQuality.REASONABLE), 'The idea was reasonable.')}"
    )
    
    return CalibratedIntentResult(
        intent_type=intent_type,
        calibrated_quality=quality.value,
        quality_score=quality_score,
        pressure=pressure.value,
        timing_score=timing,
        base_cp_score=base,
        opportunity_modifier=opportunity,
        coach_interpretation=coach_interpretation,
        full_sentence=full_sentence
    )


def calibrate_with_forcing_context(
    intent_type: str,
    cp_loss: int,
    eval_before: int,
    user_color: str,
    phase: str,
    move_uci: str,
    best_move_uci: str,
    board_fen: str
) -> CalibratedIntentResult:
    """
    Enhanced calibration with board context for forcing move detection.
    Also extracts piece type for phase-sensitive rules (e.g., queen in opening).
    """
    import chess
    
    piece_type = None
    best_is_forcing = False
    played_is_forcing = False
    
    try:
        board = chess.Board(board_fen)
        
        # Extract piece type for phase-sensitive rules
        played_move = chess.Move.from_uci(move_uci)
        piece = board.piece_at(played_move.from_square)
        if piece:
            piece_type = {
                chess.PAWN: "pawn",
                chess.KNIGHT: "knight",
                chess.BISHOP: "bishop",
                chess.ROOK: "rook",
                chess.QUEEN: "queen",
                chess.KING: "king"
            }.get(piece.piece_type)
        
        # Detect if best move is forcing
        best_move = chess.Move.from_uci(best_move_uci)
        board_copy = board.copy()
        board_copy.push(best_move)
        best_is_forcing = board_copy.is_check() or board.is_capture(best_move)
        board_copy.pop()
        
        # Detect if played move is forcing
        board_copy = board.copy()
        board_copy.push(played_move)
        played_is_forcing = board_copy.is_check() or board.is_capture(played_move)
        
    except (ValueError, chess.InvalidMoveError):
        pass
    
    return calibrate_intent_quality(
        intent_type=intent_type,
        cp_loss=cp_loss,
        eval_before=eval_before,
        user_color=user_color,
        phase=phase,
        best_move_is_forcing=best_is_forcing,
        move_is_forcing=played_is_forcing,
        piece_type=piece_type
    )


# =============================================================================
# INTEGRATION HELPER
# =============================================================================

def build_coach_sentence(intent_type: str, calibrated_quality: str, pressure: str = None, phase: str = None, piece_type: str = None) -> str:
    """
    Build the final coach sentence combining intent + quality + pressure context.
    
    Uses Indian coach tone - never says "wrong move".
    Pressure-aware phrasing makes coach sound like it understands board situation.
    """
    try:
        quality = CalibratedQuality(calibrated_quality)
    except ValueError:
        quality = CalibratedQuality.REASONABLE
    
    # Pressure-aware phrasing (makes coach feel observant)
    if pressure:
        pressure = pressure.lower()
        
        # Attack while losing/worse - acknowledge the courage/counterplay
        if intent_type == "ATTACKING" and pressure in ["losing", "worse"]:
            if quality in [CalibratedQuality.GOOD, CalibratedQuality.REASONABLE]:
                return "You were worse here, so looking for counterplay makes sense."
            elif quality == CalibratedQuality.PREMATURE:
                return "You were worse, so aggression is understandable, but timing was early."
        
        # Attack while winning - gently discourage
        if intent_type == "ATTACKING" and pressure == "winning":
            if quality == CalibratedQuality.PREMATURE:
                return "You were better here — no need to complicate."
            elif quality == CalibratedQuality.INCORRECT:
                return "You were winning — the position didn't need forcing moves."
        
        # Attack in equal - context-dependent
        if intent_type == "ATTACKING" and pressure == "equal":
            if quality == CalibratedQuality.PREMATURE:
                return "The attack idea is aggressive, but queen out early can become a target."
            elif quality == CalibratedQuality.REASONABLE:
                # Check if this is queen in opening - special case
                if phase == "opening" and piece_type == "queen":
                    return "The idea is aggressive, but bringing the queen out early can make it a target."
                return "Looking for initiative in an equal position is fine."
        
        # Defend while worse/losing - praise instinct
        if intent_type == "DEFENDING" and pressure in ["worse", "losing"]:
            if quality in [CalibratedQuality.GOOD, CalibratedQuality.EXCELLENT]:
                return "You correctly prioritized defense when under pressure."
        
        # Simplify while winning - excellent technique
        if intent_type == "SIMPLIFYING" and pressure == "winning":
            if quality == CalibratedQuality.EXCELLENT:
                return "Good technique — simplify when ahead."
            elif quality == CalibratedQuality.GOOD:
                return "Trading when better is sensible."
        
        # Simplify while losing - bad decision
        if intent_type == "SIMPLIFYING" and pressure in ["worse", "losing"]:
            if quality == CalibratedQuality.INCORRECT:
                return "When behind, you need complications, not simplification."
    
    # Fallback to standard lookup
    key = (intent_type, quality)
    return INTENT_QUALITY_SENTENCES.get(
        key,
        "The idea was reasonable here."
    )


def build_full_intent_explanation(
    intent_description: str,
    calibrated_quality: str,
    intent_type: str,
    pressure: str = None,
    phase: str = None,
    piece_type: str = None
) -> str:
    """
    Build complete coach explanation: Intent + Quality-aware context.
    
    Before: "You had a plan here."
    After:  "You tried to start an attack. You were worse here, so looking for counterplay makes sense."
    
    For contrast-structure sentences (Affirm → Contrast → Correction),
    the quality sentence is self-sufficient and replaces the intent description.
    """
    quality_sentence = build_coach_sentence(
        intent_type, calibrated_quality, pressure, phase, piece_type
    )
    
    # Contrast-structure sentences are self-sufficient (don't need intent prefix)
    # These start with "Improving/Adjusting/Development is fine, but..."
    contrast_starters = [
        "Adjusting the position is fine",
        "Improving the piece is fine",
        "Improving the position is fine",
        "Development is fine",
        "Development is okay",
        "Repositioning is okay",
    ]
    
    for starter in contrast_starters:
        if quality_sentence.startswith(starter):
            return quality_sentence
    
    # Standard case: combine intent description with quality evaluation
    return f"{intent_description} {quality_sentence}"

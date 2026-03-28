"""
Chess Brain Enums
=================

All enumeration types for the deterministic coaching engine.
These define the vocabulary of the coaching system.
"""

from enum import Enum, auto


class TeachingMode(str, Enum):
    """
    The 7 Teaching Modes - determines HOW the coach responds.
    Each interaction falls into exactly ONE mode.
    """
    # Mode 1: User made a significant error - explain what went wrong
    IMMEDIATE_MISTAKE_CORRECTION = "immediate_mistake_correction"
    
    # Mode 2: User missed a tactic - teach the pattern
    TACTICAL_PATTERN_TEACHING = "tactical_pattern_teaching"
    
    # Mode 3: Position has strategic lesson - teach the concept
    STRATEGIC_CONCEPT_TEACHING = "strategic_concept_teaching"
    
    # Mode 4: User played a good/great move - reinforce
    POSITIVE_REINFORCEMENT = "positive_reinforcement"
    
    # Mode 5: User fixed a previously recurring mistake - celebrate
    HABIT_BREAKTHROUGH = "habit_breakthrough"
    
    # Mode 6: User in opening territory - guide repertoire
    OPENING_GUIDANCE = "opening_guidance"
    
    # Mode 7: Endgame position - teach specific technique
    ENDGAME_TECHNIQUE = "endgame_technique"


class GamePhase(str, Enum):
    """
    Game phases for phase-specific coaching.
    Based on material-weighted calculation.
    """
    OPENING = "opening"              # Phase 0-15%
    EARLY_MIDDLEGAME = "early_middlegame"  # Phase 15-30%
    MIDDLEGAME = "middlegame"        # Phase 30-50%
    LATE_MIDDLEGAME = "late_middlegame"    # Phase 50-65%
    EARLY_ENDGAME = "early_endgame"  # Phase 65-80%
    ENDGAME = "endgame"              # Phase 80-95%
    DEEP_ENDGAME = "deep_endgame"    # Phase 95-100%


class MistakeCategory(str, Enum):
    """
    High-level mistake categories for fingerprinting.
    Maps to specific patterns below.
    """
    TACTICAL = "tactical"           # Missed tactics, calculation errors
    STRATEGIC = "strategic"         # Positional errors, plan issues
    PHASE_SPECIFIC = "phase_specific"  # Opening/endgame specific errors
    BEHAVIORAL = "behavioral"       # Time, tilt, impulse-related


class TacticalPattern(str, Enum):
    """
    Specific tactical patterns for detection and teaching.
    Each has an associated detector and explanation template.
    """
    # Missed offensive tactics
    MISSED_FORK = "missed_fork"
    MISSED_PIN = "missed_pin"
    MISSED_SKEWER = "missed_skewer"
    MISSED_DISCOVERY = "missed_discovery"
    MISSED_BACK_RANK = "missed_back_rank"
    MISSED_MATE = "missed_mate"
    MISSED_REMOVAL = "missed_removal"  # Removal of the guard
    MISSED_DEFLECTION = "missed_deflection"
    MISSED_DECOY = "missed_decoy"
    MISSED_OVERLOAD = "missed_overload"
    
    # Defensive failures
    HANGING_PIECE = "hanging_piece"
    TRAPPED_PIECE = "trapped_piece"
    UNDEFENDED_PIECE = "undefended_piece"
    WALKED_INTO_FORK = "walked_into_fork"
    WALKED_INTO_PIN = "walked_into_pin"
    
    # Calculation errors
    MISCALCULATION = "miscalculation"
    HORIZON_EFFECT = "horizon_effect"  # Saw tactic but missed response


class StrategicConcept(str, Enum):
    """
    Strategic concepts for position evaluation and teaching.
    Each has associated detectors and explanations.
    """
    # Pawn structure
    ISOLATED_PAWN = "isolated_pawn"
    DOUBLED_PAWNS = "doubled_pawns"
    BACKWARD_PAWN = "backward_pawn"
    PASSED_PAWN = "passed_pawn"
    PAWN_MAJORITY = "pawn_majority"
    PAWN_CHAIN = "pawn_chain"
    
    # Piece placement
    BAD_BISHOP = "bad_bishop"
    GOOD_BISHOP = "good_bishop"
    KNIGHT_OUTPOST = "knight_outpost"
    ROOK_ACTIVITY = "rook_activity"
    PIECE_COORDINATION = "piece_coordination"
    
    # Positional themes
    KING_SAFETY = "king_safety"
    SPACE_ADVANTAGE = "space_advantage"
    WEAK_SQUARES = "weak_squares"
    OPEN_FILE = "open_file"
    SEVENTH_RANK = "seventh_rank"
    
    # Planning
    PAWN_BREAK = "pawn_break"
    MINORITY_ATTACK = "minority_attack"
    PROPHYLAXIS = "prophylaxis"


class BehavioralPattern(str, Enum):
    """
    Behavioral/psychological patterns for meta-detection.
    These influence coaching tone and advice.
    """
    # Time-related
    TIME_TROUBLE = "time_trouble"
    IMPULSE_MOVE = "impulse_move"  # < 2 seconds
    OVERTHINKING = "overthinking"  # > 2 minutes
    
    # Emotional
    TILT_DETECTED = "tilt_detected"
    POST_BLUNDER_SPIRAL = "post_blunder_spiral"
    OVERCONFIDENCE = "overconfidence"
    
    # Cognitive
    TUNNEL_VISION = "tunnel_vision"  # Same piece/area focus
    CALCULATION_FATIGUE = "calculation_fatigue"


class LessonPriority(str, Enum):
    """
    Priority levels for lesson selection.
    Used in scoring formula.
    """
    CRITICAL = "critical"      # Score multiplier: 2.0
    HIGH = "high"              # Score multiplier: 1.5
    NORMAL = "normal"          # Score multiplier: 1.0
    LOW = "low"                # Score multiplier: 0.5
    OPTIONAL = "optional"      # Score multiplier: 0.25


class MoveQuality(str, Enum):
    """
    Move quality classification based on eval change.
    """
    BRILLIANT = "brilliant"     # Significantly improved + only winning move
    EXCELLENT = "excellent"     # Best or near-best move
    GOOD = "good"               # Reasonable, within 30cp of best
    INACCURACY = "inaccuracy"   # Lost 30-100cp
    MISTAKE = "mistake"         # Lost 100-250cp
    BLUNDER = "blunder"         # Lost >250cp or critical advantage


class ExplanationType(str, Enum):
    """
    Types of explanations for template selection.
    """
    WHY_BAD = "why_bad"           # Explain what went wrong
    WHY_GOOD = "why_good"         # Explain what was right
    WHAT_INSTEAD = "what_instead" # Show the better move
    CONCEPT = "concept"          # Teach the underlying principle
    PATTERN = "pattern"          # Show the tactical pattern
    MEMORY = "memory"            # Reference past occurrence
    REINFORCEMENT = "reinforcement"  # Celebrate improvement

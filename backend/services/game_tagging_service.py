"""
Game Tagging Service
====================

Comprehensive tagging system for game analysis.
Tags each critical moment with patterns that help the coach understand:
1. What kind of mistake was made
2. What tactical/strategic pattern was involved
3. What theory could have helped

Tags are rating-appropriate - different tags for different skill levels.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================
# RATING BANDS FOR TAG FILTERING
# ============================================
class RatingLevel(Enum):
    BEGINNER = "beginner"      # Below 1000
    INTERMEDIATE = "intermediate"  # 1000-1400
    ADVANCED = "advanced"      # 1400-1800
    EXPERT = "expert"          # Above 1800


def get_rating_level(rating: int) -> RatingLevel:
    """Get rating level for tag filtering"""
    if rating < 1000:
        return RatingLevel.BEGINNER
    elif rating < 1400:
        return RatingLevel.INTERMEDIATE
    elif rating < 1800:
        return RatingLevel.ADVANCED
    else:
        return RatingLevel.EXPERT


# ============================================
# COMPREHENSIVE TAG DEFINITIONS
# ============================================
GAME_TAGS = {
    # === ONE-MOVE TACTICAL OVERSIGHTS ===
    "one_move_blunder": {
        "label": "One-Move Blunder",
        "description": "Simple oversight - the threat was obvious",
        "category": "tactical",
        "min_rating": 0,
        "max_rating": 2500,
        "cp_threshold": 200,  # Minimum CP loss to qualify
        "detection_hint": "Opponent's response was a simple capture or check",
    },
    "hung_piece": {
        "label": "Hung Piece",
        "description": "Left a piece undefended",
        "category": "tactical",
        "min_rating": 0,
        "max_rating": 1800,
        "cp_threshold": 100,
        "detection_hint": "Your piece was captured with no recapture",
    },
    "walked_into_check": {
        "label": "Walked Into Check",
        "description": "Moved king or piece into check",
        "category": "tactical",
        "min_rating": 0,
        "max_rating": 1200,
        "cp_threshold": 50,
    },
    
    # === TACTICAL PATTERNS MISSED ===
    "missed_fork": {
        "label": "Missed Fork",
        "description": "Didn't see the double attack opportunity",
        "category": "tactical",
        "min_rating": 0,
        "max_rating": 2000,
        "cp_threshold": 150,
        "pattern_type": "fork",
    },
    "captured_in_fork": {
        "label": "Fell For Fork",
        "description": "Opponent forked your pieces",
        "category": "tactical",
        "min_rating": 0,
        "max_rating": 2000,
        "cp_threshold": 200,
        "pattern_type": "fork",
    },
    "missed_pin": {
        "label": "Missed Pin",
        "description": "Didn't exploit the pin opportunity",
        "category": "tactical",
        "min_rating": 800,
        "max_rating": 2200,
        "cp_threshold": 100,
        "pattern_type": "pin",
    },
    "pinned_piece_moved": {
        "label": "Moved Pinned Piece",
        "description": "Moved a piece that was pinned",
        "category": "tactical",
        "min_rating": 0,
        "max_rating": 1600,
        "cp_threshold": 200,
        "pattern_type": "pin",
    },
    "missed_skewer": {
        "label": "Missed Skewer",
        "description": "Didn't see the skewer opportunity",
        "category": "tactical",
        "min_rating": 1000,
        "max_rating": 2200,
        "cp_threshold": 150,
        "pattern_type": "skewer",
    },
    "missed_discovery": {
        "label": "Missed Discovered Attack",
        "description": "Didn't see the discovered attack",
        "category": "tactical",
        "min_rating": 1000,
        "max_rating": 2200,
        "cp_threshold": 150,
        "pattern_type": "discovery",
    },
    
    # === BACK RANK / KING SAFETY ===
    "back_rank_weakness": {
        "label": "Back Rank Weakness",
        "description": "King trapped on back rank",
        "category": "tactical",
        "min_rating": 800,
        "max_rating": 2000,
        "cp_threshold": 200,
        "pattern_type": "back_rank",
    },
    "missed_back_rank_mate": {
        "label": "Missed Back Rank Mate",
        "description": "Had back rank mate but missed it",
        "category": "tactical",
        "min_rating": 800,
        "max_rating": 2000,
        "cp_threshold": 500,
        "pattern_type": "back_rank",
    },
    "king_exposed": {
        "label": "King Exposed",
        "description": "Weakened king position unnecessarily",
        "category": "positional",
        "min_rating": 0,
        "max_rating": 2200,
        "cp_threshold": 100,
    },
    
    # === CALCULATION DEPTH ===
    "didnt_see_far_enough": {
        "label": "Calculation Depth Issue",
        "description": "Stopped calculating too early",
        "category": "calculation",
        "min_rating": 1000,
        "max_rating": 2500,
        "cp_threshold": 150,
        "detection_hint": "Best move required 3+ move calculation",
    },
    "missed_zwischenzug": {
        "label": "Missed In-Between Move",
        "description": "Didn't see the intermezzo",
        "category": "calculation",
        "min_rating": 1200,
        "max_rating": 2500,
        "cp_threshold": 150,
    },
    "premature_capture": {
        "label": "Premature Capture",
        "description": "Captured too early, missing better sequence",
        "category": "calculation",
        "min_rating": 1000,
        "max_rating": 2200,
        "cp_threshold": 100,
    },
    
    # === POSITIONAL / STRATEGIC ===
    "weakened_pawn_structure": {
        "label": "Weakened Pawn Structure",
        "description": "Created unnecessary pawn weaknesses",
        "category": "positional",
        "min_rating": 1200,
        "max_rating": 2500,
        "cp_threshold": 50,
    },
    "bad_piece_trade": {
        "label": "Poor Piece Exchange",
        "description": "Traded into a worse position",
        "category": "positional",
        "min_rating": 1000,
        "max_rating": 2200,
        "cp_threshold": 75,
    },
    "passive_move": {
        "label": "Too Passive",
        "description": "Defensive move when attack was needed",
        "category": "positional",
        "min_rating": 1200,
        "max_rating": 2500,
        "cp_threshold": 50,
    },
    "ignored_piece_activity": {
        "label": "Ignored Piece Activity",
        "description": "Piece sitting idle while others worked",
        "category": "positional",
        "min_rating": 1000,
        "max_rating": 2200,
        "cp_threshold": 75,
    },
    
    # === OPENING PHASE ===
    "opening_theory_deviation": {
        "label": "Left Theory Badly",
        "description": "Deviated from opening principles",
        "category": "opening",
        "min_rating": 0,
        "max_rating": 2000,
        "cp_threshold": 50,
        "phase": "opening",
    },
    "early_queen_adventure": {
        "label": "Early Queen Move",
        "description": "Moved queen out too early",
        "category": "opening",
        "min_rating": 0,
        "max_rating": 1400,
        "cp_threshold": 30,
        "phase": "opening",
    },
    "development_neglected": {
        "label": "Development Neglected",
        "description": "Didn't develop pieces properly",
        "category": "opening",
        "min_rating": 0,
        "max_rating": 1600,
        "cp_threshold": 30,
        "phase": "opening",
    },
    "castling_delayed": {
        "label": "Castling Delayed",
        "description": "King stayed in center too long",
        "category": "opening",
        "min_rating": 0,
        "max_rating": 1800,
        "cp_threshold": 50,
        "phase": "opening",
    },
    
    # === MIDDLEGAME ===
    "wrong_plan": {
        "label": "Wrong Plan",
        "description": "Chose incorrect strategic direction",
        "category": "strategic",
        "min_rating": 1400,
        "max_rating": 2500,
        "cp_threshold": 75,
        "phase": "middlegame",
    },
    "missed_breakthrough": {
        "label": "Missed Breakthrough",
        "description": "Had winning attack but didn't execute",
        "category": "strategic",
        "min_rating": 1200,
        "max_rating": 2500,
        "cp_threshold": 150,
        "phase": "middlegame",
    },
    "premature_attack": {
        "label": "Premature Attack",
        "description": "Attacked without sufficient preparation",
        "category": "strategic",
        "min_rating": 1200,
        "max_rating": 2200,
        "cp_threshold": 100,
        "phase": "middlegame",
    },
    
    # === ENDGAME ===
    "endgame_technique_error": {
        "label": "Endgame Technique",
        "description": "Technical mistake in endgame",
        "category": "endgame",
        "min_rating": 1000,
        "max_rating": 2500,
        "cp_threshold": 100,
        "phase": "endgame",
    },
    "king_not_active": {
        "label": "Passive King in Endgame",
        "description": "King should have been more active",
        "category": "endgame",
        "min_rating": 800,
        "max_rating": 2000,
        "cp_threshold": 75,
        "phase": "endgame",
    },
    "wrong_pawn_push": {
        "label": "Wrong Pawn Advance",
        "description": "Pushed wrong pawn in endgame",
        "category": "endgame",
        "min_rating": 1000,
        "max_rating": 2200,
        "cp_threshold": 100,
        "phase": "endgame",
    },
    "missed_opposition": {
        "label": "Missed Opposition",
        "description": "Didn't use king opposition",
        "category": "endgame",
        "min_rating": 1000,
        "max_rating": 2000,
        "cp_threshold": 100,
        "phase": "endgame",
    },
    
    # === TIME PRESSURE ===
    "time_pressure_blunder": {
        "label": "Time Pressure Blunder",
        "description": "Mistake made in time trouble",
        "category": "time_management",
        "min_rating": 0,
        "max_rating": 2500,
        "cp_threshold": 100,
        "requires_time_data": True,
    },
    
    # === ADVANTAGE CONVERSION ===
    "threw_winning_position": {
        "label": "Threw Winning Position",
        "description": "Had winning position but lost it",
        "category": "conversion",
        "min_rating": 0,
        "max_rating": 2500,
        "cp_threshold": 300,
        "detection_hint": "Eval swung from +2 or more to equal/losing",
    },
    "drew_winning_endgame": {
        "label": "Drew Winning Endgame",
        "description": "Should have won but only drew",
        "category": "conversion",
        "min_rating": 1000,
        "max_rating": 2500,
        "cp_threshold": 200,
        "phase": "endgame",
    },
}


# ============================================
# TAG DETECTION FUNCTIONS
# ============================================

@dataclass
class MomentTags:
    """Tags for a critical moment"""
    primary_tag: str
    secondary_tags: List[str]
    theory_links: List[str]
    phase: str  # opening, middlegame, endgame
    severity: str  # blunder, mistake, inaccuracy
    
    def to_dict(self) -> Dict:
        return {
            "primary_tag": self.primary_tag,
            "secondary_tags": self.secondary_tags,
            "theory_links": self.theory_links,
            "phase": self.phase,
            "severity": self.severity,
        }


def get_game_phase(move_number: int, total_moves: int) -> str:
    """Determine game phase from move number"""
    if move_number <= 12:
        return "opening"
    elif move_number >= total_moves - 10 or move_number >= 40:
        return "endgame"
    else:
        return "middlegame"


def get_severity(cp_loss: float) -> str:
    """Determine severity based on centipawn loss"""
    if cp_loss >= 300:
        return "blunder"
    elif cp_loss >= 100:
        return "mistake"
    else:
        return "inaccuracy"


def filter_tags_for_rating(rating: int) -> Dict:
    """Get tags appropriate for player's rating"""
    filtered = {}
    for tag_id, tag_info in GAME_TAGS.items():
        min_r = tag_info.get("min_rating", 0)
        max_r = tag_info.get("max_rating", 3000)
        if min_r <= rating <= max_r:
            filtered[tag_id] = tag_info
    return filtered


def detect_tactical_pattern(
    fen_before: str,
    fen_after: str,
    move_san: str,
    best_move: str,
    cp_loss: float,
    pv_after: List[str] = None
) -> Optional[str]:
    """
    Detect tactical pattern in the position.
    Returns pattern type if found.
    """
    try:
        import chess
        board_before = chess.Board(fen_before)
        board_after = chess.Board(fen_after)
        
        # Check if it's a hanging piece
        # After opponent's best response, did we lose material with no compensation?
        if cp_loss >= 100:
            # Simple check: was a piece captured immediately?
            if pv_after and len(pv_after) >= 1:
                next_move = pv_after[0]
                try:
                    test_board = board_after.copy()
                    move = test_board.parse_san(next_move)
                    if test_board.is_capture(move):
                        # Check if it's an undefended piece
                        # This is likely a hung piece
                        return "hung_piece"
                except:
                    pass
        
        # Check for fork patterns
        if pv_after and len(pv_after) >= 1:
            # If best response attacks two pieces, opponent forked us
            # Simplified detection
            pass
        
        # Check for back rank issues
        if board_before.is_check():
            # If we're in check and king is on back rank
            king_square = board_before.king(board_before.turn)
            if king_square is not None:
                rank = chess.square_rank(king_square)
                if (board_before.turn == chess.WHITE and rank == 0) or \
                   (board_before.turn == chess.BLACK and rank == 7):
                    return "back_rank_weakness"
        
        return None
    except Exception as e:
        logger.error(f"Error detecting tactical pattern: {e}")
        return None


def tag_critical_moment(
    move_number: int,
    move_san: str,
    fen_before: str,
    fen_after: str,
    cp_loss: float,
    best_move: str,
    pv_after: List[str],
    user_rating: int,
    total_moves: int,
    time_remaining: Optional[float] = None,
    eval_before: float = 0,
    eval_after: float = 0
) -> MomentTags:
    """
    Tag a critical moment with appropriate patterns.
    
    Args:
        move_number: Move number in the game
        move_san: The move played in SAN notation
        fen_before: Position before the move
        fen_after: Position after the move
        cp_loss: Centipawn loss from this move
        best_move: Stockfish's best move
        pv_after: Principal variation after the played move
        user_rating: Player's rating for tag filtering
        total_moves: Total moves in game (for phase detection)
        time_remaining: Time remaining when move was made (optional)
        eval_before: Evaluation before move
        eval_after: Evaluation after move
        
    Returns:
        MomentTags with primary tag, secondary tags, and theory links
    """
    # Get phase and severity
    phase = get_game_phase(move_number, total_moves)
    severity = get_severity(abs(cp_loss))
    
    # Get rating-appropriate tags
    filter_tags_for_rating(user_rating)
    
    primary_tag = "unknown"
    secondary_tags = []
    theory_links = []
    
    # === PRIMARY TAG DETECTION ===
    
    # Check for time pressure first (if we have time data)
    if time_remaining is not None and time_remaining < 30 and abs(cp_loss) >= 100:
        primary_tag = "time_pressure_blunder"
    
    # Check for throwing winning position
    elif eval_before >= 200 and eval_after <= 50 and abs(cp_loss) >= 200:
        primary_tag = "threw_winning_position"
    
    # Check for one-move blunder (high CP loss, simple response)
    elif abs(cp_loss) >= 200 and pv_after and len(pv_after) <= 2:
        # Detect specific tactical pattern
        tactical = detect_tactical_pattern(
            fen_before, fen_after, move_san, best_move, cp_loss, pv_after
        )
        if tactical:
            primary_tag = tactical
        else:
            primary_tag = "one_move_blunder"
    
    # Phase-specific tags
    elif phase == "opening":
        if move_number <= 6 and "Q" in move_san and user_rating < 1400:
            primary_tag = "early_queen_adventure"
        elif abs(cp_loss) >= 50:
            primary_tag = "opening_theory_deviation"
    
    elif phase == "endgame":
        if abs(cp_loss) >= 100:
            primary_tag = "endgame_technique_error"
    
    else:  # middlegame
        if abs(cp_loss) >= 150:
            tactical = detect_tactical_pattern(
                fen_before, fen_after, move_san, best_move, cp_loss, pv_after
            )
            if tactical:
                primary_tag = tactical
            elif pv_after and len(pv_after) >= 3:
                primary_tag = "didnt_see_far_enough"
            else:
                primary_tag = "one_move_blunder"
    
    # === SECONDARY TAGS ===
    
    # Add phase-related secondary tag
    if phase == "opening" and primary_tag != "opening_theory_deviation":
        secondary_tags.append("opening_phase_error")
    elif phase == "endgame" and primary_tag != "endgame_technique_error":
        secondary_tags.append("endgame_phase_error")
    
    # Add calculation depth hint if relevant
    if pv_after and len(pv_after) >= 4 and primary_tag not in ["didnt_see_far_enough"]:
        secondary_tags.append("calculation_required")
    
    # === THEORY LINKS ===
    
    # Link to relevant theory based on tags
    THEORY_MAP = {
        "one_move_blunder": ["tactical_vision_basics"],
        "hung_piece": ["piece_safety_check"],
        "back_rank_weakness": ["back_rank_mate_patterns"],
        "missed_fork": ["fork_patterns"],
        "captured_in_fork": ["fork_patterns"],
        "opening_theory_deviation": ["opening_principles"],
        "endgame_technique_error": ["basic_endgames"],
        "threw_winning_position": ["winning_position_technique"],
    }
    
    theory_links = THEORY_MAP.get(primary_tag, [])
    
    return MomentTags(
        primary_tag=primary_tag,
        secondary_tags=secondary_tags,
        theory_links=theory_links,
        phase=phase,
        severity=severity
    )


def get_tag_label(tag_id: str) -> str:
    """Get human-readable label for a tag"""
    tag_info = GAME_TAGS.get(tag_id, {})
    return tag_info.get("label", tag_id.replace("_", " ").title())


def get_tag_description(tag_id: str) -> str:
    """Get description for a tag"""
    tag_info = GAME_TAGS.get(tag_id, {})
    return tag_info.get("description", "")


# ============================================
# AGGREGATION FUNCTIONS
# ============================================

def aggregate_tags(moments: List[Dict]) -> Dict:
    """
    Aggregate tags across multiple moments/games.
    
    Returns summary like:
    {
        "top_issues": [("one_move_blunder", 5), ("hung_piece", 3)],
        "by_phase": {"opening": 2, "middlegame": 5, "endgame": 1},
        "by_category": {"tactical": 6, "positional": 2},
    }
    """
    tag_counts = {}
    phase_counts = {"opening": 0, "middlegame": 0, "endgame": 0}
    category_counts = {}
    
    for m in moments:
        tags = m.get("tags", {})
        primary = tags.get("primary_tag", "unknown")
        phase = tags.get("phase", "middlegame")
        
        # Count primary tag
        tag_counts[primary] = tag_counts.get(primary, 0) + 1
        
        # Count phase
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        
        # Count category
        tag_info = GAME_TAGS.get(primary, {})
        category = tag_info.get("category", "other")
        category_counts[category] = category_counts.get(category, 0) + 1
    
    # Sort tags by count
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "top_issues": sorted_tags[:5],
        "by_phase": phase_counts,
        "by_category": category_counts,
        "total_moments": len(moments),
    }


def compare_tag_evolution(
    recent_moments: List[Dict],
    previous_moments: List[Dict]
) -> Dict:
    """
    Compare tag distribution between two periods.
    
    Returns:
    {
        "improving": ["hung_piece", "one_move_blunder"],
        "worsening": ["endgame_technique_error"],
        "stable": ["opening_theory_deviation"],
    }
    """
    recent_agg = aggregate_tags(recent_moments)
    previous_agg = aggregate_tags(previous_moments)
    
    recent_tags = dict(recent_agg["top_issues"])
    previous_tags = dict(previous_agg["top_issues"])
    
    # Normalize by game count
    recent_total = max(recent_agg["total_moments"], 1)
    previous_total = max(previous_agg["total_moments"], 1)
    
    improving = []
    worsening = []
    stable = []
    
    all_tags = set(recent_tags.keys()) | set(previous_tags.keys())
    
    for tag in all_tags:
        recent_rate = recent_tags.get(tag, 0) / recent_total
        previous_rate = previous_tags.get(tag, 0) / previous_total
        
        if recent_rate < previous_rate * 0.7:  # 30% improvement
            improving.append(tag)
        elif recent_rate > previous_rate * 1.3:  # 30% worse
            worsening.append(tag)
        else:
            stable.append(tag)
    
    return {
        "improving": improving,
        "worsening": worsening,
        "stable": stable,
        "recent_summary": recent_agg,
        "previous_summary": previous_agg,
    }


# ============================================
# INTEGRATION WITH AUTO-CORRECTION SYSTEM
# ============================================

async def tag_critical_moment_with_corrections(
    db,
    move_number: int,
    move_san: str,
    fen_before: str,
    fen_after: str,
    cp_loss: float,
    best_move: str,
    pv_after: List[str],
    user_rating: int,
    total_moves: int,
    time_remaining: Optional[float] = None,
    eval_before: float = 0,
    eval_after: float = 0
) -> MomentTags:
    """
    Tag a critical moment with learned corrections applied.
    
    This is the enhanced version of tag_critical_moment that
    checks for user corrections before applying a tag.
    
    Args:
        db: Database connection for checking corrections
        (other args same as tag_critical_moment)
    
    Returns:
        MomentTags with potentially corrected primary tag
    """
    # First get the standard tag
    tags = tag_critical_moment(
        move_number=move_number,
        move_san=move_san,
        fen_before=fen_before,
        fen_after=fen_after,
        cp_loss=cp_loss,
        best_move=best_move,
        pv_after=pv_after,
        user_rating=user_rating,
        total_moves=total_moves,
        time_remaining=time_remaining,
        eval_before=eval_before,
        eval_after=eval_after
    )
    
    # Check if we have a learned correction for this tag
    try:
        from services.tag_feedback_service import get_corrected_tag
        
        corrected_tag = await get_corrected_tag(
            db=db,
            position_fen=fen_before,
            proposed_tag=tags.primary_tag,
            cp_loss=abs(cp_loss),
            phase=tags.phase
        )
        
        if corrected_tag and corrected_tag != tags.primary_tag:
            logger.info(f"Tag corrected: {tags.primary_tag} -> {corrected_tag}")
            
            # Update theory links for the corrected tag
            THEORY_MAP = {
                "one_move_blunder": ["tactical_vision_basics"],
                "hung_piece": ["piece_safety_check"],
                "back_rank_weakness": ["back_rank_mate_patterns"],
                "missed_fork": ["fork_patterns"],
                "captured_in_fork": ["fork_patterns"],
                "opening_theory_deviation": ["opening_principles"],
                "endgame_technique_error": ["basic_endgames"],
                "threw_winning_position": ["winning_position_technique"],
            }
            
            return MomentTags(
                primary_tag=corrected_tag,
                secondary_tags=tags.secondary_tags + [f"corrected_from_{tags.primary_tag}"],
                theory_links=THEORY_MAP.get(corrected_tag, tags.theory_links),
                phase=tags.phase,
                severity=tags.severity
            )
    except Exception as e:
        logger.debug(f"Error checking tag correction: {e}")
    
    return tags

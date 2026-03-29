"""
Wisdom Library - V1 (16 Rules)

High-frequency, easy-to-verify, explainable rules for 800-2000 rating range.
Each rule has evidence predicates and counterexample conditions.
"""

from typing import List, Dict, Optional
from .models import WisdomRule, ReasonType


# ==================== V1 WISDOM RULES (16) ====================

WISDOM_RULES: Dict[str, WisdomRule] = {
    
    # === DEVELOPMENT & TEMPO ===
    
    "DELAYED_CASTLING": WisdomRule(
        rule_id="DELAYED_CASTLING",
        title="Delayed Castling",
        category="king_safety",
        evidence_predicates=[
            "move_number >= 10",
            "king_not_castled",
            "opponent_has_active_pieces",
            "center_is_open_or_opening",
        ],
        counterexample_conditions=[
            "opposite_side_castling_planned",
            "king_is_safer_in_center",
        ],
        diagnosis_template="Your king is still in the center on move {move_number}. With the center opening up, this is dangerous.",
        memorable_rule="Castle before attacking. A safe king lets you play freely.",
        reason_type=ReasonType.KING_SAFETY,
        followup_questions=[
            {
                "text": "Why is castling usually important in the opening?",
                "options": ["To attack faster", "To connect the rooks and protect the king", "To develop the queen"],
                "correct_idx": 1,
            }
        ],
        min_rating=800,
        max_rating=1800,
    ),
    
    "EARLY_QUEEN_REPEATS": WisdomRule(
        rule_id="EARLY_QUEEN_REPEATS",
        title="Moving Queen Too Early",
        category="development",
        evidence_predicates=[
            "move_number <= 12",
            "queen_moved_multiple_times",
            "minor_pieces_undeveloped",
        ],
        counterexample_conditions=[
            "queen_move_wins_material",
            "queen_move_is_forcing",
        ],
        diagnosis_template="Your queen has moved {queen_moves} times in the first {move_number} moves while {undeveloped_count} pieces remain undeveloped.",
        memorable_rule="Develop knights and bishops before moving the queen repeatedly.",
        reason_type=ReasonType.DEVELOPMENT_TEMPO,
        followup_questions=[
            {
                "text": "Why is moving the queen early often a problem?",
                "options": ["The queen is too strong", "The queen can be chased, losing tempo", "The queen should stay on d1/d8"],
                "correct_idx": 1,
            }
        ],
    ),
    
    "MOVE_SAME_PIECE_REPEAT": WisdomRule(
        rule_id="MOVE_SAME_PIECE_REPEAT",
        title="Moving Same Piece Repeatedly",
        category="development",
        evidence_predicates=[
            "same_piece_moved_consecutively",
            "other_pieces_undeveloped",
            "no_forcing_reason",
        ],
        counterexample_conditions=[
            "move_is_forced",
            "move_wins_material",
        ],
        diagnosis_template="You moved your {piece} again ({from_sq} to {to_sq}) while other pieces haven't moved yet.",
        memorable_rule="Each move should bring a new piece into the game.",
        reason_type=ReasonType.DEVELOPMENT_TEMPO,
    ),
    
    # === TACTICS ===
    
    "MISSED_FORCING_MOVES": WisdomRule(
        rule_id="MISSED_FORCING_MOVES",
        title="Missed Forcing Move",
        category="tactics",
        evidence_predicates=[
            "forcing_move_available",
            "user_played_quiet_move",
            "sf_preferred_forcing",
        ],
        counterexample_conditions=[
            "forcing_move_leads_to_worse_position",
        ],
        diagnosis_template="There was a forcing move ({forcing_move}) that you missed. Forcing moves (checks, captures, threats) often deserve priority.",
        memorable_rule="Before each move, check: Is there a check, capture, or threat?",
        reason_type=ReasonType.THREAT,
        followup_questions=[
            {
                "text": "What should you look for before making a quiet move?",
                "options": ["Pawn moves", "Checks, captures, and threats", "Rook moves"],
                "correct_idx": 1,
            }
        ],
    ),
    
    "HANGING_PIECE": WisdomRule(
        rule_id="HANGING_PIECE",
        title="Left Piece Hanging",
        category="tactics",
        evidence_predicates=[
            "piece_is_undefended",
            "opponent_can_capture_it",
            "capture_is_profitable",
        ],
        counterexample_conditions=[
            "piece_sacrifice_is_intentional",
            "recapture_available",
        ],
        diagnosis_template="Your {piece} on {square} is undefended and can be captured.",
        memorable_rule="Before moving, ask: Is anything hanging?",
        reason_type=ReasonType.HANGING_PIECE,
    ),
    
    "SIMPLE_FORK_ALLOWED": WisdomRule(
        rule_id="SIMPLE_FORK_ALLOWED",
        title="Allowed a Fork",
        category="tactics",
        evidence_predicates=[
            "opponent_has_fork_available",
            "user_move_enabled_fork",
        ],
        counterexample_conditions=[
            "fork_is_not_profitable",
        ],
        diagnosis_template="Your move allowed a {piece} fork on {fork_square}, attacking your {targets}.",
        memorable_rule="Watch for knight forks especially - they're easy to miss.",
        reason_type=ReasonType.THREAT,
    ),
    
    # === PIECE ACTIVITY ===
    
    "OPEN_FILE_ROOK_UNUSED": WisdomRule(
        rule_id="OPEN_FILE_ROOK_UNUSED",
        title="Rook Not Using Open File",
        category="piece_activity",
        evidence_predicates=[
            "open_file_exists",
            "rook_not_on_open_file",
            "rook_could_reach_open_file",
        ],
        counterexample_conditions=[
            "rook_doing_something_more_important",
            "open_file_is_contested",
        ],
        diagnosis_template="The {file}-file is open but your rook on {rook_square} isn't using it.",
        memorable_rule="Rooks belong on open files. They're most powerful with clear paths.",
        reason_type=ReasonType.OPEN_FILE,
    ),
    
    "ROOKS_NOT_CONNECTED": WisdomRule(
        rule_id="ROOKS_NOT_CONNECTED",
        title="Rooks Not Connected",
        category="piece_activity",
        evidence_predicates=[
            "rooks_exist",
            "pieces_between_rooks",
            "could_connect_rooks",
        ],
        counterexample_conditions=[
            "connecting_rooks_loses_material",
        ],
        diagnosis_template="Your rooks on {rook1} and {rook2} aren't connected. A piece on {blocker} is in the way.",
        memorable_rule="Connect your rooks early. They protect each other and double their power.",
        reason_type=ReasonType.PIECE_ACTIVITY,
    ),
    
    "BLOCKED_BISHOP_BY_OWN_PAWN": WisdomRule(
        rule_id="BLOCKED_BISHOP_BY_OWN_PAWN",
        title="Blocked Bishop",
        category="piece_activity",
        evidence_predicates=[
            "bishop_mobility_low",  # <= 4 squares
            "own_pawn_blocks_diagonal",
            "is_closed_or_sf_prefers_knight",
        ],
        counterexample_conditions=[
            "bishop_has_good_future",
            "position_will_open",
        ],
        diagnosis_template="Your bishop on {bishop_square} is blocked by your pawn on {pawn_square}. It controls only {mobility} squares.",
        memorable_rule="Bishops need open diagonals. In closed positions, knights are often better.",
        reason_type=ReasonType.PIECE_ACTIVITY,
        followup_questions=[
            {
                "text": "In closed positions with blocked pawns, which piece is usually better?",
                "options": ["Bishop", "Knight", "Rook"],
                "correct_idx": 1,
            }
        ],
    ),
    
    "BAD_TRADE_ACTIVE_FOR_PASSIVE": WisdomRule(
        rule_id="BAD_TRADE_ACTIVE_FOR_PASSIVE",
        title="Traded Active Piece for Passive",
        category="piece_activity",
        evidence_predicates=[
            "trade_occurred",
            "our_piece_was_more_active",
            "their_piece_was_passive",
        ],
        counterexample_conditions=[
            "trade_improves_position",
            "trade_relieves_pressure",
        ],
        diagnosis_template="You traded your active {our_piece} for their passive {their_piece}. This helped them.",
        memorable_rule="Don't trade your good pieces for their bad ones.",
        reason_type=ReasonType.PIECE_ACTIVITY,
    ),
    
    "BISHOP_PAIR_GIVEN_UP_OPEN_POS": WisdomRule(
        rule_id="BISHOP_PAIR_GIVEN_UP_OPEN_POS",
        title="Gave Up Bishop Pair in Open Position",
        category="piece_activity",
        evidence_predicates=[
            "had_bishop_pair",
            "traded_bishop_for_knight",
            "position_is_open",
        ],
        counterexample_conditions=[
            "knight_outpost_very_strong",
            "bishops_were_passive",
        ],
        diagnosis_template="You gave up the bishop pair in an open position where bishops are typically stronger.",
        memorable_rule="In open positions, two bishops are usually better than bishop + knight.",
        reason_type=ReasonType.PIECE_ACTIVITY,
    ),
    
    "IGNORE_WORST_PIECE": WisdomRule(
        rule_id="IGNORE_WORST_PIECE",
        title="Ignored Your Worst Piece",
        category="piece_activity",
        evidence_predicates=[
            "worst_piece_identified",
            "worst_piece_could_improve",
            "user_moved_different_piece",
        ],
        counterexample_conditions=[
            "other_move_was_forcing",
            "worst_piece_cannot_improve",
        ],
        diagnosis_template="Your {worst_piece} on {worst_square} is your least active piece. Consider improving it before other moves.",
        memorable_rule="When unsure what to do, improve your worst piece.",
        reason_type=ReasonType.PIECE_ACTIVITY,
        followup_questions=[
            {
                "text": "What should you do when you don't know what to play?",
                "options": ["Push a pawn", "Improve your worst-placed piece", "Move the king"],
                "correct_idx": 1,
            }
        ],
    ),
    
    # === ADVANTAGE CONVERSION ===
    
    "ADVANTAGE_CONVERSION_SIMPLIFY": WisdomRule(
        rule_id="ADVANTAGE_CONVERSION_SIMPLIFY",
        title="Didn't Simplify When Ahead",
        category="conversion",
        evidence_predicates=[
            "material_advantage",
            "simplifying_trade_available",
            "user_avoided_trade",
        ],
        counterexample_conditions=[
            "attack_is_stronger",
            "trade_loses_advantage",
        ],
        diagnosis_template="You're ahead in material but avoided trading. Simplifying often makes winning easier.",
        memorable_rule="When ahead, trade pieces. When behind, avoid trades.",
        reason_type=ReasonType.PIECE_ACTIVITY,
    ),
    
    "WHEN_WORSE_AVOID_TRADES": WisdomRule(
        rule_id="WHEN_WORSE_AVOID_TRADES",
        title="Traded When Behind",
        category="conversion",
        evidence_predicates=[
            "material_disadvantage",
            "user_initiated_trade",
            "trade_not_forced",
        ],
        counterexample_conditions=[
            "trade_removes_key_attacker",
            "trade_reaches_drawable_endgame",
        ],
        diagnosis_template="You're behind in material but traded pieces. This usually makes defending harder.",
        memorable_rule="When behind, keep pieces on. Complexity gives you chances.",
        reason_type=ReasonType.PIECE_ACTIVITY,
    ),
    
    # === KING SAFETY ===
    
    "KING_SAFETY_PAWN_SHIELD_WEAKEN": WisdomRule(
        rule_id="KING_SAFETY_PAWN_SHIELD_WEAKEN",
        title="Weakened Pawn Shield",
        category="king_safety",
        evidence_predicates=[
            "king_is_castled",
            "pawn_shield_move_made",
            "opponent_has_attacking_pieces",
        ],
        counterexample_conditions=[
            "pawn_move_creates_escape_square",
            "no_attack_possible",
        ],
        diagnosis_template="Moving your {pawn} weakened your king's protection. Your opponent has pieces that can exploit this.",
        memorable_rule="Don't move pawns in front of your castled king without a good reason.",
        reason_type=ReasonType.KING_SAFETY,
    ),
    
    # === PAWN STRUCTURE ===
    
    "CENTER_TENSION_IGNORED": WisdomRule(
        rule_id="CENTER_TENSION_IGNORED",
        title="Ignored Center Tension",
        category="pawn_structure",
        evidence_predicates=[
            "center_tension_exists",
            "capture_or_push_available",
            "user_played_flank_move",
            "sf_preferred_center_action",
        ],
        counterexample_conditions=[
            "tension_should_be_maintained",
            "flank_move_is_more_important",
        ],
        diagnosis_template="There's tension in the center ({tension_squares}), but you played on the flank. Resolving center tension first is usually better.",
        memorable_rule="Don't ignore the center. Flank attacks work best when the center is stable.",
        reason_type=ReasonType.PAWN_STRUCTURE,
    ),
}


class WisdomLibrary:
    """
    Access and query the wisdom rule library.
    """
    
    def __init__(self):
        self.rules = WISDOM_RULES
    
    def get_rule(self, rule_id: str) -> Optional[WisdomRule]:
        """Get a specific rule by ID"""
        return self.rules.get(rule_id)
    
    def get_all_rules(self) -> List[WisdomRule]:
        """Get all rules"""
        return list(self.rules.values())
    
    def get_rules_by_category(self, category: str) -> List[WisdomRule]:
        """Get rules by category"""
        return [r for r in self.rules.values() if r.category == category]
    
    def get_rules_by_reason(self, reason: ReasonType) -> List[WisdomRule]:
        """Get rules by reason type"""
        return [r for r in self.rules.values() if r.reason_type == reason]
    
    def get_rules_for_rating(self, rating: int) -> List[WisdomRule]:
        """Get rules appropriate for a rating range"""
        return [r for r in self.rules.values() 
                if r.min_rating <= rating <= r.max_rating]
    
    def get_rule_ids(self) -> List[str]:
        """Get all rule IDs"""
        return list(self.rules.keys())


# Singleton instance
_library = None

def get_wisdom_library() -> WisdomLibrary:
    """Get the singleton wisdom library instance"""
    global _library
    if _library is None:
        _library = WisdomLibrary()
    return _library

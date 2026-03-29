"""
Turning Point Explanation Generator
====================================

Generates adaptive, behavioral explanations for turning points.

Key principles:
1. Rating-aware language (adapt to user's level)
2. Behavioral focus (explain the thinking error, not just the move)
3. Idea-based (what concept did the user miss?)
4. Actionable (what should user do differently next time?)

Usage:
    generator = TurningPointExplainer()
    explanation = await generator.explain(
        fen=position_fen,
        user_move="Qd3",
        best_move="Nf5",
        cp_loss=400,
        user_rating=1200,
        threat=detected_threat
    )
"""

import chess
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TurningPointExplanation:
    """Complete explanation for a turning point."""
    # Main explanation (rating-adapted)
    main_text: str
    
    # What the user didn't see
    missed_idea: str
    
    # What the opponent's idea was
    opponent_idea: str
    
    # Behavioral lesson
    thinking_error: str
    
    # What to do next time
    training_tip: str
    
    # Severity assessment
    severity: str  # "game-losing", "critical", "significant"
    
    # NEW: Categorization for pattern tracking
    category: str  # "tactical_blindness", "threat_ignorance", "positional_mistake", etc.
    category_label: str  # Human-readable: "Tactical Blindness"
    
    # NEW: How to spot this in future
    how_to_spot: List[str]  # Checklist of things to look for
    pattern_name: str  # e.g., "Queen + Bishop Battery"
    training_focus: str  # e.g., "piece_coordination"


# Turning point categories with training mappings
TURNING_POINT_CATEGORIES = {
    "tactical_blindness": {
        "label": "Tactical Blindness",
        "description": "Missed a tactical pattern (fork, pin, skewer, etc.)",
        "training_focus": "tactics",
        "patterns": ["fork", "pin", "skewer", "discovery", "back_rank", "battery"]
    },
    "threat_ignorance": {
        "label": "Threat Ignorance",
        "description": "Didn't check what opponent was threatening",
        "training_focus": "threat_awareness",
        "patterns": ["ignored_threat", "missed_attack", "hanging"]
    },
    "positional_mistake": {
        "label": "Positional Mistake",
        "description": "Created weaknesses or missed positional ideas",
        "training_focus": "positional",
        "patterns": ["weak_square", "pawn_structure", "piece_activity"]
    },
    "calculation_error": {
        "label": "Calculation Error",
        "description": "Saw the idea but miscounted or missed a defense",
        "training_focus": "calculation",
        "patterns": ["miscalculation", "missed_defense"]
    },
    "piece_coordination": {
        "label": "Piece Coordination",
        "description": "Opponent's pieces worked together dangerously",
        "training_focus": "piece_coordination",
        "patterns": ["battery", "connected_pieces", "double_attack"]
    },
    "king_safety": {
        "label": "King Safety Neglect",
        "description": "King was exposed or attacked",
        "training_focus": "king_safety",
        "patterns": ["king_attack", "mate_threat", "back_rank", "exposed_king"]
    },
    "one_move_blunder": {
        "label": "One-Move Blunder",
        "description": "Simple oversight that lost material or the game",
        "training_focus": "blunder_check",
        "patterns": ["simple_blunder", "hanging_piece", "oversight"]
    }
}


# How to spot patterns - teaching checklists
HOW_TO_SPOT_PATTERNS = {
    "fork": [
        "Before moving, check: Can a knight reach a square attacking two pieces?",
        "Look for undefended pieces on the same knight-hop distance",
        "Especially dangerous: King + Queen or King + Rook forkable"
    ],
    "pin": [
        "Check if any of your pieces are on the same line as your King/Queen",
        "Bishops and Rooks create pins along lines - scan the diagonals and files",
        "A pinned piece can't move safely - don't rely on it for defense"
    ],
    "battery": [
        "Watch for Queen + Bishop on the same diagonal aimed at your King",
        "Queen + Rook on the same file is equally dangerous",
        "If opponent's heavy pieces align, expect an attack"
    ],
    "back_rank": [
        "Always ask: Does my King have an escape square?",
        "If your King is on the back rank with no luft (h3/h6), create one",
        "Heavy pieces (Queen/Rook) on open files threaten back rank mates"
    ],
    "hanging": [
        "After EVERY move, scan: Are all my pieces defended?",
        "Count attackers vs defenders on each piece",
        "Undefended pieces are targets - either defend or move them"
    ],
    "threat_ignorance": [
        "Before YOUR move, ask: What is opponent threatening?",
        "Look at opponent's last move - what did it attack or prepare?",
        "Check ALL opponent pieces, not just the one that moved"
    ],
    "piece_coordination": [
        "Watch for opponent's pieces pointing at the same square",
        "Two pieces attacking one target often wins material",
        "Queen + minor piece combos are especially dangerous"
    ],
    "king_attack": [
        "If opponent has more pieces near your King, be defensive",
        "Don't start attacks while your King is exposed",
        "Castle early or keep the center closed if King is in the middle"
    ],
    "weak_square": [
        "Pawns can't go backward - advancing them creates permanent holes",
        "Knights love outposts on weak squares",
        "Think twice before pushing pawns in front of your King"
    ]
}


# Rating brackets for language adaptation
RATING_BRACKETS = {
    "beginner": (0, 1000),
    "intermediate": (1000, 1400),
    "advanced": (1400, 1800),
    "expert": (1800, 2200),
    "master": (2200, 3000)
}


class TurningPointExplainer:
    """
    Generates adaptive explanations for turning points.
    
    Adapts language and depth based on:
    - User rating
    - Position complexity
    - Type of mistake
    """
    
    def __init__(self):
        # Pattern-specific explanation templates
        self.tactical_explanations = {
            "fork": {
                "beginner": "Your opponent could attack two pieces at once with one move.",
                "intermediate": "There was a fork threat that won material.",
                "advanced": "The knight fork on {square} was decisive - it attacked two undefended pieces simultaneously.",
                "expert": "The double attack motif was available via {square}, exploiting the uncoordinated placement of your pieces."
            },
            "pin": {
                "beginner": "One of your pieces was stuck and couldn't move safely.",
                "intermediate": "A pin was created - your piece couldn't move without losing something bigger.",
                "advanced": "The absolute pin along the {line} file/diagonal paralyzed your defense.",
                "expert": "The pin exploitation was the key tactical motif - the X-ray attack made your {piece} immobile."
            },
            "hanging": {
                "beginner": "You left a piece unprotected and it got taken.",
                "intermediate": "A piece was left hanging without any defender.",
                "advanced": "The undefended {piece} on {square} was the target - always count attackers vs defenders.",
                "expert": "The loose piece was a tactical liability. In positions with active enemy pieces, every undefended piece is a potential target."
            },
            "back_rank": {
                "beginner": "Your king was trapped on the back row with no escape.",
                "intermediate": "The back rank was weak - your king had no escape squares.",
                "advanced": "Classic back rank motif - the lack of luft (breathing room) for your king proved fatal.",
                "expert": "The back rank weakness was exploited precisely. Creating h3/h6 escape earlier was essential prophylaxis."
            },
            "discovery": {
                "beginner": "When one piece moved, it uncovered an attack from another piece behind it.",
                "intermediate": "A discovered attack hit multiple targets at once.",
                "advanced": "The discovered attack was devastating - the moving piece created a threat while revealing another.",
                "expert": "The discovery leveraged the battery setup to create multiple simultaneous threats."
            },
            "skewer": {
                "beginner": "Your valuable piece had to move, and then the piece behind it was taken.",
                "intermediate": "A skewer forced your bigger piece to move, exposing the piece behind it.",
                "advanced": "The skewer along the {line} was the tactical blow - your {piece} had to abandon the {piece2}.",
                "expert": "Linear piece alignment created the skewer vulnerability. Piece placement on the same line requires careful attention."
            },
            "overload": {
                "beginner": "One of your pieces was trying to do too many jobs at once.",
                "intermediate": "Your piece was overloaded - defending too many things.",
                "advanced": "The overloaded {piece} couldn't maintain all its defensive duties. Something had to give.",
                "expert": "The overworked piece phenomenon - when one defender is responsible for multiple duties, tactical exploitation becomes possible."
            }
        }
        
        self.behavioral_errors = {
            "ignored_threat": {
                "description": "You didn't check what your opponent was threatening before moving.",
                "tip": "Before EVERY move, ask: 'What is my opponent threatening?'"
            },
            "premature_attack": {
                "description": "You attacked before your pieces were ready or before securing your position.",
                "tip": "Don't attack until your pieces are developed and your king is safe."
            },
            "greedy_capture": {
                "description": "You captured material but missed that it created a bigger problem.",
                "tip": "Always check: 'If I take this, what can my opponent do?'"
            },
            "tunnel_vision": {
                "description": "You focused on your plan and didn't see your opponent's idea.",
                "tip": "Look at the WHOLE board, not just where you want to play."
            },
            "piece_safety": {
                "description": "You didn't notice that a piece was undefended or could become a target.",
                "tip": "After every move, scan: 'Are all my pieces safe?'"
            },
            "king_neglect": {
                "description": "You didn't prioritize your king's safety when there were threats around.",
                "tip": "In an open position, king safety comes before everything else."
            },
            "calculation_error": {
                "description": "The position required precise calculation, and something was missed in the sequence.",
                "tip": "When the position is sharp, slow down and calculate each response."
            }
        }
    
    def get_rating_bracket(self, rating: int) -> str:
        """Determine rating bracket for language adaptation."""
        for bracket, (low, high) in RATING_BRACKETS.items():
            if low <= rating < high:
                return bracket
        return "intermediate"  # Default
    
    async def explain(
        self,
        fen: str,
        user_move: str,
        best_move: str,
        cp_loss: int,
        user_rating: int = 1200,
        threat: Optional[str] = None,
        detected_patterns: Optional[List[Dict]] = None,
        eval_before: Optional[float] = None,
        eval_after: Optional[float] = None
    ) -> TurningPointExplanation:
        """
        Generate a complete turning point explanation.
        
        Args:
            fen: Position before the mistake
            user_move: Move that was played
            best_move: Move that should have been played
            cp_loss: Centipawn loss
            user_rating: User's chess rating for language adaptation
            threat: Detected tactical threat (if any)
            detected_patterns: Patterns detected by chess_brain
            eval_before: Eval before move
            eval_after: Eval after move
        
        Returns:
            TurningPointExplanation with all components
        """
        
        bracket = self.get_rating_bracket(user_rating)
        
        # Determine severity
        if cp_loss >= 400:
            severity = "game-losing"
        elif cp_loss >= 250:
            severity = "critical"
        else:
            severity = "significant"
        
        # Analyze the position
        try:
            board = chess.Board(fen)
        except Exception:
            board = None
        
        # Detect what type of mistake this was
        tactical_type = self._identify_tactical_type(threat, detected_patterns)
        behavioral_type = self._identify_behavioral_error(
            threat, tactical_type, board, user_move, best_move, cp_loss
        )
        
        # Generate main explanation (rating-adapted)
        main_text = self._generate_main_explanation(
            bracket, tactical_type, behavioral_type, 
            user_move, best_move, cp_loss, threat
        )
        
        # Generate what user missed
        missed_idea = self._generate_missed_idea(
            bracket, tactical_type, threat, best_move
        )
        
        # Generate opponent's idea
        opponent_idea = self._generate_opponent_idea(
            bracket, tactical_type, threat
        )
        
        # Get behavioral lesson
        behavior = self.behavioral_errors.get(behavioral_type, self.behavioral_errors["calculation_error"])
        thinking_error = behavior["description"]
        training_tip = behavior["tip"]
        
        # NEW: Categorize the turning point for pattern tracking
        category, category_label, pattern_name = self._categorize_turning_point(
            tactical_type, behavioral_type, threat, cp_loss
        )
        
        # NEW: Generate "How to spot this" checklist
        how_to_spot = self._generate_how_to_spot(tactical_type, behavioral_type, pattern_name)
        
        # NEW: Determine training focus
        training_focus = self._get_training_focus(category, tactical_type)
        
        return TurningPointExplanation(
            main_text=main_text,
            missed_idea=missed_idea,
            opponent_idea=opponent_idea,
            thinking_error=thinking_error,
            training_tip=training_tip,
            severity=severity,
            category=category,
            category_label=category_label,
            how_to_spot=how_to_spot,
            pattern_name=pattern_name,
            training_focus=training_focus
        )
    
    def _categorize_turning_point(
        self,
        tactical_type: Optional[str],
        behavioral_type: str,
        threat: Optional[str],
        cp_loss: int
    ) -> tuple:
        """Categorize the turning point for pattern tracking."""
        
        threat_lower = (threat or "").lower()
        
        # Check for tactical patterns first
        if tactical_type:
            if tactical_type in ["fork", "pin", "skewer", "discovery"]:
                return "tactical_blindness", "Tactical Blindness", tactical_type.replace("_", " ").title()
            elif tactical_type == "back_rank":
                return "king_safety", "King Safety Neglect", "Back Rank Weakness"
            elif tactical_type in ["battery", "overload"]:
                return "piece_coordination", "Piece Coordination", tactical_type.replace("_", " ").title()
            elif tactical_type == "hanging":
                return "one_move_blunder", "One-Move Blunder", "Hanging Piece"
        
        # Check threat description
        if "battery" in threat_lower or "queen" in threat_lower and "bishop" in threat_lower:
            return "piece_coordination", "Piece Coordination", "Queen + Bishop Battery"
        if "mate" in threat_lower or "checkmate" in threat_lower:
            return "king_safety", "King Safety Neglect", "Mate Threat"
        if "fork" in threat_lower:
            return "tactical_blindness", "Tactical Blindness", "Fork"
        if "pin" in threat_lower:
            return "tactical_blindness", "Tactical Blindness", "Pin"
        if "hanging" in threat_lower or "undefended" in threat_lower:
            return "one_move_blunder", "One-Move Blunder", "Hanging Piece"
        
        # Based on behavioral type
        if behavioral_type == "ignored_threat":
            return "threat_ignorance", "Threat Ignorance", "Missed Opponent Threat"
        if behavioral_type == "piece_safety":
            return "one_move_blunder", "One-Move Blunder", "Piece Left Undefended"
        if behavioral_type == "king_neglect":
            return "king_safety", "King Safety Neglect", "King Exposed"
        if behavioral_type == "greedy_capture":
            return "tactical_blindness", "Tactical Blindness", "Greedy Capture Punished"
        if behavioral_type == "calculation_error":
            return "calculation_error", "Calculation Error", "Miscalculation"
        
        # Default based on cp_loss
        if cp_loss >= 500:
            return "one_move_blunder", "One-Move Blunder", "Major Oversight"
        
        return "positional_mistake", "Positional Mistake", "Strategic Error"
    
    def _generate_how_to_spot(
        self,
        tactical_type: Optional[str],
        behavioral_type: str,
        pattern_name: str
    ) -> List[str]:
        """Generate 'How to spot this' checklist for future games."""
        
        # Check for specific tactical patterns first
        if tactical_type and tactical_type in HOW_TO_SPOT_PATTERNS:
            return HOW_TO_SPOT_PATTERNS[tactical_type]
        
        # Check pattern name keywords
        pattern_lower = pattern_name.lower()
        for key, tips in HOW_TO_SPOT_PATTERNS.items():
            if key in pattern_lower:
                return tips
        
        # Check behavioral type
        if behavioral_type == "ignored_threat":
            return HOW_TO_SPOT_PATTERNS.get("threat_ignorance", [])
        if behavioral_type == "piece_safety":
            return HOW_TO_SPOT_PATTERNS.get("hanging", [])
        if behavioral_type == "king_neglect":
            return HOW_TO_SPOT_PATTERNS.get("king_attack", [])
        
        # Default checklist
        return [
            "Before each move, ask: What is my opponent threatening?",
            "Check if any of your pieces are undefended",
            "Look at the whole board, not just your own plans"
        ]
    
    def _get_training_focus(self, category: str, tactical_type: Optional[str]) -> str:
        """Get the training focus area for this type of mistake."""
        
        if category in TURNING_POINT_CATEGORIES:
            return TURNING_POINT_CATEGORIES[category]["training_focus"]
        
        if tactical_type:
            return "tactics"
        
        return "general"
    
    def _identify_tactical_type(
        self, 
        threat: Optional[str],
        detected_patterns: Optional[List[Dict]]
    ) -> Optional[str]:
        """Identify the tactical pattern involved."""
        
        if threat:
            threat_lower = threat.lower()
            for pattern in ["fork", "pin", "skewer", "back_rank", "discovery", "hanging", "overload"]:
                if pattern.replace("_", " ") in threat_lower or pattern in threat_lower:
                    return pattern
        
        if detected_patterns:
            for pattern in detected_patterns:
                pattern_type = pattern.get("type", "").lower()
                if pattern_type in self.tactical_explanations:
                    return pattern_type
        
        return None
    
    def _identify_behavioral_error(
        self,
        threat: Optional[str],
        tactical_type: Optional[str],
        board: Optional[chess.Board],
        user_move: str,
        best_move: str,
        cp_loss: int
    ) -> str:
        """Identify the thinking error that led to the mistake."""
        
        threat_lower = (threat or "").lower()
        
        # Check for specific behavioral patterns
        if "ignore" in threat_lower or "miss" in threat_lower:
            return "ignored_threat"
        
        if tactical_type == "hanging":
            return "piece_safety"
        
        if tactical_type == "back_rank":
            return "king_neglect"
        
        if "greedy" in threat_lower or "capture" in threat_lower:
            return "greedy_capture"
        
        # Check move characteristics
        if board:
            try:
                move = board.parse_san(user_move)
                # If user moved a piece that was defending something
                # or made an aggressive move while under threat
                if board.is_capture(move) and cp_loss > 200:
                    return "greedy_capture"
            except Exception:
                pass
        
        # Default based on cp_loss
        if cp_loss >= 300:
            return "tunnel_vision"
        
        return "calculation_error"
    
    def _generate_main_explanation(
        self,
        bracket: str,
        tactical_type: Optional[str],
        behavioral_type: str,
        user_move: str,
        best_move: str,
        cp_loss: int,
        threat: Optional[str]
    ) -> str:
        """Generate the main explanation text, adapted to rating."""
        
        # Get tactical explanation if available
        tactical_text = ""
        if tactical_type and tactical_type in self.tactical_explanations:
            templates = self.tactical_explanations[tactical_type]
            tactical_text = templates.get(bracket, templates.get("intermediate", ""))
        
        # Build the explanation
        if bracket == "beginner":
            if tactical_text:
                return f"This move lost the game. {tactical_text}"
            return f"After {user_move}, the position became very difficult. {best_move} was much better because it kept your pieces safe."
        
        elif bracket == "intermediate":
            if tactical_text:
                return f"{user_move} was the turning point. {tactical_text} {best_move} would have avoided this."
            if threat:
                return f"{user_move} allowed {threat}. {best_move} was needed to prevent this."
            return f"{user_move} gave away the game. {best_move} would have kept the balance."
        
        elif bracket == "advanced":
            if tactical_text:
                return f"The critical error. {tactical_text} After {user_move}, the position is objectively lost. {best_move} was required."
            return f"{user_move} was the decisive mistake (−{cp_loss/100:.1f} pawns). {best_move} maintains the position."
        
        else:  # expert/master
            eval_change = f"−{cp_loss/100:.1f}" if cp_loss else ""
            if tactical_text:
                return f"The turning point ({eval_change}). {tactical_text}"
            return f"Critical error: {user_move} ({eval_change}). The position demanded {best_move}."
    
    def _generate_missed_idea(
        self,
        bracket: str,
        tactical_type: Optional[str],
        threat: Optional[str],
        best_move: str
    ) -> str:
        """Generate what the user didn't see."""
        
        if bracket == "beginner":
            if tactical_type:
                return "You didn't see that your opponent had a trick available."
            return f"You missed that {best_move} was much safer."
        
        elif bracket == "intermediate":
            if threat:
                return f"You didn't spot the {threat.lower()} threat."
            return f"The key idea was {best_move}, which prevents the opponent's plan."
        
        else:
            if threat:
                return f"The tactical motif ({threat.lower()}) was the key resource you missed."
            return f"The prophylactic {best_move} was required to neutralize the opponent's activity."
    
    def _generate_opponent_idea(
        self,
        bracket: str,
        tactical_type: Optional[str],
        threat: Optional[str]
    ) -> str:
        """Generate what the opponent's idea was."""
        
        if bracket == "beginner":
            if tactical_type:
                return "Your opponent found a way to win material or attack your king."
            return "Your opponent saw a way to make your position worse."
        
        elif bracket == "intermediate":
            if threat:
                return f"Your opponent's idea was the {threat.lower()}."
            return "Your opponent exploited the weakness in your position."
        
        else:
            if threat:
                return f"The {threat.lower()} was the culmination of your opponent's plan."
            return "Your opponent found the precise continuation to convert the advantage."


# Singleton instance
_explainer = None

def get_turning_point_explainer() -> TurningPointExplainer:
    """Get singleton instance of the explainer."""
    global _explainer
    if _explainer is None:
        _explainer = TurningPointExplainer()
    return _explainer

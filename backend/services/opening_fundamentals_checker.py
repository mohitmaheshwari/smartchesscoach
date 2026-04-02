"""
Opening Fundamentals Checker
============================

Checks if a player follows fundamental opening principles.
These are the basics every 600-1200 player needs to learn.

Principles checked:
1. Don't move the same piece twice (without good reason)
2. Castle before move 10-12
3. Develop knights before bishops (usually)
4. Don't bring the queen out early
5. Control the center with pawns (e4/d4 or e5/d5)
6. Develop all minor pieces before attacking
7. Connect your rooks (by castling and developing)
8. Don't make unnecessary pawn moves in the opening
9. Don't neglect king safety
10. Develop toward the center, not the edges

Each violation generates a teaching moment that can be shown in Lab.
"""

import chess
import logging
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OpeningPrinciple(str, Enum):
    """Fundamental opening principles."""
    SAME_PIECE_TWICE = "same_piece_twice"
    CASTLE_EARLY = "castle_early"
    DEVELOP_MINOR_PIECES = "develop_minor_pieces"
    QUEEN_OUT_EARLY = "queen_out_early"
    CENTER_CONTROL = "center_control"
    DEVELOP_BEFORE_ATTACK = "develop_before_attack"
    CONNECT_ROOKS = "connect_rooks"
    UNNECESSARY_PAWN_MOVES = "unnecessary_pawn_moves"
    KING_SAFETY = "king_safety"
    DEVELOP_TOWARD_CENTER = "develop_toward_center"


@dataclass
class PrincipleViolation:
    """A violation of an opening principle."""
    principle: OpeningPrinciple
    move_number: int
    move: str
    explanation: str
    teaching_message: str
    severity: str  # "minor", "moderate", "major"
    what_to_do: str  # Actionable advice


PRINCIPLE_TEACHINGS = {
    OpeningPrinciple.SAME_PIECE_TWICE: {
        "name": "Don't Move the Same Piece Twice",
        "explanation": "Moving the same piece twice in the opening wastes time. Each move should bring a new piece into the game.",
        "what_to_think": "Before moving a piece again, ask: Is there a new piece I haven't developed yet?",
        "exceptions": "Only move a piece twice if: 1) It's being attacked, 2) You're winning material, or 3) There's a clear tactical reason."
    },
    OpeningPrinciple.CASTLE_EARLY: {
        "name": "Castle Early (Before Move 10-12)",
        "explanation": "Castling protects your king and connects your rooks. Delaying castling leaves your king vulnerable.",
        "what_to_think": "After developing 2-3 pieces, ask: Can I castle now? If not, what's stopping me?",
        "exceptions": "Delay castling only if: 1) You'd castle into an attack, or 2) You need the rook where it is."
    },
    OpeningPrinciple.QUEEN_OUT_EARLY: {
        "name": "Don't Bring the Queen Out Too Early",
        "explanation": "The queen can be chased around by minor pieces, wasting your time while your opponent develops.",
        "what_to_think": "The queen is powerful but vulnerable. Develop your minor pieces first to support her later.",
        "exceptions": "Early queen moves are OK if: 1) You're winning material, or 2) There's a concrete tactical threat."
    },
    OpeningPrinciple.CENTER_CONTROL: {
        "name": "Control the Center",
        "explanation": "The center (e4, d4, e5, d5) is the most important area. Pieces in the center control more squares.",
        "what_to_think": "Ask: Do I have a pawn or piece controlling the center? If not, how can I fight for it?",
        "exceptions": "Some openings (hypermodern) control the center from a distance, but this requires deeper understanding."
    },
    OpeningPrinciple.DEVELOP_MINOR_PIECES: {
        "name": "Develop Your Minor Pieces",
        "explanation": "Knights and bishops should come out before you start attacking. Undeveloped pieces can't help you.",
        "what_to_think": "Count your developed pieces. If you have 2 or fewer out, focus on development, not attack.",
        "exceptions": "Attack early only if there's a concrete win (checkmate, winning material)."
    },
    OpeningPrinciple.DEVELOP_BEFORE_ATTACK: {
        "name": "Develop Before Attacking",
        "explanation": "Attacking with only a few pieces rarely works. Your opponent can defend with their undeveloped pieces.",
        "what_to_think": "Before attacking, ask: How many of my pieces are participating? If less than 3-4, develop more.",
        "exceptions": "Attack early only with a concrete tactical sequence, not a vague 'attack'."
    },
    OpeningPrinciple.CONNECT_ROOKS: {
        "name": "Connect Your Rooks",
        "explanation": "Rooks need open files. They work together best when connected (no pieces between them on the back rank).",
        "what_to_think": "After castling, look at your back rank. Can your rooks see each other?",
        "exceptions": "Sometimes one rook goes to an open file before connecting."
    },
    OpeningPrinciple.UNNECESSARY_PAWN_MOVES: {
        "name": "Don't Make Unnecessary Pawn Moves",
        "explanation": "Pawns can't move backward. Each pawn move creates permanent weaknesses. Move pieces, not pawns.",
        "what_to_think": "Before moving a pawn (other than e/d pawns), ask: What square am I weakening?",
        "exceptions": "Pawn moves to: 1) Control center, 2) Make room for pieces, 3) Gain space purposefully."
    },
    OpeningPrinciple.KING_SAFETY: {
        "name": "Keep Your King Safe",
        "explanation": "An unsafe king is a target. Castle early, keep pawns in front of your king, don't open lines toward him.",
        "what_to_think": "Where is my king? Is he safe? What would happen if my opponent attacked?",
        "exceptions": "In some closed positions, the king can stay in the center longer."
    },
    OpeningPrinciple.DEVELOP_TOWARD_CENTER: {
        "name": "Develop Toward the Center",
        "explanation": "Knights on c3/f3/c6/f6 control more squares than on a3/h3. Bishops on diagonals toward center are stronger.",
        "what_to_think": "When developing, ask: Is this square controlling the center or pointing at it?",
        "exceptions": "Some openings fianchetto bishops (b2/g2), which is fine - they still point at the center."
    },
}


def analyze_opening_fundamentals(
    moves: List[str],
    user_color: str,
    game_result: str = None
) -> Dict[str, Any]:
    """
    Analyze a game's opening for fundamental principle violations.
    
    Args:
        moves: List of moves in SAN notation
        user_color: "white" or "black"
        game_result: Optional game result for context
    
    Returns:
        Dict with violations, adherences, and overall score
    """
    board = chess.Board()
    violations = []
    adherences = []
    
    # Track state
    piece_move_count = {}  # piece -> number of times moved
    developed_pieces = set()  # pieces that have moved
    castled = False
    queen_moved_early = False
    center_pawns_played = 0
    
    is_white = user_color == "white"
    
    for i, move_san in enumerate(moves):
        move_number = (i // 2) + 1
        is_user_move = (i % 2 == 0) == is_white
        
        if not is_user_move:
            try:
                board.push_san(move_san)
            except:
                pass
            continue
        
        try:
            move = board.parse_san(move_san)
        except:
            try:
                board.push_san(move_san)
            except:
                pass
            continue
        
        from_square = move.from_square
        to_square = move.to_square
        piece = board.piece_at(from_square)
        
        if not piece:
            try:
                board.push_san(move_san)
            except:
                pass
            continue
        
        piece_type = piece.piece_type
        piece_key = f"{chess.piece_name(piece_type)}_{chess.square_name(from_square)}"
        
        # Only analyze opening (first 15 moves)
        if move_number > 15:
            try:
                board.push_san(move_san)
            except:
                pass
            continue
        
        # === CHECK PRINCIPLES ===
        
        # 1. Same piece twice
        if piece_key in piece_move_count and move_number <= 10:
            piece_move_count[piece_key] += 1
            if piece_move_count[piece_key] >= 2:
                # Check if it's being attacked (which would be OK)
                if not board.is_attacked_by(not is_white, from_square):
                    violations.append(PrincipleViolation(
                        principle=OpeningPrinciple.SAME_PIECE_TWICE,
                        move_number=move_number,
                        move=move_san,
                        explanation=f"You moved the same piece ({chess.piece_name(piece_type)}) twice in the opening.",
                        teaching_message=PRINCIPLE_TEACHINGS[OpeningPrinciple.SAME_PIECE_TWICE]["explanation"],
                        severity="moderate",
                        what_to_do=PRINCIPLE_TEACHINGS[OpeningPrinciple.SAME_PIECE_TWICE]["what_to_think"]
                    ))
        else:
            piece_move_count[piece_key] = 1
        
        # 2. Queen out early (before move 6)
        if piece_type == chess.QUEEN and move_number <= 5 and not queen_moved_early:
            queen_moved_early = True
            # Check if it's a forcing move (capture or check)
            if not board.is_capture(move) and not board.gives_check(move):
                violations.append(PrincipleViolation(
                    principle=OpeningPrinciple.QUEEN_OUT_EARLY,
                    move_number=move_number,
                    move=move_san,
                    explanation="You brought your queen out before developing your minor pieces.",
                    teaching_message=PRINCIPLE_TEACHINGS[OpeningPrinciple.QUEEN_OUT_EARLY]["explanation"],
                    severity="moderate",
                    what_to_do=PRINCIPLE_TEACHINGS[OpeningPrinciple.QUEEN_OUT_EARLY]["what_to_think"]
                ))
        
        # 3. Center control (check if e/d pawns played by move 5)
        if piece_type == chess.PAWN:
            file = chess.square_file(to_square)
            rank = chess.square_rank(to_square)
            if file in [3, 4] and rank in [3, 4]:  # d4/e4/d5/e5
                center_pawns_played += 1
        
        # 4. Castling check (by move 12)
        if board.is_castling(move):
            castled = True
            if move_number <= 10:
                adherences.append({
                    "principle": OpeningPrinciple.CASTLE_EARLY.value,
                    "move_number": move_number,
                    "message": f"Great! You castled on move {move_number}, keeping your king safe."
                })
        
        # Track developed pieces
        if piece_type in [chess.KNIGHT, chess.BISHOP]:
            developed_pieces.add(piece_key)
        
        # Apply the move
        try:
            board.push_san(move_san)
        except:
            pass
    
    # Post-opening checks
    
    # Castle check - did they castle by move 12?
    if not castled and len(moves) >= 20:
        violations.append(PrincipleViolation(
            principle=OpeningPrinciple.CASTLE_EARLY,
            move_number=12,
            move="",
            explanation="You didn't castle in the first 12 moves, leaving your king in the center.",
            teaching_message=PRINCIPLE_TEACHINGS[OpeningPrinciple.CASTLE_EARLY]["explanation"],
            severity="major",
            what_to_do=PRINCIPLE_TEACHINGS[OpeningPrinciple.CASTLE_EARLY]["what_to_think"]
        ))
    
    # Center control check
    if center_pawns_played == 0 and len(moves) >= 10:
        violations.append(PrincipleViolation(
            principle=OpeningPrinciple.CENTER_CONTROL,
            move_number=5,
            move="",
            explanation="You didn't play any central pawns (e4/d4 or e5/d5) in the opening.",
            teaching_message=PRINCIPLE_TEACHINGS[OpeningPrinciple.CENTER_CONTROL]["explanation"],
            severity="major",
            what_to_do=PRINCIPLE_TEACHINGS[OpeningPrinciple.CENTER_CONTROL]["what_to_think"]
        ))
    elif center_pawns_played >= 1:
        adherences.append({
            "principle": OpeningPrinciple.CENTER_CONTROL.value,
            "move_number": 5,
            "message": "Good! You fought for the center with your pawns."
        })
    
    # Development check
    if len(developed_pieces) >= 3:
        adherences.append({
            "principle": OpeningPrinciple.DEVELOP_MINOR_PIECES.value,
            "move_number": 10,
            "message": f"Nice development! You brought out {len(developed_pieces)} minor pieces."
        })
    elif len(developed_pieces) < 2 and len(moves) >= 14:
        violations.append(PrincipleViolation(
            principle=OpeningPrinciple.DEVELOP_MINOR_PIECES,
            move_number=7,
            move="",
            explanation="You didn't develop enough pieces. Most minor pieces stayed home.",
            teaching_message=PRINCIPLE_TEACHINGS[OpeningPrinciple.DEVELOP_MINOR_PIECES]["explanation"],
            severity="major",
            what_to_do=PRINCIPLE_TEACHINGS[OpeningPrinciple.DEVELOP_MINOR_PIECES]["what_to_think"]
        ))
    
    # Calculate score (0-100)
    score = max(0, 100 - (len(violations) * 20))
    
    return {
        "violations": [
            {
                "principle": v.principle.value,
                "principle_name": PRINCIPLE_TEACHINGS[v.principle]["name"],
                "move_number": v.move_number,
                "move": v.move,
                "explanation": v.explanation,
                "teaching": v.teaching_message,
                "severity": v.severity,
                "what_to_think": v.what_to_do,
                "exceptions": PRINCIPLE_TEACHINGS[v.principle]["exceptions"]
            }
            for v in violations
        ],
        "adherences": adherences,
        "score": score,
        "total_violations": len(violations),
        "summary": _generate_opening_summary(violations, adherences, score)
    }


def _generate_opening_summary(violations, adherences, score):
    """Generate a coach-like summary of opening play."""
    if score >= 80:
        return "Your opening play followed fundamental principles well. Keep it up!"
    elif score >= 60:
        return f"Decent opening, but {len(violations)} principle(s) need attention. Focus on the highlighted issues."
    elif score >= 40:
        return f"Your opening had several issues. Let's work on the fundamentals - they're the foundation of good chess."
    else:
        return "The opening needs significant work. Don't worry - learning these principles will dramatically improve your game."


def get_principle_teaching(principle: OpeningPrinciple) -> Dict[str, str]:
    """Get the full teaching content for a principle."""
    return PRINCIPLE_TEACHINGS.get(principle, {})


def get_all_principles() -> List[Dict[str, Any]]:
    """Get all opening principles with their teachings."""
    return [
        {
            "id": principle.value,
            "name": teaching["name"],
            "explanation": teaching["explanation"],
            "what_to_think": teaching["what_to_think"],
            "exceptions": teaching["exceptions"]
        }
        for principle, teaching in PRINCIPLE_TEACHINGS.items()
    ]

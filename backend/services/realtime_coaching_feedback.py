"""
Realtime Coaching Feedback Service
===================================

This service generates comprehensive, human-like coaching feedback
after each user move on the CoachPlay page.

The feedback includes:
1. Assessment of the user's move (quality, what it achieved)
2. What the best move was and why
3. Explanation of the coach's counter-move
4. Personalized language based on player's understanding profile
5. Socratic questioning for mistakes/blunders
6. Pattern recognition from user's history
7. Memory references to past games

This is NOT a chatty analysis - it's a focused teaching moment
like a human coach sitting across from you.

Author: Built for truly personalized real-time coaching
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import chess

logger = logging.getLogger(__name__)


@dataclass
class MoveFeedback:
    """Comprehensive feedback for a single move"""
    # User's move assessment
    user_move: str
    user_move_quality: str  # "excellent", "good", "inaccuracy", "mistake", "blunder"
    user_move_eval_change: float  # centipawn change (negative = bad)
    
    # Best move explanation
    best_move: str
    best_move_explanation: str  # What the best move achieves
    pv_after_best: List[str]  # Best continuation
    
    # Coach's response
    coach_move: str
    coach_move_explanation: str  # Why the coach played this
    
    # Main coaching message (conversational, human-like)
    coaching_message: str
    
    # Optional: Specific tactical/positional elements
    threats_after_user_move: List[str]  # What opponent can now do
    missed_opportunities: List[str]  # What user could have done
    
    # Personalization
    relates_to_weakness: Optional[str]  # If this relates to a known weakness
    encouragement: Optional[str]  # For good moves
    
    # Trap suggestion
    trap_suggestion: Optional[Dict] = None  # If a trap is available from this position
    
    # NEW: Socratic mode - ask before telling
    socratic_question: Optional[str] = None  # Question to ask user before revealing answer
    expects_response: bool = False  # If true, wait for user response
    pattern_reference: Optional[str] = None  # Reference to recurring pattern
    memory_reference: Optional[str] = None  # Reference to past games/lessons
    
    # NEW: V5 Candidate moves (for unified coaching)
    candidate_moves: Optional[List[Dict]] = None  # Alternative moves with ideas
    golden_rule: Optional[str] = None  # Transferable learning
    consequence: Optional[str] = None  # Specific consequence of the move
    fen_before: Optional[str] = None  # Position before the move
    piece_moved: Optional[str] = None  # Which piece moved

    # Brilliant/sacrifice detection
    is_sacrifice: bool = False
    is_brilliant: bool = False

    def to_dict(self) -> Dict:
        # Compute best_move_uci from SAN + FEN for board arrow drawing
        best_move_uci = ""
        if self.best_move and self.fen_before and self.best_move != self.user_move:
            try:
                import chess as _chess
                _board = _chess.Board(self.fen_before)
                _move = _board.parse_san(self.best_move)
                best_move_uci = _move.uci()
            except Exception:
                pass

        result = {
            "user_move": self.user_move,
            "user_move_quality": self.user_move_quality,
            "user_move_eval_change": self.user_move_eval_change,
            "best_move": self.best_move,
            "best_move_uci": best_move_uci,
            "best_move_explanation": self.best_move_explanation,
            "pv_after_best": self.pv_after_best,
            "coach_move": self.coach_move,
            "coach_move_explanation": self.coach_move_explanation,
            "coaching_message": self.coaching_message,
            "threats_after_user_move": self.threats_after_user_move,
            "missed_opportunities": self.missed_opportunities,
            "relates_to_weakness": self.relates_to_weakness,
            "encouragement": self.encouragement,
            # Socratic mode fields
            "socratic_question": self.socratic_question,
            "expects_response": self.expects_response,
            "pattern_reference": self.pattern_reference,
            "memory_reference": self.memory_reference,
            # V5 fields
            "candidate_moves": self.candidate_moves,
            "golden_rule": self.golden_rule,
            "consequence": self.consequence,
            "fen_before": self.fen_before,
            "piece_moved": self.piece_moved,
            # Board annotations
            "is_sacrifice": self.is_sacrifice,
            "is_brilliant": self.is_brilliant,
        }
        if self.trap_suggestion:
            result["trap_suggestion"] = self.trap_suggestion
        return result


def _get_piece_name(piece: chess.Piece) -> str:
    """Get human-readable piece name"""
    names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king"
    }
    return names.get(piece.piece_type, "piece")


def _square_name(square: int) -> str:
    """Get algebraic square name"""
    return chess.square_name(square)


def _analyze_move_tactically(
    board_before: chess.Board,
    user_move_uci: str,
    best_move_uci: str,
    user_color: chess.Color
) -> Dict[str, Any]:
    """
    Analyze what the user's move and best move achieve tactically.
    Returns specific piece-square analysis.
    """
    result = {
        "user_move_captures": None,
        "best_move_captures": None,
        "user_move_attacks": [],
        "best_move_attacks": [],
        "threats_created": [],
        "threats_missed": []
    }
    
    try:
        user_move = chess.Move.from_uci(user_move_uci)
        best_move = chess.Move.from_uci(best_move_uci)
        
        # What user's move captures
        if board_before.is_capture(user_move):
            captured_piece = board_before.piece_at(user_move.to_square)
            if captured_piece:
                result["user_move_captures"] = _get_piece_name(captured_piece)
        
        # What best move captures
        if board_before.is_capture(best_move):
            captured_piece = board_before.piece_at(best_move.to_square)
            if captured_piece:
                result["best_move_captures"] = _get_piece_name(captured_piece)
        
        # Analyze position after user's move
        board_after_user = board_before.copy()
        board_after_user.push(user_move)
        
        # What threats exist against user after their move
        for move in board_after_user.legal_moves:
            if board_after_user.is_capture(move):
                target_piece = board_after_user.piece_at(move.to_square)
                if target_piece and target_piece.color == user_color:
                    threat = f"{_get_piece_name(board_after_user.piece_at(move.from_square))} takes {_get_piece_name(target_piece)} on {_square_name(move.to_square)}"
                    if threat not in result["threats_created"]:
                        result["threats_created"].append(threat)
        
        # What attacks best move creates
        board_after_best = board_before.copy()
        board_after_best.push(best_move)
        
        moving_piece = board_before.piece_at(best_move.from_square)
        if moving_piece:
            # Check what this piece now attacks
            for square in board_after_best.attacks(best_move.to_square):
                target = board_after_best.piece_at(square)
                if target and target.color != user_color:
                    attack = f"attacks {_get_piece_name(target)} on {_square_name(square)}"
                    result["best_move_attacks"].append(attack)
        
    except Exception as e:
        logger.warning(f"Tactical analysis error: {e}")
    
    return result


def _classify_move_quality(eval_before: float, eval_after: float, user_color: str, user_rating: int = 1200) -> str:
    """
    Classify move quality based on evaluation change AND player rating.
    
    Rating-aware thresholds ensure:
    - 800 players only hear about big blunders (not subtle inaccuracies)
    - 1600 players get feedback on positional inaccuracies too
    """
    # Calculate from user's perspective
    if user_color == "white":
        change = eval_after - eval_before
    else:
        change = eval_before - eval_after
    
    cp_change = change * 100  # Convert to centipawns
    
    # Rating-based thresholds (centipawns)
    if user_rating < 1000:
        # Beginners: only flag big blunders. Inaccuracies are noise at this level.
        thresholds = {"excellent": 20, "good": -30, "inaccuracy": -150, "mistake": -300}
    elif user_rating < 1400:
        # Improving: start showing mistakes, still lenient on inaccuracies
        thresholds = {"excellent": 20, "good": -20, "inaccuracy": -75, "mistake": -200}
    elif user_rating < 1800:
        # Intermediate: standard thresholds
        thresholds = {"excellent": 20, "good": -10, "inaccuracy": -50, "mistake": -150}
    else:
        # Advanced: tight thresholds, every centipawn matters
        thresholds = {"excellent": 10, "good": -5, "inaccuracy": -30, "mistake": -100}
    
    if cp_change >= thresholds["excellent"]:
        return "excellent"
    elif cp_change >= thresholds["good"]:
        return "good"
    elif cp_change >= thresholds["inaccuracy"]:
        return "inaccuracy"
    elif cp_change >= thresholds["mistake"]:
        return "mistake"
    else:
        return "blunder"


def _analyze_move_on_board(fen: str, move_san: str) -> Dict:
    """
    Analyze what a specific move DOES on a board. Returns concrete facts:
    - Is it a capture? What does it capture?
    - Does it give check?
    - What pieces does it attack from its new square?
    - Does it create a fork/pin/hanging piece?
    - Is it a pawn move (tempo-wasting) or piece move (active)?
    - What was the piece and where did it go?
    """
    result = {
        "is_capture": False, "captured": None,
        "gives_check": False,
        "attacks": [],  # [(piece_name, square_name), ...]
        "attacks_high_value": [],  # Queen, rook only
        "creates_fork": False, "fork_targets": [],
        "piece_moved": None, "from_sq": None, "to_sq": None,
        "is_pawn_move": False,
        "is_developing": False,  # Piece leaving back rank
    }
    try:
        board = chess.Board(fen)
        move = board.parse_san(move_san)
        piece = board.piece_at(move.from_square)
        if not piece:
            return result

        result["piece_moved"] = chess.piece_name(piece.piece_type)
        result["from_sq"] = chess.square_name(move.from_square)
        result["to_sq"] = chess.square_name(move.to_square)
        result["is_pawn_move"] = piece.piece_type == chess.PAWN
        result["is_capture"] = board.is_capture(move)
        if result["is_capture"]:
            captured = board.piece_at(move.to_square)
            if captured:
                result["captured"] = chess.piece_name(captured.piece_type)

        # Check if piece is leaving back rank (developing)
        back_rank = 0 if piece.color == chess.WHITE else 7
        if chess.square_rank(move.from_square) == back_rank and piece.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK):
            result["is_developing"] = True

        # Play the move and check what it does
        board.push(move)
        result["gives_check"] = board.is_check()

        # What does the piece attack from its new square?
        mover_color = not board.turn  # We just moved
        attacks = board.attacks(move.to_square)
        for sq in attacks:
            target = board.piece_at(sq)
            if target and target.color != mover_color and target.piece_type != chess.PAWN:
                name = chess.piece_name(target.piece_type)
                sq_name = chess.square_name(sq)
                result["attacks"].append((name, sq_name))
                if target.piece_type in (chess.QUEEN, chess.ROOK):
                    result["attacks_high_value"].append((name, sq_name))

        # Fork check
        if len(result["attacks"]) >= 2:
            result["creates_fork"] = True
            result["fork_targets"] = [(n, s) for n, s in result["attacks"]]

    except Exception:
        pass
    return result


def _contrastive_explanation(fen_before: str, user_move: str, best_move: str, user_rating: int = 1200) -> Optional[str]:
    """
    Generate a contrastive explanation: what your move does vs what the best move does.

    Returns a 1-2 sentence explanation like:
    "a3 is a pawn move that doesn't create any threats. Ng5 attacks f7 alongside
     your bishop — active pieces first, pawns later."

    Returns None if we can't generate anything meaningful (both moves are similar).
    """
    if not fen_before or not user_move or not best_move or user_move == best_move:
        return None

    yours = _analyze_move_on_board(fen_before, user_move)
    best = _analyze_move_on_board(fen_before, best_move)

    if not yours.get("piece_moved") or not best.get("piece_moved"):
        return None

    parts = []

    # === What's WRONG with your move ===
    your_doing = []
    if yours["is_pawn_move"] and not yours["is_capture"] and not yours["attacks"]:
        your_doing.append(f"{user_move} is a quiet pawn move that doesn't create threats")
    elif yours["is_pawn_move"] and not yours["is_capture"]:
        your_doing.append(f"{user_move} is a pawn push")
    elif not yours["attacks"] and not yours["is_capture"] and not yours["gives_check"]:
        your_doing.append(f"{user_move} doesn't create immediate pressure")

    # === What's GOOD about the best move ===
    best_doing = []
    if best["gives_check"]:
        best_doing.append(f"{best_move} gives check")
    if best["is_capture"] and best["captured"]:
        best_doing.append(f"{best_move} wins the {best['captured']}")
    if best["creates_fork"]:
        targets = [n for n, s in best["fork_targets"][:2]]
        best_doing.append(f"{best_move} attacks the {' and '.join(targets)} at the same time")
    elif best["attacks_high_value"]:
        targets = [f"{n} on {s}" for n, s in best["attacks_high_value"][:2]]
        best_doing.append(f"{best_move} puts pressure on the {', '.join(targets)}")
    elif best["attacks"] and not best["is_capture"]:
        targets = [f"{n}" for n, s in best["attacks"][:2]]
        best_doing.append(f"{best_move} attacks the {', '.join(targets)}")
    elif best["is_developing"]:
        best_doing.append(f"{best_move} develops the {best['piece_moved']} to an active square")

    if not your_doing and not best_doing:
        return None

    # Build the contrastive message
    if your_doing and best_doing:
        parts.append(f"{your_doing[0]}.")
        parts.append(f"{best_doing[0]}.")
    elif best_doing:
        parts.append(f"{best_doing[0]}.")
    elif your_doing:
        parts.append(f"{your_doing[0]}. {best_move} was stronger here.")

    # === Add a transferable principle ===
    principle = None
    if yours["is_pawn_move"] and not best["is_pawn_move"]:
        principle = "Active pieces first, pawns later."
    elif best["gives_check"] and not yours["gives_check"]:
        principle = "Always look for checks first."
    elif best["creates_fork"]:
        principle = "Look for moves that attack two things at once."
    elif best["is_capture"] and not yours["is_capture"]:
        principle = "Check for captures before making quiet moves."
    elif best["attacks_high_value"]:
        principle = "Put pressure on your opponent's big pieces."

    if principle:
        parts.append(principle)

    return " ".join(parts) if parts else None


def _move_context(move: str, tactical: Dict) -> str:
    """
    Generate position-aware context for a move.
    Returns a short phrase explaining what the move DOES on the board.
    """
    parts = []

    # What did the move capture?
    if tactical.get("user_move_captures"):
        parts.append(f"Takes the {tactical['user_move_captures']}.")

    # What does it attack?
    elif tactical.get("user_move_attacks"):
        attacks = tactical["user_move_attacks"][:2]
        if len(attacks) == 1:
            parts.append(f"Puts pressure on the {attacks[0]}.")
        else:
            parts.append(f"Attacks the {attacks[0]} and {attacks[1]}.")

    # Any threats to watch?
    if tactical.get("threats_created"):
        threats = tactical["threats_created"][:1]
        if threats:
            parts.append(f"Watch out — opponent now threatens {threats[0]}.")

    # Pieces left hanging?
    if tactical.get("pieces_hanging_after"):
        hanging = tactical["pieces_hanging_after"][:1]
        if hanging:
            parts.append(f"But your {hanging[0]} is now undefended.")

    if parts:
        return " " + " ".join(parts)
    return ""


def _generate_coaching_message(
    user_move: str,
    quality: str,
    best_move: str,
    tactical_analysis: Dict,
    coach_move: str,
    understanding_context: Optional[Dict] = None,
    user_name: str = "",
    user_rating: int = 1200,
    fen_before: str = "",
) -> Dict[str, Any]:
    """
    Generate a human-like coaching message in Indian-English style.
    Rating-aware: beginners get simpler, more encouraging messages.
    
    Returns dict with:
    - coaching_message: Main message
    - socratic_question: Question to ask (for mistakes/blunders)
    - encouragement: Encouragement text
    - pattern_reference: If relates to recurring pattern
    """
    import random
    
    result = {
        "coaching_message": "",
        "socratic_question": None,
        "encouragement": None,
        "expects_response": False
    }
    
    name = user_name or "friend"
    is_beginner = user_rating < 1000
    
    # ========== BRILLIANT MOVES ==========
    if quality == "brilliant":
        brilliant_phrases = [
            f"BRILLIANT! {user_move} — that sacrifice is absolutely stunning! You saw what the engine sees!",
            f"Wow {name}! {user_move} is a BRILLIANT sacrifice! This is the kind of move that makes chess beautiful!",
            f"Incredible! {user_move} — giving up material to win. This shows real calculation depth, {name}!",
            f"That's a world-class move! {user_move} — a sacrifice that was the only way to win. Outstanding vision!",
            f"BRILLIANT {name}! {user_move} — you calculated deeper than the surface. This is elite-level play!",
        ]
        result["coaching_message"] = random.choice(brilliant_phrases)
        result["encouragement"] = random.choice([
            "That was genuinely impressive.",
            "Moves like this show real chess understanding.",
            "Your tactical vision is sharp today!",
            "Remember this moment — this is your best chess.",
        ])
        return result

    # ========== BOOK MOVES (opening theory — don't praise) ==========
    if quality == "book":
        book_phrases = [
            f"{user_move}. Theory.",
            f"{user_move} — standard opening move.",
            f"{user_move}. Following the opening principles.",
        ]
        result["coaching_message"] = random.choice(book_phrases)
        result["user_move_quality"] = "book"
        return result

    # ========== EXCELLENT MOVES ==========
    if quality == "excellent":
        base = random.choice([
            f"Excellent! {user_move} is exactly right.",
            f"Yes! {user_move} — you saw it.",
            f"Beautiful! {user_move} is spot on.",
        ])
        # Add position-aware context
        context = _move_context(user_move, tactical_analysis)
        result["coaching_message"] = f"{base}{context}"
        result["encouragement"] = random.choice([
            "Keep this up!",
            "You're playing well today.",
            "This is good chess!",
        ])
        return result

    # ========== GOOD MOVES ==========
    elif quality == "good":
        base = random.choice([
            f"{user_move} is a solid choice.",
            f"Good thinking. {user_move} is reasonable here.",
            f"That works. {user_move} keeps things steady.",
        ])
        context = _move_context(user_move, tactical_analysis)
        result["coaching_message"] = f"{base}{context}"
        if best_move and best_move != user_move:
            result["coaching_message"] += f" {best_move} was slightly more precise, but your move is fine."
        return result
    
    # ========== INACCURACIES ==========
    elif quality == "inaccuracy":
        # Beginners: don't overwhelm with inaccuracy feedback, just nudge
        if is_beginner:
            result["coaching_message"] = f"{user_move} is fine for now. Let's keep going!"
            return result

        # Try contrastive explanation first (position-specific)
        contrast = _contrastive_explanation(fen_before, user_move, best_move, user_rating) if fen_before else None
        if contrast:
            result["coaching_message"] = contrast
        else:
            inaccuracy_phrases = [
                f"Hmm {name}, {user_move} is okay, but {best_move} was better here.",
                f"{user_move} is playable, but {best_move} was more accurate.",
                f"Not bad {name}, but {best_move} was the stronger choice.",
            ]
            result["coaching_message"] = random.choice(inaccuracy_phrases)

            if tactical_analysis.get("best_move_captures") and user_move != best_move:
                result["coaching_message"] += f" With {best_move} you could have won the {tactical_analysis['best_move_captures']}."
            elif tactical_analysis.get("best_move_attacks") and user_move != best_move:
                attacks = tactical_analysis["best_move_attacks"][:2]
                if attacks:
                    result["coaching_message"] += f" {best_move} would {', '.join(attacks)}."

        return result
    
    # ========== MISTAKES - CONTRASTIVE + SOCRATIC ==========
    elif quality == "mistake":
        # Try contrastive explanation (position-specific)
        contrast = _contrastive_explanation(fen_before, user_move, best_move, user_rating) if fen_before else None

        if is_beginner:
            # Beginners: direct, simple. Use contrast if available.
            if contrast:
                result["coaching_message"] = contrast
            else:
                reveal_parts = [f"Careful {name}! {user_move} loses some advantage."]
                if user_move != best_move:
                    reveal_parts.append(f"Try {best_move} instead.")
                result["coaching_message"] = " ".join(reveal_parts)
            result["encouragement"] = "Good effort though. Let's keep going!"
            return result

        # Socratic question
        socratic_questions = [
            f"{name}, interesting choice with {user_move}. What was your thinking?",
            f"Hmm {user_move}. Walk me through it {name} — why this move?",
            f"Okay {name}. Before I say anything — what was the idea behind {user_move}?",
        ]
        result["socratic_question"] = random.choice(socratic_questions)
        result["expects_response"] = True

        # Reveal: use contrast if available, fall back to generic
        if contrast:
            result["coaching_message"] = contrast
        else:
            reveal_parts = [f"Dekho {name}, that {user_move} lets some advantage slip."]
            if tactical_analysis.get("threats_created"):
                reveal_parts.append(f"Now I can play {tactical_analysis['threats_created'][0]}.")
            if user_move != best_move:
                reveal_parts.append(f"The move to find was {best_move}.")
            result["coaching_message"] = " ".join(reveal_parts)

        result["encouragement"] = random.choice([
            "Koi baat nahi. Let's learn from this.",
            "It's okay. This is how we improve.",
            "Don't worry. Even strong players miss things.",
        ])
        return result
    
    # ========== BLUNDERS - CONTRASTIVE + SOCRATIC ==========
    elif quality == "blunder":
        contrast = _contrastive_explanation(fen_before, user_move, best_move, user_rating) if fen_before else None

        if is_beginner:
            if contrast:
                result["coaching_message"] = contrast
            else:
                reveal_parts = [f"Oops {name}! {user_move} loses material."]
                if tactical_analysis.get("best_move_captures"):
                    reveal_parts.append(f"You could have played {best_move} and won the {tactical_analysis['best_move_captures']}!")
                elif user_move != best_move:
                    reveal_parts.append(f"The safe move was {best_move}.")
                result["coaching_message"] = " ".join(reveal_parts)
            result["socratic_question"] = "Before your next move, check: is any of your pieces hanging?"
            result["encouragement"] = "It's okay! Just check for hanging pieces before every move."
            return result

        # Socratic question
        socratic_questions = [
            f"Arre {name}! {user_move}... what were you thinking?",
            f"{name}, hold on. That {user_move} — explain your reasoning.",
            f"Wait {name}. {user_move}? What did you see here?",
        ]
        result["socratic_question"] = random.choice(socratic_questions)
        result["expects_response"] = True

        # Reveal: use contrast if available
        if contrast:
            result["coaching_message"] = contrast
        else:
            reveal_parts = [f"See {name}, that {user_move} was a serious mistake."]
            if tactical_analysis.get("best_move_captures"):
                reveal_parts.append(f"You could have won material with {best_move} — takes the {tactical_analysis['best_move_captures']}!")
            elif tactical_analysis.get("threats_created"):
                reveal_parts.append(f"That allows {tactical_analysis['threats_created'][0]}.")
            else:
                reveal_parts.append(f"The position needed {best_move}.")
            result["coaching_message"] = " ".join(reveal_parts)

        result["encouragement"] = random.choice([
            "But it's okay. Everyone blunders sometimes. Even Magnus!",
            "Koi baat nahi. Let's understand why and move on.",
            "This is tough, but we learn from these moments.",
        ])
        return result
    
    # Fallback
    result["coaching_message"] = f"I played {coach_move}."
    return result


async def generate_move_feedback(
    db,
    session_id: str,
    move_number: int,
    user_id: str,
    use_chess_brain: bool = True  # NEW: Enable Chess Brain by default
) -> Optional[MoveFeedback]:
    """
    Generate comprehensive feedback for a specific move in a session.
    
    Args:
        db: Database connection
        session_id: Coach play session ID
        move_number: Which user move to analyze (1-indexed)
        user_id: User ID for personalization
        use_chess_brain: If True, use the new deterministic Chess Brain engine
    
    Returns:
        MoveFeedback object with all analysis
    """
    from services.chess_understanding import get_chess_understanding, get_coaching_context_from_understanding
    
    # Get session
    session = await db.coach_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not session:
        return None
    
    move_history = session.get("move_history", [])
    user_color = session.get("user_color", "white")
    
    # Find the user's move at move_number
    user_move_data = None
    coach_move_data = None
    user_move_idx = 0
    
    for i, m in enumerate(move_history):
        if m.get("by") == "player":
            user_move_idx += 1
            if user_move_idx == move_number:
                user_move_data = m
                # Coach's response is the next move
                if i + 1 < len(move_history) and move_history[i + 1].get("by") == "coach":
                    coach_move_data = move_history[i + 1]
                break
    
    if not user_move_data:
        return None
    
    # Extract data
    user_move = user_move_data.get("move", "")
    fen_before = user_move_data.get("fen_before", "")
    eval_before = user_move_data.get("eval_before", 0)
    eval_after = user_move_data.get("eval_after", 0)
    best_move = user_move_data.get("best_move", user_move)
    
    coach_move = coach_move_data.get("move", "") if coach_move_data else ""
    
    # Classify quality using rating-aware thresholds
    user_rating = session.get("user_rating", 1200)
    quality = _classify_move_quality(eval_before, eval_after, user_color, user_rating)

    # === OPENING BOOK CHECK ===
    # In the first ~10 moves, if eval barely changed, this is likely a book move.
    # Don't praise book moves — the coach should save energy for real moments.
    # "book" quality suppresses coaching message (handled in _generate_coaching_message).
    total_moves = len(move_history)
    if total_moves <= 20 and quality in ("good", "excellent"):  # 20 half-moves = ~10 moves per side
        cp_change = abs(eval_after - eval_before) * 100
        if cp_change < 30:  # Less than 0.3 pawn swing = standard theory
            quality = "book"
    
    # ===== CHESS BRAIN INTEGRATION =====
    # Try to get deterministic coaching from Chess Brain
    chess_brain_feedback = None
    if use_chess_brain and fen_before and user_move:
        try:
            from services.chess_brain.integration import get_chess_brain_feedback
            
            stockfish_analysis = {
                "best_move": best_move,
                "eval_before": eval_before,
                "eval_after": eval_after,
                "pv": user_move_data.get("pv_after_best", [])
            }
            
            chess_brain_feedback = await get_chess_brain_feedback(
                db=db,
                fen_before=fen_before,
                user_move=user_move,
                user_id=user_id,
                session_id=session_id,
                stockfish_analysis=stockfish_analysis,
                user_color=user_color,
                move_number=move_number,
                time_spent=user_move_data.get("time_spent"),
            )
            
            # Use Chess Brain's quality assessment if available
            if chess_brain_feedback.get("is_chess_brain"):
                quality = chess_brain_feedback.get("user_move_quality", quality)
                logger.info(f"Chess Brain analyzed move {user_move}: {quality}, mode={chess_brain_feedback.get('teaching_mode')}")
        except Exception as e:
            logger.warning(f"Chess Brain feedback failed, falling back: {e}")
    # ===== END CHESS BRAIN INTEGRATION =====
    
    # ===== SACRIFICE & BRILLIANT DETECTION =====
    is_sacrifice = False
    is_brilliant = False
    if fen_before and user_move and quality in ("best", "excellent", "good"):
        try:
            sac_board = chess.Board(fen_before)
            move_obj = sac_board.parse_san(user_move)
            if sac_board.is_capture(move_obj):
                piece_vals = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 0}
                moving = sac_board.piece_at(move_obj.from_square)
                captured = sac_board.piece_at(move_obj.to_square)
                if moving and captured:
                    mv = piece_vals.get(moving.piece_type, 0)
                    cv = piece_vals.get(captured.piece_type, 0)
                    if mv > cv + 1:
                        is_sacrifice = True
                        # Check if it was the only good move (eval improved or stayed)
                        cp_diff = eval_after - eval_before
                        if user_color == "black":
                            cp_diff = -cp_diff
                        if cp_diff >= -10:  # Position stayed good or improved
                            is_brilliant = True
                            quality = "brilliant"
        except Exception:
            pass

    # Tactical analysis
    tactical = {}
    if fen_before and user_move:
        try:
            board = chess.Board(fen_before)
            user_move_uci = user_move_data.get("uci", "")
            best_move_uci = ""
            
            # Parse best move to UCI
            if best_move:
                try:
                    best_move_obj = board.parse_san(best_move)
                    best_move_uci = best_move_obj.uci()
                except chess.InvalidMoveError:
                    pass
            
            if user_move_uci and best_move_uci:
                user_chess_color = chess.WHITE if user_color == "white" else chess.BLACK
                tactical = _analyze_move_tactically(board, user_move_uci, best_move_uci, user_chess_color)
        except Exception as e:
            logger.warning(f"Tactical analysis failed: {e}")
    
    # Get player understanding for personalization
    understanding_context = None
    try:
        understanding = await get_chess_understanding(db, user_id)
        understanding_context = get_coaching_context_from_understanding(understanding)
    except Exception as e:
        logger.warning(f"Could not get understanding context: {e}")
    
    # Get pattern context from memory (for recurring mistakes)
    pattern_reference = None
    memory_reference = None
    
    if quality in ["mistake", "blunder"] and db is not None:
        try:
            from services.coach_memory import get_realtime_pattern_context, record_in_game_mistake
            
            # Determine mistake type from tactical analysis
            mistake_type = "tactical_miss"
            if tactical.get("best_move_captures"):
                mistake_type = "missed_tactic"
            elif tactical.get("threats_created"):
                mistake_type = "hanging_piece"
            
            # Get pattern context
            pattern_ctx = await get_realtime_pattern_context(db, user_id, mistake_type)
            
            if pattern_ctx.get("is_recurring"):
                pattern_reference = pattern_ctx.get("pattern_message")
            
            if pattern_ctx.get("memory_reference"):
                memory_reference = pattern_ctx.get("memory_reference")
            
            # Record this mistake for future tracking
            move_number = user_move_data.get("move_number", 0)
            await record_in_game_mistake(
                db, user_id, mistake_type, move_number, fen_before
            )
        except Exception as e:
            logger.warning(f"Could not get pattern context: {e}")
    
    # Generate main coaching message
    # Prefer Chess Brain output if available, otherwise fall back to rule-based generation
    if chess_brain_feedback and chess_brain_feedback.get("is_chess_brain"):
        # Use Chess Brain's deterministic coaching
        coaching_message = chess_brain_feedback.get("coaching_message", "")
        socratic_question = chess_brain_feedback.get("socratic_question")
        expects_response = False  # Chess Brain doesn't use dialogue mode yet
        
        # Use Chess Brain's best move explanation if available
        best_move_explanation = chess_brain_feedback.get("best_move_explanation", "")
        
        # Use Chess Brain's encouragement
        encouragement = chess_brain_feedback.get("encouragement")
        
        logger.info(f"Using Chess Brain coaching: {chess_brain_feedback.get('teaching_mode')}")
    else:
        # Fall back to legacy coaching message generation
        coaching_result = _generate_coaching_message(
            user_move=user_move,
            quality=quality,
            best_move=best_move,
            tactical_analysis=tactical,
            coach_move=coach_move,
            understanding_context=understanding_context,
            user_name="",
            user_rating=user_rating,
            fen_before=fen_before,
        )
        
        coaching_message = coaching_result.get("coaching_message", "")
        socratic_question = coaching_result.get("socratic_question")
        expects_response = coaching_result.get("expects_response", False)

        # Inject pattern memory into coaching message (the "I know you" layer)
        if pattern_reference and quality in ["mistake", "blunder"]:
            coaching_message = f"{pattern_reference} {coaching_message}"
        if memory_reference and quality in ["mistake", "blunder"]:
            coaching_message = f"{coaching_message} {memory_reference}"

        # Generate best move explanation
        best_move_explanation = ""
        if best_move and best_move != user_move:
            if tactical.get("best_move_captures"):
                best_move_explanation = f"Wins the {tactical['best_move_captures']}"
            elif tactical.get("best_move_attacks"):
                best_move_explanation = f"Creates pressure: {', '.join(tactical['best_move_attacks'][:2])}"
            else:
                best_move_explanation = "Maintains better position"
        
        # Encouragement for good moves
        encouragement = coaching_result.get("encouragement")
        if not encouragement and quality in ["excellent", "good"]:
            encouragement = "Keep it up!" if quality == "good" else "That's the move!"

    # ═══ MID-GAME ADAPTATION — adjust based on how user is playing THIS game ═══
    adaptation_nudge = None
    try:
        from services.midgame_adaptation import compute_game_adaptation
        adaptation = compute_game_adaptation(move_history, user_color, [])
        adaptation_nudge = adaptation.get("nudge")

        # If rushing + making mistakes, prepend the nudge
        if adaptation_nudge and quality in ("mistake", "blunder"):
            coaching_message = f"{adaptation_nudge} {coaching_message}"
        elif adaptation_nudge and adaptation.get("tilt_risk"):
            coaching_message = f"{adaptation_nudge} {coaching_message}"

        # If on hot streak, boost encouragement
        if adaptation.get("momentum") == "hot_streak" and quality in ("excellent", "good", "best", "brilliant"):
            streak_count = adaptation.get("good_moves_streak", 0)
            if streak_count >= 3 and not encouragement:
                encouragement = f"{streak_count} good moves in a row. You're locked in."
    except Exception as adapt_err:
        logger.debug(f"Mid-game adaptation failed (non-fatal): {adapt_err}")

    # ═══ APPLY COACH VOICE — personality wrapper ═══
    try:
        from services.coach_voice import apply_coach_voice

        # Determine intensity from move quality
        voice_intensity = "calm"
        if quality == "brilliant":
            voice_intensity = "brilliant"
        elif quality in ("mistake", "blunder"):
            voice_intensity = "firm"
            if is_sacrifice:
                voice_intensity = "calm"  # Sacrifice that lost = still brave

        # Get relationship context
        games_together = 0
        try:
            games_together = await db.coach_sessions.count_documents({"user_id": user_id})
        except Exception:
            pass

        voice_context = {
            "games_together": games_together,
            "pattern_count": 0,  # Pattern count from realtime context
            "is_recovery": False,
            "move_quality": quality,
        }

        coaching_message = apply_coach_voice(coaching_message, voice_intensity, voice_context)
    except Exception as voice_err:
        logger.debug(f"Coach voice wrapper failed (non-fatal): {voice_err}")

    # Generate coach move explanation (used by both paths)
    coach_explanation = ""
    if coach_move and fen_before:
        try:
            board_after_user = chess.Board(fen_before)
            user_move_obj = board_after_user.parse_san(user_move)
            board_after_user.push(user_move_obj)
            coach_move_obj = board_after_user.parse_san(coach_move)

            # What does the coach's move do?
            if board_after_user.is_capture(coach_move_obj):
                captured = board_after_user.piece_at(coach_move_obj.to_square)
                if captured:
                    piece_names = {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen"}
                    cn = piece_names.get(captured.piece_type, "piece")
                    coach_explanation = f"I take your {cn} with {coach_move}."

            if not coach_explanation:
                board_after_user.push(coach_move_obj)
                if board_after_user.is_check():
                    coach_explanation = f"{coach_move} — check. Protect your king."
                else:
                    moving = board_after_user.piece_at(coach_move_obj.to_square)
                    if moving:
                        piece_names = {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen", 6: "king"}
                        pn = piece_names.get(moving.piece_type, "piece")
                        sq = chess.square_name(coach_move_obj.to_square)
                        coach_explanation = f"I move my {pn} to {sq}."
        except Exception:
            pass

    if not coach_explanation and coach_move:
        if quality in ["mistake", "blunder"] and tactical.get("threats_created"):
            coach_explanation = "Takes advantage of the error."
        else:
            coach_explanation = f"I play {coach_move}."
    
    # Check if relates to known weakness (used by both paths)
    relates_to = None
    if understanding_context:
        weakness = understanding_context.get("primary_weakness", "")
        if weakness:
            if "tactical" in weakness.lower() and quality in ["mistake", "blunder"]:
                relates_to = f"This relates to your {weakness} - keep practicing!"
            elif "consistency" in weakness.lower() and quality in ["mistake", "blunder"]:
                relates_to = "Stay focused - you know better than this!"
    
    # Check if a trap is available from this position
    trap_suggestion = None
    try:
        from services.trap_library import get_trap_for_position
        
        # Get the move history as SAN moves
        san_history = [m.get("move") for m in move_history if m.get("move")]
        trap_data = get_trap_for_position(san_history)
        
        if trap_data and trap_data.get("moves_until_trap", 999) <= 4:
            # A trap is within reach!
            trap_suggestion = {
                "name": trap_data.get("name"),
                "description": trap_data.get("description"),
                "setup_remaining": trap_data.get("setup_remaining", []),
                "moves_until_trap": trap_data.get("moves_until_trap", 0),
                "result_type": trap_data.get("result_type"),
                "opening_key": trap_data.get("opening_key")
            }
    except Exception as e:
        logger.warning(f"Error checking for traps: {e}")
    
    # Build V5 candidate moves
    candidate_moves = []
    if best_move and best_move != user_move:
        # Best move as primary candidate
        candidate_moves.append({
            "move": best_move,
            "idea": best_move_explanation or f"{best_move} was the engine's top choice",
            "type": _determine_move_type(tactical, best_move),
            "is_best": True
        })
    
    # Add missed opportunities as alternative candidates
    if tactical.get("best_move_attacks"):
        for i, attack in enumerate(tactical["best_move_attacks"][:2]):
            if i == 0:
                continue  # Skip first (already covered by best_move)
            candidate_moves.append({
                "move": attack.split()[0] if " " in attack else attack,
                "idea": attack,
                "type": "tactical",
                "is_best": False
            })
    
    # Determine consequence (what happens after the user's move)
    consequence = None
    if quality in ["mistake", "blunder"]:
        if tactical.get("threats_created"):
            consequence = f"After {user_move}, your opponent gets: {', '.join(tactical['threats_created'][:2])}"
        elif tactical.get("user_move_captures") is None and tactical.get("best_move_captures"):
            consequence = f"You missed winning the {tactical['best_move_captures']}"
    
    # Determine golden rule based on the type of mistake
    golden_rule = pattern_reference
    if not golden_rule and quality in ["mistake", "blunder"]:
        if fen_before:
            try:
                board = chess.Board(fen_before)
                move_obj = board.parse_san(user_move)
                piece = board.piece_at(move_obj.from_square)
                if piece:
                    if piece.piece_type == chess.KNIGHT:
                        to_file = chess.square_file(move_obj.to_square)
                        to_rank = chess.square_rank(move_obj.to_square)
                        if to_file in [0, 7] or to_rank in [0, 7]:
                            golden_rule = "Knights on the rim are dim! They have fewer squares to jump to."
                        else:
                            golden_rule = "Every piece needs a job! Ask: what is this piece doing for me?"
                    elif piece.piece_type == chess.PAWN:
                        golden_rule = "Pawns can NEVER go back! Every pawn move creates a weakness somewhere."
                    elif piece.piece_type == chess.BISHOP:
                        golden_rule = "Bishops need OPEN diagonals. If pawns block them, they're sad!"
                    elif piece.piece_type == chess.QUEEN:
                        golden_rule = "Don't bring the Queen out too early - she'll get chased around!"
            except Exception:
                pass
    
    # Get piece moved for fun language
    piece_moved = None
    if fen_before:
        try:
            board = chess.Board(fen_before)
            move_obj = board.parse_san(user_move)
            piece = board.piece_at(move_obj.from_square)
            if piece:
                piece_moved = _get_piece_name(piece)
        except Exception:
            pass
    
    return MoveFeedback(
        user_move=user_move,
        user_move_quality=quality,
        user_move_eval_change=(eval_after - eval_before) * 100,
        best_move=best_move,
        best_move_explanation=best_move_explanation,
        pv_after_best=user_move_data.get("pv_after_best", [])[:4],
        coach_move=coach_move,
        coach_move_explanation=coach_explanation,
        coaching_message=coaching_message,
        threats_after_user_move=tactical.get("threats_created", [])[:3],
        missed_opportunities=tactical.get("best_move_attacks", [])[:3],
        relates_to_weakness=relates_to,
        encouragement=encouragement,
        trap_suggestion=trap_suggestion,
        # Socratic mode fields
        socratic_question=socratic_question,
        expects_response=expects_response,
        pattern_reference=pattern_reference,
        memory_reference=memory_reference,
        # V5 fields
        candidate_moves=candidate_moves if candidate_moves else None,
        golden_rule=golden_rule,
        consequence=consequence,
        fen_before=fen_before,
        piece_moved=piece_moved,
        is_sacrifice=is_sacrifice,
        is_brilliant=is_brilliant
    )


def _determine_move_type(tactical: Dict, move: str) -> str:
    """Determine the strategic type of a move."""
    if tactical.get("best_move_captures"):
        return "tactical"
    if tactical.get("best_move_attacks"):
        return "counter_attack"
    return "positional"


async def get_last_move_feedback(db, session_id: str, user_id: str) -> Optional[Dict]:
    """
    Get feedback for the most recent user move in a session.
    This is the main API for the frontend.
    """
    # Get session to find last move number
    session = await db.coach_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not session:
        return None
    
    move_history = session.get("move_history", [])
    
    # Count user moves
    user_move_count = sum(1 for m in move_history if m.get("by") == "player")
    
    if user_move_count == 0:
        return None
    
    # Generate feedback for the last user move
    feedback = await generate_move_feedback(db, session_id, user_move_count, user_id)
    
    if feedback:
        return feedback.to_dict()
    
    return None

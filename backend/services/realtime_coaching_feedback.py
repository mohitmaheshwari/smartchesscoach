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

    # CCT discipline grace — set when the user played a forcing move
    # (check / capture / threat) in a position where the engine's best
    # was also forcing. Even if not THE best, we don't tag this as a
    # blunder — the discipline is what matters mid-game. Frontend uses
    # this to soften penalty framing.
    cct_discipline_held: bool = False
    cct_voice_line: Optional[str] = None

    # Opening-theory note — fired when in a known opening's first
    # ~12 moves. Pairs the universal teaching rule (e.g. "pieces
    # before pawns") with opening-specific context ("In the Queen's
    # Gambit, you recover c4 with Bxc4 and keep central control.").
    # See services/opening_theory_note.py.
    opening_theory_note: Optional[Dict] = None

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
            # CCT discipline
            "cct_discipline_held": self.cct_discipline_held,
            "cct_voice_line": self.cct_voice_line,
            # Opening-theory note (None when not in a known opening
            # or past the opening phase)
            "opening_theory_note": self.opening_theory_note,
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


def _find_opponent_threat_after_move(fen_before: str, user_move_san: str) -> Optional[Dict]:
    """
    After the user's move, what's the opponent's best threat?

    Scans opponent's legal moves for the best "winning" capture or tactic.
    Returns dict with threat details, or None.

    This is what answers "why is Qb3 a mistake?" — because opponent can now
    play Nxb4 winning a pawn, or similar.
    """
    try:
        board = chess.Board(fen_before)
        move = board.parse_san(user_move_san)
        board.push(move)

        piece_vals = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                     chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}

        best_threat = None
        best_gain = 0

        for opp_move in board.legal_moves:
            if not board.is_capture(opp_move):
                continue

            captured = board.piece_at(opp_move.to_square)
            if not captured:
                continue

            attacker = board.piece_at(opp_move.from_square)
            if not attacker:
                continue

            cap_val = piece_vals.get(captured.piece_type, 0)
            att_val = piece_vals.get(attacker.piece_type, 0)

            # Check if square is defended
            board.push(opp_move)
            our_color = not board.turn  # The side that just moved (opponent)
            defended = board.is_attacked_by(board.turn, opp_move.to_square)
            board.pop()

            # Calculate material gain
            if not defended:
                gain = cap_val  # Free capture
            elif cap_val >= att_val:
                gain = cap_val - att_val  # Winning or equal trade
            else:
                continue  # Bad trade, not a threat

            if gain > best_gain:
                best_gain = gain
                best_threat = {
                    "move_san": board.san(opp_move),
                    "captured": chess.piece_name(captured.piece_type),
                    "captured_square": chess.square_name(opp_move.to_square),
                    "gain": gain,
                    "is_free": not defended,
                }

        return best_threat if best_gain >= 1 else None
    except Exception:
        return None


def _find_hanging_after_move(fen_before: str, user_move_san: str) -> Optional[str]:
    """After the user's move, does any of their pieces end up hanging?
    Returns the piece+square that's now undefended, or None."""
    try:
        board = chess.Board(fen_before)
        move = board.parse_san(user_move_san)
        board.push(move)
        our_color = not board.turn  # We just moved
        # Find pieces that are attacked and undefended (or underdefended)
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if not piece or piece.color != our_color or piece.piece_type in (chess.PAWN, chess.KING):
                continue
            attackers = list(board.attackers(board.turn, sq))
            if not attackers:
                continue
            defenders = list(board.attackers(our_color, sq))
            if len(defenders) == 0:
                # Hanging!
                return f"{chess.piece_name(piece.piece_type)} on {chess.square_name(sq)}"
            # Underdefended (cheaper attacker than piece value)
            if len(attackers) > len(defenders):
                piece_val = {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}.get(piece.piece_type, 0)
                cheapest = min(
                    ({chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}.get(
                        board.piece_at(a).piece_type, 0) for a in attackers if board.piece_at(a)),
                    default=99,
                )
                if cheapest < piece_val:
                    return f"{chess.piece_name(piece.piece_type)} on {chess.square_name(sq)}"
    except Exception:
        pass
    return None


def _attacks_center(fen_before: str, move_san: str) -> bool:
    """Does the move attack or occupy a central square (d4/e4/d5/e5)?"""
    try:
        board = chess.Board(fen_before)
        move = board.parse_san(move_san)
        center = {chess.D4, chess.E4, chess.D5, chess.E5}
        if move.to_square in center:
            return True
        board.push(move)
        attacks = board.attacks(move.to_square)
        return bool(attacks & chess.SquareSet(center))
    except Exception:
        return False


def _is_opening_phase(fen_before: str) -> bool:
    """
    Opening = early in game (first 10 moves per side) AND pieces still on back rank.
    Requires BOTH — a move 15 position isn't opening even with lots of pieces.
    """
    try:
        board = chess.Board(fen_before)
        if board.fullmove_number > 10:
            return False
        # Count minor pieces still on their starting back rank
        undeveloped = 0
        for color in (chess.WHITE, chess.BLACK):
            back_rank = 0 if color == chess.WHITE else 7
            for sq in chess.SQUARES:
                p = board.piece_at(sq)
                if p and p.color == color and p.piece_type in (chess.KNIGHT, chess.BISHOP):
                    if chess.square_rank(sq) == back_rank:
                        undeveloped += 1
        # Opening if at least 3 minor pieces still undeveloped (across both sides)
        return undeveloped >= 3
    except Exception:
        return False


def _contrastive_explanation(fen_before: str, user_move: str, best_move: str, user_rating: int = 1200) -> Optional[str]:
    """
    Generate a short, evidence-based coaching message with a memorable rule.

    Phase-aware: in the opening, focuses on development/center principles.
    In middlegame/endgame, focuses on tactics/activity.

    Only returns a message when there's REAL substance — otherwise returns None
    so the caller can suppress empty feedback (no "playable but more accurate" filler).
    """
    if not fen_before or not user_move or not best_move or user_move == best_move:
        return None

    yours = _analyze_move_on_board(fen_before, user_move)
    best = _analyze_move_on_board(fen_before, best_move)

    if not yours.get("piece_moved") or not best.get("piece_moved"):
        return None

    # Context
    hanging = _find_hanging_after_move(fen_before, user_move)
    opp_threat = _find_opponent_threat_after_move(fen_before, user_move)
    is_opening = _is_opening_phase(fen_before)
    best_attacks_center = _attacks_center(fen_before, best_move)
    yours_attacks_center = _attacks_center(fen_before, user_move)

    wrong_msg = None
    best_msg = None
    rule = None

    # === PRIORITY 1: hanging piece (always critical) ===
    if hanging:
        wrong_msg = f"{user_move} hangs your {hanging}"
        rule = "Before every move, ask: is my piece safe?"

    # === PRIORITY 1.5: opponent threat (the real reason most mistakes hurt) ===
    elif opp_threat:
        if opp_threat["is_free"]:
            wrong_msg = f"After {user_move}, I can play {opp_threat['move_san']} winning your {opp_threat['captured']}"
        else:
            wrong_msg = f"After {user_move}, I can play {opp_threat['move_san']} winning material"
        rule = "Before your move, check every capture I can make."

    # === PRIORITY 2: OPENING PRINCIPLES ===
    elif is_opening:
        # Developing vs non-developing
        if best["is_developing"] and not yours["is_developing"] and yours["is_pawn_move"]:
            wrong_msg = f"{user_move} doesn't develop a piece"
            best_msg = f"{best_move} develops your {best['piece_moved']} to an active square"
            rule = "In the opening, pieces before pawns."
        # Center control
        elif best_attacks_center and not yours_attacks_center:
            wrong_msg = f"{user_move} ignores the center"
            best_msg = f"{best_move} fights for the center"
            rule = "In the opening, control d4/e4/d5/e5."
        # Moving developed pieces twice (slow)
        elif not yours["is_developing"] and best["is_developing"]:
            wrong_msg = f"{user_move} delays development"
            best_msg = f"{best_move} brings out your {best['piece_moved']}"
            rule = "Develop all pieces before attacking."

    # === PRIORITY 3: TACTICAL (middlegame/endgame) ===
    if not wrong_msg and not best_msg:
        # Best move creates a concrete tactic
        if best["gives_check"] and best["is_capture"]:
            best_msg = f"{best_move} is check and wins the {best['captured']}"
            rule = "Always check for checks and captures first."
        elif best["is_capture"] and best["captured"] and not yours["is_capture"]:
            best_msg = f"{best_move} wins the {best['captured']}"
            rule = "Scan captures before quiet moves."
        elif best["creates_fork"]:
            targets = [n for n, s in best["fork_targets"][:2]]
            best_msg = f"{best_move} attacks my {' and '.join(targets)} together"
            rule = "Find forks — one piece hitting two."
        elif best["gives_check"] and not yours["gives_check"]:
            best_msg = f"{best_move} gives check"
            rule = "Always look for checks first."
        elif best["attacks_high_value"]:
            target = best["attacks_high_value"][0][0]
            best_msg = f"{best_move} attacks my {target}"
            rule = "Hit the big pieces."
        elif yours["is_pawn_move"] and not best["is_pawn_move"]:
            wrong_msg = f"{user_move} is a slow pawn move"
            best_msg = f"{best_move} puts a piece in play"
            rule = "Move pieces, not pawns."

    # If we couldn't find any substance, don't say anything
    if not wrong_msg and not best_msg:
        return None

    # === Assemble ===
    parts = []
    if wrong_msg:
        parts.append(f"{wrong_msg}.")
    if best_msg:
        parts.append(f"{best_msg}." if not wrong_msg else f"Better: {best_msg}.")

    if rule:
        parts.append(f"**Rule: {rule}**")

    return " ".join(parts)


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


def _try_meta_pattern(
    fen_before: str,
    user_move: str,
    best_move: str,
    eval_before: float,
    eval_after: float,
    user_color: str,
    user_rating: int,
    quality: str,
    tactical_analysis: Dict,
    extra_ctx: Optional[Dict] = None,
) -> Optional[Dict[str, str]]:
    """
    Try to match a meta-pattern (the 25 composition rules). If one matches,
    return its message + rule. Otherwise None (caller falls back to contrastive).

    Uses existing signal detection from tactical_analysis where available;
    the rest is derived from the parameters.
    """
    if not fen_before or not user_move:
        return None
    try:
        from services.meta_patterns import MetaContext, detect_meta_patterns

        extra_ctx = extra_ctx or {}

        # Build the context from what's available
        ctx = MetaContext(
            fen_before=fen_before,
            user_move=user_move,
            best_move=best_move,
            eval_before=eval_before,
            eval_after=eval_after,
            user_color=user_color,
            user_rating=user_rating,
            move_history=extra_ctx.get("move_history", []),
            move_number=extra_ctx.get("move_number", 1),
            time_spent=extra_ctx.get("time_spent", 0) or 0,
            time_remaining=extra_ctx.get("time_remaining", 999) or 999,
            game_phase=extra_ctx.get("game_phase", "middlegame"),
            # Derived flags
            is_impulse_move=(extra_ctx.get("time_spent", 99) or 99) < 2,
            is_time_pressure=(extra_ctx.get("time_remaining", 999) or 999) < 60,
            threat_ignored=bool(tactical_analysis.get("threats_created")),
            threat_descriptions=tactical_analysis.get("threats_created", [])[:2],
            # Cross-game
            consecutive_blunders=extra_ctx.get("consecutive_blunders", 0),
            blunders_this_game=extra_ctx.get("blunders_this_game", 0),
            user_move_evaluations=extra_ctx.get("user_move_evaluations", []),
            opening_name=extra_ctx.get("opening_name"),
            endgame_type=extra_ctx.get("endgame_type"),
            mistake_type=extra_ctx.get("mistake_type"),
            recent_same_mistake_count=extra_ctx.get("recent_same_mistake_count", 0),
        )

        matches = detect_meta_patterns(ctx)
        if not matches:
            return None

        top = matches[0]
        # Use fallback message + rule for now (LLM hook comes later in the flow)
        return {
            "coaching_message": top.fallback_message or top.fallback_rule,
            "rule": top.fallback_rule,
            "pattern_id": top.pattern_id,
        }
    except Exception as e:
        logger.debug(f"[META] meta-pattern detection failed: {e}")
        return None


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
    eval_before: float = 0.0,
    eval_after: float = 0.0,
    user_color: str = "white",
    extra_meta_ctx: Optional[Dict] = None,
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
    
    is_beginner = user_rating < 1000

    # ========== BRILLIANT MOVES ==========
    if quality == "brilliant":
        brilliant_phrases = [
            f"Brilliant. {user_move} — that sacrifice wins.",
            f"{user_move} is brilliant. You gave up material to win.",
            f"{user_move} — the kind of sacrifice only deep calculation finds.",
        ]
        result["coaching_message"] = random.choice(brilliant_phrases)
        result["encouragement"] = random.choice([
            "Sharp calculation.",
            "Real vision on that one.",
        ])
        return result

    # ========== BOOK MOVES (opening theory — don't praise) ==========
    if quality == "book":
        book_phrases = [
            f"{user_move}. Theory.",
            f"{user_move} — book move.",
            f"{user_move}. Standard in this opening.",
        ]
        result["coaching_message"] = random.choice(book_phrases)
        result["user_move_quality"] = "book"
        return result

    # ========== EXCELLENT MOVES ==========
    if quality == "excellent":
        base = random.choice([
            f"{user_move} — exactly right.",
            f"Yes. {user_move} is the move.",
            f"{user_move}. Best move here.",
        ])
        # Add position-aware context
        context = _move_context(user_move, tactical_analysis)
        result["coaching_message"] = f"{base}{context}"
        # No blanket encouragement — the message itself is the praise
        return result

    # ========== GOOD MOVES ==========
    elif quality == "good":
        base = random.choice([
            f"{user_move} works.",
            f"{user_move} — solid.",
            f"{user_move}. Keeps things steady.",
        ])
        context = _move_context(user_move, tactical_analysis)
        result["coaching_message"] = f"{base}{context}"
        if best_move and best_move != user_move:
            result["coaching_message"] += f" {best_move} was a touch sharper."
        return result
    
    # ========== INACCURACIES ==========
    elif quality == "inaccuracy":
        # Try contrastive explanation (position + phase aware)
        contrast = _contrastive_explanation(fen_before, user_move, best_move, user_rating) if fen_before else None

        # Under 1200: only show inaccuracy if we have substance.
        # No "playable but more accurate" filler — it teaches nothing.
        # Empty message = frontend shows no feedback for this move.
        if user_rating < 1200:
            if contrast:
                result["coaching_message"] = contrast
            else:
                result["coaching_message"] = ""  # Suppress — nothing useful to say
                result["user_move_quality"] = "good"  # Downgrade label so it doesn't show as inaccuracy
            return result

        # 1200+: show contrastive if available, else a short hint
        if contrast:
            result["coaching_message"] = contrast
        else:
            # Minimal fallback — only if we genuinely have nothing better
            result["coaching_message"] = f"{best_move} was more accurate than {user_move}."
        return result
    
    # ========== MISTAKES - CONTRASTIVE + SOCRATIC ==========
    elif quality == "mistake":
        # === 1. Try meta-pattern first (highest quality, composition-based) ===
        meta = _try_meta_pattern(
            fen_before, user_move, best_move, eval_before, eval_after,
            user_color, user_rating, quality, tactical_analysis, extra_meta_ctx
        )
        if meta:
            result["coaching_message"] = meta["coaching_message"]
            result["meta_pattern_id"] = meta["pattern_id"]
            result["rule"] = meta["rule"]
            result["encouragement"] = "Even strong players miss this kind of thing."
            return result

        # === 2. Fall back to contrastive explanation (position-specific) ===
        contrast = _contrastive_explanation(fen_before, user_move, best_move, user_rating) if fen_before else None

        if is_beginner:
            # Beginners: direct, simple. Use contrast if available.
            if contrast:
                result["coaching_message"] = contrast
            else:
                reveal_parts = [f"{user_move} loses some ground."]
                if user_move != best_move:
                    reveal_parts.append(f"{best_move} was the move.")
                result["coaching_message"] = " ".join(reveal_parts)
            # No filler encouragement — the message stands on its own
            return result

        # Socratic question
        socratic_questions = [
            f"Interesting — what was your thinking on {user_move}?",
            f"Walk me through it — why {user_move}?",
            f"Before I say anything: what was the idea behind {user_move}?",
        ]
        result["socratic_question"] = random.choice(socratic_questions)
        result["expects_response"] = True

        # Reveal: use contrast if available, fall back to generic
        if contrast:
            result["coaching_message"] = contrast
        else:
            reveal_parts = [f"{user_move} lets some advantage slip."]
            if tactical_analysis.get("threats_created"):
                reveal_parts.append(f"Now I can play {tactical_analysis['threats_created'][0]}.")
            if user_move != best_move:
                reveal_parts.append(f"The move to find was {best_move}.")
            result["coaching_message"] = " ".join(reveal_parts)

        # One tight, honest acknowledgment — no platitudes
        result["encouragement"] = "Even strong players miss this kind of thing."
        return result
    
    # ========== BLUNDERS - META-PATTERN > CONTRASTIVE > SOCRATIC ==========
    elif quality == "blunder":
        # === 1. Try meta-pattern first ===
        meta = _try_meta_pattern(
            fen_before, user_move, best_move, eval_before, eval_after,
            user_color, user_rating, quality, tactical_analysis, extra_meta_ctx
        )
        if meta:
            result["coaching_message"] = meta["coaching_message"]
            result["meta_pattern_id"] = meta["pattern_id"]
            result["rule"] = meta["rule"]
            result["encouragement"] = "Everyone blunders. What matters is the next move."
            return result

        # === 2. Fall back to contrastive ===
        contrast = _contrastive_explanation(fen_before, user_move, best_move, user_rating) if fen_before else None

        if is_beginner:
            if contrast:
                result["coaching_message"] = contrast
            else:
                reveal_parts = [f"{user_move} drops material."]
                if tactical_analysis.get("best_move_captures"):
                    reveal_parts.append(f"{best_move} would have won the {tactical_analysis['best_move_captures']}.")
                elif user_move != best_move:
                    reveal_parts.append(f"The safe move was {best_move}.")
                result["coaching_message"] = " ".join(reveal_parts)
            result["socratic_question"] = "Before your next move, check every piece — is anything left alone?"
            # No filler encouragement — the message + socratic carry it
            return result

        # Socratic question
        socratic_questions = [
            f"Wait. {user_move}? What did you see here?",
            f"Hold on — that {user_move}. Walk me through your thinking.",
            f"That {user_move} hurt. What was the plan?",
        ]
        result["socratic_question"] = random.choice(socratic_questions)
        result["expects_response"] = True

        # Reveal: use contrast if available
        if contrast:
            result["coaching_message"] = contrast
        else:
            reveal_parts = [f"{user_move} was a serious mistake."]
            if tactical_analysis.get("best_move_captures"):
                reveal_parts.append(f"{best_move} wins the {tactical_analysis['best_move_captures']}.")
            elif tactical_analysis.get("threats_created"):
                reveal_parts.append(f"It lets me play {tactical_analysis['threats_created'][0]}.")
            else:
                reveal_parts.append(f"The move was {best_move}.")
            result["coaching_message"] = " ".join(reveal_parts)

        # One tight, honest acknowledgment — these moves are the ones that fade
        result["encouragement"] = "These are the moves that fade once you slow down on captures."
        return result
    
    # Fallback
    result["coaching_message"] = f"I played {coach_move}."
    return result


async def generate_move_feedback(
    db,
    session_id: str,
    move_number: int,
    user_id: str,
    use_chess_brain: bool = False  # DISABLED: see comment below
) -> Optional[MoveFeedback]:
    """
    Generate comprehensive feedback for a specific move in a session.

    Args:
        db: Database connection
        session_id: Coach play session ID
        move_number: Which user move to analyze (1-indexed)
        user_id: User ID for personalization
        use_chess_brain: If True, use the deterministic Chess Brain engine.
            DISABLED 2026-05-10. ChessBrain's lesson library was firing
            canned snippets ("Rooks belong on open files!", "Pin the pawn
            to the knight", "King safety needs attention") matched at
            random to moves where they didn't apply — including opening
            moves where rooks haven't moved and pin geometries don't exist.
            For live coaching, wrong teaching is worse than no teaching.
            The legacy _generate_coaching_message path handles each move-
            quality tier correctly (good → quiet acknowledgment, mistake
            → contrastive explanation with best move, blunder → Socratic +
            contrastive). Re-enable only after lesson selection is fixed
            to surface lessons only when they actually match the position.

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

    # ===== CCT DISCIPLINE GRACE (Phase 5b) =====
    # When the user plays a forcing move (check/capture/threat) in a
    # position where the engine's best was ALSO forcing, we shouldn't
    # tag the move as blunder/mistake just because it wasn't THE best.
    # The discipline of staying in forcing-move mode is what matters
    # mid-game — that's the pattern we want to reward, not penalize.
    #
    # Mechanism: if quality is mistake/blunder AND user played forcing
    # AND best was forcing, downgrade to inaccuracy and attach a CCT
    # voice line that the coaching surface can use instead of the
    # standard penalty narrative.
    cct_discipline_held = False
    cct_voice_line = None
    if quality in ("mistake", "blunder") and fen_before and best_move and user_move:
        try:
            from services.cct_detector import classify_move_cct
            from services.cct_voice import coach_play_held_initiative_message

            board_before = chess.Board(fen_before)
            played_obj = board_before.parse_san(user_move)
            best_obj = None
            try:
                best_obj = board_before.parse_san(best_move)
            except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
                best_obj = None

            cct_tags = classify_move_cct(
                board_before, played_obj, best_move=best_obj
            )

            if cct_tags.get("played_forcing_when_best_was_forcing"):
                # Downgrade severity. The held-discipline message
                # carries the teaching weight; we don't need the
                # blunder framing on top.
                quality = "inaccuracy"
                cct_discipline_held = True
                # Build a voice line from the segment-style data we
                # have at this single move (no lookahead window
                # available mid-game; we synthesize one from the
                # current move alone).
                cct_voice_line = coach_play_held_initiative_message({
                    "miss_move_san": user_move,
                    "missed_best_san": best_move,
                    "window_moves_san": [user_move],
                })
        except Exception as cct_err:
            # Non-fatal — fall through with original quality
            logger.debug(f"CCT grace check failed (non-fatal): {cct_err}")
    
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
        # Build extra context for meta-pattern detection
        extra_meta_ctx = {
            "move_history": [m.get("move", "") for m in move_history],
            "move_number": move_number,
            "time_spent": user_move_data.get("time_spent", 0),
            "time_remaining": session.get("user_time_remaining", 999),
            "game_phase": (
                "opening" if move_number <= 10
                else "endgame" if move_number >= 35
                else "middlegame"
            ),
            "consecutive_blunders": sum(
                1 for m in (move_history or [])[-4:]
                if m.get("by") == "player" and (m.get("evaluation") or "").lower() == "blunder"
            ),
            "blunders_this_game": sum(
                1 for m in (move_history or [])
                if m.get("by") == "player" and (m.get("evaluation") or "").lower() == "blunder"
            ),
            "user_move_evaluations": [
                {
                    "move": m.get("move", ""),
                    "move_number": m.get("move_number", i),
                    "time_spent": m.get("time_spent", 0),
                    "cp_loss": m.get("cp_loss", 0),
                }
                for i, m in enumerate(move_history or [])
                if m.get("by") == "player"
            ],
        }

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
            eval_before=eval_before,
            eval_after=eval_after,
            user_color=user_color,
            extra_meta_ctx=extra_meta_ctx,
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
                attacks = tactical['best_move_attacks'][:2]
                if len(attacks) == 1:
                    best_move_explanation = f"Hits the {attacks[0]}"
                else:
                    best_move_explanation = f"Hits {attacks[0]} and {attacks[1]}"
            else:
                best_move_explanation = "Holds your position better"

        # Encouragement only for the genuinely strong move — drop generic
        # praise on plain "good" moves; the coaching_message itself is enough.
        encouragement = coaching_result.get("encouragement")
        if not encouragement and quality == "excellent":
            encouragement = "That's the move."

    # ═══ MID-GAME ADAPTATION — adjust based on how user is playing THIS game ═══
    # The nudge is shown as a separate field, NOT prepended to the main message,
    # so the main coaching message stays focused on the actual move.
    adaptation_nudge = None
    try:
        from services.midgame_adaptation import compute_game_adaptation
        adaptation = compute_game_adaptation(move_history, user_color, [])
        adaptation_nudge = adaptation.get("nudge")

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
            coach_explanation = f"I play {coach_move} — punishes the slip."
        else:
            coach_explanation = f"I play {coach_move}."
    
    # Check if relates to known weakness (used by both paths)
    # Voice rule: name the pattern, drop generic motivational closers
    # ("keep practicing", "you know better than this" — both anti-patterns).
    relates_to = None
    if understanding_context:
        weakness = understanding_context.get("primary_weakness", "")
        if weakness and quality in ["mistake", "blunder"]:
            if "tactical" in weakness.lower():
                relates_to = f"This is the {weakness} pattern showing up again."
            elif "consistency" in weakness.lower():
                relates_to = "Same kind of slip you've made in earlier games."
    
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
            "idea": best_move_explanation or f"{best_move} is the strongest move here",
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
                            golden_rule = "Knights on the rim are dim — they have fewer squares to jump to."
                        else:
                            golden_rule = "Every piece needs a job. What is this knight doing for you?"
                    elif piece.piece_type == chess.PAWN:
                        golden_rule = "Pawns can't go back. Every pawn move creates a weakness somewhere."
                    elif piece.piece_type == chess.BISHOP:
                        golden_rule = "Bishops need open diagonals. A bishop blocked by your own pawns is wasted."
                    elif piece.piece_type == chess.QUEEN:
                        golden_rule = "The queen out early gets chased and loses you tempo."
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

    # Opening-theory note — pairs the move-level rule with opening-
    # specific theory. Returns None when not in a known opening or
    # past the opening phase. See services/opening_theory_note.py.
    opening_theory_note = None
    try:
        from services.opening_theory_note import get_opening_theory_note
        san_history = [m.get("move", "") for m in (move_history or []) if m.get("move")]
        if san_history:
            opening_theory_note = get_opening_theory_note(
                move_history=san_history,
                move_number=move_number,
            )
    except Exception as exc:
        logger.warning(f"opening_theory_note lookup failed: {exc}")

    # Hallucination guard — verify every "X on Y" / "your X on Y" claim
    # in the user-facing strings against the actual board. Strings that
    # fail are wiped (set to empty) so the frontend falls back to other
    # available context — silence beats confidently-wrong claims.
    # Same module + same checks as smart_coaching + V5 decryption.
    try:
        from services.coaching_text_guard import verify_coaching_text

        def _guard(text_val: str) -> str:
            """Return text_val unchanged if it passes the guard, '' if not."""
            if not text_val or not isinstance(text_val, str):
                return text_val or ""
            issues = verify_coaching_text(text_val, guard_fen, user_color=user_color)
            if issues:
                logger.warning(
                    f"[PWC] Hallucination guard stripped string on move "
                    f"{user_move}: {[i.detail for i in issues]}"
                )
                return ""
            return text_val

        # The user-facing position when they read this coaching is the
        # position AFTER their move. Compute it from fen_before + move.
        guard_fen = ""
        if fen_before and user_move:
            try:
                _gboard = chess.Board(fen_before)
                _gboard.push_san(user_move)
                guard_fen = _gboard.fen()
            except Exception:
                guard_fen = fen_before  # fall back to pre-move FEN
        if guard_fen:
            coaching_message = _guard(coaching_message)
            best_move_explanation = _guard(best_move_explanation)
            coach_explanation = _guard(coach_explanation)
            consequence = _guard(consequence) if consequence else consequence
            golden_rule = _guard(golden_rule) if golden_rule else golden_rule
    except Exception as exc:
        logger.warning(f"[PWC] Hallucination guard skipped: {exc}")

    # Vacuous text suppressor — Category 5. Strip filler/no-content
    # coaching when the move severity warrants real teaching. Frontend
    # falls back to severity badge + best move on empty coaching_message.
    try:
        from services.vacuous_text_detector import is_text_vacuous
        if quality in ("mistake", "blunder", "inaccuracy"):
            if coaching_message and is_text_vacuous(coaching_message, quality):
                logger.warning(
                    f"[PWC] Stripped vacuous coaching_message on {quality} "
                    f"move {user_move}: \"{coaching_message[:80]}\""
                )
                coaching_message = ""
    except Exception as exc:
        logger.warning(f"[PWC] Vacuous-text suppressor skipped: {exc}")

    # Multi-ply chain verifier — Category 8. Check "After X Y Z" claims
    # against the post-move position; wipe field on illegal-chain
    # detection. Same module + behavior as V5 decryption + smart_coaching.
    try:
        from services.coaching_text_guard import verify_chain_claims
        chain_fen = ""
        if fen_before and user_move:
            try:
                _cb = chess.Board(fen_before)
                _cb.push_san(user_move)
                chain_fen = _cb.fen()
            except Exception:
                chain_fen = ""
        if chain_fen:
            def _chain_guard(text_val: str, name: str) -> str:
                if not text_val or not isinstance(text_val, str):
                    return text_val or ""
                issues = verify_chain_claims(text_val, chain_fen)
                if issues:
                    logger.warning(
                        f"[PWC] Stripped illegal-chain {name} on move "
                        f"{user_move}: {[i.detail for i in issues]}"
                    )
                    return ""
                return text_val
            coaching_message = _chain_guard(coaching_message, "coaching_message")
            best_move_explanation = _chain_guard(best_move_explanation, "best_move_explanation")
            coach_explanation = _chain_guard(coach_explanation, "coach_explanation")
            consequence = _chain_guard(consequence, "consequence") if consequence else consequence
    except Exception as exc:
        logger.warning(f"[PWC] Chain-legality verifier skipped: {exc}")

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
        is_brilliant=is_brilliant,
        cct_discipline_held=cct_discipline_held,
        cct_voice_line=cct_voice_line,
        opening_theory_note=opening_theory_note,
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

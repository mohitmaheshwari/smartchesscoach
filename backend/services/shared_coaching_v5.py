"""
Shared Coaching V5 Layer
========================

This is the SINGLE source of truth for V5 "Thinking Simulator" coaching.
Used by BOTH:
- Lab (Game Decryption) - analyzing past games
- Play with Coach - live coaching during play

Key Principles:
1. SAME coaching tone everywhere (Horsey, Naughty Knight, Slicey Boi)
2. SAME specific consequences (never generic "position weakens")
3. SAME Stockfish candidate moves with ideas
4. SAME "I understand" tracking
5. SAME transferable learning / Golden Rules

This ensures: Improve one place → Both pages get smarter!
"""

import chess
import chess.engine
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

STOCKFISH_PATH = "/usr/games/stockfish"


# ─── ENUMS & DATA CLASSES ───────────────────────────────────────────

class MoveSeverity(str, Enum):
    """How good/bad was the move?"""
    BRILLIANT = "brilliant"
    GREAT = "great"
    GOOD = "good"
    BOOK = "book"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"


class CoachingContext(str, Enum):
    """Where is the coaching happening?"""
    LAB_REVIEW = "lab_review"           # Reviewing a past game
    LIVE_AFTER_USER = "live_after_user"  # User just played (live game)
    LIVE_AFTER_COACH = "live_after_coach" # Coach just played (live game)
    LIVE_BEFORE_USER = "live_before_user" # User is thinking (live game)


@dataclass
class CandidateMove:
    """A candidate move with its strategic idea."""
    move: str              # SAN notation
    idea: str              # The strategic explanation
    move_type: str         # "counter_attack", "prophylactic", "development", etc.
    is_best: bool          # Is this the engine's top choice?
    eval_cp: Optional[int] = None  # Centipawn evaluation


@dataclass 
class V5Coaching:
    """
    Complete V5 coaching output for a move.
    This is the SHARED format used by both Lab and Play with Coach.
    """
    # Core coaching
    narrative: str                    # Main coaching message (fun language!)
    severity: str                     # good/inaccuracy/mistake/blunder
    
    # Plan (for mistakes)
    goal: Optional[str] = None        # What we're trying to achieve
    current_problem: Optional[str] = None  # Why the move is bad
    consequence: Optional[str] = None      # SPECIFIC consequence (not generic!)
    better_approach: Optional[str] = None  # What to do instead
    
    # Learning
    transferable_learning: Optional[str] = None  # Golden rule / pattern
    concept_id: Optional[str] = None             # For "I understand" tracking
    concept_type: Optional[str] = None           # opening/tactical/positional/endgame
    
    # Candidate moves (from Stockfish!)
    candidate_moves: List[Dict] = None  # Alternative moves with ideas
    
    # For clickable moves
    future_moves: List[str] = None      # PV to show on board
    
    # Metadata
    is_user_move: bool = True
    best_move: Optional[str] = None
    your_plan_now: Optional[str] = None  # For opponent moves - what should user do?
    pattern_memory: Optional[str] = None  # "You've missed this pattern 3 times this week"
    theory_applied: Optional[str] = None  # "You played the book move in the Italian Game"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON response."""
        result = asdict(self)
        # Remove None values for cleaner response
        return {k: v for k, v in result.items() if v is not None}


# ─── FUN PIECE NAMES ───────────────────────────────────────────────

PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop", 
    chess.ROOK: "Tower",
    chess.QUEEN: "Queen",
    chess.KING: "King"
}

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0
}


def get_fun_piece_name(piece: chess.Piece) -> str:
    """Get the fun V5 name for a piece."""
    return PIECE_NAMES.get(piece.piece_type, "piece")


def get_piece_value(piece: chess.Piece) -> int:
    """Get the material value of a piece."""
    return PIECE_VALUES.get(piece.piece_type, 0)


# ─── STOCKFISH CANDIDATE MOVES ─────────────────────────────────────

async def quick_stockfish_eval(fen_before: str, move_san: str, user_color: str, depth: int = 12) -> dict:
    """
    Quick Stockfish evaluation for a move. Returns best_move, eval_before, eval_after, cp_loss.
    Used by Play with Coach to get instant move quality without waiting for analysis worker.
    """
    try:
        board = chess.Board(fen_before)
        move = board.parse_san(move_san)
        
        transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
        try:
            # Eval BEFORE the move
            info_before = await engine.analyse(board, chess.engine.Limit(depth=depth))
            score_before = info_before.get("score")
            eval_before = 0.0
            if score_before:
                if score_before.white().is_mate():
                    eval_before = 100.0 if score_before.white().mate() > 0 else -100.0
                else:
                    eval_before = score_before.white().score(mate_score=10000) / 100.0
            
            # Get best move
            best_move_obj = info_before.get("pv", [None])[0]
            best_move_san = board.san(best_move_obj) if best_move_obj else move_san
            pv_after_best = []
            if info_before.get("pv"):
                temp_board = board.copy()
                for pv_move in info_before["pv"][:5]:
                    try:
                        pv_after_best.append(temp_board.san(pv_move))
                        temp_board.push(pv_move)
                    except Exception:
                        break
            
            # Apply the played move and eval AFTER
            board.push(move)
            info_after = await engine.analyse(board, chess.engine.Limit(depth=depth))
            score_after = info_after.get("score")
            eval_after = 0.0
            if score_after:
                if score_after.white().is_mate():
                    eval_after = 100.0 if score_after.white().mate() > 0 else -100.0
                else:
                    eval_after = score_after.white().score(mate_score=10000) / 100.0
            
            # PV after played move
            pv_after_played = []
            if info_after.get("pv"):
                temp_board = board.copy()
                for pv_move in info_after["pv"][:5]:
                    try:
                        pv_after_played.append(temp_board.san(pv_move))
                        temp_board.push(pv_move)
                    except Exception:
                        break
            
            # Calculate cp_loss (from user's perspective)
            if user_color == "white":
                cp_loss = max(0, int((eval_before - eval_after) * 100))
            else:
                cp_loss = max(0, int((eval_after - eval_before) * 100))
            
            return {
                "best_move": best_move_san,
                "eval_before": eval_before,
                "eval_after": eval_after,
                "cp_loss": cp_loss,
                "pv_after_played": pv_after_played,
                "pv_after_best": pv_after_best
            }
        finally:
            await engine.quit()
    except Exception as e:
        logger.warning(f"Quick Stockfish eval failed: {e}")
        return {
            "best_move": None,
            "eval_before": 0,
            "eval_after": 0,
            "cp_loss": 0,
            "pv_after_played": [],
            "pv_after_best": []
        }

async def get_stockfish_candidates(
    board: chess.Board, 
    num_moves: int = 3, 
    depth: int = 12
) -> List[CandidateMove]:
    """
    Get top candidate moves from Stockfish using multi-PV.
    
    This ensures we only suggest GOOD moves (not blunders like Qd6 hanging the queen).
    """
    candidates = []
    
    try:
        transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
        
        try:
            result = await engine.analyse(
                board,
                chess.engine.Limit(depth=depth),
                multipv=num_moves
            )
            
            for i, info in enumerate(result):
                if "pv" not in info or not info["pv"]:
                    continue
                
                move = info["pv"][0]
                san = board.san(move)
                
                # Get evaluation
                score = info.get("score")
                if score:
                    if score.is_mate():
                        cp = 10000 if score.relative.mate() > 0 else -10000
                    else:
                        cp = score.relative.score(mate_score=10000)
                else:
                    cp = 0
                
                # Explain the idea behind this move
                idea, move_type = explain_move_idea(board, san)
                
                candidates.append(CandidateMove(
                    move=san,
                    idea=idea,
                    move_type=move_type,
                    is_best=(i == 0),
                    eval_cp=cp
                ))
        finally:
            await engine.quit()
            
    except Exception as e:
        logger.error(f"Stockfish multi-PV failed: {e}")
    
    return candidates


def explain_move_idea(board: chess.Board, move_san: str) -> tuple:
    """
    Explain the strategic idea behind a move.
    Returns (explanation, move_type).
    """
    try:
        move = board.parse_san(move_san)
    except Exception:
        return (f"{move_san} is a strong move here", "engine_choice")
    
    piece = board.piece_at(move.from_square)
    if not piece:
        return (f"{move_san} is a strong move here", "engine_choice")
    
    sim = board.copy()
    sim.push(move)
    
    user_color = board.turn
    to_sq = move.to_square
    to_file = chess.square_file(to_sq)
    to_rank = chess.square_rank(to_sq)
    
    # Check for different move ideas
    
    # 1. COUNTER-ATTACK: Creates a threat
    for sq in chess.SQUARES:
        opp_piece = sim.piece_at(sq)
        if opp_piece and opp_piece.color != user_color:
            if sim.is_attacked_by(user_color, sq) and not board.is_attacked_by(user_color, sq):
                target_name = get_fun_piece_name(opp_piece)
                return (f"{move_san} attacks their {target_name} - forces them to respond!", "counter_attack")
    
    # 2. CASTLING: King safety
    if board.is_castling(move):
        return (f"{move_san} tucks the King away safely!", "king_safety")
    
    # 3. CHECK
    if sim.is_check():
        return (f"{move_san} gives check - forces their hand!", "tactical")
    
    # 4. CAPTURE (winning material)
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            captured_name = get_fun_piece_name(captured)
            return (f"{move_san} wins the {captured_name}!", "tactical")
    
    # 5. CENTRAL CONTROL
    center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
    if to_sq in center_squares:
        piece_name = get_fun_piece_name(piece)
        return (f"{move_san} plants the {piece_name} in the center - maximum power!", "central")
    
    # 6. DEVELOPMENT (minor pieces)
    if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
        back_rank = 0 if user_color == chess.WHITE else 7
        if chess.square_rank(move.from_square) == back_rank:
            center_distance = abs(to_file - 3.5) + abs(to_rank - 3.5)
            if center_distance < 3:
                return (f"{move_san} develops with a purpose - aims at the center!", "development")
            return (f"{move_san} gets a piece into the game!", "development")
    
    # 7. PROPHYLACTIC (pawn moves on wings preventing invasions)
    if piece.piece_type == chess.PAWN and to_file in [0, 7]:
        return (f"{move_san} prevents opponent's piece from invading!", "prophylactic")
    
    # 8. PAWN PUSH (central)
    if piece.piece_type == chess.PAWN and to_file in [3, 4]:
        return (f"{move_san} fights for central space!", "central")
    
    # Default
    return (f"{move_san} improves the position!", "positional")


# ─── CONSEQUENCE ANALYSIS ──────────────────────────────────────────

def describe_consequence(pv: List[str], board_after_move: chess.Board) -> str:
    """
    Describe SPECIFICALLY what goes wrong after the move.
    
    CRITICAL: Check for checkmate first! Nothing else matters if it's mate.
    """
    if not pv:
        return "Something's not right here!"
    
    sim = board_after_move.copy()
    user_color = not board_after_move.turn  # User just moved
    first_move_san = pv[0]
    
    # ─── CHECKMATE CHECK ──────────────────────────────────
    if "#" in first_move_san:
        return f"After {first_move_san}, it's checkmate. Game over."
    
    try:
        test_move = sim.parse_san(first_move_san)
        test_sim = sim.copy()
        test_sim.push(test_move)
        if test_sim.is_checkmate():
            return f"After {first_move_san}, it's checkmate. Game over."
        
        # Check for mate within PV
        for pv_san in pv[1:4]:
            try:
                if "#" in pv_san:
                    return f"After {first_move_san}, forced checkmate follows within a few moves."
                pm = test_sim.parse_san(pv_san)
                test_sim.push(pm)
                if test_sim.is_checkmate():
                    return f"After {first_move_san}, forced checkmate follows within a few moves."
            except Exception:
                break
    except Exception:
        pass
    
    # ─── NORMAL CONSEQUENCE ANALYSIS ──────────────────────
    sim = board_after_move.copy()
    
    # Try to play the opponent's response
    try:
        first_move = sim.parse_san(first_move_san)
        sim.push(first_move)
        
        # Check for attacked pieces
        for sq in chess.SQUARES:
            piece = sim.piece_at(sq)
            if piece and piece.color == user_color:
                attackers = list(sim.attackers(not user_color, sq))
                defenders = list(sim.attackers(user_color, sq))
                
                if attackers:
                    piece_name = get_fun_piece_name(piece)
                    sq_name = chess.square_name(sq)
                    
                    if len(attackers) > len(defenders):
                        if piece.piece_type == chess.PAWN:
                            if len(defenders) == 0:
                                return f"After {first_move_san}, your pawn on {sq_name} is totally undefended!"
                            return f"After {first_move_san}, your pawn on {sq_name} is outnumbered - {len(attackers)} attackers vs {len(defenders)} defender!"
                        else:
                            if len(defenders) == 0:
                                return f"After {first_move_san}, your {piece_name} on {sq_name} is hanging!"
                            return f"After {first_move_san}, your {piece_name} on {sq_name} is outnumbered!"
                    elif not defenders and piece.piece_type != chess.KING:
                        return f"After {first_move_san}, your {piece_name} on {sq_name} has no defenders!"
        
        # Check for check
        if sim.is_check():
            return f"After {first_move_san}, your King gets checked!"
        
    except Exception:
        pass
    
    # Check for material loss in PV
    sim = board_after_move.copy()
    for san in pv[:4]:
        try:
            move = sim.parse_san(san)
            if sim.is_capture(move):
                captured = sim.piece_at(move.to_square)
                if captured and captured.color == user_color:
                    captured_name = get_fun_piece_name(captured)
                    return f"After {san}, your {captured_name} gets captured!"
            sim.push(move)
        except Exception:
            break
    
    # Fallback to positional analysis
    return analyze_positional_weakness(board_after_move, user_color, first_move_san)


def analyze_positional_weakness(board: chess.Board, user_color: bool, opponent_move: str) -> str:
    """Find positional issues when no tactical problems found."""
    
    # Check center control
    center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
    user_center = sum(len(list(board.attackers(user_color, sq))) for sq in center_squares)
    opp_center = sum(len(list(board.attackers(not user_color, sq))) for sq in center_squares)
    
    if opp_center > user_center + 2:
        return f"After {opponent_move}, your opponent dominates the center!"
    
    # Check development
    undeveloped = 0
    back_rank_squares = [chess.B1, chess.C1, chess.F1, chess.G1] if user_color == chess.WHITE else [chess.B8, chess.C8, chess.F8, chess.G8]
    for sq in back_rank_squares:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
            undeveloped += 1
    
    if undeveloped >= 2:
        return f"After {opponent_move}, you're behind in development!"
    
    # Default - still specific!
    return f"After {opponent_move}, your opponent gains the initiative!"


# ─── FORK DETECTION ────────────────────────────────────────────────

def detect_fork_in_pv(board: chess.Board, pv: List[str], user_color: bool) -> Optional[Dict]:
    """
    Detect if the PV contains a fork threat by the KNIGHT specifically.
    Only reports a fork when the knight itself attacks 2+ valuable pieces.
    Uses chess.attacks() on the knight square instead of is_attacked_by()
    to avoid false positives from other pieces.
    """
    if not pv:
        return None
    
    sim = board.copy()
    
    try:
        for san in pv[:2]:
            move = sim.parse_san(san)
            moving_piece = sim.piece_at(move.from_square)
            
            # Check for knight forks only
            if moving_piece and moving_piece.piece_type == chess.KNIGHT:
                knight_dest = move.to_square
                sim.push(move)
                
                # Get squares attacked specifically by this knight
                knight_attacks = chess.BB_KNIGHT_ATTACKS[knight_dest]
                
                # Find user's valuable pieces on those specific squares
                attacked = []
                attacked_values = []
                
                for sq in chess.SQUARES:
                    if not (knight_attacks & chess.BB_SQUARES[sq]):
                        continue  # Knight doesn't attack this square
                    piece = sim.piece_at(sq)
                    if piece and piece.color == user_color:
                        attacked.append(get_fun_piece_name(piece))
                        attacked_values.append(get_piece_value(piece))
                
                # Fork detected if 2+ valuable pieces attacked by the knight
                # Require total value >= 6 (at least rook+bishop or queen+anything)
                if len(attacked) >= 2 and sum(attacked_values) >= 6:
                    attacked_with_values = list(zip(attacked, attacked_values))
                    attacked_with_values.sort(key=lambda x: x[1], reverse=True)
                    piece1 = attacked_with_values[0][0]
                    piece2 = attacked_with_values[1][0]
                    
                    return {
                        "type": "knight_fork",
                        "piece1": piece1,
                        "piece2": piece2,
                        "fork_move": san
                    }
            else:
                sim.push(move)
                
    except Exception:
        pass
    
    return None


# ─── OPENING BOOK MOVE CHECK ──────────────────────────────────────

def _is_book_opening_move(board: chess.Board, move_san: str, move_index: int, cp_loss: int) -> bool:
    """Check if a move is a known opening book move that shouldn't be flagged."""
    if move_index > 12 or cp_loss > 120:
        return False
    
    # Move 0: all standard white first moves
    if move_index == 0:
        return move_san in {"e4", "d4", "c4", "Nf3", "g3", "b3", "f4", "e3", "d3", "b4", "Nc3"}
    
    # Move 1: black responses to e4/d4/c4/Nf3
    if move_index == 1:
        fen = board.fen()
        if "4P3" in fen:  # after e4
            return move_san in {"e5", "c5", "e6", "c6", "d5", "d6", "Nf6", "g6", "b6", "Nc6", "a6"}
        if "3P4" in fen:  # after d4
            return move_san in {"d5", "Nf6", "f5", "e6", "c5", "d6", "g6", "c6", "e5", "Nc6", "b6"}
        if "2P5" in fen:  # after c4
            return move_san in {"e5", "c5", "Nf6", "e6", "c6", "g6", "f5", "b6"}
        if "5N2" in fen:  # after Nf3
            return move_san in {"d5", "Nf6", "c5", "g6", "f5", "e6", "d6"}
    
    # Early developing moves with small cp loss
    if move_index <= 6 and cp_loss < 60:
        try:
            move = board.parse_san(move_san)
            piece = board.piece_at(move.from_square)
            if piece:
                if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                    return True
                if piece.piece_type == chess.KING and board.is_castling(move):
                    return True
                if piece.piece_type == chess.PAWN:
                    to_file = chess.square_file(move.to_square)
                    if to_file in (2, 3, 4, 5):  # c,d,e,f files
                        return True
        except Exception:
            pass
    
    return False


# ─── MAIN COACHING GENERATION ──────────────────────────────────────

async def generate_move_coaching(
    board_before: chess.Board,
    move: chess.Move,
    best_move_san: Optional[str],
    pv_after_played: List[str],
    pv_after_best: List[str],
    cp_loss: int,
    phase: str = "opening",
    is_user_move: bool = True,
    context: CoachingContext = CoachingContext.LAB_REVIEW,
    user_color: str = "white"
) -> V5Coaching:
    """
    Generate V5 coaching for a move.
    
    This is the MAIN ENTRY POINT used by both Lab and Play with Coach.
    """
    move_san = board_before.san(move)
    board_after = board_before.copy()
    board_after.push(move)
    
    # Determine severity
    if not is_user_move:
        severity = "context"
    elif cp_loss < 30:
        severity = "good"
    elif cp_loss < 100:
        severity = "inaccuracy"
    elif cp_loss < 250:
        severity = "mistake"
    else:
        severity = "blunder"
    
    # Override: known opening book moves should not be flagged
    if is_user_move and severity in ("inaccuracy", "mistake") and phase == "opening":
        move_index = (board_before.fullmove_number - 1) * 2 + (0 if board_before.turn == chess.WHITE else 1)
        if _is_book_opening_move(board_before, move_san, move_index, cp_loss):
            severity = "good"
    
    # Get piece info
    piece = board_before.piece_at(move.from_square)
    piece_name = get_fun_piece_name(piece) if piece else "piece"
    piece_type = piece.piece_type if piece else None
    
    # ─── OPPONENT MOVE (context) ───
    if not is_user_move:
        narrative, your_plan = generate_opponent_move_coaching(
            board_before, move, pv_after_played, user_color
        )
        return V5Coaching(
            narrative=narrative,
            severity="context",
            is_user_move=False,
            your_plan_now=your_plan,
            future_moves=pv_after_played[:3] if pv_after_played else None
        )
    
    # ─── GOOD USER MOVE ───
    if severity == "good":
        narrative = generate_good_move_narrative(board_before, move, best_move_san, piece_name)
        return V5Coaching(
            narrative=narrative,
            severity="good",
            is_user_move=True,
            best_move=best_move_san
        )
    
    # ─── MISTAKE/INACCURACY ───
    
    # ─── MATE BLUNDER CHECK (highest priority) ───
    if cp_loss >= 5000 or (pv_after_played and any("#" in m for m in pv_after_played[:4])):
        # Check if this allows checkmate
        mate_move = pv_after_played[0] if pv_after_played else "the next move"
        is_immediate_mate = "#" in mate_move if pv_after_played else False
        
        if is_immediate_mate:
            consequence = f"After {mate_move}, it's checkmate. Game over."
        else:
            consequence = "This allows a forced checkmate within a few moves."
        
        return V5Coaching(
            narrative=f"{move_san} allows checkmate! This is a one-move blunder — the game is lost.",
            severity="blunder",
            goal="King safety — never allow checkmate",
            current_problem=f"{move_san} ignores the mating threat completely.",
            consequence=consequence,
            better_approach=f"{best_move_san} defends against the mate threat." if best_move_san else "Look for moves that address the checkmate threat first.",
            transferable_learning="Before ANY move, ask: can my opponent checkmate me? If there's a mating threat, deal with it FIRST — nothing else matters.",
            concept_id="king_safety_mate_threat",
            concept_type="tactical",
            candidate_moves=None,
            future_moves=pv_after_played[:4] if pv_after_played else None,
            is_user_move=True,
            best_move=best_move_san
        )
    
    # Get Stockfish candidates
    stockfish_candidates = await get_stockfish_candidates(board_before, num_moves=3, depth=12)
    
    # Build candidate moves list (excluding the played move)
    candidate_moves = []
    for c in stockfish_candidates:
        if c.move != move_san:
            candidate_moves.append({
                "move": c.move,
                "idea": c.idea,
                "type": c.move_type,
                "is_best": c.is_best,
                "eval_cp": c.eval_cp
            })
    
    # Get specific consequence
    consequence = describe_consequence(pv_after_played, board_after)
    
    # Check for fork
    fork_info = detect_fork_in_pv(board_after, pv_after_played, 
                                   board_before.turn == chess.WHITE)
    
    if fork_info:
        return V5Coaching(
            narrative=f"Careful! {move_san} allows a knight fork!",
            severity=severity,
            goal="Avoid tactical vulnerabilities",
            current_problem=f"{move_san} allows a fork!",
            consequence=f"After {fork_info['fork_move']}, their knight forks your {fork_info['piece1']} and {fork_info['piece2']}!",
            better_approach=candidate_moves[0]["idea"] if candidate_moves else f"{best_move_san} was better",
            transferable_learning=f"Knight forks are common tactical patterns. When your {fork_info['piece1']} and {fork_info['piece2']} are on the same color square, a knight can attack both!",
            concept_id="knight_fork",
            concept_type="tactical",
            candidate_moves=candidate_moves,
            future_moves=pv_after_played[:4] if pv_after_played else None,
            is_user_move=True,
            best_move=best_move_san
        )
    
    # Generate coaching based on piece type and position
    coaching = generate_piece_specific_coaching(
        board_before, move, piece_type, consequence, 
        candidate_moves, best_move_san, severity
    )
    
    coaching.future_moves = pv_after_played[:4] if pv_after_played else None
    coaching.is_user_move = True
    coaching.best_move = best_move_san
    
    return coaching


def generate_opponent_move_coaching(
    board: chess.Board, 
    move: chess.Move,
    pv: List[str],
    user_color: str
) -> tuple:
    """
    Generate coaching for opponent's move — TEACHING focused.
    Uses the same plan-reading logic as the Lab decryption.
    Returns (narrative, your_plan_now).
    """
    from services.game_decryption_v5_service import _explain_opponent_move_with_context
    
    try:
        narrative, your_plan = _explain_opponent_move_with_context(board, move, user_color, pv)
        return (narrative, your_plan)
    except Exception:
        # Fallback to basic explanation
        move_san = board.san(move)
        board_after = board.copy()
        board_after.push(move)
        
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured:
                return (f"They captured your {get_fun_piece_name(captured)} with {move_san}.", "Check if recapturing is safe.")
        
        if board_after.is_check():
            return (f"{move_san} gives check.", "Block, capture, or move your king.")
        
        return (f"Opponent plays {move_san}.", "Continue with your plan.")


def generate_good_move_narrative(
    board: chess.Board,
    move: chess.Move,
    best_move_san: Optional[str],
    piece_name: str
) -> str:
    """Generate encouraging narrative for a good move."""
    move_san = board.san(move)
    
    # Best move?
    if best_move_san and move_san == best_move_san:
        celebrations = [
            f"Perfect! {move_san} is exactly right!",
            f"Yes! {move_san} - that's the best move!",
            f"Excellent! {move_san} is spot on!",
            f"Great find! {move_san} is the engine's top choice!"
        ]
        import random
        return random.choice(celebrations)
    
    # Check/capture
    board_after = board.copy()
    board_after.push(move)
    
    if board_after.is_check():
        return f"Nice! {move_san} gives check!"
    
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            captured_name = get_fun_piece_name(captured)
            return f"Good capture! {move_san} takes the {captured_name}!"
    
    # Castling
    if board.is_castling(move):
        return f"Smart! {move_san} gets your King to safety!"
    
    # Default good
    return f"Good move! {move_san} keeps you in the game."


def generate_piece_specific_coaching(
    board: chess.Board,
    move: chess.Move,
    piece_type: Optional[int],
    consequence: str,
    candidate_moves: List[Dict],
    best_move_san: Optional[str],
    severity: str
) -> V5Coaching:
    """Generate coaching based on the piece that moved."""
    
    move_san = board.san(move)
    to_square = move.to_square
    better_approach = candidate_moves[0]["idea"] if candidate_moves else f"{best_move_san} was better"
    
    # Derive learning from candidate types
    candidate_types = [c.get("type", "") for c in candidate_moves]
    transferable_learning = derive_transferable_learning(candidate_types, piece_type)
    
    # Knight mistakes
    if piece_type == chess.KNIGHT:
        # Knight on the rim
        if chess.square_file(to_square) in [0, 7] or chess.square_rank(to_square) in [0, 7]:
            return V5Coaching(
                narrative=f"Knight issue: {move_san} goes to the edge!",
                severity=severity,
                goal="Keep knights active",
                current_problem=f"Knight moved to the edge with {move_san}!",
                consequence=consequence,
                better_approach=better_approach,
                transferable_learning=transferable_learning or "Knights on the rim are dim! They have fewer squares to jump to.",
                concept_id="knight_on_rim",
                concept_type="positional",
                candidate_moves=candidate_moves
            )
        # Knight without purpose
        return V5Coaching(
            narrative=f"Hmm, {move_san} - this knight move doesn't improve your position?",
            severity=severity,
            goal="Give pieces a job",
            current_problem=f"Knight issue: {move_san} doesn't create a threat or improve the position.",
            consequence=consequence,
            better_approach=better_approach,
            transferable_learning=transferable_learning or "Every piece needs a job! Ask: what is this piece doing for me?",
            concept_id="piece_without_purpose",
            concept_type="positional",
            candidate_moves=candidate_moves
        )
    
    # Bishop mistakes
    if piece_type == chess.BISHOP:
        return V5Coaching(
            narrative=f"Bishop is passive after {move_san}!",
            severity=severity,
            goal="Keep bishops active",
            current_problem=f"Bishop at {move_san} is blocked by your own pawns!",
            consequence=consequence,
            better_approach=better_approach,
            transferable_learning=transferable_learning or "Bishops need OPEN diagonals. If pawns block them, they're sad!",
            concept_id="blocked_bishop",
            concept_type="positional",
            candidate_moves=candidate_moves
        )
    
    # Pawn mistakes
    if piece_type == chess.PAWN:
        return V5Coaching(
            narrative=f"Careful with {move_san} - pawns can't go back!",
            severity=severity,
            goal="Think before pushing pawns",
            current_problem=f"Pawn at {move_san} is permanent — check if it weakens any squares.",
            consequence=consequence,
            better_approach=better_approach,
            transferable_learning=transferable_learning or "Pawns can NEVER go back! Every pawn move creates a weakness somewhere.",
            concept_id="premature_pawn",
            concept_type="positional",
            candidate_moves=candidate_moves
        )
    
    # Queen mistakes
    if piece_type == chess.QUEEN:
        return V5Coaching(
            narrative=f"Your Queen might be in danger after {move_san}!",
            severity=severity,
            goal="Keep your Queen safe",
            current_problem=f"The Queen is your most powerful piece - {move_san} might expose her!",
            consequence=consequence,
            better_approach=better_approach,
            transferable_learning=transferable_learning or "Don't bring the Queen out too early - she'll get chased around!",
            concept_id="queen_safety",
            concept_type="tactical",
            candidate_moves=candidate_moves
        )
    
    # Rook mistakes  
    if piece_type == chess.ROOK:
        return V5Coaching(
            narrative=f"Is your Tower happy at {move_san}?",
            severity=severity,
            goal="Activate your rooks",
            current_problem=f"{move_san} - your Tower needs open files to shine!",
            consequence=consequence,
            better_approach=better_approach,
            transferable_learning=transferable_learning or "Rooks love open files and the 7th rank! Put them where they can see far.",
            concept_id="rook_placement",
            concept_type="positional",
            candidate_moves=candidate_moves
        )
    
    # Generic
    return V5Coaching(
        narrative=f"Let's think about {move_san}...",
        severity=severity,
        goal="Think before you move",
        current_problem=f"Hmm, {move_san} has a problem!",
        consequence=consequence,
        better_approach=better_approach,
        transferable_learning=transferable_learning or "Before EVERY move, ask: what can my opponent do after this?",
        concept_id="generic_mistake",
        concept_type="general",
        candidate_moves=candidate_moves
    )


def derive_transferable_learning(candidate_types: List[str], piece_type: Optional[int]) -> str:
    """Derive a golden rule from the types of good moves available."""
    
    if "counter_attack" in candidate_types:
        return "Look for counter-attacks! When your opponent threatens, don't just defend - find YOUR threat!"
    
    if "prophylactic" in candidate_types:
        return "Ask: what does my opponent WANT to do next? Then stop it!"
    
    if "development" in candidate_types:
        return "In the opening, develop with a purpose. Each piece should aim at something!"
    
    if "central" in candidate_types:
        return "The center is king! Control d4, d5, e4, e5 and your pieces will be powerful."
    
    if len(set(candidate_types)) >= 2:
        return "Good positions have many good moves. Bad positions have only one! Think about ALL your options."
    
    return ""



# ─── COACH MOVE EXPLANATION ────────────────────────────────────────

def generate_coach_move_explanation(
    board_before: chess.Board,
    move: chess.Move,
    user_color: str = "white"
) -> Dict:
    """
    Generate a rich explanation for the COACH's move.
    
    This tells the user:
    - What the coach is doing
    - What plan the coach is following
    - What threats this creates
    - What the user should watch out for
    - Teaching point (why this is a good move)
    
    This makes the game EDUCATIONAL, not just playing moves.
    """
    move_san = board_before.san(move)
    piece = board_before.piece_at(move.from_square)
    piece_name = get_fun_piece_name(piece) if piece else "piece"
    
    board_after = board_before.copy()
    board_after.push(move)
    
    is_user_white = user_color.lower() == "white"
    user_chess_color = chess.WHITE if is_user_white else chess.BLACK
    coach_color = not user_chess_color
    
    to_square = move.to_square
    to_file = chess.square_file(to_square)
    to_rank = chess.square_rank(to_square)
    
    explanation = ""
    plan = ""
    threats = []
    teaching_point = ""
    hint_for_user = ""
    
    # ═══ DETECT WHAT THE MOVE DOES ═══
    
    # 1. CHECK
    if board_after.is_check():
        explanation = f"Check! I'm attacking your King with {move_san}."
        plan = "Force you to deal with the check before anything else."
        threats.append("Your King is in check!")
        teaching_point = "Checks are forcing moves - they limit your opponent's options."
        hint_for_user = "You MUST get out of check. Block, move the King, or capture the attacker."
        
        return {
            "move_san": move_san,
            "explanation": explanation,
            "plan": plan,
            "threats": threats,
            "teaching_point": teaching_point,
            "hint_for_user": hint_for_user
        }
    
    # 2. CAPTURE
    if board_before.is_capture(move):
        captured = board_before.piece_at(to_square)
        if captured:
            captured_name = get_fun_piece_name(captured)
            explanation = f"I'm taking your {captured_name} with {move_san}!"
            plan = "Win material and improve my position."
            teaching_point = f"Material advantage matters! I'm now up a {captured_name}."
            
            # Check if user can recapture
            if board_after.is_attacked_by(user_chess_color, to_square):
                hint_for_user = f"Can you recapture on {chess.square_name(to_square)}? Check if it's safe!"
            else:
                hint_for_user = "I've won material. Look for ways to fight back - maybe a counter-attack?"
            
            return {
                "move_san": move_san,
                "explanation": explanation,
                "plan": plan,
                "threats": threats,
                "teaching_point": teaching_point,
                "hint_for_user": hint_for_user
            }
    
    # 3. CASTLING
    if board_before.is_castling(move):
        side = "kingside" if chess.square_file(to_square) > 4 else "queenside"
        explanation = f"I'm castling {side} to get my King safe."
        plan = "King safety is crucial! Now my King is tucked away and my Rook is connected."
        teaching_point = "Castling does two things: protects the King AND activates the Rook!"
        hint_for_user = "Have you castled yet? King safety should be a priority in the opening."
        
        return {
            "move_san": move_san,
            "explanation": explanation,
            "plan": plan,
            "threats": threats,
            "teaching_point": teaching_point,
            "hint_for_user": hint_for_user
        }
    
    # 4. FIND NEW THREATS CREATED
    for sq in chess.SQUARES:
        user_piece = board_after.piece_at(sq)
        if user_piece and user_piece.color == user_chess_color:
            # Check if this piece is NOW attacked but wasn't before
            now_attacked = board_after.is_attacked_by(coach_color, sq)
            was_attacked = board_before.is_attacked_by(coach_color, sq)
            
            if now_attacked and not was_attacked:
                target_name = get_fun_piece_name(user_piece)
                sq_name = chess.square_name(sq)
                threats.append(f"Your {target_name} on {sq_name} is now under attack!")
    
    # 5. PIECE-SPECIFIC EXPLANATIONS
    if piece:
        if piece.piece_type == chess.KNIGHT:
            # Knight move
            center_squares = [chess.D4, chess.D5, chess.E4, chess.E5, chess.C3, chess.F3, chess.C6, chess.F6]
            if to_square in center_squares:
                explanation = f"Knight goes to {chess.square_name(to_square)} - a powerful central square!"
                plan = "Knights are strongest in the center where they control many squares."
                teaching_point = "Knights love the center! From there they can jump in any direction."
            else:
                explanation = f"Knight moves to {chess.square_name(to_square)}."
                plan = "Repositioning the knight for future action."
            
            # Check if knight attacks multiple pieces
            attacked_count = 0
            for sq in chess.SQUARES:
                if board_after.is_attacked_by(coach_color, sq):
                    target = board_after.piece_at(sq)
                    if target and target.color == user_chess_color:
                        attacked_count += 1
            if attacked_count >= 2:
                teaching_point = "Watch out for knight forks! My knight attacks multiple pieces."
                
        elif piece.piece_type == chess.BISHOP:
            explanation = f"My Slicey Boi slides to {chess.square_name(to_square)}."
            # Check diagonal length
            plan = "Bishops love long diagonals - they can control the whole board from there!"
            teaching_point = "Bishops need open diagonals. Don't block them with your own pawns!"
            
        elif piece.piece_type == chess.ROOK:
            # Check if on open file
            file_pawns = 0
            for rank in range(8):
                sq = chess.square(to_file, rank)
                p = board_after.piece_at(sq)
                if p and p.piece_type == chess.PAWN:
                    file_pawns += 1
            
            if file_pawns == 0:
                explanation = f"My Tower lands on an open file with {move_san}!"
                plan = "Rooks dominate on open files. From here, I control the whole file."
                teaching_point = "Open files are rook highways! Put your rooks on files with no pawns."
            else:
                explanation = f"I'm activating my Tower with {move_san}."
                plan = "Getting my heavy pieces into the game."
                
        elif piece.piece_type == chess.QUEEN:
            explanation = f"My Queen moves to {chess.square_name(to_square)}."
            plan = "The Queen is powerful but needs to be careful not to get chased around."
            teaching_point = "Don't bring your Queen out too early - she can become a target!"
            
        elif piece.piece_type == chess.PAWN:
            if to_file in [3, 4]:  # d or e file
                explanation = f"I push my central pawn with {move_san}."
                plan = "Control the center! Central pawns are the foundation of a good position."
                teaching_point = "The center is king! Control d4, d5, e4, e5 and your pieces will be powerful."
            elif abs(chess.square_rank(move.from_square) - to_rank) == 2:
                explanation = f"My pawn advances two squares with {move_san}."
                plan = "Gaining space and fighting for central control."
            else:
                explanation = f"I push a pawn with {move_san}."
                plan = "Improving my pawn structure."
    
    # Default fallback
    if not explanation:
        explanation = f"I play {move_san}."
        plan = "Improving my position step by step."
    
    # Generate hint for user
    if threats:
        hint_for_user = f"Careful! {threats[0].replace('Your ', 'your ')}"
    elif not hint_for_user:
        hint_for_user = "Think about what you want to achieve. Development? King safety? Attack?"
    
    return {
        "move_san": move_san,
        "explanation": explanation,
        "plan": plan,
        "threats": threats,
        "teaching_point": teaching_point,
        "hint_for_user": hint_for_user
    }

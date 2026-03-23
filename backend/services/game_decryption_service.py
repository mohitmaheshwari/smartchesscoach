"""
Game Decryption Service
=======================

Generates move-by-move coaching narratives for an entire game.
This is computed DURING analysis time and stored with the game_analyses document.

The goal: Make every move in the game understandable in plain English.
For each move, explain:
- What happened (the move itself)
- What opponent was trying to do (their idea)
- What you should be thinking about
- Why the move was good/bad
- The principle to remember

Philosophy: "Decrypting a game" - not just showing engine lines, but making
the entire game story understandable to a human.
"""

import chess
import chess.pgn
import json
import os
import io
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Load coaching knowledge bases
COACHING_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "coaching")

def load_coaching_data():
    """Load all coaching JSON files."""
    data = {}
    try:
        with open(os.path.join(COACHING_DATA_DIR, "move_ideas.json"), "r") as f:
            data["move_ideas"] = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load move_ideas.json: {e}")
        data["move_ideas"] = {}
    
    try:
        with open(os.path.join(COACHING_DATA_DIR, "opponent_threats.json"), "r") as f:
            data["opponent_threats"] = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load opponent_threats.json: {e}")
        data["opponent_threats"] = {}
    
    try:
        with open(os.path.join(COACHING_DATA_DIR, "phase_principles.json"), "r") as f:
            data["phase_principles"] = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load phase_principles.json: {e}")
        data["phase_principles"] = {}
    
    return data

COACHING_DATA = None

def get_coaching_data():
    """Lazy load coaching data."""
    global COACHING_DATA
    if COACHING_DATA is None:
        COACHING_DATA = load_coaching_data()
    return COACHING_DATA


@dataclass
class MoveCoaching:
    """Coaching narrative for a single move."""
    move_number: int
    is_user_move: bool
    move_san: str
    fen_before: str
    fen_after: str
    
    # Game phase
    phase: str  # opening, middlegame, endgame
    
    # Core coaching content
    what_happened: str           # Plain English description of the move
    move_idea: str               # The idea behind this move
    opponent_last_idea: Optional[str]  # What opponent was trying with their last move
    your_focus: str              # What you should be thinking about here
    
    # For mistakes (cp_loss > 0)
    is_mistake: bool
    cp_loss: int
    mistake_type: Optional[str]
    what_you_missed: Optional[str]
    better_move: Optional[str]
    better_move_idea: Optional[str]
    principle: Optional[str]
    
    # For good moves
    is_good_move: bool
    praise: Optional[str]
    
    # Engine data (for reference)
    eval_before: Optional[int]
    eval_after: Optional[int]
    best_move_san: Optional[str]
    pv_line: Optional[List[str]]
    
    def to_dict(self) -> Dict:
        return asdict(self)


def detect_game_phase(board: chess.Board, move_number: int) -> str:
    """Detect the current game phase based on position and move number."""
    # Count material
    piece_count = len(board.piece_map())
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    minors = (len(board.pieces(chess.KNIGHT, chess.WHITE)) + len(board.pieces(chess.KNIGHT, chess.BLACK)) +
              len(board.pieces(chess.BISHOP, chess.WHITE)) + len(board.pieces(chess.BISHOP, chess.BLACK)))
    
    # Opening: first 10-12 moves, most pieces still on board
    if move_number <= 10 and piece_count >= 28:
        return "opening"
    
    # Endgame: queens traded or very few pieces
    if queens == 0 or piece_count <= 14:
        return "endgame"
    
    # Late middlegame transitioning to endgame
    if piece_count <= 20 or (queens <= 1 and minors <= 3):
        return "late_middlegame"
    
    return "middlegame"


def describe_move(board: chess.Board, move: chess.Move, move_san: str) -> str:
    """Generate a plain English description of what the move does."""
    piece = board.piece_at(move.from_square)
    if not piece:
        return f"Played {move_san}"
    
    piece_names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight", 
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king"
    }
    piece_name = piece_names.get(piece.piece_type, "piece")
    
    from_sq = chess.square_name(move.from_square)
    to_sq = chess.square_name(move.to_square)
    
    # Check for special moves
    if board.is_castling(move):
        if chess.square_file(move.to_square) > chess.square_file(move.from_square):
            return "Castled kingside, bringing the king to safety"
        else:
            return "Castled queenside, activating the rook"
    
    captured = board.piece_at(move.to_square)
    if captured:
        captured_name = piece_names.get(captured.piece_type, "piece")
        return f"Captured the {captured_name} on {to_sq} with the {piece_name}"
    
    # Development moves
    if piece.piece_type in [chess.KNIGHT, chess.BISHOP] and move.from_square in [
        chess.B1, chess.G1, chess.B8, chess.G8,  # Knights
        chess.C1, chess.F1, chess.C8, chess.F8   # Bishops
    ]:
        return f"Developed the {piece_name} to {to_sq}"
    
    # Pawn moves
    if piece.piece_type == chess.PAWN:
        if abs(chess.square_rank(move.to_square) - chess.square_rank(move.from_square)) == 2:
            return f"Advanced the pawn two squares to {to_sq}"
        if move.promotion:
            promo_name = piece_names.get(move.promotion, "queen")
            return f"Promoted the pawn to a {promo_name}!"
        return f"Pushed the pawn to {to_sq}"
    
    # General move
    return f"Moved the {piece_name} to {to_sq}"


def analyze_opponent_idea(board: chess.Board, last_move: Optional[chess.Move], last_move_san: Optional[str]) -> Optional[str]:
    """Analyze what the opponent was trying to achieve with their last move."""
    if not last_move or not last_move_san:
        return None
    
    # Look for threats created by opponent's move
    board_copy = board.copy()
    
    # Check if the move created an attack
    piece = board.piece_at(last_move.to_square)
    if not piece:
        return None
    
    piece_names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop", 
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king"
    }
    
    # Check what this piece now attacks
    attacked_squares = board_copy.attacks(last_move.to_square)
    valuable_targets = []
    
    for sq in attacked_squares:
        target = board_copy.piece_at(sq)
        if target and target.color != piece.color:
            target_name = piece_names.get(target.piece_type, "piece")
            valuable_targets.append((target.piece_type, target_name, chess.square_name(sq)))
    
    # Sort by piece value
    piece_values = {chess.QUEEN: 9, chess.ROOK: 5, chess.BISHOP: 3, chess.KNIGHT: 3, chess.PAWN: 1, chess.KING: 100}
    valuable_targets.sort(key=lambda x: piece_values.get(x[0], 0), reverse=True)
    
    if valuable_targets:
        top_target = valuable_targets[0]
        if top_target[0] == chess.KING:
            return f"They gave check, forcing you to respond to the king attack"
        return f"They're now attacking your {top_target[1]} on {top_target[2]}"
    
    # Check for pawn breaks or space gaining
    if piece.piece_type == chess.PAWN:
        to_file = chess.square_file(last_move.to_square)
        if to_file in [3, 4]:  # d or e file
            return "They're fighting for central control"
        if to_file in [0, 1]:  # a or b file
            return "They're creating pressure on the queenside"
        if to_file in [6, 7]:  # g or h file
            return "They're preparing a kingside attack"
    
    # Development
    if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
        return f"They developed their {piece_names[piece.piece_type]} to an active square"
    
    return "They're improving their position"


def get_phase_focus(phase: str, is_user_move: bool, board: chess.Board) -> str:
    """Get the main focus for this phase."""
    coaching_data = get_coaching_data()
    phase_data = coaching_data.get("phase_principles", {}).get(phase, {})
    
    if phase == "opening":
        if not board.has_castling_rights(chess.WHITE) and not board.has_castling_rights(chess.BLACK):
            return "Both sides have castled. Now it's time to form a plan for the middlegame."
        if board.has_castling_rights(chess.WHITE if board.turn == chess.WHITE else chess.BLACK):
            return "Don't forget to castle! King safety is crucial."
        return "Focus on developing your remaining pieces and controlling the center."
    
    if phase == "middlegame" or phase == "late_middlegame":
        return "Look for tactical opportunities while improving your worst-placed piece."
    
    if phase == "endgame":
        return "Activate your king! In the endgame, the king is a strong piece that should move to the center."
    
    return "Think about what your opponent wants to do, then make your plan."


def analyze_mistake(
    board_before: chess.Board,
    played_move: chess.Move,
    played_san: str,
    best_move_san: str,
    cp_loss: int,
    eval_before: int,
    eval_after: int,
    cognitive_gap: Optional[str] = None,
    coaching_focus: Optional[str] = None
) -> Dict[str, str]:
    """Analyze why a move was a mistake and what should have been played."""
    coaching_data = get_coaching_data()
    
    result = {
        "what_you_missed": "",
        "better_move_idea": "",
        "principle": ""
    }
    
    # Determine mistake severity and type
    if cp_loss >= 300:
        severity = "blunder"
    elif cp_loss >= 150:
        severity = "mistake"
    elif cp_loss >= 50:
        severity = "inaccuracy"
    else:
        severity = "minor"
    
    # Use cognitive gap if available
    if cognitive_gap:
        gap_lower = cognitive_gap.lower()
        if "threat" in gap_lower or "ignored" in gap_lower:
            result["what_you_missed"] = "You missed what your opponent was threatening"
            result["principle"] = "Before every move, ask: What is my opponent threatening?"
        elif "hanging" in gap_lower:
            result["what_you_missed"] = "You left a piece undefended"
            result["principle"] = "Before moving, check: Are all my pieces protected?"
        elif "calculation" in gap_lower or "short" in gap_lower:
            result["what_you_missed"] = "You stopped calculating too early"
            result["principle"] = "Always look one move deeper than your first instinct"
        elif "tactical" in gap_lower:
            result["what_you_missed"] = "You missed a tactical opportunity"
            result["principle"] = "Check for checks, captures, and threats on every move"
        elif "positional" in gap_lower:
            result["what_you_missed"] = "The move weakened your position"
            result["principle"] = "Consider the long-term effects of your moves"
    
    # Use coaching focus if available and we haven't set content yet
    if coaching_focus and not result["what_you_missed"]:
        result["what_you_missed"] = coaching_focus
    
    # Fallback based on severity
    if not result["what_you_missed"]:
        if severity == "blunder":
            result["what_you_missed"] = f"This move lost significant material or position (about {cp_loss/100:.1f} pawns worth)"
        elif severity == "mistake":
            result["what_you_missed"] = f"This move weakened your position (about {cp_loss/100:.1f} pawns)"
        else:
            result["what_you_missed"] = "There was a better option available"
    
    if not result["principle"]:
        common_mistakes = coaching_data.get("move_ideas", {}).get("common_mistakes", {})
        if severity == "blunder":
            result["principle"] = "Take your time before making big decisions"
        else:
            result["principle"] = "Consider multiple candidate moves before choosing"
    
    # Describe the better move
    if best_move_san:
        try:
            best_move = board_before.parse_san(best_move_san)
            result["better_move_idea"] = describe_move(board_before, best_move, best_move_san)
        except:
            result["better_move_idea"] = f"The better move was {best_move_san}"
    
    return result


def generate_move_coaching(
    board_before: chess.Board,
    move: chess.Move,
    move_san: str,
    move_number: int,
    is_user_move: bool,
    user_color: str,
    last_opponent_move: Optional[chess.Move] = None,
    last_opponent_san: Optional[str] = None,
    eval_data: Optional[Dict] = None
) -> MoveCoaching:
    """
    Generate complete coaching narrative for a single move.
    
    Args:
        board_before: Position before the move
        move: The move played
        move_san: Move in SAN notation
        move_number: The full move number
        is_user_move: Whether this is the user's move
        user_color: "white" or "black"
        last_opponent_move: Opponent's previous move (for context)
        last_opponent_san: Opponent's previous move in SAN
        eval_data: Stockfish evaluation data for this move
    
    Returns:
        MoveCoaching object with full narrative
    """
    eval_data = eval_data or {}
    
    # Get FEN after move
    board_after = board_before.copy()
    board_after.push(move)
    fen_before = board_before.fen()
    fen_after = board_after.fen()
    
    # Detect phase
    phase = detect_game_phase(board_before, move_number)
    
    # Generate description
    what_happened = describe_move(board_before, move, move_san)
    
    # Get move idea based on piece and destination
    piece = board_before.piece_at(move.from_square)
    move_idea = get_move_idea(board_before, move, piece)
    
    # Analyze opponent's last move (only relevant for user's moves)
    opponent_last_idea = None
    if is_user_move and last_opponent_move:
        opponent_last_idea = analyze_opponent_idea(board_before, last_opponent_move, last_opponent_san)
    
    # Get phase-appropriate focus
    your_focus = get_phase_focus(phase, is_user_move, board_before)
    
    # Check for mistakes
    cp_loss = abs(eval_data.get("cp_loss", 0))
    is_mistake = cp_loss >= 50 and is_user_move
    mistake_type = None
    what_you_missed = None
    better_move = None
    better_move_idea = None
    principle = None
    
    if is_mistake:
        best_move_san = eval_data.get("best_move")
        eval_before = eval_data.get("eval_before", 0)
        eval_after = eval_data.get("eval_after", 0)
        cognitive_gap = eval_data.get("cognitive_gap")
        coaching_focus = eval_data.get("coaching_focus")
        
        mistake_analysis = analyze_mistake(
            board_before, move, move_san, best_move_san,
            cp_loss, eval_before, eval_after,
            cognitive_gap, coaching_focus
        )
        
        what_you_missed = mistake_analysis["what_you_missed"]
        better_move = best_move_san
        better_move_idea = mistake_analysis["better_move_idea"]
        principle = mistake_analysis["principle"]
        
        if cp_loss >= 300:
            mistake_type = "blunder"
        elif cp_loss >= 150:
            mistake_type = "mistake"
        else:
            mistake_type = "inaccuracy"
    
    # Check for good moves
    is_good_move = cp_loss <= 10 and is_user_move
    praise = None
    if is_good_move and is_user_move:
        if cp_loss == 0:
            praise = "Perfect move! This is exactly what the position needed."
        else:
            praise = "Good move! You found a strong continuation."
    
    return MoveCoaching(
        move_number=move_number,
        is_user_move=is_user_move,
        move_san=move_san,
        fen_before=fen_before,
        fen_after=fen_after,
        phase=phase,
        what_happened=what_happened,
        move_idea=move_idea,
        opponent_last_idea=opponent_last_idea,
        your_focus=your_focus,
        is_mistake=is_mistake,
        cp_loss=cp_loss,
        mistake_type=mistake_type,
        what_you_missed=what_you_missed,
        better_move=better_move,
        better_move_idea=better_move_idea,
        principle=principle,
        is_good_move=is_good_move,
        praise=praise,
        eval_before=eval_data.get("eval_before"),
        eval_after=eval_data.get("eval_after"),
        best_move_san=eval_data.get("best_move"),
        pv_line=eval_data.get("pv_after_best", [])[:5]  # First 5 moves of best line
    )


def get_move_idea(board: chess.Board, move: chess.Move, piece: Optional[chess.Piece]) -> str:
    """Get the strategic idea behind a move."""
    if not piece:
        return "Improving the position"
    
    coaching_data = get_coaching_data()
    piece_ideas = coaching_data.get("move_ideas", {}).get("piece_intentions", {})
    
    piece_type_names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king"
    }
    
    piece_type = piece_type_names.get(piece.piece_type, "piece")
    ideas = piece_ideas.get(piece_type, {})
    
    to_file = chess.square_file(move.to_square)
    to_rank = chess.square_rank(move.to_square)
    
    # Castling
    if board.is_castling(move):
        return ideas.get("castle", "Getting the king to safety and connecting rooks")
    
    # Capture
    if board.is_capture(move):
        return ideas.get("capture", "Winning material or exchanging pieces")
    
    # Piece-specific logic
    if piece.piece_type == chess.PAWN:
        if to_file in [3, 4] and to_rank in [3, 4]:
            return ideas.get("advance_center", "Fighting for central control")
        if to_file in [0, 1, 6, 7]:
            return ideas.get("advance_wing", "Creating chances on the flank")
        return ideas.get("push", "Gaining space")
    
    if piece.piece_type == chess.KNIGHT:
        if to_file in [2, 3, 4, 5] and to_rank in [2, 3, 4, 5]:
            return ideas.get("centralize", "Knights are strongest in the center")
        return ideas.get("attack", "Positioning for action")
    
    if piece.piece_type == chess.BISHOP:
        # Check if fianchetto position
        if (move.to_square in [chess.G2, chess.B2, chess.G7, chess.B7]):
            return ideas.get("fianchetto", "Controlling the long diagonal")
        return ideas.get("open_diagonal", "Activating on a diagonal")
    
    if piece.piece_type == chess.ROOK:
        # Check for open file
        file = chess.square_file(move.to_square)
        pawns_on_file = False
        for rank in range(8):
            sq = chess.square(file, rank)
            p = board.piece_at(sq)
            if p and p.piece_type == chess.PAWN:
                pawns_on_file = True
                break
        if not pawns_on_file:
            return ideas.get("open_file", "Controlling an open file")
        if to_rank in [1, 6]:  # 2nd or 7th rank
            return ideas.get("seventh_rank", "Invading the 7th rank")
        return ideas.get("defend", "Supporting the position")
    
    if piece.piece_type == chess.QUEEN:
        return ideas.get("coordinate", "Preparing to create threats")
    
    if piece.piece_type == chess.KING:
        # Endgame king activity
        if len(board.piece_map()) < 16:
            return ideas.get("activate", "In the endgame, the king becomes a fighting piece")
        return ideas.get("shelter", "Keeping the king safe")
    
    return "Improving the position"


def generate_game_decryption(
    pgn: str,
    user_color: str,
    move_evaluations: List[Dict]
) -> List[Dict]:
    """
    Generate complete move-by-move coaching for an entire game.
    
    This is called during analysis_worker processing after Stockfish analysis.
    The result is stored in game_analyses.decryption_data.
    
    Args:
        pgn: The game PGN
        user_color: "white" or "black"
        move_evaluations: List of Stockfish move evaluations
    
    Returns:
        List of MoveCoaching dictionaries
    """
    try:
        board = chess.Board()
        decryption_data = []
        
        # Parse PGN to get moves
        game = chess.pgn.read_game(io.StringIO(pgn))
        if not game:
            logger.error("Could not parse PGN")
            return []
        
        moves = list(game.mainline_moves())
        
        # Build evaluation lookup by move index
        eval_lookup = {}
        for eval_data in move_evaluations:
            # Try to match by FEN or move number
            move_num = eval_data.get("move_number", 0)
            is_user = eval_data.get("is_user_move", False)
            # Store with a key that combines move info
            idx = eval_data.get("move_index", -1)
            if idx >= 0:
                eval_lookup[idx] = eval_data
            else:
                # Fallback: try to match by FEN
                fen = eval_data.get("fen_before", "")
                if fen:
                    eval_lookup[fen] = eval_data
        
        last_opponent_move = None
        last_opponent_san = None
        
        for idx, move in enumerate(moves):
            move_san = board.san(move)
            full_move_number = (idx // 2) + 1
            is_white_move = (idx % 2 == 0)
            is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
            
            # Get evaluation data for this move
            eval_data = eval_lookup.get(idx, {})
            if not eval_data:
                # Try FEN lookup
                eval_data = eval_lookup.get(board.fen(), {})
            
            # Generate coaching
            coaching = generate_move_coaching(
                board_before=board,
                move=move,
                move_san=move_san,
                move_number=full_move_number,
                is_user_move=is_user_move,
                user_color=user_color,
                last_opponent_move=last_opponent_move if is_user_move else None,
                last_opponent_san=last_opponent_san if is_user_move else None,
                eval_data=eval_data
            )
            
            decryption_data.append(coaching.to_dict())
            
            # Track opponent's move for context
            if not is_user_move:
                last_opponent_move = move
                last_opponent_san = move_san
            
            # Make the move on the board
            board.push(move)
        
        logger.info(f"Generated decryption data for {len(decryption_data)} moves")
        return decryption_data
        
    except Exception as e:
        logger.error(f"Error generating game decryption: {e}")
        import traceback
        traceback.print_exc()
        return []


def generate_game_summary(decryption_data: List[Dict], user_color: str) -> Dict:
    """
    Generate a summary of the game based on the decryption data.
    
    Returns:
        {
            "total_moves": 45,
            "user_moves": 23,
            "mistakes": 3,
            "good_moves": 15,
            "phases": {"opening": 10, "middlegame": 25, "endgame": 10},
            "key_moments": [{"move_number": 15, "type": "mistake", "summary": "..."}],
            "overall_message": "You played solidly but missed a key tactic on move 15..."
        }
    """
    if not decryption_data:
        return {"error": "No data available"}
    
    user_moves = [m for m in decryption_data if m.get("is_user_move")]
    mistakes = [m for m in user_moves if m.get("is_mistake")]
    good_moves = [m for m in user_moves if m.get("is_good_move")]
    
    # Count by phase
    phases = {"opening": 0, "middlegame": 0, "late_middlegame": 0, "endgame": 0}
    for m in decryption_data:
        phase = m.get("phase", "middlegame")
        phases[phase] = phases.get(phase, 0) + 1
    
    # Key moments
    key_moments = []
    for m in mistakes:
        if m.get("cp_loss", 0) >= 100:
            key_moments.append({
                "move_number": m.get("move_number"),
                "type": m.get("mistake_type", "mistake"),
                "move": m.get("move_san"),
                "summary": m.get("what_you_missed", "A mistake occurred here")
            })
    
    # Generate overall message
    if not mistakes:
        overall = "Excellent game! You played with very few inaccuracies."
    elif len(mistakes) <= 2:
        overall = f"Solid play overall. Review the {len(mistakes)} critical moment(s) to improve further."
    else:
        worst = max(mistakes, key=lambda m: m.get("cp_loss", 0))
        overall = f"Focus on move {worst.get('move_number')}: {worst.get('what_you_missed', 'This was the turning point')}."
    
    return {
        "total_moves": len(decryption_data),
        "user_moves": len(user_moves),
        "mistakes": len(mistakes),
        "good_moves": len(good_moves),
        "phases": phases,
        "key_moments": key_moments[:5],  # Top 5
        "overall_message": overall
    }

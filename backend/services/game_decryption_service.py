"""
Game Decryption Service v3
==========================

Coach-quality, intent-aware, move-by-move coaching.

KEY IMPROVEMENTS over v2:
1. Move Intent Recognition: Understands WHY the user played a move (e.g., h6 to prevent Ng5)
2. Empathetic Sideline Warnings: Acknowledges valid ideas before correcting
3. Main Line Theory: Explains what theory recommends and why
4. Opening Introduction: Rich context about the opening being played

Philosophy: A great coach first understands your thinking, then guides you forward.
"""

import chess
import chess.pgn
import json
import os
import io
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Load coaching knowledge bases
COACHING_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "coaching")

def load_json_safe(filepath: str) -> dict:
    """Safely load a JSON file."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {filepath}: {e}")
        return {}

# Lazy load all coaching data
_COACHING_CACHE = {}

def get_coaching_data(key: str) -> dict:
    """Lazy load coaching data."""
    global _COACHING_CACHE
    if key not in _COACHING_CACHE:
        filepath = os.path.join(COACHING_DATA_DIR, f"{key}.json")
        _COACHING_CACHE[key] = load_json_safe(filepath)
    return _COACHING_CACHE[key]


@dataclass
class MoveCoaching:
    """Coaching narrative for a single move."""
    move_number: int
    is_user_move: bool
    move_san: str
    fen_before: str
    fen_after: str
    
    # Game context
    phase: str
    opening_name: Optional[str]
    
    # Core coaching - THE GOLD
    what_happened: str
    move_idea: str
    opponent_last_idea: Optional[str]
    your_focus: str
    
    # V3: Intent recognition
    intent_acknowledged: Optional[str] = None
    
    # For mistakes
    is_mistake: bool = False
    cp_loss: int = 0
    mistake_type: Optional[str] = None
    what_you_missed: Optional[str] = None
    better_move: Optional[str] = None
    better_move_idea: Optional[str] = None
    principle: Optional[str] = None
    
    # For good moves
    is_good_move: bool = False
    praise: Optional[str] = None
    
    # Opening theory check
    is_sideline: bool = False
    sideline_warning: Optional[str] = None
    main_line_moves: Optional[List[str]] = None
    main_line_theory: Optional[Dict] = None
    
    # Engine data
    eval_before: Optional[int] = None
    eval_after: Optional[int] = None
    best_move_san: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


def detect_opening_from_pgn(pgn: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract opening name and ECO code from PGN headers."""
    opening_name = None
    eco_code = None
    
    eco_match = re.search(r'\[ECO\s+"([^"]+)"\]', pgn)
    if eco_match:
        eco_code = eco_match.group(1)
    
    opening_match = re.search(r'\[Opening\s+"([^"]+)"\]', pgn)
    if opening_match:
        opening_name = opening_match.group(1)
    
    if not opening_name:
        eco_url_match = re.search(r'\[ECOUrl\s+"[^"]*openings/([^"]+)"\]', pgn)
        if eco_url_match:
            slug = eco_url_match.group(1)
            opening_name = slug.replace("-", " ").title()
    
    return opening_name, eco_code


def get_opening_data(eco_code: Optional[str], opening_name: Optional[str]) -> dict:
    """Get opening-specific coaching data based on ECO code or name."""
    opening_plans = get_coaching_data("opening_plans")
    
    if not opening_plans:
        return opening_plans.get("default", {})
    
    if eco_code:
        eco_prefix = eco_code[:2] if len(eco_code) >= 2 else eco_code
        for key, data in opening_plans.items():
            if key.startswith("_"):
                continue
            prefixes = data.get("eco_prefix", [])
            if eco_code in prefixes or eco_prefix in [p[:2] for p in prefixes]:
                return data
    
    if opening_name:
        name_lower = opening_name.lower()
        for key, data in opening_plans.items():
            if key.startswith("_"):
                continue
            if key.replace("_", " ") in name_lower or data.get("name", "").lower() in name_lower:
                return data
        
        keywords = {
            "queens_indian": ["queen's indian", "queens indian", "e14", "e15", "e16", "e17", "e18"],
            "london_system": ["london"],
            "sicilian_najdorf": ["najdorf", "sicilian najdorf"],
            "italian_game": ["italian", "giuoco piano", "two knights"],
            "caro_kann": ["caro-kann", "caro kann"],
            "french_defense": ["french"],
            "kings_indian": ["king's indian", "kings indian"],
            "ruy_lopez": ["ruy lopez", "spanish", "morphy"]
        }
        
        for opening_key, kws in keywords.items():
            for kw in kws:
                if kw in name_lower:
                    if opening_key in opening_plans:
                        return opening_plans[opening_key]
    
    return opening_plans.get("default", {})


def generate_opening_introduction(opening_data: dict, opening_name: Optional[str], user_color: str) -> Optional[Dict]:
    """
    Generate a rich opening introduction card.
    
    Returns context about the opening: what it is, plans for both sides,
    and what the user should focus on.
    """
    if not opening_data or opening_data.get("name") == "General Opening":
        return None
    
    name = opening_data.get("name", opening_name or "Unknown Opening")
    intro_text = opening_data.get("introduction")
    white_plan = opening_data.get("white_plan", "")
    black_plan = opening_data.get("black_plan", "")
    phase_focus = opening_data.get("phase_focus", {})
    opening_focus = phase_focus.get("opening", "")
    
    # Build a coach-like introduction
    if not intro_text:
        intro_text = f"This is the {name}."
        if white_plan:
            intro_text += f" White's goal is to {white_plan.lower().rstrip('.')}."
        if black_plan:
            intro_text += f" Black's strategy is to {black_plan.lower().rstrip('.')}."
    
    # Determine which plan is relevant to the user
    your_plan = white_plan if user_color == "white" else black_plan
    their_plan = black_plan if user_color == "white" else white_plan
    
    return {
        "name": name,
        "description": intro_text,
        "your_plan": your_plan,
        "their_plan": their_plan,
        "key_focus": opening_focus,
        "common_mistakes": opening_data.get("common_mistakes", {}),
    }


def detect_phase(board: chess.Board, move_number: int) -> str:
    """Detect game phase based on position and move count."""
    piece_count = len(board.piece_map())
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    
    if move_number <= 10 and piece_count >= 28:
        return "opening"
    if move_number <= 15 and piece_count >= 24:
        return "opening"
    if queens == 0 or piece_count <= 12:
        return "endgame"
    if piece_count <= 18:
        return "endgame"
    return "middlegame"


def recognize_move_intent(
    move_san: str,
    opening_data: dict,
    board: chess.Board,
    is_user_move: bool
) -> Optional[Dict]:
    """
    Try to recognize the strategic intent behind a move.
    
    Checks opening-specific move_intents data, then falls back to
    positional pattern recognition.
    
    Returns:
        {
            "likely_idea": "Preventing Ng5 jump",
            "evaluation": "Creative but slow...",
            "suggestion": "Consider Bc5 or Nf6 first..."
        }
        or None if no intent recognized.
    """
    if not is_user_move:
        return None
    
    # Check opening-specific intents first
    move_intents = opening_data.get("move_intents", {})
    if move_san in move_intents:
        return move_intents[move_san]
    
    # Fallback: common positional intent patterns
    if len(move_san) == 2 and move_san[0] in 'abcdefgh':
        # Pawn move — try to figure out what it prevents/prepares
        pawn_to = chess.parse_square(move_san)
        pawn_file = chess.square_file(pawn_to)
        
        # h6/h3 or g6/g3 — often prevent bishop/knight intrusions
        if move_san in ['h6', 'h3']:
            # Check if opponent has a knight that could jump to g5/g4
            opp_color = not board.turn
            for sq in board.pieces(chess.KNIGHT, opp_color):
                knight_attacks = board.attacks(sq)
                target = chess.G5 if move_san == 'h6' else chess.G4
                if target in knight_attacks:
                    return {
                        "likely_idea": f"Preventing the knight from jumping to {'g5' if move_san == 'h6' else 'g4'}",
                        "evaluation": "A defensive idea, but it costs a tempo.",
                        "suggestion": "Consider if developing a piece achieves the same goal more efficiently."
                    }
            # Check for bishop intrusions
            for sq in board.pieces(chess.BISHOP, opp_color):
                bishop_attacks = board.attacks(sq)
                target = chess.G5 if move_san == 'h6' else chess.G4
                if target in bishop_attacks:
                    return {
                        "likely_idea": f"Preventing the bishop from pinning on {'g5' if move_san == 'h6' else 'g4'}",
                        "evaluation": "Reasonable prophylaxis, but check if it's the right moment.",
                        "suggestion": "Sometimes developing first is more urgent than preventing a pin."
                    }
        
        if move_san in ['a6', 'a3']:
            # Often prevents Bb5/Bb4
            return {
                "likely_idea": f"Preventing bishop checks or pins on the {'queenside' if pawn_file == 0 else 'kingside'}",
                "evaluation": "Flexible but costs a tempo.",
                "suggestion": "Make sure you have time for this — developing pieces is usually more urgent."
            }
    
    return None


def build_intent_coaching(
    intent: Dict,
    move_san: str,
    opening_data: dict,
    is_sideline: bool,
    main_lines: Optional[Dict]
) -> Tuple[str, str]:
    """
    Build empathetic what_happened and move_idea from intent data.
    
    The coaching flow:
    1. Acknowledge: "You played h6 to prevent Ng5 — that's a valid idea"
    2. Correct: "However, the main lines are Bc5/Nf6 because..."
    """
    likely_idea = intent.get("likely_idea", "")
    evaluation = intent.get("evaluation", "")
    suggestion = intent.get("suggestion", "")
    
    # Build the acknowledgment
    what_happened = f"You played {move_san}"
    if likely_idea:
        what_happened += f" — {likely_idea.lower().rstrip('.')}. {evaluation}"
    
    # Build the coaching idea
    if suggestion:
        move_idea = suggestion
    elif is_sideline and main_lines:
        # Use main line data to explain what's better
        explanation = main_lines.get("explanation", "")
        theory_moves = main_lines.get("theory", [])
        if theory_moves:
            move_idea = f"The main theoretical moves here are {' or '.join(theory_moves)}. {explanation}"
        else:
            move_idea = evaluation
    else:
        move_idea = evaluation or "Consider the position carefully."
    
    return what_happened, move_idea


def check_sideline(
    move_san: str,
    move_number: int,
    is_user_move: bool,
    opening_data: dict,
    phase: str
) -> Tuple[bool, Optional[str], Optional[List[str]], Optional[Dict]]:
    """
    Check if a move is a sideline (deviation from main theory).
    
    V3: Returns richer data including main line theory explanations.
    
    Returns:
        (is_sideline, warning_message, main_line_moves, main_line_theory)
    """
    if phase != "opening":
        return False, None, None, None
    
    if not is_user_move:
        return False, None, None, None
    
    # Check for explicit sideline warnings
    sideline_warnings = opening_data.get("sideline_warnings", {})
    if move_san in sideline_warnings:
        warning = sideline_warnings[move_san]
        
        # Get main line moves and theory
        main_lines = opening_data.get("main_lines", {})
        main_moves = None
        main_theory = None
        
        for key, line_data in main_lines.items():
            if isinstance(line_data, dict):
                theory_moves = line_data.get("theory", [])
                if theory_moves:
                    main_moves = theory_moves
                    main_theory = {
                        "position": line_data.get("position", ""),
                        "best": line_data.get("best", ""),
                        "explanation": line_data.get("explanation", ""),
                        "lines": line_data.get("lines", {})
                    }
                    break
        
        # Check if we have intent data — make warning more empathetic
        move_intents = opening_data.get("move_intents", {})
        if move_san in move_intents:
            intent = move_intents[move_san]
            likely_idea = intent.get("likely_idea", "")
            if likely_idea:
                # Rewrite warning to be empathetic
                warning = f"I see you played {move_san} ({likely_idea.lower().rstrip('.')}). That's a reasonable thought! However, {warning.lower().lstrip(move_san).lstrip(' -').strip()}"
        
        return True, warning, main_moves, main_theory
    
    # Check if move is NOT in typical_ideas and we're in early opening
    if move_number <= 6:
        typical_ideas = opening_data.get("typical_ideas", {})
        if move_san not in typical_ideas:
            if len(move_san) == 2 and move_san[0] in 'abcdefgh':
                if move_san not in ['e4', 'e5', 'd4', 'd5', 'c4', 'c5', 'c6', 'e6', 'd6', 'b6', 'g6']:
                    return True, f"{move_san} is unusual here. Consider developing a piece instead.", None, None
    
    return False, None, None, None


def get_piece_name(piece: chess.Piece) -> str:
    """Get human-readable piece name."""
    names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king"
    }
    return names.get(piece.piece_type, "piece")


def describe_move_rich(
    board: chess.Board, 
    move: chess.Move, 
    move_san: str,
    opening_data: dict,
    phase: str,
    is_user_move: bool,
    intent: Optional[Dict] = None
) -> Tuple[str, str]:
    """
    Generate rich description and idea for a move.
    
    V3: Uses intent data for user moves when available.
    """
    piece = board.piece_at(move.from_square)
    if not piece:
        return f"Played {move_san}", "Improving the position"
    
    to_sq = chess.square_name(move.to_square)
    piece_name = get_piece_name(piece)
    
    # V3: If we have recognized intent for this user move, use it
    if intent and is_user_move:
        main_lines = opening_data.get("main_lines", {})
        # Find the relevant main line
        relevant_main_line = None
        for key, line_data in main_lines.items():
            if isinstance(line_data, dict):
                relevant_main_line = line_data
                break
        
        return build_intent_coaching(intent, move_san, opening_data, True, relevant_main_line)
    
    # Check for opening-specific move ideas
    typical_ideas = opening_data.get("typical_ideas", {})
    if move_san in typical_ideas:
        specific_idea = typical_ideas[move_san]
        
        if board.is_castling(move):
            if chess.square_file(move.to_square) > chess.square_file(move.from_square):
                what_happened = "Castled kingside"
            else:
                what_happened = "Castled queenside"
        elif board.is_capture(move):
            captured = board.piece_at(move.to_square)
            captured_name = get_piece_name(captured) if captured else "piece"
            what_happened = f"Captured the {captured_name} on {to_sq}"
        elif piece.piece_type == chess.PAWN:
            what_happened = f"Played {move_san}"
        else:
            what_happened = f"Played {move_san} ({piece_name} to {to_sq})"
        
        return what_happened, specific_idea
    
    # Generate generic but meaningful description
    if board.is_castling(move):
        if chess.square_file(move.to_square) > chess.square_file(move.from_square):
            return "Castled kingside", "Getting the king to safety and connecting the rooks"
        else:
            return "Castled queenside", "Connecting the rooks while keeping attacking chances"
    
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        captured_name = get_piece_name(captured) if captured else "piece"
        what_happened = f"Captured the {captured_name} on {to_sq} with the {piece_name}"
        
        if captured and captured.piece_type == piece.piece_type:
            move_idea = f"Trading {piece_name}s — simplifying the position"
        elif captured and captured.piece_type > piece.piece_type:
            move_idea = "Winning material!"
        else:
            move_idea = "Exchanging pieces"
        
        return what_happened, move_idea
    
    # Development moves
    back_rank_squares = {
        chess.WHITE: [chess.A1, chess.B1, chess.C1, chess.D1, chess.E1, chess.F1, chess.G1, chess.H1],
        chess.BLACK: [chess.A8, chess.B8, chess.C8, chess.D8, chess.E8, chess.F8, chess.G8, chess.H8]
    }
    
    if move.from_square in back_rank_squares.get(piece.color, []):
        if piece.piece_type == chess.KNIGHT:
            if chess.square_file(move.to_square) in [2, 3, 4, 5]:
                return f"Developed the knight to {to_sq}", "Bringing the knight toward the center where it controls more squares"
            else:
                return f"Developed the knight to {to_sq}", "Getting the knight into the game"
        
        if piece.piece_type == chess.BISHOP:
            if move.to_square in [chess.G2, chess.B2, chess.G7, chess.B7]:
                return f"Fianchettoed the bishop to {to_sq}", "Placing the bishop on the long diagonal for maximum influence"
            return f"Developed the bishop to {to_sq}", "Activating the bishop on an open diagonal"
        
        if piece.piece_type == chess.ROOK:
            return f"Developed the rook to {to_sq}", "Getting the rook to an open or semi-open file"
    
    # Pawn moves
    if piece.piece_type == chess.PAWN:
        to_file = chess.square_file(move.to_square)
        to_rank = chess.square_rank(move.to_square)
        
        if move.promotion:
            promo_piece = get_piece_name(chess.Piece(move.promotion, piece.color))
            return f"Promoted the pawn to a {promo_piece}!", "Creating a new powerful piece"
        
        if to_file in [3, 4] and to_rank in [3, 4]:
            return f"Played {move_san}", "Fighting for control of the center"
        
        if abs(chess.square_rank(move.to_square) - chess.square_rank(move.from_square)) == 2:
            if to_file in [2, 5]:
                return f"Played {move_san}", "Preparing a pawn break to challenge the center"
            return f"Played {move_san}", "Advancing the pawn two squares to gain space"
        
        return f"Played {move_san}", "Advancing the pawn to gain space"
    
    # Knight moves
    if piece.piece_type == chess.KNIGHT:
        center_squares = [chess.D4, chess.D5, chess.E4, chess.E5, chess.C4, chess.C5, chess.F4, chess.F5]
        if move.to_square in center_squares:
            return f"Centralized the knight on {to_sq}", "Knights are strongest in the center"
        return f"Moved the knight to {to_sq}", "Repositioning the knight"
    
    # Bishop moves
    if piece.piece_type == chess.BISHOP:
        return f"Moved the bishop to {to_sq}", "Improving the bishop's diagonal"
    
    # Rook moves
    if piece.piece_type == chess.ROOK:
        to_file = chess.square_file(move.to_square)
        has_pawns_on_file = False
        for rank in range(8):
            sq = chess.square(to_file, rank)
            p = board.piece_at(sq)
            if p and p.piece_type == chess.PAWN:
                has_pawns_on_file = True
                break
        
        if not has_pawns_on_file:
            return f"Placed the rook on {to_sq}", "Controlling the open file"
        
        if (piece.color == chess.WHITE and chess.square_rank(move.to_square) == 6) or \
           (piece.color == chess.BLACK and chess.square_rank(move.to_square) == 1):
            return f"Invaded with the rook to {to_sq}", "Rook on the 7th rank — very powerful!"
        
        return f"Moved the rook to {to_sq}", "Repositioning the rook"
    
    # Queen moves
    if piece.piece_type == chess.QUEEN:
        return f"Moved the queen to {to_sq}", "Repositioning the most powerful piece"
    
    # King moves (non-castling)
    if piece.piece_type == chess.KING:
        if phase == "endgame":
            center_files = [2, 3, 4, 5]
            if chess.square_file(move.to_square) in center_files:
                return f"Activated the king to {to_sq}", "In the endgame, the king is a fighting piece — bring it to the center!"
            return f"Moved the king to {to_sq}", "The king must be active in the endgame"
        return f"Moved the king to {to_sq}", "Adjusting king position"
    
    return f"Played {move_san}", "Improving the position"


def analyze_opponent_idea_rich(
    board: chess.Board,
    last_move: Optional[chess.Move],
    last_move_san: Optional[str],
    opening_data: dict
) -> Optional[str]:
    """Analyze what the opponent was trying to achieve with their last move."""
    if not last_move:
        return None
    
    piece = board.piece_at(last_move.to_square)
    if not piece:
        return None
    
    # Check opening-specific ideas first
    typical_ideas = opening_data.get("typical_ideas", {})
    if last_move_san in typical_ideas:
        idea = typical_ideas[last_move_san]
        return f"They played {last_move_san} — {idea}"
    
    piece_name = get_piece_name(piece)
    
    # Check for direct attacks on pieces
    attacks = board.attacks(last_move.to_square)
    threats = []
    
    for sq in attacks:
        target = board.piece_at(sq)
        if target and target.color != piece.color:
            target_name = get_piece_name(target)
            target_sq = chess.square_name(sq)
            threats.append((target.piece_type, target_name, target_sq))
    
    threats.sort(key=lambda x: x[0], reverse=True)
    
    if threats:
        top_threat = threats[0]
        if top_threat[0] == chess.KING:
            return "They gave check! You must respond to the attack on your king"
        if top_threat[0] >= chess.ROOK:
            return f"They're attacking your {top_threat[1]} on {top_threat[2]} — it needs to move or be defended"
        if len(threats) >= 2:
            return f"They're creating multiple threats — attacking your {threats[0][1]} and {threats[1][1]}"
        return f"They're now threatening your {top_threat[1]} on {top_threat[2]}"
    
    if piece.piece_type == chess.PAWN:
        to_file = chess.square_file(last_move.to_square)
        to_rank = chess.square_rank(last_move.to_square)
        
        if abs(chess.square_rank(last_move.to_square) - chess.square_rank(last_move.from_square)) == 2:
            return "They advanced their pawn aggressively — gaining space"
        if to_file in [3, 4] and to_rank in [3, 4]:
            return "They're fighting for central control"
        if to_file in [0, 1]:
            return "They're creating pressure on the queenside"
        if to_file in [6, 7]:
            return "They're preparing a kingside attack"
    
    if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
        return f"They developed their {piece_name} to an active square"
    
    if board.is_castling(last_move):
        return "They castled — their king is now safe"
    
    return "They're improving their position"


def get_dynamic_focus(
    phase: str,
    board: chess.Board,
    is_user_move: bool,
    opening_data: dict,
    move_number: int,
    user_has_castled: bool
) -> str:
    """Generate context-aware focus message based on position."""
    phase_focus = opening_data.get("phase_focus", {})
    
    if board.is_check():
        return "You're in check! You must get out of check."
    
    if phase == "opening":
        can_castle = board.has_castling_rights(chess.WHITE if board.turn == chess.WHITE else chess.BLACK)
        
        if not user_has_castled and can_castle and move_number >= 6:
            return "Consider castling soon — king safety is important"
        
        if move_number <= 5:
            return phase_focus.get("opening", "Focus on controlling the center and developing your pieces")
        
        if move_number <= 10:
            developed_minors = 0
            color = chess.WHITE if board.turn == chess.WHITE else chess.BLACK
            for sq in board.pieces(chess.KNIGHT, color) | board.pieces(chess.BISHOP, color):
                back_rank = 0 if color == chess.WHITE else 7
                if chess.square_rank(sq) != back_rank:
                    developed_minors += 1
            
            if developed_minors < 3:
                return "Continue developing your pieces before starting an attack"
            
            return phase_focus.get("opening", "Complete your development and prepare for the middlegame")
    
    if phase == "middlegame":
        if "pawn break" in opening_data.get("black_plan", "").lower():
            return "Look for pawn breaks to create counterplay"
        return phase_focus.get("middlegame", "Create a concrete plan — what is your opponent's weakness?")
    
    if phase == "endgame":
        return phase_focus.get("endgame", "Activate your king! In the endgame, the king is a fighting piece.")
    
    return "Think about what your opponent wants to do, then make your plan"


def analyze_mistake_rich(
    board_before: chess.Board,
    played_move: chess.Move,
    played_san: str,
    best_move_san: Optional[str],
    cp_loss: int,
    cognitive_gap: Optional[str],
    coaching_focus: Optional[str],
    opening_data: dict,
    intent: Optional[Dict] = None
) -> Dict[str, str]:
    """
    Rich analysis of why a move was a mistake.
    V3: Uses intent to make corrections more empathetic.
    """
    result = {
        "what_you_missed": "",
        "better_move_idea": "",
        "principle": ""
    }
    
    if cp_loss >= 300:
        severity = "blunder"
    elif cp_loss >= 150:
        severity = "mistake"
    elif cp_loss >= 50:
        severity = "inaccuracy"
    else:
        severity = "minor"
    
    # V3: If we recognized intent, build an empathetic correction
    if intent:
        likely_idea = intent.get("likely_idea", "")
        suggestion = intent.get("suggestion", "")
        if likely_idea:
            result["what_you_missed"] = f"Your idea ({likely_idea.lower().rstrip('.')}) makes sense defensively, but it costs a tempo in a position where development is critical."
        if suggestion:
            result["principle"] = suggestion
    
    # Use cognitive gap if available and we don't have intent-based explanation
    if not result["what_you_missed"] and cognitive_gap:
        gap_lower = cognitive_gap.lower()
        if "threat" in gap_lower or "ignored" in gap_lower:
            result["what_you_missed"] = "You missed what your opponent was threatening"
            result["principle"] = "Before every move, ask: What is my opponent threatening?"
        elif "hanging" in gap_lower:
            result["what_you_missed"] = "You left a piece unprotected"
            result["principle"] = "Before moving, check: Are all my pieces defended?"
        elif "calculation" in gap_lower or "depth" in gap_lower:
            result["what_you_missed"] = "You needed to calculate deeper — the position required more analysis"
            result["principle"] = "In complex positions, calculate at least 3 moves ahead"
        elif "tactical" in gap_lower:
            result["what_you_missed"] = "There was a tactical opportunity you didn't see"
            result["principle"] = "Look for checks, captures, and threats on every move"
        elif "positional" in gap_lower:
            result["what_you_missed"] = "The move weakened your position structurally"
            result["principle"] = "Consider the long-term consequences of your moves"
    
    if not result["what_you_missed"] and coaching_focus:
        result["what_you_missed"] = coaching_focus
    
    if not result["what_you_missed"]:
        board_after = board_before.copy()
        board_after.push(played_move)
        
        user_color = board_before.turn
        for sq in board_after.piece_map():
            piece = board_after.piece_at(sq)
            if piece and piece.color == user_color:
                attackers = board_after.attackers(not user_color, sq)
                defenders = board_after.attackers(user_color, sq)
                if len(attackers) > len(defenders):
                    piece_name = get_piece_name(piece)
                    result["what_you_missed"] = f"This move left your {piece_name} on {chess.square_name(sq)} undefended"
                    result["principle"] = "Always check if your pieces are protected after you move"
                    break
        
        if not result["what_you_missed"]:
            if severity == "blunder":
                result["what_you_missed"] = f"This was a serious mistake that lost about {cp_loss/100:.1f} pawns of value"
            else:
                result["what_you_missed"] = "There was a better move available"
    
    if not result["principle"]:
        common_mistakes = opening_data.get("common_mistakes", {})
        if common_mistakes:
            for mistake_key, mistake_desc in common_mistakes.items():
                if played_san.lower() in mistake_key.lower():
                    result["principle"] = mistake_desc
                    break
        
        if not result["principle"]:
            result["principle"] = "Take your time on critical decisions"
    
    # Explain the better move
    if best_move_san:
        typical_ideas = opening_data.get("typical_ideas", {})
        if best_move_san in typical_ideas:
            result["better_move_idea"] = typical_ideas[best_move_san]
        else:
            # Check main lines for richer explanation
            main_lines = opening_data.get("main_lines", {})
            found_in_theory = False
            for key, line_data in main_lines.items():
                if isinstance(line_data, dict):
                    lines = line_data.get("lines", {})
                    if best_move_san in lines:
                        result["better_move_idea"] = lines[best_move_san]
                        found_in_theory = True
                        break
            
            if not found_in_theory:
                try:
                    best_move = board_before.parse_san(best_move_san)
                    _, idea = describe_move_rich(board_before, best_move, best_move_san, opening_data, "middlegame", False)
                    result["better_move_idea"] = idea
                except Exception:
                    result["better_move_idea"] = f"{best_move_san} was the better choice"
    
    return result


def generate_move_coaching_v3(
    board_before: chess.Board,
    move: chess.Move,
    move_san: str,
    move_number: int,
    is_user_move: bool,
    user_color: str,
    opening_data: dict,
    opening_name: Optional[str],
    last_opponent_move: Optional[chess.Move] = None,
    last_opponent_san: Optional[str] = None,
    eval_data: Optional[Dict] = None,
    user_has_castled: bool = False
) -> MoveCoaching:
    """
    Generate rich, intent-aware coaching for a single move.
    V3: Recognizes user intent, acknowledges thinking, then coaches.
    """
    eval_data = eval_data or {}
    
    board_after = board_before.copy()
    board_after.push(move)
    fen_before = board_before.fen()
    fen_after = board_after.fen()
    
    phase = detect_phase(board_before, move_number)
    
    # V3: Recognize intent for user moves
    intent = recognize_move_intent(move_san, opening_data, board_before, is_user_move)
    intent_acknowledged = None
    
    if intent and is_user_move:
        likely_idea = intent.get("likely_idea", "")
        if likely_idea:
            intent_acknowledged = f"I see what you're doing — {likely_idea.lower().rstrip('.')}. That shows good awareness!"
    
    # Rich move description (now intent-aware)
    what_happened, move_idea = describe_move_rich(board_before, move, move_san, opening_data, phase, is_user_move, intent)
    
    # Opponent's idea (only for user moves)
    opponent_last_idea = None
    if is_user_move and last_opponent_move:
        opponent_last_idea = analyze_opponent_idea_rich(board_before, last_opponent_move, last_opponent_san, opening_data)
    
    # Dynamic focus
    your_focus = get_dynamic_focus(phase, board_before, is_user_move, opening_data, move_number, user_has_castled)
    
    # Mistake analysis
    cp_loss = abs(eval_data.get("cp_loss", 0))
    is_mistake = cp_loss >= 50 and is_user_move
    mistake_type = None
    what_you_missed = None
    better_move = None
    better_move_idea = None
    principle = None
    
    if is_mistake:
        best_move_san = eval_data.get("best_move")
        cognitive_gap = eval_data.get("cognitive_gap")
        coaching_focus = eval_data.get("coaching_focus")
        
        mistake_analysis = analyze_mistake_rich(
            board_before, move, move_san, best_move_san,
            cp_loss, cognitive_gap, coaching_focus, opening_data,
            intent=intent
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
    
    # Good move praise
    is_good_move = cp_loss <= 10 and is_user_move
    praise = None
    if is_good_move and is_user_move:
        if cp_loss == 0:
            typical_ideas = opening_data.get("typical_ideas", {})
            if move_san in typical_ideas:
                praise = f"Excellent! {typical_ideas[move_san]}"
            else:
                praise = "Perfect move! You found the best continuation."
        else:
            praise = "Good move — solid choice."
    
    # Check for sideline (V3: now returns main_line_theory too)
    is_sideline, sideline_warning, main_line_moves, main_line_theory = check_sideline(
        move_san, move_number, is_user_move, opening_data, phase
    )
    
    # If sideline detected, update the focus
    if is_sideline and sideline_warning:
        your_focus = sideline_warning
        if praise and not is_mistake:
            praise = None
    
    return MoveCoaching(
        move_number=move_number,
        is_user_move=is_user_move,
        move_san=move_san,
        fen_before=fen_before,
        fen_after=fen_after,
        phase=phase,
        opening_name=opening_name,
        what_happened=what_happened,
        move_idea=move_idea,
        opponent_last_idea=opponent_last_idea,
        your_focus=your_focus,
        intent_acknowledged=intent_acknowledged,
        is_mistake=is_mistake,
        cp_loss=cp_loss,
        mistake_type=mistake_type,
        what_you_missed=what_you_missed,
        better_move=better_move,
        better_move_idea=better_move_idea,
        principle=principle,
        is_good_move=is_good_move,
        praise=praise,
        is_sideline=is_sideline,
        sideline_warning=sideline_warning,
        main_line_moves=main_line_moves,
        main_line_theory=main_line_theory,
        eval_before=eval_data.get("eval_before"),
        eval_after=eval_data.get("eval_after"),
        best_move_san=eval_data.get("best_move")
    )


def generate_game_decryption(
    pgn: str,
    user_color: str,
    move_evaluations: List[Dict]
) -> List[Dict]:
    """
    Generate complete move-by-move coaching for an entire game.
    V3: Intent-aware, with opening introduction.
    """
    try:
        board = chess.Board()
        decryption_data = []
        
        opening_name, eco_code = detect_opening_from_pgn(pgn)
        opening_data = get_opening_data(eco_code, opening_name)
        
        logger.info(f"[DECRYPTION V3] Opening detected: {opening_name or 'Unknown'} ({eco_code or 'N/A'})")
        
        game = chess.pgn.read_game(io.StringIO(pgn))
        if not game:
            logger.error("Could not parse PGN")
            return []
        
        moves = list(game.mainline_moves())
        
        # Build evaluation lookup
        eval_lookup = {}
        for eval_data in move_evaluations:
            idx = eval_data.get("move_index", -1)
            if idx >= 0:
                eval_lookup[idx] = eval_data
        
        last_opponent_move = None
        last_opponent_san = None
        user_has_castled = False
        
        for idx, move in enumerate(moves):
            move_san = board.san(move)
            full_move_number = (idx // 2) + 1
            is_white_move = (idx % 2 == 0)
            is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
            
            if is_user_move and board.is_castling(move):
                user_has_castled = True
            
            eval_data = eval_lookup.get(idx, {})
            
            coaching = generate_move_coaching_v3(
                board_before=board,
                move=move,
                move_san=move_san,
                move_number=full_move_number,
                is_user_move=is_user_move,
                user_color=user_color,
                opening_data=opening_data,
                opening_name=opening_name,
                last_opponent_move=last_opponent_move if is_user_move else None,
                last_opponent_san=last_opponent_san if is_user_move else None,
                eval_data=eval_data,
                user_has_castled=user_has_castled
            )
            
            decryption_data.append(coaching.to_dict())
            
            if not is_user_move:
                last_opponent_move = move
                last_opponent_san = move_san
            
            board.push(move)
        
        logger.info(f"[DECRYPTION V3] Generated coaching for {len(decryption_data)} moves")
        return decryption_data
        
    except Exception as e:
        logger.error(f"Error generating game decryption: {e}")
        import traceback
        traceback.print_exc()
        return []


def generate_game_summary(decryption_data: List[Dict], user_color: str, opening_data: Optional[dict] = None) -> Dict:
    """Generate a summary of the game based on the decryption data. V3: Includes opening introduction."""
    if not decryption_data:
        return {"error": "No data available"}
    
    user_moves = [m for m in decryption_data if m.get("is_user_move")]
    mistakes = [m for m in user_moves if m.get("is_mistake")]
    good_moves = [m for m in user_moves if m.get("is_good_move")]
    
    phases = {"opening": 0, "middlegame": 0, "endgame": 0}
    for m in decryption_data:
        phase = m.get("phase", "middlegame")
        phases[phase] = phases.get(phase, 0) + 1
    
    key_moments = []
    for m in sorted(mistakes, key=lambda x: x.get("cp_loss", 0), reverse=True)[:5]:
        key_moments.append({
            "move_number": m.get("move_number"),
            "type": m.get("mistake_type", "mistake"),
            "move": m.get("move_san"),
            "summary": m.get("what_you_missed", "A mistake occurred here")
        })
    
    opening_name = decryption_data[0].get("opening_name") if decryption_data else None
    
    if not mistakes:
        overall = "Excellent game! You played with very few inaccuracies."
    elif len(mistakes) <= 2:
        worst = max(mistakes, key=lambda m: m.get("cp_loss", 0))
        overall = f"Solid play. Review move {worst.get('move_number')}: {worst.get('what_you_missed', 'This was the critical moment')}"
    else:
        worst = max(mistakes, key=lambda m: m.get("cp_loss", 0))
        overall = f"Focus on move {worst.get('move_number')}: {worst.get('what_you_missed', 'This was the turning point')}"
    
    # V3: Generate opening introduction
    opening_intro = None
    if opening_data:
        opening_intro = generate_opening_introduction(opening_data, opening_name, user_color)
    
    return {
        "total_moves": len(decryption_data),
        "user_moves": len(user_moves),
        "mistakes": len(mistakes),
        "good_moves": len(good_moves),
        "phases": phases,
        "key_moments": key_moments,
        "opening_name": opening_name,
        "overall_message": overall,
        "opening_introduction": opening_intro
    }

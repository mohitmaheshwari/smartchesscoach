"""
Chess Phase Detection and Theory Service

Provides:
1. Game phase detection (opening, middlegame, endgame)
2. Phase-specific coaching principles (RATING-ADAPTIVE)
3. Endgame pattern recognition
4. Strategic lessons for future games

Rating-Adaptive Language:
- 800-1200: Simple, action-oriented ("Move your king to the center")
- 1200-1600: Principle-based ("King activity is crucial because...")
- 1600-2000: Nuanced, theoretical ("Opposition and triangulation determine...")
"""

import chess
import chess.pgn
import io
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# RATING BRACKETS FOR ADAPTIVE COACHING
# =============================================================================

def get_rating_bracket(rating: int) -> str:
    """Get coaching bracket based on rating"""
    if rating < 1000:
        return "beginner"      # 800-999
    elif rating < 1400:
        return "intermediate"  # 1000-1399
    elif rating < 1800:
        return "advanced"      # 1400-1799
    else:
        return "expert"        # 1800+

# =============================================================================
# PHASE DETECTION
# =============================================================================

def count_material(board: chess.Board) -> Dict[str, int]:
    """Count material on the board"""
    material = {
        "white_queens": len(board.pieces(chess.QUEEN, chess.WHITE)),
        "black_queens": len(board.pieces(chess.QUEEN, chess.BLACK)),
        "white_rooks": len(board.pieces(chess.ROOK, chess.WHITE)),
        "black_rooks": len(board.pieces(chess.ROOK, chess.BLACK)),
        "white_bishops": len(board.pieces(chess.BISHOP, chess.WHITE)),
        "black_bishops": len(board.pieces(chess.BISHOP, chess.BLACK)),
        "white_knights": len(board.pieces(chess.KNIGHT, chess.WHITE)),
        "black_knights": len(board.pieces(chess.KNIGHT, chess.BLACK)),
        "white_pawns": len(board.pieces(chess.PAWN, chess.WHITE)),
        "black_pawns": len(board.pieces(chess.PAWN, chess.BLACK)),
    }
    
    material["white_pieces"] = (material["white_queens"] + material["white_rooks"] + 
                                 material["white_bishops"] + material["white_knights"])
    material["black_pieces"] = (material["black_queens"] + material["black_rooks"] + 
                                 material["black_bishops"] + material["black_knights"])
    material["total_pieces"] = material["white_pieces"] + material["black_pieces"]
    material["total_pawns"] = material["white_pawns"] + material["black_pawns"]
    
    return material


def detect_game_phase(board: chess.Board, move_number: int) -> str:
    """
    Detect the current game phase.
    
    Returns: "opening", "middlegame", or "endgame"
    """
    material = count_material(board)
    
    # Opening: First 10-15 moves, most pieces still on board
    if move_number <= 10 and material["total_pieces"] >= 12:
        return "opening"
    
    # Endgame conditions:
    # - No queens, or
    # - Queen + at most one minor piece each, or
    # - Very few pieces (<=4 total excluding kings)
    no_queens = material["white_queens"] == 0 and material["black_queens"] == 0
    queens_only = (material["white_queens"] <= 1 and material["black_queens"] <= 1 and 
                   material["total_pieces"] <= 4)
    few_pieces = material["total_pieces"] <= 4
    
    if no_queens or queens_only or few_pieces:
        return "endgame"
    
    return "middlegame"


def detect_endgame_type(board: chess.Board) -> Dict[str, any]:
    """
    Detect the specific type of endgame for targeted advice.
    """
    material = count_material(board)
    
    endgame_info = {
        "type": "complex",
        "subtype": None,
        "is_pawn_ending": False,
        "is_rook_ending": False,
        "is_minor_piece_ending": False,
        "pawn_structure": None,
        "material_balance": None
    }
    
    # Pure pawn ending (K+P vs K+P)
    if material["total_pieces"] == 0:
        endgame_info["type"] = "pawn_ending"
        endgame_info["is_pawn_ending"] = True
        
        wp = material["white_pawns"]
        bp = material["black_pawns"]
        
        if wp == 0 and bp == 0:
            endgame_info["subtype"] = "king_vs_king"
        elif wp == 1 and bp == 0:
            endgame_info["subtype"] = "king_pawn_vs_king"
        elif wp == 0 and bp == 1:
            endgame_info["subtype"] = "king_vs_king_pawn"
        elif wp > bp:
            endgame_info["subtype"] = f"pawn_majority_{wp}_vs_{bp}"
        elif bp > wp:
            endgame_info["subtype"] = f"pawn_minority_{wp}_vs_{bp}"
        else:
            endgame_info["subtype"] = f"equal_pawns_{wp}_vs_{bp}"
        
        endgame_info["pawn_structure"] = f"{wp} vs {bp} pawns"
    
    # Rook ending
    elif (material["white_rooks"] >= 1 or material["black_rooks"] >= 1) and \
         material["white_queens"] == 0 and material["black_queens"] == 0 and \
         material["white_bishops"] + material["white_knights"] <= 1 and \
         material["black_bishops"] + material["black_knights"] <= 1:
        endgame_info["type"] = "rook_ending"
        endgame_info["is_rook_ending"] = True
        endgame_info["subtype"] = f"R+{material['white_pawns']}P_vs_R+{material['black_pawns']}P"
    
    # Minor piece ending (bishop or knight)
    elif material["white_queens"] == 0 and material["black_queens"] == 0 and \
         material["white_rooks"] == 0 and material["black_rooks"] == 0:
        endgame_info["type"] = "minor_piece_ending"
        endgame_info["is_minor_piece_ending"] = True
        
        if material["white_bishops"] + material["black_bishops"] > 0 and \
           material["white_knights"] + material["black_knights"] == 0:
            endgame_info["subtype"] = "bishop_ending"
        elif material["white_knights"] + material["black_knights"] > 0 and \
             material["white_bishops"] + material["black_bishops"] == 0:
            endgame_info["subtype"] = "knight_ending"
        else:
            endgame_info["subtype"] = "mixed_minor_pieces"
    
    # Material balance
    white_material = (material["white_queens"] * 9 + material["white_rooks"] * 5 + 
                      material["white_bishops"] * 3 + material["white_knights"] * 3 +
                      material["white_pawns"])
    black_material = (material["black_queens"] * 9 + material["black_rooks"] * 5 + 
                      material["black_bishops"] * 3 + material["black_knights"] * 3 +
                      material["black_pawns"])
    
    diff = white_material - black_material
    if diff > 2:
        endgame_info["material_balance"] = "white_winning"
    elif diff < -2:
        endgame_info["material_balance"] = "black_winning"
    else:
        endgame_info["material_balance"] = "roughly_equal"
    
    return endgame_info


# =============================================================================
# PHASE-SPECIFIC THEORY AND PRINCIPLES
# =============================================================================

OPENING_PRINCIPLES = {
    "core": [
        "Control the center with pawns (e4, d4, e5, d5)",
        "Develop knights before bishops",
        "Castle early to protect your king",
        "Don't move the same piece twice in the opening",
        "Connect your rooks by developing all minor pieces"
    ],
    "mistakes_to_avoid": [
        "Don't bring your queen out too early",
        "Don't make too many pawn moves",
        "Don't neglect development to grab pawns",
        "Don't block your center pawns with knights"
    ]
}

MIDDLEGAME_PRINCIPLES = {
    "core": [
        "Create a plan based on pawn structure",
        "Improve your worst-placed piece",
        "Control open files with rooks",
        "Attack where you have more space or pieces",
        "Trade pieces when ahead in material, avoid trades when behind"
    ],
    "attack": [
        "Attack the king when you have more pieces on that side",
        "Open lines toward the enemy king",
        "Don't attack without sufficient pieces"
    ],
    "defense": [
        "Exchange attacking pieces when defending",
        "Keep pieces coordinated for defense",
        "Don't create weaknesses near your king"
    ]
}

ENDGAME_PRINCIPLES = {
    "core": [
        "King activity is CRUCIAL - bring your king to the center",
        "Passed pawns must be pushed - they're your winning ticket",
        "Rooks belong BEHIND passed pawns (yours or opponent's)",
        "The side with more pawns should create a passed pawn",
        "Avoid creating pawn weaknesses that will be targets"
    ],
    "pawn_endings": [
        "OPPOSITION: When kings face each other with 1 square between, whoever moves is at disadvantage",
        "King in FRONT of pawn wins, king BEHIND pawn often draws",
        "Outside passed pawn wins by distracting the enemy king",
        "In equal pawn endings, create a passed pawn on the side where you have majority",
        "Triangulation can help gain the opposition"
    ],
    "rook_endings": [
        "LUCENA POSITION: Rook + pawn on 7th with king in front usually wins",
        "PHILIDOR POSITION: Defender's rook on 6th rank can hold the draw",
        "Active rook > passive rook (even with a pawn deficit)",
        "Cut off the enemy king with your rook",
        "Rooks belong on the 7th rank (attacking pawns from behind)"
    ],
    "minor_piece_endings": [
        "Bishop pair is strong in open positions",
        "Knight is better in closed positions with pawns on both sides",
        "Wrong-colored bishop + rook pawn is often a draw",
        "Knights need outposts to be effective"
    ]
}


def get_phase_theory(phase: str, endgame_info: Dict = None) -> Dict[str, any]:
    """
    Get relevant theory and principles for the game phase.
    """
    theory = {
        "phase": phase,
        "key_principles": [],
        "specific_advice": [],
        "common_mistakes": [],
        "patterns_to_know": []
    }
    
    if phase == "opening":
        theory["key_principles"] = OPENING_PRINCIPLES["core"]
        theory["common_mistakes"] = OPENING_PRINCIPLES["mistakes_to_avoid"]
        theory["specific_advice"] = [
            "Focus on getting all your pieces out before attacking",
            "Castle within the first 10 moves if possible"
        ]
        
    elif phase == "middlegame":
        theory["key_principles"] = MIDDLEGAME_PRINCIPLES["core"]
        theory["specific_advice"] = MIDDLEGAME_PRINCIPLES["attack"][:2] + MIDDLEGAME_PRINCIPLES["defense"][:2]
        theory["common_mistakes"] = [
            "Attacking without enough pieces",
            "Ignoring opponent's threats",
            "Trading when behind in material"
        ]
        
    elif phase == "endgame":
        theory["key_principles"] = ENDGAME_PRINCIPLES["core"]
        
        if endgame_info:
            if endgame_info.get("is_pawn_ending"):
                theory["specific_advice"] = ENDGAME_PRINCIPLES["pawn_endings"]
                theory["patterns_to_know"] = [
                    "Opposition (direct, distant, diagonal)",
                    "Key squares (for pawn promotion)",
                    "Rule of the square (can king catch the pawn?)",
                    "Triangulation (gaining a tempo)"
                ]
            elif endgame_info.get("is_rook_ending"):
                theory["specific_advice"] = ENDGAME_PRINCIPLES["rook_endings"]
                theory["patterns_to_know"] = [
                    "Lucena Position (winning technique)",
                    "Philidor Position (drawing technique)",
                    "Building a bridge",
                    "Cutting off the king"
                ]
            elif endgame_info.get("is_minor_piece_ending"):
                theory["specific_advice"] = ENDGAME_PRINCIPLES["minor_piece_endings"]
        
        theory["common_mistakes"] = [
            "Keeping king passive when it should be active",
            "Not pushing passed pawns",
            "Putting rook in front of your own passed pawn"
        ]
    
    return theory


def generate_strategic_lesson(phase: str, endgame_info: Dict, user_mistakes: List[Dict], 
                             user_color: str, result: str) -> Dict[str, any]:
    """
    Generate a strategic lesson based on the game analysis.
    """
    lesson = {
        "phase_reached": phase,
        "lesson_title": "",
        "what_to_remember": [],
        "theory_to_study": [],
        "practice_exercises": [],
        "one_sentence_takeaway": ""
    }
    
    if phase == "endgame":
        lesson["lesson_title"] = "Endgame Lesson"
        
        if endgame_info.get("is_pawn_ending"):
            pawn_struct = endgame_info.get("pawn_structure", "")
            lesson["what_to_remember"] = [
                f"This was a {pawn_struct} pawn ending",
                "In pawn endings, your KING is a fighting piece - use it!",
                "The concept of OPPOSITION decides most pawn endings",
                "Always calculate if pawns can promote before committing"
            ]
            lesson["theory_to_study"] = [
                "King and Pawn vs King endings",
                "Opposition (direct and distant)",
                "Rule of the Square",
                "Outside passed pawn technique"
            ]
            lesson["practice_exercises"] = [
                "Practice basic K+P vs K positions",
                "Study Philidor and Lucena positions",
                "Solve pawn ending puzzles focusing on opposition"
            ]
            lesson["one_sentence_takeaway"] = "In pawn endings, king activity and opposition are everything - master these and you'll win won endings."
            
        elif endgame_info.get("is_rook_ending"):
            lesson["what_to_remember"] = [
                "Rook endings are the most common endgame type",
                "Keep your rook ACTIVE - a passive rook loses",
                "Rooks belong BEHIND passed pawns (yours or opponent's)",
                "The 7th rank is rook paradise - control it"
            ]
            lesson["theory_to_study"] = [
                "Lucena Position (how to win)",
                "Philidor Position (how to draw)",
                "Rook activity vs material",
                "King cut-off technique"
            ]
            lesson["one_sentence_takeaway"] = "In rook endings, activity beats material - keep your rook active and cut off the enemy king."
            
        else:
            lesson["what_to_remember"] = ENDGAME_PRINCIPLES["core"]
            lesson["one_sentence_takeaway"] = "Endgames are won by active kings and passed pawns - bring your king to the fight!"
    
    elif phase == "middlegame":
        lesson["lesson_title"] = "Middlegame Lesson"
        lesson["what_to_remember"] = [
            "Always have a PLAN - don't just make moves",
            "Improve your worst piece before attacking",
            "Look for opponent's weaknesses to target",
            "Coordinate your pieces before striking"
        ]
        lesson["theory_to_study"] = [
            "Pawn structure and planning",
            "Piece coordination",
            "Attacking the king"
        ]
        lesson["one_sentence_takeaway"] = "In the middlegame, have a plan and improve your worst piece - aimless moves lose games."
    
    else:  # opening
        lesson["lesson_title"] = "Opening Lesson"
        lesson["what_to_remember"] = OPENING_PRINCIPLES["core"][:4]
        lesson["theory_to_study"] = [
            "Basic opening principles",
            "Your main opening repertoire"
        ]
        lesson["one_sentence_takeaway"] = "In the opening, develop all pieces, control the center, and castle - don't hunt for material."
    
    return lesson


def analyze_game_phases(pgn_string: str, user_color: str = "white") -> Dict[str, any]:
    """
    Analyze the entire game and provide phase-by-phase breakdown with theory.
    """
    try:
        pgn_io = io.StringIO(pgn_string)
        game = chess.pgn.read_game(pgn_io)
        
        if not game:
            return {"error": "Could not parse PGN"}
        
        board = game.board()
        phases = []
        current_phase = "opening"
        phase_start_move = 1
        
        move_number = 1
        for i, move in enumerate(game.mainline_moves()):
            board.push(move)
            is_white_move = (i % 2 == 0)
            if not is_white_move:
                move_number += 1
            
            new_phase = detect_game_phase(board, move_number)
            
            if new_phase != current_phase:
                phases.append({
                    "phase": current_phase,
                    "start_move": phase_start_move,
                    "end_move": move_number - 1
                })
                current_phase = new_phase
                phase_start_move = move_number
        
        # Add final phase
        phases.append({
            "phase": current_phase,
            "start_move": phase_start_move,
            "end_move": move_number
        })
        
        # Detect final endgame type if applicable
        endgame_info = None
        if current_phase == "endgame":
            endgame_info = detect_endgame_type(board)
        
        # Get theory for the final phase
        final_theory = get_phase_theory(current_phase, endgame_info)
        
        # Generate strategic lesson
        result = game.headers.get("Result", "*")
        lesson = generate_strategic_lesson(current_phase, endgame_info or {}, [], user_color, result)
        
        return {
            "phases": phases,
            "final_phase": current_phase,
            "endgame_info": endgame_info,
            "theory": final_theory,
            "strategic_lesson": lesson,
            "total_moves": move_number
        }
        
    except Exception as e:
        logger.error(f"Error analyzing game phases: {e}")
        return {"error": str(e)}

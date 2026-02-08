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
# RATING-ADAPTIVE PHASE THEORY AND PRINCIPLES
# =============================================================================
# Each principle has versions for different rating levels

OPENING_PRINCIPLES_BY_RATING = {
    "beginner": {
        "core": [
            "Put a pawn in the center (e4 or d4)",
            "Get your knights out first",
            "Castle early to keep your king safe",
            "Move each piece once before moving any piece twice",
            "Get all your pieces out before attacking"
        ],
        "mistakes_to_avoid": [
            "Don't bring your queen out early - she can be chased",
            "Don't move too many pawns - develop pieces instead",
            "Don't grab pawns if it means falling behind in development"
        ],
        "key_concept": "DEVELOPMENT: Get all your pieces active before thinking about attacks.",
        "one_thing_to_remember": "Castle before move 10. Every game."
    },
    "intermediate": {
        "core": [
            "Control the center with pawns AND pieces (e4/d4, Nf3/Nc3)",
            "Develop knights before bishops - knights have fewer good squares",
            "Castle kingside for safety, queenside for attacking",
            "Don't move the same piece twice unless forced or winning material",
            "Connect your rooks by completing development"
        ],
        "mistakes_to_avoid": [
            "Early queen moves invite tempo-losing attacks",
            "Too many pawn moves weaken your position",
            "Grabbing pawns often costs crucial development time",
            "Blocking center pawns with knights limits your options"
        ],
        "key_concept": "PIECE COORDINATION: Your pieces should work together toward the center.",
        "one_thing_to_remember": "Ask 'Are all my pieces developed?' before starting an attack."
    },
    "advanced": {
        "core": [
            "Central control is about squares, not just occupying the center",
            "Knight development depends on pawn structure - sometimes Nc3 before Nf3",
            "Castling direction should match your pawn structure and attack plans",
            "Tempo is more valuable than material in the opening - avoid useless moves",
            "Rook connection means your opening is complete - don't start middlegame plans before this"
        ],
        "mistakes_to_avoid": [
            "Early queen moves can work IF they create concrete threats",
            "Some pawn moves (like h3/a3 prep) are fine when they prevent threats",
            "Material grabs are good IF you've calculated the consequences",
            "Blocking pawns is wrong only if you NEED that pawn to advance"
        ],
        "key_concept": "FLEXIBILITY: Keep your options open. Don't commit to a plan too early.",
        "one_thing_to_remember": "Every move should either develop, control center, or prepare castling."
    },
    "expert": {
        "core": [
            "Central control is dynamic - sometimes ceding the center to attack later is correct",
            "Piece placement depends on anticipated pawn breaks and resulting structures",
            "Castling is a commitment - delay if unclear, or use king position as a weapon",
            "Opening theory is a tool, not a rulebook - understand the IDEAS behind the moves",
            "Early imbalances (bishop pair, pawn structure) should guide middlegame plans"
        ],
        "mistakes_to_avoid": [
            "Blindly following opening principles without understanding the position",
            "Memorizing moves without understanding plans and typical structures",
            "Neglecting opponent's resources and counterplay",
            "Over-preparing for one variation while ignoring practical positions"
        ],
        "key_concept": "UNDERSTANDING: Know WHY moves are played, not just WHAT moves to play.",
        "one_thing_to_remember": "The best opening is one where you understand the resulting middlegame."
    }
}

MIDDLEGAME_PRINCIPLES_BY_RATING = {
    "beginner": {
        "core": [
            "Look for threats before making your move",
            "If you don't know what to do, improve your worst piece",
            "Put your rooks on open files (no pawns in the way)",
            "Don't trade pieces if you're losing - keep them for chances",
            "When you have more pieces attacking, that's when to attack"
        ],
        "attack_tips": [
            "Attack only when your pieces are ready",
            "More pieces = stronger attack",
            "Open files point to the enemy king = good attack"
        ],
        "defense_tips": [
            "Trade off the attacking pieces when defending",
            "Keep your pieces near your king when under attack",
            "Don't make weaknesses around your king"
        ],
        "key_concept": "PIECE ACTIVITY: An active piece is worth more than a passive piece.",
        "one_thing_to_remember": "Before every move, ask: 'What is my opponent threatening?'"
    },
    "intermediate": {
        "core": [
            "Your PLAN should be based on the pawn structure - where are the pawn breaks?",
            "Identify and improve your worst-placed piece",
            "Rooks belong on open files, semi-open files, or the 7th rank",
            "Trade pieces when ahead, avoid trades when behind",
            "Attack where you have more space or a pawn majority"
        ],
        "attack_tips": [
            "Attack where you have more pieces concentrated",
            "Open lines toward the enemy king with pawn breaks",
            "Three pieces attacking > two pieces defending"
        ],
        "defense_tips": [
            "Exchange the opponent's most dangerous attacking piece",
            "Piece coordination beats material in defense",
            "Prophylaxis: prevent opponent's threats before they happen"
        ],
        "key_concept": "PLANNING: Every move should be part of a larger plan based on position features.",
        "one_thing_to_remember": "Find your worst piece. Make it better. Repeat."
    },
    "advanced": {
        "core": [
            "Pawn structure determines piece placement and attack direction",
            "Piece harmony matters more than individual piece strength",
            "Rook placement depends on where files WILL open, not where they ARE open",
            "Material exchange decisions should consider activity differential",
            "Create weaknesses in opponent's camp before launching attack"
        ],
        "attack_tips": [
            "Attack preparation: improve all pieces to maximum before striking",
            "Pawn breaks to open lines should be timed with piece coordination",
            "Prophylaxis in attack: eliminate counterplay before final assault"
        ],
        "defense_tips": [
            "Active defense: counterattack where opponent is weak",
            "Piece exchanges should eliminate opponent's most active pieces",
            "Accept material deficit temporarily if it ruins opponent's coordination"
        ],
        "key_concept": "WEAKNESSES: Create them in opponent's position, avoid them in yours.",
        "one_thing_to_remember": "Control the position before attacking - rushed attacks backfire."
    },
    "expert": {
        "core": [
            "Pawn structure is dynamic - pawn breaks change the game's character",
            "Piece placement follows strategic goals: restricting opponent or enabling plans",
            "File control is preparation for invasion or prevention of enemy activity",
            "Material imbalances should be evaluated based on position demands",
            "Prophylaxis and provocation: make opponent's pieces work poorly"
        ],
        "attack_tips": [
            "Attack timing depends on concrete calculation, not just positional indicators",
            "Creating multiple threats forces opponent into difficult choices",
            "Piece sacrifices can be correct even without forced win - evaluate compensation"
        ],
        "defense_tips": [
            "Defensive resources: fortress structures, perpetual threats, counterplay",
            "Exchanging down to holdable endgames is a valid defensive strategy",
            "Active defense often stronger than passive - create problems for attacker"
        ],
        "key_concept": "DYNAMICS: Static advantages must be converted before opponent creates counterplay.",
        "one_thing_to_remember": "When you have an advantage, ask: 'How can opponent fight back?' Then stop it."
    }
}

ENDGAME_PRINCIPLES_BY_RATING = {
    "beginner": {
        "core": [
            "BRING YOUR KING TO THE CENTER - it's safe now and can help",
            "Push your passed pawns - they want to become queens!",
            "Put rooks BEHIND passed pawns (yours or opponent's)",
            "Count pawns - more pawns usually means you can make a queen",
            "Don't rush - think carefully in endgames"
        ],
        "pawn_endings": [
            "Your KING must help the pawn - it can't promote alone",
            "King in FRONT of the pawn is strong",
            "If kings face each other, the one who moves loses ground"
        ],
        "rook_endings": [
            "Keep your rook ACTIVE - a passive rook loses",
            "Put your rook behind the passed pawn",
            "Cut off the enemy king with your rook"
        ],
        "key_concept": "KING ACTIVITY: In the endgame, your king is a FIGHTING piece, not a hiding piece.",
        "one_thing_to_remember": "Endgame rule #1: Activate your king immediately."
    },
    "intermediate": {
        "core": [
            "King activity is CRUCIAL - centralize immediately when the endgame begins",
            "Passed pawns must be pushed - but TIME it right",
            "Rooks belong BEHIND passed pawns - this applies to BOTH sides' pawns",
            "Create passed pawns where you have a pawn majority",
            "Avoid creating pawn weaknesses - they become targets"
        ],
        "pawn_endings": [
            "OPPOSITION: Kings face each other, one square between. The side to move LOSES ground",
            "King in FRONT of pawn = winning. King BEHIND pawn = often drawing",
            "Outside passed pawn wins by distracting enemy king",
            "Create passed pawns on the side where you have more pawns",
            "Know when to push vs when to keep the tension"
        ],
        "rook_endings": [
            "LUCENA: Rook + pawn on 7th with king in front = winning technique",
            "PHILIDOR: Defender's rook on 6th rank = drawing technique",
            "Active rook beats passive rook, even down a pawn",
            "Cut off the king - prevent it from reaching key squares",
            "7th rank for rooks = attacking pawns from behind"
        ],
        "key_concept": "TECHNIQUE: Knowing basic endgame patterns wins games that calculation cannot.",
        "one_thing_to_remember": "Learn Lucena and Philidor positions - they appear constantly."
    },
    "advanced": {
        "core": [
            "King centralization speed often determines endgame outcome",
            "Passed pawn creation vs advancement - strategic timing matters",
            "Rook placement: behind passed pawns, or cutting off the king, depending on position",
            "Pawn structure determines whether you should trade into an ending",
            "Weak pawns become critical targets - avoid creating them mid-game"
        ],
        "pawn_endings": [
            "Opposition types: direct, distant, and diagonal - all serve different purposes",
            "Triangulation: losing a tempo to gain the opposition",
            "Key squares: controlling them guarantees promotion",
            "Outside passed pawn technique: deflect the king, then win the race",
            "Zugzwang: when any move worsens your position - set these up"
        ],
        "rook_endings": [
            "Lucena building a bridge technique: Rf4, Ra4, Re4+ patterns",
            "Philidor's 3rd rank defense: keeping options flexible",
            "Rook activity compensates for material - calculate carefully",
            "King cut-off technique: every file of separation = half a pawn",
            "Vancura position: drawing rook+pawn vs rook with a-pawn"
        ],
        "key_concept": "PRECISION: Small improvements accumulate. Accurate play converts advantages.",
        "one_thing_to_remember": "In complex endgames, calculate the king race first."
    },
    "expert": {
        "core": [
            "Endgame transitions should be planned from the middlegame",
            "Dynamic factors (activity, initiative) vs static factors (material, structure) - balance shifts",
            "Rook endgames are 'always drawn' is a MYTH - precision wins",
            "Pawn structure weaknesses from opening/middlegame become decisive",
            "Fortress construction vs breakthrough technique - know both sides"
        ],
        "pawn_endings": [
            "Corresponding squares: the generalization of opposition",
            "Trebuchet positions and mutual zugzwang recognition",
            "Shouldering technique for king maneuvers",
            "Pawn breakthrough calculations in complex structures",
            "Reserve tempi: maintaining pawn tension as a resource"
        ],
        "rook_endings": [
            "Tarrasch rule nuances: when NOT to put rooks behind passed pawns",
            "Long-side defense vs short-side defense selection",
            "Two weaknesses principle in rook endings",
            "Rook vs pawn races: precise calculation required",
            "Complex theoretical positions: know the assessments"
        ],
        "key_concept": "TRANSFORMATION: Convert one advantage into another when opponent defends correctly.",
        "one_thing_to_remember": "The endgame is where you cash in your middlegame advantages - or lose them."
    }
}

# Legacy compatibility - keep old structure for any code that uses it
OPENING_PRINCIPLES = OPENING_PRINCIPLES_BY_RATING["intermediate"]
MIDDLEGAME_PRINCIPLES = MIDDLEGAME_PRINCIPLES_BY_RATING["intermediate"]
ENDGAME_PRINCIPLES = ENDGAME_PRINCIPLES_BY_RATING["intermediate"]


def get_phase_theory(phase: str, endgame_info: Dict = None, rating: int = 1200) -> Dict[str, any]:
    """
    Get relevant theory and principles for the game phase.
    RATING-ADAPTIVE: Language and depth adjust based on player rating.
    """
    bracket = get_rating_bracket(rating)
    
    theory = {
        "phase": phase,
        "rating_bracket": bracket,
        "key_principles": [],
        "specific_advice": [],
        "common_mistakes": [],
        "patterns_to_know": [],
        "key_concept": "",
        "one_thing_to_remember": ""
    }
    
    if phase == "opening":
        principles = OPENING_PRINCIPLES_BY_RATING.get(bracket, OPENING_PRINCIPLES_BY_RATING["intermediate"])
        theory["key_principles"] = principles["core"]
        theory["common_mistakes"] = principles["mistakes_to_avoid"]
        theory["key_concept"] = principles.get("key_concept", "")
        theory["one_thing_to_remember"] = principles.get("one_thing_to_remember", "")
        theory["specific_advice"] = [
            "Focus on getting all your pieces out before attacking",
            "Castle within the first 10 moves if possible"
        ]
        
    elif phase == "middlegame":
        principles = MIDDLEGAME_PRINCIPLES_BY_RATING.get(bracket, MIDDLEGAME_PRINCIPLES_BY_RATING["intermediate"])
        theory["key_principles"] = principles["core"]
        theory["common_mistakes"] = [
            "Attacking without enough pieces",
            "Ignoring opponent's threats",
            "Trading when behind in material"
        ]
        theory["specific_advice"] = principles.get("attack_tips", [])[:2] + principles.get("defense_tips", [])[:2]
        theory["key_concept"] = principles.get("key_concept", "")
        theory["one_thing_to_remember"] = principles.get("one_thing_to_remember", "")
        
    elif phase == "endgame":
        principles = ENDGAME_PRINCIPLES_BY_RATING.get(bracket, ENDGAME_PRINCIPLES_BY_RATING["intermediate"])
        theory["key_principles"] = principles["core"]
        theory["key_concept"] = principles.get("key_concept", "")
        theory["one_thing_to_remember"] = principles.get("one_thing_to_remember", "")
        
        if endgame_info:
            if endgame_info.get("is_pawn_ending"):
                theory["specific_advice"] = principles.get("pawn_endings", [])
                theory["patterns_to_know"] = [
                    "Opposition (direct, distant, diagonal)",
                    "Key squares (for pawn promotion)",
                    "Rule of the square (can king catch the pawn?)",
                    "Triangulation (gaining a tempo)"
                ]
            elif endgame_info.get("is_rook_ending"):
                theory["specific_advice"] = principles.get("rook_endings", [])
                theory["patterns_to_know"] = [
                    "Lucena Position (winning technique)",
                    "Philidor Position (drawing technique)",
                    "Building a bridge",
                    "Cutting off the king"
                ]
            elif endgame_info.get("is_minor_piece_ending"):
                theory["specific_advice"] = [
                    "Bishop pair is strong in open positions",
                    "Knight is better in closed positions with pawns on both sides",
                    "Wrong-colored bishop + rook pawn is often a draw",
                    "Knights need outposts to be effective"
                ]
            else:
                theory["specific_advice"] = principles.get("core", [])[:3]
        
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

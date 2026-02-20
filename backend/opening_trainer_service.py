"""
Opening Trainer Service - Master Your Favorite Openings

This service provides:
1. Detection of user's most-played openings
2. Key variations and move orders
3. Common traps (to set and avoid)
4. Typical plans and ideas for each opening
5. Practice positions from opening lines

The goal: Help users master the openings they actually play.
"""

import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timezone
import chess

logger = logging.getLogger(__name__)


# ============================================================================
# ECO TO OPENING NAME MAPPING
# ============================================================================

ECO_OPENINGS = {}
try:
    with open("data/eco_openings.json", "r") as f:
        ECO_OPENINGS = json.load(f)
    # Remove metadata keys
    ECO_OPENINGS = {k: v for k, v in ECO_OPENINGS.items() if not k.startswith("_")}
    logger.info(f"Loaded {len(ECO_OPENINGS)} ECO opening mappings")
except Exception as e:
    logger.warning(f"Could not load ECO openings: {e}")


def get_opening_name_from_eco(eco_or_name: str) -> str:
    """
    Convert ECO code to proper opening name.
    If already a name or not found, return as-is.
    """
    if not eco_or_name:
        return "Unknown Opening"
    
    eco_code = eco_or_name.strip().upper()
    
    # Direct lookup in ECO dictionary
    if eco_code in ECO_OPENINGS:
        return ECO_OPENINGS[eco_code]
    
    # Check if it looks like an ECO code but wasn't found
    if len(eco_code) >= 2 and eco_code[0].isalpha() and eco_code[1:].isdigit():
        return eco_or_name  # Return original if ECO code not in dictionary
    
    # It's probably already a name
    return eco_or_name


# ============================================================================
# OPENING DATABASE
# Each opening includes: main line, key variations, traps, and ideas
# ============================================================================

OPENINGS_DATABASE = {
    # ==================== KING'S PAWN OPENINGS (1.e4) ====================
    "italian_game": {
        "name": "Italian Game",
        "eco": "C50-C59",
        "color": "white",
        "main_line": ["e4", "e5", "Nf3", "Nc6", "Bc4"],
        "description": "A classical opening aiming to control the center and develop quickly. The bishop targets the weak f7 square.",
        "key_ideas": [
            "Control the center with d3 or d4",
            "Castle kingside quickly",
            "The bishop on c4 eyes the f7 pawn",
            "Look for Ng5 attacks on f7 in some lines"
        ],
        "common_variations": [
            {
                "name": "Giuoco Piano",
                "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"],
                "idea": "Slow, strategic play with both sides developing harmoniously"
            },
            {
                "name": "Two Knights Defense", 
                "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"],
                "idea": "Black counterattacks immediately. White can try the Fried Liver Attack!"
            },
            {
                "name": "Evans Gambit",
                "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "b4"],
                "idea": "Sacrifice a pawn for rapid development and attack"
            }
        ],
        "traps": [
            {
                "name": "Fried Liver Attack",
                "for_color": "white",
                "position": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                "winning_line": ["Ng5", "d5", "exd5", "Nxd5", "Nxf7"],
                "explanation": "White sacrifices a knight to expose Black's king. After Kxf7, White plays Qf3+ with a devastating attack."
            },
            {
                "name": "Legal's Mate Pattern",
                "for_color": "white", 
                "position": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3",
                "winning_line": ["Nxe5", "Nxe5", "Qh5"],
                "explanation": "If Black takes the knight, the queen delivers mate threats on f7"
            }
        ],
        "typical_mistakes": [
            "Moving the queen too early",
            "Not castling quickly enough",
            "Missing the Ng5 tactics"
        ]
    },
    
    "sicilian_defense": {
        "name": "Sicilian Defense",
        "eco": "B20-B99",
        "color": "black",
        "main_line": ["e4", "c5"],
        "description": "The most popular response to 1.e4. Black fights for the center asymmetrically and aims for counterplay.",
        "key_ideas": [
            "Control d4 without playing ...d5 early",
            "Counterattack on the queenside (a and b files)",
            "The c-file becomes open after ...cxd4",
            "Black often castles queenside for opposite-side attacks"
        ],
        "common_variations": [
            {
                "name": "Open Sicilian (Najdorf)",
                "moves": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"],
                "idea": "The most theoretically complex line. Black prepares ...e5 or ...b5 expansion."
            },
            {
                "name": "Dragon Variation",
                "moves": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "g6"],
                "idea": "Black fianchettoes the bishop. Very sharp with opposite-side castling."
            },
            {
                "name": "Alapin (2.c3)",
                "moves": ["e4", "c5", "c3"],
                "idea": "White prepares d4 without allowing ...cxd4. Leads to quieter positions."
            }
        ],
        "traps": [
            {
                "name": "Siberian Trap",
                "for_color": "black",
                "position": "rnbqkb1r/pp2pppp/3p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6",
                "winning_line": ["Bc4", "e6", "O-O", "Be7", "Bb3", "O-O", "f4", "Nc6", "Be3", "Nxd4", "Bxd4", "e5"],
                "explanation": "Black wins a piece with ...e5, forking the bishop and preparing ...Qb6+"
            }
        ],
        "typical_mistakes": [
            "Playing ...d5 too early without preparation",
            "Neglecting king safety in sharp lines",
            "Not understanding the pawn structure after ...cxd4"
        ]
    },
    
    "caro_kann": {
        "name": "Caro-Kann Defense",
        "eco": "B10-B19",
        "color": "black",
        "main_line": ["e4", "c6"],
        "description": "A solid defense where Black prepares ...d5 to challenge the center. Less tactical than the Sicilian.",
        "key_ideas": [
            "Solid pawn structure with ...d5",
            "The light-squared bishop develops outside the pawn chain",
            "Often leads to endgames where Black's structure is superior",
            "Less sharp than Sicilian, good for strategic players"
        ],
        "common_variations": [
            {
                "name": "Classical (4...Bf5)",
                "moves": ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5"],
                "idea": "Black develops the bishop before playing ...e6. Solid and reliable."
            },
            {
                "name": "Advance Variation",
                "moves": ["e4", "c6", "d4", "d5", "e5"],
                "idea": "White gains space. Black should undermine with ...c5 and ...Nc6."
            }
        ],
        "traps": [],
        "typical_mistakes": [
            "Being too passive - Black should seek counterplay",
            "Not challenging the e5 pawn in the Advance",
            "Trading pieces when you have the better structure"
        ]
    },
    
    "french_defense": {
        "name": "French Defense",
        "eco": "C00-C19",
        "color": "black",
        "main_line": ["e4", "e6"],
        "description": "Black builds a solid pawn chain and attacks White's center with ...d5. The light-squared bishop is often 'bad'.",
        "key_ideas": [
            "Challenge the center with ...d5",
            "Attack the white pawn chain with ...c5",
            "The f7-f6 break can be useful",
            "Be patient - the French is strategic"
        ],
        "common_variations": [
            {
                "name": "Advance Variation",
                "moves": ["e4", "e6", "d4", "d5", "e5"],
                "idea": "White gains space. Black attacks with ...c5 and ...Nc6."
            },
            {
                "name": "Winawer Variation",
                "moves": ["e4", "e6", "d4", "d5", "Nc3", "Bb4"],
                "idea": "Black pins the knight. Very sharp and double-edged."
            }
        ],
        "traps": [],
        "typical_mistakes": [
            "Not playing ...c5 to challenge the center",
            "Leaving the light-squared bishop trapped",
            "Being too passive in the middlegame"
        ]
    },

    # ==================== QUEEN'S PAWN OPENINGS (1.d4) ====================
    "queens_gambit": {
        "name": "Queen's Gambit",
        "eco": "D00-D69",
        "color": "white",
        "main_line": ["d4", "d5", "c4"],
        "description": "White offers a pawn to gain central control. Not a true gambit - the pawn can be regained.",
        "key_ideas": [
            "Control the center with c4 and e3/e4",
            "The c4 pawn attacks d5, undermining Black's center",
            "Develop pieces to natural squares: Nc3, Nf3, Bg5",
            "Look for the minority attack on the queenside"
        ],
        "common_variations": [
            {
                "name": "Queen's Gambit Declined",
                "moves": ["d4", "d5", "c4", "e6"],
                "idea": "Black declines and builds a solid position. Very classical."
            },
            {
                "name": "Queen's Gambit Accepted",
                "moves": ["d4", "d5", "c4", "dxc4"],
                "idea": "Black takes but can't hold the pawn. White gets easy development."
            },
            {
                "name": "Slav Defense",
                "moves": ["d4", "d5", "c4", "c6"],
                "idea": "Black supports d5 with c6, keeping the bishop flexible."
            }
        ],
        "traps": [
            {
                "name": "Elephant Trap",
                "for_color": "black",
                "position": "rnbqkb1r/ppp2ppp/4pn2/3p4/2PP4/2N5/PP2PPPP/R1BQKBNR w KQkq - 0 4",
                "winning_line": ["cxd5", "exd5", "Nxd5", "Nxd5", "Qxd5", "Bb4+"],
                "explanation": "If White gets greedy, Black wins material with a discovered attack."
            }
        ],
        "typical_mistakes": [
            "Taking on d5 too early (allows ...Nxd5)",
            "Neglecting development for pawn grabbing",
            "Not preparing e4 properly"
        ]
    },
    
    "london_system": {
        "name": "London System",
        "eco": "D00",
        "color": "white",
        "main_line": ["d4", "d5", "Bf4"],
        "description": "A solid, easy-to-learn system. White develops the bishop before e3 to avoid it being locked in.",
        "key_ideas": [
            "Develop Bf4, e3, Nf3, Bd3, Nbd2, c3",
            "The pawn structure is very solid",
            "Castle kingside and play for e4 or Ne5",
            "A reliable choice against any Black setup"
        ],
        "common_variations": [
            {
                "name": "Standard London",
                "moves": ["d4", "d5", "Bf4", "Nf6", "e3", "e6", "Nf3", "Bd6"],
                "idea": "Black mirrors with ...Bd6. White should trade or retreat the bishop."
            }
        ],
        "traps": [],
        "typical_mistakes": [
            "Playing e3 before Bf4 (traps the bishop)",
            "Not knowing how to handle ...Bd6",
            "Being too passive - still need to create threats"
        ]
    },
    
    # ==================== SCANDINAVIAN DEFENSE (1.e4 d5) ====================
    "scandinavian_defense": {
        "name": "Scandinavian Defense",
        "eco": "B01",
        "color": "black",
        "main_line": ["e4", "d5"],
        "description": "An aggressive defense where Black immediately challenges White's e4 pawn. Simple and direct.",
        "key_ideas": [
            "After exd5 Qxd5, develop quickly despite the early queen move",
            "Place the queen on a5 or d6 to stay active",
            "Develop with ...Nf6, ...Bf5, ...e6, ...c6",
            "Aim for solid, easy-to-play positions"
        ],
        "common_variations": [
            {
                "name": "Main Line (Qxd5)",
                "moves": ["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5"],
                "idea": "The queen retreats to a5, staying active and eyeing e5."
            },
            {
                "name": "Modern Scandinavian (Nf6)",
                "moves": ["e4", "d5", "exd5", "Nf6"],
                "idea": "Black lets White keep the pawn temporarily, focusing on rapid development."
            },
            {
                "name": "Icelandic Gambit",
                "moves": ["e4", "d5", "exd5", "Nf6", "c4", "e6"],
                "idea": "Black sacrifices a pawn for quick development and open lines."
            }
        ],
        "traps": [
            {
                "name": "Scholar's Mate Threat Defense",
                "for_color": "black",
                "position": "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                "winning_line": ["exd5", "Qxd5", "Nc3", "Qa5"],
                "explanation": "The queen is safe on a5 and helps control key squares."
            }
        ],
        "typical_mistakes": [
            "Not developing the queen to a safe square quickly",
            "Playing ...Qd8 which wastes tempo",
            "Forgetting to develop the light-squared bishop early"
        ]
    },
    
    # ==================== QUEEN'S PAWN GAME (1.d4) ====================
    "queens_pawn_game": {
        "name": "Queen's Pawn Game",
        "eco": "D00",
        "color": "white",
        "main_line": ["d4", "d5"],
        "description": "A classical opening leading to strategic, positional play. The center is more closed than 1.e4 openings.",
        "key_ideas": [
            "Control the center with pawns on d4 and potentially c4",
            "Develop knights to f3 and c3",
            "Consider the London System (Bf4) or Queen's Gambit (c4)",
            "Play for a gradual space advantage"
        ],
        "common_variations": [
            {
                "name": "Queen's Gambit",
                "moves": ["d4", "d5", "c4"],
                "idea": "Offer a pawn to control the center. Black usually declines."
            },
            {
                "name": "London System",
                "moves": ["d4", "d5", "Bf4"],
                "idea": "Develop the bishop before e3. Solid and reliable."
            },
            {
                "name": "Colle System",
                "moves": ["d4", "d5", "Nf3", "Nf6", "e3"],
                "idea": "Set up a solid pawn structure and prepare a kingside attack."
            }
        ],
        "traps": [
            {
                "name": "Elephant Trap",
                "for_color": "black",
                "position": "rnbqkb1r/ppp2ppp/4pn2/3p4/2PP4/2N5/PP2PPPP/R1BQKBNR w KQkq - 0 4",
                "winning_line": ["cxd5", "exd5", "Nxd5", "Nxd5", "Qxd5", "Bb4+"],
                "explanation": "If White captures on d5 carelessly, Black wins material with a discovered attack."
            }
        ],
        "typical_mistakes": [
            "Not developing pieces actively",
            "Getting into passive positions",
            "Ignoring Black's counterplay on the queenside"
        ]
    },
    
    # ==================== QUEEN'S GAMBIT DECLINED ====================
    "queens_gambit_declined": {
        "name": "Queen's Gambit Declined",
        "eco": "D30-D69",
        "color": "black",
        "main_line": ["d4", "d5", "c4", "e6"],
        "description": "A solid, classical defense. Black maintains the d5 pawn and develops harmoniously.",
        "key_ideas": [
            "Maintain the pawn on d5 as long as beneficial",
            "Develop with ...Nf6, ...Be7, ...O-O, ...c6",
            "The light-squared bishop is often 'bad' - find ways to activate it",
            "Look for ...c5 or ...e5 breaks to free your position"
        ],
        "common_variations": [
            {
                "name": "Orthodox Defense",
                "moves": ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7"],
                "idea": "Classical development. Black aims for ...O-O and ...Nbd7."
            },
            {
                "name": "Tartakower Defense",
                "moves": ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7", "e3", "O-O", "Nf3", "b6"],
                "idea": "Fianchetto the queen's bishop to solve the 'bad bishop' problem."
            }
        ],
        "traps": [],
        "typical_mistakes": [
            "Releasing the tension in the center too early",
            "Not finding an active plan for the light-squared bishop",
            "Playing too passively"
        ]
    },
    
    # ==================== RUY LOPEZ ====================
    "ruy_lopez": {
        "name": "Ruy Lopez",
        "eco": "C60-C99",
        "color": "white",
        "main_line": ["e4", "e5", "Nf3", "Nc6", "Bb5"],
        "description": "One of the oldest and most respected openings. The bishop pins the knight, creating long-term pressure.",
        "key_ideas": [
            "The bishop on b5 puts pressure on Black's center",
            "Play d3, O-O, and prepare for d4",
            "The Marshall Attack (with ...d5) is a famous Black counter",
            "Long strategic battles are typical"
        ],
        "common_variations": [
            {
                "name": "Morphy Defense",
                "moves": ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6"],
                "idea": "Black kicks the bishop and develops naturally."
            },
            {
                "name": "Berlin Defense",
                "moves": ["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6"],
                "idea": "Black avoids the main lines. The Berlin Wall endgame is drawish."
            },
            {
                "name": "Marshall Attack",
                "moves": ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7", "Re1", "b5", "Bb3", "O-O", "c3", "d5"],
                "idea": "Black sacrifices a pawn for a strong attack on the kingside."
            }
        ],
        "traps": [
            {
                "name": "Noah's Ark Trap",
                "for_color": "black",
                "position": "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
                "winning_line": ["a6", "Ba4", "b5", "Bb3", "c5", "c3", "c4"],
                "explanation": "Black traps White's bishop on b3 with pawns, winning material."
            }
        ],
        "typical_mistakes": [
            "Taking on c6 too early without reason",
            "Not understanding when to exchange the bishop",
            "Missing tactical tricks with ...d5"
        ]
    },
    
    # ==================== ITALIAN: TRAXLER ATTACK ====================
    "italian_traxler_attack": {
        "name": "Italian: Traxler Attack",
        "eco": "C57",
        "color": "black",
        "main_line": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "Bc5"],
        "description": "A sharp counter-attack where Black ignores the threat to f7 and offers a counter-sacrifice!",
        "key_ideas": [
            "Black allows Nxf7 but gets strong counterplay",
            "After Nxf7 Bxf2+! leads to complex tactics",
            "Black's lead in development compensates for material",
            "Very tactical - study the main lines carefully!"
        ],
        "common_variations": [
            {
                "name": "Main Line",
                "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "Bc5", "Nxf7", "Bxf2+"],
                "idea": "Black sacrifices back, opening lines to White's king."
            }
        ],
        "traps": [
            {
                "name": "Traxler Counter-Sacrifice",
                "for_color": "black",
                "position": "r1bqk2r/pppp1ppp/2n2n2/2b1p1N1/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 5 5",
                "winning_line": ["Nxf7", "Bxf2+", "Kxf2", "Nxe4+"],
                "explanation": "Black gives back material to expose White's king and win the initiative."
            }
        ],
        "typical_mistakes": [
            "Not knowing the theory - this line requires preparation",
            "Playing Bc5 without understanding the follow-up",
            "Missing the Bxf2+ resource"
        ]
    }
}


# ============================================================================
# OPENING DETECTION
# ============================================================================

def detect_opening_from_moves(moves: List[str]) -> Optional[Dict]:
    """
    Detect which opening was played from a list of moves.
    Returns the opening info if recognized.
    """
    if not moves or len(moves) < 2:
        return None
    
    moves_str = " ".join(moves[:10]).lower()
    
    # Check each opening
    for key, opening in OPENINGS_DATABASE.items():
        main_line = " ".join(opening["main_line"]).lower()
        if main_line in moves_str or moves_str.startswith(main_line[:10]):
            return opening
    
    # Basic detection by first moves
    if moves[0].lower() == "e4":
        if len(moves) > 1:
            if moves[1].lower() == "c5":
                return OPENINGS_DATABASE.get("sicilian_defense")
            elif moves[1].lower() == "e6":
                return OPENINGS_DATABASE.get("french_defense")
            elif moves[1].lower() == "c6":
                return OPENINGS_DATABASE.get("caro_kann")
            elif moves[1].lower() == "e5":
                if len(moves) > 4 and "bc4" in moves_str:
                    return OPENINGS_DATABASE.get("italian_game")
    elif moves[0].lower() == "d4":
        if len(moves) > 2 and "c4" in moves_str:
            return OPENINGS_DATABASE.get("queens_gambit")
        elif len(moves) > 2 and "bf4" in moves_str:
            return OPENINGS_DATABASE.get("london_system")
    
    return None


# ============================================================================
# USER OPENING ANALYSIS
# ============================================================================

async def get_user_opening_stats(db, user_id: str) -> List[Dict]:
    """
    Get detailed statistics on user's most-played openings.
    Maps ECO codes to proper opening names using eco_openings.json.
    """
    # Get all analyzed games
    games = await db.games.find({"user_id": user_id}).to_list(200)
    
    opening_stats = {}
    
    for game in games:
        raw_opening = game.get("opening_name") or game.get("opening") or game.get("eco") or "Unknown"
        
        # Convert ECO code to proper opening name
        display_name = get_opening_name_from_eco(raw_opening)
        
        # Create a normalized key for grouping
        opening_key = display_name.lower().replace(" ", "_").replace("-", "_").replace("'", "").replace(":", "")
        
        # Store the ECO code if it looks like one
        eco_code = raw_opening.upper() if (len(raw_opening) <= 3 and raw_opening[0].isalpha() and raw_opening[1:].isdigit()) else None
        
        if opening_key not in opening_stats:
            opening_stats[opening_key] = {
                "name": display_name,
                "eco": eco_code,
                "games": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "as_white": 0,
                "as_black": 0,
                "total_accuracy": 0
            }
        
        stats = opening_stats[opening_key]
        stats["games"] += 1
        if eco_code and not stats["eco"]:
            stats["eco"] = eco_code
        
        result = game.get("result", "").lower()
        user_color = game.get("user_color", "white")
        
        if user_color == "white":
            stats["as_white"] += 1
            if result == "win" or result == "1-0":
                stats["wins"] += 1
            elif result == "loss" or result == "0-1":
                stats["losses"] += 1
            else:
                stats["draws"] += 1
        else:
            stats["as_black"] += 1
            if result == "win" or result == "0-1":
                stats["wins"] += 1
            elif result == "loss" or result == "1-0":
                stats["losses"] += 1
            else:
                stats["draws"] += 1
        
        accuracy = game.get("accuracy") or 0
        stats["total_accuracy"] += accuracy
    
    # Calculate averages and format results
    results = []
    for key, stats in opening_stats.items():
        if stats["games"] > 0:
            win_rate = round(stats["wins"] / stats["games"] * 100, 1)
            avg_accuracy = round(stats["total_accuracy"] / stats["games"], 1)
            
            # Get opening info from database
            db_info = OPENINGS_DATABASE.get(key, {})
            
            results.append({
                "key": key,
                "eco": stats.get("eco"),
                "name": stats["name"],
                "games_played": stats["games"],
                "win_rate": win_rate,
                "avg_accuracy": avg_accuracy,
                "wins": stats["wins"],
                "losses": stats["losses"],
                "draws": stats["draws"],
                "as_white": stats["as_white"],
                "as_black": stats["as_black"],
                "has_training_content": key in OPENINGS_DATABASE,
                "key_ideas": db_info.get("key_ideas", []),
                "description": db_info.get("description", ""),
                "mastery_level": classify_mastery(stats["games"], win_rate, avg_accuracy)
            })
    
    # Sort by games played
    results.sort(key=lambda x: -x["games_played"])
    
    return results[:10]  # Top 10


def classify_mastery(games: int, win_rate: float, accuracy: float) -> str:
    """Classify how well user knows an opening."""
    if games < 3:
        return "learning"
    elif games >= 10 and win_rate >= 60 and accuracy >= 75:
        return "mastered"
    elif games >= 5 and win_rate >= 50:
        return "comfortable"
    else:
        return "needs_work"


async def get_opening_training_content(db, user_id: str, opening_key: str) -> Dict:
    """
    Get training content for a specific opening.
    
    Returns:
    - Key variations to study
    - Traps to know
    - Practice positions
    - User's mistakes in this opening
    """
    opening = OPENINGS_DATABASE.get(opening_key)
    
    if not opening:
        return {"error": f"Opening '{opening_key}' not found in database"}
    
    # Get user's games in this opening
    user_games = await db.games.find({
        "user_id": user_id,
        "opening_name": {"$regex": opening["name"], "$options": "i"}
    }).limit(20).to_list(20)
    
    # Find common mistakes in this opening (from user's games)
    user_mistakes = []
    for game in user_games:
        analysis = await db.game_analyses.find_one({"game_id": game.get("game_id")})
        if analysis:
            sf = analysis.get("stockfish_analysis", {})
            moves = sf.get("move_evaluations", [])
            
            # Look at opening phase mistakes (first 15 moves)
            for move in moves[:15]:
                if move.get("cp_loss", 0) >= 100:
                    user_mistakes.append({
                        "game_id": game.get("game_id"),
                        "move_number": move.get("move_number"),
                        "move": move.get("move"),
                        "best_move": move.get("best_move"),
                        "cp_loss": move.get("cp_loss"),
                        "fen": move.get("fen_before")
                    })
    
    # Build practice positions from traps
    practice_positions = []
    for trap in opening.get("traps", []):
        practice_positions.append({
            "type": "trap",
            "name": trap["name"],
            "fen": trap["position"],
            "correct_line": trap["winning_line"],
            "explanation": trap["explanation"],
            "for_color": trap["for_color"]
        })
    
    return {
        "opening": opening,
        "user_stats": {
            "games_found": len(user_games),
            "mistakes_in_opening": len(user_mistakes)
        },
        "variations": opening.get("common_variations", []),
        "traps": opening.get("traps", []),
        "key_ideas": opening.get("key_ideas", []),
        "typical_mistakes": opening.get("typical_mistakes", []),
        "practice_positions": practice_positions,
        "your_mistakes": user_mistakes[:5]  # Top 5 mistakes
    }


async def get_opening_quiz(db, user_id: str, opening_key: str) -> List[Dict]:
    """
    Generate quiz questions for an opening.
    
    Questions test:
    1. Move order knowledge
    2. Trap awareness
    3. Key ideas
    """
    opening = OPENINGS_DATABASE.get(opening_key)
    if not opening:
        return []
    
    questions = []
    
    # Question type 1: What's the main idea?
    if opening.get("key_ideas"):
        questions.append({
            "type": "concept",
            "question": f"What is a key idea in the {opening['name']}?",
            "correct_answer": opening["key_ideas"][0],
            "options": opening["key_ideas"][:4] if len(opening["key_ideas"]) >= 4 else opening["key_ideas"],
            "explanation": f"In the {opening['name']}, one of the main goals is: {opening['key_ideas'][0]}"
        })
    
    # Question type 2: Trap positions
    for trap in opening.get("traps", []):
        questions.append({
            "type": "position",
            "question": f"Find the winning move in the {trap['name']}",
            "fen": trap["position"],
            "correct_move": trap["winning_line"][0],
            "explanation": trap["explanation"]
        })
    
    # Question type 3: Move order
    if opening.get("common_variations"):
        var = opening["common_variations"][0]
        questions.append({
            "type": "move_order",
            "question": f"What is the main line of the {var['name']}?",
            "correct_answer": " ".join(var["moves"]),
            "explanation": var["idea"]
        })
    
    return questions


# ============================================================================
# OPENING RECOMMENDATIONS
# ============================================================================

def get_opening_recommendations(user_openings: List[Dict], color: str = "both") -> List[Dict]:
    """
    Recommend openings to study based on user's repertoire.
    """
    recommendations = []
    
    # Find gaps in repertoire
    played_openings = {o["key"] for o in user_openings}
    
    for key, opening in OPENINGS_DATABASE.items():
        if key not in played_openings:
            if color == "both" or opening["color"] == color:
                recommendations.append({
                    "key": key,
                    "name": opening["name"],
                    "color": opening["color"],
                    "description": opening["description"],
                    "reason": "Expand your repertoire"
                })
    
    # Find openings that need work
    for opening in user_openings:
        if opening.get("mastery_level") == "needs_work" and opening["games_played"] >= 3:
            recommendations.append({
                "key": opening["key"],
                "name": opening["name"],
                "color": "white" if opening["as_white"] > opening["as_black"] else "black",
                "description": opening.get("description", ""),
                "reason": f"Win rate only {opening['win_rate']}% - time to improve!"
            })
    
    return recommendations[:5]  # Top 5 recommendations

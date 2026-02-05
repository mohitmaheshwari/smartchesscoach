"""
Opening Repertoire Analysis Service

Analyzes player's opening choices, identifies patterns, mistakes,
and provides personalized coaching recommendations.
"""

import re
from typing import Dict, Any, List, Optional
from collections import defaultdict
import chess
import chess.pgn
import io

# Common opening classifications
OPENING_DATABASE = {
    # e4 openings
    "e4 e5": {
        "name": "Open Game",
        "variations": {
            "e4 e5 Nf3 Nc6 Bb5": "Ruy Lopez",
            "e4 e5 Nf3 Nc6 Bc4": "Italian Game",
            "e4 e5 Nf3 Nc6 d4": "Scotch Game",
            "e4 e5 Nf3 Nf6": "Petrov Defense",
            "e4 e5 f4": "King's Gambit",
            "e4 e5 Nc3": "Vienna Game",
            "e4 e5 Bc4": "Bishop's Opening",
        }
    },
    "e4 c5": {
        "name": "Sicilian Defense",
        "variations": {
            "e4 c5 Nf3 d6": "Sicilian Najdorf/Dragon",
            "e4 c5 Nf3 Nc6": "Sicilian Classical",
            "e4 c5 Nf3 e6": "Sicilian Scheveningen/Kan",
            "e4 c5 c3": "Sicilian Alapin",
            "e4 c5 Nc3": "Sicilian Closed",
        }
    },
    "e4 e6": {"name": "French Defense", "variations": {}},
    "e4 c6": {"name": "Caro-Kann Defense", "variations": {}},
    "e4 d5": {"name": "Scandinavian Defense", "variations": {}},
    "e4 d6": {"name": "Pirc Defense", "variations": {}},
    "e4 Nf6": {"name": "Alekhine Defense", "variations": {}},
    "e4 g6": {"name": "Modern Defense", "variations": {}},
    
    # d4 openings
    "d4 d5": {
        "name": "Closed Game",
        "variations": {
            "d4 d5 c4": "Queen's Gambit",
            "d4 d5 c4 e6": "Queen's Gambit Declined",
            "d4 d5 c4 dxc4": "Queen's Gambit Accepted",
            "d4 d5 c4 c6": "Slav Defense",
            "d4 d5 Nf3": "Queen's Pawn Game",
            "d4 d5 Bf4": "London System",
        }
    },
    "d4 Nf6": {
        "name": "Indian Defense",
        "variations": {
            "d4 Nf6 c4 g6": "King's Indian Defense",
            "d4 Nf6 c4 e6": "Nimzo/Queen's Indian",
            "d4 Nf6 c4 c5": "Benoni Defense",
            "d4 Nf6 Nf3": "Indian Game",
            "d4 Nf6 Bf4": "London System",
        }
    },
    "d4 f5": {"name": "Dutch Defense", "variations": {}},
    "d4 d6": {"name": "Old Indian Defense", "variations": {}},
    
    # Other openings
    "c4": {"name": "English Opening", "variations": {}},
    "Nf3": {"name": "Reti Opening", "variations": {}},
    "g3": {"name": "King's Fianchetto", "variations": {}},
    "b3": {"name": "Larsen's Opening", "variations": {}},
}


def parse_pgn_moves(pgn: str) -> List[str]:
    """Extract move list from PGN"""
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if not game:
            return []
        
        moves = []
        board = game.board()
        for move in game.mainline_moves():
            moves.append(board.san(move))
            board.push(move)
        return moves
    except Exception:
        return []


def classify_opening(moves: List[str]) -> Dict[str, Any]:
    """Classify the opening based on first moves"""
    if not moves:
        return {"name": "Unknown", "eco": "", "variation": ""}
    
    # Build move sequence for matching
    move_seq = " ".join(moves[:10])
    first_move = moves[0] if moves else ""
    second_move = f"{moves[0]} {moves[1]}" if len(moves) > 1 else first_move
    
    # Try to match against database
    best_match = {"name": "Unknown", "variation": "", "moves_matched": 0}
    
    for key, data in OPENING_DATABASE.items():
        if move_seq.startswith(key) or second_move.startswith(key):
            if len(key.split()) > best_match["moves_matched"]:
                best_match = {
                    "name": data["name"],
                    "variation": "",
                    "moves_matched": len(key.split())
                }
                
                # Check for variations
                for var_key, var_name in data.get("variations", {}).items():
                    if move_seq.startswith(var_key):
                        if len(var_key.split()) > best_match["moves_matched"]:
                            best_match = {
                                "name": var_name,
                                "variation": data["name"],
                                "moves_matched": len(var_key.split())
                            }
    
    # Fallback classifications
    if best_match["name"] == "Unknown":
        if first_move == "e4":
            best_match["name"] = "King's Pawn Opening"
        elif first_move == "d4":
            best_match["name"] = "Queen's Pawn Opening"
        elif first_move == "c4":
            best_match["name"] = "English Opening"
        elif first_move == "Nf3":
            best_match["name"] = "Reti Opening"
        elif first_move in ["g3", "b3", "f4", "Nc3"]:
            best_match["name"] = f"Irregular Opening ({first_move})"
    
    return best_match


def analyze_opening_mistakes(moves: List[str], analysis: Dict, user_color: str) -> List[Dict]:
    """Extract mistakes made in the opening phase (first 10 moves)"""
    mistakes = []
    commentary = analysis.get("commentary", []) or analysis.get("move_by_move", [])
    
    for move_data in commentary:
        move_num = move_data.get("move_number", 0)
        if move_num > 10:  # Only opening phase
            break
            
        evaluation = move_data.get("evaluation", "")
        if evaluation in ["blunder", "mistake", "inaccuracy"]:
            # Check if it's the user's move
            is_user_move = (
                (user_color == "white" and move_data.get("color") != "black") or
                (user_color == "black" and move_data.get("color") == "black") or
                move_data.get("is_white", True) == (user_color == "white")
            )
            
            if is_user_move or not move_data.get("color"):  # Include if color unclear
                mistakes.append({
                    "move_number": move_num,
                    "move": move_data.get("move", moves[move_num-1] if move_num <= len(moves) else "?"),
                    "type": evaluation,
                    "lesson": move_data.get("lesson", ""),
                    "best_move": move_data.get("best_move", ""),
                    "cp_loss": move_data.get("centipawn_loss", 0)
                })
    
    return mistakes


async def analyze_opening_repertoire(db, user_id: str) -> Dict[str, Any]:
    """
    Analyze user's opening repertoire from all their games.
    Returns detailed stats and personalized recommendations.
    """
    # Get all user's games with analyses
    games = await db.games.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "result": 1, "white_player": 1, "black_player": 1}
    ).to_list(200)
    
    analyses = {}
    async for a in db.game_analyses.find({"user_id": user_id}, {"_id": 0}):
        analyses[a.get("game_id")] = a
    
    if not games:
        return {
            "has_data": False,
            "message": "No games found. Import games to see your opening repertoire analysis."
        }
    
    # Analyze each game
    white_openings = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0, "games": [], "mistakes": []})
    black_openings = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0, "games": [], "mistakes": []})
    
    all_opening_mistakes = []
    total_games = {"white": 0, "black": 0}
    
    for game in games:
        pgn = game.get("pgn", "")
        user_color = game.get("user_color", "white")
        result = game.get("result", "")
        game_id = game.get("game_id")
        
        moves = parse_pgn_moves(pgn)
        if not moves:
            continue
        
        opening = classify_opening(moves)
        opening_name = opening["name"]
        
        # Determine game outcome from user's perspective
        if result == "1-0":
            outcome = "win" if user_color == "white" else "loss"
        elif result == "0-1":
            outcome = "win" if user_color == "black" else "loss"
        else:
            outcome = "draw"
        
        # Get opening mistakes from analysis
        analysis = analyses.get(game_id, {})
        opening_mistakes = analyze_opening_mistakes(moves, analysis, user_color)
        
        # Store data
        openings = white_openings if user_color == "white" else black_openings
        total_games[user_color] += 1
        
        openings[opening_name]["games"].append({
            "game_id": game_id,
            "result": result,
            "outcome": outcome,
            "moves": moves[:10],
            "mistakes_count": len(opening_mistakes)
        })
        
        if outcome == "win":
            openings[opening_name]["wins"] += 1
        elif outcome == "loss":
            openings[opening_name]["losses"] += 1
        else:
            openings[opening_name]["draws"] += 1
        
        openings[opening_name]["mistakes"].extend(opening_mistakes)
        
        for m in opening_mistakes:
            m["opening"] = opening_name
            m["color"] = user_color
            all_opening_mistakes.append(m)
    
    # Calculate stats and generate recommendations
    white_repertoire = []
    for name, data in white_openings.items():
        total = data["wins"] + data["losses"] + data["draws"]
        if total > 0:
            win_rate = round(data["wins"] / total * 100, 1)
            white_repertoire.append({
                "name": name,
                "games_played": total,
                "wins": data["wins"],
                "losses": data["losses"],
                "draws": data["draws"],
                "win_rate": win_rate,
                "mistakes_total": len(data["mistakes"]),
                "mistakes_per_game": round(len(data["mistakes"]) / total, 2),
                "common_mistakes": get_common_mistakes(data["mistakes"])
            })
    
    black_repertoire = []
    for name, data in black_openings.items():
        total = data["wins"] + data["losses"] + data["draws"]
        if total > 0:
            win_rate = round(data["wins"] / total * 100, 1)
            black_repertoire.append({
                "name": name,
                "games_played": total,
                "wins": data["wins"],
                "losses": data["losses"],
                "draws": data["draws"],
                "win_rate": win_rate,
                "mistakes_total": len(data["mistakes"]),
                "mistakes_per_game": round(len(data["mistakes"]) / total, 2),
                "common_mistakes": get_common_mistakes(data["mistakes"])
            })
    
    # Sort by games played
    white_repertoire.sort(key=lambda x: x["games_played"], reverse=True)
    black_repertoire.sort(key=lambda x: x["games_played"], reverse=True)
    
    # Generate personalized coaching recommendations
    recommendations = generate_opening_recommendations(
        white_repertoire, 
        black_repertoire, 
        all_opening_mistakes,
        total_games
    )
    
    # Find problem areas
    problem_openings = find_problem_openings(white_repertoire, black_repertoire)
    
    return {
        "has_data": True,
        "total_games": total_games["white"] + total_games["black"],
        "games_as_white": total_games["white"],
        "games_as_black": total_games["black"],
        "white_repertoire": white_repertoire[:10],  # Top 10
        "black_repertoire": black_repertoire[:10],
        "problem_openings": problem_openings,
        "total_opening_mistakes": len(all_opening_mistakes),
        "recommendations": recommendations,
        "coaching_focus": get_coaching_focus(white_repertoire, black_repertoire, all_opening_mistakes)
    }


def get_common_mistakes(mistakes: List[Dict]) -> List[Dict]:
    """Group and count common mistake patterns"""
    mistake_counts = defaultdict(lambda: {"count": 0, "examples": []})
    
    for m in mistakes:
        key = m.get("type", "unknown")
        mistake_counts[key]["count"] += 1
        if len(mistake_counts[key]["examples"]) < 2:
            mistake_counts[key]["examples"].append({
                "move": m.get("move"),
                "move_number": m.get("move_number"),
                "lesson": m.get("lesson", "")[:100]
            })
    
    return [
        {"type": k, "count": v["count"], "examples": v["examples"]}
        for k, v in sorted(mistake_counts.items(), key=lambda x: x[1]["count"], reverse=True)
    ]


def find_problem_openings(white_rep: List, black_rep: List) -> List[Dict]:
    """Find openings with poor performance"""
    problems = []
    
    for opening in white_rep + black_rep:
        if opening["games_played"] >= 2:  # Need at least 2 games
            if opening["win_rate"] < 30:
                problems.append({
                    "name": opening["name"],
                    "color": "white" if opening in white_rep else "black",
                    "issue": "low_win_rate",
                    "win_rate": opening["win_rate"],
                    "games": opening["games_played"],
                    "message": f"Only {opening['win_rate']}% win rate in {opening['games_played']} games"
                })
            elif opening["mistakes_per_game"] > 1.5:
                problems.append({
                    "name": opening["name"],
                    "color": "white" if opening in white_rep else "black",
                    "issue": "high_mistakes",
                    "mistakes_per_game": opening["mistakes_per_game"],
                    "games": opening["games_played"],
                    "message": f"{opening['mistakes_per_game']} mistakes per game on average"
                })
    
    return sorted(problems, key=lambda x: x.get("win_rate", 100))[:5]


def generate_opening_recommendations(white_rep: List, black_rep: List, mistakes: List, total: Dict) -> List[Dict]:
    """Generate personalized opening recommendations"""
    recs = []
    
    # Check repertoire diversity
    if len(white_rep) == 1 and total["white"] >= 5:
        recs.append({
            "type": "diversity",
            "priority": "medium",
            "message": f"You only play {white_rep[0]['name']} as White. Consider learning a second opening to be less predictable.",
            "suggestion": "Try the London System (1.d4 2.Bf4) - solid and easy to learn"
        })
    
    if len(black_rep) == 1 and total["black"] >= 5:
        recs.append({
            "type": "diversity", 
            "priority": "medium",
            "message": f"You only play {black_rep[0]['name']} as Black. A backup defense would help.",
            "suggestion": "Against 1.e4, learn the Caro-Kann (1...c6) - very solid"
        })
    
    # Check for problematic openings
    for opening in white_rep + black_rep:
        if opening["games_played"] >= 3:
            if opening["win_rate"] < 25:
                recs.append({
                    "type": "struggling",
                    "priority": "high",
                    "message": f"You're struggling in the {opening['name']} ({opening['win_rate']}% win rate).",
                    "suggestion": f"Study the main ideas and typical plans. Consider switching if problems persist."
                })
            elif opening["mistakes_per_game"] > 2:
                recs.append({
                    "type": "mistakes",
                    "priority": "high", 
                    "message": f"Too many mistakes in the {opening['name']} opening ({opening['mistakes_per_game']}/game).",
                    "suggestion": "Review the theory for the first 10 moves. Focus on understanding piece placement."
                })
    
    # Check for successful openings to reinforce
    for opening in white_rep + black_rep:
        if opening["games_played"] >= 3 and opening["win_rate"] >= 60:
            recs.append({
                "type": "strength",
                "priority": "low",
                "message": f"The {opening['name']} is working well for you ({opening['win_rate']}% win rate)!",
                "suggestion": "Keep playing it and learn deeper variations to become even stronger."
            })
            break  # Only one positive rec
    
    # General recommendations based on mistake patterns
    blunder_count = len([m for m in mistakes if m.get("type") == "blunder"])
    if blunder_count >= 3:
        recs.append({
            "type": "tactical",
            "priority": "high",
            "message": f"You've blundered {blunder_count} times in openings. These are often tactical oversights.",
            "suggestion": "Before each opening move, check for opponent's threats. Don't rush the first 10 moves."
        })
    
    return sorted(recs, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["priority"], 1))


def get_coaching_focus(white_rep: List, black_rep: List, mistakes: List) -> Dict:
    """Determine main coaching focus area"""
    
    # Find the opening with most issues
    all_openings = [(o, "white") for o in white_rep] + [(o, "black") for o in black_rep]
    
    worst_opening = None
    worst_score = 100
    
    for opening, color in all_openings:
        if opening["games_played"] >= 2:
            # Score = win_rate - (mistakes_per_game * 10)
            score = opening["win_rate"] - (opening["mistakes_per_game"] * 15)
            if score < worst_score:
                worst_score = score
                worst_opening = {"opening": opening, "color": color}
    
    if worst_opening and worst_score < 40:
        return {
            "area": "opening_improvement",
            "opening": worst_opening["opening"]["name"],
            "color": worst_opening["color"],
            "message": f"Focus on improving your {worst_opening['opening']['name']} as {worst_opening['color'].capitalize()}. This is where you're losing the most games."
        }
    
    if len(mistakes) > 10:
        return {
            "area": "opening_accuracy",
            "message": "Work on reducing opening mistakes. Take your time in the first 10 moves and double-check each move."
        }
    
    return {
        "area": "maintain",
        "message": "Your opening play is solid! Focus on middlegame improvement."
    }

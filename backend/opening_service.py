"""
Opening Repertoire Analysis Service

Analyzes player's opening choices, identifies patterns, mistakes,
and provides personalized coaching recommendations in Indian coach style.
"""

import re
from typing import Dict, Any, List, Optional
from collections import defaultdict
import chess
import chess.pgn
import io

# =============================================================================
# OPENING COACHING DATABASE - Specific advice for each opening
# =============================================================================

OPENING_COACHING = {
    # ============ AS WHITE ============
    "Italian Game": {
        "color": "white",
        "key_moves": "1.e4 e5 2.Nf3 Nc6 3.Bc4",
        "main_idea": "Control the center and attack f7 - the weakest point in Black's position",
        "must_know": [
            "After Bc4, you're eyeing f7. Always look for Ng5 attacks!",
            "Castle kingside quickly (O-O) - don't delay!",
            "Push d3 first, then c3 to support d4 pawn push later",
        ],
        "common_mistakes": [
            {"mistake": "Playing d4 too early", "fix": "First play d3 and c3, THEN d4. Prepare it properly."},
            {"mistake": "Forgetting to castle", "fix": "Castle before move 8. Safety first, attack second."},
            {"mistake": "Moving same piece twice", "fix": "Develop all pieces before moving any piece twice."},
        ],
        "simple_plan": "Bc4 → O-O → d3 → c3 → d4 → Attack!",
        "practice_tip": "Play 10 games focusing ONLY on this setup. Don't try tricks, just solid development.",
    },
    
    "Ruy Lopez": {
        "color": "white", 
        "key_moves": "1.e4 e5 2.Nf3 Nc6 3.Bb5",
        "main_idea": "Put pressure on e5 pawn through the knight on c6",
        "must_know": [
            "Bb5 doesn't win the e5 pawn immediately - it's long-term pressure",
            "After ...a6, retreat to Ba4, then O-O",
            "The plan is: O-O → Re1 → c3 → d4",
        ],
        "common_mistakes": [
            {"mistake": "Taking on c6 too early", "fix": "Don't take Bxc6 unless you have a clear reason. Keep the tension!"},
            {"mistake": "Not playing c3", "fix": "c3 is essential to support d4. Always play it."},
        ],
        "simple_plan": "Bb5 → O-O → Re1 → c3 → d4 → Control center",
        "practice_tip": "This is Vishy Anand's favorite! Watch his games for inspiration.",
    },
    
    "French Defense": {
        "color": "white",
        "key_moves": "1.e4 e6 (Black plays ...e6)",
        "main_idea": "You have space advantage. Push e5 to cramp Black!",
        "must_know": [
            "After 1.e4 e6 2.d4 d5 - push 3.e5! This is the Advance Variation - easiest to play",
            "Your plan: e5 → f4 → Nf3 → Be3 → Qd2 → Castle queenside → Attack!",
            "Black's bishop on c8 is stuck. Use this advantage!",
        ],
        "common_mistakes": [
            {"mistake": "Exchanging pawns on d5", "fix": "Don't play exd5! Push e5 instead to gain space."},
            {"mistake": "Not pushing f4", "fix": "f4 supports e5 and prepares f5 attack. Always play it!"},
            {"mistake": "Castling kingside", "fix": "Castle QUEENSIDE (O-O-O) and attack on kingside with g4-h4!"},
        ],
        "simple_plan": "e5! → f4 → Nf3 → Be3 → Qd2 → O-O-O → g4 → h4 → Attack!",
        "practice_tip": "The Advance French (3.e5) is simple and strong. Black suffers with bad bishop.",
    },
    
    "Caro-Kann Defense": {
        "color": "white",
        "key_moves": "1.e4 c6 (Black plays ...c6)",
        "main_idea": "Play the Advance (3.e5) or Exchange (3.exd5) - both are good!",
        "must_know": [
            "Advance (3.e5): Similar to French - gain space, attack kingside",
            "Exchange (3.exd5 cxd5): Simple position, your knight goes to c3 → e2 → f4!",
            "In Exchange: Play c3, Bf4, Nf3, Be2, O-O - solid and easy",
        ],
        "common_mistakes": [
            {"mistake": "Not having a clear plan", "fix": "Pick ONE system (Advance OR Exchange) and stick with it!"},
            {"mistake": "Passive play", "fix": "Even in Exchange variation, look for Nf4 attacking d5!"},
        ],
        "simple_plan": "Advance: e5 → Nc3 → f4 → Nf3 → Be3 | Exchange: exd5 → Nc3 → Bf4 → e3 → Nge2",
        "practice_tip": "Start with Exchange variation (3.exd5) - very safe and easy to learn.",
    },
    
    "Sicilian Defense": {
        "color": "white",
        "key_moves": "1.e4 c5 (Black plays ...c5)",
        "main_idea": "Open Sicilian is complex. Try Alapin (2.c3) for simple play!",
        "must_know": [
            "Alapin (2.c3): Plan is d4 → get nice center → easy game!",
            "After 2.c3 d5 3.exd5 Qxd5 4.d4 - you have great center",
            "If Black plays ...Nf6, go 2.c3 Nf6 3.e5 Nd5 4.d4 - still good!",
        ],
        "common_mistakes": [
            {"mistake": "Playing Open Sicilian without preparation", "fix": "Alapin (2.c3) is much easier! Switch to it."},
            {"mistake": "Not controlling d4", "fix": "In Alapin, ALWAYS play d4. That's the whole point!"},
        ],
        "simple_plan": "2.c3! → d4 → Nf3 → Bd3 → O-O → Simple chess!",
        "practice_tip": "Alapin Sicilian avoids all the complex theory. Perfect for improving players!",
    },
    
    "Queen's Gambit": {
        "color": "white",
        "key_moves": "1.d4 d5 2.c4",
        "main_idea": "Offer the c4 pawn to open the center",
        "must_know": [
            "If Black takes (dxc4): Play e3 → Bxc4 → You got the center!",
            "If Black declines (e6): Play Nc3 → Nf3 → Bg5 → e3 → Solid position",
            "Never worry about losing c4 pawn - you always get it back with advantage",
        ],
        "common_mistakes": [
            {"mistake": "Taking back c4 pawn immediately", "fix": "No rush! Develop with e3, Bxc4 is coming anyway."},
            {"mistake": "Forgetting Bg5", "fix": "Bg5 pins the knight and creates pressure. Essential move!"},
        ],
        "simple_plan": "d4 → c4 → Nc3 → Nf3 → Bg5 → e3 → Control everything!",
        "practice_tip": "Queen's Gambit is solid and reliable. Good for long-term improvement.",
    },
    
    "London System": {
        "color": "white",
        "key_moves": "1.d4 2.Bf4 (early bishop development)",
        "main_idea": "Simple system - same setup against everything!",
        "must_know": [
            "Setup: d4 → Bf4 → e3 → Nf3 → c3 → Bd3 → O-O",
            "Put bishop on f4 BEFORE playing e3, otherwise bishop is stuck!",
            "Against ...c5, play c3 to support d4. Don't let Black break your center.",
        ],
        "common_mistakes": [
            {"mistake": "Playing e3 before Bf4", "fix": "ALWAYS Bf4 first! This is the golden rule of London."},
            {"mistake": "Not playing c3", "fix": "c3 supports d4 and stops ...Nb4. Essential!"},
        ],
        "simple_plan": "d4 → Bf4 → e3 → Nf3 → c3 → Bd3 → O-O → Easy!",
        "practice_tip": "London is perfect for beginners. Same moves every game - focus on middlegame!",
    },
    
    # ============ AS BLACK ============
    "Scandinavian Defense": {
        "color": "black",
        "key_moves": "1.e4 d5",
        "main_idea": "Challenge e4 immediately! Get active play.",
        "must_know": [
            "After 2.exd5 Qxd5 3.Nc3 - play Qa5! (safe square for queen)",
            "Develop: ...Nf6 → ...Bf5 → ...c6 → ...e6 → ...Bd6 → Solid!",
            "Your c8 bishop comes out to f5 or g4 - unlike French Defense!",
        ],
        "common_mistakes": [
            {"mistake": "Leaving queen in center", "fix": "After Nc3, IMMEDIATELY play Qa5. Don't wait!"},
            {"mistake": "Not playing ...c6", "fix": "c6 is essential - supports d5 and creates escape for queen."},
        ],
        "simple_plan": "d5 → Qxd5 → Qa5 → Nf6 → Bf5 → c6 → e6 → Solid position!",
        "practice_tip": "Scandinavian is active and practical. Magnus Carlsen has played it!",
    },
    
    "Sicilian Defense (as Black)": {
        "color": "black",
        "key_moves": "1.e4 c5",
        "main_idea": "Fight for the center with ...d6 and ...e5, attack on queenside",
        "must_know": [
            "Classical setup: ...d6 → ...Nf6 → ...Nc6 → ...e5 → Strong center!",
            "Your plan: Attack on queenside with ...a6 → ...b5 → ...Bb7",
            "Against Alapin (2.c3): Play ...d5! immediately - equalize fast",
        ],
        "common_mistakes": [
            {"mistake": "Not playing ...d6", "fix": "d6 is essential in most Sicilians. Controls e5, develops bishop."},
            {"mistake": "Panicking against attacks", "fix": "Sicilian is sharp. Trust your position, counterattack on queenside!"},
        ],
        "simple_plan": "c5 → d6 → Nf6 → Nc6 → e5 (when ready) → Attack queenside!",
        "practice_tip": "Start with the Classical Sicilian (2...Nc6) - easier to learn than Najdorf.",
    },
    
    "King's Indian Defense": {
        "color": "black",
        "key_moves": "1.d4 Nf6 2.c4 g6",
        "main_idea": "Let White take center, then ATTACK it with ...e5 or ...c5",
        "must_know": [
            "Setup: ...Nf6 → ...g6 → ...Bg7 → ...O-O → ...d6 → ...e5!",
            "The ...e5 push is your main break. Time it well!",
            "After ...e5, attack kingside: ...Nh5 → ...f5 → ...f4 → Checkmate ideas!",
        ],
        "common_mistakes": [
            {"mistake": "Not playing ...e5", "fix": "...e5 is the SOUL of King's Indian. Must play it!"},
            {"mistake": "Playing too slow", "fix": "KID is about attack! Once castled, go ...e5 → ...f5 → Attack!"},
        ],
        "simple_plan": "Nf6 → g6 → Bg7 → O-O → d6 → e5! → Nh5 → f5 → Attack king!",
        "practice_tip": "Kasparov's favorite! Watch his attacking games for inspiration.",
    },
    
    "Nimzo-Indian Defense": {
        "color": "black",
        "key_moves": "1.d4 Nf6 2.c4 e6 3.Nc3 Bb4",
        "main_idea": "Pin the knight! Double White's pawns if possible",
        "must_know": [
            "After Bb4, White often plays a3 or Qc2",
            "Against a3: Take Bxc3+ → Double their pawns → Your advantage!",
            "Against Qc2: Play ...c5 or ...d5 → Fight for center",
        ],
        "common_mistakes": [
            {"mistake": "Not taking on c3", "fix": "When White plays a3, take Bxc3! Doubled pawns are weak."},
            {"mistake": "Passive play", "fix": "Nimzo is active! Play ...c5 or ...d5 to challenge center."},
        ],
        "simple_plan": "Nf6 → e6 → Bb4 → (if a3) Bxc3+ → c5 → Fight center!",
        "practice_tip": "Very solid defense. Capablanca's favorite - positional masterpiece!",
    },
}

# Common opening classifications (simplified)
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
            
            # Get coaching info if available
            coaching = get_opening_coaching(name, "white")
            
            white_repertoire.append({
                "name": name,
                "games_played": total,
                "wins": data["wins"],
                "losses": data["losses"],
                "draws": data["draws"],
                "win_rate": win_rate,
                "mistakes_total": len(data["mistakes"]),
                "mistakes_per_game": round(len(data["mistakes"]) / total, 2),
                "common_mistakes": get_common_mistakes(data["mistakes"]),
                "coaching": coaching  # Add coaching tips!
            })
    
    black_repertoire = []
    for name, data in black_openings.items():
        total = data["wins"] + data["losses"] + data["draws"]
        if total > 0:
            win_rate = round(data["wins"] / total * 100, 1)
            
            # Get coaching info if available
            coaching = get_opening_coaching(name, "black")
            
            black_repertoire.append({
                "name": name,
                "games_played": total,
                "wins": data["wins"],
                "losses": data["losses"],
                "draws": data["draws"],
                "win_rate": win_rate,
                "mistakes_total": len(data["mistakes"]),
                "mistakes_per_game": round(len(data["mistakes"]) / total, 2),
                "common_mistakes": get_common_mistakes(data["mistakes"]),
                "coaching": coaching  # Add coaching tips!
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

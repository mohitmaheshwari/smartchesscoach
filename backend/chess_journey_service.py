"""
Chess Journey Service - Comprehensive Progress Tracking

This service provides deep insights into a player's chess journey:
1. Rating progression over time
2. Phase-specific performance (Opening, Middlegame, Endgame)
3. Improvement metrics (then vs now)
4. Habit journey (conquered, in progress, needs attention)
5. Opening repertoire analysis
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


async def get_chess_journey(db, user_id: str) -> Dict[str, Any]:
    """
    Get comprehensive chess journey data for a user.
    This is the main entry point for the Progress page.
    """
    # Get user info
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return {"error": "User not found"}
    
    # Get all analyses for this user
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)  # Oldest first for progression
    
    # Get all games
    games = await db.games.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("imported_at", 1).to_list(500)
    
    # Get player profile
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    # Get mistake cards for habit journey
    cards = await db.mistake_cards.find(
        {"user_id": user_id},
        {"_id": 0}
    ).to_list(500)
    
    # Build journey data
    journey = {
        "member_since": user.get("created_at"),
        "total_games_analyzed": len(analyses),
        "total_games_imported": len(games),
        "rating_progression": await get_rating_progression(db, user_id, user, games),
        "phase_mastery": calculate_phase_mastery(analyses),
        "improvement_metrics": calculate_improvement_metrics(analyses),
        "habit_journey": calculate_habit_journey(profile, cards, analyses),
        "opening_repertoire": calculate_opening_repertoire(games, analyses),
        "weekly_summary": generate_weekly_summary(analyses, profile),
        "insights": generate_insights(analyses, profile, cards)
    }
    
    return journey


async def get_rating_progression(db, user_id: str, user: Dict, games: List[Dict]) -> Dict:
    """
    Get rating progression over time from actual game ratings in PGN.
    """
    import re
    
    # Extract ratings from games (from PGN headers)
    rating_data = []
    
    for game in games:
        pgn = game.get("pgn", "")
        user_color = game.get("user_color", "white")
        imported_at = game.get("imported_at")
        
        # Parse rating from PGN
        white_elo_match = re.search(r'\[WhiteElo "(\d+)"\]', pgn)
        black_elo_match = re.search(r'\[BlackElo "(\d+)"\]', pgn)
        
        user_rating = None
        if user_color == "white" and white_elo_match:
            user_rating = int(white_elo_match.group(1))
        elif user_color == "black" and black_elo_match:
            user_rating = int(black_elo_match.group(1))
        
        if user_rating and imported_at:
            # Parse date
            if isinstance(imported_at, str):
                try:
                    dt = datetime.fromisoformat(imported_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
            else:
                dt = imported_at
            
            rating_data.append({
                "date": dt,
                "rating": user_rating,
                "game_id": game.get("game_id")
            })
    
    # Sort by date
    rating_data.sort(key=lambda x: x["date"])
    
    if not rating_data:
        return {
            "started_at": None,
            "current": None,
            "change": 0,
            "peak": None,
            "weekly_change": 0,
            "history": [],
            "trend": "unknown",
            "note": "No rating data available"
        }
    
    # Build weekly history
    weekly_data = defaultdict(list)
    for r in rating_data:
        week_key = r["date"].strftime("%Y-W%W")
        weekly_data[week_key].append(r["rating"])
    
    rating_history = []
    for week, ratings in sorted(weekly_data.items()):
        avg_rating = sum(ratings) / len(ratings)
        rating_history.append({
            "week": week,
            "rating": int(avg_rating),
            "games": len(ratings)
        })
    
    # Calculate stats
    first_rating = rating_data[0]["rating"]
    last_rating = rating_data[-1]["rating"]
    peak_rating = max(r["rating"] for r in rating_data)
    lowest_rating = min(r["rating"] for r in rating_data)
    
    # Weekly change
    weekly_change = 0
    if len(rating_history) >= 2:
        weekly_change = rating_history[-1]["rating"] - rating_history[-2]["rating"]
    
    # Determine trend
    if last_rating > first_rating + 20:
        trend = "improving"
    elif last_rating < first_rating - 20:
        trend = "declining"
    else:
        trend = "stable"
    
    return {
        "started_at": first_rating,
        "current": last_rating,
        "change": last_rating - first_rating,
        "peak": peak_rating,
        "lowest": lowest_rating,
        "weekly_change": weekly_change,
        "history": rating_history[-12:],  # Last 12 weeks
        "trend": trend,
        "total_games": len(rating_data)
    }


def calculate_phase_mastery(analyses: List[Dict]) -> Dict:
    """
    Calculate performance by game phase (Opening, Middlegame, Endgame).
    """
    phase_stats = {
        "opening": {"games": 0, "blunders": 0, "mistakes": 0, "good_moves": 0},
        "middlegame": {"games": 0, "blunders": 0, "mistakes": 0, "good_moves": 0},
        "endgame": {"games": 0, "blunders": 0, "mistakes": 0, "good_moves": 0}
    }
    
    # Also track early vs recent for trends
    early_phase_stats = {
        "opening": {"blunders": 0, "games": 0},
        "middlegame": {"blunders": 0, "games": 0},
        "endgame": {"blunders": 0, "games": 0}
    }
    late_phase_stats = {
        "opening": {"blunders": 0, "games": 0},
        "middlegame": {"blunders": 0, "games": 0},
        "endgame": {"blunders": 0, "games": 0}
    }
    
    midpoint = len(analyses) // 2
    
    for i, analysis in enumerate(analyses):
        phase_data = analysis.get("phase_analysis", {})
        phases = phase_data.get("phases", [])
        # final_phase available for future use
        _ = phase_data.get("final_phase", "middlegame")
        
        # Get stockfish move evaluations for counting mistakes per phase
        sf_moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
        
        # Count blunders/mistakes by move number ranges
        for phase_info in phases:
            phase_name = phase_info.get("phase", "middlegame")
            start_move = phase_info.get("start_move", 1)
            end_move = phase_info.get("end_move", 100)
            
            phase_stats[phase_name]["games"] += 1
            
            # Count mistakes in this phase
            for move in sf_moves:
                move_num = move.get("move_number", 0)
                if start_move <= move_num <= end_move:
                    eval_type = move.get("evaluation", "")
                    if hasattr(eval_type, "value"):
                        eval_type = eval_type.value
                    
                    if eval_type == "blunder":
                        phase_stats[phase_name]["blunders"] += 1
                    elif eval_type == "mistake":
                        phase_stats[phase_name]["mistakes"] += 1
                    elif eval_type in ["good", "excellent", "best"]:
                        phase_stats[phase_name]["good_moves"] += 1
            
            # Track early vs late for trends
            if i < midpoint:
                early_phase_stats[phase_name]["games"] += 1
                # Count blunders for this phase in early games
            else:
                late_phase_stats[phase_name]["games"] += 1
    
    # Calculate mastery percentages and trends
    result = {}
    for phase in ["opening", "middlegame", "endgame"]:
        stats = phase_stats[phase]
        games = max(stats["games"], 1)
        total_moves = stats["blunders"] + stats["mistakes"] + stats["good_moves"]
        
        # Mastery score: fewer mistakes = higher mastery
        if total_moves > 0:
            good_ratio = stats["good_moves"] / total_moves
            mastery_pct = int(good_ratio * 100)
        else:
            mastery_pct = 50  # Default
        
        # Determine trend
        early_blunders = early_phase_stats[phase]["blunders"] / max(early_phase_stats[phase]["games"], 1)
        late_blunders = late_phase_stats[phase]["blunders"] / max(late_phase_stats[phase]["games"], 1)
        
        if late_blunders < early_blunders * 0.7:
            trend = "improving"
        elif late_blunders > early_blunders * 1.3:
            trend = "declining"
        else:
            trend = "stable"
        
        result[phase] = {
            "mastery_pct": min(mastery_pct, 100),
            "blunders_per_game": round(stats["blunders"] / games, 2),
            "mistakes_per_game": round(stats["mistakes"] / games, 2),
            "trend": trend,
            "games_analyzed": stats["games"]
        }
    
    return result


def calculate_improvement_metrics(analyses: List[Dict]) -> Dict:
    """
    Calculate then vs now improvement metrics.
    """
    if len(analyses) < 2:
        return {
            "has_data": False,
            "message": "Need more analyzed games to show improvement"
        }
    
    # Split into first 5 and last 5 games
    early_games = analyses[:5]
    recent_games = analyses[-5:]
    
    def avg_stat(games, stat_path):
        values = []
        for g in games:
            sf = g.get("stockfish_analysis", {})
            if stat_path == "accuracy":
                val = sf.get("accuracy", 0)
            elif stat_path == "blunders":
                val = g.get("blunders", 0)
            elif stat_path == "mistakes":
                val = g.get("mistakes", 0)
            elif stat_path == "best_moves":
                val = g.get("best_moves", 0) + sf.get("excellent_moves", 0)
            elif stat_path == "avg_cp_loss":
                val = sf.get("avg_cp_loss", 0)
            else:
                val = 0
            if val > 0 or stat_path in ["blunders", "mistakes"]:
                values.append(val)
        return sum(values) / len(values) if values else 0
    
    metrics = {
        "has_data": True,
        "early_games_count": len(early_games),
        "recent_games_count": len(recent_games),
        "accuracy": {
            "then": round(avg_stat(early_games, "accuracy"), 1),
            "now": round(avg_stat(recent_games, "accuracy"), 1),
        },
        "blunders_per_game": {
            "then": round(avg_stat(early_games, "blunders"), 1),
            "now": round(avg_stat(recent_games, "blunders"), 1),
        },
        "mistakes_per_game": {
            "then": round(avg_stat(early_games, "mistakes"), 1),
            "now": round(avg_stat(recent_games, "mistakes"), 1),
        },
        "best_moves_per_game": {
            "then": round(avg_stat(early_games, "best_moves"), 1),
            "now": round(avg_stat(recent_games, "best_moves"), 1),
        },
        "avg_cp_loss": {
            "then": round(avg_stat(early_games, "avg_cp_loss"), 1),
            "now": round(avg_stat(recent_games, "avg_cp_loss"), 1),
        }
    }
    
    # Calculate changes and trends
    for key in ["accuracy", "blunders_per_game", "mistakes_per_game", "best_moves_per_game", "avg_cp_loss"]:
        then_val = metrics[key]["then"]
        now_val = metrics[key]["now"]
        
        if then_val > 0:
            change_pct = ((now_val - then_val) / then_val) * 100
        else:
            change_pct = 0
        
        # Determine if change is good or bad
        # For accuracy and best_moves: higher is better
        # For blunders, mistakes, cp_loss: lower is better
        if key in ["accuracy", "best_moves_per_game"]:
            improved = now_val > then_val
        else:
            improved = now_val < then_val
        
        metrics[key]["change"] = round(now_val - then_val, 1)
        metrics[key]["change_pct"] = round(change_pct, 1)
        metrics[key]["improved"] = improved
        metrics[key]["trend"] = "improving" if improved else ("declining" if now_val != then_val else "stable")
    
    return metrics


def calculate_habit_journey(profile: Dict, cards: List[Dict], analyses: List[Dict]) -> Dict:
    """
    Calculate habit journey: conquered, in progress, needs attention.
    """
    # Group cards by habit
    habit_stats = defaultdict(lambda: {
        "total_cards": 0,
        "mastered_cards": 0,
        "total_attempts": 0,
        "correct_attempts": 0,
        "recent_occurrences": 0
    })
    
    for card in cards:
        habit = card.get("habit_tag", "unknown")
        habit_stats[habit]["total_cards"] += 1
        if card.get("is_mastered"):
            habit_stats[habit]["mastered_cards"] += 1
        habit_stats[habit]["total_attempts"] += card.get("total_attempts", 0)
        habit_stats[habit]["correct_attempts"] += card.get("total_correct", 0)
    
    # Count recent occurrences from last 10 analyses
    recent_analyses = analyses[-10:] if analyses else []
    for analysis in recent_analyses:
        weaknesses = analysis.get("identified_weaknesses", []) or analysis.get("weaknesses", [])
        for w in weaknesses:
            if isinstance(w, dict):
                habit = w.get("subcategory", "").lower().replace(" ", "_")
                # Map to our habit categories
                habit_stats[habit]["recent_occurrences"] += 1
    
    # Categorize habits
    conquered = []
    in_progress = []
    needs_attention = []
    
    HABIT_DISPLAY_NAMES = {
        "back_rank_weakness": "Back-Rank Awareness",
        "hanging_pieces": "Hanging Pieces",
        "pin_blindness": "Pin Awareness",
        "fork_blindness": "Fork Awareness",
        "king_safety": "King Safety",
        "piece_activity": "Piece Activity",
        "pawn_structure": "Pawn Structure",
        "tactical_oversight": "Tactical Oversight",
        "endgame_technique": "Endgame Technique",
        "calculation_error": "Calculation",
        "one_move_blunders": "One-Move Blunders",
        "time_trouble": "Time Management"
    }
    
    for habit, stats in habit_stats.items():
        total = stats["total_cards"]
        mastered = stats["mastered_cards"]
        recent = stats["recent_occurrences"]
        
        display_name = HABIT_DISPLAY_NAMES.get(habit, habit.replace("_", " ").title())
        
        habit_data = {
            "key": habit,
            "display_name": display_name,
            "total_cards": total,
            "mastered_cards": mastered,
            "mastery_pct": round((mastered / total * 100) if total > 0 else 0),
            "recent_occurrences": recent,
            "accuracy": round((stats["correct_attempts"] / stats["total_attempts"] * 100) if stats["total_attempts"] > 0 else 0)
        }
        
        # Categorize
        if total > 0 and mastered >= total * 0.9 and recent == 0:
            conquered.append(habit_data)
        elif total > 0 and mastered > 0:
            in_progress.append(habit_data)
        elif recent > 0 or total > 0:
            needs_attention.append(habit_data)
    
    # Sort by mastery percentage
    in_progress.sort(key=lambda x: x["mastery_pct"], reverse=True)
    needs_attention.sort(key=lambda x: x["recent_occurrences"], reverse=True)
    
    return {
        "conquered": conquered,
        "in_progress": in_progress,
        "needs_attention": needs_attention,
        "total_cards": len(cards),
        "total_mastered": sum(1 for c in cards if c.get("is_mastered")),
        "active_habit": profile.get("top_weaknesses", [{}])[0].get("subcategory") if profile else None
    }


def calculate_opening_repertoire(games: List[Dict], analyses: List[Dict]) -> Dict:
    """
    Calculate opening repertoire with win rates.
    Extracts opening names from ECO codes in PGN.
    """
    import re
    
    # ECO code to Opening name mapping (common openings)
    ECO_TO_OPENING = {
        # A - Flank openings
        "A00": "Uncommon Opening",
        "A01": "Nimzowitsch-Larsen Attack",
        "A02": "Bird's Opening",
        "A04": "Reti Opening",
        "A10": "English Opening",
        "A20": "English Opening",
        "A30": "English Opening",
        "A40": "Queen's Pawn Game",
        "A45": "Trompowsky Attack",
        "A46": "Queen's Pawn Game",
        "A80": "Dutch Defense",
        
        # B - Semi-Open Games
        "B00": "Uncommon King's Pawn",
        "B01": "Scandinavian Defense",
        "B02": "Alekhine's Defense",
        "B06": "Modern Defense",
        "B07": "Pirc Defense",
        "B10": "Caro-Kann Defense",
        "B12": "Caro-Kann Defense",
        "B20": "Sicilian Defense",
        "B21": "Sicilian: Smith-Morra",
        "B22": "Sicilian: Alapin",
        "B23": "Sicilian: Closed",
        "B30": "Sicilian Defense",
        "B40": "Sicilian Defense",
        "B50": "Sicilian Defense",
        "B60": "Sicilian: Richter-Rauzer",
        "B70": "Sicilian: Dragon",
        "B80": "Sicilian: Scheveningen",
        "B90": "Sicilian: Najdorf",
        
        # C - Open Games
        "C00": "French Defense",
        "C01": "French Defense",
        "C02": "French: Advance",
        "C10": "French: Rubinstein",
        "C20": "King's Pawn Game",
        "C21": "Center Game",
        "C23": "Bishop's Opening",
        "C24": "Bishop's Opening",
        "C25": "Vienna Game",
        "C30": "King's Gambit",
        "C40": "King's Knight Opening",
        "C41": "Philidor Defense",
        "C42": "Petrov's Defense",
        "C44": "Scotch Game",
        "C45": "Scotch Game",
        "C46": "Three Knights",
        "C47": "Four Knights",
        "C50": "Italian Game",
        "C51": "Evans Gambit",
        "C52": "Evans Gambit",
        "C53": "Italian: Giuoco Piano",
        "C54": "Italian: Giuoco Piano",
        "C55": "Italian: Two Knights",
        "C56": "Italian: Two Knights",
        "C57": "Italian: Traxler",
        "C60": "Ruy Lopez",
        "C65": "Ruy Lopez: Berlin",
        "C70": "Ruy Lopez",
        "C80": "Ruy Lopez: Open",
        "C84": "Ruy Lopez: Closed",
        "C90": "Ruy Lopez: Closed",
        
        # D - Closed Games
        "D00": "Queen's Pawn Game",
        "D01": "Veresov Attack",
        "D02": "London System",
        "D03": "Torre Attack",
        "D04": "Colle System",
        "D06": "Queen's Gambit",
        "D10": "Slav Defense",
        "D20": "Queen's Gambit Accepted",
        "D30": "Queen's Gambit Declined",
        "D35": "Queen's Gambit: Exchange",
        "D37": "Queen's Gambit Declined",
        "D43": "Semi-Slav Defense",
        "D50": "Queen's Gambit Declined",
        "D70": "Grunfeld Defense",
        "D80": "Grunfeld Defense",
        "D90": "Grunfeld Defense",
        
        # E - Indian Defenses
        "E00": "Catalan Opening",
        "E04": "Catalan: Open",
        "E10": "Indian Defense",
        "E12": "Queen's Indian",
        "E15": "Queen's Indian",
        "E20": "Nimzo-Indian Defense",
        "E30": "Nimzo-Indian Defense",
        "E40": "Nimzo-Indian Defense",
        "E60": "King's Indian Defense",
        "E70": "King's Indian Defense",
        "E80": "King's Indian: Samisch",
        "E90": "King's Indian: Classical",
    }
    
    def get_opening_from_eco(eco_code: str) -> str:
        """Get opening name from ECO code, with fallback to code prefix"""
        if not eco_code:
            return "Unknown Opening"
        
        # Try exact match first
        if eco_code in ECO_TO_OPENING:
            return ECO_TO_OPENING[eco_code]
        
        # Try prefix match (e.g., B90 -> B9 -> B)
        for prefix_len in [2, 1]:
            prefix = eco_code[:prefix_len]
            for code, name in ECO_TO_OPENING.items():
                if code.startswith(prefix):
                    return name
        
        # Return generic based on first letter
        first_letter = eco_code[0] if eco_code else "?"
        letter_map = {
            "A": "Flank Opening",
            "B": "Semi-Open Game",
            "C": "Open Game",
            "D": "Closed Game",
            "E": "Indian Defense"
        }
        return letter_map.get(first_letter, "Unknown Opening")
    
    # Group games by opening and color
    white_openings = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0, "total": 0})
    black_openings = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0, "total": 0})
    
    for game in games:
        # Try to get opening from stored field first
        opening = game.get("opening")
        
        # If not stored, extract from PGN ECO code (case-insensitive)
        if not opening or opening == "?" or opening == "Unknown Opening":
            pgn = game.get("pgn", "")
            # Try both uppercase ECO and lowercase Eco
            eco_match = re.search(r'\[ECO "([A-E]\d{2})"\]', pgn, re.IGNORECASE)
            if not eco_match:
                eco_match = re.search(r'\[Eco "([A-E]\d{2})"\]', pgn, re.IGNORECASE)
            
            if eco_match:
                eco_code = eco_match.group(1).upper()  # Normalize to uppercase
                opening = get_opening_from_eco(eco_code)
            else:
                opening = "Unknown Opening"
        
        # Simplify opening name (take first part)
        opening = opening.split(":")[0].split(",")[0].strip()
        if len(opening) > 25:
            opening = opening[:25] + "..."
        
        user_color = game.get("user_color", "white")
        result = game.get("result", "*")
        
        # Determine if user won/lost/drew
        if result == "1-0":
            user_won = user_color == "white"
        elif result == "0-1":
            user_won = user_color == "black"
        else:
            user_won = None  # Draw or unknown
        
        # Update stats
        openings = white_openings if user_color == "white" else black_openings
        openings[opening]["total"] += 1
        
        if user_won is True:
            openings[opening]["wins"] += 1
        elif user_won is False:
            openings[opening]["losses"] += 1
        else:
            openings[opening]["draws"] += 1
    
    # Calculate win rates and sort
    def process_openings(openings_dict):
        result = []
        for name, stats in openings_dict.items():
            if stats["total"] >= 1:  # Show openings with 1+ games
                win_rate = round((stats["wins"] / stats["total"]) * 100) if stats["total"] > 0 else 0
                result.append({
                    "name": name,
                    "games": stats["total"],
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "draws": stats["draws"],
                    "win_rate": win_rate,
                    "trend": "stable"
                })
        result.sort(key=lambda x: x["games"], reverse=True)
        return result[:5]  # Top 5
    
    return {
        "as_white": {
            "total_games": sum(o["total"] for o in white_openings.values()),
            "openings": process_openings(white_openings)
        },
        "as_black": {
            "total_games": sum(o["total"] for o in black_openings.values()),
            "openings": process_openings(black_openings)
        }
    }


def generate_weekly_summary(analyses: List[Dict], profile: Dict) -> Dict:
    """
    Generate a weekly summary of progress.
    """
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    
    # Get this week's analyses
    this_week = []
    for a in analyses:
        created = a.get("created_at")
        if isinstance(created, str):
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if dt >= week_ago:
                    this_week.append(a)
            except ValueError:
                pass
    
    if not this_week:
        return {
            "games_this_week": 0,
            "message": "No games analyzed this week. Time to play!"
        }
    
    # Calculate week stats
    total_blunders = sum(a.get("blunders", 0) for a in this_week)
    total_mistakes = sum(a.get("mistakes", 0) for a in this_week)
    avg_accuracy = sum(a.get("stockfish_analysis", {}).get("accuracy", 0) for a in this_week) / len(this_week)
    
    return {
        "games_this_week": len(this_week),
        "blunders_this_week": total_blunders,
        "mistakes_this_week": total_mistakes,
        "avg_accuracy": round(avg_accuracy, 1),
        "blunders_per_game": round(total_blunders / len(this_week), 1),
        "message": f"You analyzed {len(this_week)} games this week with {avg_accuracy:.1f}% average accuracy."
    }


def generate_insights(analyses: List[Dict], profile: Dict, cards: List[Dict]) -> List[Dict]:
    """
    Generate actionable insights from the data.
    """
    insights = []
    
    if len(analyses) < 3:
        insights.append({
            "type": "info",
            "title": "Getting Started",
            "message": "Analyze more games to unlock detailed insights about your play.",
            "priority": 1
        })
        return insights
    
    # Insight 1: Biggest improvement
    recent = analyses[-5:] if len(analyses) >= 5 else analyses
    early = analyses[:5]
    
    early_blunders = sum(a.get("blunders", 0) for a in early) / len(early)
    recent_blunders = sum(a.get("blunders", 0) for a in recent) / len(recent)
    
    if recent_blunders < early_blunders * 0.7:
        insights.append({
            "type": "success",
            "title": "Blunder Rate Improved",
            "message": f"Your blunders dropped from {early_blunders:.1f} to {recent_blunders:.1f} per game!",
            "priority": 1
        })
    
    # Insight 2: Area needing work
    if profile:
        top_weakness = profile.get("top_weaknesses", [{}])[0]
        if top_weakness.get("subcategory"):
            weakness_name = top_weakness.get("subcategory", "").replace("_", " ").title()
            insights.append({
                "type": "warning",
                "title": "Focus Area",
                "message": f"'{weakness_name}' appears frequently in your games. The Mistake Mastery training will help.",
                "priority": 2
            })
    
    # Insight 3: Training progress
    mastered_cards = sum(1 for c in cards if c.get("is_mastered"))
    if mastered_cards > 0:
        insights.append({
            "type": "success",
            "title": "Training Progress",
            "message": f"You've mastered {mastered_cards} positions in Mistake Mastery training!",
            "priority": 3
        })
    elif cards:
        insights.append({
            "type": "info",
            "title": "Keep Training",
            "message": f"You have {len(cards)} positions to master. Regular training leads to improvement.",
            "priority": 3
        })
    
    # Sort by priority
    insights.sort(key=lambda x: x["priority"])
    
    return insights[:5]  # Max 5 insights

"""
Data Freshness Service
======================

Ensures all aggregated data is recalculated when games are analyzed.
This service maintains data consistency across all pages:

- Journey page: journey stats, milestones, streaks
- Dashboard: progress, blind spots, daily stats
- Lab/Memory: player identity, patterns, behavioral traits
- Training: recommended exercises based on weaknesses

When to call:
- After each game analysis completes
- When user requests a sync
- On periodic background refresh
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def refresh_all_user_data(db, user_id: str) -> Dict[str, Any]:
    """
    Master refresh function - recalculates all aggregated data for a user.
    
    Call this after game analysis to ensure all pages show fresh data.
    """
    results = {
        "user_id": user_id,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "updates": {}
    }
    
    try:
        # 1. Refresh player identity (Memory tab, coaching context)
        identity_result = refresh_player_identity(db, user_id)
        results["updates"]["player_identity"] = identity_result
        
        # 2. Refresh journey stats
        journey_result = refresh_journey_stats(db, user_id)
        results["updates"]["journey"] = journey_result
        
        # 3. Refresh player profile (dashboard)
        profile_result = refresh_player_profile(db, user_id)
        results["updates"]["player_profile"] = profile_result
        
        # 4. Refresh thinking scores if needed
        thinking_result = ensure_thinking_scores(db, user_id)
        results["updates"]["thinking_scores"] = thinking_result
        
        results["success"] = True
        
    except Exception as e:
        logger.error(f"Error refreshing user data for {user_id}: {e}")
        results["success"] = False
        results["error"] = str(e)
    
    return results


def refresh_player_identity(db, user_id: str) -> Dict[str, Any]:
    """
    Recalculate player identity from all analyzed games.
    
    This powers:
    - Memory tab in Lab
    - Coach context for personalized advice
    - Behavioral pattern detection
    """
    from services.player_identity import BlunderType, GamePhase as IdentityGamePhase
    
    current_time = datetime.now(timezone.utc)
    COLLECTION = "player_identities"
    
    # First, remove any duplicate identity documents
    duplicates = list(db[COLLECTION].find({"user_id": user_id}, {"_id": 1}))
    if len(duplicates) > 1:
        # Keep the first one, delete the rest
        for dup in duplicates[1:]:
            db[COLLECTION].delete_one({"_id": dup["_id"]})
        logger.info(f"Removed {len(duplicates)-1} duplicate identity documents for {user_id}")
    
    # Get ALL analyzed games for this user, ordered by analysis time
    games_with_analysis = list(db.game_analyses.aggregate([
        {"$lookup": {
            "from": "games",
            "localField": "game_id",
            "foreignField": "game_id",
            "as": "game_info"
        }},
        {"$unwind": "$game_info"},
        {"$match": {"game_info.user_id": user_id}},
        {"$sort": {"analyzed_at": 1}},  # Oldest first to replay in order
        {"$project": {
            "_id": 0,
            "game_id": 1,
            "result": "$game_info.result",
            "user_color": "$game_info.user_color",
            "stockfish_analysis": 1,
            "analyzed_at": 1
        }}
    ]))
    
    if not games_with_analysis:
        return {"status": "no_games", "games_processed": 0}
    
    # Recalculate from scratch
    identity = {
        "user_id": user_id,
        "games_analyzed": 0,
        "total_wins": 0,
        "total_losses": 0,
        "total_draws": 0,
        "consecutive_wins": 0,
        "consecutive_losses": 0,
        "current_streak": 0,
        "best_streak": 0,
        "current_rating": 1200,
        "peak_rating": 1200,
        "style_profile": {
            "primary_style": "developing",
            "confidence": 0.0,
            "tactical_tendency": 0.5,
            "positional_tendency": 0.5,
            "aggressive_tendency": 0.5,
            "defensive_tendency": 0.5
        },
        "blunder_taxonomy": {
            "by_type": {},
            "by_phase": {},
            "most_common_type": None,
            "worst_phase": None,
            "trend": "unknown",
            "total_blunders": 0  # Add this field for the UI
        },
        "behavioral_patterns": [],
        "recent_performance": [],
        "pattern_history": [],  # Clickable mistake history
        "recent_blunders": [],  # Recent mistakes for Memory tab
        "created_at": current_time.isoformat(),
        "updated_at": current_time.isoformat()
    }
    
    # Process each game in chronological order
    for game in games_with_analysis:
        result = game.get("result", "")
        user_color = game.get("user_color", "white")
        sf_analysis = game.get("stockfish_analysis", {})
        move_evals = sf_analysis.get("move_evaluations", [])
        
        # Determine if user won/lost/drew
        user_won = (result == "1-0" and user_color == "white") or (result == "0-1" and user_color == "black")
        user_lost = (result == "0-1" and user_color == "white") or (result == "1-0" and user_color == "black")
        
        identity["games_analyzed"] += 1
        
        if user_won:
            identity["total_wins"] += 1
            identity["consecutive_wins"] += 1
            identity["consecutive_losses"] = 0
            identity["current_streak"] = identity["consecutive_wins"]
        elif user_lost:
            identity["total_losses"] += 1
            identity["consecutive_losses"] += 1
            identity["consecutive_wins"] = 0
            identity["current_streak"] = -identity["consecutive_losses"]
        else:
            identity["total_draws"] += 1
            identity["consecutive_wins"] = 0
            identity["consecutive_losses"] = 0
            identity["current_streak"] = 0
        
        # Track best streak
        if identity["consecutive_wins"] > identity["best_streak"]:
            identity["best_streak"] = identity["consecutive_wins"]
        
        # Analyze blunders
        blunder_types = identity["blunder_taxonomy"]["by_type"]
        blunder_phases = identity["blunder_taxonomy"]["by_phase"]
        game_id = game.get("game_id")
        analyzed_at = game.get("analyzed_at", current_time.isoformat())
        
        for move_eval in move_evals:
            cp_loss = abs(move_eval.get("cp_loss", 0))
            if cp_loss >= 100:  # Significant mistake
                move_num = move_eval.get("move_number", 0)
                category = move_eval.get("category", "tactical_error")
                move_played = move_eval.get("move", "")
                best_move = move_eval.get("best_move", "")
                
                # Determine phase
                if move_num <= 12:
                    phase = "opening"
                elif move_num <= 30:
                    phase = "middlegame"
                else:
                    phase = "endgame"
                
                # Update counts
                blunder_types[category] = blunder_types.get(category, 0) + 1
                blunder_phases[phase] = blunder_phases.get(phase, 0) + 1
                identity["blunder_taxonomy"]["total_blunders"] = identity["blunder_taxonomy"].get("total_blunders", 0) + 1
                
                # Add to pattern history (for clickable links in Memory tab)
                pattern_entry = {
                    "game_id": game_id,
                    "move_number": move_num,
                    "pattern_type": category,
                    "phase": phase,
                    "cp_loss": cp_loss,
                    "move_played": move_played,
                    "best_move": best_move,
                    "date": analyzed_at if isinstance(analyzed_at, str) else analyzed_at.isoformat() if analyzed_at else current_time.isoformat()
                }
                identity["pattern_history"].append(pattern_entry)
                
                # Also track recent blunders (last 20)
                if len(identity["recent_blunders"]) < 20:
                    identity["recent_blunders"].append(pattern_entry)
        
        # Track recent performance (last 10 games)
        perf_entry = {
            "game_id": game.get("game_id"),
            "result": "win" if user_won else "loss" if user_lost else "draw",
            "accuracy": sf_analysis.get("accuracy", 0)
        }
        identity["recent_performance"].append(perf_entry)
        if len(identity["recent_performance"]) > 10:
            identity["recent_performance"] = identity["recent_performance"][-10:]
    
    # Calculate most common blunder type and worst phase
    if blunder_types:
        identity["blunder_taxonomy"]["most_common_type"] = max(blunder_types, key=blunder_types.get)
    if blunder_phases:
        identity["blunder_taxonomy"]["worst_phase"] = max(blunder_phases, key=blunder_phases.get)
    
    # Calculate style profile with confidence based on games analyzed
    games_count = identity["games_analyzed"]
    if games_count >= 20:
        identity["style_profile"]["confidence"] = 0.9
        identity["style_profile"]["primary_style"] = _determine_playing_style(identity, games_with_analysis)
    elif games_count >= 10:
        identity["style_profile"]["confidence"] = 0.6
        identity["style_profile"]["primary_style"] = _determine_playing_style(identity, games_with_analysis)
    elif games_count >= 5:
        identity["style_profile"]["confidence"] = 0.3
        identity["style_profile"]["primary_style"] = "developing"
    else:
        identity["style_profile"]["confidence"] = 0.1
        identity["style_profile"]["primary_style"] = "developing"
    
    # Trim pattern_history to last 100 entries
    if len(identity["pattern_history"]) > 100:
        identity["pattern_history"] = identity["pattern_history"][-100:]
    
    # Detect behavioral patterns
    identity["behavioral_patterns"] = detect_behavioral_patterns(identity, games_with_analysis)
    
    identity["updated_at"] = current_time.isoformat()
    
    # Upsert the identity
    db[COLLECTION].update_one(
        {"user_id": user_id},
        {"$set": identity},
        upsert=True
    )
    
    return {
        "status": "refreshed",
        "games_processed": len(games_with_analysis),
        "consecutive_wins": identity["consecutive_wins"],
        "consecutive_losses": identity["consecutive_losses"],
        "total_record": f"{identity['total_wins']}-{identity['total_losses']}-{identity['total_draws']}"
    }


def _determine_playing_style(identity: Dict, games: List[Dict]) -> str:
    """
    Determine primary playing style based on game patterns.
    """
    blunder_phases = identity.get("blunder_taxonomy", {}).get("by_phase", {})
    blunder_types = identity.get("blunder_taxonomy", {}).get("by_type", {})
    
    opening_blunders = blunder_phases.get("opening", 0)
    middlegame_blunders = blunder_phases.get("middlegame", 0)
    endgame_blunders = blunder_phases.get("endgame", 0)
    total_phase_blunders = opening_blunders + middlegame_blunders + endgame_blunders
    
    tactical_errors = blunder_types.get("tactical_error", 0) + blunder_types.get("missed_tactic", 0)
    positional_errors = blunder_types.get("positional_error", 0) + blunder_types.get("strategic_error", 0)
    total_type_errors = tactical_errors + positional_errors
    
    # Determine style based on where/how they make mistakes
    if total_type_errors > 10:
        if tactical_errors > positional_errors * 1.5:
            return "positional"  # They avoid tactical errors, so they're positional
        elif positional_errors > tactical_errors * 1.5:
            return "tactical"  # They avoid positional errors, so they're tactical
    
    # Check phase strength
    if total_phase_blunders > 10:
        if opening_blunders < middlegame_blunders and opening_blunders < endgame_blunders:
            return "solid"  # Good opening prep
        elif endgame_blunders < opening_blunders and endgame_blunders < middlegame_blunders:
            return "technical"  # Good endgame technique
    
    # Check win rate for aggressive vs defensive
    wins = identity.get("total_wins", 0)
    losses = identity.get("total_losses", 0)
    total_decisive = wins + losses
    
    if total_decisive > 10:
        win_rate = wins / total_decisive if total_decisive > 0 else 0.5
        if win_rate > 0.6:
            return "aggressive"
        elif win_rate < 0.4:
            return "defensive"
    
    return "balanced"


def detect_behavioral_patterns(identity: Dict, games: List[Dict]) -> List[Dict]:
    """
    Detect behavioral patterns from game history.
    """
    patterns = []
    
    # Check for consecutive losses pattern
    if identity.get("consecutive_losses", 0) >= 2:
        patterns.append({
            "pattern": "losing_streak",
            "description": f"Currently on a {identity['consecutive_losses']} game losing streak",
            "frequency": identity["consecutive_losses"],
            "severity": "high" if identity["consecutive_losses"] >= 3 else "medium",
            "recommendation": "Take a break, review recent games, focus on fundamentals"
        })
    
    # Check for recurring blunder types
    blunder_types = identity.get("blunder_taxonomy", {}).get("by_type", {})
    total_blunders = sum(blunder_types.values())
    
    for blunder_type, count in blunder_types.items():
        if total_blunders > 0 and count / total_blunders > 0.3:  # More than 30% of blunders
            patterns.append({
                "pattern": blunder_type,
                "description": f"Recurring issue: {blunder_type.replace('_', ' ')}",
                "frequency": count,
                "severity": "high" if count >= 5 else "medium",
                "recommendation": f"Focus on avoiding {blunder_type.replace('_', ' ')} mistakes"
            })
    
    # Check for phase-specific weakness
    blunder_phases = identity.get("blunder_taxonomy", {}).get("by_phase", {})
    total_phase_blunders = sum(blunder_phases.values())
    
    for phase, count in blunder_phases.items():
        if total_phase_blunders > 0 and count / total_phase_blunders > 0.5:  # More than 50% in one phase
            patterns.append({
                "pattern": f"{phase}_weakness",
                "description": f"Most mistakes happen in the {phase}",
                "frequency": count,
                "severity": "medium",
                "recommendation": f"Study {phase} strategies and patterns"
            })
    
    return patterns


def refresh_journey_stats(db, user_id: str) -> Dict[str, Any]:
    """
    Recalculate journey statistics for the Journey page.
    """
    current_time = datetime.now(timezone.utc)
    
    # Get all games for this user
    games = list(db.games.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "played_at": 1, "imported_at": 1}
    ))
    
    # Get analyzed game count
    analyzed_count = db.game_analyses.count_documents({
        "game_id": {"$in": [g["game_id"] for g in games]}
    })
    
    # Calculate stats
    total_games = len(games)
    wins = sum(1 for g in games if _is_win(g))
    losses = sum(1 for g in games if _is_loss(g))
    draws = total_games - wins - losses
    
    # Journey data document
    journey_data = {
        "user_id": user_id,
        "total_games": total_games,
        "analyzed_games": analyzed_count,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": round(wins / total_games * 100, 1) if total_games > 0 else 0,
        "updated_at": current_time.isoformat()
    }
    
    # Update or create journey stats
    db.journey_stats.update_one(
        {"user_id": user_id},
        {"$set": journey_data},
        upsert=True
    )
    
    return {
        "status": "refreshed",
        "total_games": total_games,
        "analyzed_games": analyzed_count,
        "record": f"{wins}-{losses}-{draws}"
    }


def refresh_player_profile(db, user_id: str) -> Dict[str, Any]:
    """
    Recalculate player profile for the Dashboard.
    
    This powers:
    - Biggest weakness card
    - Progress stats
    - Blind spots
    """
    current_time = datetime.now(timezone.utc)
    
    # Get recent analyzed games (last 20)
    recent_analyses = list(db.game_analyses.aggregate([
        {"$lookup": {
            "from": "games",
            "localField": "game_id",
            "foreignField": "game_id",
            "as": "game_info"
        }},
        {"$unwind": "$game_info"},
        {"$match": {"game_info.user_id": user_id}},
        {"$sort": {"analyzed_at": -1}},
        {"$limit": 20},
        {"$project": {
            "_id": 0,
            "game_id": 1,
            "stockfish_analysis": 1
        }}
    ]))
    
    if not recent_analyses:
        return {"status": "no_data"}
    
    # Calculate aggregated stats
    total_mistakes = 0
    total_blunders = 0
    total_inaccuracies = 0
    mistake_types = {}
    accuracies = []
    
    for analysis in recent_analyses:
        sf = analysis.get("stockfish_analysis", {})
        accuracies.append(sf.get("accuracy", 0))
        total_mistakes += sf.get("mistakes", 0)
        total_blunders += sf.get("blunders", 0)
        total_inaccuracies += sf.get("inaccuracies", 0)
        
        # Count mistake types
        for move_eval in sf.get("move_evaluations", []):
            if move_eval.get("cp_loss", 0) >= 100:
                category = move_eval.get("category", "other")
                mistake_types[category] = mistake_types.get(category, 0) + 1
    
    game_count = len(recent_analyses)
    avg_accuracy = sum(accuracies) / game_count if game_count > 0 else 0
    errors_per_game = (total_mistakes + total_blunders + total_inaccuracies) / game_count if game_count > 0 else 0
    
    # Find biggest weakness
    biggest_weakness = max(mistake_types, key=mistake_types.get) if mistake_types else None
    
    profile = {
        "user_id": user_id,
        "games_analyzed": game_count,
        "average_accuracy": round(avg_accuracy, 1),
        "errors_per_game": round(errors_per_game, 1),
        "biggest_weakness": biggest_weakness,
        "mistake_breakdown": mistake_types,
        "total_blunders": total_blunders,
        "total_mistakes": total_mistakes,
        "total_inaccuracies": total_inaccuracies,
        "updated_at": current_time.isoformat()
    }
    
    db.player_profiles.update_one(
        {"user_id": user_id},
        {"$set": profile},
        upsert=True
    )
    
    return {
        "status": "refreshed",
        "games_analyzed": game_count,
        "avg_accuracy": round(avg_accuracy, 1),
        "biggest_weakness": biggest_weakness
    }


def ensure_thinking_scores(db, user_id: str) -> Dict[str, Any]:
    """
    Ensure all analyzed games have thinking scores calculated.
    """
    from services.thinking_score import calculate_game_thinking_scores
    
    # Get games that have analysis but no thinking score
    games_with_analysis = list(db.game_analyses.aggregate([
        {"$lookup": {
            "from": "games",
            "localField": "game_id",
            "foreignField": "game_id",
            "as": "game_info"
        }},
        {"$unwind": "$game_info"},
        {"$match": {"game_info.user_id": user_id}},
        {"$project": {
            "_id": 0,
            "game_id": 1,
            "user_color": "$game_info.user_color",
            "stockfish_analysis": 1
        }}
    ]))
    
    # Get existing thinking scores
    existing_scores = set(
        doc["game_id"] for doc in db.thinking_scores.find(
            {"user_id": user_id},
            {"_id": 0, "game_id": 1}
        )
    )
    
    # Calculate missing scores
    calculated = 0
    for game in games_with_analysis:
        game_id = game.get("game_id")
        if game_id not in existing_scores:
            sf = game.get("stockfish_analysis", {})
            move_evals = sf.get("move_evaluations", [])
            user_color = game.get("user_color", "white")
            
            analysis_for_score = {
                "game_id": game_id,
                "move_evaluations": move_evals,
                "critical_moments": []
            }
            
            scores = calculate_game_thinking_scores(analysis_for_score, user_color)
            scores["user_id"] = user_id
            scores["game_id"] = game_id
            
            db.thinking_scores.update_one(
                {"user_id": user_id, "game_id": game_id},
                {"$set": scores},
                upsert=True
            )
            calculated += 1
    
    return {
        "status": "ensured",
        "total_games": len(games_with_analysis),
        "scores_calculated": calculated,
        "already_had_scores": len(existing_scores)
    }


def _is_win(game: Dict) -> bool:
    """Check if the game was a win for the user."""
    result = game.get("result", "")
    color = game.get("user_color", "white")
    return (result == "1-0" and color == "white") or (result == "0-1" and color == "black")


def _is_loss(game: Dict) -> bool:
    """Check if the game was a loss for the user."""
    result = game.get("result", "")
    color = game.get("user_color", "white")
    return (result == "0-1" and color == "white") or (result == "1-0" and color == "black")

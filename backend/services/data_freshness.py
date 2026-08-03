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
from typing import Dict, List, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Shared cognitive_gap groupings for the tactical/positional axis — used by
# both _compute_style_tendencies (tendency scores) and _determine_playing_style
# (primary_style label), so the two stay consistent with each other.
_TACTICAL_GAPS = {"missed_tactic", "tactical_oversight", "calculation_depth", "piece_safety"}
_POSITIONAL_GAPS = {"pawn_structure", "piece_activity", "opening_knowledge", "endgame_technique"}


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
            # 2026-08-03 fix: white_player/black_player were already being
            # joined in by the $lookup above and then discarded right here,
            # before the per-game loop ever saw them — the reason every
            # pattern_history entry's "opponent" defaulted to "unknown"
            # despite the real name being one join away. See
            # docs/caption_pipeline_architecture_reference.md §7.
            "white_player": "$game_info.white_player",
            "black_player": "$game_info.black_player",
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
        # Real opponent name, now that white_player/black_player survive
        # the $project above — same accessor pattern as routes/games.py.
        opponent_name = (
            game.get("black_player") if user_color == "white" else game.get("white_player")
        ) or "unknown"
        
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
                # "category" was never a real field on move_eval dicts (the
                # real field is "cognitive_gap") — this silently defaulted
                # EVERY significant mistake, for every user, to the literal
                # string "tactical_error", which is why blunder_taxonomy.by_type
                # was always exactly {"tactical_error": N} with nothing else.
                category = move_eval.get("cognitive_gap") or "tactical_error"
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
                # description reuses the real, already-verified caption text
                # from analysis (not fabricated here) — falls back to a
                # plain phase+pattern sentence only when a caption is
                # genuinely absent (older analyses predating the caption
                # pipeline).
                description = move_eval.get("caption") or f"{category.replace('_', ' ').capitalize()} in the {phase}."
                pattern_entry = {
                    "game_id": game_id,
                    "move_number": move_num,
                    "pattern_type": category,
                    "phase": phase,
                    "cp_loss": cp_loss,
                    "move_played": move_played,
                    "best_move": best_move,
                    "opponent": opponent_name,
                    "description": description,
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
    
    # Compute the 4 style tendencies from the cognitive_gap distribution
    # across this user's analyzed games. Previously these were hardcoded
    # to 0.5/0.5/0.5/0.5 (literal placeholder for every user). Now they
    # reflect what the user actually does well / badly. Only fills in if
    # we have enough games to be meaningful (>=5).
    games_count = identity["games_analyzed"]
    if games_count >= 5:
        identity["style_profile"].update(
            _compute_style_tendencies(games_with_analysis)
        )

    # Calculate style profile with confidence based on games analyzed.
    # primary_style is derived FROM the tendencies above (not a separate
    # blunder-taxonomy computation) so the label can never contradict the
    # numeric scores shown next to it — e.g. primary_style="positional"
    # while aggressive_tendency=0.83, which is what the old two-computation
    # version could and did produce.
    if games_count >= 10:
        identity["style_profile"]["confidence"] = 0.9 if games_count >= 20 else 0.6
        identity["style_profile"]["primary_style"] = _determine_playing_style(identity["style_profile"])
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


def _compute_style_tendencies(games: List[Dict]) -> Dict[str, float]:
    """Compute the 4 style tendency dimensions (0..1) directly from move data.

    REVISED after the v1 calculation failed the per-claim verifier
    (21/45 users had claimed_aggressive=True but were below cohort median
    on brilliants+sacrifices). Root cause: v1 used cct_creates_threat as
    the aggression signal, which doesn't correlate with the brilliant-move
    rate that actually measures aggressive play.

    v2 logic — directly measured signals only:
      aggressive_tendency = brilliants_plus_sacrifices_rate ranked across the
                            cohort. We need the cohort median to map this to
                            0..1, but here we don't have it — so we report the
                            raw per-1k rate, and a downstream service maps to
                            tendency by percentile rank.

      To preserve the existing API shape we return a value in [0,1] where:
        - 0.5 if not enough data
        - 1.0 if aggression_rate is in the top 10% of typical chess players
                (using ~10 brilliant+sacrifice per 100 user moves as the ref)
        - 0.0 if rate is essentially zero
      The downstream cohort-aware service can override this with true ranks.
    """
    aggressive_count = 0  # brilliant_moves + sacrifices (direct measures)
    tactical_signals = 0  # weakness counts
    positional_signals = 0
    defensive_signals = 0
    total_user_moves = 0

    for g in games:
        sf = g.get("stockfish_analysis") or {}
        aggressive_count += (sf.get("brilliant_moves", 0) or 0)
        aggressive_count += (sf.get("sacrifices", 0) or 0)
        for mv in (sf.get("move_evaluations") or []):
            if mv.get("is_opponent_move"):
                continue
            total_user_moves += 1
            gap = mv.get("cognitive_gap")
            if gap in _TACTICAL_GAPS:
                tactical_signals += 1
            elif gap in _POSITIONAL_GAPS:
                positional_signals += 1
            if gap == "king_safety":
                defensive_signals += 1

    if total_user_moves == 0:
        return {
            "tactical_tendency": 0.5,
            "positional_tendency": 0.5,
            "aggressive_tendency": 0.5,
            "defensive_tendency": 0.5,
        }

    # tactical vs positional axis: which kind of mistake do they make MORE of?
    tp_total = tactical_signals + positional_signals
    if tp_total == 0:
        tac = 0.5
    else:
        # More tactical mistakes = LESS tactical tendency.
        tac = round(positional_signals / tp_total, 2)
    pos = round(1.0 - tac, 2)

    # Aggressive axis (v2): rate of brilliants+sacrifices per 100 user moves
    # mapped to 0..1 with 10 per 100 as the upper anchor.
    agg_per_100 = (aggressive_count / total_user_moves) * 100
    agg = max(0.0, min(1.0, round(agg_per_100 / 10.0, 2)))
    defv = round(1.0 - agg, 2)

    return {
        "tactical_tendency": tac,
        "positional_tendency": pos,
        "aggressive_tendency": agg,
        "defensive_tendency": defv,
        "aggressive_per_100_moves": round(agg_per_100, 2),  # diagnostic
    }


def _determine_playing_style(style_profile: Dict) -> str:
    """
    Derive the single primary_style label FROM the tendency scores that
    _compute_style_tendencies already computed for this refresh (call this
    only after that ran). Two independent axes, each already 0..1 and
    complementary by construction (positional = 1 - tactical, defensive =
    1 - aggressive):
      - tactical <-> positional (which kind of mistake dominates)
      - aggressive <-> defensive (brilliants+sacrifices rate)

    Deliberately NOT a separate recomputation from blunder_taxonomy/win-rate
    (the old version) — that produced labels that could directly contradict
    the tendency scores shown right next to them (e.g. primary_style=
    "positional" while aggressive_tendency=0.83). Picks whichever axis has
    the stronger (more-than-noise) signal for this player; "balanced" when
    neither axis is differentiated enough to call.
    """
    agg = style_profile.get("aggressive_tendency", 0.5)
    tac = style_profile.get("tactical_tendency", 0.5)

    agg_strength = abs(agg - 0.5)
    tac_strength = abs(tac - 0.5)

    # Neither axis has a real signal yet — don't force a label.
    if max(agg_strength, tac_strength) < 0.1:
        return "balanced"

    if agg_strength >= tac_strength:
        return "aggressive" if agg > 0.5 else "defensive"
    return "tactical" if tac > 0.5 else "positional"


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
        
        # Count mistake types. Was move_eval.get("category", "other") — that
        # field never existed on any real move_evaluations doc (0/24 keys on
        # a live sample; the real field is cognitive_gap), so biggest_weakness
        # was always exactly the string "other" for every user. Confirmed
        # zero live readers of biggest_weakness/mistake_breakdown either way
        # (docs/player_profiles_consolidation_scope.md), but fixing the
        # field name while touching this function regardless.
        for move_eval in sf.get("move_evaluations", []):
            if move_eval.get("cp_loss", 0) >= 100:
                # cognitive_gap can be explicitly None (suppressed low-
                # confidence categories, see analysis_interpreter.py's
                # _precedence_adjust) — .get(key, default) only applies
                # the default when the key is ABSENT, not when it's None.
                category = move_eval.get("cognitive_gap") or "other"
                mistake_types[category] = mistake_types.get(category, 0) + 1

    game_count = len(recent_analyses)
    avg_accuracy = sum(accuracies) / game_count if game_count > 0 else 0
    errors_per_game = (total_mistakes + total_blunders + total_inaccuracies) / game_count if game_count > 0 else 0

    # Find biggest weakness
    biggest_weakness = max(mistake_types, key=mistake_types.get) if mistake_types else None

    # 2026-07-25: total_blunders/total_mistakes/total_inaccuracies used to
    # collide with analysis_worker.py's update_player_profile_sync, which
    # writes the SAME field names as career-cumulative totals. This function
    # runs immediately after that one on every analyzed game
    # (refresh_all_user_data), so the career values were silently overwritten
    # by this function's last-20-games sum every single time — the "total_"
    # names implied career, the stored value was actually a 20-game window.
    # Renamed to recent_20_* so both survive; nothing reads the plain
    # total_blunders/total_mistakes names expecting THIS function's
    # semantic (verified: only services/chess_understanding.py reads them,
    # and it now correctly gets the stable career value analysis_worker.py
    # owns, per docs/player_profiles_consolidation_scope.md Option B).
    profile = {
        "user_id": user_id,
        "games_analyzed": game_count,
        "average_accuracy": round(avg_accuracy, 1),
        "errors_per_game": round(errors_per_game, 1),
        "biggest_weakness": biggest_weakness,
        "mistake_breakdown": mistake_types,
        "recent_20_total_blunders": total_blunders,
        "recent_20_total_mistakes": total_mistakes,
        "recent_20_total_inaccuracies": total_inaccuracies,
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

"""
Home Dashboard & Data Freshness Routes
=======================================

Handles:
- Dashboard statistics (dashboard-stats)
- Game summary migration
- Home dashboard V2 (last battle, chess DNA, patterns, streak)
- Pattern prescription for home page
- Data freshness (refresh, status)
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import re
import os
import logging

from routes.auth import get_current_user, User
from blunder_intelligence_service import estimate_rating_impact

logger = logging.getLogger(__name__)

# Create router for home/dashboard endpoints
router = APIRouter(tags=["Home & Dashboard"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for home routes"""
    global db
    db = database


# ==================== DASHBOARD STATS ====================

@router.get("/dashboard-stats")
async def get_dashboard_stats(user: User = Depends(get_current_user)):
    """Get dashboard statistics including player profile for the current user"""
    total_games = await db.games.count_documents({"user_id": user.user_id})

    # Use game_analyses count as the source of truth for analyzed games
    # (more accurate than games.is_analyzed which can get out of sync)
    analyzed_games = await db.game_analyses.count_documents({"user_id": user.user_id})

    # Count games in queue / retry / failed states
    active_queued_games = await db.analysis_queue.count_documents({
        "user_id": user.user_id,
        "status": {"$in": ["pending", "processing"]}
    })
    await db.analysis_queue.count_documents({
        "user_id": user.user_id,
        "status": {"$in": ["pending", "processing", "failed"]}
    })

    # Get player profile for coaching context
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )

    # Get top weaknesses from profile (with decay) instead of raw patterns
    top_weaknesses = []
    if profile:
        top_weaknesses = profile.get("top_weaknesses", [])[:5]
    else:
        # Fallback to legacy patterns if no profile
        patterns = await db.mistake_patterns.find(
            {"user_id": user.user_id},
            {"_id": 0}
        ).sort("occurrences", -1).to_list(5)
        top_weaknesses = patterns

    # Get queued game IDs FIRST (so we can include them in the query)
    queue_items = await db.analysis_queue.find(
        {"user_id": user.user_id, "status": {"$in": ["pending", "processing", "failed"]}},
        {
            "_id": 0,
            "game_id": 1,
            "status": 1,
            "queued_at": 1,
            "started_at": 1,
            "retry_count": 1,
            "last_error": 1,
            "last_error_at": 1,
            "retrying": 1,
            "failed_at": 1,
        }
    ).to_list(100)
    queued_game_map = {q["game_id"]: q for q in queue_items}
    queued_game_ids = set(queued_game_map.keys())

    # Get recent games (up to 100)
    all_games = await db.games.find(
        {"user_id": user.user_id},
        {
            "_id": 0,
            "game_id": 1,
            "white_player": 1,
            "black_player": 1,
            "user_color": 1,
            "result": 1,
            "platform": 1,
            "opening": 1,
            "is_analyzed": 1,
            "analysis_status": 1,
            "imported_at": 1,
            "pgn": 1  # Need PGN to extract player names if not stored
        }
    ).sort("imported_at", -1).to_list(100)

    # Also fetch any queued games that might not be in the top 100
    all_game_ids = {g["game_id"] for g in all_games}
    missing_queued_ids = queued_game_ids - all_game_ids

    if missing_queued_ids:
        missing_games = await db.games.find(
            {"game_id": {"$in": list(missing_queued_ids)}, "user_id": user.user_id},
            {
                "_id": 0,
                "game_id": 1,
                "white_player": 1,
                "black_player": 1,
                "user_color": 1,
                "result": 1,
                "platform": 1,
                "opening": 1,
                "is_analyzed": 1,
                "analysis_status": 1,
                "imported_at": 1,
                "pgn": 1
            }
        ).to_list(100)
        all_games.extend(missing_games)

    # Categorize games
    analyzed_list = []
    in_queue_list = []
    not_analyzed_list = []  # NEW: Games that haven't been analyzed
    recent_games = []  # For backward compatibility, top 10

    # Enrich games with accuracy from analysis and extract player names from PGN
    for game in all_games:
        # Extract player names from PGN if not already present
        pgn = game.get("pgn", "")
        if pgn:
            if not game.get("white_player") or game.get("white_player") in ["Unknown", "?"]:
                white_match = re.search(r'\[White "([^"]+)"\]', pgn)
                if white_match:
                    game["white_player"] = white_match.group(1)
            if not game.get("black_player") or game.get("black_player") in ["Unknown", "?"]:
                black_match = re.search(r'\[Black "([^"]+)"\]', pgn)
                if black_match:
                    game["black_player"] = black_match.group(1)

            # Also extract ratings from PGN
            white_elo_match = re.search(r'\[WhiteElo "(\d+)"\]', pgn)
            black_elo_match = re.search(r'\[BlackElo "(\d+)"\]', pgn)
            if white_elo_match:
                game["white_rating"] = int(white_elo_match.group(1))
            if black_elo_match:
                game["black_rating"] = int(black_elo_match.group(1))

        # Don't send PGN to frontend (too large)
        if "pgn" in game:
            del game["pgn"]

        game_id = game.get("game_id")

        # Determine analysis status - CHECK QUEUE FIRST (priority)
        if game_id in queued_game_ids:
            # Game is in queue - show it there regardless of is_analyzed flag
            queue_info = queued_game_map.get(game_id, {})
            game["analysis_status"] = queue_info.get("status", "pending")
            game["queued_at"] = queue_info.get("queued_at")
            game["started_at"] = queue_info.get("started_at")
            game["retry_count"] = queue_info.get("retry_count", 0)
            game["last_error"] = queue_info.get("last_error")
            game["last_error_at"] = queue_info.get("last_error_at")
            game["retrying"] = queue_info.get("retrying", False)
            game["failed_at"] = queue_info.get("failed_at")
            in_queue_list.append(game)
        elif game.get("is_analyzed"):
            analysis = await db.game_analyses.find_one(
                {"game_id": game_id, "user_id": user.user_id},
                {"_id": 0, "stockfish_analysis.accuracy": 1, "stockfish_analysis.move_evaluations": 1,
                 "stockfish_analysis.blunders": 1, "stockfish_analysis.mistakes": 1,
                 "game_summary": 1}
            )
            if analysis:
                sf = analysis.get("stockfish_analysis", {})
                accuracy = sf.get("accuracy", 0)
                move_evals = sf.get("move_evaluations", [])
                game["accuracy"] = accuracy
                game["blunders"] = sf.get("blunders", 0)
                game["mistakes"] = sf.get("mistakes", 0)

                # Include rich game summary if available
                game_summary = analysis.get("game_summary")
                if game_summary:
                    game["summary"] = game_summary.get("display", {})
                    game["key_mistakes"] = game_summary.get("key_mistakes", [])[:2]  # Top 2 for list
                    game["problem_phase"] = game_summary.get("problem_phase")
                    game["tags"] = game_summary.get("tags", [])

                # Set opponent name for display
                user_color = game.get("user_color", "white")
                if user_color == "white":
                    game["opponent"] = game.get("black_player", "Opponent")
                else:
                    game["opponent"] = game.get("white_player", "Opponent")

                # If accuracy is 0 and no move evaluations, treat as NOT analyzed (incomplete analysis)
                if accuracy == 0 and len(move_evals) == 0:
                    game["analysis_status"] = "not_analyzed"
                    not_analyzed_list.append(game)
                else:
                    game["analysis_status"] = "analyzed"
                    analyzed_list.append(game)
            else:
                # No analysis record found - treat as not analyzed
                game["analysis_status"] = "not_analyzed"
                not_analyzed_list.append(game)
        else:
            game["analysis_status"] = "not_analyzed"
            not_analyzed_list.append(game)  # Add to not_analyzed list

    # Note: analyzed_games was already set correctly using game_analyses.count_documents()
    # The analyzed_list here only contains games from the recent 100 games query
    # which may not include all historically analyzed games

    # Build recent_games for backward compatibility (top 10 of all games)
    recent_games = all_games[:10]

    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "blunders": 1, "mistakes": 1, "best_moves": 1, "stockfish_analysis": 1}
    ).to_list(500)

    # Sum stats - check both top-level fields and stockfish_analysis (prefer stockfish_analysis)
    total_blunders = 0
    total_mistakes = 0
    total_best_moves = 0

    for a in analyses:
        sf = a.get('stockfish_analysis', {})
        # Prefer Stockfish analysis if available, otherwise use top-level
        total_blunders += sf.get('blunders', 0) or a.get('blunders', 0)
        total_mistakes += sf.get('mistakes', 0) or a.get('mistakes', 0)
        total_best_moves += sf.get('best_moves', 0) or a.get('best_moves', 0)

    # Build response with profile data
    response = {
        "total_games": total_games,
        "analyzed_games": analyzed_games,
        "queued_games": len(in_queue_list),
        "active_queue_games": active_queued_games,
        "not_analyzed_games": len(not_analyzed_list),  # NEW: count of unanalyzed games
        "top_weaknesses": top_weaknesses,
        "recent_games": recent_games,  # Backward compatibility
        "analyzed_list": analyzed_list,  # Only analyzed games
        "in_queue_list": in_queue_list,  # Games currently being analyzed
        "not_analyzed_list": not_analyzed_list,  # NEW: Games that need analysis
        "stats": {
            "total_blunders": total_blunders,
            "total_mistakes": total_mistakes,
            "total_best_moves": total_best_moves
        }
    }

    # Add rating impact estimate
    if len(analyses) >= 5:
        rating_impact = estimate_rating_impact(analyses)
        response["rating_impact"] = rating_impact

    # Add profile summary if available
    if profile:
        response["profile_summary"] = {
            "estimated_level": profile.get("estimated_level", "intermediate"),
            "estimated_elo": profile.get("estimated_elo", 1200),
            "improvement_trend": profile.get("improvement_trend", "stuck"),
            "strengths": profile.get("strengths", [])[:3],
            "learning_style": profile.get("learning_style", "concise"),
            "coaching_tone": profile.get("coaching_tone", "encouraging"),
            "challenges_solved": profile.get("challenges_solved", 0),
            "challenges_attempted": profile.get("challenges_attempted", 0)
        }

    return response


@router.post("/migrate-game-summaries")
async def migrate_game_summaries(user: User = Depends(get_current_user)):
    """
    Migrate existing games to include rich summaries.
    Call this once to backfill summaries for games that have V5 data.
    """
    try:
        from services.game_summary_service import migrate_existing_summaries
        stats = await migrate_existing_summaries(db, user.user_id, limit=50)
        return {
            "success": True,
            "message": f"Migrated {stats['updated']} games",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return {"success": False, "error": str(e)}


# ==================== HOME DASHBOARD V2 ====================

@router.get("/home/dashboard-v2")
async def get_home_dashboard_v2(user: User = Depends(get_current_user)):
    """
    V2 Home Dashboard — everything the reimagined home page needs in one call.
    Returns: last battle (critical position + FEN), chess DNA, #1 pattern to fix, contextual action.
    """
    from services.game_coach_summary import compute_game_summary, compute_game_memory

    result = {
        "last_battle": None,
        "chess_dna": None,
        "one_thing_to_fix": None,
        "context_action": None,
        "accuracy": 0,
        "games_analyzed": 0,
    }

    try:
        # Get last analyzed game
        last_game = await db.games.find_one(
            {"user_id": user.user_id, "is_analyzed": True},
            {"_id": 0}
        , sort=[("imported_at", -1)])

        if not last_game:
            result["context_action"] = {"type": "import", "label": "Import your first game", "href": "/import"}
            return result

        game_id = last_game.get("game_id")
        user_color = last_game.get("user_color", "white")
        game_result = last_game.get("result", "")
        pgn = last_game.get("pgn", "")
        elo_tag = "WhiteElo" if user_color == "white" else "BlackElo"
        m = re.search(rf'\[{elo_tag} "(\d+)"\]', pgn)
        user_rating = int(m.group(1)) if m else 0

        # Get analysis
        analysis = await db.game_analyses.find_one(
            {"game_id": game_id, "user_id": user.user_id},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1}
        )

        if analysis:
            evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])

            # Find the critical moment (worst user move)
            if evals:
                user_is_white = user_color == "white"
                user_moves = []
                for i, ev in enumerate(evals):
                    is_user = (i % 2 == 0 and user_is_white) or (i % 2 == 1 and not user_is_white)
                    if is_user and ev.get("cp_loss", 0) >= 100:
                        user_moves.append(ev)

                if user_moves:
                    worst = max(user_moves, key=lambda x: x.get("cp_loss", 0))
                    result["last_battle"] = {
                        "game_id": game_id,
                        "opponent": last_game.get("opponent_name") or (last_game.get("white_player") if user_color == "black" else last_game.get("black_player")),
                        "result": game_result,
                        "user_color": user_color,
                        "fen": worst.get("fen_before", ""),
                        "your_move": worst.get("move_san") or worst.get("move", ""),
                        "best_move": worst.get("best_move", ""),
                        "cp_loss": worst.get("cp_loss", 0),
                        "move_number": worst.get("move_number", 0),
                        "opening": last_game.get("opening", ""),
                    }

                # Fallback: if no worst move found or no FEN, still show the game
                if not result["last_battle"]:
                    result["last_battle"] = {
                        "game_id": game_id,
                        "opponent": last_game.get("opponent_name") or (last_game.get("white_player") if user_color == "black" else last_game.get("black_player")),
                        "result": game_result,
                        "user_color": user_color,
                        "fen": "",
                        "your_move": "",
                        "best_move": "",
                        "cp_loss": 0,
                        "move_number": 0,
                        "opening": last_game.get("opening", ""),
                    }

                # Add behavioral data from analysis
                last_analysis = await db.game_analyses.find_one(
                    {"game_id": game_id, "user_id": user.user_id},
                    {"_id": 0, "coach_summary": 1, "decryption_v5_data.core_lesson": 1, "stockfish_analysis.move_evaluations": 1, "stockfish_analysis.brilliant_moves": 1, "stockfish_analysis.sacrifices": 1}
                )
                if last_analysis and result["last_battle"]:
                    cs = last_analysis.get("coach_summary", {}) or {}
                    dd = last_analysis.get("decryption_v5_data", {})
                    if isinstance(dd, list): dd = {}
                    cl = (dd or {}).get("core_lesson", {}) or {}
                    result["last_battle"]["behavior"] = cs.get("behavioral_insight") or cs.get("key_observation") or ""
                    result["last_battle"]["lesson_label"] = cl.get("short_label", "")

                    # Add brilliant/sacrifice data
                    sf = last_analysis.get("stockfish_analysis", {})
                    brilliant_count = sf.get("brilliant_moves", 0)
                    sacrifice_count = sf.get("sacrifices", 0)

                    # Also count from move evaluations if top-level stats not yet populated
                    if not brilliant_count:
                        me = sf.get("move_evaluations", [])
                        brilliant_count = sum(1 for e in me if e.get("is_brilliant"))
                        sacrifice_count = sum(1 for e in me if e.get("is_sacrifice"))

                    result["last_battle"]["brilliant_moves"] = brilliant_count
                    result["last_battle"]["sacrifices"] = sacrifice_count

                    # Override lesson_label for brilliant games
                    if brilliant_count > 0 and not result["last_battle"]["lesson_label"]:
                        result["last_battle"]["lesson_label"] = "Brilliant sacrifice" if sacrifice_count > 0 else "Brilliant play"

                # Compute summary + memory
                summary = compute_game_summary(evals, game_result, user_color, last_game.get("opening", ""), termination=last_game.get("termination", ""))
                memory = await compute_game_memory(db, user.user_id, summary, user_rating)

                result["chess_dna"] = {
                    "archetype": memory.get("identity", {}).get("archetype", "Developing"),
                    "before_line": memory.get("identity", {}).get("before_line", ""),
                    "after_line": memory.get("identity", {}).get("after_line", ""),
                    "diagnosis": summary.get("diagnosis", ""),
                    "root_cause": summary.get("root_cause", ""),
                }

                # Impact projection as the "one thing to fix"
                impact = memory.get("impact", {})
                if impact.get("estimated_rating_gain", 0) > 0:
                    result["one_thing_to_fix"] = {
                        "pattern": impact.get("pattern_name", ""),
                        "stat_line": impact.get("stat_line", ""),
                        "fix_line": impact.get("fix_line", ""),
                        "diff_line": impact.get("diff_line", ""),
                        "severity": impact.get("severity", ""),
                        "rating_gain": impact.get("estimated_rating_gain", 0),
                    }

        # Accuracy — compute from analyses if profile doesn't have it
        profile = await db.player_profiles.find_one({"user_id": user.user_id}, {"_id": 0})
        profile_accuracy = profile.get("average_accuracy", 0) if profile else 0
        if not profile_accuracy:
            # Fallback: compute from game_analyses
            acc_cursor = db.game_analyses.find(
                {"user_id": user.user_id, "stockfish_analysis.accuracy": {"$exists": True}},
                {"_id": 0, "stockfish_analysis.accuracy": 1}
            )
            accs = []
            async for a in acc_cursor:
                acc_val = a.get("stockfish_analysis", {}).get("accuracy")
                if acc_val and acc_val > 0:
                    accs.append(acc_val)
            profile_accuracy = sum(accs) / len(accs) if accs else 0
        result["accuracy"] = profile_accuracy

        # Games count
        result["games_analyzed"] = await db.games.count_documents({"user_id": user.user_id, "is_analyzed": True})
        result["games_imported"] = await db.games.count_documents({"user_id": user.user_id})

        # Contextual action
        user_won = (game_result == "1-0" and user_color == "white") or (game_result == "0-1" and user_color == "black")
        if not user_won and "1/2" not in game_result:
            result["context_action"] = {"type": "review_loss", "label": "Review this loss", "href": f"/game/{game_id}"}
        else:
            result["context_action"] = {"type": "play", "label": "Play another game", "href": "/play-with-coach"}

        # ── STREAK ──
        recent_games = await db.games.find(
            {"user_id": user.user_id, "is_analyzed": True},
            {"_id": 0, "result": 1, "user_color": 1}
        ).sort("imported_at", -1).limit(20).to_list(20)

        streak_type = None
        streak_count = 0
        for g in recent_games:
            res = g.get("result", "")
            uc = g.get("user_color", "white")
            won = (res == "1-0" and uc == "white") or (res == "0-1" and uc == "black")
            draw = "1/2" in res
            r = "W" if won else ("D" if draw else "L")
            if streak_type is None:
                streak_type = r
            if r == streak_type:
                streak_count += 1
            else:
                break

        result["streak"] = {"type": streak_type or "none", "count": streak_count}

        # ── PATTERNS (top 3 with trend) ──
        from services.pattern_memory_service import get_top_patterns
        patterns = await get_top_patterns(db, user.user_id, limit=3)
        result["patterns"] = [
            {
                "label": p.get("label", ""),
                "pattern_type": p.get("pattern_type", ""),
                "recent_count": p.get("recent_count", 0),
                "total_count": p.get("total_count", 0),
                "severity": p.get("severity", ""),
            }
            for p in patterns
        ]

        # ── TRAINING READINESS (puzzle count for top pattern) ──
        if patterns:
            top_pt = patterns[0].get("pattern_type", "")
            if top_pt:
                try:
                    puzzle_count = await db.community_training_positions.count_documents({"pattern_type": top_pt})
                    result["training_ready"] = {
                        "pattern": top_pt,
                        "label": patterns[0].get("label", ""),
                        "puzzles_available": puzzle_count,
                    }
                except Exception:
                    pass

        # ── REVIEW PROGRESS ──
        total_analyzed = await db.games.count_documents({"user_id": user.user_id, "is_analyzed": True})
        total_reviewed = await db.games.count_documents({"user_id": user.user_id, "is_analyzed": True, "reviewed": True})
        pending_review = total_analyzed - total_reviewed
        result["review_progress"] = {
            "total": total_analyzed,
            "reviewed": total_reviewed,
            "pending": pending_review,
        }

        # ── STRENGTH PROFILE ──
        try:
            strength = await db.player_strength_profiles.find_one(
                {"user_id": user.user_id}, {"_id": 0}
            )
            if strength:
                result["strength_profile"] = {
                    "overall_score": strength.get("overall_score", 0),
                    "overall_label": strength.get("overall_label", "emerging"),
                    "strongest": strength.get("strongest"),
                    "weakest": strength.get("weakest"),
                    "headline_stats": strength.get("headline_stats", {}),
                    "domains": {
                        k: {"score": v.get("score", 0), "label": v.get("label", "emerging")}
                        for k, v in (strength.get("domains") or {}).items()
                    },
                }
        except Exception as sp_err:
            logger.debug(f"Strength profile not available: {sp_err}")

    except Exception as e:
        logger.error(f"Home dashboard V2 error: {e}")

    return result


@router.get("/home/coach-home")
async def get_coach_home(user: User = Depends(get_current_user)):
    """
    Personalized home page — feels like opening a text from your coach.
    Combines: greeting, last session recap, current problem, today's plan.
    """
    user_id = user.user_id
    result = {}

    # ─── 1. GREETING + RELATIONSHIP ───
    try:
        memory = await db.coach_memory.find_one(
            {"user_id": user_id},
            {"_id": 0, "games_played": 1, "avg_accuracy": 1, "avg_blunders_per_game": 1,
             "recent_results": 1, "improvement_rate": 1}
        )
        games_together = memory.get("games_played", 0) if memory else 0
        avg_acc = memory.get("avg_accuracy", 0) if memory else 0
        recent_results = memory.get("recent_results", []) if memory else []

        # Accuracy improvement (compare first half vs second half of recent games)
        recent_analyses = await db.game_analyses.find(
            {"user_id": user_id},
            {"_id": 0, "stockfish_analysis.accuracy": 1, "stockfish_analysis.blunders": 1}
        ).sort("created_at", -1).limit(20).to_list(20)

        acc_improving = False
        acc_old = 0
        acc_new = 0
        if len(recent_analyses) >= 6:
            recent_5 = [a.get("stockfish_analysis", {}).get("accuracy", 0) for a in recent_analyses[:5]]
            older_5 = [a.get("stockfish_analysis", {}).get("accuracy", 0) for a in recent_analyses[-5:]]
            acc_new = sum(recent_5) / len(recent_5) if recent_5 else 0
            acc_old = sum(older_5) / len(older_5) if older_5 else 0
            acc_improving = acc_new > acc_old + 3

        # Also count completed coach sessions directly (for onboarding)
        coach_session_count = await db.coach_sessions.count_documents(
            {"user_id": user_id, "status": "completed"}
        )

        result["greeting"] = {
            "games_together": max(games_together, coach_session_count),
            "coach_sessions": coach_session_count,
            "avg_accuracy": round(avg_acc) if avg_acc else None,
            "improving": acc_improving,
            "acc_old": round(acc_old) if acc_old else None,
            "acc_new": round(acc_new) if acc_new else None,
            "recent_results": recent_results[-10:],
        }
    except Exception as e:
        logger.warning(f"[COACH-HOME] Greeting failed: {e}")

    # ─── 2. LAST COACH SESSION RECAP ───
    try:
        last_session = await db.coach_sessions.find_one(
            {"user_id": user_id, "status": "completed"},
            {"_id": 0, "session_id": 1, "result": 1, "user_color": 1,
             "opening_name": 1, "opening_to_teach": 1, "opening_branch": 1,
             "move_history": 1, "created_at": 1, "evaluations": 1,
             "opening_teaching_active": 1}
        , sort=[("created_at", -1)])

        if last_session:
            mh = last_session.get("move_history", [])
            user_moves = [m for m in mh if m.get("by") == "player"]
            total_moves = len(user_moves)

            # Find the worst blunder
            worst_blunder = None
            for m in user_moves:
                eb = m.get("eval_before")
                ea = m.get("eval_after")
                if eb is not None and ea is not None:
                    drop = abs(eb - ea)
                    if drop > 1.5 and (not worst_blunder or drop > worst_blunder["drop"]):
                        worst_blunder = {
                            "move": m.get("move"),
                            "move_number": mh.index(m) // 2 + 1,
                            "drop": drop,
                        }

            # Opening info
            opening_name = last_session.get("opening_name") or last_session.get("opening_to_teach", "")
            if opening_name:
                opening_name = opening_name.replace("_", " ").title()

            # Simple accuracy: count good moves
            good_moves = sum(1 for m in user_moves
                           if m.get("eval_before") is not None and m.get("eval_after") is not None
                           and abs(m["eval_before"] - m["eval_after"]) < 0.5)
            accuracy = round(good_moves / total_moves * 100) if total_moves > 0 else 0

            recap = {
                "result": last_session.get("result", "unknown"),
                "opening": opening_name,
                "branch": last_session.get("opening_branch"),
                "total_moves": total_moves,
                "accuracy": accuracy,
            }

            # Build the story
            result_word = {"win": "You won", "loss": "You lost", "draw": "It was a draw"}.get(
                last_session.get("result"), "Game finished"
            )

            story_parts = []
            if opening_name:
                branch_name = last_session.get("opening_branch", "").replace("_", " ").title()
                if branch_name:
                    story_parts.append(f"You played the {opening_name} — {branch_name} variation.")
                else:
                    story_parts.append(f"You played the {opening_name}.")

            if worst_blunder:
                story_parts.append(
                    f"Then blundered with {worst_blunder['move']} on move {worst_blunder['move_number']}."
                )
            elif accuracy >= 80:
                story_parts.append("You played accurately throughout.")

            recap["story"] = f"{result_word}. " + " ".join(story_parts)
            result["last_session"] = recap
    except Exception as e:
        logger.warning(f"[COACH-HOME] Last session failed: {e}")

    # ─── 3. CURRENT PROBLEM ───
    try:
        problems = await db.problem_lifecycle.find(
            {"user_id": user_id, "state": "active"},
            {"_id": 0, "category": 1, "count": 1, "anger": 1}
        ).sort("count", -1).to_list(3)

        if problems:
            top = problems[0]
            category = top.get("category", "")
            count = top.get("count", 0)
            anger = top.get("anger", "first_time")

            # Check recent trend — compare last 5 games vs previous 5
            trending_better = False
            if len(recent_analyses) >= 10:
                recent_blunders = sum(a.get("stockfish_analysis", {}).get("blunders", 0) for a in recent_analyses[:5])
                older_blunders = sum(a.get("stockfish_analysis", {}).get("blunders", 0) for a in recent_analyses[5:10])
                trending_better = recent_blunders < older_blunders

            result["problem"] = {
                "category": category,
                "count": count,
                "anger": anger,
                "trending_better": trending_better,
            }
    except Exception as e:
        logger.warning(f"[COACH-HOME] Problem detection failed: {e}")

    # ─── 3.5. ACTIVE FOCUS PLAN ───
    try:
        from services.focus_engine import get_user_focus
        focus = await get_user_focus(db, user_id)
        if focus:
            game_results = focus.get("game_results", [])
            clean_count = sum(1 for r in game_results if r.get("clean"))
            total_played = len(game_results)
            target = focus.get("games_target", 5)

            result["focus_plan"] = {
                "name": focus.get("name"),
                "rule": focus.get("rule"),
                "short_rule": focus.get("short_rule"),
                "cluster": focus.get("cluster"),
                "games_played": total_played,
                "games_target": target,
                "clean_count": clean_count,
                "clean_threshold": focus.get("clean_threshold", 3),
                "game_results": [{"clean": r.get("clean"), "violations": r.get("violations", 0)} for r in game_results],
                "last_game_clean": focus.get("last_game_clean"),
            }
    except Exception as e:
        logger.warning(f"[COACH-HOME] Focus plan failed: {e}")

    # ─── 4. TODAY'S PLAN (what to play next) ───
    try:
        from services.opening_mastery_tracker import (
            select_branch_for_game, get_branch_info, OPENING_BRANCH_DATA
        )

        # Find the best opening to suggest
        mastery_docs = await db.user_opening_mastery.find(
            {"user_id": user_id}, {"_id": 0}
        ).to_list(10)

        suggested_opening = None
        suggested_branch = None
        suggested_reason = None

        if mastery_docs:
            # Prefer opening with unseen branches
            for m in mastery_docs:
                key = m.get("opening_key", "")
                if key in OPENING_BRANCH_DATA:
                    branches_seen = m.get("branches_seen", [])
                    total = len(OPENING_BRANCH_DATA[key]["branches"])
                    if len(branches_seen) < total:
                        next_branch = select_branch_for_game(key, branches_seen)
                        if next_branch:
                            branch_data = OPENING_BRANCH_DATA[key]["branches"].get(next_branch, {})
                            suggested_opening = key.replace("_", " ").title()
                            suggested_branch = branch_data.get("name", next_branch.replace("_", " ").title())
                            seen_names = [OPENING_BRANCH_DATA[key]["branches"][b]["name"]
                                         for b in branches_seen if b in OPENING_BRANCH_DATA[key]["branches"]]
                            if seen_names:
                                suggested_reason = f"You know the {', '.join(seen_names)}. Let's try the {suggested_branch}."
                            else:
                                suggested_reason = f"Let's start with the {suggested_branch} variation."
                            break

            # Fallback: continue practicing the last opening
            if not suggested_opening and mastery_docs:
                last = max(mastery_docs, key=lambda m: m.get("last_played") or "")
                key = last.get("opening_key", "")
                suggested_opening = key.replace("_", " ").title()
                games = last.get("games_played", 0)
                suggested_reason = f"You've played {games} game{'s' if games != 1 else ''} — keep building your knowledge."

        # Fallback: suggest based on last session
        if not suggested_opening and result.get("last_session", {}).get("opening"):
            suggested_opening = result["last_session"]["opening"]
            suggested_reason = "Continue where you left off."

        result["todays_plan"] = {
            "opening": suggested_opening,
            "branch": suggested_branch,
            "reason": suggested_reason,
        }

        # Puzzle warmup available?
        problem_cat = result.get("problem", {}).get("category", "")
        if problem_cat:
            puzzle_count = await db.community_puzzles.count_documents(
                {"issue_type": problem_cat, "difficulty": {"$lte": 1400}}
            )
            if puzzle_count >= 3:
                PUZZLE_LABELS = {
                    "one_move_blunder": "piece safety", "piece_safety": "piece safety",
                    "tactical_miss": "finding tactics", "missed_tactic": "finding tactics",
                    "calculation_error": "calculation", "calculation_depth": "calculation",
                    "king_safety": "king safety",
                }
                result["warmup"] = {
                    "available": True,
                    "label": PUZZLE_LABELS.get(problem_cat, problem_cat.replace("_", " ")),
                    "pattern": problem_cat,
                    "count": min(puzzle_count, 5),
                }
    except Exception as e:
        logger.warning(f"[COACH-HOME] Today's plan failed: {e}")

    # ─── ACTIVE FOCUS — single source of truth for "what to work on" ───
    # Same resolver the Lab page uses. Keeps Home / Lab / Training aligned.
    try:
        from services.focus_resolver import get_active_focus
        problem_for_agg = result.get("problem")
        top_problems_hint = [problem_for_agg] if problem_for_agg else None
        result["active_focus"] = await get_active_focus(db, user_id, top_problems_hint)
    except Exception as e:
        logger.warning(f"[COACH-HOME] Active focus failed: {e}")
        result["active_focus"] = None

    # ─── ENGINE 2: next skill to learn (forward-looking) ───
    try:
        from services.engine2_skill_builder import pick_next_skill
        from services.coach_memory import get_or_create_memory
        _mem = await get_or_create_memory(db, user_id)
        _rating = _mem.performance.best_performance_rating or 1000
        result["learn_next"] = pick_next_skill(_mem, _rating)
    except Exception as e:
        logger.warning(f"[COACH-HOME] Engine 2 failed: {e}")
        result["learn_next"] = None

    return result


@router.get("/today")
async def get_today(user: User = Depends(get_current_user)):
    """
    The single prescription for /today — one headline, one action.
    Everything the user needs to know in one shape. No menus.
    """
    from services.today_composer import compose_today
    try:
        return await compose_today(db, user.user_id)
    except Exception as e:
        logger.warning(f"[TODAY] compose failed: {e}")
        return {
            "greeting": "Welcome back.",
            "headline": "Let's play a game.",
            "evidence": [],
            "rule": None,
            "board": None,
            "action": {"verb": "Play", "cta": "Play with me", "href": "/play-with-coach", "medium": "live_game"},
            "streak": None,
            "alternates": [],
            "source": "none",
        }


@router.get("/home/pattern-prescription")
async def get_pattern_prescription(
    user: User = Depends(get_current_user)
):
    """
    Get the user's top recurring patterns with matching training position counts.
    For the Home page: "You've missed forks 4 times -> 3 fork positions waiting in Training"
    """
    from services.pattern_memory_service import get_top_patterns

    patterns = await get_top_patterns(db, user.user_id, limit=3)

    # For each pattern, count available training positions
    prescriptions = []
    for p in patterns:
        pattern_type = p["pattern_type"]

        # Count unsolved positions of this pattern type for the user
        solved_ids = set()
        solved = await db.training_solve_attempts.find(
            {"user_id": user.user_id, "pattern_type": pattern_type, "solved": True},
            {"position_id": 1, "_id": 0}
        ).to_list(100)
        solved_ids = {s["position_id"] for s in solved}

        # Count available unsolved positions
        query = {"pattern_type": pattern_type}
        if solved_ids:
            query["position_id"] = {"$nin": list(solved_ids)}

        available = await db.community_training_positions.count_documents(query)

        prescriptions.append({
            "pattern_type": pattern_type,
            "label": p["label"],
            "recent_count": p["recent_count"],
            "total_count": p["total_count"],
            "severity": p["severity"],
            "training_positions_available": available,
        })

    return {"prescriptions": prescriptions}


# ==================== DATA FRESHNESS ROUTES ====================

@router.post("/data/refresh")
async def refresh_user_data(user: User = Depends(get_current_user)):
    """
    Manually trigger a refresh of all aggregated user data.

    This recalculates:
    - Player identity (Memory tab, coaching context)
    - Journey stats (milestones, streaks)
    - Player profile (dashboard stats)
    - Thinking scores

    Call this after importing games or if data seems stale.
    """
    from services.data_freshness import refresh_all_user_data

    # Use synchronous DB connection for the service
    from pymongo import MongoClient

    sync_client = MongoClient(os.environ.get('MONGO_URL'))
    sync_db = sync_client[os.environ.get('DB_NAME', 'test_database')]

    result = refresh_all_user_data(sync_db, user.user_id)

    sync_client.close()

    return result


@router.get("/data/status")
async def get_data_status(user: User = Depends(get_current_user)):
    """
    Get the freshness status of user data across all collections.
    """
    status = {}

    # Check player_identity
    identity = await db.player_identities.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "updated_at": 1, "games_analyzed": 1}
    )
    status["player_identity"] = {
        "exists": identity is not None,
        "games_analyzed": identity.get("games_analyzed") if identity else 0,
        "updated_at": identity.get("updated_at") if identity else None
    }

    # Check player_profile
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "updated_at": 1, "games_analyzed": 1}
    )
    status["player_profile"] = {
        "exists": profile is not None,
        "games_analyzed": profile.get("games_analyzed") if profile else 0,
        "updated_at": profile.get("updated_at") if profile else None
    }

    # Check thinking scores
    score_count = await db.thinking_scores.count_documents({"user_id": user.user_id})
    status["thinking_scores"] = {
        "count": score_count
    }

    # Check total games vs analyzed
    total_games = await db.games.count_documents({"user_id": user.user_id})
    game_ids = [g["game_id"] async for g in db.games.find({"user_id": user.user_id}, {"_id": 0, "game_id": 1})]
    analyzed_games = await db.game_analyses.count_documents({"game_id": {"$in": game_ids}})

    status["games"] = {
        "total": total_games,
        "analyzed": analyzed_games,
        "pending": total_games - analyzed_games
    }

    return status

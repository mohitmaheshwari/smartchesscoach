"""
Weekly Summary Service for Chess Coach AI

Handles:
1. Generating weekly progress summaries
2. Sending weekly email summaries
3. Tracking email notification preferences
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


async def generate_weekly_summary_data(db, user_id: str) -> Dict[str, Any]:
    """
    Generate weekly summary data for a user.
    
    Returns:
        {
            "games_analyzed": 5,
            "improvement_trend": "improving",
            "top_weakness": "One-move blunders",
            "top_strength": "Endgame technique",
            "weekly_assessment": "...",
            "stats": {...},
            "habits_progress": [...]
        }
    """
    # Calculate date range (last 7 days)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)
    
    # Get games analyzed this week
    games_this_week = await db.game_analyses.find(
        {
            "user_id": user_id,
            "created_at": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()},
            "stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}}
        },
        {"_id": 0, "stockfish_analysis": 1, "game_id": 1}
    ).to_list(100)
    
    games_count = len(games_this_week)
    
    # Helper to count from Stockfish data (SOURCE OF TRUTH)
    def count_evals(analysis, eval_type):
        sf = analysis.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        return sum(1 for m in evals if m.get("evaluation") == eval_type)
    
    def count_best(analysis):
        sf = analysis.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        return sum(1 for m in evals if m.get("is_best") or m.get("evaluation") == "best")
    
    # Calculate stats from stockfish_analysis.move_evaluations
    total_blunders = sum(count_evals(g, "blunder") for g in games_this_week)
    total_mistakes = sum(count_evals(g, "mistake") for g in games_this_week)
    total_best = sum(count_best(g) for g in games_this_week)
    
    avg_blunders = total_blunders / games_count if games_count > 0 else 0
    
    # Get previous week for comparison
    prev_end = start_date
    prev_start = prev_end - timedelta(days=7)
    
    prev_games = await db.game_analyses.find(
        {
            "user_id": user_id,
            "created_at": {"$gte": prev_start.isoformat(), "$lte": prev_end.isoformat()},
            "stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}}
        },
        {"_id": 0, "stockfish_analysis": 1}
    ).to_list(100)
    
    prev_total_blunders = sum(count_evals(g, "blunder") for g in prev_games)
    prev_avg_blunders = prev_total_blunders / len(prev_games) if prev_games else avg_blunders
    
    # Determine improvement trend
    if avg_blunders < prev_avg_blunders * 0.8:
        improvement_trend = "improving"
    elif avg_blunders > prev_avg_blunders * 1.2:
        improvement_trend = "declining"
    else:
        improvement_trend = "stable"
    
    # Get profile for weaknesses/strengths
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0, "top_weaknesses": 1, "strengths": 1, "resolved_habits": 1}
    )
    
    top_weakness = None
    top_strength = None
    
    if profile:
        weaknesses = profile.get("top_weaknesses", [])
        if weaknesses:
            w = weaknesses[0]
            top_weakness = w.get("subcategory", str(w)) if isinstance(w, dict) else str(w)
        
        strengths = profile.get("strengths", [])
        if strengths:
            s = strengths[0]
            top_strength = s.get("subcategory", str(s)) if isinstance(s, dict) else str(s)
    
    # Get reflection stats this week
    reflections = await db.reflection_results.find(
        {
            "user_id": user_id,
            "created_at": {"$gte": start_date.isoformat()}
        },
        {"_id": 0, "move_correct": 1}
    ).to_list(100)
    
    reflection_total = len(reflections)
    reflection_correct = sum(1 for r in reflections if r.get("move_correct", False))
    reflection_rate = reflection_correct / reflection_total if reflection_total > 0 else 0
    
    # Generate weekly assessment
    weekly_assessment = _generate_assessment(
        games_count=games_count,
        avg_blunders=avg_blunders,
        prev_avg_blunders=prev_avg_blunders,
        improvement_trend=improvement_trend,
        top_weakness=top_weakness,
        reflection_rate=reflection_rate
    )
    
    # Get habits progress
    resolved_habits = profile.get("resolved_habits", []) if profile else []
    
    return {
        "user_id": user_id,
        "week_start": start_date.isoformat(),
        "week_end": end_date.isoformat(),
        "games_analyzed": games_count,
        "improvement_trend": improvement_trend,
        "top_weakness": top_weakness,
        "top_strength": top_strength,
        "weekly_assessment": weekly_assessment,
        "stats": {
            "total_blunders": total_blunders,
            "total_mistakes": total_mistakes,
            "total_best_moves": total_best,
            "avg_blunders_per_game": round(avg_blunders, 2),
            "prev_avg_blunders": round(prev_avg_blunders, 2),
            "reflection_attempts": reflection_total,
            "reflection_correct": reflection_correct,
            "reflection_rate": round(reflection_rate, 2)
        },
        "resolved_habits_count": len(resolved_habits)
    }


def _generate_assessment(
    games_count: int,
    avg_blunders: float,
    prev_avg_blunders: float,
    improvement_trend: str,
    top_weakness: Optional[str],
    reflection_rate: float
) -> str:
    """Generate a personalized weekly assessment."""
    
    if games_count == 0:
        return "You didn't play any analyzed games this week. No worries — when you're ready, I'll be here."
    
    # Start with trend assessment
    if improvement_trend == "improving":
        assessment = f"Strong week. Your blunders dropped from {prev_avg_blunders:.1f} to {avg_blunders:.1f} per game. "
    elif improvement_trend == "declining":
        assessment = f"Challenging week. Blunders went up slightly ({prev_avg_blunders:.1f} → {avg_blunders:.1f}). Don't worry — we'll work through this. "
    else:
        assessment = f"Steady week with {avg_blunders:.1f} blunders per game. Consistency is key. "
    
    # Add weakness focus
    if top_weakness:
        assessment += f"Keep focusing on {top_weakness.lower()} — it's your main growth area. "
    
    # Add reflection performance
    if reflection_rate >= 0.7:
        assessment += "Your reflection accuracy is excellent — you're recognizing patterns well."
    elif reflection_rate >= 0.4:
        assessment += "Your reflection practice is building solid awareness."
    elif reflection_rate > 0:
        assessment += "Keep practicing the reflections — pattern recognition takes time."
    
    return assessment.strip()


async def send_weekly_summaries(db) -> Dict[str, Any]:
    """
    Send weekly summaries to all eligible users.
    Called by a scheduled job (e.g., every Sunday).
    
    Returns summary of emails sent.
    """
    from email_service import send_email, generate_weekly_summary_email, is_email_configured
    
    if not is_email_configured():
        logger.warning("Email not configured. Skipping weekly summaries.")
        return {"status": "skipped", "reason": "Email not configured"}
    
    # Get users who have email notifications enabled
    users = await db.users.find(
        {
            "email_notifications": {"$ne": False},  # Include if not explicitly disabled
            "email": {"$exists": True, "$ne": None}
        },
        {"_id": 0, "user_id": 1, "email": 1, "name": 1}
    ).to_list(1000)
    
    sent_count = 0
    failed_count = 0
    skipped_count = 0
    
    for user in users:
        try:
            user_id = user["user_id"]
            email = user["email"]
            name = user.get("name", "Chess Player")
            
            # Generate summary data
            summary = await generate_weekly_summary_data(db, user_id)
            
            # Skip if no games this week
            if summary["games_analyzed"] == 0:
                skipped_count += 1
                continue
            
            # Generate email content
            subject, html_content, plain_content = generate_weekly_summary_email(
                user_name=name,
                games_analyzed=summary["games_analyzed"],
                improvement_trend=summary["improvement_trend"],
                top_weakness=summary["top_weakness"],
                top_strength=summary["top_strength"],
                weekly_assessment=summary["weekly_assessment"]
            )
            
            # Send email
            success = await send_email(email, subject, html_content, plain_content)
            
            if success:
                sent_count += 1
                # Log email sent
                await db.email_logs.insert_one({
                    "user_id": user_id,
                    "email": email,
                    "type": "weekly_summary",
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "summary_data": summary
                })
            else:
                failed_count += 1
                
        except Exception as e:
            logger.error(f"Failed to send weekly summary to {user.get('email')}: {e}")
            failed_count += 1
    
    logger.info(f"Weekly summaries: sent={sent_count}, failed={failed_count}, skipped={skipped_count}")
    
    return {
        "status": "completed",
        "sent": sent_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def send_single_weekly_summary(db, user_id: str) -> Dict[str, Any]:
    """
    Send weekly summary to a specific user (manual trigger).
    """
    from email_service import send_email, generate_weekly_summary_email, is_email_configured
    
    if not is_email_configured():
        return {"status": "error", "reason": "Email not configured"}
    
    # Get user
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "email": 1, "name": 1}
    )
    
    if not user or not user.get("email"):
        return {"status": "error", "reason": "User email not found"}
    
    # Generate summary
    summary = await generate_weekly_summary_data(db, user_id)
    
    # Generate and send email
    subject, html_content, plain_content = generate_weekly_summary_email(
        user_name=user.get("name", "Chess Player"),
        games_analyzed=summary["games_analyzed"],
        improvement_trend=summary["improvement_trend"],
        top_weakness=summary["top_weakness"],
        top_strength=summary["top_strength"],
        weekly_assessment=summary["weekly_assessment"]
    )
    
    success = await send_email(user["email"], subject, html_content, plain_content)
    
    return {
        "status": "sent" if success else "failed",
        "email": user["email"],
        "summary": summary
    }

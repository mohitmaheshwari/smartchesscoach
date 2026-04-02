"""
Progress Report Service — Coaching-oriented progress tracking.

Computes:
1. Weakness control trends (are patterns shrinking?)
2. Habits evolution (castling, threat checking, development discipline)
3. Phase understanding (opening/middlegame/endgame scores)
4. Recent form vs big picture
5. Review impact (did reviewing help?)
"""

from datetime import datetime, timezone


async def build_coaching_report(db, user_id: str) -> dict:
    """Build a full coaching progress report for a player."""
    
    # Fetch all games + analyses sorted by date
    games_cursor = db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "reviewed": 1,
         "reviewed_at": 1, "imported_at": 1, "opening": 1, "opponent_name": 1}
    ).sort("imported_at", 1)
    games = await games_cursor.to_list(200)
    
    if not games:
        return {"has_data": False}
    
    game_ids = [g["game_id"] for g in games]
    
    # Fetch analyses
    analyses_cursor = db.game_analyses.find(
        {"user_id": user_id, "game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "stockfish_analysis": 1, "habits_report": 1,
         "decryption_v5_data.core_lesson": 1, "coach_summary": 1}
    )
    analyses = {a["game_id"]: a async for a in analyses_cursor}
    
    # Build per-game stats
    game_stats = []
    for g in games:
        gid = g["game_id"]
        a = analyses.get(gid, {})
        sa = a.get("stockfish_analysis", {}) or {}
        hr = a.get("habits_report", {}) or {}
        dd = a.get("decryption_v5_data", {})
        if isinstance(dd, list):
            dd = {}
        cl = (dd or {}).get("core_lesson", {}) or {}
        cs = a.get("coach_summary", {}) or {}
        
        uc = g.get("user_color", "white")
        res = g.get("result", "")
        won = (res == "1-0" and uc == "white") or (res == "0-1" and uc == "black")
        draw = "1/2" in res
        
        # Cognitive gaps from move evaluations
        evals = sa.get("move_evaluations", [])
        gaps = []
        for ev in evals:
            gap = ev.get("cognitive_gap")
            if gap:
                gaps.append(gap)
        
        # Phase performance
        pp = hr.get("phase_performance", {}) or {}
        
        game_stats.append({
            "game_id": gid,
            "result": "W" if won else ("D" if draw else "L"),
            "accuracy": sa.get("accuracy", 0) or 0,
            "blunders": sa.get("blunders", 0) or 0,
            "mistakes": sa.get("mistakes", 0) or 0,
            "cognitive_gaps": gaps,
            "habits_score": hr.get("overall_habits_score", 0) or 0,
            "opening_accuracy": pp.get("opening", {}).get("accuracy", 0) if isinstance(pp.get("opening"), dict) else 0,
            "middlegame_accuracy": pp.get("middlegame", {}).get("accuracy", 0) if isinstance(pp.get("middlegame"), dict) else 0,
            "endgame_accuracy": pp.get("endgame", {}).get("accuracy", 0) if isinstance(pp.get("endgame"), dict) else 0,
            "lesson_label": cl.get("short_label", ""),
            "behavior": cs.get("behavioral_insight") or cs.get("key_observation") or "",
            "reviewed": g.get("reviewed", False),
            "opening": g.get("opening", ""),
            "opponent": g.get("opponent_name", ""),
        })
    
    total = len(game_stats)
    
    # ── 1. WEAKNESS CONTROL ──
    weakness_control = _compute_weakness_trends(game_stats)
    
    # ── 2. HABITS EVOLUTION ──
    habits_evolution = _compute_habits_trends(game_stats)
    
    # ── 3. PHASE UNDERSTANDING ──
    phase_understanding = _compute_phase_understanding(game_stats)
    
    # ── 4. RECENT FORM (last 5) vs BIG PICTURE ──
    recent_5 = game_stats[-5:] if total >= 5 else game_stats
    recent_form = _compute_form_summary(recent_5, "recent")
    big_picture = _compute_form_summary(game_stats, "all")
    
    # ── 5. REVIEW IMPACT ──
    review_impact = _compute_review_impact(game_stats)
    
    # ── COACHING HEADLINE ──
    headline = _generate_headline(weakness_control, habits_evolution, recent_form, big_picture)
    
    return {
        "has_data": True,
        "total_games": total,
        "headline": headline,
        "recent_form": recent_form,
        "big_picture": big_picture,
        "weakness_control": weakness_control,
        "habits_evolution": habits_evolution,
        "phase_understanding": phase_understanding,
        "review_impact": review_impact,
        "game_stats": game_stats,  # For the timeline chart
    }


def _compute_weakness_trends(stats):
    """Track each weakness pattern over time windows."""
    if len(stats) < 3:
        return []
    
    # Count patterns across all games
    all_gaps = {}
    for gs in stats:
        for gap in gs["cognitive_gaps"]:
            if gap not in all_gaps:
                all_gaps[gap] = {"total": 0, "recent_5": 0, "older": 0}
            all_gaps[gap]["total"] += 1
    
    # Count in recent 5 vs older
    recent = stats[-5:]
    older = stats[:-5] if len(stats) > 5 else []
    
    for gs in recent:
        for gap in gs["cognitive_gaps"]:
            if gap in all_gaps:
                all_gaps[gap]["recent_5"] += 1
    
    for gs in older:
        for gap in gs["cognitive_gaps"]:
            if gap in all_gaps:
                all_gaps[gap]["older"] += 1
    
    trends = []
    for pattern, counts in sorted(all_gaps.items(), key=lambda x: -x[1]["total"]):
        if counts["total"] < 2:
            continue
        
        older_count = counts["older"]
        recent_count = counts["recent_5"]
        older_games = max(len(older), 1)
        recent_games = max(len(recent), 1)
        
        older_rate = older_count / older_games
        recent_rate = recent_count / recent_games
        
        if recent_rate < older_rate * 0.6:
            direction = "improving"
            message = f"Showing up less. Down from {older_count} in {older_games} games to {recent_count} in {recent_games}."
        elif recent_rate > older_rate * 1.4:
            direction = "worsening"
            message = f"Getting worse. Up to {recent_count} in last {recent_games} games."
        else:
            direction = "stable"
            message = f"Still showing up. {recent_count}x in last {recent_games} games."
        
        label = pattern.replace("_", " ").title()
        
        trends.append({
            "pattern": pattern,
            "label": label,
            "total": counts["total"],
            "recent": recent_count,
            "older": older_count,
            "direction": direction,
            "message": message,
        })
    
    return trends[:5]  # Top 5 patterns


def _compute_habits_trends(stats):
    """Track behavioral habits over time."""
    if len(stats) < 3:
        return {}
    
    recent = stats[-5:]
    older = stats[:-5] if len(stats) > 5 else []
    
    def avg_field(games, field):
        vals = [g[field] for g in games if g[field] > 0]
        return sum(vals) / len(vals) if vals else 0
    
    habits_score_recent = avg_field(recent, "habits_score")
    habits_score_older = avg_field(older, "habits_score") if older else 0
    
    habits_improving = habits_score_recent > habits_score_older + 5 if older else False
    habits_declining = habits_score_recent < habits_score_older - 5 if older else False
    
    return {
        "habits_score_recent": round(habits_score_recent, 1),
        "habits_score_older": round(habits_score_older, 1),
        "direction": "improving" if habits_improving else ("worsening" if habits_declining else "stable"),
        "message": (
            "Your habits are getting stronger. Keep it up."
            if habits_improving else
            "Your discipline is slipping. Review the habits checklist."
            if habits_declining else
            "Habits holding steady."
        ),
    }


def _compute_phase_understanding(stats):
    """Track opening/middlegame/endgame understanding."""
    if len(stats) < 3:
        return {}
    
    recent = stats[-5:]
    older = stats[:-5] if len(stats) > 5 else []
    
    def avg_phase(games, field):
        vals = [g[field] for g in games if g[field] > 0]
        return round(sum(vals) / len(vals), 1) if vals else 0
    
    phases = {}
    for phase, field in [("opening", "opening_accuracy"), ("middlegame", "middlegame_accuracy"), ("endgame", "endgame_accuracy")]:
        recent_avg = avg_phase(recent, field)
        older_avg = avg_phase(older, field) if older else 0
        
        if older_avg > 0:
            delta = recent_avg - older_avg
            if delta > 5:
                direction = "improving"
            elif delta < -5:
                direction = "worsening"
            else:
                direction = "stable"
        else:
            direction = "stable"
        
        phases[phase] = {
            "score": recent_avg,
            "previous": older_avg,
            "direction": direction,
        }
    
    # Find weakest phase (only flag if it's actually weak, not if all are high)
    scored = [(k, v["score"]) for k, v in phases.items() if v["score"] > 0 and k not in ("weakest",)]
    if scored:
        min_phase = min(scored, key=lambda x: x[1])
        # Only label as "weakest" if it's actually below 75%
        if min_phase[1] < 75:
            phases["weakest"] = min_phase[0]
    
    return phases


def _compute_form_summary(stats, label):
    """Summarize a set of games."""
    if not stats:
        return {}
    
    wins = sum(1 for g in stats if g["result"] == "W")
    losses = sum(1 for g in stats if g["result"] == "L")
    draws = sum(1 for g in stats if g["result"] == "D")
    
    accs = [g["accuracy"] for g in stats if g["accuracy"] > 0]
    avg_acc = round(sum(accs) / len(accs), 1) if accs else 0
    
    blunders = sum(g["blunders"] for g in stats)
    blunder_rate = round(blunders / len(stats), 1)
    
    # Behavioral labels
    labels = [g["lesson_label"] for g in stats if g["lesson_label"]]
    
    return {
        "label": label,
        "games": len(stats),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "accuracy": avg_acc,
        "blunder_rate": blunder_rate,
        "lesson_labels": labels,
    }


def _compute_review_impact(stats):
    """Compare performance in games before and after reviews."""
    reviewed_indices = [i for i, g in enumerate(stats) if g["reviewed"]]
    
    if not reviewed_indices or len(stats) < 4:
        return {"has_data": False}
    
    first_review = min(reviewed_indices)
    
    before = stats[:first_review] if first_review > 0 else stats[:len(stats)//2]
    after = stats[first_review:] if first_review > 0 else stats[len(stats)//2:]
    
    if not before or not after:
        return {"has_data": False}
    
    before_blunders = sum(g["blunders"] for g in before) / max(len(before), 1)
    after_blunders = sum(g["blunders"] for g in after) / max(len(after), 1)
    
    before_acc = sum(g["accuracy"] for g in before if g["accuracy"] > 0)
    before_acc = before_acc / max(len([g for g in before if g["accuracy"] > 0]), 1)
    after_acc = sum(g["accuracy"] for g in after if g["accuracy"] > 0)
    after_acc = after_acc / max(len([g for g in after if g["accuracy"] > 0]), 1)
    
    blunder_change = round(((after_blunders - before_blunders) / max(before_blunders, 0.1)) * 100, 0)
    acc_change = round(after_acc - before_acc, 1)
    
    return {
        "has_data": True,
        "games_reviewed": len(reviewed_indices),
        "before_blunders": round(before_blunders, 1),
        "after_blunders": round(after_blunders, 1),
        "blunder_change_pct": blunder_change,
        "before_accuracy": round(before_acc, 1),
        "after_accuracy": round(after_acc, 1),
        "accuracy_change": acc_change,
        "improving": after_blunders < before_blunders or after_acc > before_acc,
    }


def _generate_headline(weakness_control, habits, recent_form, big_picture):
    """Generate the coaching headline."""
    # Check for improving weaknesses
    improving = [w for w in weakness_control if w["direction"] == "improving"]
    worsening = [w for w in weakness_control if w["direction"] == "worsening"]
    
    if improving and not worsening:
        return f"You're gaining control over {improving[0]['label']}. Real progress."
    
    if worsening:
        return f"{worsening[0]['label']} is getting worse. Time to focus."
    
    if habits.get("direction") == "improving":
        return "Your chess habits are getting stronger. Keep reviewing."
    
    if habits.get("direction") == "worsening":
        return "Your discipline is slipping. Slow down and review."
    
    if recent_form.get("accuracy", 0) > big_picture.get("accuracy", 0) + 3:
        return "Your recent form is stronger than your average. You're improving."
    
    if recent_form.get("accuracy", 0) < big_picture.get("accuracy", 0) - 3:
        return "Recent games are below your average. Review before playing more."
    
    return "Steady progress. Keep reviewing your games and training patterns."

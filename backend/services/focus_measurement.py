"""focus_measurement.py — MEASUREMENT for the Universal Habit Coach.

DESIGN CONSTRAINT (Mohit 2026-06-09): measurement and detection are LOGICALLY SEPARATE systems,
even though built together. This module is the measurement system. It answers exactly one
question: *for a user with a focus, was each of their analyzed games clean of the focus's
targeted mistake?* — and maintains games_with_focus / clean_games / targeted_mistakes / game_results.

It is decoupled on BOTH axes that broke the previous loop:
  1. It NEVER gates on root-problem re-detection (the old `if not primary: return` silent-skip —
     focus_engine.py:253 — caused games_with_focus=0 for 50/51 users; 96% of games hit it).
  2. It NEVER reads the sparse legacy `behavior_summary` (populated for only 6% of sessions).
     It reads `cognitive_gap` from `game_analyses` — the SAME source as the L4 metric.

It CONSUMES services.core_habit (detection) but does not detect. It does not re-detect root problems.

HEARTBEAT: the previous loop failed silently. `heartbeat()` is the daily pulse — if it ever
reports total_games_with_focus=0 again, the loop is broken and we will know immediately.
"""
import logging
from services import core_habit

logger = logging.getLogger(__name__)


def _game_result(game_id, analyzed_at, move_evals, habit):
    tm = core_habit.targeted_mistakes(move_evals, habit)
    return {
        "game_id": game_id,
        "analyzed_at": str(analyzed_at or ""),
        "targeted_mistakes": tm,
        "clean": tm == 0,
        "user_moves": core_habit.user_moves(move_evals),
    }


async def measure_user(db, user_id: str, habit: str = "threat_scan", write: bool = True) -> dict:
    """Recompute a user's full measurement from their analyzed games. Idempotent — this is the
    source of truth for the L4 windows and graduation. Reads cognitive_gap; independent of
    root-detection and behavior_summary."""
    results = []
    cur = db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "analyzed_at": 1, "stockfish_analysis.move_evaluations": 1},
    ).sort("analyzed_at", 1)
    async for a in cur:
        me = (a.get("stockfish_analysis") or {}).get("move_evaluations") or []
        if not me or not core_habit.is_real_game(me):
            continue  # skip empty + abandoned coach stubs (< MIN_GAME_MOVES user moves)
        results.append(_game_result(a.get("game_id"), a.get("analyzed_at"), me, habit))

    measurement = {
        "habit": habit,
        "games_with_focus": len(results),
        "clean_games": sum(1 for r in results if r["clean"]),
        "targeted_mistakes": sum(r["targeted_mistakes"] for r in results),
        "total_user_moves": sum(r["user_moves"] for r in results),
    }
    if write and results:
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "focus.measurement": measurement,
                "focus.measurement_game_results": results[-30:],  # recent window for L4
            }},
        )
    measurement["game_results"] = results  # full history returned (not all persisted)
    return measurement


async def record_game(db, user_id: str, game_analysis: dict, habit: str = "threat_scan") -> dict:
    """Live incremental hook — called from the analysis pipeline AFTER cognitive_gap is tagged
    for a newly analyzed game. Only meaningful for users with a focus. Recomputes idempotently
    (cheap) so a re-analyzed or out-of-order game can't double-count."""
    focus = await db.users.find_one({"user_id": user_id}, {"_id": 0, "focus": 1})
    if not (focus and focus.get("focus")):
        return {}  # no focus -> nothing to measure (NOT an error)
    return await measure_user(db, user_id, habit, write=True)


async def heartbeat(db, habit: str = "threat_scan", write: bool = False) -> dict:
    """DAILY VERIFICATION — the loop must not fail silently again. Reports the four health
    numbers across every focused user. Run from a daily cron; alert if total_games_with_focus
    is 0 while focused_users > 0 (that was the original silent failure)."""
    focused = [
        u["user_id"]
        async for u in db.users.find({"focus": {"$exists": True, "$ne": None}}, {"_id": 0, "user_id": 1})
    ]
    measured = tot_games = tot_clean = tot_tm = 0
    for uid in focused:
        m = await measure_user(db, uid, habit, write=write)
        if m["games_with_focus"] > 0:
            measured += 1
            tot_games += m["games_with_focus"]
            tot_clean += m["clean_games"]
            tot_tm += m["targeted_mistakes"]
    hb = {
        "focused_users": len(focused),
        "users_with_measured_games": measured,
        "total_games_with_focus": tot_games,
        "total_clean_games": tot_clean,
        "total_targeted_mistakes": tot_tm,
        "clean_rate_pct": round(100 * tot_clean / max(1, tot_games)),
        "silent_failure": (len(focused) > 0 and tot_games == 0),  # the alarm bit
    }
    logger.info(f"[FOCUS-HEARTBEAT] {hb}")
    return hb

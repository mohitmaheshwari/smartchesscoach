"""l4_pilot_monitor.py — health + progress monitor for the Universal Habit Coach experiment.

Run anytime (t=0 sanity, interim, and any read):
    docker exec -i chess-coach-backend python /app/backend/scripts/l4_pilot_monitor.py

Reports across BOTH cohorts in db.l4_pilot (cohort="pilot_48h" = the
original Cohort A 8 users; cohort="cohort_b" = the scale-up enrolled per
docs/experiment_01_habit_coach_scaleup_preregistration.md, via
services.focus_engine.maybe_enroll_cohort_b):
  - heartbeat() + silent_failure alarm
  - per-pilot-user: cohort, arm, focus integrity (is it the universal threat_scan focus on the right arm?),
    games played since assignment, clean rate, R_post-so-far, graduations
  - anomalies: focus corruption, unexpected zeros
Verdict = measurement still accumulating, no unexpected zeros, no corruption, no alarms.
"""
import os, sys, asyncio
sys.path.insert(0, "/app/backend")  # so `from services import ...` resolves when run as a file
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=12000)[os.environ.get("DB_NAME", "chess_coach")]
    await db.command("ping")
    from services import core_habit
    from services.focus_measurement import heartbeat

    hb = await heartbeat(db, write=False)
    print("=== HEARTBEAT ===")
    for k in ("focused_users", "users_with_measured_games", "total_games_with_focus",
              "total_clean_games", "total_targeted_mistakes", "clean_rate_pct", "silent_failure"):
        print(f"  {k}: {hb[k]}")

    print("\n=== COHORTS (db.l4_pilot) ===")
    print("user            arm        focus_ok  R_base   games_post  R_post   graduated  cohort")
    anomalies = []
    async for d in db.l4_pilot.find({}, {"_id": 0}).sort([("cohort", 1), ("arm", 1)]):
        uid = d["user_id"]; arm = d["arm"]; assigned = d.get("assigned_at", "")
        u = await db.users.find_one({"user_id": uid}, {"_id": 0, "focus": 1})
        f = (u or {}).get("focus") or {}
        focus_ok = (f.get("habit") == "threat_scan"
                    and f.get("reminder_enabled") == (arm == "treatment"))
        if not focus_ok:
            anomalies.append(f"{uid[:14]}: focus corrupted/changed (habit={f.get('habit')}, reminder={f.get('reminder_enabled')})")
        # games + targeted mistakes since assignment
        tm = um = ngames = 0
        async for a in db.game_analyses.find(
            {"user_id": uid, "analyzed_at": {"$gt": assigned}},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1},
        ):
            me = (a.get("stockfish_analysis") or {}).get("move_evaluations") or []
            if not me or not core_habit.is_real_game(me):
                continue
            ngames += 1; tm += core_habit.targeted_mistakes(me); um += core_habit.user_moves(me)
        rpost = round(tm / um, 4) if um else None
        graduated = bool(await db.focus_history.find_one({"user_id": uid, "graduated_at": {"$gt": assigned}}))
        print(f"  {uid[:14]:15} {arm:10} {'yes' if focus_ok else 'NO!':8} "
              f"{str(d.get('r_base')):>7}  {ngames:>9}   {str(rpost):>7}   {str(graduated):9}  {d.get('cohort')}")

    print("\n=== ANOMALIES ===")
    if hb["silent_failure"]:
        anomalies.append("HEARTBEAT silent_failure=True (focused users but zero measured)")
    print("  " + ("\n  ".join(anomalies) if anomalies else "none"))


asyncio.run(main())

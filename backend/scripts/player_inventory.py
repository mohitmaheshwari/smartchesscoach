"""
Player Inventory — debug view into every user's chess state.

Three modes:

  # List every user with a one-line summary
  python scripts/player_inventory.py

  # Deep-dive one user
  python scripts/player_inventory.py <user_id>

  # Backfill derived fields (rating, performance stats) on one user
  python scripts/player_inventory.py <user_id> --backfill

  # Backfill all users
  python scripts/player_inventory.py --all-backfill

The deep-dive shows:
  - Identity + connected platforms
  - Three rating signals:
      1. Platform-reported (self-declared from Chess.com/Lichess profile)
      2. PGN-inferred (average of recent game Elo in PGN headers — ChessGuru's real read)
      3. Performance-rated (Stockfish-inferred from actual play quality)
  - Game counts (total, analyzed, by platform, date range)
  - Engine 1 state: current_focus + prescription history
  - Engine 2 state: 12-skill tree progress
  - Engagement: coach sessions, puzzle attempts, messages
  - Gaps + recommendations
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(BACKEND_DIR / ".env")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ─── HELPERS ──────────────────────────────────────────────────────────


def _fmt_date(ts):
    if not ts:
        return "never"
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return ts[:16]
    if isinstance(ts, datetime):
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = now - ts
        if delta.days == 0:
            h = delta.seconds // 3600
            return f"{h}h ago" if h else f"{delta.seconds // 60}m ago"
        if delta.days < 7:
            return f"{delta.days}d ago"
        return ts.strftime("%Y-%m-%d")
    return str(ts)


def _banner(title, width=76):
    line = "═" * width
    print()
    print(line)
    print(f"  {title}")
    print(line)


def _rating_band(rating):
    if rating < 1000:
        return "beginner_low"
    if rating < 1400:
        return "beginner_high"
    if rating < 1800:
        return "intermediate"
    return "advanced"


# ─── DATA GATHERERS ───────────────────────────────────────────────────


async def get_player_summary(db, user):
    """One-line summary row for the list view."""
    user_id = user["user_id"]
    email = user.get("email", "—")[:30]

    games_count = await db.games.count_documents({"user_id": user_id, "is_analyzed": True})
    sessions_count = await db.coach_sessions.count_documents({"user_id": user_id})

    memory = await db.coach_memory.find_one({"user_id": user_id}, {"learning": 1, "performance": 1, "updated_at": 1})
    focus = "—"
    rating = 0
    if memory:
        focus = (memory.get("learning") or {}).get("current_focus") or "—"
        rating = (memory.get("performance") or {}).get("best_performance_rating") or 0

    last_session = await db.coach_sessions.find_one(
        {"user_id": user_id}, sort=[("created_at", -1)], projection={"created_at": 1}
    )
    last_active = _fmt_date((last_session or {}).get("created_at"))

    return {
        "user_id": user_id,
        "email": email,
        "games": games_count,
        "sessions": sessions_count,
        "rating": rating,
        "focus": focus[:24],
        "last_active": last_active,
    }


async def show_all_players(db):
    users = await db.users.find({}, {"user_id": 1, "email": 1, "_id": 0}).to_list(500)
    _banner(f"All Players ({len(users)} users)")
    print(f"  {'Email':<32} {'Rating':>6} {'Games':>6} {'Sess':>5}  {'Focus':<26}  Last active")
    print(f"  {'-'*32} {'-'*6} {'-'*6} {'-'*5}  {'-'*26}  {'-'*12}")

    rows = []
    for u in users:
        rows.append(await get_player_summary(db, u))
    # Sort by activity (games + sessions)
    rows.sort(key=lambda r: r["games"] + r["sessions"], reverse=True)
    for r in rows:
        print(f"  {r['email']:<32} {r['rating']:>6} {r['games']:>6} {r['sessions']:>5}  "
              f"{r['focus']:<26}  {r['last_active']}")


async def show_player_detail(db, user_id):
    # ── Identity ──
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        print(f"No user with user_id={user_id}")
        return

    _banner(f"Player: {user_id}")
    print(f"  Email:            {user.get('email', '—')}")
    print(f"  Display name:     {user.get('display_name') or user.get('name') or '—'}")
    print(f"  Chess.com:        {user.get('chess_com_username') or '—'}")
    print(f"  Lichess:          {user.get('lichess_username') or '—'}")
    print(f"  Created:          {_fmt_date(user.get('created_at'))}")

    # ── Rating signals (three sources) ──
    _banner("Rating signals")

    # 1. Platform-reported (self-declared from connected account)
    profile = await db.player_profiles.find_one({"user_id": user_id}, {"_id": 0})
    lichess_rating = chesscom_rating = None
    if profile:
        lichess_rating = (profile.get("lichess_stats") or {}).get("rating") or profile.get("lichess_rating")
        chesscom_rating = (profile.get("chesscom_stats") or {}).get("rating") or profile.get("chesscom_rating")
    print(f"  Platform-reported:")
    print(f"    Chess.com:      {chesscom_rating or '—'}")
    print(f"    Lichess:        {lichess_rating or '—'}")

    # 2. PGN-inferred (from game headers, what ChessGuru actually sees)
    try:
        from services.coach_memory import get_user_rating_from_games
        pgn_rating = await get_user_rating_from_games(db, user_id)
        print(f"  PGN-inferred (from imported game Elo headers):")
        print(f"    Current:        {pgn_rating.get('rating')} ({pgn_rating.get('source')})")
        print(f"    Avg:            {pgn_rating.get('avg_rating', '—')}")
        print(f"    High / Low:     {pgn_rating.get('highest_rating', '—')} / {pgn_rating.get('lowest_rating', '—')}")
        print(f"    Trend:          {pgn_rating.get('rating_trend')}")
        print(f"    Games used:     {pgn_rating.get('games_analyzed', 0)}")
    except Exception as e:
        print(f"  PGN-inferred:     (error: {e})")
        pgn_rating = None

    # 3. Performance-rated (Stockfish-inferred from actual play quality)
    memory = await db.coach_memory.find_one({"user_id": user_id}, {"_id": 0})
    if memory:
        perf = memory.get("performance", {})
        print(f"  Performance-rated (from Stockfish move analysis):")
        print(f"    Best:           {perf.get('best_performance_rating', 0)}")
        print(f"    Worst:          {perf.get('worst_performance_rating', 0)}")
        print(f"    Band:           {_rating_band(perf.get('best_performance_rating', 1000))}")

    # ── Game inventory ──
    _banner("Game inventory")
    games_total = await db.games.count_documents({"user_id": user_id})
    games_analyzed = await db.games.count_documents({"user_id": user_id, "is_analyzed": True})
    by_platform = {}
    for plat in ("chess.com", "lichess", "coach"):
        n = await db.games.count_documents({"user_id": user_id, "platform": plat})
        if n:
            by_platform[plat] = n

    first_game = await db.games.find_one({"user_id": user_id}, sort=[("imported_at", 1)], projection={"imported_at": 1})
    last_game = await db.games.find_one({"user_id": user_id}, sort=[("imported_at", -1)], projection={"imported_at": 1})

    print(f"  Total imported:   {games_total}")
    print(f"  Analyzed:         {games_analyzed}  ({games_analyzed * 100 // max(games_total, 1)}%)")
    print(f"  By platform:      {by_platform or '(none)'}")
    if first_game:
        print(f"  Date range:       {_fmt_date(first_game.get('imported_at'))} → {_fmt_date(last_game.get('imported_at'))}")

    # Termination breakdown (for quality read)
    term_pipeline = [
        {"$match": {"user_id": user_id, "is_analyzed": True}},
        {"$group": {"_id": "$termination", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    termination_counts = []
    async for row in db.games.aggregate(term_pipeline):
        termination_counts.append((row["_id"] or "unknown", row["count"]))
    if termination_counts:
        print(f"  Termination mix:  " + ", ".join(f"{t}={n}" for t, n in termination_counts[:6]))

    # ── Engine 1 state ──
    _banner("Engine 1 — Fix Your Mess")
    if not memory:
        print("  No coach_memory yet.")
    else:
        learning = memory.get("learning", {})
        print(f"  Current focus:    {learning.get('current_focus') or '(none)'}")
        print(f"  Suggested next:   {learning.get('suggested_next') or '[]'}")
        print(f"  Games played:     {(memory.get('performance') or {}).get('games_played', 0)}")
        print(f"  Avg accuracy:     {(memory.get('performance') or {}).get('avg_accuracy', 0):.1f}%")
        print(f"  Improvement rate: {(memory.get('performance') or {}).get('improvement_rate', 0):+.2f}")

        weaknesses = memory.get("weaknesses") or []
        weaknesses.sort(key=lambda w: w.get("detection_count", 0), reverse=True)
        if weaknesses:
            print(f"  Top weaknesses:")
            for w in weaknesses[:5]:
                trend = "↗" if w.get("improving") else "·"
                print(f"    {trend} {(w.get('name') or w.get('habit_id') or '?'):<32}  "
                      f"{w.get('detection_count', 0)} detections  last: {_fmt_date(w.get('last_detected'))}")

    # Recent prescriptions
    last_presc = await db.postgame_analyses.find(
        {"user_id": user_id, "coach_prescription": {"$exists": True, "$ne": None}},
        {"coach_prescription": 1, "prescription_type": 1, "prescription_reason": 1,
         "game_result": 1, "created_at": 1, "accuracy": 1, "_id": 0}
    ).sort("created_at", -1).to_list(5)
    if last_presc:
        print(f"  Last 5 prescriptions:")
        for p in last_presc:
            print(f"    {_fmt_date(p.get('created_at')):<10}  {(p.get('coach_prescription') or '?')[:24]:<24}  "
                  f"{p.get('game_result', '?'):<4}  acc={p.get('accuracy', 0):.0f}")

    # ── Engine 2 state ──
    _banner("Engine 2 — Build New Skills")
    if memory:
        skills = (memory.get("learning") or {}).get("skills") or []
        concepts = (memory.get("learning") or {}).get("concepts_mastered") or []
        openings = (memory.get("learning") or {}).get("openings_learned") or []
        traps = (memory.get("learning") or {}).get("traps_learned") or []
        endgames = (memory.get("learning") or {}).get("endgames_learned") or []

        if skills:
            print(f"  {'Skill':<28} {'Seen':>5} {'Corr':>5} {'Wrong':>5}  {'Last 5':<12}  Learned")
            for s in sorted(skills, key=lambda x: -x.get("seen", 0))[:12]:
                o = " ".join("✓" if x == "correct" else "✗" if x == "wrong" else "·"
                             for x in (s.get("outcomes") or [])[-5:])
                learned = "YES" if s.get("learned_at") else "—"
                print(f"  {(s.get('skill_id') or '?'):<28} {s.get('seen', 0):>5} {s.get('correct', 0):>5} "
                      f"{s.get('wrong', 0):>5}  {o:<12}  {learned}")
        else:
            print("  No skill attempts recorded yet. Run backfill_engine2_skills.py.")

        print(f"  Concepts mastered: {concepts or '(none)'}")
        print(f"  Openings learned:  {openings or '(none)'}")
        print(f"  Traps learned:     {traps or '(none)'}")
        print(f"  Endgames learned:  {endgames or '(none)'}")

        # Engine 2's current pick
        try:
            from services.engine2_skill_builder import pick_next_skill
            from services.coach_memory import get_or_create_memory
            mem_obj = await get_or_create_memory(db, user_id)
            rating = mem_obj.performance.best_performance_rating or 1000
            nxt = pick_next_skill(mem_obj, rating)
            if nxt:
                print(f"  Next pick:         {nxt['label']} (tier {nxt['tier']})")
                print(f"    reason:          {nxt['reason']}")
        except Exception as e:
            print(f"  Engine 2 pick error: {e}")

    # ── Engagement ──
    _banner("Engagement")
    coach_sessions = await db.coach_sessions.count_documents({"user_id": user_id})
    completed_sessions = await db.coach_sessions.count_documents({"user_id": user_id, "status": "completed"})
    coach_messages = await db.coach_messages.count_documents({"user_id": user_id})
    puzzle_attempts = await db.puzzle_attempts.count_documents({"user_id": user_id})
    puzzle_correct = await db.puzzle_attempts.count_documents({"user_id": user_id, "correct": True})
    notifications = await db.notifications.count_documents({"user_id": user_id})

    print(f"  Coach sessions:    {coach_sessions} total, {completed_sessions} completed")
    print(f"  Coach messages:    {coach_messages}")
    print(f"  Puzzle attempts:   {puzzle_attempts}  ({puzzle_correct} solved)")
    print(f"  Notifications:     {notifications}")

    # ── Gaps / recommendations ──
    _banner("Gaps detected")
    gaps = []
    if not memory:
        gaps.append("• No coach_memory — user hasn't had a game analyzed yet.")
    else:
        perf = memory.get("performance", {})
        if perf.get("best_performance_rating", 0) == 0:
            gaps.append("• best_performance_rating is 0 — run --backfill to set it from PGN Elo.")
        if not (memory.get("learning") or {}).get("current_focus") and games_analyzed > 0:
            gaps.append("• No current_focus despite analyzed games — curriculum brain may not have run. "
                        "Check analysis_worker PHASE 5.5.")
        if not ((memory.get("learning") or {}).get("skills") or []) and games_analyzed >= 5:
            gaps.append("• No Engine 2 skill attempts recorded. "
                        "Run: python scripts/backfill_engine2_skills.py " + user_id + " --limit 25 --reset")
    if games_total > 0 and games_analyzed == 0:
        gaps.append("• Games imported but none analyzed — check the analysis queue.")
    if chesscom_rating or lichess_rating:
        if pgn_rating and pgn_rating.get("rating", 0) > 0:
            platform_avg = (chesscom_rating or 0) + (lichess_rating or 0)
            platform_count = bool(chesscom_rating) + bool(lichess_rating)
            if platform_count:
                platform_avg = platform_avg / platform_count
                diff = abs(pgn_rating.get("rating", 0) - platform_avg)
                if diff > 200:
                    gaps.append(f"• Platform-reported rating ({platform_avg:.0f}) and PGN-inferred "
                                f"({pgn_rating.get('rating')}) diverge by {diff:.0f} — user may have "
                                f"multiple accounts or a stale profile rating.")
    if not gaps:
        print("  None detected. Data looks complete.")
    else:
        for g in gaps:
            print(f"  {g}")


# ─── BACKFILL ─────────────────────────────────────────────────────────


async def backfill_user(db, user_id: str):
    """Fill in derived fields that should exist but don't."""
    print(f"\nBackfilling {user_id}...")
    changed = []

    # 1. Compute PGN-inferred rating and set best_performance_rating if missing
    from services.coach_memory import get_user_rating_from_games, get_or_create_memory, _memory_to_doc

    rating_data = await get_user_rating_from_games(db, user_id)
    pgn_rating = rating_data.get("rating", 0)
    high_rating = rating_data.get("highest_rating", pgn_rating)

    memory = await get_or_create_memory(db, user_id)
    perf = memory.performance

    if not perf.best_performance_rating or perf.best_performance_rating < high_rating:
        old = perf.best_performance_rating
        perf.best_performance_rating = high_rating or pgn_rating
        changed.append(f"  best_performance_rating: {old} → {perf.best_performance_rating}")

    if not perf.worst_performance_rating:
        perf.worst_performance_rating = rating_data.get("lowest_rating", pgn_rating)
        changed.append(f"  worst_performance_rating: 0 → {perf.worst_performance_rating}")

    # 2. Compute games_played from actual games if zero
    if not perf.games_played:
        n = await db.games.count_documents({"user_id": user_id, "is_analyzed": True})
        if n:
            perf.games_played = n
            changed.append(f"  games_played: 0 → {n}")

    # 3. Cache the PGN rating on player_profiles so the community puzzle service finds it
    await db.player_profiles.update_one(
        {"user_id": user_id},
        {"$set": {
            "estimated_rating": pgn_rating,
            "current_rating": pgn_rating,
            "rating_source": rating_data.get("source"),
            "rating_trend": rating_data.get("rating_trend"),
            "rating_highest": rating_data.get("highest_rating"),
            "rating_games_analyzed": rating_data.get("games_analyzed"),
        }},
        upsert=True,
    )
    changed.append(f"  player_profiles.estimated_rating set to {pgn_rating}")

    # Save memory
    await db.coach_memory.update_one(
        {"user_id": user_id},
        {"$set": _memory_to_doc(memory)},
        upsert=True,
    )

    if changed:
        for c in changed:
            print(c)
    else:
        print("  Nothing to backfill — already populated.")


async def backfill_all(db):
    users = await db.users.find({}, {"user_id": 1, "_id": 0}).to_list(500)
    print(f"Backfilling {len(users)} users...")
    for u in users:
        await backfill_user(db, u["user_id"])


# ─── MAIN ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("user_id", nargs="?", help="Show detail for this user_id")
    parser.add_argument("--backfill", action="store_true", help="Backfill derived fields for the given user")
    parser.add_argument("--all-backfill", action="store_true", help="Backfill every user in the DB")
    args = parser.parse_args()

    async def run():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        print(f"DB: {DB_NAME}")

        if args.all_backfill:
            await backfill_all(db)
        elif args.user_id and args.backfill:
            await backfill_user(db, args.user_id)
        elif args.user_id:
            await show_player_detail(db, args.user_id)
        else:
            await show_all_players(db)

        client.close()

    asyncio.run(run())


if __name__ == "__main__":
    main()

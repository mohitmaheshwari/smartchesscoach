#!/usr/bin/env python3
"""
ChessGuru Diagnostics Tool
===========================
Run inside the backend container or from the project root.

Usage:
    python diagnostics.py
    
    # Or from host:
    docker exec -it chess-coach-backend python diagnostics.py
"""

import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta

# Try loading .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

DIVIDER = "=" * 60
SECTION = "-" * 40


def connect():
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client[DB_NAME]


def header(title):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def section(title):
    print(f"\n  {SECTION}")
    print(f"  {title}")
    print(f"  {SECTION}")


def check_stockfish():
    header("STOCKFISH ENGINE")
    paths = ["/usr/games/stockfish", "/usr/bin/stockfish", "/usr/local/bin/stockfish"]
    found = None
    for p in paths:
        if os.path.exists(p):
            found = p
            break

    if not found:
        try:
            result = subprocess.run(["which", "stockfish"], capture_output=True, text=True)
            if result.returncode == 0:
                found = result.stdout.strip()
        except Exception:
            pass

    if found:
        print(f"  Found: {found}")
        try:
            result = subprocess.run(
                [found], input="uci\nquit\n", capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines()[:3]:
                print(f"    {line}")
            print("  Status: WORKING")
        except Exception as e:
            print(f"  Status: ERROR - {e}")
    else:
        print("  Status: NOT FOUND")
        print("  Analysis will fail without Stockfish!")


def check_users(db):
    header("USERS")
    users = list(db.users.find({}, {"_id": 0, "user_id": 1, "name": 1, "email": 1,
                                     "chess_com_username": 1, "chesscom_username": 1,
                                     "lichess_username": 1, "role": 1}))
    print(f"  Total users: {len(users)}")
    for u in users:
        chess_com = u.get("chess_com_username") or u.get("chesscom_username") or "-"
        lichess = u.get("lichess_username") or "-"
        role = u.get("role", "user")
        name = u.get("name", "?")
        print(f"    {name} ({role})")
        print(f"      Chess.com: {chess_com}  |  Lichess: {lichess}")


def check_games(db):
    header("GAMES")
    total = db.games.count_documents({})
    analyzed_ids = set()
    for a in db.game_analyses.find({}, {"game_id": 1, "_id": 0}):
        analyzed_ids.add(a["game_id"])

    analyzed = 0
    not_analyzed = []
    for g in db.games.find({}, {"_id": 0, "game_id": 1, "user_id": 1, "imported_at": 1,
                                 "opponent_name": 1, "result": 1, "opening_name": 1}):
        if g["game_id"] in analyzed_ids:
            analyzed += 1
        else:
            not_analyzed.append(g)

    print(f"  Total games:    {total}")
    print(f"  Analyzed:       {analyzed}")
    print(f"  NOT analyzed:   {len(not_analyzed)}")

    if not_analyzed:
        section("Games waiting for analysis")
        for g in not_analyzed[:10]:
            opp = g.get("opponent_name", "?")
            res = g.get("result", "?")
            opening = g.get("opening_name", "?")
            imported = g.get("imported_at", "?")
            print(f"    {g['game_id'][:20]}  vs {opp}  {res}  {opening}")
            print(f"      Imported: {imported}")
        if len(not_analyzed) > 10:
            print(f"    ... and {len(not_analyzed) - 10} more")


def check_analysis_queue(db):
    header("ANALYSIS QUEUE")
    statuses = ["pending", "processing", "completed", "failed", "error"]
    counts = {}
    for s in statuses:
        counts[s] = db.analysis_queue.count_documents({"status": s})

    total = sum(counts.values())
    print(f"  Total jobs:     {total}")
    for s, c in counts.items():
        marker = " <<<" if (s in ("failed", "error") and c > 0) else ""
        marker = " <<< STUCK?" if (s == "processing" and c > 0) else marker
        print(f"    {s:12s}:  {c}{marker}")

    # Show failed jobs
    failed = list(db.analysis_queue.find(
        {"status": {"$in": ["failed", "error"]}},
        {"_id": 0, "game_id": 1, "error": 1, "updated_at": 1, "attempts": 1}
    ).sort("updated_at", -1).limit(5))

    if failed:
        section("Failed Jobs (most recent)")
        for f in failed:
            print(f"    Game: {f.get('game_id', '?')}")
            print(f"    Error: {f.get('error', 'unknown')}")
            print(f"    Attempts: {f.get('attempts', '?')}")
            print()

    # Show stuck processing jobs
    stuck = list(db.analysis_queue.find(
        {"status": "processing"},
        {"_id": 0, "game_id": 1, "started_at": 1, "claimed_at": 1}
    ).limit(5))

    if stuck:
        section("Stuck Processing Jobs")
        for s in stuck:
            started = s.get("started_at") or s.get("claimed_at") or "unknown"
            print(f"    Game: {s.get('game_id', '?')}  Started: {started}")


def check_recent_activity(db):
    header("RECENT ACTIVITY")

    # Last analyzed game
    last_analysis = db.game_analyses.find_one(
        {}, {"_id": 0, "game_id": 1, "created_at": 1},
        sort=[("created_at", -1)]
    )
    if last_analysis:
        print(f"  Last analysis:  {last_analysis.get('game_id', '?')}")
        print(f"    At: {last_analysis.get('created_at', '?')}")
    else:
        print("  Last analysis:  None")

    # Last imported game
    last_game = db.games.find_one(
        {}, {"_id": 0, "game_id": 1, "imported_at": 1, "opponent_name": 1},
        sort=[("imported_at", -1)]
    )
    if last_game:
        print(f"  Last import:    {last_game.get('game_id', '?')}")
        print(f"    At: {last_game.get('imported_at', '?')}")
    else:
        print("  Last import:    None")

    # Last queue activity
    last_queue = db.analysis_queue.find_one(
        {}, {"_id": 0, "game_id": 1, "status": 1, "updated_at": 1},
        sort=[("updated_at", -1)]
    )
    if last_queue:
        print(f"  Last queue job:  {last_queue.get('game_id', '?')} ({last_queue.get('status', '?')})")
        print(f"    At: {last_queue.get('updated_at', '?')}")


def check_player_profiles(db):
    header("PLAYER PROFILES")
    profiles = list(db.player_profiles.find({}, {
        "_id": 0, "user_id": 1, "estimated_elo": 1, "current_rating": 1,
        "games_analyzed_count": 1, "games_analyzed": 1, "updated_at": 1
    }))
    if not profiles:
        print("  No player profiles yet (need 3+ analyzed games)")
    for p in profiles:
        rating = p.get("estimated_elo") or p.get("current_rating", "?")
        games = p.get("games_analyzed_count") or p.get("games_analyzed", "?")
        print(f"  User: {p.get('user_id', '?')}")
        print(f"    Rating: {rating}  |  Games analyzed: {games}")
        print(f"    Updated: {p.get('updated_at', '?')}")


def suggest_fixes(db):
    header("SUGGESTED FIXES")

    pending = db.analysis_queue.count_documents({"status": "pending"})
    processing = db.analysis_queue.count_documents({"status": "processing"})
    failed = db.analysis_queue.count_documents({"status": {"$in": ["failed", "error"]}})

    total_games = db.games.count_documents({})
    total_analyses = db.game_analyses.count_documents({})
    in_queue = db.analysis_queue.count_documents({})

    games_not_in_queue = total_games - total_analyses - in_queue
    if games_not_in_queue < 0:
        games_not_in_queue = 0

    suggestions = []

    if processing > 0:
        suggestions.append(
            f"  {processing} job(s) stuck in 'processing'. Reset them:\n"
            f"    db.analysis_queue.updateMany({{status:'processing'}}, {{$set:{{status:'pending'}}}})"
        )

    if failed > 0:
        suggestions.append(
            f"  {failed} job(s) failed. Retry them:\n"
            f"    db.analysis_queue.updateMany({{status:{{$in:['failed','error']}}}}, {{$set:{{status:'pending', attempts:0}}}})"
        )

    if games_not_in_queue > 0:
        suggestions.append(
            f"  {games_not_in_queue} game(s) imported but never queued for analysis.\n"
            f"    Run: python requeue_missing.py --go"
        )

    if total_games == 0:
        suggestions.append(
            "  No games imported at all. Check:\n"
            "    1. Is Chess.com username correct? (check /api/auth/me)\n"
            "    2. Backend logs: docker logs chess-coach-backend | grep sync"
        )

    if not suggestions:
        print("  Everything looks healthy!")
    else:
        for s in suggestions:
            print(s)
            print()


def main():
    print()
    print(DIVIDER)
    print("  CHESSGURU DIAGNOSTICS")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(DIVIDER)
    print(f"  DB: {DB_NAME}")
    print(f"  Mongo: {MONGO_URL[:40]}...")

    try:
        db = connect()
        print("  Connection: OK")
    except Exception as e:
        print(f"  Connection: FAILED - {e}")
        sys.exit(1)

    check_stockfish()
    check_users(db)
    check_games(db)
    check_analysis_queue(db)
    check_recent_activity(db)
    check_player_profiles(db)
    suggest_fixes(db)

    print(f"\n{DIVIDER}")
    print("  DONE")
    print(DIVIDER)
    print()


if __name__ == "__main__":
    main()

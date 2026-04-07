"""
Debug script — run inside the backend Docker container to inspect coaching data.

Usage:
  docker exec -it chess-coach-backend python3 debug_coaching_data.py

This outputs everything needed to understand:
1. What games exist and their results
2. What cognitive_gaps are tagged per game
3. What game_reason_classifier would produce
4. What the root_problem selection logic picks
5. Why the homepage shows what it shows
"""

import os
import json
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

print(f"=== DATABASE: {DB_NAME} ===")
print(f"Games: {db.games.count_documents({})}")
print(f"Analyses: {db.game_analyses.count_documents({})}")
print(f"Training positions: {db.community_training_positions.count_documents({})}")
print(f"Solve attempts: {db.training_solve_attempts.count_documents({})}")
print()

# 1. All games with results
print("=== GAMES ===")
games = list(db.games.find({"is_analyzed": True}, {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "termination": 1, "opening": 1, "opponent_name": 1}).sort("imported_at", -1).limit(30))
for g in games:
    uc = g.get("user_color", "white")
    res = g.get("result", "")
    won = (res == "1-0" and uc == "white") or (res == "0-1" and uc == "black")
    lost = not won and "1/2" not in res
    label = "W" if won else ("D" if "1/2" in res else "L")
    term = g.get("termination", "?")
    print(f"  {g['game_id'][:12]}  {label}  term={term}  vs {g.get('opponent_name', '?')[:15]}  {g.get('opening', '')[:20]}")
print()

# 2. Cognitive gaps per game
print("=== COGNITIVE GAPS PER GAME (top 5 games) ===")
analyses = list(db.game_analyses.find({}, {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1}).sort("created_at", -1).limit(5))
for a in analyses:
    gid = a.get("game_id", "?")[:12]
    evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
    gaps = {}
    for e in evals:
        gap = e.get("cognitive_gap", "")
        cp = e.get("cp_loss", 0) or 0
        if gap and cp >= 100:
            gaps[gap] = gaps.get(gap, 0) + 1
    print(f"  {gid}: {json.dumps(gaps)}")
print()

# 3. Game reason classifier output
print("=== GAME REASON CLASSIFIER (all games) ===")
try:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    # Try importing from backend directory
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
        from services.game_reason_classifier import classify_game_reason, aggregate_game_reasons
    except ImportError:
        from game_reason_classifier import classify_game_reason, aggregate_game_reasons

    all_reasons = []
    all_analyses = list(db.game_analyses.find({}, {"_id": 0, "game_id": 1, "stockfish_analysis": 1}).sort("created_at", -1).limit(30))
    game_map = {}
    for g in db.games.find({"is_analyzed": True}, {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "termination": 1}):
        game_map[g["game_id"]] = g

    for a in all_analyses:
        gid = a.get("game_id", "")
        g = game_map.get(gid, {})
        sf = a.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        reason = classify_game_reason(
            move_evaluations=evals,
            game_result=g.get("result", ""),
            user_color=g.get("user_color", "white"),
            termination=g.get("termination", "unknown"),
            accuracy=sf.get("accuracy", 0),
        )
        all_reasons.append(reason)
        uc = g.get("user_color", "white")
        res = g.get("result", "")
        won = (res == "1-0" and uc == "white") or (res == "0-1" and uc == "black")
        label = "W" if won else ("D" if "1/2" in res else "L")
        print(f"  {gid[:12]}  {label}  → {reason['category']:25s}  \"{reason['label']}\"")

    print()
    print("=== AGGREGATED TOP 3 PROBLEMS ===")
    top = aggregate_game_reasons(all_reasons)
    for i, p in enumerate(top):
        print(f"  #{i+1}  {p['category']:25s}  {p['count']} games  \"{p['label']}\"")

except Exception as e:
    print(f"  ERROR: Could not run classifier: {e}")
    import traceback
    traceback.print_exc()

print()

# 4. Root problem selection (same logic as _build_lab_coaching)
print("=== ROOT PROBLEM SELECTION (from cognitive_gaps) ===")
pattern_scores = {}
for a in all_analyses:
    gid = a.get("game_id", "")
    g = game_map.get(gid, {})
    uc = g.get("user_color", "white")
    res = g.get("result", "")
    won = (res == "1-0" and uc == "white") or (res == "0-1" and uc == "black")
    is_draw = "1/2" in res
    is_loss = not won and not is_draw

    sf = a.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])

    # Check was_winning
    was_winning = False
    for e in evals:
        ev = e.get("eval_before", 0)
        user_ev = ev if uc == "white" else -ev
        if isinstance(user_ev, float) and abs(user_ev) < 100:
            user_ev = user_ev * 100
        if user_ev > 200:
            was_winning = True

    # Collect cognitive gaps
    gaps_in_game = set()
    for e in evals:
        gap = e.get("cognitive_gap", "")
        cp = e.get("cp_loss", 0) or 0
        if gap and cp >= 100:
            gaps_in_game.add(gap)

    for gap in gaps_in_game:
        if gap not in pattern_scores:
            pattern_scores[gap] = {"count": 0, "losses": 0, "thrown": 0}
        pattern_scores[gap]["count"] += 1
        if is_loss:
            pattern_scores[gap]["losses"] += 1
        if was_winning and is_loss:
            pattern_scores[gap]["thrown"] += 1

ranked = sorted(pattern_scores.items(), key=lambda x: (x[1]["thrown"] * 3 + x[1]["losses"] * 2 + x[1]["count"]), reverse=True)
for pat, data in ranked[:5]:
    score = data["thrown"] * 3 + data["losses"] * 2 + data["count"]
    print(f"  {pat:25s}  count={data['count']:2d}  losses={data['losses']:2d}  thrown={data['thrown']:2d}  score={score}")

if ranked:
    winner = ranked[0]
    print(f"\n  → ROOT PATTERN: {winner[0]}")
    print(f"  → This maps to HEADLINE: check HEADLINES['{winner[0]}'] in HomePage.jsx")
print()

# 5. What homepage would show
print("=== WHAT HOMEPAGE SHOWS ===")
if ranked:
    root_key = ranked[0][0]
    # Check if top_problems[0] overrides it
    if top:
        top_key = top[0]["category"]
        print(f"  topProblem.category = {top_key}")
        print(f"  root.pattern = {root_key}")
        print(f"  mistakeKey = topProblem?.category || root?.pattern = {top_key}")
        print(f"  → Homepage headline comes from: HEADLINES['{top_key}']")
    else:
        print(f"  No top_problems. Falls back to root.pattern = {root_key}")
        print(f"  → Homepage headline comes from: HEADLINES['{root_key}']")

print()
print("=== TERMINATION BREAKDOWN ===")
pipeline = [
    {"$group": {"_id": "$termination", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]
for doc in db.games.aggregate(pipeline):
    print(f"  {doc['_id'] or 'none':20s}  {doc['count']} games")

client.close()
print("\nDone.")

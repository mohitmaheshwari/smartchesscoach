#!/usr/bin/env python3
"""
Debug: Check per-game accuracy values.
Run inside the backend container:
  docker exec chess-coach-backend python3 debug_accuracy.py
"""

import os
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Get all analyzed games sorted by date
analyses = list(db.game_analyses.find(
    {},
    {"_id": 0, "game_id": 1, "stockfish_analysis.accuracy": 1,
     "stockfish_analysis.blunders": 1, "stockfish_analysis.mistakes": 1}
).sort("analyzed_at", -1))

print(f"Database: {DB_NAME}")
print(f"Total analyses found: {len(analyses)}")
print(f"{'='*60}")
print(f"{'#':<4} {'Game ID':<25} {'Accuracy':>8} {'Blunders':>8} {'Mistakes':>8}")
print(f"{'-'*60}")

accs = []
for i, a in enumerate(analyses):
    sf = a.get("stockfish_analysis", {}) or {}
    acc = sf.get("accuracy", 0) or 0
    blunders = sf.get("blunders", 0) or 0
    mistakes = sf.get("mistakes", 0) or 0
    gid = a.get("game_id", "?")
    accs.append(acc)
    marker = " <-- last 5" if i < 5 else ""
    print(f"{i+1:<4} {gid:<25} {acc:>7.1f}% {blunders:>8} {mistakes:>8}{marker}")

print(f"{'='*60}")

if accs:
    all_avg = sum(accs) / len(accs)
    last5_avg = sum(accs[:5]) / min(5, len(accs))
    print(f"All {len(accs)} games avg accuracy:  {all_avg:.1f}%")
    print(f"Last 5 games avg accuracy:    {last5_avg:.1f}%")
    print(f"Difference:                   {abs(last5_avg - all_avg):.1f}%")

    if abs(last5_avg - all_avg) < 0.5:
        print(f"\n⚠ The averages are nearly identical — this might be a coincidence")
        print(f"  or all games may have similar accuracy scores.")

    # Check if all accuracies are the same
    unique = set(round(a, 1) for a in accs)
    if len(unique) <= 3:
        print(f"\n🐛 BUG: Only {len(unique)} unique accuracy values found: {sorted(unique)}")
        print(f"  This suggests analysis is producing the same score for every game.")

client.close()

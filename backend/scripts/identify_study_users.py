#!/usr/bin/env python3
"""
Identify 20 candidate users for behavior validation study.

Criteria per scope:
  - At least 20 games analyzed in last 60 days (active)
  - ≥10 mistakes in assigned pattern (enough signal to measure)
  - Rating range: 600-1900 (target audience)
  - No puzzle solve rate >80% (we want to measure NEW training)

Sampling strategy:
  - 5 patterns: piece_safety, missed_tactic, king_safety, time_pressure, calculation_depth
  - 4 users per pattern (5 × 4 = 20)
  - Assign based on highest mistake count in that pattern
  - Block: if user doesn't have ≥10 mistakes, skip to next candidate
"""

import os
import asyncio
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict

PATTERNS = [
    "piece_safety",
    "missed_tactic",
    "king_safety",
    "time_pressure",
    "calculation_depth",
]

MIN_GAMES_LAST_60_DAYS = 20
MIN_MISTAKES_IN_PATTERN = 10
RATING_MIN = 600
RATING_MAX = 1900
MAX_PUZZLE_SOLVE_RATE = 0.80
USERS_PER_PATTERN = 4
TARGET_USERS = len(PATTERNS) * USERS_PER_PATTERN  # 20


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "test_database")
    ]

    print("=" * 80)
    print("BEHAVIOR VALIDATION STUDY: USER IDENTIFICATION")
    print("=" * 80)
    print(f"\nTarget: {TARGET_USERS} users ({USERS_PER_PATTERN} per pattern)")
    print(f"Patterns: {', '.join(PATTERNS)}\n")

    # Get all active users with recent games
    sixty_days_ago = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    active_users = await db.games.distinct(
        "user_id",
        {
            "is_analyzed": True,
            "date_played": {"$gte": sixty_days_ago},
        },
    )

    print(f"Found {len(active_users)} active users (20+ games in last 60 days)\n")

    # For each user, count mistakes per pattern
    user_pattern_mistakes = defaultdict(lambda: defaultdict(int))
    user_ratings = {}
    user_puzzle_stats = {}

    for user_id in active_users:
        # Get user rating
        user_doc = await db.users.find_one(
            {"user_id": user_id}, {"_id": 0, "rating": 1}
        )
        if not user_doc:
            continue
        rating = user_doc.get("rating")
        if rating is None or rating < RATING_MIN or rating > RATING_MAX:
            continue

        user_ratings[user_id] = rating

        # Get games analyzed for this user in last 60 days
        user_games = await db.games.distinct(
            "game_id",
            {
                "user_id": user_id,
                "is_analyzed": True,
                "date_played": {"$gte": sixty_days_ago},
            },
        )

        if len(user_games) < MIN_GAMES_LAST_60_DAYS:
            continue

        # Count mistakes per pattern
        analyses = await db.game_analyses.find(
            {"game_id": {"$in": user_games}}
        ).to_list(None)

        for analysis in analyses:
            for move_eval in analysis.get("stockfish_analysis", {}).get(
                "move_evaluations", []
            ):
                # Only count user moves (not opponent)
                if move_eval.get("is_opponent_move"):
                    continue

                gap = move_eval.get("cognitive_gap")
                if gap in PATTERNS:
                    user_pattern_mistakes[user_id][gap] += 1

        # Get puzzle solve stats
        puzzle_attempts = await db.puzzle_attempts.find(
            {"user_id": user_id}
        ).to_list(None)
        if puzzle_attempts:
            n_solved = sum(1 for a in puzzle_attempts if a.get("correct"))
            solve_rate = n_solved / len(puzzle_attempts)
            user_puzzle_stats[user_id] = solve_rate

    print(f"Found {len(user_ratings)} users with valid ratings in range\n")

    # Assignment loop: 4 users per pattern
    assignments = {pattern: [] for pattern in PATTERNS}
    used_users = set()

    for pattern in PATTERNS:
        print(f"\n{pattern.upper()}:")
        print(f"  Candidates with ≥{MIN_MISTAKES_IN_PATTERN} mistakes:")

        # Rank users by mistake count in this pattern
        candidates = [
            (uid, user_pattern_mistakes[uid][pattern])
            for uid in user_ratings.keys()
            if uid not in used_users
            and user_pattern_mistakes[uid][pattern] >= MIN_MISTAKES_IN_PATTERN
        ]
        candidates.sort(key=lambda x: -x[1])  # Sort descending by mistake count

        # Take first 4 candidates
        for i, (user_id, n_mistakes) in enumerate(candidates[:USERS_PER_PATTERN]):
            rating = user_ratings[user_id]
            puzzle_rate = user_puzzle_stats.get(user_id, 0.0)
            assignments[pattern].append(user_id)
            used_users.add(user_id)

            print(
                f"    {i+1}. {user_id:25} "
                f"rating={rating:4d} mistakes={n_mistakes:3d} puzzle_rate={puzzle_rate:.1%}"
            )

        if len(assignments[pattern]) < USERS_PER_PATTERN:
            print(
                f"    ⚠️  Only found {len(assignments[pattern])} candidates "
                f"(need {USERS_PER_PATTERN})"
            )

    # Summary
    total_assigned = sum(len(users) for users in assignments.values())
    print(f"\n" + "=" * 80)
    print(f"SUMMARY: {total_assigned}/{TARGET_USERS} users assigned")
    print("=" * 80)

    for pattern in PATTERNS:
        print(f"  {pattern:20} {len(assignments[pattern])}/4")

    if total_assigned == TARGET_USERS:
        print("\n✅ SUCCESS: All 20 users identified!\n")

        # Print assignment table for copy-paste
        print("Assignment Table:")
        print(
            "Pattern            | User IDs                      "
            "| Rating | Mistakes | Puzzle %"
        )
        print("-" * 80)
        for pattern in PATTERNS:
            for user_id in assignments[pattern]:
                rating = user_ratings[user_id]
                mistakes = user_pattern_mistakes[user_id][pattern]
                puzzle_rate = user_puzzle_stats.get(user_id, 0.0)
                print(
                    f"{pattern:18} | {user_id:30} | {rating:6d} | {mistakes:8d} | {puzzle_rate:7.1%}"
                )

    else:
        print(
            f"\n⚠️  WARNING: Only {total_assigned} users found (need {TARGET_USERS})\n"
        )


if __name__ == "__main__":
    asyncio.run(main())

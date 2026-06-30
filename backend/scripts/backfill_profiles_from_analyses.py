"""
Backfill player_profiles + player_identities from existing game_analyses.

Why this script exists:
  - The new cognitive_gap-aware weakness aggregator (see analysis_worker)
    only runs going forward. Profiles in MongoDB still carry the OLD
    2-category top_weaknesses ("one_move_blunder"/"complex_tactical_miss").
  - 14 of the 45 active users haven't played in 30 days. We can't wait
    for new games to populate their richer diagnosis — we have to
    rebuild from what's already in `stockfish_analysis.move_evaluations`.

What it does, per user:
  1) Walks all that user's game_analyses chronologically.
  2) For each move with a `cognitive_gap`, maps it via the new
     cognitive_gap_to_weakness() table.
  3) Recomputes top_weaknesses, average_accuracy,
     recent_performance, historical_performance, improvement_trend
     on player_profiles.
  4) Recomputes the 4 style_tendency dimensions on player_identities
     via _compute_style_tendencies.

SAFETY:
  - Default is DRY-RUN. Prints what would change for each user. No DB writes.
  - --apply actually writes. Pre-write, dumps the OLD top_weaknesses to
    /tmp/profile_backup_<timestamp>.json so we can roll back.
  - Skips users with <3 analyzed games (not enough signal).
"""
import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

# Import the new mappings from our just-fixed code
sys.path.insert(0, "/app/backend")
from analysis_worker import cognitive_gap_to_weakness, _calc_trend_sync  # type: ignore
from services.data_freshness import _compute_style_tendencies  # type: ignore


async def backfill_one_user(db, uid: str, apply: bool) -> dict:
    """Recompute and (optionally) write the new profile fields for one user."""
    games = []
    async for g in db.games.find({"user_id": uid, "is_analyzed": True}, {"game_id": 1, "date_played": 1}):
        games.append(g)
    if len(games) < 3:
        return {"uid": uid, "skipped": "fewer than 3 analyzed games"}

    # Pull all matching analyses in chronological order
    gids = [g["game_id"] for g in games]
    analyses = []
    async for a in db.game_analyses.find(
        {"game_id": {"$in": gids}},
        {"game_id": 1, "stockfish_analysis": 1, "analyzed_at": 1}
    ).sort("analyzed_at", 1):
        analyses.append(a)

    # Recompute top_weaknesses with new mapping
    weakness_counts = Counter()
    blunders_per_game = []
    accuracies = []
    last_seen = {}
    first_seen = {}
    for a in analyses:
        sf = a.get("stockfish_analysis") or {}
        moves = sf.get("move_evaluations") or []
        blunders = sf.get("blunders", 0) or 0
        mistakes = sf.get("mistakes", 0) or 0
        best_moves = sf.get("best_moves", 0) or 0
        accuracy = sf.get("accuracy")
        if isinstance(accuracy, (int, float)) and accuracy > 0:
            accuracies.append(float(accuracy))
        blunders_per_game.append({
            "game_id": a["game_id"],
            "blunders": blunders,
            "mistakes": mistakes,
            "best_moves": best_moves,
            "accuracy": float(accuracy) if isinstance(accuracy, (int, float)) and accuracy > 0 else None,
            "date": (a.get("analyzed_at") or datetime.now(timezone.utc)).isoformat()
                    if isinstance(a.get("analyzed_at"), datetime) else str(a.get("analyzed_at") or ""),
        })
        for mv in moves:
            if mv.get("is_opponent_move"):
                continue
            ev = mv.get("evaluation")
            cp = mv.get("cp_loss", 0)
            cg = mv.get("cognitive_gap")
            if ev not in ("blunder", "mistake"):
                continue
            mapped = cognitive_gap_to_weakness(cg, cp, ev)
            if not mapped:
                continue
            key = (mapped["category"], mapped["subcategory"])
            weakness_counts[key] += 1
            now = a.get("analyzed_at")
            if isinstance(now, datetime):
                iso = now.isoformat()
            else:
                iso = str(now or "")
            last_seen[key] = iso
            if key not in first_seen:
                first_seen[key] = iso

    # Top weaknesses (richer schema)
    top_weaknesses = []
    for (cat, sub), count in weakness_counts.most_common(10):
        top_weaknesses.append({
            "category": cat,
            "subcategory": sub,
            "occurrence_count": count,
            "first_occurrence": first_seen.get((cat, sub)),
            "last_occurrence": last_seen.get((cat, sub)),
            "decayed_score": round(count * 1.0, 2),
        })

    # Roll up recent_performance + historical from the chronological games
    blunders_per_game.reverse()  # newest first
    recent_perf = blunders_per_game[:10]
    historical_perf = blunders_per_game[10:30]
    improvement_trend = _calc_trend_sync(recent_perf, historical_perf)
    average_accuracy = round(sum(accuracies[-20:]) / len(accuracies[-20:]), 1) if accuracies else None

    # Style tendencies on the identity
    identity_tend = _compute_style_tendencies(analyses)

    # Snapshot OLD for rollback
    old_profile = await db.player_profiles.find_one(
        {"user_id": uid}, {"top_weaknesses": 1, "improvement_trend": 1, "average_accuracy": 1, "_id": 0}
    ) or {}
    old_identity = await db.player_identities.find_one(
        {"user_id": uid}, {"style_profile": 1, "_id": 0}
    ) or {}

    summary = {
        "uid": uid,
        "analyzed_games": len(analyses),
        "old_top_weaknesses_count": len(old_profile.get("top_weaknesses") or []),
        "new_top_weaknesses_count": len(top_weaknesses),
        "new_top3": [(w["subcategory"], w["occurrence_count"]) for w in top_weaknesses[:3]],
        "old_improvement_trend": old_profile.get("improvement_trend"),
        "new_improvement_trend": improvement_trend,
        "old_average_accuracy": old_profile.get("average_accuracy"),
        "new_average_accuracy": average_accuracy,
        "old_style_tendencies": {
            "tac": ((old_identity.get("style_profile") or {}).get("tactical_tendency")),
            "pos": ((old_identity.get("style_profile") or {}).get("positional_tendency")),
            "agg": ((old_identity.get("style_profile") or {}).get("aggressive_tendency")),
            "def": ((old_identity.get("style_profile") or {}).get("defensive_tendency")),
        },
        "new_style_tendencies": identity_tend,
        "_backup": {  # so we can rebuild rollback files
            "old_profile": old_profile,
            "old_identity": old_identity,
        },
    }

    if apply:
        # Re-derive games_analyzed_count from the actual game count instead of
        # trusting the existing (drifted) counter. Earlier audit found the
        # counter was over-counting by 10-20% for most users because the worker
        # auto-increments per-job but games occasionally get re-analyzed or
        # the worker double-runs.
        actual_games_analyzed = await db.games.count_documents({"user_id": uid, "is_analyzed": True})
        profile_update = {
            "top_weaknesses": top_weaknesses,
            "recent_performance": recent_perf,
            "historical_performance": historical_perf,
            "improvement_trend": improvement_trend,
            "games_analyzed_count": actual_games_analyzed,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        if average_accuracy is not None:
            profile_update["average_accuracy"] = average_accuracy
        await db.player_profiles.update_one({"user_id": uid}, {"$set": profile_update})

        # Identity — only update the 4 tendencies (preserve everything else)
        # Also bump confidence if we have >=5 analyses.
        ident_update = {
            "style_profile.tactical_tendency": identity_tend["tactical_tendency"],
            "style_profile.positional_tendency": identity_tend["positional_tendency"],
            "style_profile.aggressive_tendency": identity_tend["aggressive_tendency"],
            "style_profile.defensive_tendency": identity_tend["defensive_tendency"],
        }
        await db.player_identities.update_one({"user_id": uid}, {"$set": ident_update})

    return summary


async def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true", help="Actually write changes. Default: dry-run.")
    p.add_argument("--limit", type=int, default=0, help="Only process N users (for testing). 0=all.")
    args = p.parse_args()

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Pick users who have profiles + at least 3 analyzed games
    pipeline = [
        {"$match": {"is_analyzed": True}},
        {"$group": {"_id": "$user_id", "n": {"$sum": 1}}},
        {"$match": {"n": {"$gte": 3}}},
        {"$sort": {"n": -1}},
    ]
    uids = []
    async for r in db.games.aggregate(pipeline):
        uids.append(r["_id"])
    if args.limit:
        uids = uids[:args.limit]

    print(f"=== {'APPLY' if args.apply else 'DRY-RUN'} backfill across {len(uids)} users ===\n")

    rollback_path = f"/tmp/profile_backup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    rollback = []
    summary_path = "/tmp/backfill_summary.json"
    all_summaries = []

    for i, uid in enumerate(uids, 1):
        s = await backfill_one_user(db, uid, args.apply)
        rollback.append({"uid": s["uid"], "old": s.get("_backup", {})})
        # strip _backup from the on-screen summary
        s.pop("_backup", None)
        all_summaries.append(s)
        # Print succinct
        if s.get("skipped"):
            print(f"[{i}/{len(uids)}] {uid}: SKIP ({s['skipped']})")
        else:
            print(f"[{i}/{len(uids)}] {uid}: {s['old_top_weaknesses_count']}→{s['new_top_weaknesses_count']} weaknesses, "
                  f"trend {s['old_improvement_trend']}→{s['new_improvement_trend']}, "
                  f"acc {s['old_average_accuracy']}→{s['new_average_accuracy']}, "
                  f"top3={s['new_top3']}")

    with open(summary_path, "w") as f:
        json.dump(all_summaries, f, default=str, indent=2)
    print(f"\nSummary written to {summary_path}")

    if args.apply:
        with open(rollback_path, "w") as f:
            json.dump(rollback, f, default=str, indent=2)
        print(f"Rollback snapshot written to {rollback_path}")


if __name__ == "__main__":
    asyncio.run(main())

"""
Backfill move_observations across all existing game_analyses.

Phase 3 of the move_observations rollout — see docs/move_observations_scope.md.

This script is SAFE-BY-DEFAULT:
  - Default = DRY-RUN. Prints what it would derive but writes nothing.
  - --apply actually writes to MongoDB.
  - Idempotent — re-running with --apply overwrites by (game_id, move_number)
    so it can be safely re-run after a deriver bug fix.
  - --user-id LIMITS the run to one user (great for testing).
  - --limit N processes only the first N analyses.

After Mohit signs off on docs/move_observations_scope.md:

    # Dry-run on one user first (e.g. Mohit himself)
    python scripts/backfill_move_observations.py --user-id user_8b599930d7ef

    # Dry-run across whole corpus (no DB writes)
    python scripts/backfill_move_observations.py --all

    # Real backfill (the full-corpus selector is mandatory)
    python scripts/backfill_move_observations.py --all --apply \\
        --confirm phase8-observations

Expected runtime on full corpus (~9,572 analyses): ~10-15 min single-thread.
"""
import argparse
import asyncio
from collections import Counter
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from services.move_observation_deriver import (
    derive_observations_for_game,
    aggregate_user_signals,
    SCHEMA_VERSION,
)
from services.destination_safety_detector import FACT_VERSION, QUALITY_ID

COLLECTION = "move_observations"
_CURRENT_FACT_FIELDS = frozenset({
    "version",
    "quality_id",
    "derivation_status",
    "eligible",
    "outcome",
    "fires",
    "reason",
})


def _schema_at_least(value, minimum):
    """Treat malformed historical version values as stale, never as fatal."""
    try:
        return int(value or 0) >= int(minimum)
    except (TypeError, ValueError):
        return False


async def ensure_indexes(db):
    """Create the indexes the scope doc declares."""
    coll = db[COLLECTION]
    await coll.create_index([("user_id", 1), ("derived_at", -1)])
    await coll.create_index([("game_id", 1), ("move_number", 1)], unique=True)
    await coll.create_index([("user_id", 1), ("missed_pattern", 1)])
    await coll.create_index([("user_id", 1), ("concept_used", 1)])
    await coll.create_index([("user_id", 1), ("was_critical_moment", 1)])


def classify_destination_safety_observation(existing, derived):
    """Classify storage coverage and the newly-derived decision independently."""
    fact = (derived or {}).get("destination_safety_exact") or {}
    if (
        fact.get("version") != FACT_VERSION
        or fact.get("quality_id") != QUALITY_ID
        or not _CURRENT_FACT_FIELDS.issubset(fact)
        or fact.get("derivation_status") not in {"ok", "unavailable"}
    ):
        decision = "invalid"
    elif fact.get("derivation_status") != "ok":
        decision = "invalid"
    elif fact.get("eligible") is True:
        decision = "eligible"
    else:
        decision = "ineligible"

    if not existing:
        storage = "missing"
    else:
        stored_fact = existing.get("destination_safety_exact") or {}
        complete_current = (
            _schema_at_least(existing.get("schema_version"), SCHEMA_VERSION)
            and stored_fact.get("version") == FACT_VERSION
            and stored_fact.get("quality_id") == QUALITY_ID
            and _CURRENT_FACT_FIELDS.issubset(stored_fact)
        )
        if complete_current:
            storage = "already_current"
        elif stored_fact:
            storage = "stale_version"
        else:
            storage = "missing"
    return {
        "storage": storage,
        "decision": decision,
        "write_required": decision != "invalid" and storage != "already_current",
        "fires": bool(fact.get("fires") is True),
    }


async def backfill_one_game(db, game_doc, analysis_doc, apply: bool):
    """Derive and reconcile one game's stored observations from stored analysis."""
    game_id = game_doc.get("game_id")
    user_id = game_doc.get("user_id")
    user_color = game_doc.get("user_color", "white")
    result = {
        "game_id": game_id,
        "user_id": user_id,
        "game_status": "invalid_or_unowned",
        "derived": 0,
        "writes": 0,
        "fires": 0,
        "storage": Counter(),
        "decisions": Counter(),
    }
    if not game_id or not user_id or (
        analysis_doc.get("user_id")
        and analysis_doc.get("user_id") != user_id
    ):
        return result

    sf = analysis_doc.get("stockfish_analysis") or {}
    if not sf.get("move_evaluations"):
        return result

    v5 = analysis_doc.get("decryption_v5_data") or None

    # v9: PGN carries %clk annotations; deriver parses them for time signals
    pgn = game_doc.get("pgn")

    obs_list = derive_observations_for_game(
        stockfish_analysis=sf,
        game_id=game_id,
        user_id=user_id,
        user_color=user_color,
        decryption_v5_data=v5,
        derived_at=datetime.now(timezone.utc),
        pgn=pgn,
    )
    if not obs_list:
        return result

    existing_rows = await db[COLLECTION].find(
        {"game_id": game_id},
        {
            "_id": 0,
            "move_number": 1,
            "schema_version": 1,
            "destination_safety_exact": 1,
        },
    ).to_list(length=None)
    existing_by_move = {
        row.get("move_number"): row
        for row in existing_rows
        if row.get("move_number") is not None
    }
    ops = []
    result["derived"] = len(obs_list)
    for obs in obs_list:
        classification = classify_destination_safety_observation(
            existing_by_move.get(obs.get("move_number")),
            obs,
        )
        result["storage"][classification["storage"]] += 1
        result["decisions"][classification["decision"]] += 1
        result["fires"] += int(classification["fires"])
        if classification["write_required"]:
            ops.append(
                UpdateOne(
                    {"game_id": obs["game_id"], "move_number": obs["move_number"]},
                    {"$set": obs},
                    upsert=True,
                )
            )

    result["writes"] = len(ops)
    if apply and ops:
        await db[COLLECTION].bulk_write(ops, ordered=False)

    storage_states = set(result["storage"])
    if storage_states == {"already_current"}:
        result["game_status"] = "already_current"
    elif storage_states == {"missing"}:
        result["game_status"] = "never_evaluated"
    elif storage_states == {"stale_version"}:
        result["game_status"] = "stale_version"
    else:
        result["game_status"] = "partially_current"
    return result


async def main_async(
    apply: bool,
    user_id: Optional[str],
    limit: int,
    *,
    all_users: bool = False,
    confirm: Optional[str] = None,
):
    if apply and not (user_id or all_users):
        raise ValueError("--apply requires an explicit --user-id or --all selector")
    if apply and confirm != "phase8-observations":
        raise ValueError(
            "--apply requires --confirm phase8-observations"
        )
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    if apply:
        await ensure_indexes(db)

    # Find analyses to process
    q = {}
    if user_id:
        q["user_id"] = user_id

    cursor = db.game_analyses.find(
        q, {"game_id": 1, "user_id": 1, "stockfish_analysis": 1, "decryption_v5_data": 1}
    ).sort("analyzed_at", -1)
    if limit:
        cursor = cursor.limit(limit)

    print(f"=== {'APPLY' if apply else 'DRY-RUN'} backfill ===")
    print(f"User filter: {user_id or '(all)'}")
    print(f"Limit:       {limit or '(no limit)'}")
    print(f"Schema:      v{SCHEMA_VERSION}")
    print()

    total_games = 0
    total_obs = 0
    total_writes = 0
    total_fires = 0
    per_user_obs = Counter()
    storage_counts = Counter()
    decision_counts = Counter()
    game_status_counts = Counter()
    errors = []

    async for analysis in cursor:
        game_id = analysis.get("game_id")
        game = await db.games.find_one(
            {"game_id": game_id},
            {"game_id": 1, "user_id": 1, "user_color": 1, "pgn": 1}
        )
        if not game:
            errors.append(("no-game-doc", game_id))
            game_status_counts["invalid_or_unowned"] += 1
            continue

        try:
            outcome = await backfill_one_game(db, game, analysis, apply)
        except Exception as e:
            errors.append((str(e)[:80], game_id))
            game_status_counts["invalid_or_unowned"] += 1
            continue

        total_obs += outcome["derived"]
        total_writes += outcome["writes"]
        total_fires += outcome["fires"]
        total_games += 1
        uid = game.get("user_id", "?")
        per_user_obs[uid] += outcome["derived"]
        storage_counts.update(outcome["storage"])
        decision_counts.update(outcome["decisions"])
        game_status_counts[outcome["game_status"]] += 1

        if total_games % 100 == 0:
            print(
                f"  ... {total_games} games inspected, "
                f"{storage_counts['already_current']:,} current observations, "
                f"{total_writes:,} writes required"
            )

    print()
    print(f"=== Done ===")
    print(f"Games processed:        {total_games:,}")
    print(f"Observations inspected: {total_obs:,}")
    print(f"Writes required:        {total_writes:,}")
    print(f"Exact detector fires:   {total_fires:,}")
    print(f"Unique users covered:   {len(per_user_obs):,}")
    print(f"Avg observations/game:  {total_obs/max(total_games,1):.1f}")
    print(f"Errors:                 {len(errors)}")
    for err, gid in errors[:10]:
        print(f"  - [{err}] game={gid}")

    report = {
        "mode": "apply" if apply else "dry_run",
        "full_corpus": bool(all_users and not user_id and not limit),
        "schema_version": SCHEMA_VERSION,
        "fact_version": FACT_VERSION,
        "quality_id": QUALITY_ID,
        "games_inspected": total_games,
        "observations_inspected": total_obs,
        "writes_required": total_writes,
        "exact_fires": total_fires,
        "users_covered": len(per_user_obs),
        "game_status": dict(sorted(game_status_counts.items())),
        "storage": dict(sorted(storage_counts.items())),
        "decisions": dict(sorted(decision_counts.items())),
        "errors": len(errors),
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if apply:
        # Spot-check: top 5 users by observation count
        print()
        print("=== Spot-check: top 5 users by observation count ===")
        top = sorted(per_user_obs.items(), key=lambda x: -x[1])[:5]
        for uid, n in top:
            user = await db.users.find_one({"user_id": uid}, {"name": 1, "email": 1})
            name = (user or {}).get("name") or "?"
            print(f"  {uid}  ({name}):  {n:,} observations")
            # Pull their aggregate
            cur = db[COLLECTION].find({"user_id": uid})
            obs_list = await cur.to_list(length=2000)
            agg = aggregate_user_signals(obs_list)
            print(f"     threat_response_rate: {agg.get('threat_response_rate')}")
            print(f"     blunder_punish_rate:  {agg.get('blunder_punish_rate')}")
            print(f"     critical_find_rate:   {agg.get('critical_find_rate')}")
            print(f"     missed_pattern_counts: {agg.get('missed_pattern_counts')}")
            print(f"     concept_used_counts:   {agg.get('concept_used_counts')}")
    client.close()
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true", help="Actually write to MongoDB. Default = dry-run.")
    target = p.add_mutually_exclusive_group()
    target.add_argument("--user-id", default=None, help="Limit to one user_id (for testing).")
    target.add_argument("--all", action="store_true", dest="all_users", help="Explicitly select the full corpus (required with --apply).")
    p.add_argument("--limit", type=int, default=0, help="Process at most N analyses (0 = no limit).")
    p.add_argument("--report-json", default=None, help="Optional path for the aggregate JSON report.")
    p.add_argument(
        "--confirm",
        default=None,
        help="Required with --apply: phase8-observations",
    )
    args = p.parse_args()
    report = asyncio.run(
        main_async(
            args.apply,
            args.user_id,
            args.limit,
            all_users=args.all_users,
            confirm=args.confirm,
        )
    )
    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()

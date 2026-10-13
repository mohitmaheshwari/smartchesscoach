#!/usr/bin/env python3
"""How many positions carry the forced_mate drill label, and out of how many?

Reads only. Three measurements, each with its denominator printed:

  1. the stored pools -- how many rows a `forced_mate` request can reach, and
     how many the pre-change query shape reached (the positive/negative pair
     that shows the clause is selective rather than empty or total);
  2. a pinned sample of analyzed games replayed through the extraction gates
     and the real admission pipeline, so the forward-looking rate is measured
     rather than extrapolated from the stored pools;
  3. the pools that must NOT change -- `missed_tactic` with the old and new
     query shapes, because `forced_mate` is a narrower request and taking
     rows out of an existing pool would be a worse bug than the one fixed.

The sample is PINNED to a file (`--sample`, default /tmp/<name>.json) and
reused on later runs, so a before/after comparison is over the same games.
Delete the file or pass --repin to choose a new one.

Usage inside the backend container:
    python scripts/measure_forced_mate_label.py --games 500
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import chess  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.puzzle_extraction_service import (  # noqa: E402
    FORCED_MATE_PATTERN,
    FORCED_MATE_QUALITY_IDS,
    _is_puzzle_worthy,
    minimum_extraction_cp_loss,
    pattern_pool_clause,
    stored_pattern_label,
    verified_issue_type,
    verified_mongo_clause,
)
from services.verified_puzzle_admission import AdmissionStatus  # noqa: E402
from services.verified_puzzle_builder import build_imported_game_verdict  # noqa: E402

DEFAULT_SAMPLE = "/tmp/forced_mate_label_sample.json"
MATE_QIDS = set(FORCED_MATE_QUALITY_IDS)


async def pin_sample(db, path: str, wanted: int) -> dict:
    """Choose games deterministically so two runs measure the same thing."""
    population = await db.game_analyses.count_documents(
        {"stockfish_analysis.move_evaluations.0": {"$exists": True}}
    )
    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations.0": {"$exists": True}},
        {"_id": 0, "game_id": 1, "user_id": 1},
    ).sort("game_id", 1).limit(wanted)
    games = [
        {"game_id": row["game_id"], "user_id": row.get("user_id")}
        async for row in cursor
    ]
    sample = {
        "selector": "game_analyses with >=1 move_evaluation, sorted by game_id asc",
        "requested": wanted,
        "pinned": len(games),
        "population_with_evaluations": population,
        "games": games,
    }
    Path(path).write_text(json.dumps(sample, indent=1))
    return sample


async def measure_pools(db) -> None:
    pool = db.community_puzzles
    total = await pool.count_documents({})
    reachable = await pool.count_documents({
        **pattern_pool_clause(FORCED_MATE_PATTERN),
        **verified_mongo_clause(FORCED_MATE_PATTERN),
    })
    old_shape = await pool.count_documents({"issue_type": FORCED_MATE_PATTERN})
    print("community_puzzles")
    print(f"  DENOMINATOR (all rows)                : {total}")
    print(f"  reachable as '{FORCED_MATE_PATTERN}'            : {reachable}")
    print(f"  reachable by the old query shape      : {old_shape}"
          "   <- 0 is the bug this label fixes")
    if not 0 < reachable < total:
        print("  !! the clause is not selective -- stop and look at it")

    # The pool that must not shrink.
    old_mt = await pool.count_documents({
        "issue_type": "missed_tactic", "approved": True,
        **verified_mongo_clause("missed_tactic"),
    })
    new_mt = await pool.count_documents({
        "approved": True, **pattern_pool_clause("missed_tactic"),
        **verified_mongo_clause("missed_tactic"),
    })
    mates_in_mt = await pool.count_documents({
        "issue_type": "missed_tactic", "approved": True,
        **verified_mongo_clause("missed_tactic"),
        "verified_admission.quality_id": {"$in": list(MATE_QIDS)},
    })
    print(f"  missed_tactic pool, old shape         : {old_mt}")
    print(f"  missed_tactic pool, new shape         : {new_mt}"
          f"   {'(unchanged)' if old_mt == new_mt else '!! CHANGED'}")
    print(f"  ...of which are the mates, still there: {mates_in_mt}")

    # The second pool, read in Python because this collection answers only
    # exact-match queries reliably.
    pwc = db.community_training_positions
    pwc_total = await pwc.count_documents({})
    rows = await pwc.find(
        {}, {"_id": 0, "pattern_type": 1, "verified_admission.quality_id": 1},
    ).to_list(None)
    pwc_mate = [
        row for row in rows
        if ((row.get("verified_admission") or {}).get("quality_id")) in MATE_QIDS
    ]
    print("community_training_positions")
    print(f"  DENOMINATOR (all rows)                : {pwc_total}")
    print(f"  proven mates                          : {len(pwc_mate)}")
    print("  their pattern_type                    : "
          f"{dict(collections.Counter(r.get('pattern_type') for r in pwc_mate))}")


async def measure_extraction(db, sample: dict, games_used: int) -> None:
    games = sample["games"][:games_used]
    print("\nFRESH EXTRACTION over the pinned sample")
    print(f"  sample selector      : {sample['selector']}")
    print(f"  pinned / population  : {sample['pinned']} of "
          f"{sample['population_with_evaluations']}")
    print(f"  DENOMINATOR (games)  : {len(games)}")

    ratings: dict = {}
    moves_seen = candidates = admitted = passed_floor = 0
    labels: collections.Counter = collections.Counter()
    drill_labels: collections.Counter = collections.Counter()
    mate_in: collections.Counter = collections.Counter()
    started = time.time()

    for index, entry in enumerate(games):
        game_id, user_id = entry["game_id"], entry["user_id"]
        analysis = await db.game_analyses.find_one(
            {"game_id": game_id, "user_id": user_id}, {"_id": 0})
        game = await db.games.find_one(
            {"game_id": game_id},
            {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1,
             "opening": 1, "opening_eco": 1})
        if not analysis or not game:
            continue
        if user_id not in ratings:
            doc = await db.users.find_one({"user_id": user_id},
                                          {"_id": 0, "rating": 1})
            ratings[user_id] = (doc or {}).get("rating", 1200)
        rating = int(ratings[user_id] or 1200)
        floor = minimum_extraction_cp_loss(rating)
        user_color = str(game.get("user_color", "white")).lower()

        for evaluation in (analysis.get("stockfish_analysis") or {}).get(
                "move_evaluations") or []:
            moves_seen += 1
            cp_loss = evaluation.get("cp_loss", 0) or 0
            if cp_loss < floor:
                continue
            passed_floor += 1
            fen_before = evaluation.get("fen_before")
            best = (evaluation.get("best_move_san")
                    or evaluation.get("best_move"))
            if not fen_before or not best:
                continue
            if (evaluation.get("is_opponent_move") is True
                    or evaluation.get("is_user_move") is False):
                continue
            try:
                mover_is_white = chess.Board(fen_before).turn == chess.WHITE
            except ValueError:
                continue
            if mover_is_white != (user_color == "white"):
                continue
            pv = evaluation.get("pv_after_best") or []
            if not _is_puzzle_worthy(
                fen_before=fen_before,
                best_move_san=best,
                best_move_uci=evaluation.get("best_move_uci"),
                pv_after_best=pv if isinstance(pv, list) else [],
                move_number=evaluation.get("move_number", 0),
                user_rating=rating,
                cp_loss=int(cp_loss),
            ):
                continue
            candidates += 1
            verdict = build_imported_game_verdict(
                game=game, move_evaluation=evaluation,
                broad_category=evaluation.get("cognitive_gap") or None)
            if verdict.status == AdmissionStatus.QUARANTINE:
                continue
            admitted += 1
            issue = verified_issue_type(verdict)
            labels[issue] += 1
            drill_labels[stored_pattern_label({
                "issue_type": issue,
                "verified_admission": verdict.to_document(),
            })] += 1
            if verdict.quality_id in MATE_QIDS:
                facts = verdict.detector_facts or ({},)
                mate_in[(facts[0] or {}).get("claimed_mate_in")] += 1
        if (index + 1) % 100 == 0:
            print(f"  ... {index + 1} games, {time.time() - started:.0f}s",
                  flush=True)

    print(f"  move_evaluations seen        : {moves_seen}")
    print(f"  passed the cp_loss floor     : {passed_floor}")
    print(f"  puzzle candidates (all gates): {candidates}")
    print(f"  admitted (non-quarantine)    : {admitted}  <- DENOMINATOR")
    print(f"\n  stored broad label (issue_type), n={admitted}")
    for key, count in labels.most_common():
        print(f"    {key:22s} {count:6d}  {100.0 * count / max(admitted, 1):5.2f}%")
    print(f"\n  drill label a pool query can request, n={admitted}")
    for key, count in drill_labels.most_common():
        print(f"    {key:22s} {count:6d}  {100.0 * count / max(admitted, 1):5.2f}%")
    reachable = drill_labels.get(FORCED_MATE_PATTERN, 0)
    print(f"\n  '{FORCED_MATE_PATTERN}' requestable: {reachable} of {admitted} admitted"
          f" ({100.0 * reachable / max(admitted, 1):.2f}%)")
    print(f"  distance to mate on those    : "
          f"{dict(sorted(mate_in.items(), key=lambda kv: (kv[0] is None, kv[0])))}")
    print(f"  elapsed {time.time() - started:.0f}s")


async def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=500)
    parser.add_argument("--sample", default=DEFAULT_SAMPLE)
    parser.add_argument("--repin", action="store_true",
                        help="choose a new sample instead of reusing the file")
    parser.add_argument("--pools-only", action="store_true")
    args = parser.parse_args(argv)

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")
    ]
    await measure_pools(db)
    if args.pools_only:
        return 0

    path = Path(args.sample)
    if args.repin or not path.exists():
        sample = await pin_sample(db, str(path), args.games)
        print(f"\npinned {sample['pinned']} games to {path}")
    else:
        sample = json.loads(path.read_text())
        print(f"\nreusing the pinned sample at {path}")
    await measure_extraction(db, sample, args.games)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

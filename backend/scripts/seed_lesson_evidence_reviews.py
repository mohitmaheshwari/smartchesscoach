"""Seed the lesson-evidence review queue: export on prod, Maia locally, load on prod.

docs/phase1_lesson_evidence_review_scope.md, WS1. Three steps, because Maia
never runs on the server (it needs ~800 MB the box does not have), and writes
to prod go through the server, never a tunnel:

  export  -- inside chess-coach-backend. Reads learning_sessions,
             move_observations and games; applies rules 1, 3 and 4
             (services/lesson_evidence_review.py); prints one JSON candidate per
             line. Read-only.
  score   -- on this machine. Adds Maia's probabilities at the player's rating
             and keeps the rows that pass rule 2 (temptation).
  load    -- inside chess-coach-backend. Upserts rows into
             lesson_evidence_reviews by key. Never touches learning_sessions,
             never deletes a row that has a ruling.

Usage (from the repo root on Mohit's machine):

  ssh root@72.60.204.176 "docker exec chess-coach-backend sh -c \
      'cd /app/backend && python scripts/seed_lesson_evidence_reviews.py export'" \
      > candidates.jsonl
  python -I backend/scripts/seed_lesson_evidence_reviews.py score \
      candidates.jsonl rows.jsonl --model C:/Users/MIISCO/chess-tools/models/rapid_model.pt
  scp rows.jsonl root@72.60.204.176:/tmp/lesson_rows.jsonl
  ssh root@72.60.204.176 "docker cp /tmp/lesson_rows.jsonl chess-coach-backend:/tmp/lesson_rows.jsonl && \
      docker exec chess-coach-backend sh -c \
      'cd /app/backend && python scripts/seed_lesson_evidence_reviews.py load /tmp/lesson_rows.jsonl'"
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from typing import Any, Dict, List, Optional, Tuple

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from services.destination_safety_detector import (  # noqa: E402
    QUALITY_ID as DESTINATION_SAFETY_QUALITY_ID,
    grade_destination_safety_candidate,
)
from services.lesson_evidence_review import (  # noqa: E402
    REVIEWS,
    RULINGS,
    candidate_rejection,
    first_lesson_dates,
    lesson_family,
    review_row,
)


def _ref(event: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    ref = str(((event.get("lesson_result") or {}).get("provenance") or {}).get("ref") or "")
    game_id, _, ply = ref.rpartition(":")
    return (game_id, int(ply)) if game_id and ply.isdigit() else None


async def export() -> None:
    from motor.motor_asyncio import AsyncIOMotorClient

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    events: List[Tuple[str, Dict[str, Any]]] = []
    sessions = []
    async for s in db.learning_sessions.find(
        {}, {"_id": 0, "user_id": 1, "lesson_type": 1, "skill_id": 1, "completed_at": 1, "events": 1}
    ):
        sessions.append({k: s.get(k) for k in ("user_id", "lesson_type", "skill_id", "completed_at")})
        for e in s.get("events") or []:
            app = ((e or {}).get("lesson_result") or {}).get("application") or {}
            if (
                isinstance(e, dict)
                and e.get("event_type") == "lesson_result"
                and app.get("source_type") == "organic_game"
                and app.get("detector_quality_id") == DESTINATION_SAFETY_QUALITY_ID
            ):
                events.append((str(s.get("user_id")), e))
    lessons = first_lesson_dates(sessions)

    game_ids = sorted({ref[0] for _, e in events if (ref := _ref(e))})
    observations: Dict[Tuple[str, int, str], Dict[str, Any]] = {}
    ratings: Dict[str, Tuple[Optional[int], Optional[int]]] = {}
    for i in range(0, len(game_ids), 200):
        chunk = game_ids[i:i + 200]
        async for m in db.move_observations.find(
            {"game_id": {"$in": chunk}},
            {"_id": 0, "game_id": 1, "ply": 1, "user_id": 1, "move_number": 1, "fen_before": 1,
             "move_uci": 1, "cp_loss": 1, "execution_quality": 1},
        ):
            observations[(m["game_id"], m.get("ply"), str(m.get("user_id")))] = m
        async for g in db.games.find(
            {"game_id": {"$in": chunk}},
            {"_id": 0, "game_id": 1, "user_rating": 1, "white_rating": 1, "black_rating": 1, "user_color": 1},
        ):
            opponent = g.get("black_rating") if g.get("user_color") == "white" else g.get("white_rating")
            ratings[g["game_id"]] = (g.get("user_rating"), opponent)

    # The record the coach sees is re-graded, like rule 1: the stored outcome
    # disagrees with today's detector on 18% of events.
    record: Dict[str, Counter] = defaultdict(Counter)
    joined = []
    for user_id, e in events:
        ref = _ref(e)
        obs = observations.get((ref[0], ref[1], user_id)) if ref else None
        joined.append((user_id, e, obs))
        if obs and obs.get("fen_before") and obs.get("move_uci"):
            status = grade_destination_safety_candidate(obs["fen_before"], obs["move_uci"]).get("status")
            if status in ("pass", "fail"):
                record[f"{user_id}|{e.get('skill_id')}"]["kept" if status == "pass" else "lost"] += 1

    why_not: Counter = Counter()
    for user_id, e, obs in joined:
        me, opponent = ratings.get(obs["game_id"], (None, None)) if obs else (None, None)
        rejection = candidate_rejection(e, obs, me)
        if rejection:
            why_not[rejection] += 1
            continue
        why_not["candidate"] += 1
        skill_id = str(e.get("skill_id") or "")
        print(json.dumps({
            "user_id": user_id,
            "event": {k: e.get(k) for k in ("idempotency_key", "skill_id", "occurred_at")},
            "observation": obs,
            "user_rating": me,
            "opponent_rating": opponent,
            "record": dict(record[f"{user_id}|{skill_id}"]),
            "first_lesson_at": lessons.get((user_id, lesson_family(skill_id))),
        }, default=str))
    print(json.dumps({"events": len(events), **why_not}), file=sys.stderr)


_maia = None


def _init_maia(model_path: str) -> None:
    global _maia
    from services.human_behavior_engine import Maia2Provider
    _maia = Maia2Provider(model_path=model_path)


def _score_one(line: str) -> Optional[str]:
    from services.human_behavior_engine import MoveContext
    c = json.loads(line)
    obs = c["observation"]
    me = int(c["user_rating"])
    dist = _maia.predict(MoveContext(fen=obs["fen_before"], player_elo=me,
                                     opponent_elo=int(c.get("opponent_rating") or me)))
    if not dist or not dist.probabilities:
        return None
    row = review_row(
        c["event"], obs,
        user_id=c["user_id"], user_rating=me, opponent_rating=c.get("opponent_rating"),
        probabilities=dist.probabilities, record=c.get("record") or {},
        first_lesson_at=c.get("first_lesson_at"),
    )
    return json.dumps(row) if row else None


def score(src: str, dst: str, model_path: str, workers: int) -> None:
    lines = [line for line in open(src, encoding="utf-8") if line.strip()]
    kept = 0
    with Pool(workers, initializer=_init_maia, initargs=(model_path,)) as pool, \
            open(dst, "w", encoding="utf-8") as out:
        for row in pool.imap_unordered(_score_one, lines, chunksize=20):
            if row:
                out.write(row + "\n")
                kept += 1
    print(json.dumps({"candidates": len(lines), "rows": kept}))


async def load(path: str) -> None:
    from motor.motor_asyncio import AsyncIOMotorClient

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    coll = db[REVIEWS]
    await coll.create_index("key", unique=True)
    await db[RULINGS].create_index([("key", 1), ("skill_id", 1)], unique=True)
    written = 0
    for row in rows:
        await coll.update_one({"key": row["key"]}, {"$set": row}, upsert=True)
        written += 1
    print(json.dumps({"loaded": written, "in_collection": await coll.count_documents({}),
                      "rulings": await db[RULINGS].count_documents({})}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("export")
    s = sub.add_parser("score")
    s.add_argument("src")
    s.add_argument("dst")
    s.add_argument("--model", default=os.environ.get("MAIA2_MODEL_PATH", ""))
    s.add_argument("--workers", type=int, default=6)
    ld = sub.add_parser("load")
    ld.add_argument("path")
    args = parser.parse_args()
    if args.step == "export":
        asyncio.run(export())
    elif args.step == "score":
        if not args.model:
            parser.error("--model (or MAIA2_MODEL_PATH) is required")
        score(args.src, args.dst, args.model, args.workers)
    else:
        asyncio.run(load(args.path))


if __name__ == "__main__":
    main()

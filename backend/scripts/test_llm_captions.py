"""
Test LLM caption generation on N games (default 1).

Reads existing decryption_v5_data from game_analyses, walks each game
to annotate trap + opening context per move, and (when there's a
teaching signal) sends to gpt-4o-mini through call_llm with:
  - Coach Voice rules (services/coach_voice_prompt.py)
  - The 28 caption principle catalog (services/caption_principles.py)
  - The 23 shape pattern catalog (services/shape_patterns.py)

All shared logic lives in services/llm_caption_generator.py.

Does NOT touch production data. Prints per-move side-by-side comparison
to stdout — existing renderer caption vs LLM caption + facts that were
sent.

Usage:
    docker exec -it chess-coach-backend python scripts/test_llm_captions.py
    docker exec -it chess-coach-backend python scripts/test_llm_captions.py --n 5 --source random
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

from services.llm_caption_generator import (
    build_system_prompt,
    has_teaching_signal,
    annotate_runtime_facts,
    generate_caption_for_move,
)


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def format_facts_inline(move: Dict[str, Any]) -> str:
    parts = []
    if move.get("_trap"):
        parts.append(f"TRAP={move['_trap']['name']}")
    if move.get("_opening"):
        parts.append(f"opening={move['_opening']['name']}@step{move['_opening']['matched_steps']}")
    if move.get("best_move_san"):
        parts.append(f"best={move['best_move_san']}")
    if move.get("caption_facts_primary_reason"):
        parts.append(f"rule={move['caption_facts_primary_reason']}")
    if move.get("shape_pattern_name"):
        parts.append(f"shape={move['shape_pattern_name']}")
    pids = [p.get("principle_id") for p in (move.get("caption_facts_principles_violated") or []) if p]
    if pids:
        parts.append(f"principles={','.join(pids)}")
    return " | ".join(parts) or "(none)"


async def pick_games(db, n: int, source: str) -> List[Dict[str, str]]:
    if source == "queue":
        items = await db.authoring_queue.find(
            {},
            {"_id": 0, "game_id": 1, "bucket": 1, "order_in_round": 1},
        ).sort("order_in_round", 1).limit(n).to_list(n)
        if items:
            return items
        print("[test] authoring_queue empty — falling back to random sample", file=sys.stderr)

    items: List[Dict[str, str]] = []
    async for g in db.games.aggregate([
        {"$match": {"is_active": {"$ne": False}, "is_analyzed": True}},
        {"$sample": {"size": n}},
        {"$project": {"_id": 0, "game_id": 1}},
    ]):
        items.append({"game_id": g["game_id"], "bucket": "random"})
    return items


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1,
                    help="Number of games to test (default 1 — keep low until prompt is validated).")
    ap.add_argument("--source", choices=["queue", "random"], default="queue",
                    help="queue=use active authoring_queue (default), random=random sample")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    games = await pick_games(db, args.n, args.source)
    sys_prompt = build_system_prompt()

    totals = {"moves": 0, "called": 0, "gated": 0, "llm_empty": 0, "errors": 0}

    for idx, item in enumerate(games, 1):
        gid = item["game_id"]
        bucket = item.get("bucket", "?")

        print("")
        print("═" * 78)
        print(f"GAME {idx}/{len(games)}   game_id: {gid}   bucket: {bucket}")
        print(f"  open in UI:  /game/{gid}")
        print("═" * 78)

        analysis = await db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, "decryption_v5_data": 1},
        )
        if not analysis or not analysis.get("decryption_v5_data"):
            print("  (no V5 data for this game)")
            continue

        moves = analysis["decryption_v5_data"]
        annotate_runtime_facts(moves)

        # Print trap detection summary
        for m in moves:
            if m.get("_trap"):
                t = m["_trap"]
                step = t.get("step", 0)
                if step == 0:
                    print(f"\n  ▶ TRAP DETECTED on move {m.get('move_number')}: "
                          f"{t['name']} ({t['family']}) — completed by "
                          f"{'user' if t.get('completed_by_user') else 'opp'}")
                else:
                    print(f"  ▶ TRAP CONTINUATION on move {m.get('move_number')}.{m.get('move_san')} "
                          f"— step {step} ({t.get('step_label')})")

        for m in moves:
            totals["moves"] += 1
            mv = m.get("move_san", "?")
            mn = m.get("move_number", "?")
            mover = "user" if m.get("is_user_move") else "opp "
            sev = (m.get("severity") or "?").ljust(13)

            if not has_teaching_signal(m):
                totals["gated"] += 1
                continue

            totals["called"] += 1
            llm_caption = await generate_caption_for_move(m, sys_prompt)

            if not llm_caption:
                totals["llm_empty"] += 1
                tag = "[LLM-EMPTY]"
            elif llm_caption.startswith("[ERROR"):
                totals["errors"] += 1
                tag = "[ERROR]    "
            else:
                tag = "           "

            existing = (m.get("caption") or "").strip() or "(no existing)"
            print(f"\n  move {mn:>3}.{mv:<8}  {mover}  {sev}  {tag}")
            print(f"    existing : {existing}")
            print(f"    LLM      : {llm_caption or '(empty)'}")
            print(f"    facts    : {format_facts_inline(m)}")

    print("")
    print("─" * 78)
    print(
        f"moves={totals['moves']}  called={totals['called']}  "
        f"gated={totals['gated']}  llm_empty={totals['llm_empty']}  errors={totals['errors']}"
    )


if __name__ == "__main__":
    asyncio.run(main())

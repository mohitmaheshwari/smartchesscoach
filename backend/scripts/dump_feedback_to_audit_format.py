"""
Dump all entries from the move_feedback collection into the same JSON
shape Parth's admin export uses. Writes to a file inside the container —
no host-side wrangling needed.

After running this, the regular pipeline runs cleanly:
    python scripts/dump_feedback_to_audit_format.py --out /tmp/parth_full.json
    python scripts/reconstruct_bug_fens.py --in /tmp/parth_full.json --out /tmp/parth_full_with_fen.json
    python scripts/content_correctness_audit.py --bug-file /tmp/parth_full_with_fen.json --engine
"""
from __future__ import annotations

import argparse
import asyncio
import json as json_lib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _serialise_dt(v):
    if isinstance(v, datetime):
        return v.isoformat()
    return v


async def run(args):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    query = {}
    if args.status and args.status != "all":
        query["status"] = args.status
    if args.source and args.source != "all":
        query["source"] = args.source

    items = []
    async for fb in db.move_feedback.find(query, {"_id": 0}).sort("created_at", -1):
        diag = fb.get("diagnostics") or {}
        items.append({
            "feedback_id": fb.get("feedback_id"),
            "page": fb.get("source", "unknown"),
            "issue": fb.get("user_note", ""),
            "coaching_text_flagged": fb.get("coaching_text"),
            "severity": diag.get("severity") or "unknown",
            "status": fb.get("status", "pending"),
            "user": fb.get("user_name") or fb.get("user_id"),
            "user_rating": fb.get("user_rating"),
            "created_at": _serialise_dt(fb.get("created_at")),
            "position": {
                "fen": fb.get("fen"),
                "move_san": fb.get("move_san"),
                "move_number": fb.get("move_number"),
                "best_move": diag.get("best_move"),
                "cp_loss": diag.get("cp_loss"),
                "eval_before": diag.get("eval_before"),
                "eval_after": diag.get("eval_after"),
                "phase": diag.get("phase"),
            },
            "context": {
                "game_id": fb.get("game_id"),
                "session_id": fb.get("session_id"),
                "component": diag.get("component"),
                "concept_id": diag.get("concept_id"),
                "goal": diag.get("goal"),
                "consequence": diag.get("consequence"),
                "better_approach": diag.get("better_approach"),
                "your_plan_now": diag.get("your_plan_now"),
            },
            "admin_notes": fb.get("admin_notes"),
            "reviewed_by": fb.get("reviewed_by"),
            "reviewed_at": _serialise_dt(fb.get("reviewed_at")),
        })

    client.close()

    export_data = {
        "export_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "filters": {"status": args.status or "all", "source": args.source or "all"},
        "total": len(items),
        "feedback": items,
    }

    Path(args.out_path).write_text(json_lib.dumps(export_data, indent=2), encoding="utf-8")
    print(f"Wrote {len(items)} entries to {args.out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", dest="out_path", required=True, help="output JSON path")
    p.add_argument("--status", default="all", help="filter by status (pending/reviewed/all)")
    p.add_argument("--source", default="all", help="filter by source page (lab/coach/play_with_coach/all)")
    asyncio.run(run(p.parse_args()))

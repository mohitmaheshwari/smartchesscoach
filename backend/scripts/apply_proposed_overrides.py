"""
Apply Claude-proposed overrides to coach_overrides in bulk.

Reads a JSON file (default: backend/scripts/proposed_overrides.json)
of override entries that Claude wrote during a chat session, and
upserts each into the coach_overrides collection. The flagged-moment
queue automatically hides anything with an override (per the existing
admin endpoint), so a clean pull of this script + redeploy + regen
is enough to clear the queue.

JSON shape:
    [
      {
        "game_id":      "...",
        "move_number":  14,
        "move_san":     "Bb4",
        "override_text": "Bxh7+ was coming. After Kxh7 Qh5+, you lose the queen on g5. g6 blocks the diagonal.",
        "coach_note":   "Greek Gift defense — propose walked_into_attack detector"
      },
      ...
    ]

Usage:
    python scripts/apply_proposed_overrides.py
    python scripts/apply_proposed_overrides.py --file /tmp/my_overrides.json
    python scripts/apply_proposed_overrides.py --dry-run
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

# Tag the coach_user_id so audits know these came from Claude review.
CLAUDE_REVIEW_USER_ID = "claude_review"
CLAUDE_REVIEW_EMAIL = "claude-review@chessguru.local"


async def main(args) -> None:
    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    try:
        proposals = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to parse {path}: {e}")
        sys.exit(1)

    if not isinstance(proposals, list):
        print(f"Expected a JSON array; got {type(proposals).__name__}")
        sys.exit(1)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    applied = 0
    skipped = 0
    errors = 0

    for i, p in enumerate(proposals, 1):
        gid = p.get("game_id")
        mn = p.get("move_number")
        ms = p.get("move_san")
        text = (p.get("override_text") or "").strip()

        if not (gid and mn and ms and text):
            print(f"[{i}/{len(proposals)}] SKIP — missing required fields: {p}")
            skipped += 1
            continue

        # Pull the original moment so we capture full context (FEN,
        # source, confidence, etc.) — same shape the admin POST endpoint
        # produces.
        analysis = await db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, "user_id": 1, "decryption_block": 1},
        )
        if not analysis:
            print(f"[{i}/{len(proposals)}] ERROR — no game_analyses for {gid}")
            errors += 1
            continue
        moments = ((analysis.get("decryption_block") or {}).get("moments") or [])
        target = next(
            (m for m in moments
             if m.get("move_number") == mn and m.get("move_san") == ms),
            None,
        )
        if not target:
            print(f"[{i}/{len(proposals)}] ERROR — no moment {mn} {ms} in {gid}")
            errors += 1
            continue

        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "game_id": gid,
            "user_id": analysis.get("user_id"),
            "move_number": mn,
            "move_san": ms,
            "move_uci": target.get("move_uci"),
            "fen_before": target.get("fen_before"),
            "fen_after": target.get("fen_after"),
            "cp_loss": target.get("cp_loss"),
            "severity": target.get("severity"),
            "source": target.get("source"),
            "pattern_type": (
                target.get("source", "").split(":", 1)[1]
                if target.get("source", "").startswith("template:") else None
            ),
            "best_move_san": next(
                (c.get("san") for c in (target.get("candidates") or []) if c.get("isCorrect")),
                None,
            ),
            "original_text": target.get("text"),
            "override_text": text,
            "coach_note": p.get("coach_note"),
            "confidence": target.get("confidence"),
            "confidence_breakdown": target.get("confidence_breakdown"),
            "coach_user_id": CLAUDE_REVIEW_USER_ID,
            "coach_email": CLAUDE_REVIEW_EMAIL,
            "updated_at": now,
        }

        if args.dry_run:
            print(f"[{i}/{len(proposals)}] DRY-RUN — would upsert: {gid} M{mn} {ms}")
            print(f"    text: {text[:80]}")
            applied += 1
            continue

        await db.coach_overrides.update_one(
            {"game_id": gid, "move_number": mn, "move_san": ms},
            {
                "$set": doc,
                "$setOnInsert": {
                    "override_id": f"ov_{uuid.uuid4().hex[:12]}",
                    "created_at": now,
                },
            },
            upsert=True,
        )
        print(f"[{i}/{len(proposals)}] OK — {gid} M{mn} {ms}: {text[:60]}")
        applied += 1

    client.close()

    print()
    print("=" * 70)
    print(f"  applied: {applied}")
    print(f"  skipped: {skipped}")
    print(f"  errors:  {errors}")
    if args.dry_run:
        print("  (dry-run — no DB writes)")
    print("=" * 70)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--file",
        default=str(BACKEND_DIR / "scripts" / "proposed_overrides.json"),
        help="path to the JSON array of proposals",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="print what would happen without writing to DB")
    args = p.parse_args()
    asyncio.run(main(args))

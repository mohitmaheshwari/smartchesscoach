"""Mirror admin/permission flags from a source user onto a target user.

Use to grant a co-admin the SAME role + reviewer + permission flags as
the primary owner without copying identifying fields (user_id, email,
name, OAuth keys, chess.com handle, ratings, game stats).

Mohit 2026-06-04 — built to mirror bhutramohit@gmail.com's flags onto
shobhit.bhutra1993@gmail.com.

Usage:
  docker exec chess-coach-backend python \\
    /app/backend/scripts/mirror_admin_flags.py \\
    --from bhutramohit@gmail.com --to shobhit.bhutra1993@gmail.com [--apply]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

# Explicit allowlist of admin/permission fields. Everything else is
# treated as personal data (gameplay ratings, OAuth handles, focus,
# pattern logs, last-login timestamps, profile picture etc.) and stays
# on the target user untouched.
ADMIN_FIELDS = {
    "role",          # "user" / "admin" / "super_admin"
    "is_reviewer",   # access to /review/authoring
    "is_admin",      # legacy bool, kept in case any route still checks it
    "feature_flags", # internal cohort + experimental feature gates
    "plan",          # billing tier (pro / free)
}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True, help="source user email")
    ap.add_argument("--to", dest="dst", required=True, help="target user email")
    ap.add_argument("--apply", action="store_true", help="commit changes (default: dry-run)")
    args = ap.parse_args()

    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)[DB_NAME]
    src = await db.users.find_one({"email": args.src})
    dst = await db.users.find_one({"email": args.dst})
    if not src:
        print(f"ERROR: source user {args.src} not found")
        return 1
    if not dst:
        print(f"ERROR: target user {args.dst} not found")
        return 1

    # Build the set of fields to mirror — only those in the explicit allowlist.
    to_copy = {k: src[k] for k in ADMIN_FIELDS if k in src}

    # Compare current dst values to see what would change.
    changes = []
    for k, v in to_copy.items():
        if dst.get(k) != v:
            changes.append((k, dst.get(k), v))

    if not changes:
        print(f"Nothing to mirror — {args.dst} already matches {args.src} on all non-identifying fields.")
        return 0

    print(f"Mirror plan: {args.src} → {args.dst}")
    print(f"  src user_id: {src.get('user_id')}")
    print(f"  dst user_id: {dst.get('user_id')}")
    print()
    print(f"Fields that would change ({len(changes)}):")
    for k, old, new in changes:
        print(f"  {k}: {old!r} → {new!r}")
    print()

    if not args.apply:
        print("DRY RUN — rerun with --apply to commit.")
        return 0

    result = await db.users.update_one(
        {"email": args.dst},
        {"$set": to_copy},
    )
    print(f"Applied. matched={result.matched_count}, modified={result.modified_count}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

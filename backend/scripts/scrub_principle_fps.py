"""
Scrub stale-FP principle fires from existing game_analyses records.

Background: when a V5 principle detector is fixed (e.g. TAC_BACK_RANK
adding the enemy-king-on-back-rank gate on 2026-05-12), existing
decryption_v5_data records still carry pre-fix FPs in their
caption_facts_principles_violated arrays. This script re-runs the
audit's geometric verifier per fire, drops fires that fail, and
clears principle_cue/principle_id_used when the dropped fire was
the chosen cue.

This is a targeted scrub — NOT a full V5 re-extraction. For full
refresh use scripts/audit_caption_v5_corpus.py --write-db.

By default scrubs only the principles that have a GEOMETRIC verifier
in audit_caption_principles_per_fire.py and that we know have had
detector fixes. Pass --principle to scrub a specific one.

Usage:
    docker exec -it chess-coach-backend python scripts/scrub_principle_fps.py --dry-run
    docker exec -it chess-coach-backend python scripts/scrub_principle_fps.py
    docker exec -it chess-coach-backend python scripts/scrub_principle_fps.py --principle TAC_BACK_RANK
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import chess
from motor.motor_asyncio import AsyncIOMotorClient

# Reuse the audit's geometric verifiers — same code that audits, scrubs.
sys.path.insert(0, str(BACKEND_DIR / "scripts"))
from audit_caption_principles_per_fire import _VERIFIERS  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


# Principles whose detectors have been fixed and need stale-FP scrubbing.
# Add to this list when a detector fix lands. Only principles with a true
# GEOMETRIC verifier (not STRUCTURAL) should be here — structural verifiers
# can't tell stale from real.
SCRUB_TARGETS_DEFAULT: Set[str] = {
    "TAC_BACK_RANK",  # fixed 2026-05-12: now requires enemy king on back rank
}


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--principle", type=str, default=None,
                    help="Scrub only this principle_id (overrides default set)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would be scrubbed without writing")
    ap.add_argument("--limit", type=int, default=None,
                    help="Process at most N games (most-recent first)")
    args = ap.parse_args()

    targets = {args.principle} if args.principle else SCRUB_TARGETS_DEFAULT
    print(f"Scrubbing FP fires for principles: {sorted(targets)}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'WRITE'}")
    print()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Only fetch games that have at least one of the target principles fired.
    query = {"decryption_v5_data.caption_facts_principles_violated.principle_id": {"$in": list(targets)}}
    cursor = db.game_analyses.find(query, {"_id": 1, "decryption_v5_data": 1, "game_id": 1})
    cursor = cursor.sort("analyzed_at", -1)
    if args.limit:
        cursor = cursor.limit(args.limit)

    games_scanned = 0
    games_modified = 0
    fires_kept = 0
    fires_dropped = 0
    cues_cleared = 0
    drop_reasons: Counter = Counter()
    drops_by_pid: Counter = Counter()
    start = time.time()

    async for doc in cursor:
        games_scanned += 1
        v5 = doc.get("decryption_v5_data") or []
        if not v5:
            continue
        game_modified = False

        for rec in v5:
            pv = rec.get("caption_facts_principles_violated") or []
            if not pv:
                continue
            fen = rec.get("fen_before")
            played_san = rec.get("move_san")
            if not fen:
                continue
            try:
                board = chess.Board(fen)
            except Exception:
                continue

            new_pv = []
            dropped_pids: Set[str] = set()
            for ev in pv:
                pid = ev.get("principle_id")
                if pid not in targets:
                    new_pv.append(ev)
                    continue
                verifier = _VERIFIERS.get(pid)
                if not verifier:
                    new_pv.append(ev)
                    continue
                try:
                    ok, reason, scope = verifier(board, ev, played_san)
                except Exception as exc:
                    # Verifier crash → keep (don't want to scrub on our own bug)
                    new_pv.append(ev)
                    continue
                if scope != "GEOMETRIC":
                    # Structural-only verifiers can't distinguish stale from real.
                    new_pv.append(ev)
                    continue
                if ok:
                    new_pv.append(ev)
                    fires_kept += 1
                else:
                    fires_dropped += 1
                    drops_by_pid[pid] += 1
                    drop_reasons[reason[:80]] += 1
                    dropped_pids.add(pid)
            if len(new_pv) != len(pv):
                rec["caption_facts_principles_violated"] = new_pv
                game_modified = True
                # If the principle_id_used was dropped, clear cue + id.
                if rec.get("principle_id_used") in dropped_pids:
                    rec["principle_id_used"] = None
                    rec["principle_cue"] = ""
                    cues_cleared += 1

        if game_modified and not args.dry_run:
            await db.game_analyses.update_one(
                {"_id": doc["_id"]},
                {"$set": {"decryption_v5_data": v5}},
            )
            games_modified += 1
        elif game_modified:
            games_modified += 1  # would-be-modified count for dry-run

        if games_scanned % 50 == 0:
            elapsed = time.time() - start
            print(f"  [{elapsed:.0f}s] {games_scanned} scanned, {games_modified} modified, {fires_dropped} fires dropped",
                  file=sys.stderr, flush=True)

    elapsed = time.time() - start
    print(f"\n── Scrub summary ─────────────────────────────────")
    print(f"  Games scanned:        {games_scanned}")
    print(f"  Games modified:       {games_modified}")
    print(f"  Fires kept:           {fires_kept}")
    print(f"  Fires dropped:        {fires_dropped}")
    print(f"  Cues cleared:         {cues_cleared}")
    print(f"  Elapsed:              {elapsed:.1f}s")
    print(f"  Mode:                 {'DRY-RUN' if args.dry_run else 'WRITE'}")
    if drops_by_pid:
        print(f"\n  Drops by principle:")
        for pid, n in drops_by_pid.most_common():
            print(f"    {pid:28s} {n}")
    if drop_reasons:
        print(f"\n  Top drop reasons:")
        for reason, n in drop_reasons.most_common(10):
            print(f"    {n:5d}  {reason}")


if __name__ == "__main__":
    asyncio.run(main())

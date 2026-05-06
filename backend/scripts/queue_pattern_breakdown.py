"""
Break down the review queue and the wider moment set by source/pattern.

Answers:
  - of all moments in DB, what fraction are template-resolved vs flagged?
  - which templates are firing (and how often)?
  - of the flagged ones, what's the distribution of cp_loss / severity?
  - sample 5 flagged moments per source so we can see what's left to build

Usage:
    python scripts/queue_pattern_breakdown.py
"""

import asyncio
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main() -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Pre-load overrides so we can mark moments as 'overridden'.
    override_keys = set()
    async for ov in db.coach_overrides.find({}, {"_id": 0, "game_id": 1, "move_number": 1, "move_san": 1}):
        override_keys.add((ov.get("game_id"), ov.get("move_number"), ov.get("move_san")))

    source_counts = Counter()
    flagged_visible_count = 0     # needs_review AND no override (visible in /admin queue)
    flagged_overridden_count = 0  # needs_review BUT overridden (hidden from queue)
    shipped_count = 0
    total = 0
    flagged_samples_by_source = defaultdict(list)
    shipped_samples_by_source = defaultdict(list)

    async for ga in db.game_analyses.find(
        {"decryption_block.moments.0": {"$exists": True}},
        {"_id": 0, "game_id": 1, "decryption_block.moments": 1},
    ):
        gid = ga.get("game_id")
        moments = (ga.get("decryption_block") or {}).get("moments") or []
        for m in moments:
            total += 1
            src = m.get("source") or "unknown"
            source_counts[src] += 1
            mn = m.get("move_number")
            ms = m.get("move_san")
            has_override = (gid, mn, ms) in override_keys
            if m.get("needs_review"):
                if has_override:
                    flagged_overridden_count += 1
                else:
                    flagged_visible_count += 1
                    if len(flagged_samples_by_source[src]) < 5:
                        flagged_samples_by_source[src].append({
                            "game_id": gid,
                            "move": f"{mn} {ms}",
                            "cp_loss": m.get("cp_loss"),
                            "text": (m.get("text") or "")[:80],
                        })
            else:
                shipped_count += 1
                if len(shipped_samples_by_source[src]) < 3:
                    shipped_samples_by_source[src].append({
                        "game_id": gid,
                        "move": f"{mn} {ms}",
                        "text": (m.get("text") or "")[:80],
                    })

    print("=" * 78)
    print("QUEUE PATTERN BREAKDOWN")
    print("=" * 78)
    flagged_total = flagged_visible_count + flagged_overridden_count
    print(f"  total moments:                {total}")
    print(f"  template-shipped (✓):         {shipped_count}")
    print(f"  flagged-but-overridden (✓):   {flagged_overridden_count}    (hidden from /admin queue)")
    print(f"  flagged-VISIBLE (⚠ review):   {flagged_visible_count}    (still in /admin queue)")
    print(f"  flagged total (raw):          {flagged_total}")
    print()
    print("BY SOURCE (most common first):")
    for src, n in source_counts.most_common():
        flag = " ← needs work" if src in ("engine_fallback", "llm", "fallback_template") else ""
        print(f"  {n:4d}  {src}{flag}")
    print()

    print("FLAGGED SAMPLES (what's still unresolved):")
    for src, samples in flagged_samples_by_source.items():
        print(f"  source = {src}:")
        for s in samples:
            print(f"    {s['game_id']}  M{s['move']}  cp={s['cp_loss']}")
            print(f"      text: {s['text']}")
        print()

    print("SHIPPED SAMPLES (templates that are working):")
    for src, samples in shipped_samples_by_source.items():
        print(f"  source = {src}:")
        for s in samples:
            print(f"    {s['game_id']}  M{s['move']}: {s['text']}")
        print()

    client.close()


if __name__ == "__main__":
    asyncio.run(main())

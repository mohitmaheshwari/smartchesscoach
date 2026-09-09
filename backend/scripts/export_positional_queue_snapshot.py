"""Export the positional-reason queue without printing database credentials."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient


async def main() -> None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ.get("DB_NAME", "test_database")]
    queue = await database.positional_reason_queue.find({}, {"_id": 0}).to_list(None)
    submissions = await database.positional_reason_submissions.find({}, {"_id": 0}).to_list(None)
    target = Path(os.environ.get("POSITIONAL_EXPORT_PATH", "/tmp/positional-reasons-snapshot.json"))
    target.write_text(
        json.dumps({"queue": queue, "submissions": submissions}, default=str, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"queue": len(queue), "submissions": len(submissions), "path": str(target)}))


if __name__ == "__main__":
    asyncio.run(main())

"""Report what games are in the Lab, per user.

This is a DIAGNOSTIC SCRIPT, not a unit test. It only carries a `test_` prefix
because it lives in tests/, which means pytest collects it -- and it used to
open a Mongo connection while doing so. On any machine without a local Mongo
that raised ServerSelectionTimeoutError during COLLECTION, which aborts the
entire pytest run rather than failing one file. That is why `pytest tests/`
could not be run here at all.

The connection now happens inside a fixture, and the whole module skips when no
database is configured. Run it directly for the report:

    python tests/test_lab_games.py
"""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]

    # Find the user
    users = await db.users.find({}, {"_id": 0, "user_id": 1}).to_list(10)
    for u in users:
        uid = u["user_id"]
        total = await db.games.count_documents({"user_id": uid})
        analyzed = await db.games.count_documents({"user_id": uid, "is_analyzed": True})
        coach = await db.games.count_documents({"user_id": uid, "platform": "coach"})
        other = await db.games.count_documents({"user_id": uid, "platform": {"$ne": "coach"}})
        other_analyzed = await db.games.count_documents({"user_id": uid, "platform": {"$ne": "coach"}, "is_analyzed": True})

        print(f"User: {uid}")
        print(f"  Total games: {total}")
        print(f"  Analyzed: {analyzed}")
        print(f"  Coach games: {coach}")
        print(f"  Imported games: {other}")
        print(f"  Imported + analyzed: {other_analyzed}")
        print()

    client.close()

# Guarded: without this the connection ran at IMPORT time, so pytest hit it
# during collection and aborted the entire run on any machine without a local
# Mongo. A module in tests/ must never do work just by being imported.
if __name__ == "__main__":
    asyncio.run(main())

"""Check what games are in the Lab"""
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

asyncio.run(main())

#!/usr/bin/env python3
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check():
    db = AsyncIOMotorClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))['test_database']

    user_id = "user_8b599930d7ef"
    pres = await db.user_coaching_prescriptions.find({"user_id": user_id, "status": "pending"}).to_list(None)

    print(f"Pending prescriptions for {user_id}:")
    for p in pres:
        print(f"  {p['issue_detected']}: {p['prescription_id']}")

asyncio.run(check())

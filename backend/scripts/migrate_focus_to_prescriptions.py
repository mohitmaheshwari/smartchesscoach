#!/usr/bin/env python3
"""
Migrate Focus Locks to Coaching Prescriptions
"""
import asyncio, logging, sys, uuid, os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')

FOCUS_TO_ISSUE = {
    'HANGING_PIECE': 'piece_safety',
    'TACTICAL_MISS': 'missed_tactic',
    'TIME_PRESSURE': 'rushing',
}

FOCUS_TO_PLAN = {
    'HANGING_PIECE': 'loose-piece-discipline',
    'TACTICAL_MISS': 'spot-tactical-opportunities',
    'TIME_PRESSURE': 'critical-moment-thinking',
}

async def get_db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]

async def apply_migration(db):
    users = await db.users.find({'focus_locks': {'$exists': True}}).to_list(None)
    for user in users:
        for focus_type, lock_data in user.get('focus_locks', {}).items():
            prescription = {
                'prescription_id': str(uuid.uuid4()),
                'user_id': user['user_id'],
                'plan_id': FOCUS_TO_PLAN.get(focus_type, 'spot-tactical-opportunities'),
                'status': 'active' if lock_data.get('active') else 'pending',
                'issue_detected': FOCUS_TO_ISSUE.get(focus_type, 'missed_tactic'),
                'reasoning': f'Migrated from focus_lock: {focus_type}',
                'baseline_metric': lock_data.get('baseline_metric', 0.5),
                'current_metric': lock_data.get('current_metric', 0.5),
                'improvement_pct': lock_data.get('improvement_pct', 0.0),
                'priority_order': 1,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            await db.user_coaching_prescriptions.insert_one(prescription)
    print("Migration complete")

async def main():
    db = await get_db()
    await apply_migration(db)
    db.client.close()

if __name__ == '__main__':
    asyncio.run(main())

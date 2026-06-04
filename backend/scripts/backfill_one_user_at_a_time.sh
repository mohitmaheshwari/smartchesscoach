#!/bin/bash
# Wrap backfill_concept_mastery.py in a per-user loop so each invocation
# gets a fresh mongo connection. The multi-user mode dies on idle-connection
# timeout around user #7-10.
set -e
USERS=$(python -c "
import asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
async def m():
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])['chess_coach']
    users = await db.user_concept_understanding.distinct('user_id', {'last_evaluated_game_id': None})
    for u in users:
        print(u)
asyncio.run(m())
")
total=$(echo "$USERS" | wc -l)
idx=0
for uid in $USERS; do
    idx=$((idx + 1))
    echo "[$idx/$total] backfilling $uid"
    python -u /app/backend/scripts/backfill_concept_mastery.py --user-id "$uid" 2>&1 | tail -2
done
echo "DONE"

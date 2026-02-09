# Chess Coach AI - Scheduled Tasks & Cron Jobs

## Overview

The application has **built-in background tasks** that run automatically when the server starts. However, for **production reliability**, you may want to set up external cron jobs as backups.

---

## 1. Built-in Background Tasks (Automatic)

These run **automatically** inside the FastAPI server:

### Game Sync Loop
- **What it does:** Syncs games from Chess.com and Lichess for all users with linked accounts
- **Frequency:** Every 6 hours
- **Location:** `server.py` → `background_sync_loop()`
- **Config:** `BACKGROUND_SYNC_INTERVAL_SECONDS` in `config.py` (default: 21600 seconds = 6 hours)

```
✅ This runs automatically when the server starts
✅ No cron job needed for this
```

---

## 2. Optional Cron Jobs (Recommended for Production)

For production, you may want external cron jobs as **backup** in case the server restarts:

### A. Manual Game Sync Trigger (Backup)

Create a script `cron_sync_games.py`:

```python
#!/usr/bin/env python3
"""
Cron job to trigger game sync for all users.
Run every 6 hours as backup to built-in sync.

Crontab: 0 */6 * * * /path/to/venv/bin/python /path/to/cron_sync_games.py
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

async def sync_all_users():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Import the sync function
    import sys
    sys.path.insert(0, '/path/to/backend')
    from journey_service import run_background_sync
    
    count = await run_background_sync(db)
    print(f"Synced {count} games")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(sync_all_users())
```

**Crontab entry:**
```bash
# Run every 6 hours at minute 0
0 */6 * * * cd /path/to/backend && /path/to/venv/bin/python cron_sync_games.py >> /var/log/chess-coach/sync.log 2>&1
```

---

### B. Weekly Summary Emails (If Using Email Feature)

Create a script `cron_weekly_emails.py`:

```python
#!/usr/bin/env python3
"""
Send weekly summary emails to users who opted in.
Run every Monday at 9 AM.

Crontab: 0 9 * * 1 /path/to/venv/bin/python /path/to/cron_weekly_emails.py
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

async def send_weekly_summaries():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Find users with weekly email enabled
    users = await db.users.find({
        "email_notifications.weekly_summary": True
    }).to_list(1000)
    
    print(f"Found {len(users)} users with weekly emails enabled")
    
    for user in users:
        try:
            # Get last week's analyses
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            analyses = await db.game_analyses.find({
                "user_id": user["user_id"],
                "created_at": {"$gte": week_ago.isoformat()}
            }).to_list(100)
            
            if analyses:
                # Import email service
                import sys
                sys.path.insert(0, '/path/to/backend')
                from email_service import send_weekly_summary_email
                from chess_journey_service import generate_weekly_summary
                from player_profile_service import get_or_create_profile
                
                profile = await get_or_create_profile(db, user["user_id"], user.get("name", "Player"))
                summary = generate_weekly_summary(analyses, profile)
                
                # Send email (implement based on your email_service.py)
                print(f"Would send weekly summary to {user['email']}")
                
        except Exception as e:
            print(f"Error for user {user['user_id']}: {e}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(send_weekly_summaries())
```

**Crontab entry:**
```bash
# Run every Monday at 9:00 AM
0 9 * * 1 cd /path/to/backend && /path/to/venv/bin/python cron_weekly_emails.py >> /var/log/chess-coach/weekly-emails.log 2>&1
```

---

### C. Database Cleanup (Optional)

Create a script `cron_cleanup.py`:

```python
#!/usr/bin/env python3
"""
Clean up old/expired data.
Run daily at 3 AM.

Crontab: 0 3 * * * /path/to/venv/bin/python /path/to/cron_cleanup.py
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

async def cleanup():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    now = datetime.now(timezone.utc)
    
    # 1. Clean expired sessions (TTL index should handle this, but backup)
    expired = await db.user_sessions.delete_many({
        "expires_at": {"$lt": now}
    })
    print(f"Deleted {expired.deleted_count} expired sessions")
    
    # 2. Clean old notifications (older than 30 days)
    month_ago = now - timedelta(days=30)
    old_notifs = await db.notifications.delete_many({
        "created_at": {"$lt": month_ago.isoformat()},
        "read": True
    })
    print(f"Deleted {old_notifs.deleted_count} old notifications")
    
    # 3. Clean stale analysis queue items (failed/stuck for > 24 hours)
    day_ago = now - timedelta(hours=24)
    stale = await db.analysis_queue.delete_many({
        "status": {"$in": ["pending", "processing"]},
        "created_at": {"$lt": day_ago.isoformat()}
    })
    print(f"Deleted {stale.deleted_count} stale queue items")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(cleanup())
```

**Crontab entry:**
```bash
# Run daily at 3:00 AM
0 3 * * * cd /path/to/backend && /path/to/venv/bin/python cron_cleanup.py >> /var/log/chess-coach/cleanup.log 2>&1
```

---

## 3. Complete Crontab Setup

```bash
# Edit crontab
crontab -e

# Add these lines:
# ================================================
# Chess Coach AI - Scheduled Tasks
# ================================================

# Game sync backup (every 6 hours)
0 */6 * * * cd /app/backend && /usr/bin/python3 cron_sync_games.py >> /var/log/chess-coach/sync.log 2>&1

# Weekly summary emails (Monday 9 AM)
0 9 * * 1 cd /app/backend && /usr/bin/python3 cron_weekly_emails.py >> /var/log/chess-coach/weekly-emails.log 2>&1

# Database cleanup (daily 3 AM)
0 3 * * * cd /app/backend && /usr/bin/python3 cron_cleanup.py >> /var/log/chess-coach/cleanup.log 2>&1
```

---

## 4. Docker/Kubernetes Considerations

If running in Docker/Kubernetes, you have two options:

### Option A: Sidecar Container
Run a separate container with cron:

```yaml
# docker-compose.yml addition
services:
  cron:
    build:
      context: .
      dockerfile: Dockerfile.cron
    environment:
      - MONGO_URL=${MONGO_URL}
      - DB_NAME=${DB_NAME}
    depends_on:
      - mongodb
```

### Option B: Kubernetes CronJob
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: chess-coach-sync
spec:
  schedule: "0 */6 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: sync
            image: chess-coach:latest
            command: ["python", "cron_sync_games.py"]
            env:
            - name: MONGO_URL
              valueFrom:
                secretKeyRef:
                  name: chess-coach-secrets
                  key: mongo-url
          restartPolicy: OnFailure
```

---

## Summary Table

| Task | Frequency | Built-in? | Cron Needed? |
|------|-----------|-----------|--------------|
| Game Sync | Every 6 hours | ✅ Yes | Optional (backup) |
| Weekly Emails | Weekly (Monday) | ❌ No | ✅ Yes (if using emails) |
| DB Cleanup | Daily | ❌ No | ✅ Recommended |
| Session Expiry | Continuous | ✅ TTL Index | ❌ No |

---

## Environment Variables for Cron Scripts

Make sure your cron scripts have access to:

```bash
export MONGO_URL="mongodb://your-host:27017"
export DB_NAME="chess_coach"
export SENDGRID_API_KEY="your-key"  # For email scripts
export SENDER_EMAIL="noreply@yourdomain.com"
```

Or add them to `/etc/environment` or use a `.env` file loader in your scripts.

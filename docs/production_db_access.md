# Production MongoDB — access

**Status:** available. Verified 2026-08-28.

**No credentials appear in this file, deliberately.** Production DB credentials
were stripped from 34 tracked files in an earlier security commit; re-adding them
to a tracked document would undo that. Every method below reads the credentials
from the place they already live — the backend container's environment.

---

## ⚠ Read this first: the port is publicly exposed

`docker-compose.yml` carries this comment on the mongodb service:

> `# Bound to localhost only (2026-07-14 security hardening): the DB was`
> `# publicly reachable on 0.0.0.0 with root creds. Remote access goes via`
> `# SSH tunnel (ssh -L 27018:localhost:27017), never a public bind.`

**The line underneath it does not do that.**

```yaml
- "27017:27017"          # binds 0.0.0.0 — the whole internet
```

Verified on 2026-08-28:

| Check | Result |
|---|---|
| `docker port chess-coach-mongodb` | `27017/tcp -> 0.0.0.0:27017` |
| Connect from a laptop over the internet | **succeeds** |
| `ufw status` | **inactive** — no firewall |
| Read data without credentials | **blocked** (auth is on) |

So the data is not directly readable — authentication *is* enforced — but the
database is listening to the public internet with no firewall in front of it.
That leaves a live brute-force and credential-stuffing surface, and turns any
future MongoDB CVE into a remotely reachable one.

**The fix is one line**, and it makes the code match the comment that has been
sitting above it since July:

```yaml
- "127.0.0.1:27017:27017"
```

Then `docker compose up -d mongodb`. Everything in this document keeps working
afterwards — methods 1 and 3 do not depend on the public bind. Method 2 is the
only one that does, and it is the one that should stop working.

---

## Connection facts

| | |
|---|---|
| Host | `72.60.204.176` |
| Container | `chess-coach-mongodb` (image `mongo:7.0`) |
| Database | `chess_coach` |
| Credentials | `MONGO_URL` and `DB_NAME` inside the `chess-coach-backend` container |
| Backend app root in container | `/app/backend` |
| Repo on server | `/root/repos/smartchesscoach` |

Read the connection string without printing the password:

```bash
ssh root@72.60.204.176 'docker exec chess-coach-backend printenv MONGO_URL' \
  | sed 's/:[^:@]*@/:***@/'
```

---

## Method 1 — SSH + `docker exec` (recommended)

The most reliable path, and the one used for every measurement in the analysis
docs. Credentials never leave the server and never touch your shell history.

Write a script locally, pipe it in:

```bash
ssh root@72.60.204.176 'docker exec -i chess-coach-backend python -' < query.py
```

```python
# query.py
import os
from pymongo import MongoClient
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
print(db.move_observations.count_documents({"schema_version": 17}))
```

For a module that isn't deployed yet, copy it in first:

```bash
ssh root@72.60.204.176 'cat > /tmp/mod.py' < backend/services/mod.py
ssh root@72.60.204.176 'docker cp /tmp/mod.py chess-coach-backend:/app/backend/services/mod.py'
```

Add `sys.path.insert(0, "/app/backend")` at the top of the query script to import
project modules.

## Method 2 — direct connection (works today; should stop working)

```
mongodb://<user>:<pass>@72.60.204.176:27017/?authSource=admin
```

Only possible because of the exposed bind above. Do not build tooling on this.

## Method 3 — SSH tunnel (the intended remote path)

```bash
ssh -L 27018:localhost:27017 root@72.60.204.176
# then connect to mongodb://<user>:<pass>@localhost:27018/?authSource=admin
```

Documented as chronically flaky in practice; prefer method 1.

---

## Collections that matter

| Collection | Count (2026-08-28) | Notes |
|---|---|---|
| `move_observations` | **428,906** | per-move facts. **Always filter `schema_version >= 16`** — earlier rows predate the SEE fix and over-fired by ~⅓ |
| `game_analyses` | 13,425 | moves at `stockfish_analysis.move_evaluations` |
| `games` | 14,021 | see the date gotcha below |
| `users` | 120 | |
| `community_training_positions` | 37,266 | `fen`, both moves, difficulty, source rating |
| `user_active_focus` | ~272 | the canonical focus spine |

## Gotchas that have already cost time

- **`games` has no `created_at`.** The field is `imported_at`, stored as an
  **ISO string**, not a BSON date. Querying `created_at` returns zero silently
  and looks exactly like "no active users".
- **`$sample` is not seeded.** Two runs give different samples. A small
  difference between runs is sampling noise, not a contradiction.
- **`schema_version` 17 is current** (adds `piece_safety.d_live.v1`); 16 added
  SEE-based `simple_hang`. Anything below 16 must not enter a baseline.
- **Mixed timestamp types.** Some collections store ISO strings, others BSON
  datetimes. Never compare the two directly.

---

## The pattern worth noticing

Twice in one week the same failure shape appeared: a comment describing a fix
that the code beneath it does not implement.

- The frontend build wrote to `/var/www/html/SMART_CHESS_COACH` while nginx
  served `/var/www/chessguru.ai` — three weeks of deploys reached nobody.
- Mongo's port comment claims a localhost bind that the port line does not make.

Neither failed loudly. Both were found only by checking the live system against
what the code claimed. Worth applying to anything else documented as "hardened".

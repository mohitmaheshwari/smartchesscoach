"""
Production indexes for the coaching query paths.
=================================================

Idempotent. Safe to re-run: every index is created only if absent, and all
builds are background so the collections stay readable and writable.

WHY THIS FILE EXISTS
--------------------
These indexes were first created by hand over SSH on 2026-08-29 while
diagnosing a server at load 13.7 on 4 cores. That fixed the running box and
nothing else: a fresh deploy, a restored backup, or a second environment would
have come up without them and quietly gone back to scanning. Committing the
migration is what makes the fix reproducible.

WHAT WAS ACTUALLY SCANNING (measured, not guessed)
--------------------------------------------------
`db.currentOp()` on the live server caught two COLLSCANs:

    op=update   ns=chess_coach.analysis_queue   plan=COLLSCAN
                q: {"game_id": "coach_c7888237-a0f"}
    op=getmore  ns=chess_coach.game_analyses    plan=COLLSCAN   secs_running=46

The first ran on every analysis job, continuously. The second was a 46-second
scan of 13.7k analyses. Both are now IXSCAN, verified with an explain in
queryPlanner mode.

TWO MISTAKES WORTH RECORDING
----------------------------
Both were caught by measuring, not by reading the code back.

1. INDEX ORDER. A first attempt added {schema_version: 1, subtype: 1}. The
   planner ignored it and kept scanning -- correctly. Measured selectivity
   across 430,245 documents:

       schema_version  6 values, two dominant (15: 268,968 | 16: 149,886)
       subtype        29 values, present on only 41,373 docs (9.6%)

   Leading with schema_version indexes nearly the whole collection, which is
   cheaper to skip than to walk. What makes an index useful is the
   SELECTIVITY of its leading field, not how often the field appears in a
   filter. Reordered to lead with `subtype`.

2. PARTIAL FILTER. The reordered index was first built with
   partialFilterExpression {subtype: {$type: "string"}} and was STILL never
   used. The planner cannot prove that an equality match on a string is a
   subset of a $type predicate, so it silently declined the index -- no
   error, just a scan:

       {"subtype": "simple_hang", ...}          -> COLLSCAN
       {"subtype": {"$type": "string"}, ...}    -> IXSCAN

   Same index; only the phrasing differed. {$exists: true} is a form the
   planner CAN reason about, and plain equality now plans IXSCAN.

   The general lesson: creating an index is not the same as the index being
   used. Always confirm with an explain in queryPlanner mode, using the
   filter the application actually sends.
"""

import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient

# (collection, keys, name, extra kwargs)
INDEXES = [
    # The analysis worker updates by game_id on every job.
    ("analysis_queue", [("game_id", 1)], "aq_game_id", {}),
    # Stale-job reset sweeps on status + heartbeat.
    ("analysis_queue", [("status", 1), ("last_heartbeat", 1)], "aq_status_heartbeat", {}),
    # Game review looks analyses up by game_id; only user_id was indexed.
    ("game_analyses", [("game_id", 1)], "ga_game_id", {}),
    # Detector and curriculum queries filter by subtype. Partial because only
    # 9.6% of rows carry one -- the rest do not belong in the index.
    # The filter MUST be $exists, not $type: see note 2 above.
    (
        "move_observations",
        [("subtype", 1), ("schema_version", 1)],
        "mo_subtype_schema",
        {"partialFilterExpression": {"subtype": {"$exists": True}}},
    ),
]

# Created during diagnosis, then measured as unused: schema_version is not
# selective enough to lead an index. Dropped so it stops costing write
# throughput on a 430k collection for nothing.
DROP = [
    ("move_observations", "mo_schema_subtype"),   # wrong leading field
    ("move_observations", "mo_user_schema"),      # redundant with user_id_1_derived_at_-1
]


async def run(db) -> None:
    for coll, name in DROP:
        existing = await db[coll].index_information()
        if name in existing:
            await db[coll].drop_index(name)
            print(f"  dropped {coll}.{name}")

    for coll, keys, name, extra in INDEXES:
        existing = await db[coll].index_information()
        if name in existing:
            print(f"  {name} already present")
            continue
        await db[coll].create_index(keys, name=name, background=True, **extra)
        print(f"  created {coll}.{name}")


async def main() -> None:
    url = os.environ.get("MONGO_URL")
    dbname = os.environ.get("DB_NAME")
    if not url or not dbname:
        raise SystemExit("MONGO_URL and DB_NAME must be set (they live in the backend container)")
    client = AsyncIOMotorClient(url)
    try:
        await run(client[dbname])
        print("done")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())

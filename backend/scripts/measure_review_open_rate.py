#!/usr/bin/env python3
"""Who opens a game review, and how soon after the game was imported?

This answers open question 1 of docs/lichess_instant_review_scope.md. The
instant-review watcher cut play -> imported from ~5-22 minutes to seconds.
Whether that mattered depends on one number: does anyone open the review of a
game they just played? Section 5 of docs/play_through_lichess_scope.md
measures the play-through board against the same number, so this is the
baseline for both.

Run it ON THE PROD HOST (nginx's logs only exist there), from a directory
that is not /root, with -I:

    cd /root/measure && python3 -I measure_review_open_rate.py --days 14

`-I` matters: there is a /root/struct.py on the prod box that shadows the
stdlib `struct` module, so any python started from /root dies on `import gzip`.

Method
------
A review open is GET /api/coach/decryption/v5/{game_id}. That is the only call
GameDecryptionV5 makes to load a game (frontend/src/components/
GameDecryptionV5.jsx), and the game_id sits in the path, so nginx's default
`combined` format suffices -- we never need the session cookie it does not
log. game_id -> user_id comes from the games collection.

Four traps this encodes. Each one produced a wrong answer by hand first:

1. `imported_at` in `games` is a STRING, not a BSON date. A
   `{"$gte": datetime(...)}` filter matches NOTHING and returns a confident
   zero. Compare ISO-8601 string prefixes instead.

2. Our own traffic dominates. python-requests, curl, HeadlessChrome (the
   playwright runs), crawlers and the docker-internal 172.x range are all
   ours, and are excluded.

3. Internal accounts dominate what is left. On 2026-11-25, 10 of 19 opens
   were the developer's own account plus "Coach Test". Reporting a rate
   without splitting those out overstates real usage roughly 2x.

4. The per-game rate over ALL imported games is meaningless: imports are
   bulk, ~72 games per user per fortnight, and nobody reviews 72 games. The
   number that bears on the watcher is opens where the review was opened the
   same day the game was imported. That is what `--days` windows.

Also: the frontend re-polls one game_id every ~6s while analysis is pending,
so raw hit counts are not read counts. Distinct game_id is the unit.

Not to be confused with `what_a_real_user_sees.py`, which asks whether a page
RENDERS for ordinary users by calling it as them. That script says so itself:
"[it does not] exercise nginx or auth; those failures show up in the access log
instead." This script is the access-log half. Neither replaces the other.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import gzip
import io
import json
import re
import subprocess
import sys
from typing import Dict, Iterator, List, Tuple

OPEN_RE = re.compile(r"GET /api/coach/decryption/v5/([^ ?&\"]+)")
TS_RE = re.compile(r"\[(\d{2})/(\w{3})/(\d{4}):")

# Traffic we generate ourselves. Never counted as a read.
OURS_UA = ("python-requests", "curl/", "headlesschrome", "bot", "spider", "wget")
OURS_IP = ("172.", "127.0.0.1", "10.")

# Internal accounts, matched on the users collection `name`. Reported
# separately rather than dropped, so the split stays visible.
INTERNAL_NAMES = ("Mohit Maheshwari", "Coach Test")

MONTHS = {
    m: i
    for i, m in enumerate(
        "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1
    )
}


def log_lines(patterns: List[str]) -> Iterator[str]:
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            opener = gzip.open if path.endswith(".gz") else io.open
            try:
                with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
                    yield from fh
            except OSError as exc:  # rotated out from under us
                print(f"  (skipped {path}: {exc})", file=sys.stderr)


def is_ours(line: str) -> bool:
    if any(line.startswith(prefix) for prefix in OURS_IP):
        return True
    lowered = line.lower()
    return any(marker in lowered for marker in OURS_UA)


def collect_opens(patterns: List[str]) -> Tuple[Dict[str, str], collections.Counter]:
    """-> ({game_id: earliest day opened}, opens per day). Distinct games only."""
    first_day: Dict[str, str] = {}
    per_day: collections.Counter = collections.Counter()
    for line in log_lines(patterns):
        match = OPEN_RE.search(line)
        if not match or is_ours(line):
            continue
        stamp = TS_RE.search(line)
        if not stamp:
            continue
        day, mon, year = stamp.groups()
        iso = f"{year}-{MONTHS[mon]:02d}-{day}"
        game_id = match.group(1)
        per_day[iso] += 1
        if game_id not in first_day or iso < first_day[game_id]:
            first_day[game_id] = iso
    return first_day, per_day


# Runs inside the backend container, which holds MONGO_URL. Kept to plain
# %-formatting: the container's python predates PEP 701, so nested quotes in
# an f-string are a SyntaxError there.
MONGO_PROGRAM = """
import os, asyncio, json
from motor.motor_asyncio import AsyncIOMotorClient

OPENED = json.loads(%(opened)s)   # {game_id: day opened}
SINCE = %(since)s

async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]
    window = {"imported_at": {"$gte": SINCE}}   # STRING compare, see docstring
    out = {
        "imported": await db.games.count_documents(window),
        "importers": len(await db.games.distinct("user_id", window)),
        "rows": [],
    }
    for game_id, opened_day in OPENED.items():
        game = await db.games.find_one(
            {"game_id": game_id}, {"user_id": 1, "imported_at": 1}
        )
        user_id = (game or {}).get("user_id")
        user = await db.users.find_one({"user_id": user_id}, {"name": 1}) if user_id else None
        out["rows"].append({
            "game_id": game_id,
            "opened": opened_day,
            "imported": str((game or {}).get("imported_at"))[:10],
            "user_id": user_id,
            "name": (user or {}).get("name") or "?",
        })
    print(json.dumps(out))

asyncio.run(main())
"""


def query_mongo(container: str, opened: Dict[str, str], since: str) -> dict:
    program = MONGO_PROGRAM % {
        "opened": repr(json.dumps(opened)),
        "since": repr(since),
    }
    result = subprocess.run(
        ["docker", "exec", "-i", container, "python", "-"],
        input=program,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        sys.exit(f"mongo query failed:\n{result.stderr.strip()}")
    return json.loads(result.stdout.strip().splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument(
        "--logs",
        nargs="+",
        default=["/var/log/nginx/access.log", "/var/log/nginx/access.log.*"],
    )
    parser.add_argument("--container", default="chess-coach-backend")
    args = parser.parse_args()

    since = (dt.date.today() - dt.timedelta(days=args.days)).isoformat()
    print(f"window: {since} .. today  ({args.days} days)\n")

    first_day, per_day = collect_opens(args.logs)
    if not first_day:
        # A zero needs a positive control: did the scanner see ANY api traffic?
        any_api = sum(1 for line in log_lines(args.logs) if "/api/" in line)
        print(f"NO review opens found. Lines mentioning /api/ in the same logs: {any_api}")
        if any_api == 0:
            sys.exit("these logs hold no /api/ traffic at all -- wrong path, not a real zero")
        return

    data = query_mongo(args.container, first_day, since)
    rows = [r for r in data["rows"] if r["opened"] >= since]
    rows.sort(key=lambda r: r["opened"])

    print(f"{'game':<40} {'opened':<11} {'imported':<11} {'who':<20} same-day")
    for row in rows:
        same = "YES" if row["imported"] == row["opened"] else ""
        print(f"{row['game_id']:<40} {row['opened']:<11} {row['imported']:<11} "
              f"{row['name'][:20]:<20} {same}")

    real = [r for r in rows if r["name"] not in INTERNAL_NAMES]
    internal = [r for r in rows if r["name"] in INTERNAL_NAMES]
    real_same_day = [r for r in real if r["imported"] == r["opened"]]

    print(f"\ngames imported in window:       {data['imported']}"
          f"  (by {data['importers']} users)")
    print(f"review opens, distinct games:   {len(rows)}")
    print(f"  by internal accounts:         {len(internal)}  ({', '.join(INTERNAL_NAMES)})")
    print(f"  by real users:                {len(real)}"
          f"  across {len({r['user_id'] for r in real})} users")
    print(f"  by real users, SAME DAY as import: {len(real_same_day)}"
          f"  across {len({r['user_id'] for r in real_same_day})} users")
    if real_same_day:
        print("    " + ", ".join(sorted({r["name"] for r in real_same_day})))

    print("\nopens per day (hits, not distinct games):")
    for day in sorted(per_day):
        if day >= since:
            print(f"  {day}  {per_day[day]}")


if __name__ == "__main__":
    main()

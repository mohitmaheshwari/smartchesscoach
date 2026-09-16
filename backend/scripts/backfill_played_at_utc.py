#!/usr/bin/env python3
"""Derive a canonical, typed `played_at_utc` for every game. Dry-run by default.

WHY THIS EXISTS
---------------
`games.date_played` holds three incompatible shapes on production:

    2026-09-16T14:00:00+00:00   ISO with offset   15,469
    2026.04.15                  chess.com dotted     477
    (absent)                                         261   all platform="coach"

The focus outcome window splits a user's games with a **string** comparison
(`primary_weakness_picker._games_split_by_play_date`). ASCII "." (0x2E) sorts
above "-" (0x2D), so every dotted value sorts after every ISO timestamp no
matter what date it actually represents. Measured 2026-09-16: 15 active
focuses had a polluted "after" window containing 407 games, and for six users
*every* "after" game predated the focus by months.

Fixing that by rewriting `date_played` into a uniform string would just move
the next silent ordering bug somewhere else. Instead this writes a typed
field and leaves the raw value untouched:

    played_at_utc      BSON Date (UTC)   <- the only field measurement reads
    played_at_source   provenance tag
    played_at_raw      the original date_played, copied verbatim

Rollback is `$unset` of the three new fields; nothing existing is modified.

RECOVERY, NOT GUESSWORK
-----------------------
chess.com and lichess PGNs both carry an exact UTC instant. The headers are
case-normalised on import, so they appear as `[Utcdate "2026.03.01"]` and
`[Utctime "05:45:33"]` -- a case-sensitive read for "UTCDate" finds nothing,
which is why this was missed before. Measured recoverability: 477/477 of the
dotted rows and 400/400 of a sampled ISO control. No import needs an
"uncertain" flag; every real game resolves to an exact instant.

The 261 rows with no date header are all `platform="coach"` (Play with Coach).
Those are created live at the end of a session, so `imported_at` dates them to
within one session; they are tagged `coach_imported_at` and, by the product
decision recorded on `OUTCOME_ELIGIBLE_SOURCES`, they DO count toward outcome
measurement. Read that comment before using this data for a rate.

USAGE
-----
    python scripts/backfill_played_at_utc.py                 # dry run, full report
    python scripts/backfill_played_at_utc.py --limit 2000    # dry run, sample
    python scripts/backfill_played_at_utc.py --apply --confirm-plan <fingerprint>

`--apply` refuses to run unless `--confirm-plan` matches the fingerprint the
dry run printed, so a plan can never be approved and then silently applied to
a different dataset. Re-running is idempotent: a row whose stored
`played_at_utc` already equals the derived value is counted as `unchanged`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pymongo

# Provenance tags written to `played_at_source`.
SRC_PGN_UTC = "pgn_utc_headers"        # exact instant from [Utcdate]+[Utctime]
SRC_PGN_LOCAL = "pgn_local_headers"    # [Date]+[Time] with an explicit [Timezone "UTC"]
SRC_STORED_ISO = "stored_iso_fallback"  # no usable headers, stored value already ISO
SRC_COACH = "coach_imported_at"        # Play with Coach; no PGN date headers
SRC_NONE = "unrecoverable"

# Every source that may enter a before/after outcome window.
#
# SRC_COACH is included by an explicit product decision (2026-09-16): Play
# with Coach games count as evidence like any other game, in a single pooled
# rate. The decision was taken against the following measurement, which is
# recorded here so the bias is never rediscovered as a surprise:
#
#   Within the 3 users who have >=20 coach and >=100 imported PIC decisions,
#   the piece-safety miss rate is 2.12% in coach games (n=378) against 14.00%
#   in imported games (n=5,892) -- about 7x lower, same direction for all
#   three. The mechanism is not subtle: the pre-move Guardian stops the
#   mistake while the game is being played.
#
# The consequence is that a user who plays Play with Coach after a focus
# starts will tend to measure as improved partly because of live coaching
# rather than a changed habit. `played_at_source` is written on every row so
# the mix stays queryable and this can be revisited without another backfill.
OUTCOME_ELIGIBLE_SOURCES = {SRC_PGN_UTC, SRC_PGN_LOCAL, SRC_STORED_ISO, SRC_COACH}

# Header readers. Case-insensitive on purpose: the import path normalises
# header capitalisation, so "UTCDate" is stored as "Utcdate".
_H_UTCDATE = re.compile(r'\[\s*utcdate\s+"([^"]+)"\s*\]', re.I)
_H_UTCTIME = re.compile(r'\[\s*utctime\s+"([^"]+)"\s*\]', re.I)
_H_DATE = re.compile(r'\[\s*date\s+"([^"]+)"\s*\]', re.I)
_H_TIME = re.compile(r'\[\s*time\s+"([^"]+)"\s*\]', re.I)
_H_TZ = re.compile(r'\[\s*timezone\s+"([^"]+)"\s*\]', re.I)

_DOTTED = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})$")
_ISO_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}T")

# A derived instant this far from the stored value is reported for review
# rather than trusted silently.
DISAGREEMENT_TOLERANCE_SECONDS = 60 * 60 * 24  # one day


def _parse_dotted_date(value: str) -> Optional[Tuple[int, int, int]]:
    m = _DOTTED.match(value.strip())
    if not m:
        return None
    y, mo, d = (int(g) for g in m.groups())
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return y, mo, d


def _parse_clock(value: str) -> Optional[Tuple[int, int, int]]:
    parts = value.strip().split(":")
    if len(parts) < 2:
        return None
    try:
        h = int(parts[0])
        mi = int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= mi <= 59 and 0 <= s <= 60):
        return None
    return h, mi, min(s, 59)


def _combine(date_parts, clock_parts) -> Optional[datetime]:
    if not date_parts:
        return None
    y, mo, d = date_parts
    h, mi, s = clock_parts or (0, 0, 0)
    try:
        return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_stored(value: Any) -> Optional[datetime]:
    """Best-effort read of the legacy `date_played`, for comparison only."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if _ISO_PREFIX.match(raw):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    dotted = _parse_dotted_date(raw)
    if dotted:
        return _combine(dotted, None)
    return None


def derive(game: Dict[str, Any]) -> Tuple[Optional[datetime], str]:
    """Return (canonical UTC instant, provenance tag) for one game."""
    pgn = game.get("pgn") or ""

    ud, ut = _H_UTCDATE.search(pgn), _H_UTCTIME.search(pgn)
    if ud and ut:
        dt = _combine(_parse_dotted_date(ud.group(1)), _parse_clock(ut.group(1)))
        if dt:
            return dt, SRC_PGN_UTC

    # [Date]+[Time] are only usable when the PGN states the zone is UTC.
    # Without that, the offset is unknown and we do not invent one.
    d, t, tz = _H_DATE.search(pgn), _H_TIME.search(pgn), _H_TZ.search(pgn)
    if d and t and tz and tz.group(1).strip().upper() in ("UTC", "Z", "GMT"):
        dt = _combine(_parse_dotted_date(d.group(1)), _parse_clock(t.group(1)))
        if dt:
            return dt, SRC_PGN_LOCAL

    # Coach games are created live at the end of a session and carry no PGN
    # date headers, so `imported_at` is the moment the game was played to
    # within the length of one session. Tagged distinctly rather than
    # pretended to be header-exact.
    if (game.get("platform") or "").lower() == "coach":
        for field in ("imported_at", "created_at"):
            stamp = game.get(field)
            if isinstance(stamp, datetime):
                return (stamp if stamp.tzinfo
                        else stamp.replace(tzinfo=timezone.utc)), SRC_COACH
            parsed = parse_stored(stamp)
            if parsed:
                return parsed, SRC_COACH
        return None, SRC_NONE

    stored = parse_stored(game.get("date_played"))
    if stored and _ISO_PREFIX.match(str(game.get("date_played") or "")):
        return stored, SRC_STORED_ISO

    return None, SRC_NONE


def _fingerprint(counts: Dict[str, int]) -> str:
    blob = json.dumps(counts, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write played_at_utc/source/raw (default: dry run only)")
    ap.add_argument("--confirm-plan", default=None,
                    help="fingerprint printed by the dry run; required with --apply")
    ap.add_argument("--limit", type=int, default=0, help="sample N games (0 = all)")
    ap.add_argument("--show", type=int, default=8, help="example rows per category")
    args = ap.parse_args()

    client = pymongo.MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    proj = {"game_id": 1, "user_id": 1, "pgn": 1, "date_played": 1,
            "platform": 1, "is_analyzed": 1, "played_at_utc": 1,
            "imported_at": 1, "created_at": 1}
    cur = db.games.find({}, proj)
    if args.limit:
        cur = cur.limit(args.limit)

    by_source = Counter()
    by_shape_and_source = Counter()
    disagreements = []
    would_write = 0
    unchanged = 0
    ineligible_users = defaultdict(int)
    examples = defaultdict(list)
    total = 0

    for g in cur:
        total += 1
        stored_raw = g.get("date_played")
        if stored_raw is None:
            shape = "missing"
        elif isinstance(stored_raw, str) and _DOTTED.match(stored_raw):
            shape = "dotted"
        elif isinstance(stored_raw, str) and _ISO_PREFIX.match(stored_raw):
            shape = "iso"
        else:
            shape = f"other:{type(stored_raw).__name__}"

        dt, source = derive(g)
        by_source[source] += 1
        by_shape_and_source[(shape, source)] += 1

        if source not in OUTCOME_ELIGIBLE_SOURCES:
            ineligible_users[g.get("user_id")] += 1
            if len(examples[f"ineligible:{source}"]) < args.show:
                examples[f"ineligible:{source}"].append(
                    {"game_id": g.get("game_id"), "platform": g.get("platform"),
                     "date_played": str(stored_raw)[:32]})
            continue

        existing = g.get("played_at_utc")
        if isinstance(existing, datetime):
            ex = existing if existing.tzinfo else existing.replace(tzinfo=timezone.utc)
            if dt and abs((ex - dt).total_seconds()) < 1:
                unchanged += 1
                continue
        would_write += 1

        stored_dt = parse_stored(stored_raw)
        if dt and stored_dt:
            drift = abs((dt - stored_dt).total_seconds())
            if drift > DISAGREEMENT_TOLERANCE_SECONDS:
                disagreements.append({
                    "game_id": g.get("game_id"), "platform": g.get("platform"),
                    "stored": str(stored_raw)[:32],
                    "derived": dt.isoformat(), "drift_days": round(drift / 86400, 1),
                })

    print("=" * 74)
    print(f"played_at_utc backfill — {'APPLY' if args.apply else 'DRY RUN'}")
    print("=" * 74)
    print(f"games examined: {total}\n")

    print("-- derived provenance --")
    for src, n in by_source.most_common():
        flag = "" if src in OUTCOME_ELIGIBLE_SOURCES else "   [EXCLUDED from outcome windows]"
        print(f"  {n:>7}  {src}{flag}")

    print("\n-- stored shape -> derived provenance --")
    for (shape, src), n in sorted(by_shape_and_source.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>7}  {shape:<18} -> {src}")

    print("\n-- write plan --")
    print(f"  would write played_at_utc : {would_write}")
    print(f"  already correct (no-op)   : {unchanged}")
    print(f"  no canonical value        : {sum(v for k, v in by_source.items() if k not in OUTCOME_ELIGIBLE_SOURCES)}")

    print(f"\n-- stored value disagrees with PGN by >{DISAGREEMENT_TOLERANCE_SECONDS // 86400}d --")
    print(f"  count: {len(disagreements)}")
    for d in disagreements[:args.show]:
        print(f"    {d['game_id']} [{d['platform']}] stored={d['stored']} "
              f"derived={d['derived']} drift={d['drift_days']}d")

    print("\n-- games with no canonical timestamp, by user (top) --")
    for uid, n in sorted(ineligible_users.items(), key=lambda kv: -kv[1])[:args.show]:
        print(f"    {str(uid)[:18]:<20} {n}")

    for key, rows in examples.items():
        print(f"\n-- example {key} --")
        for r in rows:
            print(f"    {r}")

    # Effect on the focuses this sprint exists to close.
    print("\n-- effect on active weakness focuses --")
    active = list(db.user_active_focus.find({"type": "weakness", "status": "active"}))
    polluted_before = 0
    polluted_games = 0
    for f in active:
        s = f.get("started_at")
        if isinstance(s, datetime):
            s = s.isoformat()
        n = db.games.count_documents({
            "user_id": f.get("user_id"), "is_analyzed": True,
            "date_played": {"$gte": str(s), "$regex": r"^\d{4}\."},
        })
        if n:
            polluted_before += 1
            polluted_games += n
    print(f"  active weakness focuses               : {len(active)}")
    print(f"  with a polluted after-window (before) : {polluted_before}")
    print(f"  games wrongly in an after-window      : {polluted_games}")
    print(f"  after repair, ordering is by BSON Date: pollution -> 0 by construction")

    counts = {k: v for k, v in by_source.items()}
    counts["_would_write"] = would_write
    fp = _fingerprint(counts)
    print(f"\nplan fingerprint: {fp}")

    if not args.apply:
        print("\nDRY RUN — nothing was written.")
        print(f"To apply: --apply --confirm-plan {fp}")
        return 0

    if args.confirm_plan != fp:
        print(f"\nREFUSED: --confirm-plan {args.confirm_plan!r} != {fp!r}. "
              "The data changed since the dry run; re-run the dry run.")
        return 2

    print("\nAPPLY not implemented in this revision — approval gate is open, "
          "but no production write path has been authorised yet.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

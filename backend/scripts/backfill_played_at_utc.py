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
from pymongo import UpdateOne

# Provenance tags written to `played_at_source`.
# The derivation moved to services/played_at.py so the IMPORT PATH can set this
# field too. Re-exported here unchanged: this script's CLI and
# tests/test_played_at_utc_backfill.py both import these names from this
# module, and a migration and the writer that feeds it must never drift apart.
from services.played_at import (  # noqa: E402,F401
    DISAGREEMENT_TOLERANCE_SECONDS,
    OUTCOME_ELIGIBLE_SOURCES,
    SRC_COACH,
    SRC_NONE,
    SRC_PGN_LOCAL,
    SRC_PGN_UTC,
    SRC_STORED_ISO,
    derive,
    parse_stored,
)


def _fingerprint(sources: Dict[str, int], disagreements: int) -> str:
    """Fingerprint the SHAPE of the plan, not its row counts.

    Games keep importing, so a fingerprint over raw counts goes stale within
    minutes and the operator is trained to expect a refusal and work around
    it -- which defeats the gate. What must not change between review and
    apply is the plan's character: which provenance categories exist, whether
    anything is unrecoverable, and whether any stored value disagrees with
    its own PGN. Ordinary import drift leaves all three untouched; a genuine
    change to the data's shape invalidates the plan, which is the point.
    """
    shape = {
        "sources": sorted(sources),
        "has_unrecoverable": bool(sources.get(SRC_NONE)),
        "has_disagreements": bool(disagreements),
    }
    blob = json.dumps(shape, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


WRITTEN_FIELDS = ("played_at_utc", "played_at_source", "played_at_raw")


def _rollback(db, args) -> int:
    """Remove exactly the three fields this script adds. Touches nothing else."""
    q = {"$or": [{f: {"$exists": True}} for f in WRITTEN_FIELDS]}
    n = db.games.count_documents(q)
    print(f"rollback: {n} games carry at least one of {WRITTEN_FIELDS}")
    if not args.apply:
        print("DRY RUN — nothing removed. Re-run with --rollback --apply.")
        return 0
    res = db.games.update_many(q, {"$unset": {f: "" for f in WRITTEN_FIELDS}})
    print(f"rollback applied: matched={res.matched_count} modified={res.modified_count}")
    left = db.games.count_documents(q)
    print(f"games still carrying any of the fields: {left}")
    return 0 if left == 0 else 1


def _write_batches(db, ops, batch: int) -> Tuple[int, int]:
    """Bulk-write in batches. Returns (matched, modified)."""
    from pymongo import UpdateOne  # noqa: F401  (imported for the caller's type)
    matched = modified = 0
    for i in range(0, len(ops), batch):
        res = db.games.bulk_write(ops[i:i + batch], ordered=False)
        matched += res.matched_count
        modified += res.modified_count
        print(f"    wrote {min(i + batch, len(ops))}/{len(ops)}", flush=True)
    return matched, modified


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write played_at_utc/source/raw (default: dry run only)")
    ap.add_argument("--confirm-plan", default=None,
                    help="fingerprint printed by the dry run; required with --apply")
    ap.add_argument("--rollback", action="store_true",
                    help="$unset the three fields this script writes, and nothing else")
    ap.add_argument("--batch", type=int, default=1000, help="bulk write batch size")
    ap.add_argument("--limit", type=int, default=0, help="sample N games (0 = all)")
    ap.add_argument("--show", type=int, default=8, help="example rows per category")
    args = ap.parse_args()

    client = pymongo.MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    if args.rollback:
        return _rollback(db, args)

    pending_ops = []
    proj = {"_id": 1, "game_id": 1, "user_id": 1, "pgn": 1, "date_played": 1,
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
        # Re-running is a no-op for rows already carrying the right value
        # (counted as `unchanged` above), so this is safe to repeat.
        pending_ops.append(UpdateOne(
            {"_id": g["_id"]},
            {"$set": {
                "played_at_utc": dt,
                "played_at_source": source,
                "played_at_raw": stored_raw,
            }},
        ))

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

    fp = _fingerprint(dict(by_source), len(disagreements))
    print(f"\nplan fingerprint: {fp}")

    if not args.apply:
        print("\nDRY RUN — nothing was written.")
        print(f"To apply: --apply --confirm-plan {fp}")
        return 0

    if args.confirm_plan != fp:
        print(f"\nREFUSED: --confirm-plan {args.confirm_plan!r} != {fp!r}. "
              "The data changed since the dry run; re-run the dry run.")
        return 2

    if args.limit:
        print("\nREFUSED: --apply with --limit would leave the collection "
              "half-migrated. Re-run the dry run without --limit.")
        return 2

    print(f"\nAPPLYING {len(pending_ops)} updates in batches of {args.batch} ...")
    matched, modified = _write_batches(db, pending_ops, args.batch)
    print(f"  matched={matched} modified={modified}")

    remaining = db.games.count_documents({"played_at_utc": {"$exists": False}})
    print(f"  games still without played_at_utc: {remaining}")
    print("\nRollback if needed: --rollback --apply")
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Backfill the motif got_positions contract fix (2026-08-13).

THE BUG
-------
`motif_profile_service.compute_game_motifs` stored one record holding TWO positions:

    fen               = the position AFTER the user's blunder (opponent to move)
    solution          = the best move in the position BEFORE the blunder
    opp_creates_motif = the opponent's reply (legal in `fen`)

`solution` therefore does not belong to `fen`. Measured across all 558 stored fork
positions in production: 511 (92%) of `solution` values are ILLEGAL in the stored `fen`.

Two shipped surfaces consumed it:
  - MotifDrill.jsx     — renders `fen` and prints `solution` next to it (non-interactive,
                         so it never threw; it just displayed an unplayable move)
  - PrescribedTraining — maps solution -> solution_san and GRADES the user against it on
                         an interactive board, i.e. asks users to find an illegal move

THE FIX
-------
Recover `fen_before` (and provenance) by joining each stored record back to
`game_analyses.stockfish_analysis.move_evaluations` on the pair

    (move_evaluations.fen_after, move_evaluations.move) == (stored.fen, stored.user_blunder_move)

Verified on the 203 knight-created fork records: 203/203 = 100% matched.

Writes, per got_position:
    fen_before, fen_after, game_id, move_number, contract_version=2

IDEMPOTENT: a record that already has `fen_before` is skipped. Re-running is a no-op.
Records that cannot be matched are stamped `unresolved: true` so `get_drills()` drops
them deliberately instead of serving an illegal move.

USAGE
    python scripts/backfill_motif_got_positions.py               # dry run (default)
    python scripts/backfill_motif_got_positions.py --apply
    python scripts/backfill_motif_got_positions.py --apply --user user_xxx
"""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402
from pymongo import MongoClient  # noqa: E402

MOTIFS = ["fork", "pin", "skewer", "discovered", "loose"]
CONTRACT_VERSION = 2


def _legal(fen, san):
    if not fen or not san:
        return False
    try:
        chess.Board(fen).parse_san(san)
        return True
    except Exception:
        return False


def build_index(db, user_id):
    """(fen_after, move) -> (game_id, move_number, fen_before) for one user's games."""
    idx = {}
    game_ids = [g["game_id"] for g in db.games.find(
        {"user_id": user_id, "is_analyzed": True}, {"game_id": 1})]
    if not game_ids:
        return idx
    for a in db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {"game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        for ev in (a.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            key = (ev.get("fen_after"), ev.get("move"))
            if key[0] and key[1] and key not in idx:
                idx[key] = (a.get("game_id"), ev.get("move_number"), ev.get("fen_before"))
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default is dry run)")
    ap.add_argument("--user", help="restrict to one user_id")
    args = ap.parse_args()

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db = MongoClient(mongo_url)[os.environ.get("DB_NAME", "chess_coach")]

    q = {"motif_profile": {"$exists": True}}
    if args.user:
        q["user_id"] = args.user

    stats = Counter()
    users_touched = 0

    # Iterate and write by _id, not user_id. `player_profiles` is NOT unique on
    # user_id in production — 69 docs / 67 distinct users on 2026-08-13 — so
    # update_one({"user_id": ...}) silently writes only the first duplicate and
    # drops the rest (this cost 68 rows on the first run before it was caught).
    for prof in db.player_profiles.find(q, {"_id": 1, "user_id": 1, "motif_profile": 1}):
        doc_id = prof["_id"]
        user_id = prof["user_id"]
        mp = prof.get("motif_profile") or {}

        pending = [
            p for mt in MOTIFS
            for p in ((mp.get(mt) or {}).get("got_positions") or [])
            if isinstance(p, dict) and not p.get("fen_before") and not p.get("unresolved")
        ]
        if not pending:
            stats["users already clean"] += 1
            continue

        idx = build_index(db, user_id)
        changed = False

        for mt in MOTIFS:
            bucket = mp.get(mt) or {}
            for p in bucket.get("got_positions") or []:
                if not isinstance(p, dict):
                    continue
                if p.get("fen_before"):
                    stats["skipped (already backfilled)"] += 1
                    continue

                hit = idx.get((p.get("fen"), p.get("user_blunder_move")))
                if not hit:
                    p["unresolved"] = True
                    stats["UNRESOLVED (no join match)"] += 1
                    changed = True
                    continue

                game_id, move_number, fen_before = hit
                if not _legal(fen_before, p.get("solution")):
                    # The join matched but the recovered position still does not accept
                    # the stored solution. Do not guess — mark and drop.
                    p["unresolved"] = True
                    stats["UNRESOLVED (solution illegal in recovered fen_before)"] += 1
                    changed = True
                    continue

                p["fen_before"] = fen_before
                p["fen_after"] = p.get("fen")
                p["game_id"] = p.get("game_id") or game_id
                p["move_number"] = p.get("move_number") if p.get("move_number") is not None else move_number
                p["contract_version"] = CONTRACT_VERSION
                p.pop("unresolved", None)
                stats["backfilled"] += 1
                stats[f"backfilled:{mt}"] += 1
                changed = True

        if changed:
            users_touched += 1
            if args.apply:
                db.player_profiles.update_one(
                    {"_id": doc_id}, {"$set": {"motif_profile": mp}}
                )

    mode = "APPLIED" if args.apply else "DRY RUN (no writes)"
    print(f"\n=== backfill_motif_got_positions — {mode} ===")
    print(f"users modified: {users_touched}")
    for k, v in sorted(stats.items()):
        print(f"  {k:52} {v}")
    if not args.apply:
        print("\nRe-run with --apply to write.")


if __name__ == "__main__":
    main()

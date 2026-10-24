"""Add Maia2 (human-policy) evidence to games already analysed by Stockfish.

Mohit, 2026-10-24: "I need games analysed for me, shobhit and parth with
stockfish (i think already done) with Maia... do it from local machine".

Runs on his machine and writes to prod through the SSH tunnel the local
container already uses. The server has the model file now but the flags are
off, because loading it costs ~800MB resident and mongodb is uncapped on a
box that OOM-kills.

Uses the GOVERNED path -- `enrich_move_evaluations_with_human_chess`, which
verifies history, legality and probability shape, and records the model's
sha256 with every row. Earlier today I wrote a second, ungoverned Maia2
script; this replaces it.

BOTH SIDES. The enrichment is colour-generic: `_user_positions(game,
user_color)` collects whichever side is to move and takes the opponent's
rating from the matching header, so "user" means "the side these rows
belong to". Calling it twice -- once per colour, ratings swapped -- covers
the opponent's moves, which is where the whole idea started: the engine
answers Nxh3+ with Kh2 while 70% of 1200s take the knight and lose it.

SIZE. Each evidence row carries the full legal-move distribution, about
3KB, so roughly 246KB a game and ~325MB across all three accounts. That
nearly doubles documents which are already ~300KB and which nothing may
scan. Run an account at a time and watch it.

Usage:
    python scripts/maia_backfill_local.py --users <uid>[,<uid>] [--limit N]
    python scripts/maia_backfill_local.py --users <uid> --limit 3 --dry-run
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set BEFORE importing the runtime: both are read at call time, but the model
# path is resolved when a provider is constructed and the flag gates the whole
# function. Pointing at the repo's own copy keeps this independent of the
# server's /opt/hci-runtime layout.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("HUMAN_CHESS_ANALYSIS_ENRICHMENT_ENABLED", "true")
os.environ.setdefault("HUMAN_POLICY_EVIDENCE_ENABLED", "true")
os.environ.setdefault(
    "MAIA2_MODEL_PATH", os.path.join(_REPO, "maia2_models", "rapid_model.pt"))

from services.human_chess_analysis_enrichment import (  # noqa: E402
    enrich_move_evaluations_with_human_chess,
)

OPP_PATH = "stockfish_analysis.opponent_move_evaluations"
USER_PATH = "stockfish_analysis.move_evaluations"


def prod_mongo_url(port: str) -> str:
    """Prod's URL, read from the running local container.

    That container tunnels to prod, so the host only has to point at
    127.0.0.1. Reading it keeps the credential out of this file and out of
    git. The port is a flag because the shared tunnel on 27018 goes
    half-open -- it keeps listening and stops forwarding, which fails as a
    timeout and reads like a dead database.
    """
    url = subprocess.check_output(
        ["docker", "exec", "chess-coach-backend", "printenv", "MONGO_URL"],
        text=True).strip()
    return url.replace("host.docker.internal:27018", "127.0.0.1:%s" % port)


def _rating(game: Dict[str, Any], colour: str) -> Optional[int]:
    """Rating off the GAME DOCUMENT, not the PGN.

    The enrichment falls back to WhiteElo/BlackElo, and 108 of 200 of
    Mohit's games carry no Elo header -- including the three most recent --
    while white_rating/black_rating are on 72.1% of them.
    """
    key = "white_rating" if str(colour).lower() == "white" else "black_rating"
    for candidate in (game.get(key), game.get("user_rating")):
        try:
            value = int(candidate or 0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def _already_done(doc: Dict[str, Any]) -> bool:
    """Done means EVIDENCE, not merely a reason.

    The first version counted any `human_policy_reason` as done, so a run
    that refused every row with `missing_measured_rating` marked 25 games
    finished and the rerun skipped them. A refusal is a thing to retry once
    its cause is fixed; only evidence is terminal.

    The cost is re-attempting games that genuinely yield nothing -- Parth's
    are all outside the validated rating band -- but those abstain before
    any model call, so a retry is cheap.
    """
    sa = doc.get("stockfish_analysis") or {}
    rows = (sa.get("move_evaluations") or []) + (
        sa.get("opponent_move_evaluations") or [])
    return any("human_policy_evidence" in r for r in rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--port", default="27019")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from pymongo import MongoClient

    db = MongoClient(prod_mongo_url(args.port),
                     serverSelectionTimeoutMS=20000)["chess_coach"]
    uids = [u.strip() for u in args.users.split(",") if u.strip()]

    cur = db.games.find(
        {"user_id": {"$in": uids}, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "user_id": 1,
         "white_rating": 1, "black_rating": 1, "user_rating": 1}
    ).sort("played_at", -1)
    games = list(cur.limit(args.limit) if args.limit else cur)
    print("games for %s: %d%s" % (",".join(uids), len(games),
                                  "   DRY RUN" if args.dry_run else ""))

    done = skipped = enriched_rows = 0
    reasons: Dict[str, int] = {}
    bytes_added = 0
    t0 = time.time()
    for n, g in enumerate(games, 1):
        gid = g["game_id"]
        doc = db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, USER_PATH: 1, OPP_PATH: 1})
        if not doc:
            skipped += 1
            continue
        if _already_done(doc):
            skipped += 1
            continue
        sa = doc.get("stockfish_analysis") or {}
        user_rows = sa.get("move_evaluations") or []
        opp_rows = sa.get("opponent_move_evaluations") or []
        if not user_rows:
            skipped += 1
            continue

        colour = (g.get("user_color") or "white").lower()
        opp_colour = "black" if colour == "white" else "white"
        before = len(str(user_rows)) + len(str(opp_rows))

        user_rows, s1 = enrich_move_evaluations_with_human_chess(
            user_rows, pgn=g.get("pgn") or "", user_color=colour,
            user_rating=_rating(g, colour),
            opponent_rating=_rating(g, opp_colour))
        s2 = {}
        if opp_rows:
            opp_rows, s2 = enrich_move_evaluations_with_human_chess(
                opp_rows, pgn=g.get("pgn") or "", user_color=opp_colour,
                user_rating=_rating(g, opp_colour),
                opponent_rating=_rating(g, colour))

        got = s1.get("human_policy_evidence", 0) + s2.get(
            "human_policy_evidence", 0)
        enriched_rows += got
        bytes_added += (len(str(user_rows)) + len(str(opp_rows))) - before
        for row in list(user_rows) + list(opp_rows):
            why = row.get("human_policy_reason")
            if why:
                reasons[why] = reasons.get(why, 0) + 1

        if not args.dry_run:
            update = {USER_PATH: user_rows}
            if opp_rows:
                update[OPP_PATH] = opp_rows
            db.game_analyses.update_one({"game_id": gid}, {"$set": update})
        done += 1
        if n % 10 == 0 or n == len(games):
            print("  [%d/%d] %s  +%d evidence rows  (%.0fs, %.1f MB added)"
                  % (n, len(games), gid[:12], enriched_rows,
                     time.time() - t0, bytes_added / 1024 / 1024), flush=True)

    print()
    print("games enriched: %d   skipped: %d" % (done, skipped))
    print("evidence rows written: %d" % enriched_rows)
    print("approx size added: %.1f MB" % (bytes_added / 1024 / 1024))
    print("reasons:")
    for why, count in sorted(reasons.items(), key=lambda kv: -kv[1])[:10]:
        print("   %-34s %d" % (why, count))


if __name__ == "__main__":
    main()

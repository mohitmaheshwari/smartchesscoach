"""Convert played games into teaching scripts. Idempotent, resumable.

Finds analysed games that have no teaching script yet, looks for a position
in each where exactly one move wins, builds the tree for it (the only move,
what this rating actually plays instead, the defender's tries and our answer
to each), and stores it.

Run it again whenever new games land. It only picks up what is not done.

    python3 backend/scripts/build_teaching_scripts.py --limit 25
    python3 backend/scripts/build_teaching_scripts.py --limit 5 --dry-run
    python3 backend/scripts/build_teaching_scripts.py --user user_xxx --maia
    python3 backend/scripts/build_teaching_scripts.py --rebuild   # version bumped

Nothing here writes a sentence. It writes a tree. Rendering that tree into
English is a separate step, so that whatever writes the words can never
choose a move or a verdict.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
import chess.engine
from motor.motor_asyncio import AsyncIOMotorClient

from services.teaching_script_builder import (
    BUILDER_VERSION,
    build_tree,
    candidate_positions_from_pgn,
)

COLLECTION = "teaching_scripts"

ENGINE_CANDIDATES = [
    os.environ.get("TEACHING_STOCKFISH_PATH"),
    os.environ.get("STOCKFISH_AVX2_PATH"),
    "/usr/local/bin/stockfish-avx2",
    "/usr/games/stockfish",
    r"C:\Users\MIISCO\chess-tools\engine\stockfish\stockfish-windows-x86-64-universal.exe",
]


def open_engine(threads: int) -> chess.engine.SimpleEngine:
    for path in ENGINE_CANDIDATES:
        if not path:
            continue
        try:
            eng = chess.engine.SimpleEngine.popen_uci(path)
        except Exception:
            continue
        try:
            eng.configure({"Threads": threads, "Hash": 512})
        except Exception:
            pass
        print(f"  engine: {path} ({threads} threads)")
        return eng
    raise SystemExit("no stockfish found; set TEACHING_STOCKFISH_PATH")


def load_maia(elo_default: int = 1200):
    """Optional. Returns a callable fen,elo -> {uci: prob}, or None."""
    try:
        from services.human_behavior_engine import Maia2Provider, MoveContext
    except Exception as exc:
        print(f"  maia unavailable ({exc}); scripts will have no human column")
        return None
    model_path = os.environ.get("MAIA2_MODEL_PATH", "maia2_models/rapid_model.pt")
    if not os.path.exists(model_path):
        print(f"  maia model not at {model_path}; scripts will have no human column")
        return None
    provider = Maia2Provider(model_type="rapid", device="cpu", model_path=model_path)
    if not provider.available():
        print("  maia package not importable; no human column")
        return None

    def predict(fen: str, elo: int):
        try:
            dist = provider.predict(
                MoveContext(fen=fen, player_elo=int(elo), opponent_elo=int(elo),
                            time_control="600+0"),
                top_k=20,
            )
        except Exception as exc:
            print(f"    maia failed on a position: {exc}")
            return None, {}
        if dist is None:
            return None, {}
        return dict(dist.probabilities), {
            "provider": dist.provider,
            "version": dist.provider_version,
            "elo": int(elo),
        }

    print(f"  maia: {provider.version} ({model_path})")
    return predict


async def already_done(db, rebuild: bool) -> set:
    q = {} if rebuild else {"builder_version": BUILDER_VERSION}
    return {d["game_id"] async for d in db[COLLECTION].find(q, {"_id": 0, "game_id": 1})}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20,
                    help="how many games to convert this run")
    ap.add_argument("--user", default=None, help="restrict to one user_id")
    ap.add_argument("--max-men", type=int, default=7,
                    help="only consider positions with at most this many pieces")
    ap.add_argument("--depth", type=int, default=24)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--maia", action="store_true",
                    help="add what this rating actually plays (slower)")
    ap.add_argument("--rebuild", action="store_true",
                    help="redo games already converted by an older builder")
    ap.add_argument("--dry-run", action="store_true", help="write nothing")
    ap.add_argument("--scan", type=int, default=600,
                    help="how many analysed games to look through")
    args = ap.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    print(f"builder {BUILDER_VERSION}")
    done = await already_done(db, args.rebuild)
    print(f"  already converted: {len(done)}")

    engine = open_engine(args.threads)
    maia = load_maia() if args.maia else None

    # Read from `games`, not `game_analyses`. See the note on
    # candidate_positions_from_pgn: the analysis documents are ~300 KB each
    # and pulling them to find out a game never reached an endgame measured
    # at 2.9s per game, with about one game in thirteen even qualifying.
    q: Dict[str, Any] = {"is_analyzed": True, "pgn": {"$ne": None}}
    if args.user:
        q["user_id"] = args.user

    built, skipped, looked = 0, 0, 0
    started = time.time()

    cursor = db.games.find(
        q, {"_id": 0, "game_id": 1, "user_id": 1, "pgn": 1,
            "user_color": 1, "user_rating": 1}
    ).limit(args.scan)

    async for game in cursor:
        if built >= args.limit:
            break
        game_id = game.get("game_id")
        if not game_id or game_id in done:
            continue
        looked += 1
        if looked % 50 == 0:
            print(f"    ...{looked} games read, {built} built, "
                  f"{time.time() - started:.0f}s", flush=True)
        cands = candidate_positions_from_pgn(
            game.get("pgn") or "",
            user_color=game.get("user_color"),
            max_men=args.max_men,
        )
        if not cands:
            skipped += 1
            continue

        rating = 1200
        if game.get("user_rating"):
            try:
                rating = int(game["user_rating"])
            except (TypeError, ValueError):
                pass

        chosen = None
        for cand in cands[:12]:            # a few tries, then move on
            probs, meta = ({}, {})
            if maia is not None:
                probs, meta = maia(cand["fen"], rating)
            try:
                tree = build_tree(cand["fen"], engine, depth=args.depth,
                                  human_probs=probs or None, maia_meta=meta)
            except chess.engine.EngineTerminatedError:
                print("  engine died; restarting")
                engine = open_engine(args.threads)
                continue
            except Exception as exc:
                print(f"  {game_id} ply {cand['ply']}: {exc}")
                continue
            if tree is not None:
                chosen = (cand, tree)
                break

        if chosen is None:
            skipped += 1
            continue

        cand, tree = chosen
        doc = {
            "game_id": game_id,
            "user_id": game.get("user_id"),
            "ply": cand["ply"],
            "move_number": cand.get("move_number"),
            "their_move": cand["is_opponent_move"],
            "played_instead": cand["played"],
            "player_found_it": cand["played"] == tree.only_move.san,
            "user_rating_at_time": rating,
            "builder_version": BUILDER_VERSION,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "tree": tree.to_doc(),
            "status": "draft",          # a coach reviews before anyone sees it
        }
        built += 1
        tag = "found it" if cand["played"] == tree.only_move.san else "MISSED IT"
        print(f"  [{built:3}] {game_id[-12:]} ply {cand['ply']:>3} "
              f"{tree.men} men  {tree.proof:10} only move "
              f"{tree.only_move.san:7} ({tag})")
        if not args.dry_run:
            await db[COLLECTION].update_one(
                {"game_id": game_id, "ply": cand["ply"]},
                {"$set": doc},
                upsert=True,
            )

    engine.quit()
    secs = time.time() - started
    print(f"\n  looked at {looked} unconverted games in {secs:.0f}s")
    print(f"  built {built}   no teachable position {skipped}")
    if args.dry_run:
        print("  DRY RUN -- nothing was written")
    else:
        total = await db[COLLECTION].count_documents({})
        print(f"  {COLLECTION} now holds {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

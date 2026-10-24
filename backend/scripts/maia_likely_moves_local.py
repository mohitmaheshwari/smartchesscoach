"""Find the move a player at THIS rating would probably play, and whether it loses.

Mohit, after seeing Stockfish answer Nxh3+ with Kh2: "a 1200 would take up
the knight and that creates the understanding... user might just ask with
arrows why king moved and knight not taken by pawn". The engine's defence is
often an admission that the tactic works; the human line is where the lesson
lands.

Runs on Mohit's MACHINE, not the server -- "until that is done, I would run
it from my machine itself", the server being 0.8 GB short of comfortable
until mongodb is capped and matrimonial moves off. It reaches prod through
the SSH tunnel the local container already uses (host.docker.internal:27018),
and the credential is read from that container, never written down here.

Measured over 92 games (5,871 plies) before any of this was built:

  Maia2 names the move actually played          52.2%   (both rating bands)
  its top move differs from Stockfish's best     55.7%
  ...and is engine-confirmed bad, played fine     134    = 1.5 a game
      what it costs      median 203 cp, p90 663 cp
      how likely they are median 38%, p90 66%

The examples are why this is worth running: a move 90% of 1191-rated players
make, losing 122 cp, in a position where the player found the right move
instead. No authored distractor is that well calibrated.

NOT called a trap. `trap_tracking` already exists and means a trapped PIECE
-- one with no escape squares. Two meanings of one word in one database is
how the caption layer ended up with two writers.

Writes to its own collection. These positions reach no screen yet: wiring
them into the question surface is a separate, deliberate step, and a
collection nothing reads is this repo's most familiar failure.

Usage:
    python scripts/maia_likely_moves_local.py --users <uid>[,<uid>] --limit 50
    python scripts/maia_likely_moves_local.py --users <uid> --limit 5 --dry-run
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import time
from typing import Dict, List, Optional

import chess
import chess.engine
import chess.pgn

COLLECTION = "maia_likely_moves"

# Above this an eval is the mate sentinel, not a centipawn score; the repo
# uses the same bound in scripts/derive_opponent_moves.py.
CLAMP = 900

# The played move has to have been FINE, or this is just a blunder the
# review page already covers.
PLAYED_WAS_FINE = 50

# And the likely move has to be a real mistake, not a shrug. 100 is the
# repo's own mistake bar (stockfish_service.CP_THRESHOLDS).
LIKELY_IS_BAD = 100

STOCKFISH = os.environ.get(
    "LOCAL_STOCKFISH",
    r"C:\Users\MIISCO\chess-tools\engine\stockfish"
    r"\stockfish-windows-x86-64-universal.exe")


def prod_mongo_url() -> str:
    """The prod URL, read from the running local container.

    That container already tunnels to prod on 27018, so the host only has to
    point at 127.0.0.1 instead of docker's internal name. Reading it keeps
    the credential out of this file and out of git.
    """
    url = subprocess.check_output(
        ["docker", "exec", "chess-coach-backend", "printenv", "MONGO_URL"],
        text=True).strip()
    return url.replace("host.docker.internal", "127.0.0.1")


def key4(fen: Optional[str]) -> str:
    return " ".join((fen or "").split()[:4])


def pov_cp(engine, board: chess.Board, pov, depth: int) -> Optional[int]:
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    score = info["score"].pov(pov)
    return None if score.is_mate() else score.score()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", required=True)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--depth", type=int, default=16)
    ap.add_argument("--elo", type=int, default=0,
                    help="override the rating; default reads the PGN headers")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from pymongo import MongoClient
    from maia2 import model, inference

    db = MongoClient(prod_mongo_url(), serverSelectionTimeoutMS=15000)[
        "chess_coach"]
    coll = db[COLLECTION]
    if not args.dry_run:
        # Re-running must not duplicate a position. One record per ply.
        coll.create_index([("game_id", 1), ("ply", 1)], unique=True)
        coll.create_index([("source_user_id", 1), ("created_at", -1)])

    uids = [u.strip() for u in args.users.split(",") if u.strip()]
    done = set(coll.distinct("game_id", {"source_user_id": {"$in": uids}}))
    games = [g for g in db.games.find(
        {"user_id": {"$in": uids}, "is_analyzed": True},
        {"game_id": 1, "pgn": 1, "user_color": 1, "user_id": 1,
         "white_rating": 1, "black_rating": 1, "_id": 0}
    ).sort("played_at", -1).limit(args.limit * 4)
        if g["game_id"] not in done][:args.limit]

    print("games to process: %d  (already done: %d)%s" % (
        len(games), len(done), "   DRY RUN" if args.dry_run else ""))
    if not games:
        return

    m = model.from_pretrained(type="rapid", device="cpu")
    prepared = inference.prepare()
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    engine.configure({"Threads": 2, "Hash": 256})

    found = considered = skipped_no_elo = 0
    t0 = time.time()
    try:
        for n, g in enumerate(games, 1):
            gid = g["game_id"]
            try:
                game = chess.pgn.read_game(io.StringIO(g.get("pgn") or ""))
            except Exception:
                continue
            if game is None:
                continue
            # The RATING comes off the game document first.
            #
            # A first version read WhiteElo/BlackElo from the PGN and
            # skipped 108 of 200 games -- including every one of the three
            # most recent, so the dry run found nothing at all and looked
            # like a broken detector. The import does not preserve those
            # headers, but it does store `white_rating` / `black_rating` on
            # the game itself. The PGN is the fallback, not the source.
            headers = game.headers

            def _num(*values):
                for value in values:
                    try:
                        n = int(value)
                    except (TypeError, ValueError):
                        continue
                    if n > 0:
                        return n
                return 0

            welo = args.elo or _num(g.get("white_rating"),
                                    headers.get("WhiteElo"))
            belo = args.elo or _num(g.get("black_rating"),
                                    headers.get("BlackElo"))
            # One side known is enough: Maia2 wants both, and an opponent of
            # roughly equal strength is a better guess than giving up the
            # game. Stated here because it IS a guess.
            welo = welo or belo
            belo = belo or welo
            if not welo or not belo:
                skipped_no_elo += 1
                continue

            doc = db.game_analyses.find_one(
                {"game_id": gid},
                {"stockfish_analysis.move_evaluations.fen_before": 1,
                 "stockfish_analysis.move_evaluations.best_move": 1,
                 "stockfish_analysis.move_evaluations.cp_loss": 1,
                 "stockfish_analysis.opponent_move_evaluations.fen_before": 1,
                 "stockfish_analysis.opponent_move_evaluations.best_move": 1,
                 "stockfish_analysis.opponent_move_evaluations.cp_loss": 1,
                 "_id": 0})
            if not doc:
                continue
            sa = doc.get("stockfish_analysis") or {}
            stored: Dict[str, dict] = {}
            for rec in (sa.get("move_evaluations") or []):
                stored[key4(rec.get("fen_before"))] = rec
            for rec in (sa.get("opponent_move_evaluations") or []):
                stored.setdefault(key4(rec.get("fen_before")), rec)

            user_is_white = (g.get("user_color") or "white") == "white"
            board = game.board()
            rows: List[dict] = []
            for ply, mv in enumerate(game.mainline_moves()):
                fen = board.fen()
                rec = stored.get(key4(fen)) or {}
                best = rec.get("best_move")
                cp_loss = rec.get("cp_loss")
                played = board.san(mv)
                white_to_move = board.turn == chess.WHITE

                if (best and cp_loss is not None
                        and int(cp_loss) < PLAYED_WAS_FINE):
                    considered += 1
                    elo_self = welo if white_to_move else belo
                    elo_oppo = belo if white_to_move else welo
                    try:
                        out = inference.inference_each(
                            m, prepared, fen, elo_self, elo_oppo)
                        probs = out[0] if isinstance(out, tuple) else out
                        top = max(probs.items(), key=lambda kv: kv[1])
                        likely = chess.Move.from_uci(top[0])
                        likely_san = board.san(likely)
                    except Exception:
                        likely_san = None
                    if likely_san and likely_san not in (best, played):
                        try:
                            pov = board.turn
                            before = pov_cp(engine, board, pov, args.depth)
                            after_board = board.copy()
                            after_board.push(likely)
                            after = pov_cp(engine, after_board, pov,
                                           args.depth)
                        except Exception:
                            before = after = None
                        if (before is not None and after is not None
                                and abs(before) <= CLAMP
                                and abs(after) <= CLAMP):
                            loss = before - after
                            if loss >= LIKELY_IS_BAD:
                                rows.append({
                                    "game_id": gid,
                                    "ply": ply,
                                    "fen": fen,
                                    "source_user_id": g.get("user_id"),
                                    "user_color": g.get("user_color"),
                                    "mover_is_user": (
                                        white_to_move == user_is_white),
                                    "played_san": played,
                                    "played_cp_loss": int(cp_loss),
                                    "best_move_san": best,
                                    "likely_move_san": likely_san,
                                    "likely_move_uci": top[0],
                                    "likely_move_pct": round(top[1] * 100, 1),
                                    "likely_move_cp_loss": int(loss),
                                    "elo_self": elo_self,
                                    "elo_oppo": elo_oppo,
                                    "engine_depth": args.depth,
                                    "source": "maia_likely_move",
                                    "created_at": time.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                })
                board.push(mv)

            found += len(rows)
            if rows and not args.dry_run:
                from pymongo import UpdateOne
                coll.bulk_write([
                    UpdateOne({"game_id": r["game_id"], "ply": r["ply"]},
                              {"$set": r}, upsert=True) for r in rows],
                    ordered=False)
            print("  [%d/%d] %s  %d found  (%.0fs total)" % (
                n, len(games), gid[:12], len(rows), time.time() - t0),
                flush=True)
    finally:
        engine.quit()

    print()
    print("positions considered (played move was fine): %d" % considered)
    print("likely-and-losing positions found:           %d" % found)
    print("games skipped for no rating in the pgn:      %d" % skipped_no_elo)
    print("per game: %.1f" % (found / max(len(games) - skipped_no_elo, 1)))
    if not args.dry_run:
        print("collection %s now holds %d" % (
            COLLECTION, coll.estimated_document_count()))


if __name__ == "__main__":
    main()

"""Give the opponent's mistakes the engine truth they were back-filled without.

Mohit 2026-10-28, on a card reading "Your opponent played c6. That was a
mistake. Play d4 -- it attacks the pawn on e5.": "it tells my move both
captions and arrow, but doens't tell why their move is bad" -- and then the
right question, "our engine could still tell it right?? why engine is not
telling it, it runs stockfish on fly".

It does, now. stockfish_service analyses opponent moves and stores
best_move plus both lines for the ones that are errors. What it did not do
was store them for games analysed before that gate was removed, and the
repair that followed (derive_opponent_moves.py) rebuilt those rows from the
user's eval deltas with ZERO engine calls -- deliberately, because the full
engine pass was 34 hours and was refused. Those rows carry exact evals and
no best_move and no line at all, so the card can grade the move and then has
nothing left to say about it.

Measured before writing this:

    opponent faults >= 100cp, engine-backed   176 of 201 of his games
       ...card names what they should play    176   (100%)
       ...caption says why their move was bad 146   (83%)
    opponent faults >= 100cp, derived         551
       ...either of those                       0   (0%)

So the captions already work; the data was missing. 2,167 derived fault
rows exist across 514 games, and depth 16 measured 0.38s / 0.66s / 1.21s on
three of these positions -- about 27 minutes for all of them on one worker.

This fills ONLY faults. The other 23,578 derived rows are quiet moves whose
lines nobody reads, and computing them is the 34-hour job that was already
turned down.

What it writes, and what it deliberately does not: the engine fields
(best_move, best_move_uci, move_uci, pv_after_best, pv_after_played,
eval_line_played) plus a stamp naming them. `derived` STAYS, because
cp_loss, eval_before and eval_after are still the derived values and a
later measurement must not mistake them for engine truth.

Running it unsets decryption_v5_version on each game it touches, so the
card re-renders on the next view -- the version is already current, so
nothing would refresh otherwise.

    python3 scripts/backfill_opponent_fault_lines.py                # count only
    python3 scripts/backfill_opponent_fault_lines.py --apply
    python3 scripts/backfill_opponent_fault_lines.py --apply --user user_xxx
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import chess.engine
from pymongo import MongoClient

STAMP = "opponent_fault_lines.v1"
DEPTH_BEST = 16          # what the measurement above was timed at
DEPTH_LINE = 12          # what stockfish_service uses for opponent lines
PV_PLIES = 12
ENGINE_PATHS = ("/usr/games/stockfish", "/usr/local/bin/stockfish",
                "/usr/bin/stockfish")


def engine_path():
    for path in ENGINE_PATHS:
        if os.path.exists(path):
            return path
    raise SystemExit("stockfish not found in %s" % (ENGINE_PATHS,))


def san_line(engine, board, plies):
    """The engine's line from here, as SAN, the way the stored rows hold it."""
    try:
        info = engine.analyse(board, chess.engine.Limit(depth=DEPTH_LINE))
    except Exception:
        return []
    out = []
    walk = board.copy()
    for move in (info.get("pv") or [])[:plies]:
        if move not in walk.legal_moves:
            break
        out.append(walk.san(move))
        walk.push(move)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write; without it nothing is changed")
    ap.add_argument("--user", help="limit to one user's games")
    ap.add_argument("--min-cp", type=int, default=100)
    ap.add_argument("--limit", type=int, default=0, help="stop after N rows")
    args = ap.parse_args()

    db = MongoClient(os.environ["MONGO_URL"],
                     serverSelectionTimeoutMS=30000)[
                         os.environ.get("DB_NAME", "chess_coach")]

    if args.user:
        gids = [g["game_id"] for g in db.games.find(
            {"user_id": args.user, "is_analyzed": True},
            {"game_id": 1, "_id": 0})]
        query = {"game_id": {"$in": gids}}
    else:
        query = {"stockfish_analysis.opponent_move_evaluations.0":
                 {"$exists": True}}

    todo = []
    for a in db.game_analyses.find(query, {
            "_id": 0, "game_id": 1,
            "stockfish_analysis.opponent_move_evaluations": 1}):
        rows = (a.get("stockfish_analysis") or {}).get(
            "opponent_move_evaluations") or []
        for i, r in enumerate(rows):
            if not r.get("derived"):
                continue
            if (r.get("cp_loss") or 0) < args.min_cp:
                continue
            if r.get("engine_backfilled") == STAMP or r.get("best_move"):
                continue          # idempotent: already done
            if not r.get("fen_before") or not r.get("move"):
                continue
            todo.append((a["game_id"], i, r["fen_before"], r["move"]))
            if args.limit and len(todo) >= args.limit:
                break
        if args.limit and len(todo) >= args.limit:
            break

    games = len({t[0] for t in todo})
    print("rows to fill : %d  across %d games" % (len(todo), games))
    if not args.apply:
        print("dry run; pass --apply to write")
        return
    if not todo:
        return

    engine = chess.engine.SimpleEngine.popen_uci(engine_path())
    filled = skipped = 0
    touched = set()
    started = time.time()
    try:
        for n, (gid, idx, fen, played_san) in enumerate(todo, 1):
            try:
                board = chess.Board(fen)
                played = board.parse_san(str(played_san))
            except Exception:
                skipped += 1
                continue
            try:
                info = engine.analyse(board,
                                      chess.engine.Limit(depth=DEPTH_BEST))
                pv = info.get("pv") or []
                if not pv or pv[0] not in board.legal_moves:
                    skipped += 1
                    continue
                best = pv[0]
                best_san = board.san(best)

                after_best = board.copy()
                after_best.push(best)
                after_played = board.copy()
                after_played.push(played)
                line_best = san_line(engine, after_best, PV_PLIES)
                line_played = san_line(engine, after_played, PV_PLIES)
            except Exception as err:
                print("  engine failed on %s[%d]: %s" % (gid[:8], idx, err))
                skipped += 1
                continue

            base = "stockfish_analysis.opponent_move_evaluations.%d." % idx
            db.game_analyses.update_one({"game_id": gid}, {"$set": {
                base + "best_move": best_san,
                base + "best_move_uci": best.uci(),
                base + "move_uci": played.uci(),
                base + "pv_after_best": line_best,
                base + "pv_after_played": line_played,
                base + "eval_line_played": line_played,
                # Names exactly which fields are engine truth. cp_loss,
                # eval_before and eval_after keep their `derived` stamp
                # because they still are derived.
                base + "engine_backfilled": STAMP,
            }})
            filled += 1
            touched.add(gid)
            if n % 100 == 0:
                rate = (time.time() - started) / n
                print("  %d/%d  %.2fs/row  ~%.0f min left"
                      % (n, len(todo), rate, (len(todo) - n) * rate / 60))
    finally:
        engine.quit()

    # The cards only re-render when the stored version is behind the code's,
    # and it is already current -- so nothing would refresh without this.
    refreshed = 0
    for gid in touched:
        db.game_analyses.update_one(
            {"game_id": gid}, {"$unset": {"decryption_v5_version": ""}})
        refreshed += 1

    print("\nfilled   : %d" % filled)
    print("skipped  : %d" % skipped)
    print("games    : %d, version unset so they re-render on view" % refreshed)
    print("elapsed  : %.1f min" % ((time.time() - started) / 60))


if __name__ == "__main__":
    main()

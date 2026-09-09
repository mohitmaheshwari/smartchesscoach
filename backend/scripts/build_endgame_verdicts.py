#!/usr/bin/env python3
"""Record a verdict for EVERY stored endgame mistake, not just the real ones.

The earlier pass counted the rejected buckets and kept only the survivors,
which is fine for measuring the corpus and useless for filtering it: to stop
showing a false accusation you need a row saying that specific move on that
specific board is not one.

So this writes one document per candidate into `endgame_move_verdicts`, keyed
by game and move number, carrying the fresh evaluation either side of the move
and one of four verdicts:

    positional       real, and nothing could be captured afterwards
    tactical         real, and something hung
    not_a_mistake    gives up less than the bar on fresh analysis
    already_decided  a real slip in a position already won or lost

It also records `understates`, because the gate is not only about deletion:
one sampled move stored as -133cp actually loses 8514, and a filter that only
removed things would throw that away.

Serving code reads these rows. Nothing re-analyses at request time.

Run it in cg-analysis, never in the 2GB serving container:
    docker exec -d -e PYTHONPATH=/app/backend cg-analysis \\
        sh -c 'python /tmp/verdicts.py > /tmp/verdicts.out 2>&1'
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
import chess.engine
from pymongo import MongoClient, UpdateOne

DEPTH = int(os.environ.get("VERIFY_DEPTH", "20"))
ENDGAME_MEN = int(os.environ.get("ENDGAME_MEN", "12"))
MISTAKE_CP = int(os.environ.get("MISTAKE_CP", "100"))
DECIDED_CP = int(os.environ.get("DECIDED_CP", "600"))
# A stored figure this far below the truth is worth flagging in its own right.
UNDERSTATED_CP = int(os.environ.get("UNDERSTATED_CP", "300"))
MATERIAL_CP = 100
BATCH = 200


def played_move(board, ev):
    for key in ("move_uci", "played_move_uci", "user_move_uci"):
        if ev.get(key):
            try:
                mv = chess.Move.from_uci(str(ev[key]))
                if mv in board.legal_moves:
                    return mv
            except ValueError:
                pass
    for key in ("move", "move_san", "played_move", "user_move_san"):
        if ev.get(key):
            try:
                return board.parse_san(str(ev[key]))
            except ValueError:
                pass
    return None


def wins_material(board):
    from coach_play.coach_blunder_guard import see_gain
    return any(
        board.is_capture(mv) and see_gain(board, mv) >= MATERIAL_CP
        for mv in board.legal_moves
    )


def main() -> int:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]

    candidates = []
    for doc in db.game_analyses.find(
        {}, {"_id": 0, "game_id": 1, "user_id": 1, "stockfish_analysis.move_evaluations": 1}
    ):
        for ev in (doc.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            if ev.get("is_opponent_move"):
                continue
            stored, fen = ev.get("cp_loss"), ev.get("fen_before")
            if not isinstance(stored, (int, float)) or stored < MISTAKE_CP or not fen:
                continue
            try:
                board = chess.Board(fen)
            except Exception:
                continue
            if len(board.piece_map()) > ENDGAME_MEN:
                continue
            mv = played_move(board, ev)
            if mv is None:
                continue
            candidates.append({
                "game_id": doc.get("game_id"), "user_id": doc.get("user_id"),
                "move_number": ev.get("move_number"), "fen": fen, "uci": mv.uci(),
                "stored_cp_loss": int(stored), "men": len(board.piece_map()),
            })

    print(f"  candidates: {len(candidates)}", flush=True)

    tally = Counter()
    pending = []
    with chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish") as eng:
        for i, row in enumerate(candidates, 1):
            board = chess.Board(row["fen"])
            mover = board.turn
            mv = chess.Move.from_uci(row["uci"])
            before_info = eng.analyse(board, chess.engine.Limit(depth=DEPTH))
            before = before_info["score"].pov(mover).score(mate_score=10000)
            after_board = board.copy()
            after_board.push(mv)
            after = eng.analyse(after_board, chess.engine.Limit(depth=DEPTH))[
                "score"].pov(mover).score(mate_score=10000)
            real = before - after

            if real < MISTAKE_CP:
                verdict = "not_a_mistake"
            elif before <= -DECIDED_CP or after >= DECIDED_CP:
                verdict = "already_decided"
            elif wins_material(after_board):
                verdict = "tactical"
            else:
                verdict = "positional"
            tally[verdict] += 1

            doc = {
                **row,
                "verdict": verdict,
                "show_to_user": verdict in ("positional", "tactical"),
                "fresh_cp_loss": int(real),
                "eval_before": int(before),
                "eval_after": int(after),
                "best_move_san": board.san(before_info["pv"][0]) if before_info.get("pv") else None,
                "understates": bool(real - row["stored_cp_loss"] >= UNDERSTATED_CP),
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "verify_depth": DEPTH,
            }
            pending.append(UpdateOne(
                {"game_id": row["game_id"], "move_number": row["move_number"]},
                {"$set": doc}, upsert=True,
            ))
            if len(pending) >= BATCH:
                db.endgame_move_verdicts.bulk_write(pending, ordered=False)
                pending = []
            if i % 250 == 0:
                print(f"     {i}/{len(candidates)}  {dict(tally)}", flush=True)

    if pending:
        db.endgame_move_verdicts.bulk_write(pending, ordered=False)
    db.endgame_move_verdicts.create_index([("game_id", 1), ("move_number", 1)], unique=True)
    db.endgame_move_verdicts.create_index("show_to_user")
    db.endgame_move_verdicts.create_index("user_id")

    total = sum(tally.values()) or 1
    print()
    for k in ("positional", "tactical", "not_a_mistake", "already_decided"):
        print(f"     {k:18} {tally[k]:6}  {100*tally[k]//total:3}%")
    shown = tally["positional"] + tally["tactical"]
    print()
    print(f"  will keep showing : {shown}")
    print(f"  will stop showing : {total - shown}")
    understated = db.endgame_move_verdicts.count_documents({"understates": True})
    print(f"  understated (we said too little): {understated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

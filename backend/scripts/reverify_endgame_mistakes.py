#!/usr/bin/env python3
"""Re-verify the endgame mistake corpus before anything is built on it.

Two independent reviewers looking at a 72-position sample reported that
roughly 29 of them are not mistakes at all once the engine re-examines the
position. The original filter trusted `cp_loss` as stored by the analysis
worker, and a stored number from an older run at an unknown depth is not
evidence. Coverage measured against an inflated denominator is worthless,
so this rebuilds the set from scratch.

For every candidate it evaluates the position and the position after the
move that was played, at a fixed depth, now, and sorts the result:

  not_a_mistake      the move gives up less than the threshold. The stored
                     cp_loss was wrong or came from a shallower search.
  already_decided    both evaluations are past the point where the game is
                     settled. The move may be inaccurate and it changes
                     nothing, so there is no lesson in it.
  tactical           a real mistake, and afterwards something can be taken.
  positional         a real mistake, and nothing can be taken. This is the
                     set worth teaching to, and the only number that should
                     ever be quoted as the size of the problem.

Run it in a container of its own. It opens an engine and holds it for
hours; sharing the 2GB serving container gets the engine OOM-killed and
takes the API's spare memory with it.

Usage:
    docker exec -d -e PYTHONPATH=/app/backend cg-analysis \\
        sh -c 'python /tmp/reverify.py > /tmp/reverify.out 2>&1'
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
import chess.engine
from pymongo import MongoClient

DEPTH = int(os.environ.get("VERIFY_DEPTH", "20"))
ENDGAME_MEN = int(os.environ.get("ENDGAME_MEN", "12"))
MISTAKE_CP = int(os.environ.get("MISTAKE_CP", "100"))
# Past this the game is already decided; giving up more of it teaches nothing.
DECIDED_CP = int(os.environ.get("DECIDED_CP", "600"))
MATERIAL_CP = 100
OUT = os.environ.get("OUT", "/tmp/reverified_mistakes.json")


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
        {}, {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1}
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
                "game_id": doc.get("game_id"), "fen": fen, "uci": mv.uci(),
                "stored_cp_loss": int(stored),
                "move_number": ev.get("move_number"),
                "men": len(board.piece_map()),
            })

    print(f"  candidates carrying a stored cp_loss >= {MISTAKE_CP}: {len(candidates)}", flush=True)

    verdicts = Counter()
    kept = []
    with chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish") as eng:
        for i, row in enumerate(candidates, 1):
            board = chess.Board(row["fen"])
            mover = board.turn
            mv = chess.Move.from_uci(row["uci"])
            best = eng.analyse(board, chess.engine.Limit(depth=DEPTH))
            before = best["score"].pov(mover).score(mate_score=10000)
            after_board = board.copy()
            after_board.push(mv)
            after = eng.analyse(after_board, chess.engine.Limit(depth=DEPTH))
            got = after["score"].pov(mover).score(mate_score=10000)
            real_loss = before - got
            row["fresh_cp_loss"] = int(real_loss)
            row["eval_before"] = int(before)
            row["eval_after"] = int(got)
            row["best_move"] = board.san(best["pv"][0]) if best.get("pv") else None

            if real_loss < MISTAKE_CP:
                verdicts["not_a_mistake"] += 1
            elif before <= -DECIDED_CP or got >= DECIDED_CP:
                # already lost before the move, or still winning after it
                verdicts["already_decided"] += 1
            elif wins_material(after_board):
                verdicts["tactical"] += 1
                row["kind"] = "tactical"
                kept.append(row)
            else:
                verdicts["positional"] += 1
                row["kind"] = "positional"
                kept.append(row)

            if i % 250 == 0:
                print(f"     {i}/{len(candidates)}  "
                      f"positional={verdicts['positional']} "
                      f"tactical={verdicts['tactical']} "
                      f"not_a_mistake={verdicts['not_a_mistake']} "
                      f"already_decided={verdicts['already_decided']}", flush=True)

    total = sum(verdicts.values()) or 1
    print()
    print(f"  re-verified at depth {DEPTH}: {total}")
    for k in ("positional", "tactical", "not_a_mistake", "already_decided"):
        v = verdicts[k]
        print(f"     {k:18} {v:6}  {100*v//total:3}%")
    print()
    print(f"  TEACHABLE positional endgame mistakes: {verdicts['positional']}")
    print("  (this number replaces the earlier 7,141, which trusted stored cp_loss)")
    json.dump({"verdicts": dict(verdicts), "kept": kept},
              open(OUT, "w", encoding="utf-8"))
    print(f"  written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

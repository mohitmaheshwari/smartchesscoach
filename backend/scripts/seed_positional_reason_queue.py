#!/usr/bin/env python3
"""Build the queue of positions to ask a human coach about.

The machine can check a positional idea and count how often it discriminates.
It cannot reliably invent the idea: of five predicates written in one pass,
one fired zero times in 46,655 positions. So the concepts have to come from
someone who can look at a board and say why the good move is good.

Which positions to ask about matters. Showing ones the existing predicates
already explain wastes the coach's time and teaches us nothing, so the queue
is ordered to put UNEXPLAINED positions first -- those are the ones where a
human reason adds a concept we do not yet have.

Positions are stratified by material so the queue does not fill with twenty
rook endings in a row.

Usage:
    python backend/scripts/seed_positional_reason_queue.py
    LIMIT=400 python backend/scripts/seed_positional_reason_queue.py
"""
from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
import chess.engine
from pymongo import MongoClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "coach_play"))

LIMIT = int(os.environ.get("LIMIT", "400"))
MIN_CP = int(os.environ.get("MIN_CP", "150"))
MAX_MEN = int(os.environ.get("MAX_MEN", "24"))
# Mate scores arrive as five-figure cp_loss. A missed mate is a tactic and
# asking a coach why mate is good wastes the only scarce resource here.
MATE_CP = 5000
# Stored cp_loss is unreliable: re-verified, 29% of these are not mistakes and
# 28% are moves in games already won or lost. Both were reaching the top of the
# queue, because sorting by stored cp_loss sorts by exactly the wrong number.
DECIDED_CP = 600
VERIFY_DEPTH = int(os.environ.get("VERIFY_DEPTH", "18"))
PER_BUCKET = int(os.environ.get("PER_BUCKET", "60"))


def passed_pawns(board, colour):
    out = []
    for sq in board.pieces(chess.PAWN, colour):
        f, r = chess.square_file(sq), chess.square_rank(sq)
        if any(
            abs(chess.square_file(o) - f) <= 1
            and ((colour == chess.WHITE and chess.square_rank(o) > r)
                 or (colour == chess.BLACK and chess.square_rank(o) < r))
            for o in board.pieces(chess.PAWN, not colour)
        ):
            continue
        out.append(sq)
    return out


def _stop_square(sq, colour):
    r = chess.square_rank(sq) + (1 if colour == chess.WHITE else -1)
    return chess.square(chess.square_file(sq), r) if 0 <= r <= 7 else None


def p_blockade(board, us):
    for sq in passed_pawns(board, not us):
        st = _stop_square(sq, not us)
        if st is None:
            continue
        pc = board.piece_at(st)
        if (pc and pc.color == us) or board.is_attacked_by(us, st):
            return True
    return False


def p_rook_behind(board, us):
    for sq in passed_pawns(board, us):
        f = chess.square_file(sq)
        for rk in board.pieces(chess.ROOK, us):
            if chess.square_file(rk) == f and (
                (us == chess.WHITE and chess.square_rank(rk) < chess.square_rank(sq))
                or (us == chess.BLACK and chess.square_rank(rk) > chess.square_rank(sq))
            ):
                return True
    return False


def p_outpost(board, us):
    for n in board.pieces(chess.KNIGHT, us):
        f, r = chess.square_file(n), chess.square_rank(n)
        if not 2 <= r <= 5:
            continue
        if any(
            abs(chess.square_file(o) - f) == 1 and chess.square_rank(o) > r
            for o in board.pieces(chess.PAWN, not us)
        ):
            continue
        if board.is_attacked_by(us, n):
            return True
    return False


def p_shelter(board, us):
    k = board.king(us)
    if k is None:
        return False
    f, r = chess.square_file(k), chess.square_rank(k)
    cover = 0
    for df in (-1, 0, 1):
        nf = f + df
        if not 0 <= nf <= 7:
            continue
        for dr in (1, 2):
            nr = r + dr if us == chess.WHITE else r - dr
            if 0 <= nr <= 7:
                pc = board.piece_at(chess.square(nf, nr))
                if pc and pc.piece_type == chess.PAWN and pc.color == us:
                    cover += 1
                    break
    return cover >= 2


PREDICATES = [
    ("blockade", p_blockade),
    ("rook_behind_passer", p_rook_behind),
    ("knight_outpost", p_outpost),
    ("king_pawn_cover", p_shelter),
]


def _move(board, ev, keys_uci, keys_san):
    for k in keys_uci:
        if ev.get(k):
            try:
                mv = chess.Move.from_uci(str(ev[k]))
                if mv in board.legal_moves:
                    return mv
            except ValueError:
                pass
    for k in keys_san:
        if ev.get(k):
            try:
                return board.parse_san(str(ev[k]))
            except ValueError:
                pass
    return None


def material_bucket(board):
    men = len(board.piece_map())
    heavy = bool(board.pieces(chess.QUEEN, chess.WHITE) or board.pieces(chess.QUEEN, chess.BLACK))
    if men <= 8:
        return "bare endgame"
    if men <= 14:
        return "endgame"
    return "middlegame with queens" if heavy else "middlegame"


def main() -> int:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
    already = {d["fen"] for d in db.positional_reason_queue.find({}, {"_id": 0, "fen": 1})}

    buckets = defaultdict(list)
    for doc in db.game_analyses.find(
        {}, {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1}
    ):
        for ev in (doc.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            if ev.get("is_opponent_move"):
                continue
            cp, fen = ev.get("cp_loss"), ev.get("fen_before")
            if not isinstance(cp, (int, float)) or cp < MIN_CP or not fen or fen in already:
                continue
            try:
                board = chess.Board(fen)
            except Exception:
                continue
            if len(board.piece_map()) > MAX_MEN:
                continue
            if cp >= MATE_CP:
                continue                      # missed or allowed mate: a tactic
            played = _move(board, ev, ("move_uci", "played_move_uci", "user_move_uci"),
                           ("move", "move_san", "played_move", "user_move_san"))
            best = _move(board, ev, ("best_move_uci",), ("best_move_san", "best_move"))
            if played is None or best is None or played == best:
                continue
            best_san = board.san(best)
            if "#" in best_san:
                continue                      # the answer is mate, not an idea
            after_played_probe = board.copy()
            after_played_probe.push(played)
            # If something simply hangs, the lesson is "you dropped a piece".
            # That is already detected and is not what a coach is needed for.
            from coach_blunder_guard import see_gain
            if any(
                after_played_probe.is_capture(m)
                and see_gain(after_played_probe, m) >= 200
                for m in after_played_probe.legal_moves
            ):
                continue

            us = board.turn
            after_played = board.copy(); after_played.push(played)
            after_best = board.copy(); after_best.push(best)
            explained = [
                name for name, fn in PREDICATES
                if fn(after_best, us) and not fn(after_played, us)
            ]
            bucket = material_bucket(board)
            if len(buckets[bucket]) >= PER_BUCKET * 3:
                continue
            buckets[bucket].append({
                "fen": fen,
                "game_id": doc.get("game_id"),
                "move_number": ev.get("move_number"),
                "side_to_move": "white" if us == chess.WHITE else "black",
                "played_san": board.san(played),
                "best_san": best_san,
                "played_uci": played.uci(),
                "best_uci": best.uci(),
                "cp_loss": int(cp),
                "men": len(board.piece_map()),
                "bucket": bucket,
                # Positions no current predicate explains are the ones worth
                # a coach's time -- they are where a new concept can come from.
                "already_explained_by": explained,
                "priority": 0 if not explained else 1,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    # Verify every candidate before it can reach a coach. A position that was
    # already decided has no honest answer to "why is the good move good" --
    # the honest answer is "nothing was decided here" -- and a move that is not
    # a mistake has no question at all.
    print("  verifying candidates before queueing ...", flush=True)
    kept_buckets = defaultdict(list)
    dropped = Counter()
    with chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish") as eng:
        for bucket, items in buckets.items():
            for row in items:
                if len(kept_buckets[bucket]) >= PER_BUCKET:
                    break
                board = chess.Board(row["fen"])
                mover = board.turn
                try:
                    mv = chess.Move.from_uci(row["played_uci"])
                except ValueError:
                    continue
                before = eng.analyse(board, chess.engine.Limit(depth=VERIFY_DEPTH))[
                    "score"].pov(mover).score(mate_score=10000)
                after_board = board.copy()
                after_board.push(mv)
                after = eng.analyse(after_board, chess.engine.Limit(depth=VERIFY_DEPTH))[
                    "score"].pov(mover).score(mate_score=10000)
                real = before - after
                if real < MIN_CP:
                    dropped["not a mistake on fresh analysis"] += 1
                    continue
                if before <= -DECIDED_CP or after >= DECIDED_CP:
                    dropped["game already decided either way"] += 1
                    continue
                row["fresh_cp_loss"] = int(real)
                row["eval_before"] = int(before)
                row["eval_after"] = int(after)
                kept_buckets[bucket].append(row)
    for reason, n in dropped.most_common():
        print(f"     dropped {n}: {reason}")
    buckets = kept_buckets

    rows = []
    for bucket, items in buckets.items():
        items.sort(key=lambda r: (r["priority"], -r.get("fresh_cp_loss", 0)))
        rows.extend(items[:PER_BUCKET])
    rows.sort(key=lambda r: (r["priority"], -r.get("fresh_cp_loss", 0)))
    rows = rows[:LIMIT]

    if rows:
        db.positional_reason_queue.insert_many(rows)
        db.positional_reason_queue.create_index("status")
        db.positional_reason_queue.create_index([("priority", 1), ("cp_loss", -1)])

    print(f"  queued: {len(rows)}")
    per = defaultdict(int)
    for r in rows:
        per[r["bucket"]] += 1
    for k, v in sorted(per.items()):
        print(f"     {k:24} {v}")
    unexplained = sum(1 for r in rows if not r["already_explained_by"])
    print(f"  of these, no existing predicate explains: {unexplained} "
          f"({100*unexplained//max(len(rows),1)}%) — shown first")
    return 0


if __name__ == "__main__":
    sys.exit(main())

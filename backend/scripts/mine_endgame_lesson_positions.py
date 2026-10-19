"""Mine real teaching positions, grouped by the ending they belong to.

The pattern Mohit wants: a detector notices the moment, a LESSON carries the
concept, and every position in it comes from a game one of his players
actually lost. Verified by tablebase, not invented.

So this finds every move in the corpus that provably threw away a result,
groups them by what kind of ending it was, and reports which groups are big
enough to carry a lesson. The groups decide what gets authored -- not my
guess about which endgames matter.

For each case it also records how many moves would have held the result,
because that separates a technique a player has never been taught from a
moment of carelessness, and the two need different lessons.

Read-only. Runs on this machine with the tablebase on E:.
"""
import collections
import io
import json
import os
import sys

import chess
import chess.pgn
import chess.syzygy
from pymongo import MongoClient

SYZYGY = os.environ.get("SYZYGY_PATH", "E:/syzygy")
N_GAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 12000
OUT = os.environ.get("OUT", "lesson_material.json")
MAX_PIECES = 5
ORDER = {"loss": 0, "draw": 1, "win": 2}
NAMES = {chess.PAWN: "P", chess.KNIGHT: "N", chess.BISHOP: "B",
         chess.ROOK: "R", chess.QUEEN: "Q"}


def outcome(tables, board):
    if len(board.piece_map()) > MAX_PIECES or not board.is_valid():
        return None
    if board.is_checkmate():
        return "loss"
    if board.is_stalemate() or board.is_insufficient_material():
        return "draw"
    try:
        wdl = tables.probe_wdl(board)
    except Exception:
        return None
    return "win" if wdl > 0 else ("loss" if wdl < 0 else "draw")


def after(tables, board, move):
    nxt = board.copy()
    try:
        nxt.push(move)
    except Exception:
        return None
    theirs = outcome(tables, nxt)
    if theirs is None:
        return None
    return {"win": "loss", "loss": "win", "draw": "draw"}[theirs]


def ending_name(board, colour):
    mine = collections.Counter()
    theirs = collections.Counter()
    for _sq, p in board.piece_map().items():
        if p.piece_type == chess.KING:
            continue
        (mine if p.color == colour else theirs)[p.piece_type] += 1

    def sig(c):
        return "".join(NAMES[t] * n for t in (chess.QUEEN, chess.ROOK, chess.BISHOP,
                                              chess.KNIGHT, chess.PAWN) for n in [c[t]])
    a, b = sig(mine), sig(theirs)
    if not a and not b:
        return "bare kings"
    if set(a + b) <= {"P"}:
        return "pawn ending (%s v %s)" % (a or "-", b or "-")
    return "%s v %s" % (a or "-", b or "-")


def main():
    tables = chess.syzygy.open_tablebase(SYZYGY)
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=20000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    cur = db.games.find(
        {"is_analyzed": True, "pgn": {"$nin": [None, ""]}},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1},
    ).limit(N_GAMES)

    found = []
    seen = 0
    for g in cur:
        seen += 1
        uc = chess.WHITE if (g.get("user_color") or "white").lower() == "white" else chess.BLACK
        try:
            game = chess.pgn.read_game(io.StringIO(g["pgn"]))
        except Exception:
            continue
        if game is None:
            continue
        board = game.board()
        for mv in game.mainline_moves():
            if board.turn == uc and len(board.piece_map()) <= MAX_PIECES:
                before = outcome(tables, board)
                if before is not None and before != "loss":
                    got = after(tables, board, mv)
                    if got is not None and ORDER[got] < ORDER[before]:
                        legal = list(board.legal_moves)
                        held = [m for m in legal
                                if (after(tables, board, m) or "loss") == before]
                        try:
                            san = board.san(mv)
                            held_san = [board.san(m) for m in held[:4]]
                        except Exception:
                            board.push(mv)
                            continue
                        found.append({
                            "game_id": g["game_id"],
                            "fen": board.fen(),
                            "played": san,
                            "move_number": board.fullmove_number,
                            "before": before,
                            "after": got,
                            "held": len(held),
                            "legal": len(legal),
                            "held_moves": held_san,
                            "ending": ending_name(board, uc),
                            "stalemate": (lambda bb: (bb.push(mv), bb.is_stalemate())[1])(board.copy()),
                        })
            board.push(mv)
        if seen % 3000 == 0:
            print("   ...%d games, %d cases" % (seen, len(found)), flush=True)

    tables.close()
    groups = collections.Counter(c["ending"] for c in found)
    print("\n%d games walked, %d provable result-changing moves\n" % (seen, len(found)))
    print("BY ENDING -- which groups are big enough to carry a lesson")
    print("%-34s%8s%10s%10s" % ("ending", "cases", "stalemate", "1-move-only"))
    print("-" * 64)
    for name, n in groups.most_common(14):
        sm = sum(1 for c in found if c["ending"] == name and c["stalemate"])
        one = sum(1 for c in found if c["ending"] == name and c["held"] == 1)
        print("%-34s%8d%10d%10d" % (name, n, sm, one))

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(found, fh, indent=1)
    print("\nwrote %d cases to %s" % (len(found), OUT))


main()

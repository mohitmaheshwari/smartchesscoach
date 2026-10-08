"""Does the printed question tell the truth about each tagged position?

The pin card says "two of their pieces are on one line, and the one in front is
worth less". The skewer card says the bigger one is in front. Those are claims
about the board, printed to the player, and nothing so far has checked them --
the gate was asked "is this a pin" and answered, and we would be taking its word
for what the sentence promises.

This is the printed-question-against-the-grader check in its original form: a
card may not advertise a geometry the position does not have.

HOW IT CHECKS. Independently of the gate, by maths and not by labels. After the
move is played, walk every ray from the moving piece's landing square. A ray
counts when it meets an enemy piece and then, continuing in the same direction
through empty squares, meets a second enemy piece. The piece values of those two
decide which sentence is honest:

    front worth LESS than back  -> the pin sentence is true
    front worth MORE than back  -> the skewer sentence is true
    equal                       -> NEITHER sentence is true, and the position
                                   must not be served with either card

The king is given a value above the queen, so "king in front" is a skewer and
"king behind" is a pin, which is how both are taught.

A negative control runs alongside: the same check against a random legal move
instead of the answer. If that scores anywhere near the real answers, the check
is passing everything and is worthless.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import random
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import chess  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.opportunity_gate import shape_of_best_move  # noqa: E402

# The king sits above the queen so that "king in front" reads as a skewer.
VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
         chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 10}

RAYS = {
    chess.ROOK: ((1, 0), (-1, 0), (0, 1), (0, -1)),
    chess.BISHOP: ((1, 1), (1, -1), (-1, 1), (-1, -1)),
}
RAYS[chess.QUEEN] = RAYS[chess.ROOK] + RAYS[chess.BISHOP]


def alignment_after(fen: str, uci: str):
    """Which sentence is true after this move: 'pin', 'skewer', or None.

    Only the piece that moved is considered. A pin created by a piece standing
    still is a different claim and this card does not make it.
    """
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
    except Exception:
        return None
    if move not in board.legal_moves:
        return None
    mover = board.piece_at(move.from_square)
    if mover is None:
        return None
    board.push(move)
    piece = board.piece_at(move.to_square)
    if piece is None:
        return None                      # promoted or captured away
    directions = RAYS.get(piece.piece_type)
    if not directions:
        return None                      # knights, pawns and kings make no line
    me = piece.color
    found = []
    f0, r0 = chess.square_file(move.to_square), chess.square_rank(move.to_square)
    for df, dr in directions:
        first = second = None
        f, r = f0 + df, r0 + dr
        while 0 <= f < 8 and 0 <= r < 8:
            at = board.piece_at(chess.square(f, r))
            if at is not None:
                if at.color == me:
                    break                # own piece blocks the line
                if first is None:
                    first = at
                else:
                    second = at
                    break
            f, r = f + df, r + dr
        if first is not None and second is not None:
            found.append((VALUE[first.piece_type], VALUE[second.piece_type]))
    for front, back in found:
        if front < back:
            return "pin"
    for front, back in found:
        if front > back:
            return "skewer"
    return None


async def main_async(sample: int) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]
    rng = random.Random(20261003)
    overall = collections.Counter()

    for name, themed in (("lichess_puzzles", True),
                         ("community_puzzles", False),
                         ("community_training_positions", False)):
        query = ({"themes": {"$in": ["pin", "skewer"]},
                  "rating": {"$gte": 1000, "$lte": 1400}} if themed else {})
        proj = ({"_id": 0, "fen": 1, "moves": 1} if themed
                else {"_id": 0, "fen": 1, "best_move_uci": 1})
        docs = await db[name].find(query, proj).limit(sample * 12).to_list(sample * 12)
        rows = collections.Counter()
        control = collections.Counter()
        shown = 0
        for doc in docs:
            if themed:
                moves = (doc["moves"].split() if isinstance(doc.get("moves"), str)
                         else list(doc.get("moves") or ()))
                if len(moves) < 2:
                    continue
                board = chess.Board(doc["fen"])
                try:
                    setup = chess.Move.from_uci(moves[0])
                except Exception:
                    continue
                if setup not in board.legal_moves:
                    continue
                board.push(setup)
                fen, answer = board.fen(), moves[1]
            else:
                fen, answer = doc.get("fen"), doc.get("best_move_uci")
                if not fen or not answer:
                    continue
            gate = shape_of_best_move(fen, answer)
            if gate not in ("pin", "skewer"):
                continue
            truth = alignment_after(fen, answer)
            rows[(gate, truth)] += 1
            if rows.total() <= sample:
                # NEGATIVE CONTROL: the same geometry test on a random legal
                # move from the same position.
                board = chess.Board(fen)
                legal = [m.uci() for m in board.legal_moves if m.uci() != answer]
                if legal:
                    control[alignment_after(fen, rng.choice(legal))] += 1
                if truth is None and shown < 4:
                    shown += 1
                    print("   MISMATCH gate=%s truth=none  %s  %s"
                          % (gate, fen, answer))
            if rows.total() >= sample:
                break

        total = sum(rows.values())
        agree = sum(v for (g, t), v in rows.items() if g == t)
        wrong_word = sum(v for (g, t), v in rows.items()
                         if t is not None and g != t)
        none = sum(v for (g, t), v in rows.items() if t is None)
        print("\n%s -- %d gate-tagged positions checked" % (name, total))
        if total:
            print("   sentence true as tagged      %4d  (%.0f%%)"
                  % (agree, 100.0 * agree / total))
            print("   other sentence would be true %4d  (%.0f%%)"
                  % (wrong_word, 100.0 * wrong_word / total))
            print("   neither sentence true        %4d  (%.0f%%)"
                  % (none, 100.0 * none / total))
        ctot = sum(control.values())
        chit = ctot - control[None]
        print("   control, a random legal move:  %d of %d show any alignment (%.0f%%)"
              % (chit, ctot, 100.0 * chit / max(ctot, 1)))
        overall["agree"] += agree
        overall["wrong"] += wrong_word
        overall["none"] += none

    tot = sum(overall.values())
    print("\nACROSS ALL SOURCES -- %d positions" % tot)
    for k in ("agree", "wrong", "none"):
        print("   %-6s %5d  (%.0f%%)" % (k, overall[k], 100.0 * overall[k] / max(tot, 1)))
    print("\nA position where neither sentence is true must not be served, and")
    print("one where the other sentence is true must be served with that card.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=300)
    args = parser.parse_args()
    return asyncio.run(main_async(args.sample))


if __name__ == "__main__":
    raise SystemExit(main())

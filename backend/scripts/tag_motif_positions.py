"""Write `drill_motif` onto positions that already exist in the pools.

docs/pin_skewer_drill_scope.md. The drill needs to know which stored positions
are pins and which are skewers. The positions are already there -- 4.1M Lichess
puzzles, 41k community puzzles, 50k community training positions -- and what is
missing is the label. So this adds a field and creates nothing.

TWO DECISIONS, DELIBERATELY SEPARATE.

Whether to serve the position at all: `opportunity_gate.shape_of_best_move`,
the function that measured the weakness, so the drill trains what was measured.
Lichess ships its own `themes` and they answer a DIFFERENT question -- a pin
mattering anywhere in the solution line, against this move creating one -- so
the theme only narrows the scan and the gate decides.

Which card to print: `motif_alignment.alignment_after`, from the geometry. On
900 tagged positions the two names agreed 895 times, and the five disagreements
would each have printed a sentence that was false about the board. So the stored
`drill_motif` comes from the geometry and a position is tagged only when BOTH
call it an alignment. The printed sentence is then true by construction.

THE LICHESS OFF-BY-ONE. `moves[0]` is the OPPONENT'S move and the player's
answer is `moves[1]`. Measured, not read off a spec: treating `moves[0]` as the
answer gets 8% gate agreement on pin and 2% on skewer, and playing it first gets
40% and 69%. So for Lichess this also stores `drill_fen` and `drill_answer_uci`
-- the position the player is actually shown and the move that solves it -- so
no reader downstream has to rediscover the offset. Every place that recomputes
it is a place it can be got wrong again.

Safe by default: prints ROWS, not just totals, and writes nothing without
--apply. Idempotent -- re-running overwrites the same field by _id.

    python scripts/tag_motif_positions.py                      # dry run
    python scripts/tag_motif_positions.py --apply
    python scripts/tag_motif_positions.py --source lichess --apply
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import chess  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from pymongo import UpdateOne  # noqa: E402

from services.motif_alignment import alignment_after  # noqa: E402
from services.opportunity_gate import GATE_VERSION, shape_of_best_move  # noqa: E402

WANTED = ("pin", "skewer")


def admit(fen: str, answer: str):
    """The card to print, or None to leave this position alone.

    Both must agree it is an alignment tactic; the geometry chooses the wording.
    """
    if shape_of_best_move(fen, answer) not in WANTED:
        return None
    card = alignment_after(fen, answer)
    return card if card in WANTED else None

# Set in the scope from the measured spread of Lichess ratings for these shapes
# (pin p25 1264, skewer p25 1004) against a player near 1200. Widening it is a
# config change, not a code change, which is why it is named here and not
# inlined at the query.
LICHESS_RATING_MIN = 1000
LICHESS_RATING_MAX = 1400

BATCH = 2000


def _moves(doc) -> list:
    raw = doc.get("moves")
    if isinstance(raw, str):
        return raw.split()
    return list(raw or ())


def tag_lichess(doc):
    """(card, drill_fen, answer_uci) for a Lichess puzzle, or None.

    The opponent's move is played FIRST. Both the position after it and the
    answer are stored, so the offset is resolved once, here.
    """
    moves = _moves(doc)
    if len(moves) < 2:
        return None
    try:
        board = chess.Board(doc["fen"])
        setup = chess.Move.from_uci(moves[0])
        if setup not in board.legal_moves:
            return None
        board.push(setup)
    except Exception:
        return None
    drill_fen = board.fen()
    card = admit(drill_fen, moves[1])
    if card is None:
        return None
    return card, drill_fen, moves[1]


def tag_community(doc):
    """(card, fen, answer_uci) for a community position, or None.

    These store the position the player saw and the engine's move directly, so
    there is no offset to resolve.
    """
    fen = doc.get("fen")
    best = doc.get("best_move_uci")
    if not fen or not best:
        return None
    card = admit(fen, best)
    if card is None:
        return None
    return card, fen, best


async def run(db, name, query, projection, tagger, apply, limit):
    total = await db[name].count_documents(query)
    print("\n%s -- %d candidate docs" % (name, total))
    seen = scanned = 0
    found = collections.Counter()
    ops = []
    shown = 0
    cursor = db[name].find(query, projection)
    if limit:
        cursor = cursor.limit(limit)
    async for doc in cursor:
        scanned += 1
        got = tagger(doc)
        if got is None:
            continue
        shape, fen, answer = got
        found[shape] += 1
        seen += 1
        if shown < 5:
            shown += 1
            print("   ROW %s  %s  answer=%s" % (shape, fen, answer))
        ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {
            # The card to print, from the geometry. This is what the serving
            # layer reads, so that nothing downstream can word a card from a
            # name the board does not support.
            "drill_motif": shape,
            "gate_version": GATE_VERSION,
            "drill_fen": fen,
            "drill_answer_uci": answer,
        }}))
        if apply and len(ops) >= BATCH:
            await db[name].bulk_write(ops, ordered=False)
            ops = []
    if apply and ops:
        await db[name].bulk_write(ops, ordered=False)
    print("   scanned %d, tagged %d  (%s)"
          % (scanned, seen, ", ".join("%s %d" % kv for kv in found.most_common())
             or "none"))
    if not apply:
        print("   DRY RUN -- nothing written")
    return seen


async def main_async(apply: bool, only: str | None, limit: int) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]
    print("gate: %s" % GATE_VERSION)
    if not apply:
        print("DRY RUN. Pass --apply to write.")

    jobs = {
        "lichess": ("lichess_puzzles",
                    {"themes": {"$in": list(WANTED)},
                     "rating": {"$gte": LICHESS_RATING_MIN,
                                "$lte": LICHESS_RATING_MAX}},
                    {"fen": 1, "moves": 1}, tag_lichess),
        "community_puzzles": ("community_puzzles", {},
                              {"fen": 1, "best_move_uci": 1}, tag_community),
        "community_positions": ("community_training_positions", {},
                                {"fen": 1, "best_move_uci": 1}, tag_community),
    }
    if only:
        if only not in jobs:
            print("unknown source %r; pick from %s" % (only, ", ".join(jobs)))
            return 1
        jobs = {only: jobs[only]}

    tagged = 0
    for label, (name, query, proj, tagger) in jobs.items():
        tagged += await run(db, name, query, proj, tagger, apply, limit)
    print("\ntotal tagged: %d" % tagged)
    if apply:
        for name in {j[0] for j in jobs.values()}:
            await db[name].create_index([("drill_motif", 1)])
        print("indexed drill_motif on each collection touched")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source", default=None)
    parser.add_argument("--limit", type=int, default=0,
                        help="scan only this many docs per source, for a smoke test")
    args = parser.parse_args()
    return asyncio.run(main_async(args.apply, args.source, args.limit))


if __name__ == "__main__":
    raise SystemExit(main())

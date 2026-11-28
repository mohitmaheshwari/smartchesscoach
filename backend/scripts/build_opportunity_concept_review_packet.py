"""Build the semantic review sheet for the opportunity-denominator ids.

    gap:missed_tactic:fork_opportunity
    gap:missed_tactic:skewer_opportunity

WHY THIS IS NOT SHAPED LIKE THE OTHER PACKETS
---------------------------------------------
Every other `build_*_promotion_packet.py` here rebuilds a GOLD from board
state "without importing the detector, its verifier or the stored verdict".
That independence is what makes a precision number mean something about a
heuristic.

It does not transfer to these two ids. Their candidate is already an
exhaustive board proof -- the move, every legal reply, then the best
follow-up capture by static exchange. A second independent implementation of
an exhaustive search is the same search written twice: agreement would be
implementation-against-implementation, which the 2026-08-27 threshold lock
rejects for precision, and disagreement would only mean one of them has a bug.

What is unmeasured is not the arithmetic. It is the concept:

    the proof says   "this move forces >= 200cp of material against every reply"
    the claim says   "a fork was there to play"

Only the second reaches a player. So this script does not grade anything. It
assembles the rows a human has to read, one question per row:

    is "a fork was there to play" TRUE and worth teaching in this position?

That answer is what the lock means by reviewed semantic precision for a
prover, and no script can produce it.

WHAT IS IN THE SHEET
--------------------
POSITIVES   `coachable` fires -- the chance was proved, he did not take it,
            and the engine independently calls his move an error of >=100cp.
            This is exactly the set a caption would ever be built from, so it
            is the only set whose precision matters.

NEGATIVES   stratified near-misses, because a reviewer who only sees
            positives cannot tell a precise prover from a greedy one:

              under_bar          proved a gain, but below MIN_*_GAIN_CP
              engine_disagrees   proved and not played, but the engine liked
                                 his move (the 39.9% v1 failure mode)
              negative_floor     the shape is there and the floor came back
                                 negative -- the three-ply horizon

Read-only. No engine, no writes, and no user, game or account identity: each
row is keyed by a hash of position-and-move so a reviewer cannot be swayed by
whose game it was, and so the sheet carries nothing about a player.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient                                # noqa: E402

from services import tactic_opportunity as to                  # noqa: E402
from services.tactic_payoff import forced_material_gain        # noqa: E402

SCHEMA_VERSION = "opportunity_concept_review.v1"
SEED = "20261128-opportunity-concept-review-v1"
QUALITY_IDS = {
    "fork": "gap:missed_tactic:fork_opportunity",
    "skewer": "gap:missed_tactic:skewer_opportunity",
}
BARS = {"fork": to.MIN_FORK_GAIN_CP, "skewer": to.MIN_SKEWER_GAIN_CP}
CANDIDATES = {"fork": to.fork_candidates, "skewer": to.skewer_candidates}
POSITIVE_TARGET = 50
NEGATIVE_PER_STRATUM = 8
STRATA = ("under_bar", "engine_disagrees", "negative_floor")
PIECE_NAMES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king",
}


def row_id(fen: str, move_uci: str) -> str:
    """A stable key that carries no identity. Position and move only."""
    digest = hashlib.sha256(
        (SEED + "|" + fen + "|" + move_uci).encode("utf-8")).hexdigest()
    return digest[:12]


def men_hit(board: chess.Board, move: chess.Move) -> list:
    """Which enemy men the moved piece attacks once it lands.

    Descriptive only -- it explains the row to the reviewer and is never used
    to decide anything, so it may not be mistaken for a second prover.
    """
    after = board.copy(stack=False)
    after.push(move)
    them = not board.turn
    out = []
    for square in after.attacks(move.to_square):
        piece = after.piece_at(square)
        if piece is not None and piece.color == them:
            out.append("%s on %s" % (PIECE_NAMES[piece.piece_type],
                                     chess.square_name(square)))
    return sorted(out)


def explain(board: chess.Board, move: chess.Move, motif: str) -> dict:
    """How the row is described to the reviewer, in the motif's own terms.

    `men_hit` alone is WRONG for a skewer and would have corrupted the grade.
    A skewer's rear man is behind the front man on the same ray, so the front
    man blocks it and `board.attacks` never reports it: the row for
    `2r5/R7/2Pp4/5k2/1p3b2/6p1/1PP5/1K5R w - - 0 40`, Rf7+, read "hits: king
    on f5" and looked like a plain check, when the bishop on f4 behind the
    king is the whole point and the proved gain of 300 is that bishop. A
    reviewer shown only the front man marks a correct skewer false, and a
    review sheet that misleads produces a precision number worse than none.

    So a skewer row carries the alignment the prover actually found --
    attacker, front, rear -- read back from `verify_created_alignment`, which
    is the same call that admitted the move. That is not a second prover: it
    is the row explaining itself.
    """
    if motif != "skewer":
        return {"men_the_move_hits": men_hit(board, move)}
    from services.aligned_tactic_puzzle_proof import verify_created_alignment
    created = verify_created_alignment(board, move, "skewer") or {}
    after = board.copy(stack=False)
    after.push(move)

    def name_at(square_name):
        try:
            piece = after.piece_at(chess.parse_square(str(square_name)))
        except (ValueError, TypeError):
            piece = None
        return ("%s on %s" % (PIECE_NAMES[piece.piece_type], square_name)
                if piece else str(square_name))

    front, rear = created.get("front_square"), created.get("rear_square")
    return {
        "the_line": {
            "attacker_lands_on": created.get("attacker_square"),
            "front_man": name_at(front) if front else None,
            "rear_man_behind_it": name_at(rear) if rear else None,
        },
        # Kept so a fork row and a skewer row stay comparable, but named for
        # what it is: only the man in front, never the one behind.
        "men_the_move_hits_directly": men_hit(board, move),
    }


def engine_of(row: dict) -> dict:
    return {
        "best_move_uci": row.get("best_move_uci"),
        "evaluation": row.get("execution_quality"),
        "cp_loss": row.get("cp_loss"),
    }


def san_of(board: chess.Board, move_uci) -> str:
    try:
        return board.san(chess.Move.from_uci(str(move_uci)))
    except (ValueError, TypeError, AssertionError):
        return str(move_uci)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mongo-url", default=os.environ.get("MONGO_URL"))
    ap.add_argument("--db", default=os.environ.get("DB_NAME") or "chess_coach")
    ap.add_argument("--scan", type=int, default=20000,
                    help="stored user moves to read before sampling")
    ap.add_argument("--out", default=None, help="write JSON here as well")
    args = ap.parse_args()
    if not args.mongo_url:
        print("need --mongo-url or MONGO_URL", file=sys.stderr)
        return 2

    db = MongoClient(args.mongo_url, serverSelectionTimeoutMS=25000)[args.db]
    cursor = db.move_observations.find(
        {"fen_before": {"$ne": None}},
        {"_id": 0, "fen_before": 1, "move_uci": 1, "cp_loss": 1,
         "execution_quality": 1, "best_move_uci": 1},
    ).limit(args.scan)

    positives = defaultdict(list)
    negatives = defaultdict(lambda: defaultdict(list))
    seen = Counter()
    scanned = 0

    for row in cursor:
        fen = row["fen_before"]
        try:
            board = chess.Board(fen)
        except (ValueError, TypeError):
            continue
        if not board.is_valid():
            continue
        scanned += 1
        engine = engine_of(row)
        verdicts = to.opportunities(fen, row.get("move_uci"), engine=engine)
        if verdicts is None:
            continue

        for motif in ("fork", "skewer"):
            verdict = verdicts[motif]
            seen[motif + ":eligible"] += int(bool(verdict["eligible"]))
            seen[motif + ":fires"] += int(bool(verdict["fires"]))
            seen[motif + ":coachable"] += int(verdict["coachable"] is True)

            if verdict["coachable"] is True:
                if len(positives[motif]) < POSITIVE_TARGET:
                    chance = chess.Move.from_uci(verdict["chances"][0])
                    entry = {
                        "row_id": row_id(fen, verdict["chances"][0]),
                        "fen": fen,
                        "he_played": san_of(board, row.get("move_uci")),
                        "chance": san_of(board, verdict["chances"][0]),
                        "chance_uci": verdict["chances"][0],
                        "proved_gain_cp": forced_material_gain(board, chance),
                        "engine_called_his_move": engine["evaluation"],
                        "engine_cp_loss": engine["cp_loss"],
                        "claim_under_review":
                            "A %s was there to play" % motif,
                    }
                    entry.update(explain(board, chance, motif))
                    positives[motif].append(entry)
                continue

            # Negatives: the shape was offered but no claim was made. Which
            # reason it failed on is the stratum.
            offered = CANDIDATES[motif](board)
            if not offered:
                continue
            gains = [(mv, forced_material_gain(board, mv)) for mv in offered]
            gains = [(mv, g) for mv, g in gains if g is not None]
            if not gains:
                continue
            best_move, best_gain = max(gains, key=lambda pair: pair[1])

            if best_gain < 0:
                stratum = "negative_floor"
            elif best_gain < BARS[motif]:
                stratum = "under_bar"
            elif verdict["fires"]:
                stratum = "engine_disagrees"
            else:
                continue

            bucket = negatives[motif][stratum]
            if len(bucket) < NEGATIVE_PER_STRATUM:
                entry = {
                    "row_id": row_id(fen, best_move.uci()),
                    "fen": fen,
                    "he_played": san_of(board, row.get("move_uci")),
                    "shape_offered": san_of(board, best_move.uci()),
                    "proved_gain_cp": best_gain,
                    "bar_cp": BARS[motif],
                    "engine_called_his_move": engine["evaluation"],
                    "engine_cp_loss": engine["cp_loss"],
                    "why_no_claim": stratum,
                    "claim_withheld":
                        "A %s was there to play" % motif,
                }
                entry.update(explain(board, best_move, motif))
                bucket.append(entry)

    report = {
        "schema_version": SCHEMA_VERSION,
        "seed": SEED,
        "quality_ids": QUALITY_IDS,
        "bars_cp": BARS,
        "opportunity_version": to.TACTIC_OPPORTUNITY_VERSION,
        "moves_scanned": scanned,
        "counts": dict(seen),
        "question_for_the_reviewer": (
            "For each POSITIVE row: is the claim true, and is it worth "
            "teaching? For each NEGATIVE row: was withholding the claim "
            "right? The 2026-08-27 lock needs >=95% of the positives true, "
            "with a Wilson lower bound >=85%, for Caption."
        ),
        "grade_this_sheet_cannot_produce": (
            "semantic precision -- a human must answer, because the "
            "arithmetic is a proof and only the concept is in question"
        ),
        "positives": {m: positives[m] for m in ("fork", "skewer")},
        "negatives": {
            m: {s: negatives[m][s] for s in STRATA} for m in ("fork", "skewer")
        },
        "database_writes": 0,
        "engine_calls": 0,
    }

    text = json.dumps(report, sort_keys=True, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("wrote %s" % args.out, file=sys.stderr)
    else:
        print(text)

    print("scanned %d moves | positives fork=%d skewer=%d | negatives %s"
          % (scanned, len(positives["fork"]), len(positives["skewer"]),
             {m: {s: len(negatives[m][s]) for s in STRATA}
              for m in ("fork", "skewer")}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

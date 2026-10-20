"""What are the 7,195 `missed_generic_tactic` observations, actually?

The subtype is assigned when a move loses 200 centipawns or more and none of
the four named motif checks matched. Measured separately: no existing prover
recognises about three quarters of them, and the quarter that is recognised is
dominated by one prover too imprecise to name. So before anyone writes another
motif detector, the question is whether these positions are tactics at all.

That is decidable from stored data with no model and no reviewer. A tactic wins
material, and soon. So this walks the engine's own best line and asks what it
actually achieves:

    mate in the line            a forcing sequence
    material within 4 plies     a tactic in the ordinary sense
    material only later         a calculation-depth problem, not a motif
    no material at all          a POSITIONAL loss, and calling it a missed
                                tactic is a mislabel, not a missing name

It also asks what the played move did, because "missed a tactic" and "gave
something away" are different errors that cp_loss cannot separate, and the
second needs no motif detector at all.

Material is counted in centipawns from the mover's side, queen 900 down to
pawn 100, kings excluded. A gain of 100 is the threshold for "won material" --
one pawn, the smallest unit a 600-1500 player is being asked to notice.

Read-only.
"""
from __future__ import annotations

import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402
from pymongo import MongoClient  # noqa: E402

VALUE = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300,
         chess.ROOK: 500, chess.QUEEN: 900}
MATERIAL_GAIN = 100
FAST_PLIES = 4


def advantage(board: chess.Board, colour: bool) -> int:
    total = 0
    for piece in board.piece_map().values():
        if piece.piece_type == chess.KING:
            continue
        value = VALUE[piece.piece_type]
        total += value if piece.color == colour else -value
    return total


def walk(board: chess.Board, first_move: str, line, mover: bool):
    """Push a move then its SAN continuation; report what the line achieves.

    Returns (mate, best_gain, plies_to_gain, final_gain) or None when the line
    will not replay. A line that does not replay is reported, never silently
    treated as achieving nothing.

    `best_gain` is a running MAXIMUM, which is what "the line wins material"
    needs. `final_gain` is where the line ends up, and it is reported
    separately because the first pass used the maximum for both and so could
    never register a LOSS -- it reported that 100% of played moves held their
    material, which is not a believable number and was the tell.
    """
    probe = board.copy()
    try:
        move = probe.parse_san(first_move)
    except (ValueError, AssertionError):
        try:
            move = chess.Move.from_uci(str(first_move))
            if move not in probe.legal_moves:
                return None
        except ValueError:
            return None
    base = advantage(probe, mover)
    probe.push(move)
    best_gain, plies_to_gain, ply = 0, None, 1
    final_gain = advantage(probe, mover) - base
    if probe.is_checkmate():
        return True, 10000, ply, final_gain
    for san in (line or [])[:10]:
        try:
            probe.push(probe.parse_san(str(san)))
        except (ValueError, AssertionError):
            break
        ply += 1
        if probe.is_checkmate():
            return True, 10000, ply, final_gain
        gain = advantage(probe, mover) - base
        final_gain = gain
        if gain > best_gain:
            best_gain = gain
            if plies_to_gain is None and gain >= MATERIAL_GAIN:
                plies_to_gain = ply
    return False, best_gain, plies_to_gain, final_gain


def classify(result) -> str:
    if result is None:
        return "line will not replay"
    mate, gain, plies, _final = result
    if mate:
        return "mate in the best line"
    if plies is not None and plies <= FAST_PLIES:
        return "wins material within 4 plies"
    if plies is not None:
        return "wins material only later"
    return "NO material gain: positional"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1200)
    args = parser.parse_args()

    url = os.environ["MONGO_URL"].replace("host.docker.internal", "localhost")
    db_name = os.environ.get("DB_NAME")
    if not db_name:
        raise SystemExit("DB_NAME must be set explicitly")
    db = MongoClient(url, serverSelectionTimeoutMS=30000,
                     socketTimeoutMS=900000)[db_name]

    observations = list(db.move_observations.find(
        {"subtype": "missed_generic_tactic"},
        {"_id": 0, "game_id": 1, "fen_before": 1, "phase": 1},
    ).limit(args.n))
    game_ids = list({o["game_id"] for o in observations})
    rows = {}
    for analysis in db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        for move in (analysis.get("stockfish_analysis") or {}).get(
                "move_evaluations") or []:
            if move.get("fen_before"):
                rows[(analysis["game_id"], move["fen_before"])] = move

    best_kind = collections.Counter()
    shape = collections.Counter()
    played_lost = collections.Counter()
    phases = collections.defaultdict(collections.Counter)
    tried = 0

    for observation in observations:
        move = rows.get((observation["game_id"], observation.get("fen_before")))
        if not move or not move.get("best_move") or not move.get("move"):
            continue
        try:
            board = chess.Board(observation["fen_before"])
        except ValueError:
            continue
        tried += 1
        mover = board.turn

        try:
            best = board.parse_san(move["best_move"])
            best_kind["capture" if board.is_capture(best) else
                      ("check" if board.gives_check(best) else "quiet")] += 1
        except (ValueError, AssertionError):
            best_kind["unparseable"] += 1

        label = classify(walk(board, move["best_move"],
                              move.get("pv_after_best"), mover))
        shape[label] += 1
        phases[observation.get("phase") or "unknown"][label] += 1

        played = walk(board, move["move"], move.get("pv_after_played"), mover)
        if played is None:
            played_lost["played line will not replay"] += 1
        elif played[3] <= -MATERIAL_GAIN:
            played_lost["played move itself loses material"] += 1
        else:
            played_lost["played move holds material"] += 1

    print(f"generic observations characterised: {tried}")
    print()
    print("WHAT THE ENGINE'S BEST LINE ACHIEVES")
    for label, count in shape.most_common():
        print("   %-32s %5d  %5.1f%%" % (label, count, 100.0 * count / tried))
    print()
    print("THE BEST MOVE ITSELF")
    for label, count in best_kind.most_common():
        print("   %-32s %5d  %5.1f%%" % (label, count, 100.0 * count / tried))
    print()
    print("WHAT THE PLAYED MOVE DID")
    for label, count in played_lost.most_common():
        print("   %-32s %5d  %5.1f%%" % (label, count, 100.0 * count / tried))
    print()
    print("BY PHASE")
    for phase, counts in sorted(phases.items(),
                                key=lambda kv: -sum(kv[1].values())):
        total = sum(counts.values())
        top = counts.most_common(1)[0]
        print("   %-12s %5d observations, mostly %s (%.0f%%)"
              % (phase, total, top[0], 100.0 * top[1] / total))


if __name__ == "__main__":
    main()

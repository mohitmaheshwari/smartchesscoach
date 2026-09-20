"""Measure our motif detectors against Lichess's 4.1M theme-labelled puzzles.

Mohit, 2026-09-21: "lichess has already categorized puzzles for us, can you
use those theme puzzles, build detectors and see detectors should fire as
stockfish suggests for all the themes?"

This is the thing that has blocked every promotion in this product. The
2026-08-27 threshold lock rejects implementation-to-implementation agreement
("duplicated logic can agree and still be wrong"), so precision has had to
come from Mohit ruling cards one at a time -- discovered_attack reached 49 of
the 50 it needed and stalled there. And RECALL has never been measured at
all: Plan grade asks for >=60% semantic recall on independently selected
opportunities, and we have no such set.

lichess_puzzles is one. 4,110,434 positions, 74 themes, each puzzle
engine-verified for a unique solution and solve-tested by thousands of humans
(the sample rows carry hundreds to thousands of plays). For a theme we claim
to detect, the labelled puzzles ARE independently selected opportunities.

HONEST LIMIT, stated because it decides what this can promote: Lichess themes
are computed by Lichess's own detectors, not hand-labelled. So this is still
one implementation checked against another -- exactly what the lock rejects
for PRECISION. It is a different team's implementation over millions of
positions rather than our own second copy, which makes it far stronger
evidence than the simple_hang packet that cost us a day, but it is not human
semantic gold and this script does not claim it is.

What it gives us that we genuinely do not have:

  RECALL   -- of the puzzles Lichess calls a fork, how many does our fork
              detector find? Never measured before, for any detector.
  SCALE    -- thousands of cases per theme instead of 50 hand rulings.
  REGRESSION -- a fixed set to re-run after every detector change.

    python scripts/validate_detectors_against_lichess.py
    python scripts/validate_detectors_against_lichess.py --per-theme 500

Lichess puzzle format: `fen` is BEFORE the opponent's setup move. moves[0] is
that setup move, moves[1] is the solution, moves[2:] is the continuation --
which is exactly the pv_after_best our proof builders take.
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
from pymongo import MongoClient

# A puzzle is by definition a real tactic, so the cp_loss gate our detectors
# apply to game moves is satisfied by construction. 300 stands in for "this
# was a significant miss" without inventing an evaluation.
ASSUMED_CP_LOSS = 300


def _puzzle_position(doc: Dict[str, Any]):
    """The position the solver sees, the solution, and the continuation."""
    moves = list(doc.get("moves") or [])
    if len(moves) < 2:
        return None
    try:
        board = chess.Board(str(doc["fen"]))
        board.push(chess.Move.from_uci(str(moves[0])))
        solution = chess.Move.from_uci(str(moves[1]))
        if solution not in board.legal_moves:
            return None
        san = board.san(solution)
        # The rest of the line, in SAN, as pv_after_best
        pv: List[str] = []
        probe = board.copy(stack=False)
        probe.push(solution)
        for uci in moves[2:]:
            mv = chess.Move.from_uci(str(uci))
            if mv not in probe.legal_moves:
                break
            pv.append(probe.san(mv))
            probe.push(mv)
        return board, solution, san, pv
    except Exception:  # noqa: BLE001
        return None


def _a_different_legal_move(board: chess.Board, solution: chess.Move):
    """Our proof builders need a 'played' move that is not the best one."""
    for move in board.legal_moves:
        if move != solution:
            return board.san(move)
    return None


def _fires_fork(board, played_san, best_san, pv):
    from services.fork_puzzle_proof import build_fork_proof
    bundle = build_fork_proof(board.copy(stack=False), played_san, best_san,
                              pv, ASSUMED_CP_LOSS)
    return bool(bundle and getattr(bundle.verifier, "verified", False))


def _fires_discovered(board, played_san, best_san, pv):
    from services.discovered_attack_puzzle_proof import (
        build_discovered_attack_proof)
    bundle = build_discovered_attack_proof(
        board.copy(stack=False), played_san, best_san, pv, ASSUMED_CP_LOSS)
    return bool(bundle and getattr(bundle.verifier, "verified", False))


def _fires_back_rank(board, played_san, best_san, pv):
    from services.mate_lesson import back_rank_seal
    probe = board.copy(stack=False)
    try:
        mv = probe.parse_san(best_san)
    except Exception:  # noqa: BLE001
        return False
    probe.push(mv)
    if not probe.is_checkmate():
        return False
    king = probe.king(probe.turn)
    if king is None:
        return False
    return back_rank_seal(probe, mv, king, probe.turn) >= 2


# theme -> (our detector, a short label)
DETECTORS = {
    "fork": (_fires_fork, "tactic:fork_with_stored_payoff"),
    "discoveredAttack": (_fires_discovered,
                         "tactic:discovered_attack_with_stored_payoff"),
    "backRankMate": (_fires_back_rank, "back_rank (mate_lesson)"),
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-theme", type=int, default=400)
    args = parser.parse_args(argv)

    db = MongoClient(os.environ["MONGO_URL"],
                     serverSelectionTimeoutMS=20000)[
        os.environ.get("DB_NAME", "chess_coach")]

    print(f"{'theme':18s} {'detector':46s} {'n':>5s} {'fires':>6s} "
          f"{'RECALL':>7s}")
    print("-" * 90)
    results = {}
    for theme, (fires, label) in DETECTORS.items():
        seen = hit = skipped = 0
        errors: collections.Counter = collections.Counter()
        for doc in db.lichess_puzzles.find(
                {"themes": theme}, {"fen": 1, "moves": 1}).limit(args.per_theme):
            parsed = _puzzle_position(doc)
            if parsed is None:
                skipped += 1
                continue
            board, solution, san, pv = parsed
            played = _a_different_legal_move(board, solution)
            if played is None:
                skipped += 1
                continue
            seen += 1
            try:
                if fires(board, played, san, pv):
                    hit += 1
            except Exception as exc:  # noqa: BLE001
                errors[f"{type(exc).__name__}: {exc}"[:60]] += 1
        recall = 100 * hit / max(seen, 1)
        results[theme] = (seen, hit, recall, errors, skipped)
        print(f"{theme:18s} {label:46s} {seen:5d} {hit:6d} {recall:6.1f}%")

    print()
    print("CROSS-FIRE -- does each detector stay quiet on OTHER themes?")
    print(f"{'detector':22s} {'tested on':18s} {'n':>5s} {'fires':>6s} {'rate':>6s}")
    print("-" * 64)
    for theme, (fires, _label) in DETECTORS.items():
        for other in DETECTORS:
            if other == theme:
                continue
            seen = hit = 0
            for doc in db.lichess_puzzles.find(
                    {"themes": other, "themes": {"$ne": theme}},
                    {"fen": 1, "moves": 1}).limit(200):
                parsed = _puzzle_position(doc)
                if parsed is None:
                    continue
                board, solution, san, pv = parsed
                played = _a_different_legal_move(board, solution)
                if played is None:
                    continue
                seen += 1
                try:
                    if fires(board, played, san, pv):
                        hit += 1
                except Exception:  # noqa: BLE001
                    pass
            if seen:
                print(f"{theme:22s} {other:18s} {seen:5d} {hit:6d} "
                      f"{100 * hit / seen:5.1f}%")

    print()
    for theme, (seen, hit, recall, errors, skipped) in results.items():
        if errors:
            print(f"probe errors on {theme} (a bug, not a finding):")
            for detail, n in errors.most_common(4):
                print(f"   {n:5d}x {detail}")
        if skipped:
            print(f"{theme}: {skipped} puzzles unparseable/skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

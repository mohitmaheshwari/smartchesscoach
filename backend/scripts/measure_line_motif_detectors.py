"""Measure clearance / xRayAttack / interference against Lichess theme labels.

Lichess's own theme tags are the truth source: every puzzle carrying a theme
that the matching detector does not fire on is a bug report, and every puzzle
of ANOTHER theme that it does fire on is a false positive unless the motifs
genuinely coexist there.

Recall is read on the VERIFIER, not the detector, because the verifier is what
gates anything user-facing. Both are printed so a gap between them is visible.

Cross-fire is measured on `mateIn2` and `fork` with the detector's own theme
excluded from the sample. Lichess multi-tags heavily -- roughly half the
`clearance` sample at 600-1500 is also `mateIn2` -- so a cross-fire number
computed without that exclusion measures the tagging, not the detector.

  python scripts/measure_line_motif_detectors.py
  python scripts/measure_line_motif_detectors.py --recall 1000 --crossfire 300
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Optional, Sequence

import chess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.clearance_puzzle_proof import build_clearance_proof  # noqa: E402
from services.interference_puzzle_proof import (  # noqa: E402
    build_interference_proof,
)
from services.xray_attack_puzzle_proof import (  # noqa: E402
    build_xray_attack_proof,
)


#: The proofs take a stored mistake, so the harness has to present a puzzle as
#: one: a plausible wrong move plus a loss big enough to clear the shared 100cp
#: floor. Only the floor matters to the detectors, so a constant is honest here.
HARNESS_CP_LOSS = 250

BUILDERS = {
    "clearance": ("clearance", build_clearance_proof),
    "xRayAttack": ("xRayAttack", build_xray_attack_proof),
    "interference": ("interference", build_interference_proof),
}
CROSSFIRE_THEMES = ("mateIn2", "fork")


def prepare(puzzle: dict) -> Optional[tuple]:
    """Lichess stores the position BEFORE the opponent's move, so push it."""
    moves = puzzle.get("moves") or []
    if len(moves) < 2:
        return None
    try:
        board = chess.Board(puzzle["fen"])
        opening = chess.Move.from_uci(moves[0])
        if opening not in board.legal_moves:
            return None
        board.push(opening)
        best_move = chess.Move.from_uci(moves[1])
        if best_move not in board.legal_moves:
            return None
        best = board.san(best_move)
        played = next(
            (board.san(m) for m in board.legal_moves if m != best_move), None
        )
        if played is None:
            return None
        line = []
        probe = board.copy()
        for uci in moves[1:]:
            move = chess.Move.from_uci(uci)
            if move not in probe.legal_moves:
                break
            line.append(probe.san(move))
            probe.push(move)
        return board, played, best, line[1:]
    except (ValueError, KeyError, AssertionError):
        return None


async def sample(db, theme: str, limit: int, exclude: Sequence[str] = ()) -> list:
    out = []
    cursor = db.lichess_puzzles.find(
        {"themes": theme, "rating": {"$gte": 600, "$lte": 1500}}
    ).limit(limit * 5)
    async for puzzle in cursor:
        themes = puzzle.get("themes") or []
        if any(item in themes for item in exclude):
            continue
        prepared = prepare(puzzle)
        if prepared is None:
            continue
        out.append((puzzle["puzzle_id"], prepared))
        if len(out) >= limit:
            break
    return out


def score(builder, cases) -> tuple:
    fired = 0
    verified = 0
    crashes = 0
    misses = []
    for puzzle_id, (board, played, best, line) in cases:
        try:
            bundle = builder(board, played, best, line, HARNESS_CP_LOSS)
        except Exception as exc:  # a crash is a miss, and a loud one
            crashes += 1
            misses.append((puzzle_id, f"raised {type(exc).__name__}: {exc}"))
            continue
        if bundle is None:
            misses.append((puzzle_id, "no detector fire"))
            continue
        fired += 1
        if bundle.verifier.verified:
            verified += 1
        else:
            misses.append((puzzle_id, "detector fired, verifier refused"))
    return fired, verified, crashes, misses


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recall", type=int, default=1000)
    parser.add_argument("--crossfire", type=int, default=300)
    parser.add_argument("--show-misses", type=int, default=0)
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    client = AsyncIOMotorClient(
        os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    )
    db = client[os.environ.get("DB_NAME", "test_database")]

    wanted = [t for t in BUILDERS if not args.only or t == args.only]
    for name in wanted:
        theme, builder = BUILDERS[name]
        cases = await sample(db, theme, args.recall)
        fired, verified, crashes, misses = score(builder, cases)
        total = len(cases) or 1
        print(f"\n=== {name} ===")
        print(
            f"recall on {len(cases)} `{theme}` puzzles (600-1500): "
            f"detector {fired} ({100 * fired / total:.1f}%), "
            f"verified {verified} ({100 * verified / total:.1f}%)"
        )
        if crashes:
            print(f"  !! {crashes} puzzle(s) CRASHED the builder: "
                  f"{misses[0][1] if misses else ''}")
        for other in CROSSFIRE_THEMES:
            cross = await sample(db, other, args.crossfire, exclude=(theme,))
            c_fired, c_verified, c_crashes, _ = score(builder, cross)
            c_total = len(cross) or 1
            print(
                f"cross-fire on {len(cross)} `{other}` puzzles "
                f"(no `{theme}` tag): detector {c_fired} "
                f"({100 * c_fired / c_total:.1f}%), verified {c_verified} "
                f"({100 * c_verified / c_total:.1f}%)"
                + (f"  !! {c_crashes} crashed" if c_crashes else "")
            )
        for puzzle_id, reason in misses[: args.show_misses]:
            print(f"  miss {puzzle_id}: {reason}")


if __name__ == "__main__":
    asyncio.run(main())

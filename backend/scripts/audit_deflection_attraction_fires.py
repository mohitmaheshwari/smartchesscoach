"""Print every fire with its walked line, so a human can judge the claim.

A recall percentage says a detector fired; it does not say the detector
fired for the right reason. This prints the stored line ply by ply next to
the exact guard / target / sacrifice square the proof named, which is the
only way to tell an untagged true positive from a lucky coincidence.

    python backend/scripts/audit_deflection_attraction_fires.py \
        --detector deflection --theme mateIn2 --limit 300 --show 30
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from scripts.measure_deflection_attraction_detectors import (  # noqa: E402
    SYNTHETIC_CP_LOSS,
    load,
)
from services.attraction_puzzle_proof import build_attraction_proof  # noqa: E402
from services.deflection_puzzle_proof import build_deflection_proof  # noqa: E402


BUILDERS = {
    "deflection": build_deflection_proof,
    "attraction": build_attraction_proof,
}


def walk(board, pv_uci):
    probe = board.copy()
    out = []
    for index, uci in enumerate(pv_uci):
        move = chess.Move.from_uci(uci)
        if move not in probe.legal_moves:
            break
        san = probe.san(move)
        probe.push(move)
        mark = "#" if probe.is_checkmate() else ("+" if probe.is_check() else "")
        out.append(f"{index}:{san}{mark}")
    return " ".join(out)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--detector", required=True, choices=sorted(BUILDERS))
    parser.add_argument("--theme", required=True)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--show", type=int, default=30)
    parser.add_argument("--exclude-own", action="store_true")
    args = parser.parse_args()

    builder = BUILDERS[args.detector]
    db = AsyncIOMotorClient(
        os.environ["MONGO_URL"], serverSelectionTimeoutMS=30000
    )[os.environ.get("DB_NAME", "chess_coach")]

    exclude = (args.detector,) if args.exclude_own else ()
    samples = await load(db, args.theme, args.limit, exclude=exclude)

    shown = 0
    for puzzle, ready in samples:
        board, played, best, pv = ready
        try:
            bundle = builder(board, played, best, pv, SYNTHETIC_CP_LOSS)
        except Exception as exc:  # pragma: no cover - audit tool
            print(f"ERROR {puzzle.get('puzzle_id')}: {exc}")
            continue
        if bundle is None or not bundle.verifier.verified:
            continue
        facts = bundle.verifier.facts[0]
        print("=" * 72)
        print(
            f"{puzzle.get('puzzle_id') or puzzle.get('_id')} r{puzzle.get('rating')} "
            f"themes={sorted(puzzle.get('themes') or [])}"
        )
        print(f"  fen  {board.fen()}")
        print(f"  line {walk(board, puzzle['moves'][1:])}")
        if args.detector == "deflection":
            print(
                f"  CLAIM lure={facts['lure_move']} "
                f"(check={facts['lure_gives_check']}, "
                f"recapture={facts['lure_is_recaptured']}) "
                f"guard={facts['guard_piece']}@{facts['guard_square']}"
                f"->{facts['guard_forced_to']} "
                f"abandons {facts['target_square']}"
                f"({facts['target_piece']}) "
                f"payoff={facts['payoff_move']}@ply{facts['payoff_ply_in_line']} "
                f"kind={facts['payoff_kind']} net={facts['net_material_gain_cp']}"
            )
        else:
            print(
                f"  CLAIM sac={facts['sacrifice_move']} on "
                f"{facts['sacrifice_square']} invest={facts['net_investment_cp']}cp "
                f"attracts {facts['attracted_piece']}@{facts['attracted_from']} "
                f"(king={facts['attracted_is_king']}) "
                f"payoff={facts['payoff_move']}@ply{facts['payoff_ply_in_line']} "
                f"check={facts['payoff_gives_check']} "
                f"kind={facts['payoff_kind']} net={facts['net_material_gain_cp']}"
            )
        shown += 1
        if shown >= args.show:
            break
    print(f"\nshown {shown} fires from {len(samples)} {args.theme} puzzles")


if __name__ == "__main__":
    asyncio.run(main())

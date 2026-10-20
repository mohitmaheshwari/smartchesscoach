"""Does the removal-of-defender prover agree with human labels, at scale?

Before this motif is named to a player, its detection has to be shown correct
against an adjudicator the quality lock accepts. A model is rejected by name,
and a reviewer cannot read thousands of positions -- but `lichess_puzzles`
holds 4,110,434 positions carrying 74 human-curated theme tags, including
`capturingDefender`, which is this motif under Lichess's name. That is human
adjudication, industrialised.

HOW A PUZZLE IS TURNED INTO A DETECTOR CALL
    A Lichess puzzle's `fen` is the position before the first move in `moves`,
    and that first move is the opponent setting the puzzle up. So:

        board  = fen, then push moves[0]      -> the solver is now to move
        best   = moves[1]                     -> the human-verified solution
        pv     = moves[2:]                    -> the rest of the human line
        played = any legal move that is not best

    The prover only requires `played != best` and a cp_loss at or above 100,
    so the choice of `played` cannot manufacture a detection; cp_loss is
    supplied as a constant, which is sound here because a puzzle is a winning
    tactic by construction. Both assumptions are stated in the output so a
    reader can discount them.

WHAT IS MEASURED
    recall     of `capturingDefender` puzzles, how many does the prover find
    precision  of puzzles that are NOT tagged `capturingDefender`, how many
               does it claim anyway

    Reported twice over: for any returned bundle, and for the strict signal
    `verifier.verified`. They are different detectors and conflating them
    would overstate whichever is convenient.

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

from services.attraction_puzzle_proof import build_attraction_proof  # noqa: E402
from services.clearance_puzzle_proof import build_clearance_proof  # noqa: E402
from services.deflection_puzzle_proof import build_deflection_proof  # noqa: E402
from services.interference_puzzle_proof import (  # noqa: E402
    build_interference_proof,
)
from services.removal_defender_puzzle_proof import (  # noqa: E402
    build_removal_defender_proof,
)
from services.xray_attack_puzzle_proof import (  # noqa: E402
    build_xray_attack_proof,
)

# motif -> (prover, the Lichess theme that names the same idea)
#
# The theme is the adjudicator and the pairing is the one judgement in this
# file, so each is spelled out rather than derived from the motif name.
MOTIFS = {
    "clearance": (build_clearance_proof, "clearance"),
    "deflection": (build_deflection_proof, "deflection"),
    "attraction": (build_attraction_proof, "attraction"),
    "xray": (build_xray_attack_proof, "xRayAttack"),
    "interference": (build_interference_proof, "interference"),
    "remove_defender": (build_removal_defender_proof, "capturingDefender"),
}

THEME = "capturingDefender"
CONTROL_THEMES = [
    "clearance", "attraction", "xRayAttack", "interference", "capturingDefender",
    "fork", "pin", "skewer", "backRankMate", "hangingPiece",
    "discoveredAttack", "trappedPiece", "deflection",
]
ASSUMED_CP_LOSS = 300


def themes_of(row) -> set:
    raw = row.get("themes")
    if isinstance(raw, str):
        return set(raw.split())
    return set(raw or ())


PROVER = build_removal_defender_proof


def call_prover(row):
    """Return (bundle_returned, strictly_verified) or None when unusable."""
    moves = row.get("moves")
    if isinstance(moves, str):
        moves = moves.split()
    if not moves or len(moves) < 2:
        return None
    try:
        board = chess.Board(row["fen"])
        board.push(chess.Move.from_uci(moves[0]))
    except (ValueError, KeyError, AssertionError):
        return None
    best = moves[1]
    try:
        best_move = chess.Move.from_uci(best)
    except ValueError:
        return None
    if best_move not in board.legal_moves:
        return None
    played = next(
        (m.uci() for m in board.legal_moves if m != best_move), None
    )
    if played is None:
        return None
    try:
        bundle = PROVER(board, played, best, moves[2:], ASSUMED_CP_LOSS)
    except Exception:
        return None
    if bundle is None:
        return False, False
    return True, bool(getattr(bundle.verifier, "verified", False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1500,
                        help="puzzles per arm")
    parser.add_argument("--rating-max", type=int, default=1500,
                        help="keep to the band the detectors were built for")
    parser.add_argument("--motif", default="remove_defender",
                        choices=sorted(MOTIFS))
    args = parser.parse_args()

    global PROVER, THEME
    PROVER, THEME = MOTIFS[args.motif]

    url = os.environ["MONGO_URL"].replace("host.docker.internal", "localhost")
    db_name = os.environ.get("DB_NAME")
    if not db_name:
        raise SystemExit("DB_NAME must be set explicitly")
    db = MongoClient(url, serverSelectionTimeoutMS=30000,
                     socketTimeoutMS=900000)[db_name]

    # `themes` is an indexed ARRAY, so exact member equality uses the index.
    # A regex here defeats it and the query does not finish over the tunnel.
    band = {"rating": {"$lte": args.rating_max}}
    arms = {
        "tagged (positive)": dict(band, themes=THEME),
        # The control is other TACTICAL themes rather than random puzzles,
        # and deliberately so. Random positions are trivial to reject, which
        # would flatter the precision figure. These are real tactics that are
        # not defender-removal, so a false positive here is the mistake that
        # would actually reach a player: naming the wrong motif on a position
        # where some motif is genuinely present. Index-backed via $in, and any
        # row that also carries capturingDefender is dropped in Python.
        "other tactics (hard control)": dict(
            band, themes={"$in": [t for t in CONTROL_THEMES if t != THEME]}),
    }

    print(f"motif: {args.motif}   adjudicator theme: {THEME}")
    print(f"puzzles rated <= {args.rating_max}; cp_loss supplied as "
          f"{ASSUMED_CP_LOSS}; played move is an arbitrary legal non-best move")
    print()

    summary = {}
    for label, query in arms.items():
        counts = collections.Counter()
        project = {"_id": 0, "fen": 1, "moves": 1, "themes": 1, "rating": 1}
        cursor = db.lichess_puzzles.find(query, project).limit(args.n)
        for row in cursor:
            if THEME in themes_of(row) and "control" in label:
                continue
            outcome = call_prover(row)
            if outcome is None:
                counts["unusable"] += 1
                continue
            returned, verified = outcome
            counts["usable"] += 1
            counts["returned"] += int(returned)
            counts["verified"] += int(verified)
        summary[label] = counts
        usable = max(counts["usable"], 1)
        print(f"{label}")
        print(f"   usable {counts['usable']}   unusable {counts['unusable']}")
        print(f"   bundle returned  {counts['returned']:5d}  "
              f"{100.0 * counts['returned'] / usable:5.1f}%")
        print(f"   strictly verified{counts['verified']:5d}  "
              f"{100.0 * counts['verified'] / usable:5.1f}%")
        print()

    pos = summary["tagged (positive)"]
    neg = summary["other tactics (hard control)"]
    for mode in ("returned", "verified"):
        tp, fp = pos[mode], neg[mode]
        recall = 100.0 * tp / max(pos["usable"], 1)
        precision = 100.0 * tp / max(tp + fp, 1)
        print(f"{mode.upper():9s}  recall {recall:5.1f}%   "
              f"precision {precision:5.1f}%   (tp {tp}, fp {fp})")
    print()
    print("The lock wants >=95% precision with a 95% Wilson lower bound >=85% "
          "for caption grade. Recall matters for plan grade, not caption.")


if __name__ == "__main__":
    main()

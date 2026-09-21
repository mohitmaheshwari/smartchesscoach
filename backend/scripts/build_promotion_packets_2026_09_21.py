"""Build detector promotion packets for review.

WHY THIS EXISTS
---------------
`services/detector_quality._AUTHORIZATIONS` currently grants Plan authority
to exactly one thing. Measured 2026-09-21: of 36 topics users actually miss,
`topic_can_be_planned` returns True for 1. That is why every user's coach
says "piece safety" -- a 606-game player and a 14-game player get the same
sentence, because it is the only sentence the system is permitted to say.

This script produces the evidence a promotion review needs for two blocked
detectors, in the shape of the one packet that passed
(`destination_safety_exact_plan_promotion_2026-09-01.json`):

    reviewed fires -> semantic precision + Wilson lower bound
    independent opportunities -> semantic recall
    adversarial true negatives -> fires must be zero

THIS SCRIPT DOES NOT PROMOTE ANYTHING. It writes a snapshot and prints a
proposed authorization block. A human edits `_AUTHORIZATIONS`. The rule that
no model may approve its own detector claims is the reason this is split in
two, and it is not worked around here.

INDEPENDENCE
------------
The verifiers below are written from the detector's stated CLAIM, not from
its code, and nothing in this file imports `shape_detectors`. If the shipped
detector and this file agree, that is two implementations agreeing. If they
disagree, the disagreement is the finding.

    python backend/scripts/build_promotion_packets_2026_09_21.py
"""

import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

SEED = "20260921-detector-promotion-v1"
SAMPLE_FIRES = 200
SAMPLE_OPPORTUNITIES = 200
ADVERSARIAL_CASES = 60
SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "corpus_snapshots")


def wilson_lower(successes: int, total: int, z: float = 2.326) -> float:
    """Wilson lower bound at ~99% one-sided, as the passing packet used."""
    if total == 0:
        return 0.0
    p = successes / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return round(100.0 * (centre - margin) / denom, 2)


# ── Independent verifier 1: same_piece_better_square ──────────────────────
#
# The claim verified here is the one the CAPTION makes to the player:
#   "it also hits the {piece} on {square}"
# i.e. from the engine's square the piece attacks an enemy non-king piece
# that it does not attack from the square the player chose.
#
# A first draft of this verifier additionally demanded that the extra target
# be UNDEFENDED and that the engine's square attack strictly more pieces by
# count. That measured 34.5% and would have been reported as a detector
# failure. It was not: the detector counts any enemy non-king piece and
# requires only a non-empty set difference, which is exactly what the
# caption says. The stricter draft was testing a claim nobody makes.

def _targets_after(board: chess.Board, move: chess.Move) -> set:
    """Enemy non-king pieces attacked from the move's destination."""
    probe = board.copy(stack=False)
    mover_colour = board.turn
    probe.push(move)
    out = set()
    for sq in probe.attacks(move.to_square):
        target = probe.piece_at(sq)
        if target is None or target.color == mover_colour:
            continue
        if target.piece_type == chess.KING:
            continue
        out.add(sq)
    return out


def verify_same_piece_better_square(fen: str, played_san: str, best_san: str):
    try:
        board = chess.Board(fen)
        um = board.parse_san(played_san)
        bm = board.parse_san(best_san)
    except Exception as exc:
        return False, f"unparseable: {exc}"
    if um.from_square != bm.from_square:
        return False, "not the same piece moving"
    if um.to_square == bm.to_square:
        return False, "same destination"
    if board.piece_at(um.from_square) is None:
        return False, "no piece on origin"
    extra = _targets_after(board, bm) - _targets_after(board, um)
    if not extra:
        return False, "engine square hits nothing the played square does not"
    probe = board.copy(stack=False)
    probe.push(bm)
    names = ", ".join(
        f"{chess.piece_name(probe.piece_at(sq).piece_type)} on {chess.square_name(sq)}"
        for sq in sorted(extra) if probe.piece_at(sq) is not None
    )
    return True, f"engine square also hits: {names}"


# ── Independent verifier 2: endgame_loose_pawn_attack ─────────────────────
#
# CLAIM: in an endgame (<= 12 non-pawn pieces on the board), the engine's
# best move is played by a non-pawn piece, and it either captures an
# undefended enemy pawn or lands on a square attacking one.

def verify_endgame_loose_pawn(fen: str, played_san: str, best_san: str):
    try:
        board = chess.Board(fen)
        bm = board.parse_san(best_san)
    except Exception as exc:
        return False, f"unparseable: {exc}"
    non_pawn = sum(
        1 for sq in chess.SQUARES
        if (p := board.piece_at(sq)) is not None and p.piece_type != chess.PAWN
    )
    if non_pawn > 12:
        return False, f"not an endgame ({non_pawn} non-pawn pieces)"
    mover = board.piece_at(bm.from_square)
    if mover is None or mover.piece_type == chess.PAWN:
        return False, "best move is not by a non-pawn piece"

    captured = board.piece_at(bm.to_square)
    if (captured is not None and captured.color != mover.color
            and captured.piece_type == chess.PAWN
            and not board.attackers(captured.color, bm.to_square)):
        return True, (
            f"{chess.piece_name(mover.piece_type)} captures undefended pawn on "
            f"{chess.square_name(bm.to_square)}"
        )

    probe = board.copy(stack=False)
    try:
        probe.push(bm)
    except Exception as exc:
        return False, f"illegal best move: {exc}"
    them = probe.turn
    for sq in probe.attacks(bm.to_square):
        target = probe.piece_at(sq)
        if target is None or target.color != them or target.piece_type != chess.PAWN:
            continue
        if probe.attackers(them, sq):
            continue
        return True, (
            f"{chess.piece_name(mover.piece_type)} lands attacking undefended pawn on "
            f"{chess.square_name(sq)}"
        )
    return False, "no undefended enemy pawn captured or attacked"


DETECTORS = {
    "same_piece_better_square": {
        "verifier": verify_same_piece_better_square,
        "claim": (
            "The player and the engine move the same piece from the same "
            "square to different squares, and from the engine's square that "
            "piece attacks at least one enemy non-king piece it does not "
            "attack from the square the player chose. This is the claim the "
            "caption makes: 'it also hits the {piece} on {square}'."
        ),
        "quality_id": "gap:piece_activity:same_piece_better_square",
    },
    "endgame_loose_pawn_attack": {
        "verifier": verify_endgame_loose_pawn,
        "claim": (
            "In an endgame (at most 12 non-pawn pieces), the engine's best "
            "move is by a non-pawn piece that either captures an undefended "
            "enemy pawn or lands on a square attacking one."
        ),
        "quality_id": "gap:endgame_technique:endgame_loose_pawn_attack",
    },
}


async def collect(db, concept: str, rng):
    """Every stored fire for a concept, with the fields a verifier needs."""
    rows = []
    cursor = db.user_pattern_events.find(
        {"outcome": "miss",
         "$or": [{"concept_id": concept}, {"pattern_id": concept}],
         "fen_before": {"$nin": [None, ""]},
         "best_move_san": {"$nin": [None, ""]},
         "move_san": {"$nin": [None, ""]}},
        {"_id": 0, "fen_before": 1, "move_san": 1, "best_move_san": 1,
         "game_id": 1, "move_number": 1, "user_id": 1, "cp_loss": 1},
    )
    async for row in cursor:
        rows.append(row)
    return rows


async def independent_opportunities(db, concept: str, verifier, limit: int, rng):
    """Positions the CLAIM is true of, found without asking the detector.

    Scans stored mistakes of any concept, applies the independent verifier,
    and records whether production actually fired this concept there. That
    is the recall denominator: the detector does not get to define what it
    should have caught.
    """
    hits, scanned = [], 0
    cursor = db.user_pattern_events.find(
        {"outcome": "miss",
         "fen_before": {"$nin": [None, ""]},
         "best_move_san": {"$nin": [None, ""]},
         "move_san": {"$nin": [None, ""]}},
        {"_id": 0, "fen_before": 1, "move_san": 1, "best_move_san": 1,
         "game_id": 1, "move_number": 1, "concept_id": 1, "pattern_id": 1},
    )
    async for row in cursor:
        scanned += 1
        ok, _ = verifier(row["fen_before"], row["move_san"], row["best_move_san"])
        if ok:
            hits.append(row)
        if len(hits) >= limit * 6:
            break
    return hits, scanned


async def true_negative_cases(db, concept: str, verifier, rng, want=ADVERSARIAL_CASES):
    """Positions where the claim is FALSE. The detector must be silent there.

    An earlier draft built these by swapping the engine move for another
    legal move by the same piece and asking whether the verifier still
    fired. 18 of 60 did -- which is not a failure, because a piece often
    hits something new from several squares. That construction could not
    produce a true negative, so it could not test anything.

    These are real analysed positions the verifier rejects. If production
    recorded this concept there anyway, the detector fired on a position
    where its own claim does not hold.
    """
    cases, checked = [], 0
    cursor = db.user_pattern_events.find(
        {"outcome": "miss",
         "fen_before": {"$nin": [None, ""]},
         "best_move_san": {"$nin": [None, ""]},
         "move_san": {"$nin": [None, ""]}},
        {"_id": 0, "fen_before": 1, "move_san": 1, "best_move_san": 1,
         "game_id": 1, "move_number": 1, "concept_id": 1, "pattern_id": 1},
    )
    async for row in cursor:
        if len(cases) >= want:
            break
        checked += 1
        ok, why = verifier(row["fen_before"], row["move_san"], row["best_move_san"])
        if ok:
            continue
        fired = (row.get("concept_id") or row.get("pattern_id")) == concept
        cases.append({
            "game_id": row.get("game_id"),
            "move_number": row.get("move_number"),
            "claim_holds": False,
            "reason": why,
            "detector_fired_anyway": bool(fired),
        })
    return cases, checked


async def build(db, concept: str, spec: dict, rng) -> dict:
    verifier = spec["verifier"]
    fires = await collect(db, concept, rng)

    sample = fires if len(fires) <= SAMPLE_FIRES else rng.sample(fires, SAMPLE_FIRES)
    true_fires, failures = 0, []
    for row in sample:
        ok, why = verifier(row["fen_before"], row["move_san"], row["best_move_san"])
        if ok:
            true_fires += 1
        elif len(failures) < 10:
            failures.append({
                "game_id": row.get("game_id"),
                "move_number": row.get("move_number"),
                "played": row.get("move_san"),
                "best": row.get("best_move_san"),
                "reason": why,
            })

    opps, scanned = await independent_opportunities(db, concept, verifier, SAMPLE_OPPORTUNITIES, rng)
    opp_sample = opps if len(opps) <= SAMPLE_OPPORTUNITIES else rng.sample(opps, SAMPLE_OPPORTUNITIES)
    opp_hits = sum(
        1 for o in opp_sample
        if (o.get("concept_id") or o.get("pattern_id")) == concept
    )

    adversarial, tn_checked = await true_negative_cases(db, concept, verifier, rng)
    adversarial_fires = sum(1 for a in adversarial if a["detector_fired_anyway"])

    precision = round(100.0 * true_fires / len(sample), 2) if sample else 0.0
    recall = round(100.0 * opp_hits / len(opp_sample), 2) if opp_sample else 0.0
    wl = wilson_lower(true_fires, len(sample))
    wl_95 = wilson_lower(true_fires, len(sample), z=1.96)

    return {
        "audit": f"{concept}_plan_promotion",
        "candidate_claim": spec["claim"],
        "quality_id": spec["quality_id"],
        "read_only": True,
        "production_data_exported": False,
        "stockfish_rerun": False,
        "verifier_independence": (
            "The verifier in backend/scripts/build_promotion_packets_2026_09_21.py "
            "is written from the stated claim and does not import "
            "services/shape_detectors.py. Agreement is two implementations "
            "agreeing; disagreement is the finding."
        ),
        "population": {
            "stored_fires_total": len(fires),
            "distinct_players": len({r.get("user_id") for r in fires}),
            "distinct_games": len({r.get("game_id") for r in fires}),
            "observations_scanned_for_opportunities": scanned,
            "independent_positive_opportunities_found": len(opps),
        },
        "review": {
            "reviewed_fires": len(sample),
            "true_fires": true_fires,
            "semantic_precision_pct": precision,
            "wilson_lower_pct": wl,
            "wilson_lower_pct_z1_96": wl_95,
            "wilson_note": (
                "The packet that passed on 2026-09-01 reports 98.12 for 200/200, "
                "which is z=1.96. wilson_lower_pct here uses a stricter z=2.326; "
                "wilson_lower_pct_z1_96 is the like-for-like comparison."
            ),
            "reviewed_opportunities": len(opp_sample),
            "opportunity_hits": opp_hits,
            "semantic_recall_pct": recall,
            "adversarial_cases": len(adversarial),
            "candidate_fires_in_true_negatives": adversarial_fires,
            "distinct_review_games": len({r.get("game_id") for r in sample}),
            "distinct_review_players": len({r.get("user_id") for r in sample}),
        },
        "precision_failures_sample": failures,
        "adversarial_sample": adversarial[:10],
        "recall_interpretation": (
            "Recall is a LOWER BOUND on the detector's quality, not an upper "
            "bound on its coverage. The independent verifier models the "
            "caption's claim only; the shipped detector additionally requires "
            "the moved piece to SURVIVE on the engine's square "
            "(_mover_dies_on_destination). Positions where the claim holds but "
            "the piece is immediately lost satisfy the verifier and are "
            "correctly declined by the detector, and they count against recall "
            "here. Checked separately: 27.5% of analysed moves already carry "
            "more than one concept (max 8), so this figure is not depressed by "
            "single-label storage."
        ),
        "limitations": [
            "chess.Board.attackers() is PSEUDO-legal: a pinned defender still "
            "counts as defending, so 'undefended' is conservative. This can "
            "suppress real fires (costing recall) but does not invent them.",
            "Recall is measured over stored mistakes only, so opportunities in "
            "positions never analysed are out of scope.",
            "No human has eyeballed these positions; this is machine "
            "verification of a board claim, and it is not a substitute for the "
            "reviewed judgement the promotion requires.",
        ],
        "packet": {
            "seed": SEED,
            "fingerprint_sha256": hashlib.sha256(
                (SEED + concept + str(len(fires))).encode("utf-8")
            ).hexdigest(),
            "case_details_retained_on_database_host": True,
        },
        "plan_promotion_gate_passed": None,   # a human decides this
    }


async def main() -> int:
    rng = random.Random(SEED)
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    for concept, spec in DETECTORS.items():
        print(f"\n{'=' * 68}\n{concept}\n{'=' * 68}")
        packet = await build(db, concept, spec, rng)
        pop, rev = packet["population"], packet["review"]
        print(f"  stored fires          : {pop['stored_fires_total']:,} "
              f"across {pop['distinct_players']} players / {pop['distinct_games']} games")
        print(f"  reviewed fires        : {rev['reviewed_fires']}")
        print(f"  semantic precision    : {rev['semantic_precision_pct']}%  "
              f"(Wilson lower {rev['wilson_lower_pct']}%)")
        print(f"  independent opps found: {pop['independent_positive_opportunities_found']:,} "
              f"from {pop['observations_scanned_for_opportunities']:,} scanned")
        print(f"  semantic recall       : {rev['semantic_recall_pct']}%  "
              f"({rev['opportunity_hits']}/{rev['reviewed_opportunities']})")
        print(f"  adversarial fires     : {rev['candidate_fires_in_true_negatives']} "
              f"of {rev['adversarial_cases']}  (must be 0)")
        if packet["precision_failures_sample"]:
            print("  precision failures (first few):")
            for f in packet["precision_failures_sample"][:3]:
                print(f"    {f['game_id']} m{f['move_number']} "
                      f"{f['played']} vs {f['best']}: {f['reason']}")

        packet["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
        packet["schema_version"] = "detector_plan_promotion.v1"
        out = os.path.join(SNAPSHOT_DIR, f"{concept}_plan_promotion_2026-09-21.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(packet, fh, indent=2, default=str)
        print(f"  snapshot -> backend/data/corpus_snapshots/{os.path.basename(out)}")

    print("\nNothing was promoted. A human edits _AUTHORIZATIONS.")
    return 0


if __name__ == "__main__":
    argparse.ArgumentParser().parse_args()
    raise SystemExit(asyncio.run(main()))

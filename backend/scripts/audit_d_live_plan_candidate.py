"""Read-only bake-off for a Plan-grade destination-safety detector.

The existing D_live fact proves that the moved piece is legally capturable on
its destination and that the move crossed the SEE and stored Stockfish-loss
floors.  This audit tests a narrower, more explainable candidate: the stored
Stockfish continuation must begin by capturing that exact moved piece.

No engine is run and no collection is mutated.  The output contains aggregate
counts plus a deterministic, de-identified review packet.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from typing import Any, Dict, Iterable, Optional

import chess
from pymongo import MongoClient


FACT_VERSION = "piece_safety.d_live.v1"
PACKET_VERSION = "destination_safety_plan_candidate.v1"
PACKET_SEED = "20260901-destination-safety-plan-v1"
SEE_FLOOR_CP = 150
CP_LOSS_FLOOR = 150


def _stable_ref(game_id: str, ply: Any) -> str:
    raw = f"{game_id}:{ply}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def _stable_rank(label: str, row: Dict[str, Any]) -> str:
    raw = "|".join(
        (
            PACKET_SEED,
            label,
            str(row.get("case_ref") or ""),
        )
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _stable_unit(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:16]


def _cp_bucket(value: Any) -> str:
    try:
        cp = int(float(value))
    except (TypeError, ValueError):
        return "unknown"
    if cp < 200:
        return "150_199"
    if cp < 300:
        return "200_299"
    if cp < 500:
        return "300_499"
    return "500_plus"


def _matching_evaluation(rows: Iterable[Dict[str, Any]], observation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    move_number = observation.get("move_number")
    move_san = observation.get("move_san")
    move_uci = observation.get("move_uci")
    candidates = [row for row in rows if row.get("move_number") == move_number]
    exact_uci = [row for row in candidates if row.get("move_uci") == move_uci]
    exact_san = [row for row in candidates if row.get("move") == move_san]
    pool = exact_uci or exact_san or candidates
    user_rows = [row for row in pool if not row.get("is_opponent_move")]
    return (user_rows or pool or [None])[0]


def _first_reply_captures_destination(evaluation: Dict[str, Any]) -> tuple[bool, str]:
    fen_after = evaluation.get("fen_after")
    move_uci = str(evaluation.get("move_uci") or "")
    pv = evaluation.get("pv_after_played") or []
    if not fen_after:
        return False, "missing_fen_after"
    if len(move_uci) < 4:
        return False, "missing_move_uci"
    if not pv:
        return False, "missing_pv"
    try:
        destination = chess.parse_square(move_uci[2:4])
        board = chess.Board(fen_after)
        moved_piece = board.piece_at(destination)
        if moved_piece is None:
            return False, "moved_piece_not_on_destination"
        reply = board.parse_san(str(pv[0]))
    except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError):
        return False, "invalid_position_or_pv"
    if not board.is_capture(reply):
        return False, "first_reply_not_capture"
    if reply.to_square != destination:
        return False, "first_reply_captures_other_square"
    return True, "exact_first_reply_capture"


def _case_record(
    observation: Dict[str, Any],
    evaluation: Dict[str, Any],
    fact: Dict[str, Any],
    *,
    candidate_fires: bool,
    candidate_reason: str,
) -> Dict[str, Any]:
    game_id = str(observation.get("game_id") or "")
    return {
        "case_ref": _stable_ref(game_id, observation.get("ply")),
        "game_unit": _stable_unit(game_id),
        "player_unit": _stable_unit(observation.get("user_id")),
        "move_number": observation.get("move_number"),
        "move_san": observation.get("move_san"),
        "move_uci": evaluation.get("move_uci") or observation.get("move_uci"),
        "best_move": evaluation.get("best_move"),
        "fen_before": evaluation.get("fen_before") or observation.get("fen_before"),
        "fen_after": evaluation.get("fen_after"),
        "pv_after_played": list(evaluation.get("pv_after_played") or [])[:4],
        "pv_after_best": list(evaluation.get("pv_after_best") or [])[:4],
        "moved_piece": fact.get("moved_piece"),
        "destination_see_cp": fact.get("destination_see_cp"),
        "stockfish_cp_loss": fact.get("stockfish_cp_loss"),
        "d_live_outcome": fact.get("outcome"),
        "candidate_fires": candidate_fires,
        "candidate_reason": candidate_reason,
        "is_sacrifice": evaluation.get("is_sacrifice"),
    }


def _take_stable(label: str, rows: list[Dict[str, Any]], size: int) -> list[Dict[str, Any]]:
    return sorted(rows, key=lambda row: _stable_rank(label, row))[: max(0, size)]


def build_report(
    db,
    *,
    packet_size: int,
    opportunity_size: int,
    negative_size: int,
    adversarial_size: int,
) -> Dict[str, Any]:
    # v16 is the first SEE-backed schema. v17 persists the additive D_live
    # fact; older v16 rows can be deterministically re-derived from their
    # already-stored FEN/move/cp_loss without re-running Stockfish.
    query = {"schema_version": {"$gte": 16}}
    projection = {
        "_id": 0,
        "user_id": 1,
        "game_id": 1,
        "ply": 1,
        "move_number": 1,
        "move_san": 1,
        "move_uci": 1,
        "fen_before": 1,
        "cp_loss": 1,
        "schema_version": 1,
        "piece_safety_decision": 1,
    }
    observations = list(db.move_observations.find(query, projection))
    from services.move_observation_deriver import _derive_d_live_fact

    analysis_cache: Dict[str, list[Dict[str, Any]]] = {}
    reasons: Counter[str] = Counter()
    pieces: Counter[str] = Counter()
    cp_buckets: Counter[str] = Counter()
    candidates: list[Dict[str, Any]] = []
    opportunities: list[Dict[str, Any]] = []
    non_opportunities: list[Dict[str, Any]] = []
    decision_count = 0
    miss_count = 0
    candidate_games: set[str] = set()
    candidate_users: set[str] = set()

    for observation in observations:
        fact = observation.get("piece_safety_decision") or {}
        if not (
            fact.get("version") == FACT_VERSION
            and fact.get("derivation_status") == "ok"
        ):
            fact = _derive_d_live_fact(observation)
        if not fact.get("eligible"):
            continue
        decision_count += 1
        is_miss = fact.get("outcome") == "miss"
        if is_miss:
            miss_count += 1

        game_id = str(observation.get("game_id") or "")
        if not game_id:
            reasons["missing_game_id"] += 1
            continue
        if game_id not in analysis_cache:
            analysis = db.game_analyses.find_one(
                {"game_id": game_id},
                {"_id": 0, "stockfish_analysis.move_evaluations": 1},
            ) or {}
            analysis_cache[game_id] = (
                (analysis.get("stockfish_analysis") or {}).get("move_evaluations")
                or []
            )
        evaluation = _matching_evaluation(analysis_cache[game_id], observation)
        if evaluation is None:
            reasons["missing_matching_evaluation"] += 1
            continue
        accepted, reason = _first_reply_captures_destination(evaluation)
        if is_miss:
            reasons[reason] += 1
        record = _case_record(
            observation,
            evaluation,
            fact,
            candidate_fires=bool(is_miss and accepted),
            candidate_reason=(reason if is_miss else "d_live_non_miss"),
        )
        if not is_miss:
            # These positions still offered a legal destination capture, but
            # the independent D_live loss gates say the move was not a miss.
            # They are the strongest non-opportunity controls for this claim.
            non_opportunities.append(record)
            continue
        opportunities.append(record)
        if not accepted:
            continue

        piece = str(fact.get("moved_piece") or "unknown")
        pieces[piece] += 1
        cp_buckets[_cp_bucket(fact.get("stockfish_cp_loss"))] += 1
        candidates.append(record)
        candidate_games.add(game_id)
        if observation.get("user_id"):
            candidate_users.add(str(observation["user_id"]))

    packet = _take_stable("positive", candidates, packet_size)
    opportunity_packet = _take_stable("opportunity", opportunities, opportunity_size)
    negative_packet = _take_stable("negative", non_opportunities, negative_size)
    # Near-threshold and explicitly sacrifice-marked fires are where a loose
    # detector is most likely to overclaim. Keep a deterministic edge packet.
    adversarial_pool = sorted(
        candidates,
        key=lambda row: (
            0 if row.get("is_sacrifice") else 1,
            abs(float(row.get("destination_see_cp") or 0) - SEE_FLOOR_CP),
            abs(float(row.get("stockfish_cp_loss") or 0) - CP_LOSS_FLOOR),
            _stable_rank("adversarial", row),
        ),
    )
    adversarial_packet = adversarial_pool[: max(0, adversarial_size)]
    accepted_count = len(candidates)
    return {
        "audit_version": PACKET_VERSION,
        "candidate_claim": (
            "After the player's move, Stockfish's stored first reply captures "
            "the exact moved piece on its destination; D_live also records a "
            "destination SEE loss and at least 150cp stored move loss."
        ),
        "counts": {
            "see_backed_observations_scanned": len(observations),
            "d_live_decisions": decision_count,
            "d_live_misses": miss_count,
            "candidate_fires": accepted_count,
            "candidate_recall_within_d_live_misses_pct": round(
                accepted_count / max(miss_count, 1) * 100, 2
            ),
            "distinct_games": len(candidate_games),
            "distinct_users": len(candidate_users),
            "review_packet": len(packet),
            "opportunity_packet": len(opportunity_packet),
            "non_opportunity_packet": len(negative_packet),
            "adversarial_packet": len(adversarial_packet),
        },
        "rejection_reasons": dict(sorted(reasons.items())),
        "candidate_distribution": {
            "moved_piece": dict(sorted(pieces.items())),
            "stockfish_cp_loss": dict(sorted(cp_buckets.items())),
        },
        "packet_seed": PACKET_SEED,
        "thresholds": {
            "destination_see_floor_cp": SEE_FLOOR_CP,
            "stockfish_cp_loss_floor": CP_LOSS_FLOOR,
        },
        "review_packet": packet,
        "opportunities": opportunity_packet,
        "non_opportunities": negative_packet,
        "adversarial": adversarial_packet,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-size", type=int, default=200)
    parser.add_argument("--opportunity-size", type=int, default=200)
    parser.add_argument("--negative-size", type=int, default=60)
    parser.add_argument("--adversarial-size", type=int, default=60)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    client = MongoClient(os.environ["MONGO_URL"])
    try:
        db = client[os.environ.get("DB_NAME", "chess_coach")]
        report = build_report(
            db,
            packet_size=args.packet_size,
            opportunity_size=args.opportunity_size,
            negative_size=args.negative_size,
            adversarial_size=args.adversarial_size,
        )
        if args.summary_only:
            for key in (
                "review_packet",
                "opportunities",
                "non_opportunities",
                "adversarial",
            ):
                report.pop(key, None)
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

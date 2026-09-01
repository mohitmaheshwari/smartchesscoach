"""Read-only independent promotion audit for destination-safety planning.

The production candidate is intentionally narrow: a stored D_live miss whose
stored Stockfish continuation starts by capturing the exact piece that moved.
This audit independently rebuilds the board, explores every legal capture
sequence on the destination square, and compares that semantic truth with the
candidate. It never runs Stockfish and never writes to Mongo.

Only aggregate results and a cryptographic packet fingerprint are printed; no
FEN, game id, player id, move, or stored continuation leaves the database host.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from typing import Any, Dict, Iterable, Optional

import chess
from pymongo import MongoClient

from services.destination_safety_detector import derive_destination_safety_exact


SEED = "20260901-destination-safety-plan-v1"
SEE_FLOOR_CP = 150
CP_LOSS_FLOOR = 150
REVIEW_FIRES = 200
REVIEW_OPPORTUNITIES = 200
REVIEW_NEGATIVES = 60
REVIEW_ADVERSARIAL = 60
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def _safe_cp(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _captured_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return PIECE_VALUES[chess.PAWN]
    captured = board.piece_at(move.to_square)
    return PIECE_VALUES[captured.piece_type] if captured else 0


def _exact_exchange_gain(board: chess.Board, target: int) -> int:
    """Independent minimax over every legal capture on one target square."""
    best = 0
    for move in list(board.legal_moves):
        if not board.is_capture(move) or move.to_square != target:
            continue
        captured = _captured_value(board, move)
        board.push(move)
        continuation = _exact_exchange_gain(board, target)
        board.pop()
        best = max(best, captured - continuation)
    return max(0, best)


def _matching_evaluation(
    rows: Iterable[Dict[str, Any]], observation: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    move_number = observation.get("move_number")
    candidates = [row for row in rows if row.get("move_number") == move_number]
    exact_uci = [
        row for row in candidates
        if row.get("move_uci") == observation.get("move_uci")
    ]
    exact_san = [
        row for row in candidates
        if row.get("move") == observation.get("move_san")
    ]
    pool = exact_uci or exact_san or candidates
    user_rows = [row for row in pool if not row.get("is_opponent_move")]
    return (user_rows or pool or [None])[0]


def _independent_truth(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    fen = evaluation.get("fen_before")
    uci = str(evaluation.get("move_uci") or "")
    result = {
        "valid": False,
        "opportunity": False,
        "miss": False,
        "exact_first_reply_capture": False,
        "see_cp": 0,
        "excluded_reason": None,
    }
    if not fen or len(uci) < 4:
        return result
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            return result
        piece = board.piece_at(move.from_square)
        if piece is None or piece.piece_type not in (
            chess.KNIGHT,
            chess.BISHOP,
            chess.ROOK,
            chess.QUEEN,
        ):
            return result
        board.push(move)
        destination = move.to_square
        captures = [
            reply for reply in board.legal_moves
            if board.is_capture(reply) and reply.to_square == destination
        ]
        if any(reply.promotion is not None for reply in captures):
            result["valid"] = False
            result["excluded_reason"] = "promotion_exchange_not_in_packet"
            return result
        result["valid"] = True
        result["opportunity"] = bool(captures)
        if not captures:
            return result
        result["see_cp"] = _exact_exchange_gain(board, destination)
        result["miss"] = (
            result["see_cp"] >= SEE_FLOOR_CP
            and _safe_cp(evaluation.get("cp_loss")) >= CP_LOSS_FLOOR
        )
        pv = evaluation.get("pv_after_played") or []
        if pv:
            reply = board.parse_san(str(pv[0]))
            result["exact_first_reply_capture"] = (
                board.is_capture(reply) and reply.to_square == destination
            )
        return result
    except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError):
        return result


def _case_ref(game_id: Any, ply: Any) -> str:
    return hashlib.sha256(f"{game_id}:{ply}".encode("utf-8")).hexdigest()[:20]


def _rank(label: str, row: Dict[str, Any]) -> str:
    return hashlib.sha256(
        f"{SEED}|{label}|{row['case_ref']}".encode("utf-8")
    ).hexdigest()


def _stable_sample(
    label: str, rows: list[Dict[str, Any]], size: int, *, one_per_game: bool = True
) -> list[Dict[str, Any]]:
    selected: list[Dict[str, Any]] = []
    seen_games: set[str] = set()
    ordered = sorted(rows, key=lambda row: _rank(label, row))
    for row in ordered:
        game = row["game_unit"]
        if one_per_game and game in seen_games:
            continue
        selected.append(row)
        seen_games.add(game)
        if len(selected) >= size:
            return selected
    if one_per_game and len(selected) < size:
        selected_refs = {row["case_ref"] for row in selected}
        for row in ordered:
            if row["case_ref"] in selected_refs:
                continue
            selected.append(row)
            if len(selected) >= size:
                break
    return selected


def _wilson_lower(successes: int, total: int) -> float:
    if total <= 0:
        return 0.0
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator


def _packet_fingerprint(groups: Dict[str, list[Dict[str, Any]]]) -> str:
    manifest = {
        label: [
            {
                "case_ref": row["case_ref"],
                "candidate": row["candidate"],
                "semantic_truth": row["semantic_truth"],
            }
            for row in cases
        ]
        for label, cases in sorted(groups.items())
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_report(db) -> Dict[str, Any]:
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
        "piece_safety_decision": 1,
    }
    observations = list(
        db.move_observations.find({"schema_version": {"$gte": 16}}, projection)
    )
    analysis_cache: Dict[str, list[Dict[str, Any]]] = {}
    rows: list[Dict[str, Any]] = []
    coverage: Counter[str] = Counter()

    for observation in observations:
        game_id = str(observation.get("game_id") or "")
        if not game_id:
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
            coverage["missing_evaluation"] += 1
            continue
        candidate_fact = derive_destination_safety_exact(evaluation)
        candidate = bool(candidate_fact.get("fires"))
        independent = _independent_truth(evaluation)
        if not independent["valid"]:
            coverage[
                independent.get("excluded_reason")
                or "invalid_independent_position"
            ] += 1
            continue
        semantic_truth = bool(
            independent["miss"] and independent["exact_first_reply_capture"]
        )
        case_ref = _case_ref(game_id, observation.get("ply"))
        rows.append({
            "case_ref": case_ref,
            "game_unit": hashlib.sha256(game_id.encode("utf-8")).hexdigest()[:16],
            "player_unit": hashlib.sha256(
                str(observation.get("user_id") or "").encode("utf-8")
            ).hexdigest()[:16],
            "candidate": bool(candidate),
            "semantic_truth": semantic_truth,
            "independent_opportunity": bool(independent["miss"]),
            "independent_non_opportunity": bool(
                independent["opportunity"] and not independent["miss"]
            ),
            "see_cp": independent["see_cp"],
            "cp_loss": _safe_cp(evaluation.get("cp_loss")),
            "is_sacrifice": bool(evaluation.get("is_sacrifice")),
        })

    fires = [row for row in rows if row["candidate"]]
    opportunities = [row for row in rows if row["independent_opportunity"]]
    negatives = [row for row in rows if row["independent_non_opportunity"]]
    positive_packet = _stable_sample("positive", fires, REVIEW_FIRES)
    opportunity_packet = _stable_sample(
        "opportunity", opportunities, REVIEW_OPPORTUNITIES
    )
    negative_packet = _stable_sample("negative", negatives, REVIEW_NEGATIVES)
    adversarial_pool = sorted(
        fires,
        key=lambda row: (
            0 if row["is_sacrifice"] else 1,
            abs(row["see_cp"] - SEE_FLOOR_CP),
            abs(row["cp_loss"] - CP_LOSS_FLOOR),
            _rank("adversarial", row),
        ),
    )
    adversarial_packet = _stable_sample(
        "adversarial", adversarial_pool, REVIEW_ADVERSARIAL
    )
    groups = {
        "reviewed_fires": positive_packet,
        "opportunities": opportunity_packet,
        "non_opportunities": negative_packet,
        "adversarial": adversarial_packet,
    }

    true_fires = sum(row["semantic_truth"] for row in positive_packet)
    opportunity_hits = sum(row["candidate"] for row in opportunity_packet)
    false_negative_fires = sum(row["candidate"] for row in negative_packet)
    adversarial_errors = sum(not row["semantic_truth"] for row in adversarial_packet)
    precision = true_fires / max(len(positive_packet), 1)
    recall = opportunity_hits / max(len(opportunity_packet), 1)
    distinct_review_games = len({row["game_unit"] for row in positive_packet})
    distinct_review_players = len({row["player_unit"] for row in positive_packet})
    promotion_passed = all((
        len(positive_packet) >= REVIEW_FIRES,
        precision >= 0.95,
        _wilson_lower(true_fires, len(positive_packet)) >= 0.90,
        len(opportunity_packet) >= 100,
        recall >= 0.60,
        len(negative_packet) >= 30,
        false_negative_fires == 0,
        adversarial_errors == 0,
        distinct_review_games == len(positive_packet),
    ))
    return {
        "audit": "destination_safety_exact_plan_promotion",
        "read_only": True,
        "stockfish_rerun": False,
        "production_data_exported": False,
        "candidate_claim": (
            "The player moved a non-pawn piece where the opponent can take it "
            "immediately for a verified exchange loss; the stored Stockfish "
            "continuation starts with that exact capture."
        ),
        "thresholds": {
            "semantic_precision_pct": 95.0,
            "wilson_lower_pct": 90.0,
            "reviewed_fires": 200,
            "semantic_recall_pct": 60.0,
            "reviewed_opportunities": 100,
            "true_negatives": 30,
            "critical_adversarial_errors": 0,
        },
        "population": {
            "observations_scanned": len(observations),
            "valid_positions": len(rows),
            "candidate_fires": len(fires),
            "independent_positive_opportunities": len(opportunities),
            "independent_non_opportunities": len(negatives),
            "coverage_notes": dict(coverage),
        },
        "review": {
            "reviewed_fires": len(positive_packet),
            "true_fires": true_fires,
            "semantic_precision_pct": round(precision * 100, 2),
            "wilson_lower_pct": round(
                _wilson_lower(true_fires, len(positive_packet)) * 100, 2
            ),
            "reviewed_opportunities": len(opportunity_packet),
            "opportunity_hits": opportunity_hits,
            "semantic_recall_pct": round(recall * 100, 2),
            "true_negative_cases": len(negative_packet),
            "candidate_fires_in_true_negatives": false_negative_fires,
            "adversarial_cases": len(adversarial_packet),
            "critical_adversarial_errors": adversarial_errors,
            "distinct_review_games": distinct_review_games,
            "distinct_review_players": distinct_review_players,
        },
        "packet": {
            "seed": SEED,
            "fingerprint_sha256": _packet_fingerprint(groups),
            "case_details_retained_on_database_host": True,
        },
        "plan_promotion_gate_passed": promotion_passed,
    }


def main() -> int:
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=10_000)
    try:
        report = build_report(client[os.environ.get("DB_NAME", "chess_coach")])
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["plan_promotion_gate_passed"] else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

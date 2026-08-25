"""Read-only implementation-agreement audit for the D_live SEE rule.

The production candidate uses the existing SEE implementation. This audit checks
that SEE result against a separately implemented exhaustive capture tree on a
fixed, deterministic, stratified sample. Both labels reuse the same stored
cp_loss gate, so this proves implementation agreement, not external semantic
precision/recall. It never writes to Mongo and is not imported by runtime code.

Pre-registered sample (seed 20260825): 100 positions from each of four strata:
candidate miss, compensated sacrifice, other cp-loss, and clean exchange.

Acceptance rule, fixed before the query runs:
  * candidate-miss-stratum agreement >= 98%; and
  * agreement >= 95% in every stratum.

Run inside the backend container:
    python scripts/audit_d_live_outcome_validation.py
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

import chess
from pymongo import MongoClient

from coach_play.coach_blunder_guard import see_gain


SCHEMA_VERSION = 16
SEE_FLOOR_CP = 150
CORROBORATING_CP_LOSS = 150
SAMPLE_PER_STRATUM = 100
SAMPLE_SEED = "20260825"
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
STRATA = (
    "candidate_miss",
    "compensated_sacrifice",
    "other_cp_loss",
    "clean_exchange",
)


def _safe_cp(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _pct(numerator: int, denominator: int) -> Optional[float]:
    if not denominator:
        return None
    return round(numerator * 100.0 / denominator, 2)


def _iter_analyses(db, game_ids: Iterable[str]):
    projection = {
        "_id": 0,
        "game_id": 1,
        "stockfish_analysis.move_evaluations": 1,
    }
    ids = list(game_ids)
    for start in range(0, len(ids), 500):
        batch = ids[start : start + 500]
        yield from db.game_analyses.find({"game_id": {"$in": batch}}, projection)


def _captured_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return PIECE_VALUES[chess.PAWN]
    captured = board.piece_at(move.to_square)
    return PIECE_VALUES[captured.piece_type] if captured else 0


def _exact_exchange_gain(board: chess.Board, target: int) -> int:
    """Exact minimax gain from optional legal captures on one target square.

    Unlike the production SEE's least-valuable-attacker recursion, this explores
    every legal capturing choice at every ply. Returning zero models declining a
    losing continuation.
    """
    best = 0
    replies = [
        move
        for move in board.legal_moves
        if board.is_capture(move) and move.to_square == target
    ]
    for move in replies:
        captured = _captured_value(board, move)
        board.push(move)
        continuation = _exact_exchange_gain(board, target)
        board.pop()
        best = max(best, captured - continuation)
    return max(0, best)


def _candidate_see_gain(board_after: chess.Board, target: int) -> Tuple[int, int]:
    captures = [
        move
        for move in board_after.legal_moves
        if board_after.is_capture(move) and move.to_square == target
    ]
    return max((see_gain(board_after, move) for move in captures), default=0), len(
        captures
    )


def _stratum(candidate_see: int, cp_loss: float) -> str:
    see_losing = candidate_see >= SEE_FLOOR_CP
    eval_losing = cp_loss >= CORROBORATING_CP_LOSS
    if see_losing and eval_losing:
        return "candidate_miss"
    if see_losing:
        return "compensated_sacrifice"
    if eval_losing:
        return "other_cp_loss"
    return "clean_exchange"


def _stable_rank(record: Dict[str, Any]) -> str:
    identity = "|".join(
        (
            SAMPLE_SEED,
            str(record["game_id"]),
            str(record["move_number"]),
            str(record["move_uci"]),
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def main() -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=10_000)
    db = client[db_name]

    observation_projection = {
        "_id": 0,
        "game_id": 1,
        "move_number": 1,
        "move_uci": 1,
    }
    observations = list(
        db.move_observations.find(
            {"schema_version": SCHEMA_VERSION}, observation_projection
        )
    )
    observation_keys = {
        (
            str(obs.get("game_id") or ""),
            int(obs.get("move_number") or 0),
            str(obs.get("move_uci") or ""),
        )
        for obs in observations
    }
    game_ids = sorted({key[0] for key in observation_keys if key[0]})

    candidates: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    coverage: Counter[str] = Counter()

    for analysis in _iter_analyses(db, game_ids):
        coverage["analyses_scanned"] += 1
        game_id = str(analysis.get("game_id") or "")
        moves = (
            (analysis.get("stockfish_analysis") or {}).get("move_evaluations")
            or []
        )
        for mv in moves:
            if mv.get("is_opponent_move"):
                continue
            coverage["user_moves_scanned"] += 1
            fen = mv.get("fen_before")
            uci = str(mv.get("move_uci") or "")
            move_number = int(mv.get("move_number") or 0)
            if (game_id, move_number, uci) not in observation_keys:
                continue
            if not fen or len(uci) < 4:
                coverage["invalid_position_fields"] += 1
                continue
            try:
                board = chess.Board(fen)
                move = chess.Move.from_uci(uci)
            except (ValueError, TypeError):
                coverage["invalid_position_fields"] += 1
                continue
            if move not in board.legal_moves:
                coverage["illegal_moves"] += 1
                continue
            moved_piece = board.piece_at(move.from_square)
            if moved_piece is None or moved_piece.piece_type in (chess.PAWN, chess.KING):
                continue

            board_after = board.copy()
            board_after.push(move)
            candidate_see, legal_capture_count = _candidate_see_gain(
                board_after, move.to_square
            )
            if not legal_capture_count:
                continue
            coverage["d_live_decisions"] += 1
            cp_loss = _safe_cp(mv.get("cp_loss"))
            record = {
                "game_id": game_id,
                "move_number": move_number,
                "move_uci": uci,
                "fen_after": board_after.fen(),
                "target": move.to_square,
                "candidate_see": candidate_see,
                "cp_loss": cp_loss,
            }
            candidates[_stratum(candidate_see, cp_loss)].append(record)

    selected: List[Tuple[str, Dict[str, Any]]] = []
    population_by_stratum = {}
    for stratum in STRATA:
        records = candidates[stratum]
        population_by_stratum[stratum] = len(records)
        records.sort(key=_stable_rank)
        selected.extend(
            (stratum, record) for record in records[:SAMPLE_PER_STRATUM]
        )

    confusion: Counter[str] = Counter()
    stratum_results: Dict[str, Counter[str]] = defaultdict(Counter)
    disagreements = []
    for stratum, record in selected:
        board_after = chess.Board(record["fen_after"])
        independent_see = _exact_exchange_gain(board_after, record["target"])
        candidate_miss = (
            record["candidate_see"] >= SEE_FLOOR_CP
            and record["cp_loss"] >= CORROBORATING_CP_LOSS
        )
        independent_miss = (
            independent_see >= SEE_FLOOR_CP
            and record["cp_loss"] >= CORROBORATING_CP_LOSS
        )
        confusion[f"candidate_{candidate_miss}_exact_{independent_miss}"] += 1
        stratum_results[stratum]["sampled"] += 1
        if candidate_miss == independent_miss:
            stratum_results[stratum]["agreed"] += 1
        else:
            stratum_results[stratum]["disagreed"] += 1
            if len(disagreements) < 20:
                disagreements.append(
                    {
                        "game_id": record["game_id"],
                        "move_number": record["move_number"],
                        "move_uci": record["move_uci"],
                        "candidate_see": record["candidate_see"],
                        "independent_see": independent_see,
                        "cp_loss": record["cp_loss"],
                    }
                )

    per_stratum = {
        stratum: {
            "population": population_by_stratum[stratum],
            "sampled": stratum_results[stratum]["sampled"],
            "agreement_pct": _pct(
                stratum_results[stratum]["agreed"],
                stratum_results[stratum]["sampled"],
            ),
            "disagreements": stratum_results[stratum]["disagreed"],
        }
        for stratum in STRATA
    }
    candidate_miss_agreement = per_stratum["candidate_miss"]["agreement_pct"]
    total_sampled = sum(result["sampled"] for result in per_stratum.values())
    total_agreed = sum(
        result["sampled"] - result["disagreements"]
        for result in per_stratum.values()
    )
    overall_agreement = _pct(total_agreed, total_sampled)
    acceptance_passed = (
        candidate_miss_agreement is not None
        and candidate_miss_agreement >= 98.0
        and all(
            result["agreement_pct"] is not None
            and result["agreement_pct"] >= 95.0
            for result in per_stratum.values()
        )
    )

    report = {
        "audit": "d_live_see_implementation_agreement",
        "read_only": True,
        "external_semantic_ground_truth": False,
        "shared_gate_not_independently_verified": "stored cp_loss >=150",
        "schema_version": SCHEMA_VERSION,
        "candidate_rule": {
            "decision": "non-pawn/non-king moved piece is legally capturable on destination",
            "miss": "destination SEE >=150 and cp_loss >=150",
        },
        "pre_registered_sample": {
            "seed": SAMPLE_SEED,
            "per_stratum": SAMPLE_PER_STRATUM,
            "strata": list(STRATA),
        },
        "acceptance_rule": {
            "minimum_candidate_miss_stratum_agreement_pct": 98.0,
            "minimum_each_stratum_agreement_pct": 95.0,
        },
        "coverage": dict(coverage),
        "sample_by_stratum": per_stratum,
        "confusion": dict(confusion),
        "candidate_miss_stratum_agreement_pct": candidate_miss_agreement,
        "overall_see_outcome_agreement_pct": overall_agreement,
        "implementation_agreement_gate_passed": acceptance_passed,
        "disagreement_examples": disagreements,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

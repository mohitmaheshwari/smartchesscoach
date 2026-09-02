"""Read-only coverage replay for Home Teaching Case V2.

Runs inside the production backend container. It uses stored schema-18
positions and deterministic board geometry only: no Stockfish calls, no Mongo
writes, and no production identifiers or positions in the output.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from typing import Any, Dict

import chess
from pymongo import MongoClient

from services.destination_safety_detector import (
    FACT_VERSION,
    grade_destination_safety_candidate,
)


REPORT_VERSION = "home_teaching_reason_coverage.v1"


def _normalized_fen(fen: str) -> str:
    return " ".join(chess.Board(fen).fen().split()[:4])


def _eligible_moves(board: chess.Board):
    for move in board.legal_moves:
        piece = board.piece_at(move.from_square)
        if piece and piece.piece_type in (
            chess.KNIGHT,
            chess.BISHOP,
            chess.ROOK,
            chess.QUEEN,
        ):
            yield move


def _component_facts(board: chess.Board, move: chess.Move) -> Dict[str, bool]:
    mover = board.turn
    opponent = not mover
    origin_attackers = set(board.attackers(opponent, move.from_square))
    multi_target_attacker = False
    for attacker_square in origin_attackers:
        attacked = board.attacks(attacker_square)
        other_targets = [
            square
            for square in attacked
            if square != move.from_square
            and (piece := board.piece_at(square)) is not None
            and piece.color == mover
            and piece.piece_type != chess.KING
        ]
        if other_targets:
            multi_target_attacker = True
            break

    after = board.copy(stack=False)
    after.push(move)
    destination_captures = [
        reply
        for reply in after.legal_moves
        if after.is_capture(reply) and reply.to_square == move.to_square
    ]
    direct_recapture = False
    for reply in destination_captures:
        work = after.copy(stack=False)
        work.push(reply)
        if any(
            work.is_capture(recapture) and recapture.to_square == move.to_square
            for recapture in work.legal_moves
        ):
            direct_recapture = True
            break

    moved_piece_attacks = set(after.attacks(move.to_square))
    return {
        "incoming_threat": bool(origin_attackers),
        "multi_target_threat": multi_target_attacker,
        "counterattack": bool(origin_attackers & moved_piece_attacks),
        "destination_unattacked": not destination_captures,
        "one_recapture_line": bool(destination_captures and direct_recapture),
    }


def build_report(db) -> Dict[str, Any]:
    rows = list(db.move_observations.find(
        {
            "schema_version": {"$gte": 18},
            "destination_safety_exact.version": FACT_VERSION,
            "destination_safety_exact.fires": True,
        },
        {
            "_id": 0,
            "user_id": 1,
            "fen_before": 1,
            "move_uci": 1,
            "destination_safety_exact": 1,
        },
    ))

    distinct_users = {str(row.get("user_id") or "") for row in rows}
    positions: Dict[str, Dict[str, Any]] = {}
    invalid_rows = 0
    for row in rows:
        try:
            fen = str(row.get("fen_before") or "")
            key = _normalized_fen(fen)
            positions.setdefault(key, row)
        except (TypeError, ValueError):
            invalid_rows += 1

    totals: Counter[str] = Counter()
    safe_component_counts: Counter[str] = Counter()
    component_combinations: Counter[str] = Counter()
    safe_moves_per_position: Counter[int] = Counter()
    original_fire_recheck: Counter[str] = Counter()

    for row in positions.values():
        board = chess.Board(str(row["fen_before"]))
        original_uci = str(
            row.get("move_uci")
            or (row.get("destination_safety_exact") or {}).get("move_uci")
            or ""
        )
        if original_uci:
            original = grade_destination_safety_candidate(board.fen(), original_uci)
            original_fire_recheck[str(original.get("status") or "unmeasured")] += 1
            if original.get("proofs_agree"):
                original_fire_recheck["proofs_agree"] += 1

        safe_in_position = 0
        for move in _eligible_moves(board):
            totals["eligible_legal_moves"] += 1
            grade = grade_destination_safety_candidate(board.fen(), move.uci())
            status = str(grade.get("status") or "unmeasured")
            totals[f"status_{status}"] += 1
            if grade.get("proofs_agree"):
                totals["proofs_agree"] += 1
            if status != "pass" or not grade.get("proofs_agree"):
                continue
            safe_in_position += 1
            facts = _component_facts(board, move)
            active = sorted(name for name, present in facts.items() if present)
            for name in active:
                safe_component_counts[name] += 1
            component_combinations["+".join(active) or "destination_only"] += 1

        safe_moves_per_position[safe_in_position] += 1
        if safe_in_position:
            totals["positions_with_supported_safe_move"] += 1

    fingerprint_payload = {
        "report_version": REPORT_VERSION,
        "position_count": len(positions),
        "totals": dict(sorted(totals.items())),
        "safe_component_counts": dict(sorted(safe_component_counts.items())),
        "component_combinations": dict(sorted(component_combinations.items())),
        "safe_moves_per_position": dict(sorted(safe_moves_per_position.items())),
        "original_fire_recheck": dict(sorted(original_fire_recheck.items())),
    }
    canonical = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"))
    return {
        "audit": REPORT_VERSION,
        "read_only": True,
        "stockfish_rerun": False,
        "production_data_exported": False,
        "privacy": "Aggregate only; no ids, FENs, moves, PGNs, or free text.",
        "population": {
            "stored_exact_fires": len(rows),
            "distinct_players": len(distinct_users - {""}),
            "distinct_normalized_positions": len(positions),
            "invalid_rows": invalid_rows,
        },
        "candidate_move_coverage": dict(sorted(totals.items())),
        "safe_move_component_coverage": dict(sorted(safe_component_counts.items())),
        "safe_move_component_combinations": dict(sorted(component_combinations.items())),
        "safe_moves_per_position": {
            str(key): value for key, value in sorted(safe_moves_per_position.items())
        },
        "original_fire_recheck": dict(sorted(original_fire_recheck.items())),
        "fingerprint_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=10_000)
    try:
        db = client[os.environ.get("DB_NAME", "chess_coach")]
        print(json.dumps(build_report(db), indent=2, sort_keys=True))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

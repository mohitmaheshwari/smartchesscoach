"""
Read-only full-corpus audit for the Personal Improvement Cycle proof gate.

This script measures how often stored schema-v16 simple_hang observations cover
moves where the canonical SEE and Stockfish cp_loss corroborate a material hang.
It never writes to Mongo and is not imported by product runtime code.

Run inside the backend container:
    python scripts/audit_simple_hang_recall.py
"""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any, Dict, Iterable, Optional, Tuple

import chess
from pymongo import MongoClient

from coach_play.coach_blunder_guard import material_hung_after, see_gain


SCHEMA_VERSION = 16
SEE_FLOOR_CP = 150
CORROBORATING_CP_LOSS = 150
SIMPLE_HANG_CP_LOSS = 200


def _key(doc: Dict[str, Any]) -> Tuple[str, int, str]:
    return (
        str(doc.get("game_id") or ""),
        int(doc.get("move_number") or 0),
        str(doc.get("move_uci") or ""),
    )


def _safe_cp(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _is_forcing_san(san: str) -> bool:
    return "x" in san or san.endswith("+") or san.endswith("#")


def _destination_see_loss(
    board_before: chess.Board, move: chess.Move
) -> Tuple[int, bool]:
    """Return opponent SEE gain on the moved piece's square and capture availability."""
    board_after = board_before.copy()
    board_after.push(move)
    gains = []
    for reply in list(board_after.legal_moves):
        if board_after.is_capture(reply) and reply.to_square == move.to_square:
            gains.append(see_gain(board_after, reply))
    return (max(gains, default=0), bool(gains))


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
        "move_san": 1,
        "subtype": 1,
        "missed_pattern": 1,
        "cp_loss": 1,
        "execution_quality": 1,
        "opponent_previous.created_threat": 1,
    }
    observations = list(
        db.move_observations.find(
            {"schema_version": SCHEMA_VERSION}, observation_projection
        )
    )
    obs_by_key = {_key(obs): obs for obs in observations}
    game_ids = sorted({key[0] for key in obs_by_key if key[0]})
    flagged_keys = {
        key for key, obs in obs_by_key.items() if obs.get("subtype") == "simple_hang"
    }

    counts: Counter[str] = Counter()
    misses_by_reason: Counter[str] = Counter()
    matched_flagged_keys = set()

    for analysis in _iter_analyses(db, game_ids):
        counts["analyses_scanned"] += 1
        game_id = str(analysis.get("game_id") or "")
        moves = (
            (analysis.get("stockfish_analysis") or {}).get("move_evaluations")
            or []
        )
        for mv in moves:
            if mv.get("is_opponent_move"):
                continue
            counts["user_moves_scanned"] += 1

            fen = mv.get("fen_before")
            uci = str(mv.get("move_uci") or "")
            move_number = int(mv.get("move_number") or 0)
            key = (game_id, move_number, uci)
            observation = obs_by_key.get(key)
            if observation is None:
                counts["moves_without_v16_observation"] += 1
            else:
                counts["v16_observed_user_moves"] += 1

            if not fen or len(uci) < 4:
                counts["invalid_position_fields"] += 1
                continue
            try:
                board = chess.Board(fen)
                move = chess.Move.from_uci(uci)
            except (ValueError, TypeError):
                counts["invalid_position_fields"] += 1
                continue
            if move not in board.legal_moves:
                counts["illegal_moves"] += 1
                continue

            moved_piece = board.piece_at(move.from_square)
            if moved_piece is None:
                counts["missing_moved_piece"] += 1
                continue

            cp_loss = _safe_cp(mv.get("cp_loss"))
            destination_loss, destination_capturable = _destination_see_loss(
                board, move
            )
            board_after = board.copy()
            board_after.push(move)
            destination_raw_attacked = bool(
                board_after.attackers(board_after.turn, move.to_square)
            )
            is_major_or_minor = moved_piece.piece_type in (
                chess.KNIGHT,
                chess.BISHOP,
                chess.ROOK,
                chess.QUEEN,
            )

            # D_live: a non-pawn/non-king piece is moved onto a square where
            # the opponent has a legal capture. This is an exposure denominator,
            # not yet a production threshold.
            if (
                observation is not None
                and is_major_or_minor
                and destination_raw_attacked
            ):
                counts["d_live_raw_attack_decisions"] += 1
                if cp_loss >= CORROBORATING_CP_LOSS:
                    counts["d_live_raw_attack_cp_misses"] += 1
                if destination_loss >= SEE_FLOOR_CP:
                    counts["d_live_raw_attack_see_misses"] += 1
                if (
                    destination_loss >= SEE_FLOOR_CP
                    and cp_loss >= CORROBORATING_CP_LOSS
                ):
                    counts["d_live_raw_attack_corroborated_misses"] += 1

            if (
                observation is not None
                and is_major_or_minor
                and destination_capturable
            ):
                counts["d_live_decisions"] += 1
                d_live_missed = (
                    destination_loss >= SEE_FLOOR_CP
                    and cp_loss >= CORROBORATING_CP_LOSS
                )
                if d_live_missed:
                    counts["d_live_misses"] += 1
                    if key in flagged_keys:
                        counts["d_live_misses_flagged_simple_hang"] += 1
                        matched_flagged_keys.add(key)
                else:
                    counts["d_live_handled"] += 1

            if cp_loss < CORROBORATING_CP_LOSS:
                continue

            try:
                worst_loss, _ = material_hung_after(board, move)
            except Exception:
                counts["see_errors"] += 1
                continue
            if worst_loss < SEE_FLOOR_CP:
                continue

            # Broad target requested by the corpus review:
            # SEE >= 150 and Stockfish cp_loss >= 150 agree a hang occurred.
            counts["corroborated_hangs"] += 1
            if key in flagged_keys:
                counts["corroborated_hangs_flagged_simple_hang"] += 1
                matched_flagged_keys.add(key)
            else:
                if _is_forcing_san(str(mv.get("move") or "")):
                    misses_by_reason["forcing_or_capture"] += 1
                if cp_loss < SIMPLE_HANG_CP_LOSS:
                    misses_by_reason["cp_loss_150_to_199"] += 1
                if moved_piece.piece_type == chess.KING:
                    misses_by_reason["king_move"] += 1
                if observation is None:
                    misses_by_reason["missing_v16_observation"] += 1
                elif (observation.get("opponent_previous") or {}).get(
                    "created_threat"
                ):
                    misses_by_reason["prior_created_threat"] += 1
                elif observation.get("missed_pattern") != "piece_safety":
                    misses_by_reason["not_tagged_piece_safety"] += 1

            # Narrow target matching the current simple_hang taxonomy before
            # the cognitive-gap gate. This separates intentional taxonomy
            # exclusions from pipeline recall.
            san = str(mv.get("move") or "")
            prior_threat = bool(
                (observation or {}).get("opponent_previous", {}).get(
                    "created_threat"
                )
            )
            taxonomy_eligible = (
                moved_piece.piece_type != chess.KING
                and cp_loss >= SIMPLE_HANG_CP_LOSS
                and not _is_forcing_san(san)
                and not prior_threat
            )
            if taxonomy_eligible:
                counts["taxonomy_eligible_hangs"] += 1
                if key in flagged_keys:
                    counts["taxonomy_eligible_flagged_simple_hang"] += 1
                    matched_flagged_keys.add(key)

    report = {
        "audit": "simple_hang_recall",
        "read_only": True,
        "schema_version": SCHEMA_VERSION,
        "thresholds_inherited_from_existing_contract": {
            "see_floor_cp": SEE_FLOOR_CP,
            "corroborating_cp_loss": CORROBORATING_CP_LOSS,
            "simple_hang_cp_loss": SIMPLE_HANG_CP_LOSS,
        },
        "coverage": {
            "v16_observations_loaded": len(observations),
            "v16_games_requested": len(game_ids),
            "stored_simple_hang_flags": len(flagged_keys),
            "stored_flags_matched_by_any_audit_target": len(matched_flagged_keys),
            **{
                key: counts[key]
                for key in (
                    "analyses_scanned",
                    "user_moves_scanned",
                    "v16_observed_user_moves",
                    "moves_without_v16_observation",
                    "invalid_position_fields",
                    "illegal_moves",
                    "missing_moved_piece",
                    "see_errors",
                )
            },
        },
        "broad_corroborated_hang_recall": {
            "gold_hangs": counts["corroborated_hangs"],
            "flagged_simple_hang": counts[
                "corroborated_hangs_flagged_simple_hang"
            ],
            "recall_pct": _pct(
                counts["corroborated_hangs_flagged_simple_hang"],
                counts["corroborated_hangs"],
            ),
            "unflagged_reason_counts_nonexclusive": dict(misses_by_reason),
        },
        "taxonomy_eligible_recall": {
            "gold_hangs": counts["taxonomy_eligible_hangs"],
            "flagged_simple_hang": counts[
                "taxonomy_eligible_flagged_simple_hang"
            ],
            "recall_pct": _pct(
                counts["taxonomy_eligible_flagged_simple_hang"],
                counts["taxonomy_eligible_hangs"],
            ),
        },
        "d_live": {
            "decisions": counts["d_live_decisions"],
            "share_of_scanned_user_moves_pct": _pct(
                counts["d_live_decisions"], counts["v16_observed_user_moves"]
            ),
            "handled": counts["d_live_handled"],
            "missed": counts["d_live_misses"],
            "handled_pct": _pct(
                counts["d_live_handled"], counts["d_live_decisions"]
            ),
            "missed_pct": _pct(
                counts["d_live_misses"], counts["d_live_decisions"]
            ),
            "misses_flagged_simple_hang": counts[
                "d_live_misses_flagged_simple_hang"
            ],
            "simple_hang_recall_within_misses_pct": _pct(
                counts["d_live_misses_flagged_simple_hang"],
                counts["d_live_misses"],
            ),
            "formula_bakeoff": {
                "raw_attacked_square": {
                    "decisions": counts["d_live_raw_attack_decisions"],
                    "share_of_moves_pct": _pct(
                        counts["d_live_raw_attack_decisions"],
                        counts["v16_observed_user_moves"],
                    ),
                    "cp_loss_only_miss_pct": _pct(
                        counts["d_live_raw_attack_cp_misses"],
                        counts["d_live_raw_attack_decisions"],
                    ),
                    "destination_see_only_miss_pct": _pct(
                        counts["d_live_raw_attack_see_misses"],
                        counts["d_live_raw_attack_decisions"],
                    ),
                    "destination_see_and_cp_loss_miss_pct": _pct(
                        counts["d_live_raw_attack_corroborated_misses"],
                        counts["d_live_raw_attack_decisions"],
                    ),
                },
                "legal_capture_destination_see_and_cp_loss": {
                    "decisions": counts["d_live_decisions"],
                    "miss_pct": _pct(
                        counts["d_live_misses"], counts["d_live_decisions"]
                    ),
                },
            },
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

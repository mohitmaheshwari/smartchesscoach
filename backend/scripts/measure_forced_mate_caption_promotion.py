"""Measure the stored forced-mate population without trusting its proof path.

The independent path below does not import the missed-mate detector, forced-mate
proof builder, stored-line verifier, admission verdict, engine, or LLM. It reads
stored puzzle evidence only and emits aggregate, privacy-safe JSON.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from typing import Any, Dict, Mapping, Optional, Sequence

import chess
from pymongo import MongoClient


QUALITY_ID = "tactic:forced_mate_exact"
POOLS = ("community_puzzles", "community_training_positions")
CP_LOSS_FLOOR = 100
MAX_STORED_PLIES = 64
PROJECTION = {
    "_id": 0,
    "fen": 1,
    "best_move_uci": 1,
    "best_move_san": 1,
    "played_move": 1,
    "user_move": 1,
    "move": 1,
    "user_move_uci": 1,
    "user_move_san": 1,
    "cp_loss": 1,
    "pv_after_best": 1,
    "verified_admission": 1,
    "source_game_id": 1,
    "game_id": 1,
    "position_id": 1,
}


def _parse_move(board: chess.Board, raw: Any) -> Optional[chess.Move]:
    if isinstance(raw, chess.Move):
        return raw if raw in board.legal_moves else None
    if not isinstance(raw, str) or not raw.strip():
        return None
    token = raw.strip()
    try:
        move = chess.Move.from_uci(token.lower())
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    try:
        return board.parse_san(token)
    except (ValueError, AssertionError):
        return None


def _token(raw: Any) -> Optional[str]:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, Mapping):
        value = raw.get("move") or raw.get("san") or raw.get("uci")
        return str(value) if value else None
    return None


def _cp_loss(row: Mapping[str, Any]) -> Optional[float]:
    value = row.get("cp_loss")
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def _moves(
    row: Mapping[str, Any],
) -> tuple[Optional[chess.Board], Optional[chess.Move], Optional[chess.Move]]:
    try:
        board = chess.Board(str(row.get("fen") or ""))
    except (TypeError, ValueError):
        return None, None, None
    best = _parse_move(
        board, row.get("best_move_uci") or row.get("best_move_san")
    )
    played = _parse_move(
        board,
        row.get("played_move")
        or row.get("user_move")
        or row.get("move")
        or row.get("user_move_uci")
        or row.get("user_move_san"),
    )
    return board, played, best


def _piece_name(piece: Optional[chess.Piece]) -> Optional[str]:
    return chess.piece_name(piece.piece_type) if piece else None


def independent_adjudication(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Legally replay one stored line and report only facts it establishes."""
    board, played, best = _moves(row)
    if board is None:
        return {"status": "reject", "reason": "invalid_fen"}
    if best is None:
        return {"status": "reject", "reason": "invalid_best_move"}
    if played is None:
        return {"status": "reject", "reason": "invalid_played_move"}
    if played == best:
        return {"status": "reject", "reason": "played_best_move"}
    loss = _cp_loss(row)
    if loss is None:
        return {"status": "reject", "reason": "invalid_consequence"}
    if loss < CP_LOSS_FLOOR:
        return {"status": "reject", "reason": "insufficient_consequence"}

    continuation = [
        token
        for raw in (row.get("pv_after_best") or ())
        if (token := _token(raw))
    ]
    first = _parse_move(board, continuation[0]) if continuation else None
    full: Sequence[str] = (
        continuation if first == best else [best.uci(), *continuation]
    )
    if not full:
        return {"status": "reject", "reason": "empty_line"}
    if len(full) > MAX_STORED_PLIES:
        return {"status": "reject", "reason": "line_too_long"}

    replay = board.copy(stack=False)
    initiator = replay.turn
    replayed_uci = []
    replayed_san = []
    final_fact: Dict[str, Any] = {}
    for ply, raw in enumerate(full, start=1):
        move = _parse_move(replay, raw)
        if move is None:
            return {
                "status": "reject",
                "reason": "illegal_or_incomplete_line",
                "legal_prefix_plies": len(replayed_uci),
            }
        mover = replay.turn
        san = replay.san(move)
        replayed_uci.append(move.uci())
        replayed_san.append(san)
        replay.push(move)
        if replay.is_checkmate():
            if ply != len(full):
                return {
                    "status": "reject",
                    "reason": "moves_after_checkmate",
                    "mate_ply": ply,
                }
            king_square = replay.king(replay.turn)
            final_fact = {
                "mate_ply": ply,
                "mating_move_uci": move.uci(),
                "mating_move_san": san,
                # The piece standing on the mating square AFTER the move.
                # Reading the from-square reports "pawn" for a promotion
                # mate, and the shipped proof had the same defect, so the
                # two agreed while both were wrong.
                "mating_piece": _piece_name(
                    replay.piece_at(move.to_square)
                ),
                "mating_square": chess.square_name(move.to_square),
                "king_square": (
                    chess.square_name(king_square)
                    if king_square is not None
                    else None
                ),
                "terminal_legal_replies": replay.legal_moves.count(),
                "mating_color": "white" if mover else "black",
            }
            if mover != initiator:
                return {
                    "status": "reject",
                    "reason": "wrong_side_checkmate",
                    **final_fact,
                }

    if not replay.is_checkmate():
        return {
            "status": "reject",
            "reason": "line_does_not_end_in_checkmate",
            "legal_prefix_plies": len(replayed_uci),
        }

    first_board = board.copy(stack=False)
    first_piece = first_board.piece_at(best.from_square)
    first_san = first_board.san(best)
    subtype = "mate_in_one" if len(replayed_uci) == 1 else "longer_line"
    return {
        "status": "exact",
        "subtype": subtype,
        "best_move_uci": best.uci(),
        "best_move_san": first_san,
        "first_piece": _piece_name(first_piece),
        "first_destination": chess.square_name(best.to_square),
        "cp_loss": loss,
        "replayed_uci": replayed_uci,
        "replayed_san": replayed_san,
        **final_fact,
    }


def _source_key(row: Mapping[str, Any], *, pool: str) -> str:
    admission = row.get("verified_admission") or {}
    raw = (
        admission.get("source_fingerprint")
        or row.get("source_game_id")
        or row.get("game_id")
        or row.get("position_id")
        or json.dumps(
            {
                "pool": pool,
                "fen": row.get("fen"),
                "best": row.get("best_move_uci")
                or row.get("best_move_san"),
                "played": row.get("played_move")
                or row.get("user_move_uci")
                or row.get("user_move_san"),
            },
            sort_keys=True,
        )
    )
    return hashlib.sha256(
        f"forced-mate-source\x1f{raw}".encode("utf-8")
    ).hexdigest()[:20]


def _stored_fact(row: Mapping[str, Any]) -> Dict[str, Any]:
    admission = row.get("verified_admission") or {}
    facts = admission.get("verifier_facts") or ()
    fact = facts[0] if facts and isinstance(facts[0], Mapping) else {}
    return {
        "mate_ply": fact.get("mate_ply"),
        "replayed_uci": list(fact.get("replayed_uci") or ()),
    }


def build_report(db: Any) -> Dict[str, Any]:
    scanned = 0
    stored_candidates = 0
    stored_sources = set()
    candidate_outcomes: Counter[str] = Counter()
    exact_subtypes: Counter[str] = Counter()
    exact_pools: Counter[str] = Counter()
    exact_subtype_pools: Counter[str] = Counter()
    exact_subtype_sources: Dict[str, set[str]] = {
        "mate_in_one": set(),
        "longer_line": set(),
    }
    line_lengths: Counter[int] = Counter()
    full_pool_outcomes: Counter[str] = Counter()
    stored_field_coverage: Counter[str] = Counter()
    fact_mismatches = 0
    examples = []

    for pool in POOLS:
        for row in db[pool].find({}, PROJECTION):
            scanned += 1
            gold = independent_adjudication(row)
            full_pool_outcomes[
                gold.get("subtype")
                if gold.get("status") == "exact"
                else str(gold.get("reason"))
            ] += 1
            admission = row.get("verified_admission") or {}
            if admission.get("quality_id") != QUALITY_ID:
                continue

            stored_candidates += 1
            source_key = _source_key(row, pool=pool)
            stored_sources.add(source_key)
            for field in (
                "quality_id",
                "proof_version",
                "detector_version",
                "verifier_version",
                "source_fingerprint",
                "verifier_facts",
            ):
                if admission.get(field) not in (None, "", [], {}):
                    stored_field_coverage[field] += 1
            outcome = (
                gold.get("subtype")
                if gold.get("status") == "exact"
                else str(gold.get("reason"))
            )
            candidate_outcomes[outcome] += 1
            if gold.get("status") != "exact":
                if len(examples) < 10:
                    examples.append({"pool": pool, "outcome": outcome})
                continue

            exact_subtypes[str(gold["subtype"])] += 1
            exact_pools[pool] += 1
            exact_subtype_pools[f"{gold['subtype']}:{pool}"] += 1
            exact_subtype_sources[str(gold["subtype"])].add(source_key)
            line_lengths[int(gold["mate_ply"])] += 1
            stored = _stored_fact(row)
            if stored != {
                "mate_ply": gold.get("mate_ply"),
                "replayed_uci": gold.get("replayed_uci"),
            }:
                fact_mismatches += 1

    return {
        "read_only": True,
        "stockfish_runs": 0,
        "llm_calls": 0,
        "database_writes": 0,
        "quality_id": QUALITY_ID,
        "population": {
            "documents_scanned": scanned,
            "stored_candidates": stored_candidates,
            "distinct_source_keys": len(stored_sources),
            "candidate_independent_outcomes": dict(
                sorted(candidate_outcomes.items())
            ),
            "exact_subtypes": dict(sorted(exact_subtypes.items())),
            "exact_by_pool": dict(sorted(exact_pools.items())),
            "exact_by_subtype_and_pool": dict(
                sorted(exact_subtype_pools.items())
            ),
            "distinct_sources_by_subtype": {
                key: len(value)
                for key, value in sorted(exact_subtype_sources.items())
            },
            "mate_ply_distribution": {
                str(key): value for key, value in sorted(line_lengths.items())
            },
            "stored_fact_mismatches": fact_mismatches,
            "stored_admission_field_coverage": dict(
                sorted(stored_field_coverage.items())
            ),
        },
        "full_pool_independent_outcomes": dict(
            sorted(full_pool_outcomes.items())
        ),
        "candidate_failure_examples": examples,
    }


def main() -> int:
    client = MongoClient(
        os.environ["MONGO_URL"], serverSelectionTimeoutMS=10_000
    )
    try:
        report = build_report(
            client[os.environ.get("DB_NAME", "chess_coach")]
        )
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        failures = sum(
            value
            for key, value in report["population"][
                "candidate_independent_outcomes"
            ].items()
            if key not in {"mate_in_one", "longer_line"}
        )
        return 0 if failures == 0 else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

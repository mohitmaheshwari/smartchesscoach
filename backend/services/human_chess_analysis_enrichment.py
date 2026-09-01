"""Persist exact/human evidence once when a future game is analyzed.

This consumes the existing Stockfish result and PGN.  It never reruns
Stockfish and never alters move classification, severity or captions.
"""
from __future__ import annotations

import io
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import chess
import chess.pgn

from services.exact_endgame_service import probe_configured_fathom
from services.human_behavior_engine import MoveContext
from services.human_policy_runtime import derive_human_policy_evidence


ANALYSIS_ENRICHMENT_FLAG = "HUMAN_CHESS_ANALYSIS_ENRICHMENT_ENABLED"
_TRUE = frozenset({"1", "true", "yes", "on"})


def human_chess_analysis_enrichment_enabled() -> bool:
    return os.environ.get(ANALYSIS_ENRICHMENT_FLAG, "false").strip().lower() in _TRUE


def _key(fen: str) -> str:
    return " ".join(chess.Board(fen).fen().split()[:4])


def _header_rating(game: chess.pgn.Game, name: str) -> Optional[int]:
    try:
        value = int(game.headers.get(name) or 0)
        return value or None
    except (TypeError, ValueError):
        return None


def _user_positions(
    game: chess.pgn.Game,
    user_color: str,
) -> List[Tuple[str, Tuple[str, ...], int]]:
    board = game.board()
    history: List[str] = []
    target_white = str(user_color).lower() == "white"
    result = []
    for move in game.mainline_moves():
        if board.turn == target_white:
            result.append((_key(board.fen()), tuple(history), board.fullmove_number))
        history.append(move.uci())
        board.push(move)
    return result


def enrich_move_evaluations_with_human_chess(
    move_evaluations: Sequence[Dict[str, Any]],
    *,
    pgn: str,
    user_color: str,
    user_rating: Optional[int],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    rows = [dict(row) for row in move_evaluations]
    summary = {
        "rows": len(rows),
        "position_mismatch": 0,
        "exact_evidence": 0,
        "human_policy_evidence": 0,
    }
    if not human_chess_analysis_enrichment_enabled():
        summary["disabled"] = 1
        return rows, summary
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None:
            raise ValueError("invalid PGN")
        positions = _user_positions(game, user_color)
    except Exception:
        for row in rows:
            row["exact_endgame_probe_reason"] = "invalid_pgn"
            row["human_policy_reason"] = "invalid_pgn"
        return rows, summary

    opponent_rating = _header_rating(
        game, "BlackElo" if str(user_color).lower() == "white" else "WhiteElo"
    )
    time_control = str(game.headers.get("TimeControl") or "")

    for index, row in enumerate(rows):
        if index >= len(positions):
            row["exact_endgame_probe_reason"] = "missing_pgn_position"
            row["human_policy_reason"] = "missing_pgn_position"
            summary["position_mismatch"] += 1
            continue
        fen = str(row.get("fen_before") or "")
        position_key, history_uci, move_number = positions[index]
        try:
            if _key(fen) != position_key:
                raise ValueError("position mismatch")
        except ValueError:
            row["exact_endgame_probe_reason"] = "position_mismatch"
            row["human_policy_reason"] = "position_mismatch"
            summary["position_mismatch"] += 1
            continue

        exact, exact_reason = probe_configured_fathom(fen)
        row["exact_endgame_probe_reason"] = exact_reason
        if exact is not None:
            row["exact_endgame_evidence"] = exact.contract_dict()
            summary["exact_evidence"] += 1

        is_teaching_candidate = bool(
            row.get("cognitive_gap")
            or row.get("severity") in {"inaccuracy", "mistake", "blunder"}
            or int(row.get("cp_loss") or 0) > 0
        )
        if not is_teaching_candidate:
            row["human_policy_reason"] = "not_teaching_candidate"
            continue
        if user_rating is None or opponent_rating is None:
            row["human_policy_reason"] = "missing_measured_rating"
            continue
        evidence, reason = derive_human_policy_evidence(
            MoveContext(
                fen=fen,
                player_elo=int(user_rating),
                opponent_elo=int(opponent_rating),
                time_control=time_control,
                history_uci=history_uci,
                clock_seconds=None,
                clock_fraction=None,
                move_number=move_number,
            )
        )
        row["human_policy_reason"] = reason
        if evidence is not None:
            row["human_policy_evidence"] = evidence.contract_dict()
            summary["human_policy_evidence"] += 1
    return rows, summary

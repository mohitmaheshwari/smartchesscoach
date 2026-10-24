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
    opponent_rating: Optional[int] = None,
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

    # The caller's value first, the PGN header only as a fallback.
    #
    # The header was the sole source, and it refused 1,520 of 1,520 rows
    # across 25 of Mohit's most recent games with `missing_measured_rating`
    # -- those games carry no WhiteElo/BlackElo at all (108 of 200 do not),
    # while `white_rating`/`black_rating` sit on the game document for 72.1%
    # of them. Fixing only the user's side is not enough: BOTH ratings have
    # to be known or the row is refused, so the opponent's missing header
    # blocked every move.
    opponent_rating = opponent_rating or _header_rating(
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

        # Every move, not only the ones that went wrong.
        #
        # Mohit, 2026-10-24: "each game analysis should have both stockfish
        # and maia2". The gate here admitted a move only if it carried a
        # cognitive_gap, a bad severity, or ANY cp_loss -- which excludes
        # precisely the rows worth the most.
        #
        # Measured over 92 of his games before this changed: the positions
        # where a player of his rating would probably have blundered and he
        # did NOT are 1.4 a game, the likely move taken by a median 39% of
        # peers (one by 89%) and losing a median 178cp. Every one of those
        # has cp_loss under 50 and most have 0, so the old gate dropped the
        # entire family. They are also the only source this product has for
        # praise that is specific and checkable rather than filler.
        #
        # Cost is one policy call per ply, about 30ms, so roughly 1.2s on a
        # game whose Stockfish analysis already takes a median 182s.
        if not row.get("fen_before") and not row.get("fen"):
            row["human_policy_reason"] = "no_position"
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

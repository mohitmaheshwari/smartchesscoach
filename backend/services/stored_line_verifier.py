"""One deterministic legality/material verifier for stored continuations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

import chess

from services.caption_facts import PIECE_VALUE_CP


STORED_LINE_VERIFIER_VERSION = "stored_line_verifier.v1"


@dataclass(frozen=True)
class StoredLineReplay:
    complete: bool
    replayed_uci: Tuple[str, ...]
    final_fen: str
    checkmate: bool
    checkmating_color: Optional[chess.Color]
    mate_ply: Optional[int]
    net_material_gain_cp: int


def parse_legal_move(board: chess.Board, raw: Any) -> Optional[chess.Move]:
    if isinstance(raw, chess.Move):
        return raw if raw in board.legal_moves else None
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        move = chess.Move.from_uci(text.lower())
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    try:
        return board.parse_san(text)
    except (ValueError, AssertionError):
        return None


def _token(raw: Any) -> Optional[str]:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, Mapping):
        value = raw.get("move") or raw.get("san") or raw.get("uci")
        return str(value) if value else None
    return None


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(
        len(board.pieces(piece_type, color)) * PIECE_VALUE_CP[piece_type]
        for piece_type in (
            chess.PAWN,
            chess.KNIGHT,
            chess.BISHOP,
            chess.ROOK,
            chess.QUEEN,
        )
    )


def replay_stored_line(
    board_before: chess.Board,
    leading_move: Any,
    continuation: Sequence[Any],
) -> StoredLineReplay:
    """Normalize include/omit-leading formats and replay every stored ply."""
    initial = board_before.copy(stack=False)
    initiator = initial.turn
    leading = parse_legal_move(initial, leading_move)
    if leading is None:
        return StoredLineReplay(
            complete=False,
            replayed_uci=(),
            final_fen=initial.fen(),
            checkmate=False,
            checkmating_color=None,
            mate_ply=None,
            net_material_gain_cp=0,
        )

    tokens = [token for raw in continuation if (token := _token(raw))]
    first = parse_legal_move(initial, tokens[0]) if tokens else None
    full = ([] if first == leading else [leading.uci()]) + tokens

    board = initial.copy(stack=False)
    own_before = _material(board, initiator)
    opp_before = _material(board, not initiator)
    replayed = []
    checkmating_color = None
    mate_ply = None
    complete = True
    for index, raw in enumerate(full, start=1):
        move = parse_legal_move(board, raw)
        if move is None:
            complete = False
            break
        mover = board.turn
        replayed.append(move.uci())
        board.push(move)
        if board.is_checkmate():
            checkmating_color = mover
            mate_ply = index
            if index != len(full):
                complete = False
            break

    own_after = _material(board, initiator)
    opp_after = _material(board, not initiator)
    net_gain = (own_after - own_before) - (opp_after - opp_before)
    return StoredLineReplay(
        complete=complete,
        replayed_uci=tuple(replayed),
        final_fen=board.fen(),
        checkmate=board.is_checkmate(),
        checkmating_color=checkmating_color,
        mate_ply=mate_ply,
        net_material_gain_cp=net_gain,
    )

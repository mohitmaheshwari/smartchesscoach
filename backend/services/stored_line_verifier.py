"""One deterministic legality/material verifier for stored continuations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

import chess

from services.caption_facts import PIECE_VALUE_CP


STORED_LINE_VERIFIER_VERSION = "stored_line_verifier.v1"


@dataclass(frozen=True)
class StoredCapture:
    ply: int
    actor: str
    move_san: str
    origin: str
    destination: str
    capturing_piece: str
    captured_piece: str
    captured_square: str
    captured_value_cp: int

    def contract_dict(self) -> Mapping[str, Any]:
        return {
            "ply": self.ply,
            "actor": self.actor,
            "move_san": self.move_san,
            "origin": self.origin,
            "destination": self.destination,
            "capturing_piece": self.capturing_piece,
            "captured_piece": self.captured_piece,
            "captured_square": self.captured_square,
            "captured_value_cp": self.captured_value_cp,
        }


@dataclass(frozen=True)
class StoredLineReplay:
    complete: bool
    replayed_uci: Tuple[str, ...]
    replayed_san: Tuple[str, ...]
    captures: Tuple[StoredCapture, ...]
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
            replayed_san=(),
            captures=(),
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
    replayed_san = []
    captures = []
    checkmating_color = None
    mate_ply = None
    complete = True
    for index, raw in enumerate(full, start=1):
        move = parse_legal_move(board, raw)
        if move is None:
            complete = False
            break
        mover = board.turn
        san = board.san(move)
        capturing_piece = board.piece_at(move.from_square)
        captured_square = move.to_square
        if board.is_en_passant(move):
            captured_square += -8 if mover == chess.WHITE else 8
        captured_piece = (
            board.piece_at(captured_square) if board.is_capture(move) else None
        )
        if capturing_piece is None:
            complete = False
            break
        if captured_piece is not None:
            captures.append(StoredCapture(
                ply=index,
                actor="initiator" if mover == initiator else "opponent",
                move_san=san,
                origin=chess.square_name(move.from_square),
                destination=chess.square_name(move.to_square),
                capturing_piece=chess.piece_name(capturing_piece.piece_type),
                captured_piece=chess.piece_name(captured_piece.piece_type),
                captured_square=chess.square_name(captured_square),
                captured_value_cp=PIECE_VALUE_CP[captured_piece.piece_type],
            ))
        replayed.append(move.uci())
        replayed_san.append(san)
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
        replayed_san=tuple(replayed_san),
        captures=tuple(captures),
        final_fen=board.fen(),
        checkmate=board.is_checkmate(),
        checkmating_color=checkmating_color,
        mate_ply=mate_ply,
        net_material_gain_cp=net_gain,
    )

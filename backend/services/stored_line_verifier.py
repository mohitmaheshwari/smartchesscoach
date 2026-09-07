"""One deterministic legality/material verifier for stored continuations."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import chess

from services.caption_facts import PIECE_VALUE_CP


STORED_LINE_VERIFIER_VERSION = "stored_line_verifier.v4"
STORED_LINE_MATERIAL_SETTLEMENT_PLIES = 4
_MATERIAL_MATE_SCORE_CP = 100_000


def _actor(color: chess.Color, initiator: chess.Color) -> str:
    return "initiator" if color == initiator else "opponent"


def _piece_name(piece_type: int) -> str:
    return chess.piece_name(piece_type)


@dataclass(frozen=True)
class StoredPieceRelationState:
    """Exact geometry around one occupied square at one board state.

    reachable_squares is geometric mobility, not a claim that every move
    is legal or sound. Pins and king safety are carried separately.
    """

    actor: str
    piece_id: str
    piece: str
    square: str
    enemy_attackers: Tuple[str, ...]
    friendly_defenders: Tuple[str, ...]
    attack_squares: Tuple[str, ...]
    reachable_squares: Tuple[str, ...]
    pinned_to_king: bool

    def contract_dict(self) -> Mapping[str, Any]:
        return {
            "actor": self.actor,
            "piece_id": self.piece_id,
            "piece": self.piece,
            "square": self.square,
            "enemy_attackers": list(self.enemy_attackers),
            "friendly_defenders": list(self.friendly_defenders),
            "attack_squares": list(self.attack_squares),
            "reachable_squares": list(self.reachable_squares),
            "pinned_to_king": self.pinned_to_king,
        }


@dataclass(frozen=True)
class StoredPieceRelationChange:
    square: str
    before: Optional[StoredPieceRelationState]
    after: Optional[StoredPieceRelationState]

    def contract_dict(self) -> Mapping[str, Any]:
        return {
            "square": self.square,
            "before": self.before.contract_dict() if self.before else None,
            "after": self.after.contract_dict() if self.after else None,
        }


@dataclass(frozen=True)
class StoredLineGeometryChange:
    """Squares gained or lost by an unmoved bishop, rook, or queen."""

    kind: str
    actor: str
    piece: str
    slider_square: str
    changed_squares: Tuple[str, ...]

    def contract_dict(self) -> Mapping[str, Any]:
        return {
            "kind": self.kind,
            "actor": self.actor,
            "piece": self.piece,
            "slider_square": self.slider_square,
            "changed_squares": list(self.changed_squares),
        }


@dataclass(frozen=True)
class StoredLineEvent:
    ply: int
    actor: str
    move_uci: str
    move_san: str
    origin: str
    destination: str
    moving_piece: str
    moving_piece_id: str
    captured_piece: Optional[str]
    captured_piece_id: Optional[str]
    captured_square: Optional[str]
    captured_value_cp: int
    promotion_piece: Optional[str]
    gave_check: bool
    checkmate: bool
    stalemate: bool
    legal_reply_count: int
    forced_reply_uci: Optional[str]
    forced_reply_san: Optional[str]
    fen_before: str
    fen_after: str
    relation_changes: Tuple[StoredPieceRelationChange, ...]
    line_geometry_changes: Tuple[StoredLineGeometryChange, ...]

    def contract_dict(self) -> Mapping[str, Any]:
        return {
            "ply": self.ply,
            "actor": self.actor,
            "move_uci": self.move_uci,
            "move_san": self.move_san,
            "origin": self.origin,
            "destination": self.destination,
            "moving_piece": self.moving_piece,
            "moving_piece_id": self.moving_piece_id,
            "captured_piece": self.captured_piece,
            "captured_piece_id": self.captured_piece_id,
            "captured_square": self.captured_square,
            "captured_value_cp": self.captured_value_cp,
            "promotion_piece": self.promotion_piece,
            "gave_check": self.gave_check,
            "checkmate": self.checkmate,
            "stalemate": self.stalemate,
            "legal_reply_count": self.legal_reply_count,
            "forced_reply_uci": self.forced_reply_uci,
            "forced_reply_san": self.forced_reply_san,
            "fen_before": self.fen_before,
            "fen_after": self.fen_after,
            "relation_changes": [
                item.contract_dict() for item in self.relation_changes
            ],
            "line_geometry_changes": [
                item.contract_dict() for item in self.line_geometry_changes
            ],
        }


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
    initial_fen: str
    replayed_uci: Tuple[str, ...]
    replayed_san: Tuple[str, ...]
    captures: Tuple[StoredCapture, ...]
    events: Tuple[StoredLineEvent, ...]
    final_fen: str
    checkmate: bool
    checkmating_color: Optional[chess.Color]
    mate_ply: Optional[int]
    net_material_gain_cp: int

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.contract_dict(include_fingerprint=False),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def contract_dict(
        self, *, include_fingerprint: bool = True
    ) -> Mapping[str, Any]:
        payload: Dict[str, Any] = {
            "schema_version": STORED_LINE_VERIFIER_VERSION,
            "complete": self.complete,
            "initial_fen": self.initial_fen,
            "replayed_uci": list(self.replayed_uci),
            "replayed_san": list(self.replayed_san),
            "captures": [item.contract_dict() for item in self.captures],
            "events": [item.contract_dict() for item in self.events],
            "final_fen": self.final_fen,
            "checkmate": self.checkmate,
            "checkmating_color": (
                "white"
                if self.checkmating_color == chess.WHITE
                else "black"
                if self.checkmating_color == chess.BLACK
                else None
            ),
            "mate_ply": self.mate_ply,
            "net_material_gain_cp": self.net_material_gain_cp,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


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


def _legal_prefix_length(
    initial: chess.Board,
    raw_moves: Sequence[Any],
) -> int:
    board = initial.copy(stack=False)
    replayed = 0
    for raw in raw_moves:
        move = parse_legal_move(board, raw)
        if move is None:
            break
        replayed += 1
        board.push(move)
    return replayed


def _normalized_line(
    initial: chess.Board,
    leading: chess.Move,
    tokens: Sequence[str],
    *,
    resolve_ambiguous_continuation: bool,
) -> Tuple[Any, ...]:
    """Resolve include-leading and after-leading stored formats legally.

    A SAN token can describe the leading move in the initial position and a
    different opponent reply after that move (for example Rxd8 / Rxd8+).
    Therefore SAN equality alone cannot decide the format.
    """
    if not resolve_ambiguous_continuation:
        first_on_initial = (
            parse_legal_move(initial, tokens[0]) if tokens else None
        )
        return (
            tuple(tokens)
            if first_on_initial == leading
            else (leading.uci(), *tokens)
        )

    after_leading = (leading.uci(), *tokens)
    after_prefix = _legal_prefix_length(initial, after_leading)
    first_on_initial = (
        parse_legal_move(initial, tokens[0]) if tokens else None
    )
    includes_leading = (
        tuple(tokens)
        if first_on_initial == leading
        else None
    )
    included_prefix = (
        _legal_prefix_length(initial, includes_leading)
        if includes_leading is not None
        else -1
    )

    if after_prefix == len(after_leading):
        # continuation is the public parameter contract. Prefer it when both
        # interpretations happen to be legal; included-leading is compatibility.
        return after_leading
    if (
        includes_leading is not None
        and included_prefix == len(includes_leading)
    ):
        return includes_leading
    if includes_leading is not None and included_prefix > after_prefix:
        return includes_leading
    # Preserve the documented after-leading line's legal prefix. The replay
    # loop will retain a reached terminal fact but mark trailing junk incomplete.
    return after_leading


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


def _move_material_delta_cp(
    board: chess.Board,
    move: chess.Move,
    root: chess.Color,
) -> int:
    """Return exact signed capture/promotion material for one legal move."""
    captured_value_cp = 0
    if board.is_en_passant(move):
        captured_value_cp = PIECE_VALUE_CP[chess.PAWN]
    elif board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured is not None:
            captured_value_cp = PIECE_VALUE_CP.get(captured.piece_type, 0)

    promotion_gain_cp = 0
    if move.promotion is not None:
        promotion_gain_cp = (
            PIECE_VALUE_CP.get(move.promotion, 0)
            - PIECE_VALUE_CP[chess.PAWN]
        )

    delta = captured_value_cp + promotion_gain_cp
    return delta if board.turn == root else -delta


def settled_material_gain_cp(
    replay: StoredLineReplay,
    *,
    max_plies: int = STORED_LINE_MATERIAL_SETTLEMENT_PLIES,
) -> Optional[int]:
    """Settle a stored branch through bounded legal forcing-move quiescence.

    The score stays in the stored line initiator's perspective. At quiet
    nodes either side may decline another forcing move; captures, promotions,
    and checks are explored. In check, standing pat is illegal and every legal
    evasion is considered. This is deliberately a material verifier, not an
    engine or a positional evaluator.
    """
    if not replay.complete or max_plies < 0:
        return None
    try:
        root = chess.Board(replay.initial_fen).turn
        chess.Board(replay.final_fen)
    except (ValueError, TypeError):
        return None

    @lru_cache(maxsize=None)
    def _forcing_quiescence(fen: str, depth: int) -> int:
        board = chess.Board(fen)
        if board.is_checkmate():
            return (
                -_MATERIAL_MATE_SCORE_CP
                if board.turn == root
                else _MATERIAL_MATE_SCORE_CP
            )
        if depth <= 0:
            return 0

        if board.is_check():
            moves = tuple(board.legal_moves)
            if not moves:
                return (
                    -_MATERIAL_MATE_SCORE_CP
                    if board.turn == root
                    else _MATERIAL_MATE_SCORE_CP
                )
            values = []
        else:
            moves = tuple(
                move
                for move in board.legal_moves
                if (
                    board.is_capture(move)
                    or move.promotion is not None
                    or board.gives_check(move)
                )
            )
            values = [0]

        for move in moves:
            delta = _move_material_delta_cp(board, move, root)
            after = board.copy(stack=False)
            after.push(move)
            values.append(
                delta + _forcing_quiescence(after.fen(), depth - 1)
            )
        return max(values) if board.turn == root else min(values)

    return replay.net_material_gain_cp + _forcing_quiescence(
        replay.final_fen,
        max_plies,
    )


def _geometric_reach(
    board: chess.Board,
    square: chess.Square,
    piece: chess.Piece,
) -> Tuple[str, ...]:
    """Return deterministic non-own-occupied geometric destinations."""
    if piece.piece_type == chess.PAWN:
        destinations = set()
        direction = 8 if piece.color == chess.WHITE else -8
        one = square + direction
        if 0 <= one < 64 and board.piece_at(one) is None:
            destinations.add(one)
            start_rank = 1 if piece.color == chess.WHITE else 6
            two = square + (2 * direction)
            if (
                chess.square_rank(square) == start_rank
                and 0 <= two < 64
                and board.piece_at(two) is None
            ):
                destinations.add(two)
        for target in board.attacks(square):
            occupant = board.piece_at(target)
            if occupant is not None and occupant.color != piece.color:
                destinations.add(target)
        return tuple(
            chess.square_name(item) for item in sorted(destinations)
        )

    destinations = [
        target
        for target in board.attacks(square)
        if (
            board.piece_at(target) is None
            or board.piece_at(target).color != piece.color
        )
    ]
    return tuple(chess.square_name(item) for item in sorted(destinations))


def _relation_states(
    board: chess.Board,
    initiator: chess.Color,
    piece_ids: Mapping[chess.Square, str],
) -> Dict[str, StoredPieceRelationState]:
    states: Dict[str, StoredPieceRelationState] = {}
    for square, piece in sorted(board.piece_map().items()):
        enemy_attackers = tuple(
            chess.square_name(item)
            for item in sorted(board.attackers(not piece.color, square))
        )
        friendly_defenders = tuple(
            chess.square_name(item)
            for item in sorted(board.attackers(piece.color, square))
        )
        square_name = chess.square_name(square)
        states[square_name] = StoredPieceRelationState(
            actor=_actor(piece.color, initiator),
            piece_id=piece_ids[square],
            piece=_piece_name(piece.piece_type),
            square=square_name,
            enemy_attackers=enemy_attackers,
            friendly_defenders=friendly_defenders,
            attack_squares=tuple(
                chess.square_name(item)
                for item in sorted(board.attacks(square))
            ),
            reachable_squares=_geometric_reach(board, square, piece),
            pinned_to_king=(
                piece.piece_type != chess.KING
                and board.is_pinned(piece.color, square)
            ),
        )
    return states


def _relation_changes(
    before: chess.Board,
    after: chess.Board,
    initiator: chess.Color,
    before_piece_ids: Mapping[chess.Square, str],
    after_piece_ids: Mapping[chess.Square, str],
) -> Tuple[StoredPieceRelationChange, ...]:
    before_states = _relation_states(before, initiator, before_piece_ids)
    after_states = _relation_states(after, initiator, after_piece_ids)
    changes = []
    for square in sorted(set(before_states) | set(after_states)):
        prior = before_states.get(square)
        current = after_states.get(square)
        if prior != current:
            changes.append(StoredPieceRelationChange(
                square=square,
                before=prior,
                after=current,
            ))
    return tuple(changes)


def _line_geometry_changes(
    before: chess.Board,
    after: chess.Board,
    initiator: chess.Color,
) -> Tuple[StoredLineGeometryChange, ...]:
    changes = []
    for square, piece in sorted(before.piece_map().items()):
        if piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
            continue
        if after.piece_at(square) != piece:
            continue
        before_reach = set(_geometric_reach(before, square, piece))
        after_reach = set(_geometric_reach(after, square, piece))
        for kind, changed in (
            ("opened", after_reach - before_reach),
            ("closed", before_reach - after_reach),
        ):
            if changed:
                changes.append(StoredLineGeometryChange(
                    kind=kind,
                    actor=_actor(piece.color, initiator),
                    piece=_piece_name(piece.piece_type),
                    slider_square=chess.square_name(square),
                    changed_squares=tuple(sorted(changed)),
                ))
    return tuple(changes)


def _stored_line_event(
    *,
    before: chess.Board,
    after: chess.Board,
    move: chess.Move,
    move_san: str,
    ply: int,
    mover: chess.Color,
    initiator: chess.Color,
    moving_piece: chess.Piece,
    moving_piece_id: str,
    captured_piece: Optional[chess.Piece],
    captured_piece_id: Optional[str],
    captured_square: chess.Square,
    before_piece_ids: Mapping[chess.Square, str],
    after_piece_ids: Mapping[chess.Square, str],
) -> StoredLineEvent:
    legal_replies = list(after.legal_moves)
    forced_reply = legal_replies[0] if len(legal_replies) == 1 else None
    return StoredLineEvent(
        ply=ply,
        actor=_actor(mover, initiator),
        move_uci=move.uci(),
        move_san=move_san,
        origin=chess.square_name(move.from_square),
        destination=chess.square_name(move.to_square),
        moving_piece=_piece_name(moving_piece.piece_type),
        moving_piece_id=moving_piece_id,
        captured_piece=(
            _piece_name(captured_piece.piece_type)
            if captured_piece is not None
            else None
        ),
        captured_piece_id=captured_piece_id,
        captured_square=(
            chess.square_name(captured_square)
            if captured_piece is not None
            else None
        ),
        captured_value_cp=(
            PIECE_VALUE_CP[captured_piece.piece_type]
            if captured_piece is not None
            else 0
        ),
        promotion_piece=(
            _piece_name(move.promotion) if move.promotion else None
        ),
        gave_check=after.is_check(),
        checkmate=after.is_checkmate(),
        stalemate=after.is_stalemate(),
        legal_reply_count=len(legal_replies),
        forced_reply_uci=(
            forced_reply.uci() if forced_reply is not None else None
        ),
        forced_reply_san=(
            after.san(forced_reply) if forced_reply is not None else None
        ),
        fen_before=before.fen(),
        fen_after=after.fen(),
        relation_changes=_relation_changes(
            before,
            after,
            initiator,
            before_piece_ids,
            after_piece_ids,
        ),
        line_geometry_changes=_line_geometry_changes(
            before, after, initiator
        ),
    )


def replay_stored_line(
    board_before: chess.Board,
    leading_move: Any,
    continuation: Sequence[Any],
    *,
    include_events: bool = False,
    resolve_ambiguous_continuation: bool = False,
) -> StoredLineReplay:
    """Normalize include/omit-leading formats and replay every stored ply."""
    initial = board_before.copy(stack=False)
    initiator = initial.turn
    leading = parse_legal_move(initial, leading_move)
    if leading is None:
        return StoredLineReplay(
            complete=False,
            initial_fen=initial.fen(),
            replayed_uci=(),
            replayed_san=(),
            captures=(),
            events=(),
            final_fen=initial.fen(),
            checkmate=False,
            checkmating_color=None,
            mate_ply=None,
            net_material_gain_cp=0,
        )

    tokens = [token for raw in continuation if (token := _token(raw))]
    full = _normalized_line(
        initial,
        leading,
        tokens,
        resolve_ambiguous_continuation=(
            resolve_ambiguous_continuation
        ),
    )

    board = initial.copy(stack=False)
    piece_ids = {
        square: (
            f"{'white' if piece.color == chess.WHITE else 'black'}:"
            f"{_piece_name(piece.piece_type)}:{chess.square_name(square)}"
        )
        for square, piece in board.piece_map().items()
    }
    own_before = _material(board, initiator)
    opp_before = _material(board, not initiator)
    replayed = []
    replayed_san = []
    captures = []
    events = []
    checkmating_color = None
    mate_ply = None
    complete = True
    for index, raw in enumerate(full, start=1):
        move = parse_legal_move(board, raw)
        if move is None:
            complete = False
            break
        mover = board.turn
        board_before_move = board.copy(stack=False)
        before_piece_ids = dict(piece_ids)
        san = board.san(move)
        capturing_piece = board.piece_at(move.from_square)
        moving_piece_id = piece_ids.get(move.from_square)
        captured_square = move.to_square
        if board.is_en_passant(move):
            captured_square += -8 if mover == chess.WHITE else 8
        captured_piece = (
            board.piece_at(captured_square) if board.is_capture(move) else None
        )
        captured_piece_id = (
            piece_ids.get(captured_square)
            if captured_piece is not None
            else None
        )
        if capturing_piece is None or moving_piece_id is None:
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
        piece_ids.pop(move.from_square, None)
        if captured_piece is not None:
            piece_ids.pop(captured_square, None)
        if board.is_castling(move):
            rank = 0 if mover == chess.WHITE else 7
            kingside = move.to_square > move.from_square
            rook_from = chess.square(7 if kingside else 0, rank)
            rook_to = chess.square(5 if kingside else 3, rank)
            rook_id = piece_ids.pop(rook_from, None)
            if rook_id is not None:
                piece_ids[rook_to] = rook_id
        piece_ids[move.to_square] = moving_piece_id
        board.push(move)
        if include_events:
            events.append(_stored_line_event(
                before=board_before_move,
                after=board,
                move=move,
                move_san=san,
                ply=index,
                mover=mover,
                initiator=initiator,
                moving_piece=capturing_piece,
                moving_piece_id=moving_piece_id,
                captured_piece=captured_piece,
                captured_piece_id=captured_piece_id,
                captured_square=captured_square,
                before_piece_ids=before_piece_ids,
                after_piece_ids=piece_ids,
            ))
        replayed.append(move.uci())
        replayed_san.append(san)
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
        initial_fen=initial.fen(),
        replayed_uci=tuple(replayed),
        replayed_san=tuple(replayed_san),
        captures=tuple(captures),
        events=tuple(events),
        final_fen=board.fen(),
        checkmate=board.is_checkmate(),
        checkmating_color=checkmating_color,
        mate_ply=mate_ply,
        net_material_gain_cp=net_gain,
    )

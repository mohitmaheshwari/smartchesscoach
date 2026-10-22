"""Absolute facts about a game, read off its moves and its PGN headers.

Mohit, 2026-10-22: "there can be more absolute tags ... each game can be
classified brilliantly with tags and searchable for community and coach".

Everything here is a FACT, not a judgement, so it needs no engine and cannot
be wrong in the way a detector can: how the game ended, the mating pattern on
the final board, castling, promotions, en passant, early queen trades, the
endgame reached, the time control, the clock, the rating gap, stalemates.

Measured over 3,000 production games before adoption (2026-10-22); the
mating patterns were checked by eye on example positions.

Pure: no database. Returns {tag: [move refs]} so each tag can open the
position behind it; a tag about the whole game has no move refs.
"""
from __future__ import annotations

import io
import re
from collections import Counter
from typing import Any, Dict, List, Mapping, Optional

import chess
import chess.pgn

_CLK = re.compile(r"\[%clk (\d+):(\d+):(\d+(?:\.\d+)?)\]")
_VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5,
          chess.QUEEN: 9, chess.KING: 0}

# Rating gap that makes a win an upset, or a loss one against a lower player.
RATING_GAP = 150
# A game with mate this early is a miniature.
MINIATURE_MOVES = 20
LONG_GAME_MOVES = 60
QUEENS_OFF_EARLY_MOVE = 20
# An endgame counts as reached when its material held for this many plies.
ENDGAME_HOLD_PLIES = 6
# Down to this many seconds, or this share of the starting clock.
SCRAMBLE_SECONDS = 10
SCRAMBLE_SHARE = 0.05


def time_control_category(time_control: Optional[str]) -> Optional[str]:
    """bullet / blitz / rapid / classical / daily from a PGN TimeControl.

    The stored `time_control_category` field was empty on every one of 3,000
    games checked, so it is worked out here from the header, with lichess's
    estimate: base seconds plus forty times the increment.
    """
    text = str(time_control or "").strip()
    if not text or text == "-":
        return None
    if "/" in text:
        return "daily"
    try:
        base, _, inc = text.partition("+")
        estimate = float(base) + 40 * float(inc or 0)
    except ValueError:
        return None
    if estimate < 180:
        return "bullet"
    if estimate < 480:
        return "blitz"
    if estimate < 1500:
        return "rapid"
    return "classical"


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(_VALUE[p.piece_type] for p in board.piece_map().values() if p.color == color)


def _endgame_kind(board: chess.Board) -> Optional[str]:
    pieces = [(sq, p) for sq, p in board.piece_map().items()
              if p.piece_type not in (chess.KING, chess.PAWN)]
    kinds = {p.piece_type for _, p in pieces}
    if not pieces:
        return "pawn_endgame"
    if kinds == {chess.ROOK} and {p.color for _, p in pieces} == {chess.WHITE, chess.BLACK}:
        return "rook_endgame"
    if kinds == {chess.QUEEN} and len(pieces) == 2 and pieces[0][1].color != pieces[1][1].color:
        return "queen_endgame"
    if kinds <= {chess.KNIGHT, chess.BISHOP} and len(pieces) <= 4:
        if len(pieces) == 2 and kinds == {chess.BISHOP} and pieces[0][1].color != pieces[1][1].color:
            shade = lambda sq: (chess.square_file(sq) + chess.square_rank(sq)) % 2  # noqa: E731
            if shade(pieces[0][0]) != shade(pieces[1][0]):
                return "opposite_bishops_endgame"
        return "minor_piece_endgame"
    return None


def mate_pattern(board: chess.Board) -> Optional[str]:
    """Name the mate on a checkmated board, from geometry alone.

    Smothered: a knight mates a king whose every neighbour is its own piece.
    Back rank: a rook or queen mates along the king's back rank and every
    square in front of the king is its own piece. Otherwise the mating piece.
    """
    if not board.is_checkmate():
        return None
    mated = board.turn
    king = board.king(mated)
    checkers = list(board.checkers())
    if len(checkers) == 2:
        return "double_check_mate"
    if len(checkers) != 1 or king is None:
        return None
    square = checkers[0]
    piece = board.piece_at(square)
    ring = [sq for sq in chess.SQUARES if chess.square_distance(sq, king) == 1]

    def own(sq):
        p = board.piece_at(sq)
        return p is not None and p.color == mated

    if piece.piece_type == chess.KNIGHT and all(own(sq) for sq in ring):
        return "smothered_mate"
    back = 0 if mated == chess.WHITE else 7
    if piece.piece_type in (chess.ROOK, chess.QUEEN) and chess.square_rank(king) == back \
            and chess.square_rank(square) == back:
        forward = [sq for sq in ring if chess.square_rank(sq) != back]
        if forward and all(own(sq) for sq in forward):
            return "back_rank_mate"
    return {chess.QUEEN: "queen_mate", chess.ROOK: "rook_mate", chess.BISHOP: "bishop_mate",
            chess.KNIGHT: "knight_mate", chess.PAWN: "pawn_mate"}.get(piece.piece_type)


def _seconds(match) -> float:
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


def game_facts(game: Mapping[str, Any], outcome: Optional[str]) -> Dict[str, List[Dict[str, Any]]]:
    """{tag: [move refs]} for every fact that holds for this game."""
    facts: Dict[str, List[Dict[str, Any]]] = {}

    def add(tag: str, ref: Optional[Dict[str, Any]] = None):
        refs = facts.setdefault(tag, [])
        if ref and ref not in refs:
            refs.append(ref)

    term = str(game.get("termination") or "unknown")
    if outcome in ("win", "loss", "draw"):
        add(f"ended_{outcome}_by_{term}")

    user_rating, opp_rating = game.get("user_rating"), game.get("opponent_rating")
    if isinstance(user_rating, (int, float)) and isinstance(opp_rating, (int, float)):
        if outcome == "win" and opp_rating - user_rating >= RATING_GAP:
            add("user_beat_higher_rated")
        if outcome == "loss" and user_rating - opp_rating >= RATING_GAP:
            add("user_lost_to_lower_rated")

    pgn = game.get("pgn")
    try:
        parsed = chess.pgn.read_game(io.StringIO(str(pgn))) if pgn else None
    except Exception:
        parsed = None
    if parsed is None:
        return facts

    category = time_control_category(parsed.headers.get("TimeControl") or game.get("time_control"))
    if category:
        add(f"time_control_{category}")

    user = chess.WHITE if str(game.get("user_color") or "white") == "white" else chess.BLACK
    board = parsed.board()
    castled = {chess.WHITE: None, chess.BLACK: None}
    queens_off = False
    endgame_run: Counter = Counter()
    first_clock: Dict[bool, float] = {}
    scrambled = False
    last_ref = None
    node = parsed
    while node.variations:
        node = node.variations[0]
        move = node.move
        mover = board.turn
        ref = {"move_number": board.fullmove_number, "san": board.san(move),
               "side": "you" if mover == user else "them"}
        if board.is_castling(move):
            side = "kingside" if board.is_kingside_castling(move) else "queenside"
            castled[mover] = side
            if mover == user:
                add(f"user_castled_{side}", ref)
        if move.promotion:
            who = "user" if mover == user else "opponent"
            add(f"{who}_promoted_a_pawn", ref)
            if who == "user" and move.promotion != chess.QUEEN:
                add("user_underpromoted", ref)
        if mover == user and board.is_en_passant(move):
            add("user_captured_en_passant", ref)
        board.push(move)
        last_ref = ref
        clock = _CLK.search(node.comment or "")
        if clock and mover == user:
            seconds = _seconds(clock)
            first_clock.setdefault(mover, seconds)
            if not scrambled and seconds <= max(SCRAMBLE_SECONDS, SCRAMBLE_SHARE * first_clock[mover]):
                scrambled = True
                add("user_in_time_scramble", ref)
        if not queens_off and not board.pieces(chess.QUEEN, chess.WHITE) \
                and not board.pieces(chess.QUEEN, chess.BLACK):
            queens_off = True
            if board.fullmove_number <= QUEENS_OFF_EARLY_MOVE:
                add("queens_traded_early", ref)
        kind = _endgame_kind(board)
        if kind:
            endgame_run[kind] += 1
            if endgame_run[kind] == ENDGAME_HOLD_PLIES:
                add(f"reached_{kind}", ref)

    moves = board.fullmove_number
    if moves >= LONG_GAME_MOVES:
        add("long_game")
    if castled[user] is None and moves >= 20:
        add("user_never_castled")
    if castled[not user] is None and moves >= 20:
        add("opponent_never_castled")
    if castled[user] and castled[not user] and castled[user] != castled[not user]:
        add("opposite_side_castling")

    pattern = mate_pattern(board)
    if pattern:
        who = "user_delivered" if board.turn != user else "user_suffered"
        add(f"{who}_{pattern}", last_ref)
        if moves <= MINIATURE_MOVES:
            add("user_won_miniature" if who == "user_delivered" else "user_lost_miniature", last_ref)
    if board.is_stalemate():
        diff = _material(board, user) - _material(board, not user)
        if diff >= 3:
            add("user_stalemated_while_ahead", last_ref)
        elif diff <= -3:
            add("user_saved_by_stalemate", last_ref)
    return facts

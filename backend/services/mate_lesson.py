"""Which lesson a mate-allowing move should teach, and where its words live.

Built 2026-09-20 after Mohit asked why the back-rank captions he had approved
were not showing. They were -- in `/admin/detector-review` only. The rules had
been written into that route's own caption producer, so the surface a PLAYER
reads (`game_decryption_v5` -> `caption_pipeline` -> `R01_mate.json`) still
said "Bxd5 allows mate in 3." and nothing else. Two caption paths for one
position is exactly what feedback_one_source_of_truth forbids: migrate, do not
patch.

So this module owns the ORDER, once:

  1. a named pattern the player can look up, recognise and prevent
  2. situations where a generic lesson would be unfair, or simply false
  3. the habit behind the mistake
  4. today's symptom

and `R01_mate.json` owns the WORDS, once. Neither surface writes prose of its
own; both ask `mate_lesson_id()` what the lesson is and `lesson_text()` how to
say it. Adding a lesson means editing the order here and the variant there --
never one caller.

Every predicate is board-provable. Nothing here consults an engine except
through `mate_info`, which the analyser already stored.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, Optional, Tuple

import chess

# Lesson ids, in the order they are tried. The id is what crosses the boundary
# between code and content, so it is stable even when the wording changes.
BACK_RANK = "back_rank"
IN_CHECK = "in_check"
OPPONENT_PLAN = "opponent_plan"
MATE_THREATENED = "mate_threatened"
WIN_A_PIECE = "win_a_piece"
FREE_PAWN = "free_pawn"
CASTLE = "castle"
GIVE_AIR = "give_air"
SCAN = "scan"

# A real material win, not an engine preference. From the measured
# distribution of these captures rather than chosen.
WIN_A_PIECE_CP = 200

_HOME_SQUARES_BY_TYPE = {
    chess.WHITE: {chess.QUEEN: (chess.D1,), chess.ROOK: (chess.A1, chess.H1),
                  chess.BISHOP: (chess.C1, chess.F1),
                  chess.KNIGHT: (chess.B1, chess.G1)},
    chess.BLACK: {chess.QUEEN: (chess.D8,), chess.ROOK: (chess.A8, chess.H8),
                  chess.BISHOP: (chess.C8, chess.F8),
                  chess.KNIGHT: (chess.B8, chess.G8)},
}

_CAPTIONS = pathlib.Path(__file__).resolve().parent.parent / "data" / "captions"
_R01 = _CAPTIONS / "R01_mate.json"
_VARIANT_FOR = {
    BACK_RANK: "user_allows_back_rank",
    IN_CHECK: "user_allows_in_check",
    OPPONENT_PLAN: "user_allows_opponent_plan",
    MATE_THREATENED: "user_allows_mate_threatened",
    WIN_A_PIECE: "user_allows_win_a_piece",
    FREE_PAWN: "user_allows_free_pawn",
    CASTLE: "user_allows_castle",
    GIVE_AIR: "user_allows_give_air",
    SCAN: "user_allows_scan",
}

_TEXT_CACHE: Dict[str, str] = {}


def lesson_text(lesson_id: str) -> Optional[str]:
    """The words for a lesson, read from R01_mate.json.

    Prose lives in the caption file and nowhere else, which is what the
    caption-guard hook enforces and what lets the wording be edited without
    touching either caller.
    """
    if not _TEXT_CACHE:
        try:
            data = json.loads(_R01.read_text(encoding="utf-8"))
            _TEXT_CACHE.update(data.get("variants") or {})
        except Exception:  # noqa: BLE001
            return None
    return _TEXT_CACHE.get(_VARIANT_FOR.get(lesson_id, ""))


def back_rank_seal(mated_board, mating_move, king_square, king_color) -> int:
    """How many of the king's escape squares are sealed by its OWN pawns.

    Two or more is what separates "sealed in" from "happens to have a pawn
    nearby". The mate must also arrive ALONG that rank, from a piece that
    travels it.
    """
    home = 0 if king_color == chess.WHITE else 7
    if chess.square_rank(king_square) != home:
        return 0
    lander = mated_board.piece_at(mating_move.to_square)
    if lander is None or lander.piece_type not in (chess.ROOK, chess.QUEEN):
        return 0
    if chess.square_rank(mating_move.to_square) != home:
        return 0
    step = 1 if king_color == chess.WHITE else -1
    sealed = 0
    for offset in (-1, 0, 1):
        file_index = chess.square_file(king_square) + offset
        if not 0 <= file_index <= 7:
            continue
        square = chess.square(file_index, home + step)
        blocker = mated_board.piece_at(square)
        if (blocker is not None
                and blocker.color == king_color
                and blocker.piece_type == chess.PAWN):
            sealed += 1
    return sealed


def mate_was_already_threatened(board_before) -> bool:
    """Could the OPPONENT have mated immediately, before our move?

    Flipping the turn is only sound when the player is NOT in check, which the
    caller establishes first -- otherwise the flipped position is illegal.
    """
    try:
        probe = board_before.copy(stack=False)
        probe.turn = not board_before.turn
        for move in probe.legal_moves:
            after = probe.copy(stack=False)
            after.push(move)
            if after.is_checkmate():
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def pieces_brought_to_the_king(board_before, attacker_squares) -> int:
    """How many of the mating pieces were MANEUVERED there.

    A piece still on its starting square was not brought anywhere and proves
    no plan. Evaluated on the PRE-MOVE board on purpose: in a multi-ply mate
    an attacker often arrives during the line, and claiming they had been
    building it would describe moves that had not happened yet.
    """
    brought = 0
    for square in attacker_squares:
        piece = board_before.piece_at(square)
        if piece is None or piece.piece_type in (chess.PAWN, chess.KING):
            continue
        homes = _HOME_SQUARES_BY_TYPE[piece.color].get(piece.piece_type, ())
        if square not in homes:
            brought += 1
    return brought


def capture_net_cp(board_before, played_move) -> Optional[int]:
    """What the capture actually NETS, not merely that it was a capture.

    is_capture() says a piece was taken and nothing about whether anything was
    won: measured over these cards, 5 of 13 win a piece, 6 win only a pawn and
    2 LOSE material -- one at -400, captioned as winning one.
    """
    if played_move is None or not board_before.is_capture(played_move):
        return None
    from services.caption_facts import PIECE_VALUE_CP

    victim = board_before.piece_at(played_move.to_square)
    took = PIECE_VALUE_CP.get(victim.piece_type, 100) if victim else 100
    after = board_before.copy(stack=False)
    after.push(played_move)
    try:
        from services.legal_exchange_verifier import independent_exchange_gain
        return took - independent_exchange_gain(after, played_move.to_square)
    except Exception:  # noqa: BLE001
        return None


def escape_square_note(board_before: chess.Board) -> Optional[Tuple[str, str]]:
    """How many squares the king had left, as (long, short) wording.

    Mohit flagged two allowed_mate cards on 2026-09-20 asking for the same
    thing: "count escape squares after a check, you know something like
    that?" and "king escape squares from immediate checks". He is pointing at
    the definition of mate itself -- a king with nowhere to go.

    Measured over the 1,912 indexed allowed_mate claims, counting the king's
    squares in the position BEFORE the player moved:

        0 squares  15.2%
        1 square   36.0%
        2 squares  30.6%
        3+         18.2%

    So 81.8% of players who walked into mate were already down to two squares
    or fewer, which makes the count a real warning sign rather than trivia --
    and it is a different number on every board, so it is not filler. Above
    two it is not a warning, so nothing is said.
    """
    king = board_before.king(board_before.turn)
    if king is None:
        return None
    squares = len({mv.to_square for mv in board_before.legal_moves
                   if mv.from_square == king})
    if squares > 2:
        return None
    had = ("had nowhere to go" if squares == 0
           else "had one square" if squares == 1 else "had two squares")
    short = f"Your king {had} before you moved."
    return (f"{short} Count that number -- when it is low, go through every "
            "check they have.", short)


def mate_lesson_id(
    board_before: chess.Board,
    played_move: Optional[chess.Move],
    *,
    mated_board: Optional[chess.Board] = None,
    mating_move: Optional[chess.Move] = None,
    mated_king: Optional[int] = None,
    mated_king_color: Optional[bool] = None,
    attacker_squares: Optional[list] = None,
    own_blocked_escapes: int = 0,
    king_is_castled: bool = False,
    king_in_centre: bool = False,
    attackers_were_standing: bool = False,
    has_supporters: bool = False,
    mate_info: Optional[Dict[str, Any]] = None,
) -> str:
    """The single definition of which lesson this mate should teach."""
    # 1. Back-rank is the most actionable thing here: a named pattern every
    # beginner meets, with a fix they can apply on move 10.
    if (mated_board is not None and mating_move is not None
            and mated_king is not None and mated_king_color is not None):
        if back_rank_seal(mated_board, mating_move, mated_king,
                          mated_king_color) >= 2:
            return BACK_RANK

    # 2. Being IN CHECK is its own situation, and a rule about openings or
    # greed does not belong on a card where the player had one job. Gated on
    # mate_info.before being empty -- the engine saying the position was not
    # yet a forced mate, so a survivable answer existed. Without this the card
    # blames someone for a move they were forced into.
    in_check = board_before.is_check()
    if in_check and (mate_info or {}).get("before") is None:
        return IN_CHECK

    # 3. The habit. Mohit chose this framing explicitly on dxc5/Qxh2#: "it's
    # about ignorance of opponent plan, that's the teaching." Where the board
    # proves they walked pieces over AND mate was available, the plan lesson
    # wins; the mate threat is only its symptom.
    if attacker_squares and pieces_brought_to_the_king(
            board_before, attacker_squares) >= 2:
        return OPPONENT_PLAN

    # 4. Not "pieces are gathering" but "they could have mated you that move".
    if not in_check and mate_was_already_threatened(board_before):
        return MATE_THREATENED

    net = capture_net_cp(board_before, played_move)
    if net is not None and net >= WIN_A_PIECE_CP:
        return WIN_A_PIECE
    if net is not None and 0 < net < WIN_A_PIECE_CP:
        return FREE_PAWN

    # "Give your king air" is advice for a king that has ALREADY castled. With
    # the king still on e8 the lesson is CASTLE, and telling them to make luft
    # teaches the wrong habit.
    if king_in_centre and has_supporters:
        return CASTLE
    if king_is_castled and own_blocked_escapes >= 2:
        return GIVE_AIR
    if attackers_were_standing:
        return SCAN
    return SCAN


def lesson_from_caption_facts(facts: Dict[str, Any]) -> Optional[str]:
    """Decide the lesson from the caption pipeline's own fact bundle.

    The game review reaches this module through here, so the player-facing
    caption and /admin/detector-review answer the same question the same way.
    Returns None when the position does not support a lesson, which leaves the
    existing generic variants to render exactly as they do today -- this can
    only add a caption, never replace a working one with nothing.
    """
    fen = facts.get("fen_before")
    played_san = facts.get("played_san")
    if not fen or not played_san:
        return None
    try:
        board = chess.Board(str(fen))
        played = board.parse_san(str(played_san))
    except Exception:  # noqa: BLE001
        return None

    # The mate the move ALLOWS is the opponent's forced line from the position
    # after it -- the same line the review renders as the punishment.
    after = board.copy(stack=False)
    try:
        after.push(played)
    except Exception:  # noqa: BLE001
        return None

    mated_board = mating_move = mated_king = None
    mated_king_color = None
    attacker_squares: list = []
    walk = after.copy(stack=False)
    for san in list(facts.get("pv_after_played") or [])[:8]:
        try:
            move = walk.parse_san(str(san))
        except Exception:  # noqa: BLE001
            break
        probe = walk.copy(stack=False)
        probe.push(move)
        if probe.is_checkmate():
            mated_board, mating_move = walk.copy(stack=False), move
            mated_king = probe.king(probe.turn)
            mated_king_color = probe.turn
            attacker_squares = [move.from_square]
            for square in probe.attackers(not probe.turn, move.to_square):
                if square != move.to_square:
                    attacker_squares.append(square)
            break
        walk.push(move)

    own_blocked = 0
    castled = in_centre = False
    if mated_king is not None:
        home = 0 if mated_king_color == chess.WHITE else 7
        on_home = chess.square_rank(mated_king) == home
        king_file = chess.square_file(mated_king)
        castled = on_home and king_file in (1, 2, 6, 7)
        in_centre = on_home and king_file in (3, 4)
        try:
            from services.escape_squares_service import count_king_escape_squares
            info = count_king_escape_squares(
                mated_board.fen() if mated_board else str(fen),
                "white" if mated_king_color == chess.WHITE else "black")
            own_blocked = sum(
                1 for b in (info.get("blocked_squares") or [])
                if b.get("reason") == "own_piece")
        except Exception:  # noqa: BLE001
            own_blocked = 0

    return mate_lesson_id(
        board,
        played,
        mated_board=mated_board,
        mating_move=mating_move,
        mated_king=mated_king,
        mated_king_color=mated_king_color,
        attacker_squares=attacker_squares,
        own_blocked_escapes=own_blocked,
        king_is_castled=castled,
        king_in_centre=in_centre,
        attackers_were_standing=bool(attacker_squares),
        has_supporters=len(attacker_squares) > 1,
        mate_info=facts.get("mate_info"),
    )

"""Check first, take second: the capture that works only after a check.

Mohit, 2026-11-06, on 3628ebef move 32: "why is this a mistake?" White played
Rxe7 and the engine wanted Re6+. Both moves take the knight on e7. After Rxe7
the line runs Qxe7 Rxe7 Kxe7: the king on f6 takes back last and every piece
comes off. After Re6+ the king has to step away (Kg5 in the line), and when
the rook then takes on e7 the king is no longer next to that square.

The card said "it also hits the knight on e7 ... attacks more things", and the
Why button said "Re6+ was the move: it leads to Rxe7, picking up their knight
on e7 for free" -- about a knight the played move takes too. Neither names the
difference, which is the king.

The family (docs/caption_line_reasoning_scope.md, fix 3) fires only when every
one of these is read off the two lines:

  shape   the played move is a capture on S; the better move gives check and
          is not that capture; the better line then takes the same piece on S
  played  in the played line the opponent's KING makes a capture on S
  check   the reply to the check in the better line is a king move
  after   when the better line takes on S the king no longer attacks S, and
          nothing of the opponent's captures on S for the rest of the line
  gain    the exchange on S ends at least a pawn better for the mover in the
          better line than in the played line (the same ledger the material
          family uses)

Anything else is silent, and the measurement says which condition stopped it,
so a pass over many cards gives the fire-rate distribution. V1 covers the
king's recapture only; a check that removes another defender is a later
variant and stays silent here.

Engine-free: both lines are given. The Why button passes the lines its own
search produced; the caption facts pass the stored lines.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import chess

from services.stored_line_verifier import parse_legal_move

PIECE_NAME = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
              chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}

# The better line has to take on the same square soon: its own second move in
# the Rxe7 case (ply 2). Later than its third move (ply 4) the capture is a
# different story from "check first, take second".
CAPTURE_BY_PLY = 4
# The rest of the better line is read this far for a recapture on the square,
# the same window the exchange ledger reads.
LINE_HORIZON = 12
# The exchange on the square must end at least a pawn better after the check.
MIN_GAIN_CP = 100


def _measure() -> Dict[str, Any]:
    return {"shape": False, "fires": False, "why_not": None, "square": None, "piece": None,
            "capture_san": None, "capture_ply": None, "king_from": None, "king_to": None,
            "king_takes_back_ply": None, "king_last": None, "check_forces_king": None,
            "net_played_cp": None, "net_better_cp": None,
            "text": None, "facts": None, "consequence": None}


def check_first_claim(root: chess.Board, played_line: Sequence[str], alt_line: Sequence[str], *,
                      mover_is_user: bool) -> Dict[str, Any]:
    """The measurement for this family on one position, and the sentence when it fires.

    `played_line` and `alt_line` start with the played move and the better
    move. Always returns the measurement; `why_not` names the first condition
    that failed.
    """
    out = _measure()
    mover = root.turn
    played_line = [str(m) for m in (played_line or [])]
    alt_line = [str(m) for m in (alt_line or [])]
    if not played_line or not alt_line:
        out["why_not"] = "no_line"
        return out
    played = parse_legal_move(root, played_line[0])
    alt = parse_legal_move(root, alt_line[0])
    if played is None or alt is None or played == alt:
        out["why_not"] = "unplayable"
        return out

    # ---- shape: a capture against a check that takes the same piece later
    victim = root.piece_at(played.to_square)
    if victim is None or victim.color == mover or root.is_en_passant(played):
        out["why_not"] = "played_not_capture"
        return out
    square = played.to_square
    if not root.gives_check(alt):
        out["why_not"] = "better_not_check"
        return out
    if alt.to_square == square:
        out["why_not"] = "better_is_the_capture"
        return out
    out["square"] = chess.square_name(square)
    out["piece"] = PIECE_NAME[victim.piece_type]

    board = root.copy()
    board.push(alt)
    every_reply_is_king = all(board.piece_type_at(m.from_square) == chess.KING for m in board.legal_moves)
    capture_ply = None
    capture_san = None
    king_to = None
    for ply, san in enumerate(alt_line[1:CAPTURE_BY_PLY + 1], start=1):
        move = parse_legal_move(board, san)
        if move is None:
            break
        if board.turn == mover:
            if move.to_square == square:
                target = board.piece_at(square)
                if (target is not None and target.color != mover
                        and target.piece_type == victim.piece_type):
                    capture_ply, capture_san = ply, board.san(move)
                break_after = capture_ply is not None
            else:
                break_after = False
        else:
            # The piece must still be the one the played move takes.
            if move.from_square == square or move.to_square == square:
                break
            if ply == 1 and board.piece_type_at(move.from_square) == chess.KING:
                king_to = chess.square_name(move.to_square)
            break_after = False
        if break_after:
            break
        board.push(move)
    if capture_ply is None:
        out["why_not"] = "no_same_capture"
        return out
    out["shape"] = True
    out["capture_san"], out["capture_ply"] = capture_san, capture_ply
    out["check_forces_king"] = every_reply_is_king

    # ---- played: the king takes back on the square
    king_ply = None
    king_from = None
    opp_captures_on_square: List[int] = []
    walk = root.copy()
    for ply, san in enumerate(played_line[:LINE_HORIZON]):
        move = parse_legal_move(walk, san)
        if move is None:
            break
        if walk.turn != mover and move.to_square == square and walk.piece_at(square) is not None:
            opp_captures_on_square.append(ply)
            if walk.piece_type_at(move.from_square) == chess.KING and king_ply is None:
                king_ply, king_from = ply, chess.square_name(move.from_square)
        walk.push(move)
    if king_ply is None:
        out["why_not"] = "no_king_recapture"
        return out
    out["king_takes_back_ply"], out["king_from"] = king_ply, king_from
    out["king_last"] = king_ply > 1

    # ---- check: the reply is the king stepping
    if king_to is None:
        out["why_not"] = "reply_not_king_move"
        return out
    out["king_to"] = king_to

    # ---- after: at the capture the king no longer attacks the square, and
    # nothing takes back there for the rest of the line. `board` stands just
    # before the better line's capture.
    king_square = board.king(not mover)
    if king_square is None or square in board.attacks(king_square):
        out["why_not"] = "king_still_guards"
        return out
    after = board.copy()
    after.push(parse_legal_move(board, capture_san))
    rest = alt_line[capture_ply + 1:LINE_HORIZON]
    for san in rest:
        move = parse_legal_move(after, san)
        if move is None:
            break
        if after.turn != mover and move.to_square == square:
            out["why_not"] = "still_recaptured"
            return out
        after.push(move)
    if not rest and any(m.to_square == square for m in after.legal_moves):
        # The line ends on the capture and a recapture is legal: unknown.
        out["why_not"] = "open_at_horizon"
        return out

    # ---- gain: the same ledger the material family reads
    from .differential import exchange_ledger
    name = out["square"]
    net_played = next((g["net_cp"] for g in exchange_ledger(root, played_line, mover) if g["square"] == name), None)
    net_better = next((g["net_cp"] for g in exchange_ledger(root, alt_line, mover) if g["square"] == name), None)
    out["net_played_cp"], out["net_better_cp"] = net_played, net_better
    if net_played is None or net_better is None or net_better - net_played < MIN_GAIN_CP:
        out["why_not"] = "no_gain_on_square"
        return out

    out["fires"] = True
    played_san, alt_san = root.san(played), root.san(alt)
    their = "their" if mover_is_user else "your"          # the side whose king it is
    you = "you" if mover_is_user else "they"
    piece = out["piece"]

    both = f"Both {played_san} and {alt_san} go for the {piece} on {name}."
    if out["king_last"]:
        after_played = (f"After {played_san}, the pieces come off on {name} and {their} king "
                        f"on {king_from} takes back last.")
    else:
        after_played = f"After {played_san}, {their} king on {king_from} takes back."
    if every_reply_is_king:
        the_check = f"{alt_san} first makes {their} king step away to {king_to}."
    else:
        the_check = f"After {alt_san} {their} king steps away to {king_to}."
    then = f"Then {capture_san} takes the {piece} and the king cannot take back."
    out["text"] = " ".join((both, after_played, the_check, then))

    from services.why_words import _RELATION, _owned
    out["facts"] = {
        "relation": _RELATION["CHECK_FIRST"],
        "the_square_both_moves_take_on": name,
        "the_piece_taken_there": _owned(their, piece),
        "after_the_move_played": f"{_owned(their, 'king')} on {king_from} takes back on {name}"
                                 + (", last" if out["king_last"] else ""),
        "what_the_check_does": f"{_owned(their, 'king')} steps away to {king_to}"
                               + (" because it has to" if every_reply_is_king else ""),
        "after_the_better_move": f"{capture_san} takes the {piece} and the king cannot take back",
        "who_takes_after_the_check": you,
    }
    out["consequence"] = {"mechanism": "CHECK_FIRST", "direction": "missed", "agent_move": alt_san,
                          "square": name, "victim_piece": piece, "victim_square": name,
                          "gained_piece": None, "payoff_cp": net_better - net_played,
                          "ply": capture_ply, "captures": [capture_san], "text": out["text"]}
    return out

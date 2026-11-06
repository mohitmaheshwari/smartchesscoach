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
          is not a capture; the better line takes the same piece on S with its
          very next move (check, king move, take)
  played  in the played line the opponent's KING makes a capture on S
  check   the reply to the check in the better line is a king move. If the
          king takes the checking piece, the check was a sacrifice and its
          cost is counted and said ("gives up a pawn to pull their king away")
  after   when the better line takes on S the king no longer attacks S, and
          nothing of the opponent's captures on S for the rest of the line
  gain    the exchange on S ends at least a pawn better for the mover in the
          better line than in the played line, after the cost of a sacrificed
          checking piece (the same ledger the material family uses)

Anything else is silent, and the measurement says which condition stopped it,
so a pass over many cards gives the fire-rate distribution. V1 covers the
king's recapture only; a check that removes another defender is a later
variant and stays silent here.

The first fire-rate pass (20,257 games, 2026-11-06) and a hand grade of 14
fired cards set three of those conditions. A capture that came two checks
later was worded as if it came at once (32f3573f m38, fa38efa7 m67), so the
capture must be the very next move. A rook given up on h1 to win a rook on
f1 was worded as a clean gain (6701f983 m24), so a sacrificed checking piece
is costed. A checking move that is itself a capture is a trade first and a
different story (game_a84 m6), so it is silent.

Engine-free: both lines are given. The Why button passes the lines its own
search produced; the caption facts pass the stored lines.
"""
from __future__ import annotations

from typing import Any, Dict, Sequence

import chess

from services.stored_line_verifier import parse_legal_move

PIECE_NAME = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
              chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}

# The better line has to take on the same square with its very next move:
# check, king move, take (ply 2). A capture that comes after a second check
# is a longer story than "check first, take second", and the sentence would
# skip a move pair.
CAPTURE_BY_PLY = 2
_VALUE = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300, chess.ROOK: 500, chess.QUEEN: 900}
# The rest of the better line is read this far for a recapture on the square,
# the same window the exchange ledger reads.
LINE_HORIZON = 12
# The exchange on the square must end at least a pawn better after the check.
MIN_GAIN_CP = 100


def _measure() -> Dict[str, Any]:
    return {"shape": False, "fires": False, "why_not": None, "square": None, "piece": None,
            "capture_san": None, "capture_ply": None, "king_from": None, "king_to": None,
            "king_takes_back_ply": None, "king_last": None, "check_forces_king": None,
            "sacrificed": None, "net_played_cp": None, "net_better_cp": None,
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
    if root.is_capture(alt):
        # A check that takes something is a trade or a win first; whatever
        # follows on S is a second story (game_a84 m6: Qxd8+ Kxd8 Nxf7+).
        out["why_not"] = "check_is_a_capture"
        return out
    out["square"] = chess.square_name(square)
    out["piece"] = PIECE_NAME[victim.piece_type]

    board = root.copy()
    board.push(alt)
    # The piece that now stands where the checking move went: what the king
    # takes if it takes there (a promoted piece counts as what it became).
    checker_type = board.piece_type_at(alt.to_square)
    every_reply_is_king = all(board.piece_type_at(m.from_square) == chess.KING for m in board.legal_moves)
    capture_ply = None
    capture_san = None
    king_to = None
    sacrificed = None
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
                if board.is_capture(move):
                    if move.to_square != alt.to_square:
                        # The king takes something else on its way: a
                        # different exchange, not this family's.
                        out["why_not"] = "reply_takes_material"
                        return out
                    sacrificed = PIECE_NAME.get(checker_type)
            break_after = False
        if break_after:
            break
        board.push(move)
    if capture_ply is None:
        out["why_not"] = "no_same_capture"
        return out
    out["sacrificed"] = sacrificed
    out["shape"] = True
    out["capture_san"], out["capture_ply"] = capture_san, capture_ply
    out["check_forces_king"] = every_reply_is_king

    # ---- played: the king takes back on the square
    # "Takes back" means the king's capture belongs to the exchange the played
    # move started: every move from the played capture up to it is a capture
    # on S. A king that wanders over and takes the piece many moves later
    # (d4b52618 m42: cxd3 a1=Q+ ... Kxd3) is another story.
    king_ply = None
    king_from = None
    walk = root.copy()
    for ply, san in enumerate(played_line[:LINE_HORIZON]):
        move = parse_legal_move(walk, san)
        if move is None:
            break
        on_square = move.to_square == square and walk.piece_at(square) is not None
        if ply >= 1 and not on_square:
            break                                  # the exchange on S is over
        if walk.turn != mover and on_square and walk.piece_type_at(move.from_square) == chess.KING:
            king_ply, king_from = ply, chess.square_name(move.from_square)
            break
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
    # Where the checking piece stands now, unless the king already took it or
    # it is the piece that made the capture on S.
    checker_square = None if (sacrificed or after.piece_at(alt.to_square) is None
                              or after.piece_at(alt.to_square).color != mover) else alt.to_square
    for san in rest:
        move = parse_legal_move(after, san)
        if move is None:
            break
        if after.turn != mover and move.to_square == square:
            out["why_not"] = "still_recaptured"
            return out
        if after.turn != mover and checker_square is not None and move.to_square == checker_square:
            # The check cost its piece a move or two later (bc7bb6bf m51:
            # Nd8+ Kd5 Rxb7 Rxd8). "Wins the pawn" would leave that out.
            out["why_not"] = "checker_lost_later"
            return out
        if after.turn == mover and checker_square is not None and move.from_square == checker_square:
            checker_square = move.to_square
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
    cost = _VALUE.get(checker_type, 0) if sacrificed else 0
    if net_played is None or net_better is None or net_better - net_played - cost < MIN_GAIN_CP:
        # 6701f983 m24: a rook given up on h1 to win a rook on f1 is no gain.
        out["why_not"] = "no_gain_after_sacrifice" if sacrificed else "no_gain_on_square"
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
    if sacrificed:
        # The king took the checking piece: say what the check cost.
        the_check = f"{alt_san} gives up a {sacrificed} to pull {their} king away to {king_to}."
    elif every_reply_is_king:
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
        "what_the_check_does": (
            f"it gives up a {sacrificed}, and {_owned(their, 'king')} takes it on {king_to}" if sacrificed
            else f"{_owned(their, 'king')} steps away to {king_to}"
                 + (" because it has to" if every_reply_is_king else "")),
        "after_the_better_move": f"{capture_san} takes the {piece} and the king cannot take back",
        "who_takes_after_the_check": you,
    }
    out["consequence"] = {"mechanism": "CHECK_FIRST", "direction": "missed", "agent_move": alt_san,
                          "square": name, "victim_piece": piece, "victim_square": name,
                          "gained_piece": None, "payoff_cp": net_better - net_played - cost,
                          "sacrificed_piece": sacrificed,
                          "ply": capture_ply, "captures": [capture_san], "text": out["text"]}
    return out

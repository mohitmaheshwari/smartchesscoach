"""
Board Concepts — deterministic detectors that name what actually happened
=========================================================================

74% of stored move observations use a generic subtype (`small_slip`,
`generic_endgame_slip`, `missed_generic_tactic`) that tells the player only that
something went wrong. This module exists to convert those into named chess
events, because "you didn't apply the rule of the square" teaches and
"generic_endgame_slip" does not.

WHY THESE FIVE
--------------
Each concept below is referenced by name across the codebase — `rule_of_square`
in 19 places, `opposition` in 29, `back_rank` in 48 — and has produced **zero**
observations in a corpus of 40,745. The vocabulary was built; the detection was
never written. These are the five, and every one of them is geometry or
arithmetic: no engine call, no model, no authoring.

CONTRACT
--------
Every function is a pure function of a `chess.Board`. Deterministic, side-effect
free, and safe to call on any legal position. Each returns either `None` (the
concept is not present) or a dict carrying the squares involved, so a caption can
name them rather than gesture at them.

Geometry that already exists lives in `services.caption_facts` (ray casting, pin
detection, passed pawns) and in `coach_play.coach_blunder_guard` (SEE). This
module never re-implements either.
"""

import logging
from typing import Any, Dict, List, Optional

import chess

logger = logging.getLogger(__name__)

# Pieces that can be "trapped" in a way worth teaching. A pawn with no moves is
# not a trapped piece, it is a pawn.
TRAPPABLE = (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)

# A trapped piece must be losing at least this much to be worth naming.
TRAPPED_FLOOR_CP = 150

PIECE_NAMES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king",
}


def _passed_pawns(board: chess.Board, color: chess.Color) -> List[int]:
    """Squares of `color`'s passed pawns.

    A pawn is passed when no enemy pawn stands on its file or either adjacent
    file, anywhere ahead of it.
    """
    out = []
    for sq in board.pieces(chess.PAWN, color):
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        blocked = False
        for ef in (f - 1, f, f + 1):
            if ef < 0 or ef > 7:
                continue
            for er in range(8):
                ahead = er > r if color == chess.WHITE else er < r
                if not ahead:
                    continue
                p = board.piece_at(chess.square(ef, er))
                if p and p.piece_type == chess.PAWN and p.color != color:
                    blocked = True
                    break
            if blocked:
                break
        if not blocked:
            out.append(sq)
    return out


def _steps_to_promote(sq: int, color: chess.Color) -> int:
    """Moves the pawn needs to reach the promotion rank, counting the initial
    double step when it is still on its starting rank."""
    r = chess.square_rank(sq)
    if color == chess.WHITE:
        steps = 7 - r
        if r == 1:
            steps -= 1
    else:
        steps = r
        if r == 6:
            steps -= 1
    return steps


def _path_clear(board: chess.Board, sq: int, color: chess.Color) -> bool:
    """Nothing standing on the pawn's file between it and promotion."""
    f = chess.square_file(sq)
    r = chess.square_rank(sq)
    ranks = range(r + 1, 8) if color == chess.WHITE else range(r - 1, -1, -1)
    for er in ranks:
        if board.piece_at(chess.square(f, er)):
            return False
    return True


def rule_of_the_square(board: chess.Board) -> Optional[Dict[str, Any]]:
    """Is there a passed pawn the defending king cannot catch?

    The classic rule: the pawn needs `steps` moves to promote, the king needs
    `king_dist` moves to reach the promotion square. The king catches it when
    `king_dist <= steps`, plus one tempo when it is the king's turn.

    Only fires on a clear path — a blocked pawn is a different lesson, and the
    rule does not apply to it.
    """
    for color in (chess.WHITE, chess.BLACK):
        defender = not color
        king_sq = board.king(defender)
        if king_sq is None:
            continue
        for pawn_sq in _passed_pawns(board, color):
            if not _path_clear(board, pawn_sq, color):
                continue
            steps = _steps_to_promote(pawn_sq, color)
            promo_sq = chess.square(
                chess.square_file(pawn_sq), 7 if color == chess.WHITE else 0
            )
            king_dist = chess.square_distance(king_sq, promo_sq)
            tempo = 1 if board.turn == defender else 0
            catches = king_dist <= steps + tempo
            if not catches:
                return {
                    "concept": "rule_of_square",
                    "pawn_square": chess.square_name(pawn_sq),
                    "promotion_square": chess.square_name(promo_sq),
                    "defending_king": chess.square_name(king_sq),
                    "pawn_steps": steps,
                    "king_distance": king_dist,
                    "pawn_color": "white" if color == chess.WHITE else "black",
                    "king_catches": False,
                }
    return None


def opposition(board: chess.Board) -> Optional[Dict[str, Any]]:
    """Are the kings in direct opposition, and who holds it?

    Direct opposition: same file, rank or diagonal with exactly one square
    between. The side NOT to move holds it — they have handed the other player
    the obligation to give way.

    Only meaningful once the queens are off and material is light; the caller
    decides that, this reports the geometry.
    """
    wk = board.king(chess.WHITE)
    bk = board.king(chess.BLACK)
    if wk is None or bk is None:
        return None

    wf, wr = chess.square_file(wk), chess.square_rank(wk)
    bf, br = chess.square_file(bk), chess.square_rank(bk)
    df, dr = abs(wf - bf), abs(wr - br)

    aligned = (df == 0 and dr == 2) or (dr == 0 and df == 2) or (df == 2 and dr == 2)
    if not aligned:
        return None

    holder = chess.BLACK if board.turn == chess.WHITE else chess.WHITE
    return {
        "concept": "opposition",
        "white_king": chess.square_name(wk),
        "black_king": chess.square_name(bk),
        "kind": "diagonal" if (df == 2 and dr == 2) else ("file" if df == 0 else "rank"),
        "held_by": "white" if holder == chess.WHITE else "black",
        "to_move": "white" if board.turn == chess.WHITE else "black",
    }


def pawn_race(board: chess.Board) -> Optional[Dict[str, Any]]:
    """Both sides have an uncatchable passed pawn — who promotes first?

    Counts tempi only. It does not evaluate what happens after both promote
    (a queen check, a skewer on the new queen), so callers must treat a narrow
    margin as inconclusive rather than as a result.
    """
    legs = {}
    for color in (chess.WHITE, chess.BLACK):
        best = None
        for pawn_sq in _passed_pawns(board, color):
            if not _path_clear(board, pawn_sq, color):
                continue
            steps = _steps_to_promote(pawn_sq, color)
            king_sq = board.king(not color)
            if king_sq is not None:
                promo_sq = chess.square(
                    chess.square_file(pawn_sq), 7 if color == chess.WHITE else 0
                )
                tempo = 1 if board.turn == (not color) else 0
                if chess.square_distance(king_sq, promo_sq) <= steps + tempo:
                    continue  # the king catches this one; it is not in the race
            if best is None or steps < best[1]:
                best = (pawn_sq, steps)
        if best:
            legs[color] = best

    if chess.WHITE not in legs or chess.BLACK not in legs:
        return None

    w_sq, w_steps = legs[chess.WHITE]
    b_sq, b_steps = legs[chess.BLACK]
    # The side to move effectively promotes a tempo sooner.
    w_eff = w_steps if board.turn == chess.WHITE else w_steps + 0.5
    b_eff = b_steps if board.turn == chess.BLACK else b_steps + 0.5

    return {
        "concept": "pawn_race",
        "white_pawn": chess.square_name(w_sq),
        "black_pawn": chess.square_name(b_sq),
        "white_steps": w_steps,
        "black_steps": b_steps,
        "leader": "white" if w_eff < b_eff else ("black" if b_eff < w_eff else "level"),
        "margin": abs(w_eff - b_eff),
        "to_move": "white" if board.turn == chess.WHITE else "black",
    }


def back_rank_weakness(board: chess.Board, color: chess.Color) -> Optional[Dict[str, Any]]:
    """`color`'s king is stuck on its back rank behind its own pawns.

    Reports the weakness (no luft) plus whether a heavy piece can actually
    exploit it, so a caption can distinguish "your king has no air" from
    "your king is about to be mated".
    """
    king_sq = board.king(color)
    if king_sq is None:
        return None
    back_rank = 0 if color == chess.WHITE else 7
    if chess.square_rank(king_sq) != back_rank:
        return None

    # Escape squares on the rank in front of the king.
    forward = 1 if color == chess.WHITE else -1
    kf = chess.square_file(king_sq)
    escapes = []
    blocked_by_own_pawn = 0
    for f in (kf - 1, kf, kf + 1):
        if f < 0 or f > 7:
            continue
        sq = chess.square(f, back_rank + forward)
        p = board.piece_at(sq)
        if p is None:
            escapes.append(chess.square_name(sq))
        elif p.color == color and p.piece_type == chess.PAWN:
            blocked_by_own_pawn += 1

    if escapes or blocked_by_own_pawn == 0:
        return None

    # Can a heavy enemy piece reach the back rank at all?
    threats = []
    for pt in (chess.ROOK, chess.QUEEN):
        for sq in board.pieces(pt, not color):
            for mv in board.attacks(sq):
                if chess.square_rank(mv) == back_rank:
                    threats.append(chess.square_name(sq))
                    break

    return {
        "concept": "back_rank",
        "king_square": chess.square_name(king_sq),
        "color": "white" if color == chess.WHITE else "black",
        "pawns_blocking": blocked_by_own_pawn,
        "heavy_pieces_bearing_down": sorted(set(threats)),
        "exploitable": bool(threats),
    }


def trapped_pieces(board: chess.Board, color: chess.Color) -> List[Dict[str, Any]]:
    """`color`'s pieces that are attacked and cannot get to safety.

    A piece is trapped when it is currently attacked and every legal move it has
    still loses at least `TRAPPED_FLOOR_CP`. Staying put must also lose material,
    otherwise it is merely restricted.

    This is the failure mode that eval-based detectors miss: the cause is board
    geometry, not the evaluation drop that follows it.
    """
    from coach_play.coach_blunder_guard import piece_value_cp, see_gain

    out = []
    if board.turn != color:
        return out  # only meaningful for the side that must find a square

    for sq in list(board.pieces(chess.KNIGHT, color)) + list(board.pieces(chess.BISHOP, color)) \
            + list(board.pieces(chess.ROOK, color)) + list(board.pieces(chess.QUEEN, color)):
        piece = board.piece_at(sq)
        if piece is None or piece.piece_type not in TRAPPABLE:
            continue
        if not board.is_attacked_by(not color, sq):
            continue

        # Cost of leaving it there: the opponent's best capture on this square.
        stay_cost = 0
        tmp = board.copy(stack=False)
        tmp.turn = not color
        for mv in tmp.legal_moves:
            if tmp.is_capture(mv) and mv.to_square == sq:
                g = see_gain(tmp, mv)
                if g > stay_cost:
                    stay_cost = g
        if stay_cost < TRAPPED_FLOOR_CP:
            continue

        # Can any move of this piece reach safety? Follow only this piece.
        # A global "material hung after" value is wrong here: an unrelated
        # loose piece can otherwise make every escape look unsafe.
        escaped = False
        for mv in board.legal_moves:
            if mv.from_square != sq:
                continue

            captured = board.piece_at(mv.to_square)
            capture_credit = (
                piece_value_cp(captured.piece_type)
                if captured is not None and captured.color != color
                else 0
            )

            after = board.copy(stack=False)
            after.push(mv)
            destination_loss = 0
            for reply in after.legal_moves:
                if after.is_capture(reply) and reply.to_square == mv.to_square:
                    destination_loss = max(
                        destination_loss,
                        see_gain(after, reply),
                    )

            # Trading the escaping piece for enemy material is not the same as
            # simply losing it. Credit what the escape captured before naming
            # the remaining net loss.
            net_loss = max(0, destination_loss - capture_credit)
            if net_loss < TRAPPED_FLOOR_CP:
                escaped = True
                break
        if escaped:
            continue

        out.append({
            "concept": "trapped_piece",
            "square": chess.square_name(sq),
            "piece": PIECE_NAMES[piece.piece_type],
            "color": "white" if color == chess.WHITE else "black",
            "cost_cp": stay_cost,
        })
    return out


def newly_trapped_pieces(
    board: chess.Board,
    move: chess.Move,
) -> List[Dict[str, Any]]:
    """Own pieces that become trapped as a direct state change of move.

    The post-move position is probed with the mover to move again because this
    function measures that side's escape geometry, not the real turn order.
    Capturability on the opponent's actual reply remains part of
    trapped_pieces via SEE.
    """
    if move not in board.legal_moves:
        return []

    color = board.turn
    before = {item["square"] for item in trapped_pieces(board, color)}

    after = board.copy(stack=False)
    after.push(move)
    probe = after.copy(stack=False)
    probe.turn = color

    return [
        item
        for item in trapped_pieces(probe, color)
        if item["square"] not in before
    ]


def detect_all(board: chess.Board) -> Dict[str, Any]:
    """Every concept present in one position.

    Callers should treat a concept's absence as "not detected", never as
    "not true" — these detectors are precise by design and deliberately silent
    when the geometry is ambiguous.
    """
    found: Dict[str, Any] = {}
    try:
        ros = rule_of_the_square(board)
        if ros:
            found["rule_of_square"] = ros
        opp = opposition(board)
        if opp:
            found["opposition"] = opp
        race = pawn_race(board)
        if race:
            found["pawn_race"] = race
        for color in (chess.WHITE, chess.BLACK):
            br = back_rank_weakness(board, color)
            if br and br["exploitable"]:
                found.setdefault("back_rank", []).append(br)
        trapped = trapped_pieces(board, board.turn)
        if trapped:
            found["trapped_piece"] = trapped
    except Exception as exc:  # a detector must never break analysis
        logger.warning("board_concepts.detect_all failed: %s", exc)
    return found

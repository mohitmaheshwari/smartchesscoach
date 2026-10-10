"""Deterministic families for mistakes the engine's own line cannot explain.

Mohit 2026-10-10: "i am not trying to fix all the problem with one issue, i
am trying to make familiies backed by stockfish."

That reframing is what makes these usable. Earlier attempts were measured as
DETECTORS -- does this fact appear more on bad moves than on good ones -- and
every one failed, including with the base rate removed by comparing the
played move against the engine's move in the same position:

    doubles your pawns       131 played-only vs 139 best-only   0.94x
    strips the king shield   470 vs 508                         0.93x
    isolates a pawn          111 vs  71                         1.56x
    leaves a piece loose     430 vs 311                         1.38x
    pawn can kick it         579 vs 452                         1.28x
    cuts your own mobility   348 vs 295                         1.18x

None of them CAUSES a mistake; Stockfish doubles its own pawns and opens its
own king as readily as a 1200 does. But that is the wrong question. Stockfish
has already ruled the move a mistake. These say which KIND, and the
comparison against the engine's move keeps the sentence honest: the family
only applies when YOUR move does it and the better move does not.

Measured over 1,737 quiet mistake cards (engine flagged it, its line shows no
material and no check): one of these covers 60.6%.

    less space         575  33.1%
    pawn kicks it      319  18.4%
    piece left loose   238  13.7%
    king opened        162   9.3%
    pawns doubled       35   2.0%
    pawn isolated       31   1.8%

Order matters: 269 of those cards match more than one, and a card leads with
exactly one. The order below is by size, which is a placeholder -- the real
order is a teaching judgement and is Mohit's to make.
"""
from __future__ import annotations

import collections
from typing import Dict, List, Optional

import chess

VALUES: Dict[int, int] = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100,
}
# How much of your own movement has to vanish before it is worth saying.
_MOBILITY_DROP = 2


def _pawn_files(board: chess.Board, colour: chess.Color):
    return collections.Counter(
        chess.square_file(sq) for sq in board.pieces(chess.PAWN, colour))


def doubled_pawns(board: chess.Board, colour: chess.Color) -> int:
    return sum(n - 1 for n in _pawn_files(board, colour).values() if n > 1)


def isolated_pawns(board: chess.Board, colour: chess.Color) -> int:
    files = _pawn_files(board, colour)
    return sum(1 for f in files
               if (f - 1) not in files and (f + 1) not in files)


def king_shield(board: chess.Board, colour: chess.Color) -> int:
    king = board.king(colour)
    if king is None:
        return 0
    return sum(
        1 for sq in chess.SQUARES
        if chess.square_distance(sq, king) == 1
        and (p := board.piece_at(sq))
        and p.color == colour and p.piece_type == chess.PAWN)


def piece_mobility(board: chess.Board, colour: chess.Color) -> int:
    """Squares the non-pawn pieces can see, own pieces excluded.

    attacks() is pseudo-legal -- it ignores pins -- which is right for "how
    much board does this side command" and is never used here to claim a
    capture is available.
    """
    total = 0
    own = board.occupied_co[colour]
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == colour and piece.piece_type != chess.PAWN:
            total += sum(1 for s in board.attacks(sq) if not (own >> s) & 1)
    return total


def loose_pieces(board: chess.Board, colour: chess.Color) -> int:
    """Attacked, and either undefended or attacked by something cheaper."""
    count = 0
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != colour or piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(not colour, sq)
        if not attackers:
            continue
        cheapest = min(VALUES[board.piece_at(s).piece_type] for s in attackers)
        if not board.attackers(colour, sq) or cheapest < VALUES[piece.piece_type]:
            count += 1
    return count


def pawn_can_kick(board: chess.Board, colour: chess.Color, square: int) -> bool:
    """Can an enemy PAWN attack this square with its next move?"""
    for move in board.legal_moves:
        piece = board.piece_at(move.from_square)
        if not piece or piece.piece_type != chess.PAWN or piece.color == colour:
            continue
        after = board.copy()
        after.push(move)
        if square in after.attacks(move.to_square):
            return True
    return False


# key, the words, and the test. Each test answers: does the PLAYED move do
# this where the engine's move does not?
FAMILIES = (
    ("less_space", "your pieces end up with less room"),
    ("pawn_kicks_it", "it lands where a pawn can chase it"),
    ("piece_left_loose", "it leaves one of your pieces loose"),
    ("king_opened", "it takes a pawn away from in front of your king"),
    ("pawns_doubled", "it doubles your pawns"),
    ("pawn_isolated", "it leaves a pawn with no neighbour"),
)


def all_families(fen: str, played_san: str, best_san: str) -> List[str]:
    """Every family the played move is in and the engine's move is not."""
    try:
        board = chess.Board(fen)
        mover = board.turn
        played = board.parse_san(str(played_san))
        best = board.parse_san(str(best_san))
    except Exception:  # noqa: BLE001
        return []
    after_played = board.copy()
    after_played.push(played)
    after_best = board.copy()
    after_best.push(best)
    hits: List[str] = []
    if piece_mobility(after_played, mover) < piece_mobility(after_best, mover) - _MOBILITY_DROP:
        hits.append("less_space")
    if (pawn_can_kick(after_played, mover, played.to_square)
            and not pawn_can_kick(after_best, mover, best.to_square)):
        hits.append("pawn_kicks_it")
    if loose_pieces(after_played, mover) > loose_pieces(after_best, mover):
        hits.append("piece_left_loose")
    if king_shield(after_played, mover) < king_shield(after_best, mover):
        hits.append("king_opened")
    if doubled_pawns(after_played, mover) > doubled_pawns(after_best, mover):
        hits.append("pawns_doubled")
    if isolated_pawns(after_played, mover) > isolated_pawns(after_best, mover):
        hits.append("pawn_isolated")
    return hits


def first_family(fen: str, played_san: str, best_san: str) -> Optional[str]:
    """The one a card would lead with, or None."""
    hits = all_families(fen, played_san, best_san)
    return hits[0] if hits else None


def is_unexplained(fen: str, played_san: str, best_san: str,
                   pv_after_played, pv_after_best) -> bool:
    """True when nothing we have can say why this move was bad.

    Three steps, in this order, because each one owns the card if it fires:

      1. the engine's own line tells the story (punishment / opportunity)
      2. one of the six families above covers it
      3. something concrete happens in the stored line -- material moves by
         two or more, or they give check

    Only a move that survives all three belongs in front of a human. Lives
    here rather than inside the route so the route and its tests ask the same
    question; the first version had this logic inline and the tests had to
    reach into a request handler to reach it.
    """
    pv_played = [str(x) for x in (pv_after_played or [])]
    pv_best = [str(x) for x in (pv_after_best or [])]
    if not fen or not played_san or not best_san or played_san == best_san:
        return False
    if len(pv_played) < 2:
        return False
    try:
        from services.caption_pipeline import classify_move_story
        story, _ = classify_move_story(fen, played_san, pv_played,
                                       pv_best, best_san)
    except Exception:  # noqa: BLE001
        return False
    if story in ("punishment", "opportunity"):
        return False
    try:
        if first_family(fen, played_san, best_san):
            return False
    except Exception:  # noqa: BLE001
        return False
    try:
        board = chess.Board(fen)
        mover = board.turn
        walk = board.copy()
        walk.push_san(played_san)
        net = 0
        for san in pv_played:
            move = walk.parse_san(san)
            theirs = walk.turn != mover
            if walk.is_capture(move):
                victim = walk.piece_at(move.to_square)
                value = VALUES.get(victim.piece_type, 1) if victim else 1
                net += value if theirs else -value
            if walk.gives_check(move) and theirs:
                return False
            walk.push(move)
    except Exception:  # noqa: BLE001
        return False
    return abs(net) < 2

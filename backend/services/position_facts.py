"""Deterministic facts for a move, for the cards no capture can explain.

Mohit 2026-10-08: "whenever you're not able to determine from punishment or
opportunity, we need to understand from these concepts". 358 of 1,748 flagged
moves in his last 100 games have no capture of his in the engine's line and no
capture on offer -- every material-shaped caption is blind on them, which is
why one of them told him his rook was "passive -- squeezed for space".

Two batches of 60 were explained by Claude against measured numbers, and both
independently reported the SAME missing facts. Those are what this module adds.
The ranking was a surprise and it is the reason the module looks like this:

    make their good piece move / stop ignoring it   23%
    time: the piece has to move again               20%
    the piece stopped doing its job                 16%
    the centre                                      14%
    king and development                            13%
    your own pieces get in each other's way         10%
    pawn structure                                   4%   <- what I had built

Tempo and initiative, not structure. The doubled-pawn, passed-pawn and
king-air numbers I wrote first were never once the reason a move was bad.

Everything here is counted on a board. Nothing infers, because the one thing
measured today is that I am reliable reporting what a probe printed and
unreliable the moment I work it out in my head.
docs/board_lesson_templates_scope.md
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import chess

VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
         chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

CENTRE = (chess.D4, chess.E4, chess.D5, chess.E5)
BIG_CENTRE = CENTRE + (chess.C4, chess.C5, chess.F4, chess.F5,
                       chess.D3, chess.E3, chess.D6, chess.E6)


# ── helpers ────────────────────────────────────────────────────────────────

def mobility_of(board: chess.Board, square: int) -> int:
    """How many moves the piece on this square has, whoever's turn it is."""
    piece = board.piece_at(square)
    if piece is None:
        return 0
    probe = board.copy()
    probe.turn = piece.color
    probe.clear_stack()
    return sum(1 for m in probe.legal_moves if m.from_square == square)


def can_a_pawn_ever_attack(board: chess.Board, square: int, by: bool) -> bool:
    """Is any enemy pawn still able, ever, to attack this square?

    Pure geometry: a pawn can only attack diagonally forward, so only pawns on
    the two neighbouring files, behind the square, can ever do it. This is the
    outpost test and the permanent-hole test, which are the same question
    asked from the two sides.
    """
    f, r = chess.square_file(square), chess.square_rank(square)
    rng = range(r + 1, 8) if by == chess.BLACK else range(0, r)
    for ff in (f - 1, f + 1):
        if not 0 <= ff <= 7:
            continue
        for rr in rng:
            p = board.piece_at(chess.square(ff, rr))
            if p and p.piece_type == chess.PAWN and p.color == by:
                return True
    return False


def _in_our_half(square: int, us: bool) -> bool:
    r = chess.square_rank(square)
    return r <= 3 if us == chess.WHITE else r >= 4


def _settle(board: chess.Board) -> chess.Board:
    """Let the obvious recapture happen before counting material.

    110 of 1,056 engine lines stop on a capture the other side answers at once.
    Material read at the raw last ply is wrong on every one of them -- it is
    what made me tell Mohit a losing line came out level.
    """
    out = board.copy()
    if not out.move_stack:
        return out
    last = out.peek().to_square
    recaps = [m for m in out.legal_moves if m.to_square == last]
    if recaps:
        out.push(min(recaps, key=lambda m: VALUE[out.piece_at(m.from_square).piece_type]))
    return out


def _walk(board: chess.Board, line: Sequence[str]) -> chess.Board:
    out = board.copy()
    for san in line:
        try:
            out.push_san(str(san))
        except (ValueError, AssertionError):
            break
    return out


# ── the facts both agents asked for ────────────────────────────────────────

def moves_again(board_after: chess.Board, square: int, line: Sequence[str],
                origin: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Does the piece that just moved have to move AGAIN inside the line?

    The most-used reason in both batches, about 20 of 120, and nothing saw it.
    A move that is answered by having to move the same piece again is a move
    that lost time, whatever else is true of it.
    """
    probe = board_after.copy()
    here = square
    for ply, san in enumerate(list(line or [])[:8], start=1):
        try:
            mv = probe.parse_san(str(san))
        except (ValueError, AssertionError):
            return None
        if mv.from_square == here:
            return {
                "ply": ply,
                "to": chess.square_name(mv.to_square),
                # Computed, not hardcoded. The first version shipped this as a
                # literal False on every row, including one where the queen
                # walked straight back to d8 -- a field that always says the
                # same thing is a field nobody can trust.
                "returns_home": mv.to_square == origin,
            }
        probe.push(mv)
    return None


def pawn_can_kick(board_after: chess.Board, square: int, us: bool) -> Optional[Dict[str, Any]]:
    """An enemy pawn one move away from attacking the square we just landed on.

    The CAUSE behind the time-loss family, and knowable at the moment of the
    move without any engine line at all.
    """
    for pawn_sq in board_after.pieces(chess.PAWN, not us):
        probe = board_after.copy()
        probe.turn = not us
        probe.clear_stack()
        for mv in probe.legal_moves:
            if mv.from_square != pawn_sq:
                continue
            landed = probe.copy()
            landed.push(mv)
            if square in landed.attacks(mv.to_square):
                return {
                    "pawn_on": chess.square_name(pawn_sq),
                    "goes_to": chess.square_name(mv.to_square),
                    "hits": chess.square_name(square),
                }
    return None


def unchallenged_enemy_pieces(board: chess.Board, us: bool) -> List[Dict[str, str]]:
    """Their pieces sitting in our half or the centre that no pawn of ours hits.

    Drove the single biggest family (23%). A 600-1500 player's commonest
    positional error is not noticing that a piece has simply moved in.
    """
    out = []
    for sq, piece in board.piece_map().items():
        if piece.color == us or piece.piece_type in (chess.PAWN, chess.KING):
            continue
        if not (_in_our_half(sq, us) or sq in BIG_CENTRE):
            continue
        hit_now = any(board.piece_at(a) and board.piece_at(a).piece_type == chess.PAWN
                      for a in board.attackers(us, sq))
        if hit_now:
            continue
        out.append({
            "piece": chess.piece_name(piece.piece_type),
            "square": chess.square_name(sq),
            "can_ever_be_hit_by_a_pawn": can_a_pawn_ever_attack(board, sq, us),
        })
    return out


def guard_changes(before: chess.Board, after: chess.Board, us: bool) -> List[Dict[str, Any]]:
    """Our own squares that lost a defender, including 'two guards became one'.

    A strict attackers>defenders test misses this, which is why the biggest
    Tier-1 family kept being described by the wrong fact.
    """
    out = []
    for sq, piece in before.piece_map().items():
        if piece.color != us or piece.piece_type == chess.KING:
            continue
        if after.piece_at(sq) is None or after.piece_at(sq).color != us:
            continue
        d0, d1 = len(before.attackers(us, sq)), len(after.attackers(us, sq))
        if d1 < d0:
            out.append({
                "square": chess.square_name(sq),
                "piece": chess.piece_name(piece.piece_type),
                "guards_before": d0, "guards_after": d1,
                "attackers_after": len(after.attackers(not us, sq)),
            })
    return out


def best_move_covers_extra(board: chess.Board, played: chess.Move,
                           best: Optional[chess.Move], us: bool) -> List[str]:
    """Squares the better move would watch that the played move does not.

    One agent called this the most informative number it computed, because it
    says what the better move was FOR, rather than only what the played move
    was against.
    """
    if best is None or best == played:
        return []
    a, b = board.copy(), board.copy()
    a.push(played)
    b.push(best)
    return sorted(chess.square_name(s) for s in
                  (set(b.attacks(best.to_square)) - set(a.attacks(played.to_square))))


def outpost_change(before: chess.Board, after: chess.Board, played: chess.Move,
                   us: bool) -> Dict[str, Any]:
    """Did we leave a square nothing can chase us off -- capture or not?

    The first cut only fired when the move was a capture, so a knight quietly
    walking off an outpost registered as nothing at all.
    """
    out: Dict[str, Any] = {"left_own_outpost": None}
    piece = before.piece_at(played.from_square)
    if piece is not None and not can_a_pawn_ever_attack(before, played.from_square, not us):
        if _in_our_half(played.from_square, not us) or played.from_square in BIG_CENTRE:
            out["left_own_outpost"] = {
                "square": chess.square_name(played.from_square),
                "piece": chess.piece_name(piece.piece_type),
                "moves_there": mobility_of(before, played.from_square),
                "moves_now": mobility_of(after, played.to_square),
            }
    return out


def enemy_gains_outpost(before: chess.Board, end: chess.Board, us: bool) -> List[Dict[str, str]]:
    """Their piece ends the line on a square our pawns can never attack."""
    out = []
    for sq, piece in end.piece_map().items():
        if piece.color == us or piece.piece_type in (chess.PAWN, chess.KING):
            continue
        if not (_in_our_half(sq, us) or sq in BIG_CENTRE):
            continue
        if can_a_pawn_ever_attack(end, sq, us):
            continue
        was = before.piece_at(sq)
        if was is not None and was.color != us:
            continue           # already sat there before our move
        out.append({"piece": chess.piece_name(piece.piece_type),
                    "square": chess.square_name(sq)})
    return out



def own_pieces_blocked(before: chess.Board, after: chess.Board, played: chess.Move,
                       us: bool) -> List[Dict[str, Any]]:
    """Our OTHER pieces that lost moves because of where this one went.

    Carries 10 of 160 labelled positions and both agents had to work it out by
    hand. mobility_* only ever described the piece that moved, so "the square
    you took is one your own piece needed" was invisible.
    """
    out = []
    for sq, piece in before.piece_map().items():
        if piece.color != us or sq == played.from_square:
            continue
        if after.piece_at(sq) is None or after.piece_at(sq).color != us:
            continue
        m0, m1 = mobility_of(before, sq), mobility_of(after, sq)
        if m1 < m0:
            out.append({
                "square": chess.square_name(sq),
                "piece": chess.piece_name(piece.piece_type),
                "moves_before": m0, "moves_after": m1,
                "frozen": m1 == 0,
            })
    out.sort(key=lambda d: d["moves_after"] - d["moves_before"])
    return out[:3]


def development_state(board: chess.Board, us: bool) -> Dict[str, Any]:
    """Minor pieces still at home, castling rights, where the king stands.

    Eleven development_delayed rows and five king_safety_postponed rows were
    read off the FEN by eye because nothing computed this.
    """
    home = 0 if us == chess.WHITE else 7
    minors = [sq for sq in list(board.pieces(chess.KNIGHT, us)) + list(board.pieces(chess.BISHOP, us))
              if chess.square_rank(sq) == home]
    king = board.king(us)
    return {
        "minors_still_home": len(minors),
        "can_castle_short": board.has_kingside_castling_rights(us),
        "can_castle_long": board.has_queenside_castling_rights(us),
        "king_square": chess.square_name(king) if king is not None else None,
        "king_still_home": king is not None and king == (chess.E1 if us == chess.WHITE else chess.E8),
    }


def best_move_played_later(board_after: chess.Board, best: Optional[chess.Move],
                           line: Sequence[str], us: bool) -> Optional[int]:
    """Do we play the engine's move anyway, a few plies late?

    The exact signature of losing a tempo: not a different plan, the same plan
    one move slower. moves_again saw the second move but never that it WAS the
    recommended one.
    """
    if best is None:
        return None
    probe = board_after.copy()
    for ply, san in enumerate(list(line or [])[:8], start=1):
        try:
            mv = probe.parse_san(str(san))
        except (ValueError, AssertionError):
            return None
        if probe.turn == us and mv == best:
            return ply
        probe.push(mv)
    return None


def squares_a_pawn_stopped_guarding(before: chess.Board, after: chess.Board,
                                    played: chess.Move, us: bool) -> List[str]:
    """A pawn push gives up the squares it used to watch.

    enemy_gains_outpost only sees squares no pawn can EVER reach, so everyday
    give-aways -- e5 no longer covering d4 and f4 -- were invisible.
    """
    piece = before.piece_at(played.from_square)
    if piece is None or piece.piece_type != chess.PAWN:
        return []
    lost = set(before.attacks(played.from_square)) - set(after.attacks(played.to_square))
    return sorted(chess.square_name(s) for s in lost
                  if not can_a_pawn_ever_attack(after, s, us))


def pawn_can_kick_anything(board_after: chess.Board, us: bool,
                           exclude: Optional[int] = None) -> Optional[Dict[str, str]]:
    """An enemy pawn one move from hitting ANY of our pieces, not just the
    one that just moved. The mirror the second agent asked for."""
    for sq, piece in board_after.piece_map().items():
        if piece.color != us or piece.piece_type in (chess.PAWN, chess.KING):
            continue
        if exclude is not None and sq == exclude:
            continue
        hit = pawn_can_kick(board_after, sq, us)
        if hit:
            return {**hit, "piece": chess.piece_name(piece.piece_type)}
    return None


# ── entry point ────────────────────────────────────────────────────────────

def extract(fen_before: str, played_san: str,
            line_after_played: Optional[Sequence[str]] = None,
            best_move_san: Optional[str] = None) -> Dict[str, Any]:
    """Every fact, measured. No conclusions -- the ordering is not mine to pick.

    Which fact outranks which, when several fire, comes out of the labelled
    corpus. Guessing that ordering is how a fork detector came to fire on a
    quarter of his games.
    """
    before = chess.Board(fen_before)
    us = before.turn
    played = before.parse_san(str(played_san))
    after = before.copy()
    after.push(played)

    best = None
    if best_move_san:
        try:
            best = before.parse_san(str(best_move_san))
        except (ValueError, AssertionError):
            best = None

    line = list(line_after_played or [])
    end = _settle(_walk(after, line))

    def bal(b: chess.Board) -> int:
        return (sum(VALUE[p.piece_type] for p in b.piece_map().values() if p.color == us)
                - sum(VALUE[p.piece_type] for p in b.piece_map().values() if p.color != us))

    f: Dict[str, Any] = {
        "material_before": bal(before),
        "material_end": bal(end),
        "material_swing": bal(end) - bal(before),
        "moved_piece": chess.piece_name(before.piece_at(played.from_square).piece_type),
        "from_square": chess.square_name(played.from_square),
        "to_square": chess.square_name(played.to_square),
        "mobility_from": mobility_of(before, played.from_square),
        "mobility_to": mobility_of(after, played.to_square),
        # The SAME line the caller will display. Handing extract() a longer
        # list than the reader sees puts facts on the card that point at moves
        # off the end of it: 23 of 164 rows claimed a ply-8 retreat nobody
        # could check.
        "moves_again": moves_again(after, played.to_square, line, played.from_square),
        "pawn_can_kick": pawn_can_kick(after, played.to_square, us),
        "unchallenged_before": unchallenged_enemy_pieces(before, us),
        "unchallenged_after": unchallenged_enemy_pieces(after, us),
        "guards_lost": guard_changes(before, after, us),
        "best_covers_extra": best_move_covers_extra(before, played, best, us),
        "enemy_gains_outpost": enemy_gains_outpost(before, end, us),
        "played_is_capture": before.is_capture(played),
        "played_gives_check": after.is_check(),
        "we_were_in_check": before.is_check(),
        "own_pieces_blocked": own_pieces_blocked(before, after, played, us),
        "development_before": development_state(before, us),
        "development_after": development_state(after, us),
        "best_move_played_later": best_move_played_later(after, best, line, us),
        "pawn_stopped_guarding": squares_a_pawn_stopped_guarding(before, after, played, us),
        "pawn_can_kick_another": pawn_can_kick_anything(after, us, exclude=played.to_square),
    }
    f.update(outpost_change(before, after, played, us))
    f["mobility_change"] = f["mobility_to"] - f["mobility_from"]
    return f

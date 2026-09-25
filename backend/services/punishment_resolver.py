"""Derive WHY a move was a mistake from the board, in both directions.

The rule, from Mohit 2026-09-24: *the why is the opponent's punishment.*
Our mistake -> what their reply collects. Their mistake -> what our reply
would have collected. One derivation, sides swapped.

Why this module exists at all
-----------------------------
`R12_blunder.json` answers "which of my ~100 sentences matches the flags
that happen to be set?" -- a flat priority list in which a formatting
variant and a statement of what the opponent won are peers. Measured
2026-09-24: on one position three entries were eligible at once, and
making a *fourth* true fact available rerouted the caption to a worse one.
A system where knowing more produces a worse answer is inverted.

So this module answers a different question -- "what did the move DO?" --
and picks between answers **by payoff size, never by list position**. That
single property is what makes added knowledge monotonically helpful.

Scenarios are unbounded; consequences are not. A chess board expresses
only material counts, attack maps, legal-move availability, king status
and promotion distance, so the closed set below is the whole space of
*measurable* punishments. Named motifs (Greek gift, Noah's Ark, back-rank)
each collapse into one or more of these.

Coverage over 2,500 analysed games / 24,577 mistakes, as first measured:
    direction "received"            46.5%
    + direction "missed"            57.4%   <- see the WARNING below
The "missed" half of that figure was measuring the wrong thing until the
2026-09-24 fix described on resolve_missed(); it needs re-measuring.

Whatever the number, a large remainder has no derivable why, and that is
NOT a licence to invent one. resolve_both() returns None, and callers must
say less rather than synthesise a story.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import chess

from services.caption_facts import (
    PIECE_VALUE_CP,
    _normalize_pv_starting_with,
)

# Ranked biggest payoff first. Order here IS the precedence, and it is a
# statement about chess (mate beats material beats tempo), not about which
# template someone wrote first.
MECHANISM_RANK: tuple = (
    "MATE",
    "WINS_MATERIAL",
    "FORK",
    "TRAPPED",
    "PROMOTES",
    "FORCES_RETREAT",
)

MINOR_CP = PIECE_VALUE_CP[chess.KNIGHT]
_MATE_PAYOFF = 100_000
_LINE_PLY = 6


@dataclass
class Punishment:
    """One derived consequence, carrying its own proof.

    `line` is the engine continuation the claim was read off. Verification
    replays it -- no caller should ever inspect the rendered prose to decide
    whether a claim is true.
    """

    direction: str           # "received" (they punished us) | "missed" (we could have)
    mechanism: str
    agent_move: str          # the move that does the damage, SAN
    payoff_cp: int
    line: List[str] = field(default_factory=list)
    victim_piece: Optional[str] = None
    victim_square: Optional[str] = None
    retreat_san: Optional[str] = None      # FORCES_RETREAT: where it must go
    returns_home: bool = False             # ...and it is the square it came from

    def as_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction,
            "mechanism": self.mechanism,
            "agent_move": self.agent_move,
            "payoff_cp": self.payoff_cp,
            "line": list(self.line),
            "victim_piece": self.victim_piece,
            "victim_square": self.victim_square,
            "retreat_san": self.retreat_san,
            "returns_home": self.returns_home,
        }


def _material(board: chess.Board, colour: bool) -> int:
    return sum(PIECE_VALUE_CP.get(p.piece_type, 0)
               for p in board.piece_map().values() if p.color == colour)


def _must_move(board: chess.Board, square: int, owner: bool) -> bool:
    """Is the piece on `square` obliged to move?

    Three ways, any one sufficient. The middle one is a body count and the
    outer two are not -- which matters, because a defender-count gate alone
    silences both a king in check (a king can never be defended) and every
    tempo attack (nobody trades a queen for a bishop however many pawns
    guard her).
    """
    piece = board.piece_at(square)
    if piece is None or piece.color != owner:
        return False
    attackers = board.attackers(not owner, square)
    if not attackers:
        return False
    if piece.piece_type == chess.KING:
        return True
    defenders = board.attackers(owner, square)
    if len(attackers) > len(defenders):
        return True
    cheapest = min(PIECE_VALUE_CP.get(board.piece_at(s).piece_type, 0)
                   for s in attackers if board.piece_at(s) is not None)
    return cheapest < PIECE_VALUE_CP.get(piece.piece_type, 0)


def _safe_squares(board: chess.Board, square: int, owner: bool) -> List[chess.Move]:
    """Destinations where the piece is not again won by a cheaper attacker."""
    piece = board.piece_at(square)
    if piece is None:
        return []
    value = PIECE_VALUE_CP.get(piece.piece_type, 0)
    out: List[chess.Move] = []
    for mv in board.legal_moves:
        if mv.from_square != square:
            continue
        probe = board.copy(stack=False)
        probe.push(mv)
        attackers = probe.attackers(not owner, mv.to_square)
        if not attackers:
            out.append(mv)
            continue
        cheapest = min(PIECE_VALUE_CP.get(probe.piece_at(s).piece_type, 0)
                       for s in attackers if probe.piece_at(s) is not None)
        if cheapest >= value and probe.attackers(owner, mv.to_square):
            out.append(mv)
    return out


def _net_victim_loss(pre: chess.Board, after: chess.Board,
                     victim: bool, aggressor: bool) -> Optional[str]:
    """Which piece the victim is NET down once the line is played out.

    WINS_MATERIAL is a net centipawn figure over a whole exchange, so it
    has no single victim -- which is why it shipped with victim_piece
    unset and every sentence read "wins your piece". That is a word with
    no information in it, and because the fallback never errored it read
    as a working caption for months.

    A net figure still has a nameable piece most of the time: take what
    each side actually lost over the line and cancel them off largest
    first. Whatever of the victim's is left unmatched is the piece they
    are genuinely down. Returns None when nothing survives the
    cancellation, and None must stay unnamed rather than be papered over.
    """
    def lost(colour: bool) -> List[int]:
        out: List[int] = []
        for piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP,
                           chess.KNIGHT, chess.PAWN):
            gone = (len(pre.pieces(piece_type, colour))
                    - len(after.pieces(piece_type, colour)))
            out.extend([piece_type] * max(0, gone))
        return out

    theirs = sorted(lost(victim),
                    key=lambda t: PIECE_VALUE_CP.get(t, 0), reverse=True)
    ours = sorted(lost(aggressor),
                  key=lambda t: PIECE_VALUE_CP.get(t, 0), reverse=True)

    # Cancel biggest against biggest; an even trade tells the player
    # nothing, so it must not be described as a piece they lost.
    for spent in ours:
        for i, taken in enumerate(theirs):
            if PIECE_VALUE_CP.get(taken, 0) <= PIECE_VALUE_CP.get(spent, 0):
                theirs.pop(i)
                break
    if not theirs:
        return None
    return chess.piece_name(theirs[0])


def _consequences(
    pre: chess.Board,
    agent_move: chess.Move,
    line: Sequence[str],
    victim: bool,
    direction: str,
    agent_san: str,
    victim_origin: Optional[int] = None,
    material_baseline_cp: int = 0,
) -> Optional[Punishment]:
    """What does `agent_move` DO to `victim`?

    `pre` is the board immediately BEFORE agent_move; `line` is the engine
    continuation from the position after it. Everything is measured against
    `victim`, and that parameter is the whole reason one routine serves both
    directions: the punishment we received (victim = us) and the one we
    missed (victim = them).
    """
    post = pre.copy(stack=False)
    post.push(agent_move)
    aggressor = not victim

    found: Dict[str, Punishment] = {}

    def offer(mech: str, payoff: int, **kw: Any) -> None:
        cur = found.get(mech)
        if cur is None or payoff > cur.payoff_cp:
            found[mech] = Punishment(direction=direction, mechanism=mech,
                                     agent_move=agent_san, payoff_cp=payoff,
                                     line=list(line[:_LINE_PLY]), **kw)

    # --- MATE -----------------------------------------------------------
    if post.is_checkmate():
        offer("MATE", _MATE_PAYOFF)
    else:
        mate_board = post.copy(stack=False)
        for san in line[:_LINE_PLY]:
            try:
                mate_board.push(mate_board.parse_san(str(san or "").strip()))
            except (ValueError, AssertionError, KeyError):
                break
            if mate_board.is_checkmate() and mate_board.turn == victim:
                offer("MATE", _MATE_PAYOFF)
                break

    # --- WINS_MATERIAL ---------------------------------------------------
    # Net over the whole line, so an exchange the victim recaptures does NOT
    # read as material won. A single-ply diff counts every even trade, which
    # measured 42% of mistakes instead of the true 29.8%.
    line_board = post.copy(stack=False)
    for san in line[:_LINE_PLY]:
        try:
            line_board.push(line_board.parse_san(str(san or "").strip()))
        except (ValueError, AssertionError, KeyError):
            break
    net = ((_material(line_board, victim) - _material(line_board, aggressor))
           - (_material(pre, victim) - _material(pre, aggressor)))
    # `material_baseline_cp` is what the move actually played already wins.
    # Without it the "missed" direction credits the engine's move with
    # material the played move collects too: 13...dxe5 and 13...Nxe5 both take
    # the same pawn, and both lines win more later, so the raw figure fired on
    # positions where the two moves are materially identical. Only the surplus
    # is a punishment the player MISSED.
    gain = -net - material_baseline_cp
    if gain > 0:
        offer("WINS_MATERIAL", gain,
              victim_piece=_net_victim_loss(pre, line_board, victim, aggressor))

    # --- FORK ------------------------------------------------------------
    hit = [sq for sq in post.attacks(agent_move.to_square)
           if (pc := post.piece_at(sq)) is not None and pc.color == victim
           and PIECE_VALUE_CP.get(pc.piece_type, 0) >= MINOR_CP]
    if len(hit) >= 2 or (post.is_check() and hit):
        best_hit = max(hit, key=lambda sq: PIECE_VALUE_CP.get(
            post.piece_at(sq).piece_type, 0), default=None)
        offer("FORK",
              PIECE_VALUE_CP.get(post.piece_at(best_hit).piece_type, MINOR_CP)
              if best_hit is not None else MINOR_CP,
              victim_piece=(chess.piece_name(post.piece_at(best_hit).piece_type)
                            if best_hit is not None else None),
              victim_square=(chess.square_name(best_hit)
                             if best_hit is not None else None))

    # --- TRAPPED / FORCES_RETREAT ----------------------------------------
    for square, piece in list(post.piece_map().items()):
        if piece.color != victim or piece.piece_type == chess.KING:
            continue
        if PIECE_VALUE_CP.get(piece.piece_type, 0) < MINOR_CP:
            continue          # a pawn with no safe square is normal
        attackers = post.attackers(aggressor, square)
        # Caused BY the move: either the moved piece attacks it, or the square
        # was not attacked at all before the move landed.
        if agent_move.to_square not in attackers and pre.attackers(aggressor, square):
            continue
        if not _must_move(post, square, victim):
            continue
        escapes = _safe_squares(post, square, victim)
        name = chess.piece_name(piece.piece_type)
        where = chess.square_name(square)
        value = PIECE_VALUE_CP.get(piece.piece_type, 0)
        if not escapes:
            offer("TRAPPED", value, victim_piece=name, victim_square=where)
            continue
        # Tempo, not material -- payoff is deliberately small so any real
        # material consequence outranks it.
        retreat_san = None
        returns_home = False
        if line:
            try:
                nxt = post.parse_san(str(line[0] or "").strip())
                if nxt.from_square == square:
                    retreat_san = str(line[0]).strip()
                    returns_home = (victim_origin is not None
                                    and nxt.to_square == victim_origin)
            except (ValueError, AssertionError, KeyError):
                pass
        offer("FORCES_RETREAT", max(1, value // 10), victim_piece=name,
              victim_square=where, retreat_san=retreat_san,
              returns_home=returns_home)

    # --- PROMOTES ---------------------------------------------------------
    if any("=" in str(m or "") for m in line[:_LINE_PLY]):
        offer("PROMOTES", PIECE_VALUE_CP[chess.QUEEN])

    for mech in MECHANISM_RANK:
        if mech in found:
            return found[mech]
    return None


def resolve_received(
    fen_before: str, played_san: str, pv_after_played: Sequence[str]
) -> Optional[Punishment]:
    """What their reply collects after our mistake. Victim = us.

    `pv_after_played[0]` is their reply; the rest is the continuation.
    """
    if not (fen_before and played_san and pv_after_played):
        return None
    try:
        board = chess.Board(fen_before)
        played = board.parse_san(played_san)
    except (ValueError, AssertionError, KeyError):
        return None
    mover = board.piece_at(played.from_square)
    if mover is None:
        return None
    us = mover.color
    # Stored PVs are inconsistent: some records lead with the played move,
    # some with the opponent's reply (measured 2026-09-24 -- pv_after_played
    # was ['Nxe5','dxe5',...] on one move and ['Kg1','Na6',...] on another).
    # Reading pv[0] as the reply misparsed the first kind into a different
    # legal move and produced a confident, wrong answer. Normalise first;
    # canonical form leads with the move itself, so the reply is pv[1].
    # Stored PVs are inconsistent: some records lead with the played move,
    # some with the opponent's reply (measured 2026-09-24 -- pv_after_played
    # was ['Nxe5','dxe5',...] on one move and ['Kg1','Na6',...] on another).
    #
    # SAN matching cannot separate them, because on a RECAPTURE the reply
    # very often carries the same SAN as the move played (13...Nxe5 answered
    # by 14.Nxe5). Legality can: decide by asking whether the first entry is
    # a legal move for the OPPONENT in the position after ours.
    board.push(played)
    pv = [str(x or "").strip() for x in pv_after_played if str(x or "").strip()]
    if not pv:
        return None
    reply = None
    try:
        reply = board.parse_san(pv[0])
        rest = pv[1:]
    except (ValueError, AssertionError, KeyError):
        reply = None
    if reply is None:
        # Not playable by them -> the list led with our own move; drop it.
        if len(pv) < 2:
            return None
        try:
            reply = board.parse_san(pv[1])
        except (ValueError, AssertionError, KeyError):
            return None
        rest = pv[2:]
        reply_san = pv[1]
    else:
        reply_san = pv[0]
    return _consequences(board, reply, rest, us,
                         "received", reply_san,
                         victim_origin=played.from_square)


def _line_material_gain(fen_before: str, move_san: str,
                        line: Sequence[str]) -> int:
    """How much material the MOVER nets over `move_san` plus `line`."""
    try:
        board = chess.Board(fen_before)
        mv = board.parse_san(move_san)
    except (ValueError, AssertionError, KeyError):
        return 0
    piece = board.piece_at(mv.from_square)
    if piece is None:
        return 0
    us = piece.color
    before = _material(board, us) - _material(board, not us)
    board.push(mv)
    for san in _normalize_pv_starting_with(move_san, list(line))[1:][:_LINE_PLY]:
        try:
            board.push(board.parse_san(str(san or "").strip()))
        except (ValueError, AssertionError, KeyError):
            break
    return (_material(board, us) - _material(board, not us)) - before


def resolve_missed(
    fen_before: str,
    best_san: str,
    pv_after_best: Sequence[str],
    material_baseline_cp: int = 0,
) -> Optional[Punishment]:
    """What OUR best move would have collected. Victim = them.

    This is the half that was wrong until 2026-09-24. Both directions used
    to measure consequences against the MOVER, so this one asked "what do
    they do to us after our best move" instead of "what would we have won".

    It was caught on game_74fdbd74c468 move 26 (26...g5, -417cp): Black was
    +4.45, the engine's 26...Qd3 wins a knight via 27.Nc2 Rxf3 28.Qxf3
    Qxc2+, and the old code returned None -- so a decided, explainable
    blunder landed in the "no why" queue as unexplainable.
    """
    if not (fen_before and best_san):
        return None
    try:
        board = chess.Board(fen_before)
        best = board.parse_san(best_san)
    except (ValueError, AssertionError, KeyError):
        return None
    mover = board.piece_at(best.from_square)
    if mover is None:
        return None
    them = not mover.color
    pv = _normalize_pv_starting_with(best_san, list(pv_after_best or []))
    return _consequences(board, best, pv[1:], them,
                         "missed", str(best_san).strip(),
                         material_baseline_cp=material_baseline_cp)


def resolve(
    fen_before: str,
    move_san: str,
    pv: Sequence[str],
    direction: str = "received",
) -> Optional[Punishment]:
    """Back-compat entry point; prefer the two explicit functions."""
    if direction == "missed":
        return resolve_missed(fen_before, move_san, pv)
    return resolve_received(fen_before, move_san, pv)


def resolve_both(
    fen_before: str,
    played_san: str,
    best_san: Optional[str],
    pv_after_played: Sequence[str],
    pv_after_best: Sequence[str],
) -> Optional[Punishment]:
    """The punishment we took, else the one we missed, else None.

    None is a real answer and must be honoured: callers name the better move
    and stop -- they do not reach for a principle to fill the slot. Every
    hallucinated caption audited on 2026-09-24 came from a caller treating
    None as "say something anyway".
    """
    got = resolve_received(fen_before, played_san, pv_after_played)
    if got is not None:
        return got
    if best_san:
        baseline = _line_material_gain(fen_before, played_san,
                                       pv_after_played or [])
        return resolve_missed(fen_before, best_san, pv_after_best or [],
                              material_baseline_cp=max(0, baseline))
    return None

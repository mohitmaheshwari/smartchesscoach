"""Derive WHY a move was a mistake from the board, in both directions.

The rule, from Mohit 2026-09-24: *the why is the opponent's punishment.*
Our mistake -> what their reply collects. Their mistake -> what our reply
would have collected. One derivation, sides swapped.

Why this module exists at all
-----------------------------
`R12_blunder.json` answers "which of my ~100 sentences matches the flags
that happen to be set?" — a flat priority list in which a formatting
variant and a statement of what the opponent won are peers. Measured
2026-09-24: on one position three entries were eligible at once, and
making a *fourth* true fact available rerouted the caption to a worse one.
A system where knowing more produces a worse answer is inverted.

So this module answers a different question — "what did the reply DO?" —
and picks between answers **by payoff size, never by list position**. That
single property is what makes added knowledge monotonically helpful.

Scenarios are unbounded; consequences are not. A chess board expresses
only material counts, attack maps, legal-move availability, king status
and promotion distance, so the closed set below is the whole space of
*measurable* punishments. Named motifs (Greek gift, Noah's Ark, back-rank)
each collapse into one or more of these.

Coverage, measured over 2,500 analysed games / 24,577 mistakes:
    direction "received"            46.5%
    + direction "missed"            57.4%
    remainder has no derivable why  42.6%
The remainder is NOT a licence to invent one. See resolve_both() — it
returns None, and callers must say less rather than synthesise a story.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import chess

from services.caption_facts import PIECE_VALUE_CP, static_exchange_eval

# Ranked biggest payoff first. Order here IS the precedence, and it is a
# statement about chess (mate beats material beats tempo), not about which
# template someone wrote first.
MECHANISM_RANK: tuple[str, ...] = (
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
    replays it — no caller should ever inspect the rendered prose to decide
    whether a claim is true.
    """

    direction: str           # "received" (they punished us) | "missed" (we could have)
    mechanism: str
    agent_move: str          # the punishing move, SAN
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
    outer two are not — which matters, because a defender-count gate alone
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


def resolve(
    fen_before: str,
    move_san: str,
    pv: Sequence[str],
    direction: str = "received",
) -> Optional[Punishment]:
    """Play `move_san`, then the reply in `pv[0]`, and report what it DID.

    `pv` is the engine line *after* `move_san` — index 0 is the opponent's
    reply, index 1 is what the mover must play next. Returns the
    highest-payoff mechanism, or None when nothing measurable happened.
    """
    if not fen_before or not move_san or not pv:
        return None
    try:
        board = chess.Board(fen_before)
        played = board.parse_san(move_san)
    except (ValueError, AssertionError, KeyError):
        return None
    mover = board.piece_at(played.from_square)
    if mover is None:
        return None
    us = mover.color
    them = not us
    board.push(played)

    try:
        reply = board.parse_san(str(pv[0] or "").strip())
    except (ValueError, AssertionError, KeyError, IndexError):
        return None
    after = board.copy(stack=False)
    after.push(reply)

    found: Dict[str, Punishment] = {}

    def offer(mech: str, payoff: int, **kw: Any) -> None:
        cur = found.get(mech)
        if cur is None or payoff > cur.payoff_cp:
            found[mech] = Punishment(direction=direction, mechanism=mech,
                                     agent_move=str(pv[0]).strip(),
                                     payoff_cp=payoff, line=list(pv[:_LINE_PLY]),
                                     **kw)

    # --- MATE -----------------------------------------------------------
    if after.is_checkmate():
        offer("MATE", _MATE_PAYOFF)

    # --- WINS_MATERIAL --------------------------------------------------
    # Net over the whole stored line, so a trade they initiate and we
    # recapture does NOT read as material won. A single-ply diff counts
    # every even exchange as a punishment; measured, that inflated this
    # bucket from 29.8% to 42%.
    line_board = board.copy(stack=False)
    for san in pv[:_LINE_PLY]:
        try:
            line_board.push(line_board.parse_san(str(san or "").strip()))
        except (ValueError, AssertionError, KeyError):
            break
    net = ((_material(line_board, us) - _material(line_board, them))
           - (_material(board, us) - _material(board, them)))
    if net < 0:
        offer("WINS_MATERIAL", -net)

    # --- FORK -----------------------------------------------------------
    hit = [s for s in after.attacks(reply.to_square)
           if (p := after.piece_at(s)) is not None and p.color == us
           and PIECE_VALUE_CP.get(p.piece_type, 0) >= MINOR_CP]
    if len(hit) >= 2 or (after.is_check() and hit):
        best_hit = max(hit, key=lambda s: PIECE_VALUE_CP.get(
            after.piece_at(s).piece_type, 0), default=None)
        offer("FORK", PIECE_VALUE_CP.get(after.piece_at(best_hit).piece_type, MINOR_CP)
              if best_hit is not None else MINOR_CP,
              victim_piece=(chess.piece_name(after.piece_at(best_hit).piece_type)
                            if best_hit is not None else None),
              victim_square=(chess.square_name(best_hit)
                             if best_hit is not None else None))

    # --- TRAPPED / FORCES_RETREAT ---------------------------------------
    for square, piece in list(after.piece_map().items()):
        if piece.color != us or piece.piece_type == chess.KING:
            continue
        if PIECE_VALUE_CP.get(piece.piece_type, 0) < MINOR_CP:
            continue          # a pawn with no safe square is normal, not a punishment
        # The punishment must be CAUSED by the reply: either the reply's own
        # piece attacks it, or it was not attacked before the reply landed.
        attackers = after.attackers(them, square)
        if reply.to_square not in attackers and board.attackers(them, square):
            continue
        if not _must_move(after, square, us):
            continue
        escapes = _safe_squares(after, square, us)
        name = chess.piece_name(piece.piece_type)
        where = chess.square_name(square)
        value = PIECE_VALUE_CP.get(piece.piece_type, 0)
        if not escapes:
            offer("TRAPPED", value, victim_piece=name, victim_square=where)
            continue
        # Tempo, not material — payoff is deliberately small so any real
        # material consequence outranks it.
        retreat_san = None
        returns_home = False
        if len(pv) > 1:
            try:
                nxt = after.parse_san(str(pv[1] or "").strip())
                if nxt.from_square == square:
                    retreat_san = str(pv[1]).strip()
                    returns_home = nxt.to_square == played.from_square
            except (ValueError, AssertionError, KeyError):
                pass
        offer("FORCES_RETREAT", max(1, value // 10), victim_piece=name,
              victim_square=where, retreat_san=retreat_san,
              returns_home=returns_home)

    # --- PROMOTES -------------------------------------------------------
    if any("=" in str(m or "") for m in pv[:_LINE_PLY]):
        offer("PROMOTES", PIECE_VALUE_CP[chess.QUEEN])

    for mech in MECHANISM_RANK:
        if mech in found:
            return found[mech]
    return None


def resolve_both(
    fen_before: str,
    played_san: str,
    best_san: Optional[str],
    pv_after_played: Sequence[str],
    pv_after_best: Sequence[str],
) -> Optional[Punishment]:
    """The punishment we took, else the one we missed, else None.

    None is a real answer and must be honoured: ~42% of engine-confirmed
    mistakes have no derivable consequence in either direction. Callers name
    the better move and stop — they do not reach for a principle to fill the
    slot. Every hallucinated caption audited on 2026-09-24 came from a
    caller treating None as "say something anyway".
    """
    got = resolve(fen_before, played_san, pv_after_played, "received")
    if got is not None:
        return got
    if best_san and pv_after_best:
        return resolve(fen_before, best_san, pv_after_best, "missed")
    return None

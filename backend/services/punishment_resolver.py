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
    legal_exchange_gain,
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


def _is_quiet(board: chess.Board, landed: Optional[int]) -> bool:
    """Nothing hanging from the move that just landed on `landed`."""
    if board.is_check():
        return False
    if landed is None:
        return True
    return not any(m.to_square == landed for m in board.legal_moves)


def _walk_to_quiet(start: chess.Board, line: Sequence[str],
                   max_ply: int,
                   landed_on: Optional[int] = None) -> Optional[chess.Board]:
    """Replay `line`, then stop at the last position where nothing is hanging
    from the move that just happened.

    Counting material at a fixed ply counts it mid-exchange. Mohit's move 7
    e5, 2026-10-21: the "Why was this bad?" button said "After e5, dxe5 wins
    your knight" with a payoff of 400, while the engine's own verdict for the
    move was cp_loss 100. The quoted line is

        dxe5  Nxe5  Nxd5  Nxf3+  Bxf3  c6  Nxf6+

    and `_LINE_PLY` is 6, which lands exactly on `Nxf6+` -- a capture, with
    check, and the recapture still to come. Black plays gxf6 next and the
    balance is one pawn, which is what cp_loss said all along.

    Quiet here means two board facts, both cheap: the side to move is not in
    check, and it has no capture onto the square the previous move landed on.
    That is the same bar the arrows already answer to -- a payoff has to
    survive the recapture -- applied to the number the sentence quotes.

    Walking BACK rather than extending the line is deliberate: the engine gave
    us these moves and inventing a recapture it did not play would be a
    different line, judged by us instead of by it.

    `landed_on` is the square the move that produced `start` arrived on, so
    the starting position is judged by the same rule as every later one. Without
    it a one-move line ending in an un-recaptured capture banks the piece --
    "Qxd5 wins a queen" with Kxd5 waiting.

    Returns `(quiet, final)` -- the last settled position, or None when there
    is none in range, alongside the end of the walk.

    Callers take whichever reading claims LESS. That rule is not a detail.
    Measured over 3,521 cards, backing off to the quiet position on its own
    changed 5.5% of them but ADDED 53 material claims and raised 60 payoffs,
    and sent more readings further from the engine's own cp_loss (54) than
    closer to it (44). Of course it did: stopping earlier can stop before the
    compensation arrives, which is the same error as stopping mid-exchange,
    pointing the other way. A guard against overclaiming may never manufacture
    a claim, so it is allowed to lower a number and never to raise one.
    """
    board = start.copy(stack=False)
    quiet = board.copy(stack=False) if _is_quiet(board, landed_on) else None
    for san in list(line)[:max_ply]:
        try:
            move = board.parse_san(str(san or "").strip())
        except (ValueError, AssertionError, KeyError):
            break
        board.push(move)
        if _is_quiet(board, move.to_square):
            quiet = board.copy(stack=False)
    return quiet, board


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

    # Name the COUNT as well as the piece. Returning only the largest
    # unmatched piece undercounted: on game_b5d23694a803 move 13, dxe5
    # nets 200cp -- two pawns -- and this said "pawn", so the caption read
    # "dxe5 wins their pawn" where the shipping caption said "two pawns"
    # and was right. Verified by replaying both captures to depth 18:
    # Nxe5 nets +100, dxe5 nets +200. Naming one piece of several is a
    # quieter wrong answer than the vague "piece" it replaced, which is
    # worse, because it reads precise.
    same = [t for t in theirs
            if PIECE_VALUE_CP.get(t, 0) == PIECE_VALUE_CP.get(theirs[0], 0)]
    name = chess.piece_name(theirs[0])
    if len(same) == 1:
        return name
    # Spelled out, never a digit, and only for counts a player can picture.
    words = {2: "two", 3: "three", 4: "four"}
    if len(same) in words:
        return f"{words[len(same)]} {name}s"
    return f"several {name}s"


def _fork_survives(
    post: chess.Board,
    agent_move: chess.Move,
    line: Sequence[str],
    aggressor: bool,
    victim: bool,
) -> bool:
    """Is one of the forked pieces still winnable after the victim answers?

    Returns True only when, after the victim's first reply, the forking piece
    still attacks a victim piece worth at least a minor AND taking it actually
    gains material once the exchange is played out.

    With no reply stored we cannot tell, and a fork claim is exactly the kind
    that measurement showed is usually answered, so the silent direction is to
    refuse it.
    """
    if not line:
        return False
    board = post.copy(stack=False)
    try:
        reply = board.parse_san(str(line[0]))
    except (ValueError, AssertionError):
        return False
    board.push(reply)
    # The forking piece may itself have been captured by the reply.
    forker = board.piece_at(agent_move.to_square)
    if forker is None or forker.color != aggressor:
        return False
    probe = board.copy(stack=False)
    if probe.is_check():
        return False
    try:
        probe.push(chess.Move.null())      # hand the aggressor the move back
    except Exception:
        return False
    for square in board.attacks(agent_move.to_square):
        piece = board.piece_at(square)
        if piece is None or piece.color != victim:
            continue
        if PIECE_VALUE_CP.get(piece.piece_type, 0) < MINOR_CP:
            continue
        try:
            if (legal_exchange_gain(probe, square, aggressor) or 0) >= MINOR_CP:
                return True
        except (ValueError, TypeError):
            continue
    return False


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
    quiet_board, final_board = _walk_to_quiet(
        post, line, _LINE_PLY, landed_on=agent_move.to_square)
    baseline_mat = _material(pre, victim) - _material(pre, aggressor)

    def _net(board):
        return ((_material(board, victim) - _material(board, aggressor))
                - baseline_mat)

    # No quiet point in range means the material is still in flight, so there
    # is no claim to make; otherwise take whichever reading claims less. `net`
    # is the VICTIM's swing, so the smaller claim is the LARGER net.
    if quiet_board is None:
        net, net_board = 0, final_board
    elif _net(quiet_board) >= _net(final_board):
        net, net_board = _net(quiet_board), quiet_board
    else:
        net, net_board = _net(final_board), final_board
    # `material_baseline_cp` is what the move actually played already wins.
    # Without it the "missed" direction credits the engine's move with
    # material the played move collects too: 13...dxe5 and 13...Nxe5 both take
    # the same pawn, and both lines win more later, so the raw figure fired on
    # positions where the two moves are materially identical. Only the surplus
    # is a punishment the player MISSED.
    gain = -net - material_baseline_cp
    if gain > 0:
        offer("WINS_MATERIAL", gain,
              victim_piece=_net_victim_loss(pre, net_board, victim, aggressor))  # the SAME board the number came from

    # --- FORK ------------------------------------------------------------
    # A fork has to survive the victim's reply. This branch tested the board
    # the instant after agent_move and never asked what they answer -- the same
    # defect as the "attacks the X" reasons fixed in v184.
    #
    # There is also a structural reason to doubt every fork that gets this far:
    # WINS_MATERIAL outranks FORK in MECHANISM_RANK and measures net material
    # across the WHOLE line, so a fork that actually collected something would
    # have been claimed as material first. A fork reaching a caption therefore
    # implies the line nets nothing. Measured over 400 games, 177 captions chose
    # FORK and NOT ONE of them won material: median net 0, zero at or above
    # 100cp, against WINS_MATERIAL's median +100 and 79%. Some were outright
    # bad for the forker -- Qxd4 there nets -300.
    #
    # So the fork must still be winnable after they reply, and `_fork_survives`
    # plays that out instead of trusting the snapshot.
    hit = [sq for sq in post.attacks(agent_move.to_square)
           if (pc := post.piece_at(sq)) is not None and pc.color == victim
           and PIECE_VALUE_CP.get(pc.piece_type, 0) >= MINOR_CP]
    if hit and not _fork_survives(post, agent_move, line, aggressor, victim):
        hit = []
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
        # Only claim a forced retreat the line actually shows. `retreat_san`
        # is set just above when the victim's answer moves THIS piece, so it
        # already encodes "they really do move it" -- it was merely decorative
        # before, and the claim fired whether or not it was set.
        #
        # Measured over 400 games: of 861 FORCES_RETREAT claims, 601 (69%) are
        # borne out by the line and 260 (30%) name a retreat the opponent never
        # makes. Requiring the field turns a 69%-true claim into a true one.
        # The same defect as the "attacks the X" reasons in v184 and the FORK
        # branch above, in its mildest form: _must_move answers "can this piece
        # stay?" on a snapshot, which is not the same question as "do they move
        # it?"
        # ...and it must actually be a retreat. `retreat_san` only proves the
        # piece MOVED, which is a different question. A piece that answers an
        # attack by taking something is counter-attacking, and calling that a
        # retreat is backwards:
        #
        #   "drives their bishop back"  ->  they play Bxh4
        #   "drives their queen back"   ->  they play Qxa8
        #   "drives their knight back"  ->  they play Nxf3+   with check
        #
        # Measured over 400 games on 423 of these claims: not one piece
        # returned home and 45.9% moved FORWARD. Found on Mohit's own position,
        # where "d4 drives their knight back" described c3 -> e4.
        retreat_is_a_capture = False
        if retreat_san:
            try:
                retreat_is_a_capture = post.is_capture(
                    post.parse_san(str(retreat_san)))
            except (ValueError, AssertionError, KeyError):
                retreat_is_a_capture = True      # cannot read it, do not claim it
        if retreat_san and not retreat_is_a_capture:
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
    # Same rule as the WINS_MATERIAL branch, and for the same reason: a count
    # taken mid-exchange banks a piece that is about to be taken back. Both
    # read through one helper so the two can never disagree about where it is
    # safe to count. The move itself is walked here rather than pushed first,
    # so its OWN recapture is judged like any other.
    settled, final = _walk_to_quiet(
        board, _normalize_pv_starting_with(move_san, list(line)),
        _LINE_PLY + 1)
    if settled is None:
        return 0            # nothing settled in range: no claim to make
    # The smaller claim of the two, for the reason in _walk_to_quiet: this
    # guard may lower a number, never raise one.
    return min((_material(settled, us) - _material(settled, not us)) - before,
               (_material(final, us) - _material(final, not us)) - before)


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

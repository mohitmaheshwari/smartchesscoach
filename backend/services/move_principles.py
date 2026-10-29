"""Why the better move was better: facts that SEPARATE it from the move played.

The idea, from Mohit on 2026-10-29, after a day in which six positional
mechanisms were written and five died: do not ask what is true about the move
played. Ask what is true about the engine's preferred moves and **not** true
about the played one, and the reverse.

That inversion is the whole design. Each of those five families failed with the
same signature -- the engine's own best move had the identical property:

    Nd5 vacates the same square as Na4;  Kb1 raises king pressure like Ka2;
    h3 is the same wing pawn push as b4, at 0cp where b4 costs 59;
    Kf4 releases d3 like Kf3;  Qh5+ releases g7 like Qf5+.

A property measured on ONE move is nearly independent of the evaluation gap
between TWO moves, so a good move shares it about as often as a bad one.
Comparing makes a shared fact unselectable by construction: the negative
control stops being a review step we must remember and becomes the selector.

Nothing here reads an evaluation number, calls an engine, or decides that a
move was bad. Stockfish decides THAT; these functions only say WHAT DIFFERS.

Principles are grouped into THEMES and the selector works on themes, because
one coaching idea often has several board forms. Mohit stated the first one
that way himself -- "either do a development move, get a minor piece out or
make space for other minor piece to come out" -- and the data needs it: on his
position Nf3 and Bg2 develop while d3 frees, so no single test covers all three
of the engine's good moves, and the theme covers all three.

Scope, evidence and the pass mark every principle must clear before it is
allowed to speak: docs/differential_why_engine_scope.md. The four principles
here are derived from ONE position and verified only there; that is exactly why
the selector requires separation rather than trusting them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import chess

# A minor's starting squares. "Development" is only meaningful against them.
HOME_MINORS: Dict[bool, Tuple[int, ...]] = {
    chess.WHITE: (chess.B1, chess.C1, chess.F1, chess.G1),
    chess.BLACK: (chess.B8, chess.C8, chess.F8, chess.G8),
}
MINOR_TYPES = (chess.KNIGHT, chess.BISHOP)


@dataclass(frozen=True)
class Fact:
    """One principle firing on one move.

    `detail` is plain board language for the sentence layer to phrase; it is
    never prose to be shipped as-is, and it carries no evaluation number.

    `polarity` says which direction the fact can be read in, and it exists
    because the first measured run got this wrong. Over 12 positions the
    selector faulted 2 of 33 engine-APPROVED moves, and both were
    `received/development`: the played move developed a minor and the
    alternatives did not, so the asymmetry was real -- and emitting it as a
    fault says "you brought a piece out" in the voice of an accusation.

    A virtue is only ever a `missed` answer: you should have developed.
    A fault is only ever a `received` answer: your move gave the square away.
    Separation alone is not enough; the direction has to mean something.
    """
    principle: str
    theme: str
    detail: str
    subject: Optional[str] = None
    polarity: str = "fault"        # "virtue" | "fault"


@dataclass(frozen=True)
class Separation:
    """A theme that tells the played move apart from the engine's choices.

    direction "missed"   : true of every good move, false of the played move
                           -- why the better move was better
    direction "received" : true of the played move, false of every good move
                           -- what your move did
    """
    theme: str
    direction: str
    facts: Tuple[Fact, ...]
    good_moves: Tuple[str, ...]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _squares_available(board: chess.Board, square: int) -> int:
    """How many squares the piece on `square` can move to.

    Counted from the attack set minus our own men, NOT from legal_moves. Two
    reasons, and the second is the important one:

      * asking legal_moves means flipping board.turn, which can make the
        position invalid when the other king is in check, and the count then
        silently becomes zero;
      * this number is only ever used as a DIFFERENCE between two positions
        that differ by one move, so a systematic simplification (ignoring
        pins) cancels, while an occasional invalid board does not.

    Verified against the real thing on the position this came from: a bishop
    on c1 behind a pawn on d2 counts 0 squares, and 5 after d3 -- which is what
    board.legal_moves reports there.
    """
    piece = board.piece_at(square)
    if piece is None:
        return 0
    own = board.occupied_co[piece.color]
    return chess.popcount(int(board.attacks(square)) & ~own)


def _home_minors(board: chess.Board, colour: bool) -> Tuple[int, ...]:
    out = []
    for sq in HOME_MINORS[colour]:
        pc = board.piece_at(sq)
        if pc is not None and pc.color == colour and pc.piece_type in MINOR_TYPES:
            out.append(sq)
    return tuple(out)


def _can_ever_guard(board: chess.Board, colour: bool, target: int) -> bool:
    """Could any pawn of `colour` ever come to control `target`?

    A pawn controls the two squares diagonally ahead of it, so it can only ever
    guard `target` from one rank behind it on an adjacent file. A pawn that has
    already marched past that rank can never come back -- which is what makes
    the answer permanent rather than a snapshot.
    """
    tf = chess.square_file(target)
    tr = chess.square_rank(target)
    guard_rank = tr - 1 if colour == chess.WHITE else tr + 1
    if not 0 <= guard_rank <= 7:
        return False
    for sq, pc in board.piece_map().items():
        if pc.color != colour or pc.piece_type != chess.PAWN:
            continue
        if abs(chess.square_file(sq) - tf) != 1:
            continue
        r = chess.square_rank(sq)
        if (r <= guard_rank) if colour == chess.WHITE else (r >= guard_rank):
            return True
    return False


def _pawn_guards_from(colour: bool, square: int) -> Tuple[int, ...]:
    """The squares a pawn of `colour` standing on `square` would control."""
    f = chess.square_file(square)
    r = chess.square_rank(square)
    ahead = r + 1 if colour == chess.WHITE else r - 1
    if not 0 <= ahead <= 7:
        return ()
    return tuple(chess.square(nf, ahead)
                 for nf in (f - 1, f + 1) if 0 <= nf <= 7)


def _name(sq: int) -> str:
    return chess.square_name(sq)


# --------------------------------------------------------------------------
# the principles
# --------------------------------------------------------------------------
def develops_a_minor(board: chess.Board, move: chess.Move) -> Optional[Fact]:
    """The move brings a minor piece off its starting square."""
    pc = board.piece_at(move.from_square)
    if pc is None or pc.piece_type not in MINOR_TYPES:
        return None
    if move.from_square not in HOME_MINORS[pc.color]:
        return None
    return Fact(
        principle="develops_a_minor", theme="development",
        detail="brings the %s on %s into the game"
               % (chess.piece_name(pc.piece_type), _name(move.from_square)),
        subject=_name(move.from_square), polarity="virtue")


def frees_a_buried_minor(board: chess.Board,
                         move: chess.Move) -> Optional[Fact]:
    """A minor of ours that could not move at all now can.

    Zero to non-zero, PER PIECE -- never a total. A first version counted the
    squares available to all home minors together, and that version scored both
    e3 and e4 as freeing moves on Mohit's position: each vacates e2 and so
    hands the g1 knight one extra square, while leaving the c1 bishop buried. A
    knight that already has f3 and h3 does not need e2; a bishop with nothing
    needs a diagonal. The per-piece reading is what separates d3 from e3.
    """
    pc = board.piece_at(move.from_square)
    if pc is None:
        return None
    me = pc.color
    before = {sq: _squares_available(board, sq)
              for sq in _home_minors(board, me)}
    if not any(n == 0 for n in before.values()):
        return None
    after = board.copy(stack=False)
    after.push(move)
    for sq, n in before.items():
        if n != 0 or sq == move.from_square:
            continue
        still = after.piece_at(sq)
        if still is None or still.color != me or \
                still.piece_type not in MINOR_TYPES:
            continue
        gained = _squares_available(after, sq)
        if gained > 0:
            return Fact(
                principle="frees_a_buried_minor", theme="development",
                detail="opens a way out for the %s on %s, which had none"
                       % (chess.piece_name(still.piece_type), _name(sq)),
                subject=_name(sq), polarity="virtue")
    return None


def sells_a_square_forever(board: chess.Board,
                           move: chess.Move) -> Optional[Fact]:
    """A pawn push that gives up a square no pawn of ours can ever guard again.

    Only a straight push, never a capture: a capture changes the file and the
    bookkeeping with it, and nothing yet measured says it belongs here.

    The squares at stake are the ones the pawn would have controlled had it
    stopped short. A single push stops nowhere, so it sells nothing; a double
    push skips a rank, and whatever that skipped square would have guarded is
    what is given up -- provided no OTHER pawn of ours can ever guard it.

    On Mohit's position, e2-e4 skips e3, which would have guarded d4 and f4.
    The g3 pawn already guards f4, so f4 is not sold; nothing can ever guard d4
    again, because the c-pawn is on c4 and has passed c3. So the test
    discriminates within a single move, not merely between moves.
    """
    pc = board.piece_at(move.from_square)
    if pc is None or pc.piece_type != chess.PAWN:
        return None
    if board.is_capture(move) or move.promotion is not None:
        return None
    if chess.square_file(move.from_square) != chess.square_file(move.to_square):
        return None
    me = pc.color

    step = 1 if me == chess.WHITE else -1
    f = chess.square_file(move.from_square)
    r0 = chess.square_rank(move.from_square)
    r1 = chess.square_rank(move.to_square)
    skipped = [chess.square(f, r) for r in range(r0 + step, r1, step)]
    if not skipped:
        return None

    after = board.copy(stack=False)
    after.push(move)
    after.ep_square = None

    sold = []
    for mid in skipped:
        for target in _pawn_guards_from(me, mid):
            if not _can_ever_guard(board, me, target):
                continue            # it was never ours to give away
            if _can_ever_guard(after, me, target):
                continue            # another pawn still covers it
            sold.append(target)
    if not sold:
        return None
    # The dearest square first: the one the opponent already controls and we do
    # not. Ordering only; the claim is the same either way.
    sold.sort(key=lambda s: (-len(after.attackers(not me, s)),
                             len(after.attackers(me, s))))
    first = sold[0]
    return Fact(
        principle="sells_a_square_forever", theme="square_control",
        detail="gives up %s for good -- no pawn of ours can ever guard it again"
               % _name(first),
        subject=_name(first))


def buries_own_piece(board: chess.Board, move: chess.Move) -> Optional[Fact]:
    """A piece of ours that could move before this move cannot move after it."""
    pc = board.piece_at(move.from_square)
    if pc is None:
        return None
    me = pc.color
    after = board.copy(stack=False)
    after.push(move)
    for sq, p in board.piece_map().items():
        if p.color != me or p.piece_type in (chess.PAWN, chess.KING):
            continue
        if sq == move.from_square:
            continue
        still = after.piece_at(sq)
        if still is None or still.color != me or \
                still.piece_type != p.piece_type:
            continue
        if _squares_available(board, sq) > 0 and _squares_available(after, sq) == 0:
            return Fact(
                principle="buries_own_piece", theme="own_mobility",
                detail="leaves our own %s on %s with nowhere to go"
                       % (chess.piece_name(p.piece_type), _name(sq)),
                subject=_name(sq))
    return None


# Each principle, with the phases in which the idea means anything. "Get your
# minors out" is an opening statement; in a four-piece endgame it talks
# nonsense, so the gate is declared here rather than left to the caller.
PRINCIPLES: Tuple[Tuple[Callable[[chess.Board, chess.Move], Optional[Fact]],
                        Tuple[str, ...]], ...] = (
    (develops_a_minor, ("opening",)),
    (frees_a_buried_minor, ("opening",)),
    (sells_a_square_forever, ("opening", "middlegame")),
    (buries_own_piece, ("opening", "middlegame", "endgame")),
)


def facts_for(board: chess.Board, move: chess.Move,
              phase: Optional[str] = None) -> Tuple[Fact, ...]:
    """Every principle that fires on this move, phase gate applied."""
    out = []
    for fn, phases in PRINCIPLES:
        if phase is not None and phase not in phases:
            continue
        try:
            fact = fn(board, move)
        except Exception:
            fact = None          # a principle may decline, never explode
        if fact is not None:
            out.append(fact)
    return tuple(out)


# --------------------------------------------------------------------------
# the selector
# --------------------------------------------------------------------------
def separating_themes(
    fen_before: str,
    played_san: str,
    good_sans: Sequence[str],
    phase: Optional[str] = None,
) -> List[Separation]:
    """Themes that tell the played move apart from the engine's good moves.

    `good_sans` are moves the engine approves of -- the caller decides what
    "approves" means (a closeness window on the evaluation) because that is an
    engine question, not a board one.

    A theme is returned only when it holds for EVERY good move and for none of
    the played move, or the exact reverse. Requiring every good move is the
    strict reading on purpose: a theme true of one good move out of four has
    not told us what the engine wanted, and the whole value of this design is
    that a fact shared with a good move cannot be selected.

    Empty list is a real answer and means we have nothing to say.
    """
    try:
        board = chess.Board(fen_before)
    except ValueError:
        return []
    try:
        played = board.parse_san(str(played_san or "").strip())
    except (ValueError, AssertionError, KeyError):
        return []

    good: List[Tuple[str, chess.Move]] = []
    for san in good_sans:
        san = str(san or "").strip()
        if not san or san == str(played_san or "").strip():
            continue
        try:
            good.append((san, board.parse_san(san)))
        except (ValueError, AssertionError, KeyError):
            continue
    if not good:
        return []

    played_facts = facts_for(board, played, phase)
    played_themes = {f.theme: f for f in played_facts}

    good_facts = {san: facts_for(board, mv, phase) for san, mv in good}
    good_themes: Dict[str, Dict[str, Fact]] = {
        san: {f.theme: f for f in facts} for san, facts in good_facts.items()}

    themes = {t for _, fs in good_themes.items() for t in fs}
    themes |= set(played_themes)

    out: List[Separation] = []
    for theme in sorted(themes):
        in_played = theme in played_themes
        holds_for = [san for san in good_themes if theme in good_themes[san]]
        all_good = len(holds_for) == len(good_themes)
        none_good = not holds_for

        # Polarity decides which reading is allowed. A virtue the played move
        # happens to have and the alternatives do not is a real asymmetry and
        # not a fault -- 2 of 33 approved moves were faulted that way before
        # this gate existed, both of them for bringing a piece out.
        if all_good and not in_played:
            facts = tuple(good_themes[san][theme] for san in good_themes)
            if facts[0].polarity != "virtue":
                continue
            out.append(Separation(
                theme=theme, direction="missed", facts=facts,
                good_moves=tuple(good_themes)))
        elif in_played and none_good:
            fact = played_themes[theme]
            if fact.polarity != "fault":
                continue
            out.append(Separation(
                theme=theme, direction="received", facts=(fact,),
                good_moves=tuple(good_themes)))
    return out

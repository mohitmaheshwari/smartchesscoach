"""Play any line on the review board (docs/play_any_line_scope.md).

The student moves a piece from a position of their game; the board answers
with the engine's best reply. This module turns one such step into words a
student can read, using only things the board or the engine proves:

  * the student's move: a verdict from the rating table
    (rating_resolver.move_classification_thresholds, the one table every
    surface uses) plus what the move does on the board;
  * the reply: what it does on the board -- takes, checks, mates, and new
    attacks that matter (an unguarded target, or one worth more than the
    attacker), with a piece standing behind the target on the same line and
    a line opened by the student's previous move;
  * a running count of what changed hands, only at a quiet point (the engine
    line shows no capture in the next four plies), so a count is never read in
    the middle of an exchange.

The deeper "why is this a mistake" sentence is NOT made here. It comes from
the why button's engine (services/why_differential.py) through the route's
second call, because it takes seconds and the reply must not wait for it.

Nothing here invents a reason. When there is nothing provable to say about a
move, the step carries no sentence and the board still plays it with an arrow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import chess
import chess.engine

from services.rating_resolver import move_classification_thresholds

PIECE_WORD = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king",
}
VALUE = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100,
}
MATE_SCORE = 10000
# A count of what changed hands is shown only when the engine line has no
# capture in this many plies after the reply.
QUIET_PLIES = 4
# At most this many attacked targets are named for one move.
MAX_TARGETS = 2


class LineError(ValueError):
    """The line the client sent does not replay."""


# ---------------------------------------------------------------- replay

def replay(start_fen: str, moves_san: Sequence[str]) -> Tuple[chess.Board, List[chess.Move]]:
    """The board after `moves_san` from `start_fen`, and the moves played."""
    try:
        board = chess.Board(start_fen)
    except ValueError as exc:
        raise LineError(f"bad position: {exc}") from exc
    played: List[chess.Move] = []
    for san in moves_san:
        try:
            mv = board.parse_san(san)
        except ValueError as exc:
            raise LineError(f"illegal move in line: {san}") from exc
        board.push(mv)
        played.append(mv)
    return board, played


def game_positions(pgn_text: str, initial_fen: Optional[str] = None) -> set:
    """Every position of the game, as the first four FEN fields.

    The line must start from a position the game actually reached, so the
    endpoint cannot be used as a free engine for any position.
    """
    import io

    import chess.pgn

    out = set()
    game = chess.pgn.read_game(io.StringIO(pgn_text or ""))
    if game is None:
        return out
    board = game.board()
    out.add(_key(board.fen()))
    for mv in game.mainline_moves():
        board.push(mv)
        out.add(_key(board.fen()))
    return out


def _key(fen: str) -> str:
    return " ".join(fen.split()[:4])


def position_in_game(fen: str, positions: set) -> bool:
    return _key(fen) in positions


# ---------------------------------------------------------------- words

def _owner(color: chess.Color, user_color: chess.Color) -> str:
    return "your" if color == user_color else "their"


def _sq(square: int, notation: bool) -> str:
    return f" on {chess.square_name(square)}" if notation else ""


def _defended(board: chess.Board, square: int, color: chess.Color) -> bool:
    """Is the piece of `color` on `square` guarded by its own side?"""
    return bool(board.attackers(color, square))


def _ray_squares(a: int, b: int) -> List[int]:
    """Squares strictly between a and b on a rank, file or diagonal."""
    between = chess.SquareSet(chess.between(a, b))
    return list(between)


def _behind(board: chess.Board, attacker_sq: int, target_sq: int) -> Optional[int]:
    """The first piece beyond `target_sq` on the line from the attacker."""
    piece = board.piece_at(attacker_sq)
    if piece is None or piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return None
    df = chess.square_file(target_sq) - chess.square_file(attacker_sq)
    dr = chess.square_rank(target_sq) - chess.square_rank(attacker_sq)
    step_f = (df > 0) - (df < 0)
    step_r = (dr > 0) - (dr < 0)
    f, r = chess.square_file(target_sq) + step_f, chess.square_rank(target_sq) + step_r
    while 0 <= f < 8 and 0 <= r < 8:
        sq = chess.square(f, r)
        if board.piece_at(sq) is not None:
            return sq
        f += step_f
        r += step_r
    return None


@dataclass
class Target:
    square: int
    piece: chess.Piece
    attacker: int
    behind: Optional[int] = None
    opened_by: Optional[int] = None  # the square the previous move left


def meaningful_attacks(board_after: chess.Board, move: chess.Move,
                       previous: Optional[chess.Move] = None,
                       board_before: Optional[chess.Board] = None) -> List[Target]:
    """New attacks by the side that just moved that matter.

    A target matters when it is unguarded, or worth more than the piece
    attacking it. Kings are left to "check". Only attacks that did not exist
    before the move are named, and only by the moved piece or by a piece whose
    line the move (or the previous move) opened.
    """
    mover = not board_after.turn
    before = board_before
    found: Dict[int, Target] = {}
    for sq, piece in board_after.piece_map().items():
        if piece.color == mover or piece.piece_type == chess.KING:
            continue
        for att in board_after.attackers(mover, sq):
            a_piece = board_after.piece_at(att)
            if a_piece is None:
                continue
            new = True
            if before is not None and att == move.to_square:
                # The moved piece already hit this square from where it stood.
                if sq in before.attacks(move.from_square) and sq != move.to_square:
                    new = False
            if before is not None and att != move.to_square:
                # Attacked already before this move by the same piece: not new.
                b_piece = before.piece_at(att)
                if b_piece is not None and b_piece == a_piece and att in before.attackers(mover, sq):
                    new = False
            if not new:
                continue
            unguarded = not _defended(board_after, sq, piece.color)
            if not (unguarded or VALUE[piece.piece_type] > VALUE[a_piece.piece_type]):
                continue
            ray = _ray_squares(att, sq)
            opened = None
            if att != move.to_square:
                if move.from_square in ray:
                    opened = move.from_square
                elif previous is not None and previous.from_square in ray:
                    opened = previous.from_square
                else:
                    continue  # not this move's doing
            elif previous is not None and previous.from_square in ray:
                opened = previous.from_square
            behind = _behind(board_after, att, sq)
            if behind is not None:
                bp = board_after.piece_at(behind)
                if bp is None or bp.color != piece.color or VALUE[bp.piece_type] <= VALUE[piece.piece_type]:
                    behind = None
            t = Target(square=sq, piece=piece, attacker=att, behind=behind, opened_by=opened)
            old = found.get(sq)
            if old is None or VALUE[a_piece.piece_type] < VALUE[board_after.piece_at(old.attacker).piece_type]:
                found[sq] = t
    targets = sorted(found.values(), key=lambda t: -VALUE[t.piece.piece_type])[:MAX_TARGETS]
    # A target with a piece behind it is named last, so "behind it" reads with
    # its own target and not the next one (2026-11-18 grade, item 21).
    targets.sort(key=lambda t: t.behind is not None)
    return targets


def _target_words(board: chess.Board, t: Target, user_color: chess.Color, notation: bool) -> str:
    words = f"{_owner(t.piece.color, user_color)} {PIECE_WORD[t.piece.piece_type]}"
    if t.piece.piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK):
        words += _sq(t.square, notation)
    if t.behind is not None:
        bp = board.piece_at(t.behind)
        words += (f", with {_owner(bp.color, user_color)} {PIECE_WORD[bp.piece_type]}"
                  f"{_sq(t.behind, notation)} behind it")
    return words


def _join(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def describe(board_before: chess.Board, move: chess.Move, user_color: chess.Color, *,
             previous: Optional[chess.Move] = None,
             previous_board: Optional[chess.Board] = None,
             notation: bool = True) -> List[str]:
    """Plain sentences for what `move` does, each a board fact. May be empty."""
    mover = board_before.turn
    san = board_before.san(move)
    after = board_before.copy()
    after.push(move)
    if after.is_checkmate():
        return [f"{san} is checkmate."]
    out: List[str] = []
    takes = None
    if board_before.is_capture(move):
        cap_sq = move.to_square
        if board_before.is_en_passant(move):
            cap_sq = chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square))
        captured = board_before.piece_at(cap_sq)
        if captured is not None:
            check_now = after.is_check()
            takes = (f"{san} takes {_owner(captured.color, user_color)} "
                     f"{PIECE_WORD[captured.piece_type]}{_sq(cap_sq, notation)}"
                     f"{' with check' if check_now else ''}.")
            # The captured piece was attacking one of the mover's pieces.
            for sq in board_before.attacks(cap_sq):
                p = board_before.piece_at(sq)
                if p is None or p.color != mover or p.piece_type == chess.KING:
                    continue
                if _defended(board_before, sq, mover) and VALUE[p.piece_type] <= VALUE[captured.piece_type]:
                    continue
                what = ("it" if sq == move.from_square else
                        f"{_owner(mover, user_color)} {PIECE_WORD[p.piece_type]}{_sq(sq, notation)}")
                takes += f" That {PIECE_WORD[captured.piece_type]} was attacking {what}."
                break
    check = after.is_check()
    if takes:
        out.append(takes)
    elif check:
        out.append(f"{san} gives check.")

    targets = meaningful_attacks(after, move, previous=previous, board_before=board_before)
    prev_vacated = previous.from_square if previous is not None else None
    direct = [t for t in targets
              if t.attacker == move.to_square and (prev_vacated is None or t.opened_by != prev_vacated)]
    reopened = [t for t in targets if prev_vacated is not None and t.opened_by == prev_vacated]
    uncovered = [t for t in targets if t.attacker != move.to_square and t.opened_by == move.from_square]

    if direct:
        lead = "It also attacks" if out else f"{san} attacks"
        out.append(f"{lead} {_join([_target_words(after, t, user_color, notation) for t in direct])}.")
    if reopened and previous_board is not None:
        mp = previous_board.piece_at(prev_vacated)
        if mp is not None:
            left = (f"Now that {_owner(mp.color, user_color)} {PIECE_WORD[mp.piece_type]} has left"
                    f"{' ' + chess.square_name(prev_vacated) if notation else ' its square'}")
            by_moved = [t for t in reopened if t.attacker == move.to_square]
            others = [t for t in reopened if t.attacker != move.to_square]
            if by_moved:
                subject = "it also hits" if out else f"{san} hits"
                out.append(f"{left}, {subject} "
                           f"{_join([_target_words(after, t, user_color, notation) for t in by_moved])}.")
            for t in others:
                ap = after.piece_at(t.attacker)
                out.append(f"{left}, {_owner(ap.color, user_color)} {PIECE_WORD[ap.piece_type]}"
                           f"{_sq(t.attacker, notation)} hits {_target_words(after, t, user_color, notation)}.")
    if uncovered:
        parts = []
        for t in uncovered:
            ap = after.piece_at(t.attacker)
            parts.append(f"{_owner(ap.color, user_color)} {PIECE_WORD[ap.piece_type]}"
                         f"{_sq(t.attacker, notation)} now hits {_target_words(after, t, user_color, notation)}")
        out.append(f"Moving out of the way, {san} opens a line: {_join(parts)}.")
    return out


# ---------------------------------------------------------------- verdict

def verdict(drop_cp: int, rating: Optional[int]) -> str:
    """good / inaccuracy / mistake / blunder from the shared rating table."""
    th = move_classification_thresholds(rating)
    change = -int(drop_cp)
    if change >= th["good"]:
        return "good"
    if change >= th["inaccuracy"]:
        return "inaccuracy"
    if change >= th["mistake"]:
        return "mistake"
    return "blunder"


# "The best move" is said only when the next-best move is at least this much
# worse. The 2026-11-18 grade found "Re2 is the best move here" false: at the
# board's depth Re2 was top, deeper it was 52 points behind Kg5.
BEST_MARGIN_CP = 30


def verdict_sentence(san: str, cls: str, *, is_best: bool, best_san: Optional[str],
                     allows_mate: bool, best_margin: Optional[int] = None) -> str:
    """The verdict, worded so it stays true when the engine is a little noisy.

    The 2026-11-18 grade found two class words wrong near a class line ("a
    little slower" for a loss of about a pawn, "a mistake" for about half a
    pawn). So the middle of the table gets one plain comparison that is true on
    either side of the line, and "a mistake" is kept for the big losses
    (blunder in the rating table), where depth does not change the answer.
    """
    if allows_mate:
        return f"{san} allows a forced mate."
    if is_best:
        if best_margin is not None and best_margin >= BEST_MARGIN_CP:
            return f"{san} is the best move here."
        return f"{san} is a good move."
    if cls == "good":
        return f"{san} is fine."
    if cls in ("inaccuracy", "mistake"):
        # Not a review caption: the central caption layer explains stored game
        # moves; this is a verdict on a move the student just tried, from the
        # same rating table. docs/play_any_line_scope.md.
        return f"{best_san} was better than {san}." if best_san else f"{san} is not the best here."  # allow-noncentral-caption
    return (f"{san} is a mistake: {best_san} was better."  # allow-noncentral-caption
            if best_san else f"{san} is a mistake.")  # allow-noncentral-caption


# ---------------------------------------------------------------- material

_WORD_ORDER = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]


def _list_words(pieces: List[int]) -> str:
    parts = []
    for pt in _WORD_ORDER:
        n = pieces.count(pt)
        if n == 0:
            continue
        w = PIECE_WORD[pt]
        parts.append(f"a {w}" if n == 1 else f"{_NUM.get(n, n)} {w}s")
    if not parts:
        return "nothing"
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


_NUM = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


def captures_by_side(start: chess.Board, moves: Sequence[chess.Move]) -> Dict[chess.Color, List[int]]:
    """Piece types each side took along the line."""
    return line_material(start, moves)[0]


def line_material(start: chess.Board, moves: Sequence[chess.Move]):
    """(took, promoted): piece types each side took, and pieces each side made
    by promotion, along the line. A promotion changes the material as much as
    a capture, so a count that left it out would be false."""
    b = start.copy()
    took: Dict[chess.Color, List[int]] = {chess.WHITE: [], chess.BLACK: []}
    made: Dict[chess.Color, List[int]] = {chess.WHITE: [], chess.BLACK: []}
    for mv in moves:
        if b.is_capture(mv):
            sq = mv.to_square
            if b.is_en_passant(mv):
                sq = chess.square(chess.square_file(mv.to_square), chess.square_rank(mv.from_square))
            p = b.piece_at(sq)
            if p is not None:
                took[b.turn].append(p.piece_type)
        if mv.promotion:
            made[b.turn].append(mv.promotion)
        b.push(mv)
    return took, made


def _size_word(points: int) -> str:
    if points >= 9:
        return "a queen"
    if points >= 5:
        return "a rook"
    if points >= 3:
        return "a piece"
    if points == 2:
        return "two pawns"
    return "a pawn"


def board_balance(board: chess.Board, color: chess.Color) -> int:
    """Material of `color` minus the other side's, in pawns (kings excluded)."""
    total = 0
    for p in board.piece_map().values():
        if p.piece_type == chess.KING:
            continue
        total += VALUE[p.piece_type] if p.color == color else -VALUE[p.piece_type]
    return total


def material_sentence(start: chess.Board, moves: Sequence[chess.Move], user_color: chess.Color,
                      continuation: Sequence[chess.Move]) -> Optional[str]:
    """What changed hands along the line, and where that leaves the material.

    Only at a quiet point (no capture in the engine's next QUIET_PLIES moves),
    and only when the line moved real material: a piece or more either way, or
    an exchange that ended two pawns or more apart. "Overall" is read from the
    board itself, never from the line alone: a line can lose a pawn while the
    player stays a piece up from earlier in the game.
    """
    end = start.copy()
    for mv in moves:
        end.push(mv)
    look = end.copy()
    for mv in list(continuation)[:QUIET_PLIES]:
        if mv not in look.legal_moves:
            break
        if look.is_capture(mv):
            return None
        look.push(mv)
    took, made = line_material(start, moves)
    mine, theirs = took[user_color], took[not user_color]
    my_new, their_new = made[user_color], made[not user_color]
    net = (sum(VALUE[p] for p in mine) - sum(VALUE[p] for p in theirs)
           + sum(VALUE[p] - 1 for p in my_new) - sum(VALUE[p] - 1 for p in their_new))
    if not (abs(net) >= 3 or (mine and theirs and abs(net) >= 2)):
        return None
    parts = []
    if mine:
        parts.append(f"you won {_list_words(mine)}")
    if my_new:
        parts.append(f"you made {_list_words(my_new).replace('a ', 'a new ', 1)}")
    if theirs:
        parts.append(f"they won {_list_words(theirs)}")
    if their_new:
        parts.append(f"they made {_list_words(their_new).replace('a ', 'a new ', 1)}")
    if not parts:
        return None
    head = "In this line " + _join(parts) + "."
    overall = board_balance(end, user_color)
    if overall == 0:
        return head + " Overall the material is level."
    return head + f" Overall you are {_size_word(abs(overall))} {'up' if overall > 0 else 'down'}."


# ---------------------------------------------------------------- browser engine

class ClientAnswers:
    """Answers step()'s two engine questions from the student's own browser.

    docs/play_any_line_scope.md section 10: the reply and arrows come from
    Stockfish running in the browser, so the move is answered at once; the
    server only writes the words. This stands in for the engine: the position
    before the move (best move, its score, the next move's score) and the
    position after it (the reply line and its score). Scores are centipawns
    from the side to move, a mate as +-(10000 - n), like the server's.

    Anything that does not fit the board is refused (LineError) and the route
    falls back to the server engine.
    """

    def __init__(self, before_fen: str, best_uci: str, best_cp: int, second_cp: Optional[int],
                 after_fen: Optional[str], pv_after_uci: Sequence[str], after_cp: Optional[int]):
        def clamp(v):
            return None if v is None else max(-MATE_SCORE, min(MATE_SCORE, int(v)))

        before = chess.Board(before_fen)
        try:
            best = chess.Move.from_uci(best_uci)
        except ValueError as exc:
            raise LineError("bad best move from the browser") from exc
        if best not in before.legal_moves:
            raise LineError("the browser's best move is not legal here")
        self.before_key = _key(before_fen)
        self.best = best
        self.best_cp = clamp(best_cp)
        self.second_cp = clamp(second_cp)
        self.after_key = _key(after_fen) if after_fen else None
        self.after_cp = clamp(after_cp)
        self.pv_after: List[chess.Move] = []
        if after_fen:
            b = chess.Board(after_fen)
            for u in list(pv_after_uci)[:12]:
                try:
                    mv = chess.Move.from_uci(u)
                except ValueError:
                    break
                if mv not in b.legal_moves:
                    break
                self.pv_after.append(mv)
                b.push(mv)

    @staticmethod
    def _info(board: chess.Board, cp: int, pv: List[chess.Move]) -> Dict:
        return {"score": chess.engine.PovScore(chess.engine.Cp(cp), board.turn), "pv": pv}

    def analyse(self, board: chess.Board, limit=None, multipv: int = 1):
        key = _key(board.fen())
        if key == self.before_key:
            out = [self._info(board, self.best_cp, [self.best])]
            if self.second_cp is not None:
                out.append(self._info(board, self.second_cp, []))
            return out if multipv > 1 else out[0]
        if self.after_key is not None and key == self.after_key and self.after_cp is not None:
            return self._info(board, self.after_cp, list(self.pv_after))
        raise LineError("the browser's search was for another position")


# ---------------------------------------------------------------- one step

@dataclass
class Step:
    student_san: str
    student_uci: str
    cls: str
    is_best: bool
    best_san: Optional[str]
    student_text: str
    reply_san: Optional[str] = None
    reply_uci: Optional[str] = None
    reply_text: Optional[str] = None
    count_text: Optional[str] = None
    fen_after: str = ""
    needs_why: bool = False
    arrows: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "student": {"san": self.student_san, "uci": self.student_uci, "class": self.cls,
                        "is_best": self.is_best, "best_san": self.best_san, "text": self.student_text},
            "reply": ({"san": self.reply_san, "uci": self.reply_uci, "text": self.reply_text}
                      if self.reply_san else None),
            "count_text": self.count_text,
            "fen_after": self.fen_after,
            "needs_why": self.needs_why,
            "arrows": self.arrows,
        }


def _score(info) -> int:
    return info["score"].relative.score(mate_score=MATE_SCORE)


def step(engine: chess.engine.SimpleEngine, start_fen: str, line_san: Sequence[str],
         move_san: Optional[str], *, user_color: chess.Color, rating: Optional[int],
         depth: int, notation: bool = True) -> Step:
    """One student move and the engine's answer.

    `move_san` None means "Best move here": the engine's best is played as the
    student's move.
    """
    start, _ = replay(start_fen, [])
    board, played = replay(start_fen, line_san)
    if board.is_game_over():
        raise LineError("the game is over in this line")
    infos = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=2)
    if isinstance(infos, dict):
        infos = [infos]
    info_before = infos[0]
    best = (info_before.get("pv") or [None])[0]
    best_score = _score(info_before)
    best_margin = (best_score - _score(infos[1])) if len(infos) > 1 else None
    if move_san is None:
        if best is None:
            raise LineError("no move")
        move = best
    else:
        try:
            move = board.parse_san(move_san)
        except ValueError as exc:
            raise LineError(f"illegal move: {move_san}") from exc
    san = board.san(move)
    best_san = board.san(best) if best is not None else None
    previous = played[-1] if played else None
    prev_board = None
    if previous is not None:
        prev_board = board.copy()
        prev_board.pop()

    after = board.copy()
    after.push(move)
    reply = None
    reply_score = None
    pv_after: List[chess.Move] = []
    if not after.is_game_over():
        info_after = engine.analyse(after, chess.engine.Limit(depth=depth))
        pv_after = list(info_after.get("pv") or [])
        reply = pv_after[0] if pv_after else None
        reply_score = _score(info_after)
        played_score = -reply_score
    else:
        played_score = MATE_SCORE if after.is_checkmate() else 0
    is_best = best is not None and move == best
    drop = 0 if is_best else max(0, best_score - played_score)
    cls = "good" if is_best else verdict(drop, rating)
    allows_mate = reply_score is not None and reply_score >= MATE_SCORE - 200 and best_score < MATE_SCORE - 200

    facts = describe(board, move, user_color, previous=previous, previous_board=prev_board,
                     notation=notation)
    head = verdict_sentence(san, cls, is_best=is_best, best_san=best_san, allows_mate=allows_mate,
                            best_margin=best_margin)
    # The verdict already names the move; a fact that only restates it adds nothing.
    tail = [f for f in facts if not f.startswith(f"{san} is checkmate")]
    if after.is_checkmate():
        student_text = f"{san} is checkmate."
    elif tail:
        first = tail[0]
        # "It" only when the verdict before it is about the same move: after
        # "Be3 was better than dxe6." an "It takes ..." would read as Be3.
        if first.startswith(san + " ") and head.startswith(san + " "):
            first = "It " + first[len(san) + 1:]
        student_text = head + " " + " ".join([first] + tail[1:])
    else:
        student_text = head

    out = Step(student_san=san, student_uci=move.uci(), cls=cls, is_best=is_best,
               best_san=best_san, student_text=student_text,
               needs_why=cls in ("mistake", "blunder") and not after.is_checkmate())
    out.arrows.append({"from": chess.square_name(move.from_square),
                       "to": chess.square_name(move.to_square), "color": "blue"})
    final = after
    moves_so_far = list(played) + [move]
    if reply is not None:
        reply_facts = describe(after, reply, user_color, previous=move, previous_board=board,
                               notation=notation)
        out.reply_san = after.san(reply)
        out.reply_uci = reply.uci()
        out.reply_text = " ".join(reply_facts) if reply_facts else f"The engine answers {out.reply_san}."
        out.arrows.append({"from": chess.square_name(reply.from_square),
                           "to": chess.square_name(reply.to_square), "color": "red"})
        final = after.copy()
        final.push(reply)
        standing = meaningful_attacks(final, reply, previous=move, board_before=after)
        for t in standing:
            out.arrows.append({"from": chess.square_name(t.attacker),
                               "to": chess.square_name(t.square), "color": "red"})
        moves_so_far.append(reply)
    else:
        standing = []
    # No count while the reply leaves a real attack standing: the engine line
    # varies run to run, the attack on the board does not.
    if not standing:
        out.count_text = material_sentence(start, moves_so_far, user_color,
                                           pv_after[1:] if reply else [])
    out.fen_after = final.fen()
    return out

"""Six board lessons: pick the thing off the board, end with the teaching.

Mohit 2026-10-07, on three cards from one King's Gambit game: "captions are
too long and really don't make sense -- the idea of caption is to explain
what's on the board and the arrow to show what's on the board". Then on the
family names I proposed: "dumb shit strings, 'another piece of yours is taken',
what is this lesson". And the shape he settled on:

    "from the board pick the thing and end the lesson, these are our templates"

So a card is two sentences. The first names something counted on the board.
The second is the lesson, identical every time that template fires, because
that is the half the player still has in a week.

THE POINT OF THIS MODULE is that one `slots` dict produces the sentence AND
the arrows. The cards he reported had a caption about one move and arrows
about another -- Nc4 said "runs into bxc4" and drew f7->f5, e5->f6, d8->f6 --
and both halves were individually correct, because nothing in the pipeline
compares them and an arrow carries no record of what it illustrates. Here
there is nothing to compare: there is one source.

The victim is always a piece the engine's own line actually takes. The counts
are evidence for that capture, never a prediction standing on their own.

Measured over 100 of his games, both sides, 5,913 plies at depth 16. At
cp_loss >= 100 these six cover 536 of 1,056 mistakes and blunders.
docs/board_lesson_templates_scope.md
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import chess

_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "captions", "board_lessons.json")
_PIECE_VALUE = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
}

_TEMPLATES: Optional[Dict[str, Dict[str, str]]] = None


def _templates() -> Dict[str, Dict[str, str]]:
    global _TEMPLATES
    if _TEMPLATES is None:
        with open(os.path.abspath(_DATA), encoding="utf-8") as fh:
            _TEMPLATES = json.load(fh)["templates"]
    return _TEMPLATES


@dataclass
class BoardLesson:
    template_id: str
    slots: Dict[str, Any]
    caption: str
    arrows: List[Dict[str, str]] = field(default_factory=list)
    # Arrows that are true of the position but NOT of the board the card
    # shows -- a recommended capture by the piece that has already moved, for
    # instance. They carry their own FEN rather than being drawn over a board
    # where their from-square is empty.
    plan_arrows: List[Dict[str, str]] = field(default_factory=list)
    plan_fen: str = ""


def drawable_on(board: chess.Board, arrows: List[Dict[str, str]]):
    """Split arrows into the ones this board can honestly show, and the rest.

    THE RULE: an arrow may start from a square that holds a piece, or from the
    square a previous arrow in the same set pointed at. The first is a move you
    can see; the second is the next step of a sequence the eye is already
    following. Anything else begins nowhere, which is the complaint Mohit has
    now raised four times -- "a8 bishop is missing, the arrow is missing
    there", "why this arrow?", "no arrow at all, what's wrong with you".

    Measured when the rule was added: 162 of 1,082 arrows these templates drew
    began on an empty, unconnected square.
    """
    ok: List[Dict[str, str]] = []
    orphans: List[Dict[str, str]] = []
    reached = set()
    for a in arrows:
        try:
            frm = chess.parse_square(a["from"])
        except (ValueError, KeyError):
            orphans.append(a)
            continue
        if board.piece_at(frm) is not None or a["from"] in reached:
            ok.append(a)
            reached.add(a["to"])
        else:
            orphans.append(a)
    return ok, orphans


# Words, not digits. "d4 is attacked 1 times and defended 0" was the first
# thing these templates produced, and the house rule is simple English with no
# numerals in user-facing text. feedback_published_text_simple_english
_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}


def _count_phrases(n_attackers: int, n_defenders: int) -> Dict[str, str]:
    a = _WORDS.get(n_attackers, str(n_attackers))
    if n_attackers == 1:
        attack = "{a} of their pieces attacks".format(a=a)
    else:
        attack = "{a} of their pieces attack".format(a=a)
    if n_defenders == 0:
        defend = "Nothing of yours defends it."
    elif n_defenders == 1:
        defend = "Only one of yours defends it."
    else:
        defend = "{d} of yours defend it.".format(d=_WORDS.get(n_defenders, str(n_defenders)).lower())
    return {"attack": attack, "defend": defend}


def _name(piece: Optional[chess.Piece]) -> str:
    return chess.piece_name(piece.piece_type) if piece else "piece"


def _arrow(frm: int, to: int, colour: str) -> Dict[str, str]:
    return {"from": chess.square_name(frm), "to": chess.square_name(to),
            "color": colour, "teach": True}


def _render(template_id: str, slots: Dict[str, Any]) -> Optional[str]:
    """Both sentences, or nothing. A missing slot is silence, never a gap."""
    tpl = _templates().get(template_id)
    if not tpl:
        return None
    try:
        board = tpl["board"].format(**slots)
    except (KeyError, IndexError):
        return None
    return f"{board} {tpl['lesson']}".strip()


def _first_capture_of_ours(board_after: chess.Board, us: bool,
                           line: Sequence[str]) -> Optional[Dict[str, Any]]:
    """Walk the engine's line; return the first capture THEY make of OURS.

    Everything downstream hangs off a capture the engine actually plays, so a
    lesson can never be an attacker-count that nobody ever cashes in.
    """
    probe = board_after.copy()
    for san in list(line or [])[:8]:
        try:
            move = probe.parse_san(str(san))
        except (ValueError, AssertionError):
            return None
        victim = probe.piece_at(move.to_square)
        theirs = probe.turn != us
        if theirs and victim is not None and victim.color == us:
            return {
                "move": move,
                "san": str(san),
                # The board as it stands when the capture is made. Counting on
                # the board right after OUR move was wrong: on Mohit's Nc4 the
                # knight lands one-against-one and only becomes two-against-one
                # once b3 arrives, so the template refused a card whose whole
                # lesson is that count.
                "board_at_capture": probe.copy(),
                "victim": victim,
                "victim_square": move.to_square,
                "attacker": probe.piece_at(move.from_square),
                "attacker_square": move.from_square,
                "value": _PIECE_VALUE[victim.piece_type],
            }
        probe.push(move)
    return None


# -- the six ---------------------------------------------------------------

def _can_be_taken_for_profit(board: chess.Board, us: bool, square: int) -> bool:
    """Could we just capture the piece sitting there and come out ahead?

    Played out rather than counted: board.attackers() is pseudo-legal, so a
    pinned defender reads as a real one. Each capture is made on a copy and
    the opponent's best recapture allowed, which is the cheapest honest
    version of the question.
    """
    victim = board.piece_at(square)
    if victim is None:
        return False
    gain = _PIECE_VALUE[victim.piece_type]
    probe = board.copy()
    probe.turn = us
    for mv in probe.legal_moves:
        if mv.to_square != square:
            continue
        taker = probe.piece_at(mv.from_square)
        after_take = probe.copy()
        after_take.push(mv)
        back = min(
            (_PIECE_VALUE[taker.piece_type] for r in after_take.legal_moves
             if r.to_square == square),
            default=0,
        )
        if gain - back > 0:
            return True
    return False


def _forked(before, after, move, us, loss, line):
    """One of their pieces lands attacking two of ours at once.

    Mohit asked whether the king-square family was "sort of fork". It is not:
    45 of its 48 cards attack a single piece, and the trick there is that the
    square cannot be answered, not that two things are hit. Three were real
    forks, and a fork is a pattern worth naming when it actually is one -- so
    it gets its own template rather than being folded into a lesson about
    king safety.
    """
    probe = after.copy()
    route: List[Dict[str, str]] = []
    for san in list(line or [])[:8]:
        try:
            m = probe.parse_san(str(san))
        except (ValueError, AssertionError):
            return None
        if probe.turn != us:
            landed = probe.copy()
            landed.push(m)
            targets = [
                sq for sq in landed.attacks(m.to_square)
                if (landed.piece_at(sq) and landed.piece_at(sq).color == us
                    and _PIECE_VALUE[landed.piece_at(sq).piece_type] >= 3)
            ]
            king = landed.king(us)
            if king is not None and king in landed.attacks(m.to_square):
                targets = [king] + [t for t in targets if t != king]
            # A fork is not "a piece that happens to see two things". The
            # piece has to be SAFE where it lands -- otherwise you simply take
            # it and there is no fork to teach. Without this the family fired
            # on 251 of 1,056 moves, a quarter of every mistake in his games,
            # which is not what a fork is. feedback_verify_with_own_perspective
            if len(targets) >= 2 and not _can_be_taken_for_profit(landed, us, m.to_square):
                attacker = probe.piece_at(m.from_square)
                # worth more first: that is the one they are really after
                targets.sort(key=lambda sq: -_PIECE_VALUE[landed.piece_at(sq).piece_type])
                slots = {
                    "attacker": _name(attacker),
                    "landing_square": chess.square_name(m.to_square),
                    "first": _name(landed.piece_at(targets[0])),
                    "first_square": chess.square_name(targets[0]),
                    "second": _name(landed.piece_at(targets[1])),
                    "second_square": chess.square_name(targets[1]),
                }
                caption = _render("forked", slots)
                if not caption:
                    return None
                arrows = route + [
                    _arrow(m.from_square, m.to_square, "red"),
                    _arrow(m.to_square, targets[0], "red"),
                    _arrow(m.to_square, targets[1], "red"),
                ]
                return BoardLesson("forked", slots, caption, arrows[:5])
            route.append(_arrow(m.from_square, m.to_square, "red"))
        probe.push(m)
    return None


def _king_square_theirs(before, after, move, us, loss, line):
    """An enemy piece settles beside our king on a square the king may not take.

    161 of 1,748 flagged moves, and it surprised me -- I would have guessed it
    too rare to carry its own template. It is Mohit's Na5 card: the knight
    reaches h7, the king cannot capture because the bishop on d3 guards h7, and
    from h7 it takes the rook on f8. The GUARD is the lesson, so it gets an
    arrow of its own.
    """
    king = after.king(us)
    if king is None:
        return None
    probe = after.copy()
    route: List[Dict[str, str]] = []
    for index, san in enumerate(list(line or [])[:8]):
        try:
            m = probe.parse_san(str(san))
        except (ValueError, AssertionError):
            return None
        theirs = probe.turn != us
        if theirs:
            landed = probe.copy()
            landed.push(m)
            adjacent = chess.square_distance(m.to_square, king) == 1
            cannot_take = chess.Move(king, m.to_square) not in landed.legal_moves
            guards = list(landed.attackers(not us, m.to_square))
            if adjacent and cannot_take and guards:
                rest = _first_capture_of_ours(landed, us, list(line)[index + 1:])
                if rest is None or rest["victim_square"] == m.to_square:
                    return None
                guard_sq = guards[0]
                slots = {
                    "enemy": _name(probe.piece_at(m.from_square)),
                    "landing_square": chess.square_name(m.to_square),
                    "guard": _name(landed.piece_at(guard_sq)),
                    "guard_square": chess.square_name(guard_sq),
                    "victim": _name(rest["victim"]),
                    "victim_square": chess.square_name(rest["victim_square"]),
                }
                # Two thirds of this family (32 of 48) arrive WITH check, and
                # that is the forcing half of the trick: you must answer, and
                # while you do, the piece helps itself. The lesson is the same
                # either way; the board sentence is not.
                tid = ("king_square_theirs_check" if landed.is_check()
                       else "king_square_theirs")
                caption = _render(tid, slots)
                if not caption:
                    return None
                arrows = route + [
                    _arrow(m.from_square, m.to_square, "red"),
                    _arrow(guard_sq, m.to_square, "yellow"),
                    _arrow(m.to_square, rest["victim_square"], "red"),
                ]
                return BoardLesson(tid, slots, caption, arrows[:5])
            route.append(_arrow(m.from_square, m.to_square, "red"))
        probe.push(m)
    return None


def _arrival_moves(after: chess.Board, us: bool, line: Sequence[str]) -> Dict[int, tuple]:
    """Which enemy move in the line lands on which square.

    An attacker that is not on its square yet cannot be drawn from there --
    Mohit's Nc4 card counts the b3 pawn, and on the board he is looking at that
    pawn is still on b2. Drawing b2->b3 and then b3->c4 is the chain rule doing
    its job: the second arrow starts where the first one ended.
    """
    out: Dict[int, tuple] = {}
    probe = after.copy()
    for san in list(line or [])[:8]:
        try:
            m = probe.parse_san(str(san))
        except (ValueError, AssertionError):
            break
        if probe.turn != us:
            out.setdefault(m.to_square, (m.from_square, m.to_square))
        probe.push(m)
    return out


def _landed_uncounted(before, after, move, us, loss, line):
    """The piece that just moved is the one the line takes."""
    if loss["victim_square"] != move.to_square:
        return None
    at = loss.get("board_at_capture") or after
    attackers = sorted(at.attackers(not us, move.to_square))
    defenders = sorted(at.attackers(us, move.to_square))
    if not attackers or len(attackers) <= len(defenders):
        return None
    phrases = _count_phrases(len(attackers), len(defenders))
    slots = {
        "to_square": chess.square_name(move.to_square),
        "n_attackers": len(attackers),
        "n_defenders": len(defenders),
        "attack_phrase": "{a} {sq}.".format(a=phrases["attack"],
                                            sq=chess.square_name(move.to_square)),
        "defend_phrase": phrases["defend"],
    }
    caption = _render("landed_uncounted", slots)
    if not caption:
        return None
    arrivals = _arrival_moves(after, us, line)
    arrows: List[Dict[str, str]] = []
    for sq in attackers:
        if after.piece_at(sq) is None and sq in arrivals:
            frm, to = arrivals[sq]
            arrows.append(_arrow(frm, to, "red"))
        arrows.append(_arrow(sq, move.to_square, "red"))
    arrows += [_arrow(s, move.to_square, "yellow") for s in defenders]
    return BoardLesson("landed_uncounted", slots, caption, arrows[:5])


def _moved_the_guard(before, after, move, us, loss, line):
    """The square the piece left was defending the square the line takes."""
    victim_sq = loss["victim_square"]
    if victim_sq == move.to_square:
        return None
    if victim_sq not in before.attacks(move.from_square):
        return None
    if len(after.attackers(us, victim_sq)) >= len(before.attackers(us, victim_sq)):
        return None
    slots = {
        "mover": _name(before.piece_at(move.from_square)),
        "from_square": chess.square_name(move.from_square),
        "victim": _name(loss["victim"]),
        "victim_square": chess.square_name(victim_sq),
        "capture": loss["san"],
    }
    caption = _render("moved_the_guard", slots)
    if not caption:
        return None
    # The square it LEFT is already highlighted by the card as the move's
    # from-square, so the lesson does not need an arrow starting there -- and
    # could not honestly draw one, since the piece is gone.
    return BoardLesson("moved_the_guard", slots, caption, [
        _arrow(loss["attacker_square"], victim_sq, "red"),
    ])


def _opened_line(before, after, move, us, loss, line):
    """The victim gained attackers only once our piece stepped out of the way."""
    victim_sq = loss["victim_square"]
    if victim_sq == move.to_square:
        return None
    if len(after.attackers(not us, victim_sq)) <= len(before.attackers(not us, victim_sq)):
        return None
    attacker_sq = loss["attacker_square"]
    if move.from_square not in chess.SquareSet.between(attacker_sq, victim_sq):
        return None
    slots = {
        "from_square": chess.square_name(move.from_square),
        "attacker": _name(loss["attacker"]),
        "attacker_square": chess.square_name(attacker_sq),
        "victim": _name(loss["victim"]),
        "victim_square": chess.square_name(victim_sq),
    }
    caption = _render("opened_line", slots)
    if not caption:
        return None
    return BoardLesson("opened_line", slots, caption,
                       [_arrow(attacker_sq, victim_sq, "red")])


def _hanging_ignored(before, after, move, us, loss, line):
    """It was already attacked and undefended, and the move went elsewhere.

    The largest single thinking error in his games: 149 of 1,056 mistakes and
    blunders. 1.e4 e5 2.Nf3 Bc5? is the shape -- e5 is attacked, nothing holds
    it, and the move develops instead.
    """
    victim_sq = loss["victim_square"]
    if victim_sq == move.to_square:
        return None
    attackers = sorted(before.attackers(not us, victim_sq))
    defenders = sorted(before.attackers(us, victim_sq))
    if not attackers or len(defenders) >= len(attackers):
        return None
    if victim_sq in before.attacks(move.from_square):
        return None          # that is moved_the_guard, a different lesson
    slots = {
        "victim": _name(loss["victim"]),
        "victim_square": chess.square_name(victim_sq),
        "attacker": _name(loss["attacker"]),
        "attacker_square": chess.square_name(loss["attacker_square"]),
    }
    caption = _render("hanging_ignored", slots)
    if not caption:
        return None
    # The piece the sentence NAMES is drawn first, always. Measured when this
    # was written: 10 cards named an attacker that the pre-move attacker list
    # did not contain, so the words said one square and the board drew another
    # -- the exact drift this module exists to make impossible, reproduced
    # inside it.
    ordered = [loss["attacker_square"]]
    ordered += [sq for sq in attackers if sq != loss["attacker_square"]]
    return BoardLesson("hanging_ignored", slots, caption,
                       [_arrow(sq, victim_sq, "red") for sq in ordered][:5])


def _capture_window(before, after, move, us, best_move, best_san, line):
    """The capture was winning, and their reply takes it away.

    96 of the 320 positions where a capture was on offer -- 30%. Mohit on the
    Bc4 card: the generic "look at every capture" is true and misses the whole
    point, which is that the chance was one move wide. e5 was attacked twice
    and defended once; after d6 it is two and two, and it never comes back.
    """
    if best_move is None or best_move == move:
        return None
    target_sq = best_move.to_square
    if before.is_en_passant(best_move):
        target = chess.Piece(chess.PAWN, not us)
    else:
        target = before.piece_at(target_sq)
    if target is None or target.color == us:
        return None
    if len(before.attackers(us, target_sq)) <= len(before.attackers(not us, target_sq)):
        return None                      # it was never winning, so nothing closed
    reply = (list(line or []) or [None])[0]
    if not reply:
        return None
    probe = after.copy()
    try:
        reply_move = probe.parse_san(str(reply))
    except (ValueError, AssertionError):
        return None
    probe.push(reply_move)
    if len(probe.attackers(us, target_sq)) > len(probe.attackers(not us, target_sq)):
        return None                      # still winning, the chance did not close
    slots = {
        "best_san": best_san or before.san(best_move),
        "target": _name(target),
        "target_square": chess.square_name(target_sq),
        "reply": str(reply),
    }
    caption = _render("capture_window_closed", slots)
    if not caption:
        return None
    arrows = [_arrow(best_move.from_square, target_sq, "blue"),
              _arrow(reply_move.from_square, reply_move.to_square, "red")]
    if target_sq in probe.attacks(reply_move.to_square):
        arrows.append(_arrow(reply_move.to_square, target_sq, "red"))
    return BoardLesson("capture_window_closed", slots, caption, arrows)


def _capture_available(before, after, move, us, best_move, best_san):
    """There was a capture on the board and the move went elsewhere.

    Any capture, not just a piece: the first cut of this family set the bar at
    a knight, and a free pawn to take back is the same lesson.
    """
    if best_move is None or best_move == move:
        return None
    if before.is_en_passant(best_move):
        target = chess.Piece(chess.PAWN, not us)
    else:
        target = before.piece_at(best_move.to_square)
    if target is None or target.color == us:
        return None
    slots = {
        "best_san": best_san or before.san(best_move),
        "target": _name(target),
        "target_square": chess.square_name(best_move.to_square),
    }
    caption = _render("capture_available", slots)
    if not caption:
        return None
    return BoardLesson("capture_available", slots, caption,
                       [_arrow(best_move.from_square, best_move.to_square, "blue")])


# -- entry point -----------------------------------------------------------

# Ordered by what the player could have DONE DIFFERENTLY, not by how
# impressive the pattern is.
#
# Putting the fork first was wrong and the corpus said so: it took 205 of
# 1,056 cards, including the Bc5 position whose lesson is that the bishop on
# f8 was holding g7. "One piece can attack two of yours" does not help anyone
# avoid that move; "check what it is holding" does. A fork is named when
# nothing earlier explains the move -- then it is the lesson, and a good one.
_ORDER = (_king_square_theirs, _landed_uncounted, _moved_the_guard,
          _opened_line, _hanging_ignored, _forked)


def find_board_lesson(
    fen_before: str,
    played_san: str,
    pv_after_played: Optional[Sequence[str]] = None,
    best_move_san: Optional[str] = None,
) -> Optional[BoardLesson]:
    """The one lesson this move teaches, with the arrows that prove it."""
    try:
        before = chess.Board(fen_before)
        move = before.parse_san(str(played_san))
    except (ValueError, AssertionError, TypeError):
        return None
    us = before.turn
    after = before.copy()
    after.push(move)

    best_move = None
    if best_move_san:
        try:
            best_move = before.parse_san(str(best_move_san))
        except (ValueError, AssertionError):
            best_move = None

    found = None
    loss = _first_capture_of_ours(after, us, pv_after_played or [])
    if loss is not None:
        for rule in _ORDER:
            try:
                found = rule(before, after, move, us, loss, pv_after_played or [])
            except Exception:
                found = None
            if found is not None:
                break
    if found is None:
        # Nothing of ours comes off, but a capture was sitting there unplayed.
        # The narrower lesson first: "it was there and now it is gone" beats
        # "a capture existed" wherever the board can prove the window shut.
        try:
            found = _capture_window(before, after, move, us, best_move,
                                    best_move_san, pv_after_played or [])
        except Exception:
            found = None
        if found is None:
            try:
                found = _capture_available(before, after, move, us, best_move, best_move_san)
            except Exception:
                found = None
    if found is None:
        return None

    # One rule decides what this board may show. Orphans move to their own
    # frame -- the position BEFORE the move, where they are all legal -- which
    # the card already has a surface for.
    drawn, orphans = drawable_on(after, found.arrows)
    found.arrows = drawn[:5]
    if orphans:
        found.plan_arrows = orphans[:5]
        found.plan_fen = before.fen()
    return found

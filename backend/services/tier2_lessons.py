"""Three quiet-position lessons, each earned by rows in Mohit's own games.

For the moves where no capture happens in the engine's line, so every
material-shaped caption is blind. 323 such positions in his last 100 games were
labelled by Claude against measured facts, and then every candidate rule was
scored against those labels. These three survived:

    a check that changes nothing     20 rows   95%
    you moved the guard              11 rows   73%
    a pawn kicks it, it goes anyway  31 rows   68%

Nine other candidates were measured and dropped: "you blocked your own piece"
(27%), "you left an outpost" (37%), "the piece has no moves" (44%), "it goes
back where it came from" (26%), "you play the best move later" (23%). Each is a
true statement about the board and none of them predicts the lesson, which is
the distinction this module exists to respect.

WHY SO FEW. On a typical quiet position three to five facts fire at once and
only one is the lesson. Measuring more facts does not help choose between the
ones already measured -- a doctor with five abnormal results is not helped by a
sixth test. Picking the teaching point is judgement, and the honest machine
answer is to speak only where the data says one fact dominates, and stay silent
on the other 80%.

docs/board_lesson_templates_scope.md
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess

from services.position_facts import can_a_pawn_ever_attack, extract, mobility_of

_MAX_PLY = 4


def _arrow(frm: str, to: str, colour: str) -> Dict[str, str]:
    return {"from": frm, "to": to, "color": colour, "teach": True}


def _drawable(board: chess.Board, arrows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """An arrow starts on a piece, or where the previous arrow ended.

    The same rule the Tier 1 templates use. 162 of 1,082 arrows began on an
    empty unconnected square before it existed, which is the complaint Mohit
    raised four separate times.
    """
    out: List[Dict[str, str]] = []
    reached = set()
    for a in arrows:
        try:
            frm = chess.parse_square(a["from"])
        except (ValueError, KeyError):
            continue
        if board.piece_at(frm) is not None or a["from"] in reached:
            out.append(a)
            reached.add(a["to"])
    return out


class Tier2Lesson:
    def __init__(self, rule_id: str, caption: str, arrows: List[Dict[str, str]],
                 facts: Dict[str, Any]):
        self.rule_id = rule_id
        self.caption = caption
        self.arrows = arrows
        self.facts = facts
        # For a picture that is true of the position but not of the board the
        # card shows -- an empty outpost cannot be the start of an arrow.
        self.plan_arrows: List[Dict[str, str]] = []
        self.plan_fen = ""


def _check_that_changes_nothing(board, played, after, us, f):
    """95% of 20 rows. A check, and the checking piece moves again at once."""
    ma = f.get("moves_again") or {}
    if not (f.get("played_gives_check") and ma and ma.get("ply", 99) <= _MAX_PLY):
        return None
    king = after.king(not us)
    if king is None:
        return None
    piece = after.piece_at(played.to_square)
    board_fact = (
        f"Your {chess.piece_name(piece.piece_type)} checks from "
        f"{chess.square_name(played.to_square)}, and has to move again to "
        f"{ma['to']} straight after."
    )
    lesson = "Check only when it wins something or stops something."
    arrows = [
        _arrow(chess.square_name(played.to_square), chess.square_name(king), "red"),
        _arrow(chess.square_name(played.to_square), ma["to"], "palegrey"),
    ]
    return Tier2Lesson("pointless_check", f"{board_fact} {lesson}", arrows, f)


def _you_moved_the_guard(board, played, after, us, f):
    """73% of 11 rows. A square of ours lost a guard and is now attacked."""
    hits = [g for g in (f.get("guards_lost") or [])
            if g.get("guards_after", 9) < g.get("attackers_after", 0)]
    if not hits:
        return None
    g = hits[0]
    board_fact = (
        f"Your {g['piece']} on {g['square']} had {g['guards_before']} "
        f"{'guard' if g['guards_before'] == 1 else 'guards'} and now has "
        f"{g['guards_after']}, with {g['attackers_after']} of their pieces on it."
    )
    lesson = "Before you move a piece, check what it is holding."
    target = chess.parse_square(g["square"])
    arrows = [_arrow(chess.square_name(s), g["square"], "red")
              for s in sorted(after.attackers(not us, target))][:3]
    return Tier2Lesson("defender_leaves_its_post", f"{board_fact} {lesson}", arrows, f)


def _a_pawn_kicks_it(board, played, after, us, f):
    """68% of 31 rows. A pawn can hit the square, and the piece leaves anyway."""
    kick = f.get("pawn_can_kick")
    ma = f.get("moves_again") or {}
    if not (kick and ma and ma.get("ply", 99) <= _MAX_PLY):
        return None
    piece = after.piece_at(played.to_square)
    if piece is None:
        return None
    board_fact = (
        f"Their pawn on {kick['pawn_on']} can go to {kick['goes_to']} and hit your "
        f"{chess.piece_name(piece.piece_type)} on {kick['hits']}, which ends up on "
        f"{ma['to']} anyway."
    )
    lesson = "Check whether a pawn can hit the square before you go there."
    arrows = [
        _arrow(kick["pawn_on"], kick["goes_to"], "red"),
        _arrow(kick["goes_to"], kick["hits"], "red"),
        _arrow(kick["hits"], ma["to"], "palegrey"),
    ]
    return Tier2Lesson("piece_chased_loses_time", f"{board_fact} {lesson}", arrows, f)



_CENTRE_ISH = (chess.D4, chess.E4, chess.D5, chess.E5, chess.C4, chess.C5,
               chess.F4, chess.F5, chess.D6, chess.E6, chess.D3, chess.E3)
_HEAVY = (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)


def _outpost_left_for_nothing(board, played, after, us, f):
    """A knight walks off a square nothing could ever chase it from, for nothing.

    Mohit 2026-10-09: "if it's moving from there for something better like
    forking, attacking or whatever, then obviously it's a good move, but if we
    are just moving it somewhere else, exchanging it, then that's bad."

    He was right and the undifferentiated rule hid it. "Knight leaves an
    outpost" measures 1.6x against engine-approved moves -- near noise. Split
    by what it left FOR:

        left for NOTHING          4.6x      <- this rule
        left to trade / take a pawn 3.1x
        left to attack a piece      2.3x
        forced, it was attacked     1.5x    <- the biggest bucket, excluded
        left to win a piece         1.2x
        left to give CHECK          0.8x    <- a marker of a GOOD move

    The 0.8x is the part that makes the rest believable: the split agrees with
    him on the branches that argue against the rule, not only the one for it.

    Small: 15 of 1,748. Re-measure on a second sample before trusting 4.6x.
    """
    piece = board.piece_at(played.from_square)
    if piece is None or piece.piece_type != chess.KNIGHT:
        return None
    frm = played.from_square
    if can_a_pawn_ever_attack(board, frm, not us):
        return None
    rank, file = chess.square_rank(frm), chess.square_file(frm)
    forward = rank >= 4 if us == chess.WHITE else rank <= 3
    if not (forward or frm in _CENTRE_ISH):
        return None
    # A knight on a8 or a1 also has "no pawn that can ever attack it" -- it is
    # trapped in the corner, not posted. The first cut of this rule told Mohit
    # a cornered knight was on an outpost. An outpost is a square the piece
    # WORKS from, so it has to be off the rim and have real scope there.
    if file in (0, 7) or rank in (0, 7):
        return None
    if mobility_of(board, frm) < 4:
        return None
    # Excluded: it had no choice, and that is the biggest bucket by far.
    if board.attackers(not us, frm) or board.is_check():
        return None
    if board.is_capture(played) or after.is_check():
        return None
    # Did it land somewhere that does something?
    if [s for s in after.attacks(played.to_square)
            if after.piece_at(s) and after.piece_at(s).color != us
            and after.piece_at(s).piece_type in _HEAVY]:
        return None

    kick = f.get("pawn_can_kick")
    slots = {
        "from_square": chess.square_name(frm),
        "to_square": chess.square_name(played.to_square),
        "kick_clause": (f", and their pawn on {kick['pawn_on']} can come to "
                        f"{kick['goes_to']} and chase it" if kick else ""),
    }
    caption = _render_outpost(slots)
    if not caption:
        return None
    # On the board the card shows, the outpost is empty -- so what the knight
    # USED to cover goes on its own frame rather than as arrows starting from
    # a square with nothing on it.
    def _deep(sq):
        r = chess.square_rank(sq)
        return r >= 4 if us == chess.WHITE else r <= 3
    plan = [_arrow(chess.square_name(frm), chess.square_name(s), "yellow")
            for s in sorted(board.attacks(frm)) if _deep(s)][:4]
    arrows = []
    if kick:
        arrows = [_arrow(kick["pawn_on"], kick["goes_to"], "red"),
                  _arrow(kick["goes_to"], kick["hits"], "red")]
    les = Tier2Lesson("outpost_left_for_nothing", caption, arrows, f)
    les.plan_arrows = plan
    les.plan_fen = board.fen()
    return les


def _render_outpost(slots):
    import json as _json
    import os as _os
    path = _os.path.join(_os.path.dirname(__file__), "..", "data", "captions",
                         "board_lessons.json")
    try:
        with open(_os.path.abspath(path), encoding="utf-8") as fh:
            tpl = _json.load(fh)["templates"]["outpost_left_for_nothing"]
        return f"{tpl['board'].format(**slots)} {tpl['lesson']}"
    except Exception:
        return None


# Most precise first. Measured, not chosen: 95%, 73%, 68%.
_RULES = (_check_that_changes_nothing, _you_moved_the_guard, _a_pawn_kicks_it,
          _outpost_left_for_nothing)


def find_tier2_lesson(fen_before: str, played_san: str,
                      line_after_played: Optional[List[str]] = None,
                      best_move_san: Optional[str] = None) -> Optional[Tier2Lesson]:
    """The lesson for a quiet move, or nothing. Silence is the common answer."""
    try:
        board = chess.Board(fen_before)
        played = board.parse_san(str(played_san))
    except (ValueError, AssertionError, TypeError):
        return None
    after = board.copy()
    after.push(played)
    us = board.turn
    try:
        f = extract(fen_before, played_san, line_after_played or [], best_move_san)
    except Exception:
        return None
    for rule in _RULES:
        try:
            found = rule(board, played, after, us, f)
        except Exception:
            found = None
        if found is not None:
            found.arrows = _drawable(after, found.arrows)[:4]
            return found
    return None

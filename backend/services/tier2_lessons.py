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

from services.position_facts import extract

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


# Most precise first. Measured, not chosen: 95%, 73%, 68%.
_RULES = (_check_that_changes_nothing, _you_moved_the_guard, _a_pawn_kicks_it)


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

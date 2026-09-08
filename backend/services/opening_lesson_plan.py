"""Decide what a student is taught in an opening, and in what order.

The page this replaces opened with seven choices: three variation chips and
four tabs. A student who knew whether they needed the Bishop's Line or the
Frankenstein-Dracula would not need a coach, so picking is our job, not
theirs.

This returns one ordered thread of chapters. It carries what to say, where
to stop and ask, and what to say when the answer is wrong -- the tree has
all three on every node, and a lesson that only narrates would waste them.

Ordering is fixed rather than clever: what you got wrong, then the main
line, then the trap that punishes the tempting move, then the sharp
alternative, then what to remember. The one conditional chapter is the
first, and it has to earn its place -- see below.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess

from services.opening_theory_json_service import (
    get_opening_theory,
    resolve_opening_key,
)

# A personal opener only helps when it can name a position and a move. A
# weakness *category* cannot: 49 of the 53 users with one on file are
# "piece_safety", so telling them that is the same sentence for almost
# everybody and reads as coaching while saying nothing.
MAX_PERSONAL_MISTAKES = 2
# Two branches is a lesson; five is a reference manual read aloud.
MAX_TRAP_CHAPTERS = 2


def _plays_white(opening: Dict[str, Any]) -> bool:
    return str(opening.get("color") or "white").lower() != "black"


def _walk_main_line(opening: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The main thread of the tree, as steps that know when to ask.

    Follows the first reply at each turn, which is the authored main line.
    A step for our own move carries the question and the answer for a wrong
    guess; the opponent's move only needs describing.
    """
    tree = opening.get("tree") or {}
    if not tree:
        return _walk_move_ideas(opening)
    board = chess.Board()
    steps: List[Dict[str, Any]] = []

    first_san, node = next(iter(tree.items()))
    try:
        board.push_san(first_san)
    except ValueError:
        return []
    steps.append({
        "move": first_san,
        "side": "white",
        "kind": "ours" if _plays_white(opening) else "theirs",
        "say": str(node.get("idea") or node.get("right_feedback") or "").strip(),
    })

    preview_next = _plays_white(opening)
    for _ in range(40):
        if not isinstance(node, dict):
            break
        taught = str(node.get("next") or "")
        if taught and not preview_next:
            try:
                board.push_san(taught)
            except ValueError:
                break
            steps.append({
                "move": taught,
                "side": "white" if board.turn == chess.BLACK else "black",
                "kind": "ours",
                "say": str(node.get("right_feedback") or node.get("idea") or "").strip(),
                "ask": str(node.get("hint") or "").strip() or None,
                "if_wrong": str(node.get("wrong_feedback") or "").strip() or None,
            })
        preview_next = False

        responses = node.get("responses") or {}
        chosen = None
        for san, child in responses.items():
            probe = board.copy(stack=False)
            try:
                probe.push_san(str(san))
            except ValueError:
                continue
            chosen = (str(san), child, probe)
            break
        if not chosen:
            break
        san, child, board = chosen
        steps.append({
            "move": san,
            "side": "white" if board.turn == chess.BLACK else "black",
            "kind": "theirs",
            "say": str(
                (child or {}).get("idea_opponent")
                or (child or {}).get("name")
                or ""
            ).strip(),
        })
        node = child
    return steps


def _walk_move_ideas(opening: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fallback for the openings that have a line but no branching tree.

    Fifteen publishable openings are in this state -- the Najdorf, the
    Dragon, the Grunfeld among them -- and without this they produce a
    lesson with no chapters at all, which is worse than the tab page we
    are replacing. They still have a main line and authored move ideas, so
    a plain walkthrough is honest: fewer questions, but real explanations.
    """
    main = [str(m) for m in (opening.get("main_line") or []) if str(m).strip()]
    ideas = opening.get("move_ideas") or {}
    if not main:
        return []
    ours_is_white = _plays_white(opening)
    board = chess.Board()
    steps: List[Dict[str, Any]] = []
    for san in main:
        try:
            board.push_san(san)
        except ValueError:
            break
        side = "white" if board.turn == chess.BLACK else "black"
        ours = (side == "white") == ours_is_white
        idea = ideas.get(san) or {}
        steps.append({
            "move": san,
            "side": side,
            "kind": "ours" if ours else "theirs",
            "say": str((idea or {}).get("idea") or "").strip(),
            "arrow": (idea or {}).get("arrow"),
        })
    return steps


def _find_node(opening: Dict[str, Any], path: List[str]) -> Optional[Dict[str, Any]]:
    """Follow a trap's trigger path through the tree, if it is in there."""
    responses = opening.get("tree") or {}
    node = None
    preview = _plays_white(opening)
    index = 0
    while index < len(path):
        san = path[index]
        node = responses.get(san)
        if node is None:
            return None
        index += 1
        taught = str(node.get("next") or "")
        if taught and not preview and index < len(path) and path[index] == taught:
            index += 1
        preview = False
        responses = node.get("responses") or {}
    return node


def _trap_chapters(opening: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Traps, told as a branch off the line we just played.

    Only the kinds where somebody is about to go wrong. A `common_line`
    entry is a normal continuation, and dressing it up as a trap would be
    inventing drama the position does not have.
    """
    chapters = []
    for trap in opening.get("traps") or []:
        kind = str(trap.get("trap_type") or "")
        if kind not in {"punish", "avoid", "only_move", "bait"}:
            continue
        moves = list(trap.get("trigger_after") or [])
        trigger = str(trap.get("trigger_move") or "")
        reply = str(trap.get("our_reply") or "")
        if not (moves and trigger):
            continue
        board = chess.Board()
        ok = True
        for san in moves + [trigger] + ([reply] if reply else []):
            try:
                board.push_san(san)
            except ValueError:
                ok = False
                break
        if not ok:
            continue

        if kind == "avoid":
            intro = (
                f"Now the move that looks obvious here and is not. "
                f"{trap.get('description') or ''}"
            ).strip()
        elif kind == "bait":
            intro = (
                f"This one is a gamble rather than a winning line. "
                f"{trap.get('description') or ''}"
            ).strip()
        else:
            intro = (
                f"Now — what if they play {trigger}? "
                f"{trap.get('description') or ''}"
            ).strip()

        # The tree usually already has a question written for this exact
        # position, and it is a better one than anything generic: "their
        # knight is out on its own and f7 is thin" beats "what does it stop
        # defending?". Only fall back when the trap sits outside the tree.
        node = _find_node(opening, list(moves) + [trigger])
        authored_ask = str((node or {}).get("hint") or "").strip()

        chapters.append({
            "key": f"trap:{trap.get('name')}",
            "title": str(trap.get("name") or "The trap"),
            "kind": "trap",
            "coach_intro": intro,
            "setup_moves": moves,
            "their_move": trigger,
            "ask": authored_ask or (
                "Their move looks natural. What did it stop defending?"
                if kind in {"punish", "only_move"}
                else "Before you play the tempting move, what does it give them?"
            ),
            "answer": reply or None,
            "say": str(trap.get("trap_idea") or "").strip(),
            "takeaway": str(trap.get("simple_lesson") or "").strip() or None,
            "if_declined": str(trap.get("if_declined") or "").strip() or None,
        })
        if len(chapters) >= MAX_TRAP_CHAPTERS:
            break
    return chapters


def _variation_chapter(
    opening: Dict[str, Any],
    already_taught: List[str],
) -> Optional[Dict[str, Any]]:
    """One alternative, framed as a change of mood rather than a menu item.

    Picks the variation that leaves the line we just walked through
    earliest. The first one in the file is often the main line under
    another name -- the Scandinavian's is exd5 Qxd5 Nc3 Qa5, which the
    walkthrough has already played move for move -- and showing a student
    the same moves twice under a new heading is worse than showing nothing.
    """
    variations = opening.get("variations") or {}
    main = list(opening.get("main_line") or [])

    def divergence(moves: List[str]) -> int:
        """How many moves in before this stops repeating the walkthrough."""
        full = main + moves
        for i, san in enumerate(full):
            if i >= len(already_taught) or already_taught[i] != san:
                return i
        return len(full)

    best = None
    for key, data in variations.items():
        if not isinstance(data, dict):
            continue
        moves = list(data.get("moves_from_parent") or []) + list(data.get("continuation") or [])
        if not moves:
            continue
        point = divergence(moves)
        # Nothing new until deep into the line means it is the same lesson.
        if point >= len(already_taught):
            continue
        if best is None or point < best[0]:
            best = (point, key, data, moves)

    if best is None:
        return None
    _, key, data, moves = best
    if True:
        warning = str(data.get("key_warning") or "").strip()
        intro = str(data.get("when_to_play") or "").strip() or (
            "Same position, different mood."
        )
        return {
            "key": f"variation:{key}",
            "title": str(data.get("name") or key),
            "kind": "variation",
            "coach_intro": intro,
            "main_line": list(opening.get("main_line") or []),
            "moves": moves,
            "plan": str(data.get("white_plan") or data.get("black_plan") or "").strip(),
            "warning": warning or None,
        }
    return None


def _personal_chapter(mistakes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Their own mistake, but only when we can name the move.

    Anything vaguer stays out. A chapter that opens "your weakness is piece
    safety" is true of almost every user we have and tells them nothing.
    """
    usable = [
        m for m in (mistakes or [])
        if str(m.get("your_move") or m.get("user_move") or "").strip()
    ][:MAX_PERSONAL_MISTAKES]
    if not usable:
        return None
    first = usable[0]
    played = str(first.get("your_move") or first.get("user_move") or "").strip()
    better = str(first.get("best_move") or "").strip()
    times = len(usable)
    if times > 1:
        opener = f"You have gone wrong here more than once, most recently with {played}."
    else:
        opener = f"Last time you reached this position you played {played}."
    return {
        "key": "your_game",
        "title": "The move that cost you",
        "kind": "your_game",
        "coach_intro": opener,
        "mistakes": usable,
        "ask": "Same position. What would you play now?",
        "answer": better or None,
    }


async def build_lesson_plan(db, user_id: str, opening_key: str) -> Optional[Dict[str, Any]]:
    """One ordered thread for this student, with no choices to make first."""
    resolved = resolve_opening_key(opening_key) or opening_key
    opening = get_opening_theory(resolved)
    if not opening:
        return None

    mistakes: List[Dict[str, Any]] = []
    if db is not None and user_id:
        try:
            from routes.openings import _compute_opening_mistakes

            mistakes = await _compute_opening_mistakes(user_id, resolved) or []
        except Exception:
            # A personal opener is an upgrade. Losing it must never cost the
            # student the lesson.
            mistakes = []

    chapters: List[Dict[str, Any]] = []

    personal = _personal_chapter(mistakes)
    if personal:
        chapters.append(personal)

    steps = _walk_main_line(opening)
    if steps:
        chapters.append({
            "key": "main_line",
            "title": "The main line",
            "kind": "walkthrough",
            "coach_intro": (
                str(opening.get("summary") or "").strip()
                if not personal
                else "Now the line itself, so you can see where that move came from."
            ),
            "steps": steps,
        })

    chapters.extend(_trap_chapters(opening))

    taught_moves = [str(step["move"]) for step in steps]
    variation = _variation_chapter(opening, taught_moves)
    if variation:
        chapters.append(variation)

    # The openings without a tree tend to have no golden_rules either, and a
    # lesson that just stops after the last move feels unfinished.
    remember = [
        str(r).strip()
        for r in (opening.get("golden_rules") or opening.get("common_learnings") or [])
        if str(r).strip()
    ]
    if remember:
        chapters.append({
            "key": "close",
            "title": "What to remember",
            "kind": "close",
            "coach_intro": "Three things worth keeping.",
            "remember": remember[:3],
        })

    return {
        "opening_key": resolved,
        "name": opening.get("name"),
        "color": opening.get("color"),
        "personalised": bool(personal),
        "chapters": chapters,
    }

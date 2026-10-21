"""You walked away from your own guard: four sentence shapes, pieces named
from the board.

Mohit 2026-10-21 sent back the card my own fallback wrote:

    "This move cost you something. Compare it with the engine's line below."

It is honest and it teaches nothing, which makes it worse than silence because
it occupies the slot where the lesson goes. The board on that card says
something a player can use: the e-pawn was guarding d5, it pushed, and d5 fell.

Shapes chosen from the distribution, not from taste. Over 435 cases in 2,500
analysed games:

    no guard left           339   78.0%
    still has help, quiet    76   17.5%
    still has help, check    20    4.6%

There were four shapes for a while, splitting the no-guard case by check as
well. Reading the cards killed that split. When nothing is left guarding the
piece, the check is not why it fell -- it was simply undefended -- and the
card was ending on "look for their checks before you call a piece safe" about
a queen that no longer had a guard at all. A true fact, the wrong lesson. The
check now earns a shape only where it does real work: the piece DID still have
help, and the check is the reason that help never arrived.

Which piece walked away (queen 34.5%, knight 20.0%, pawn 17.4%, rook 15.5%,
bishop 12.6%) and what was lost (pawn 60.9%) are slots filled from the board,
not branches -- the same discipline as `atd_caption.py`.

The word this file refuses is "only". I checked it before writing it: 390 of
the 395 no-guard-left cases did have a single guard, so "the only thing
guarding it" reads true almost always. The other five are positions where the
move walked one guard away AND blocked the second one's line -- a black pawn
to d5 stepping in front of its own rook on e5, cutting it off from c5. Two
guards, one move, none left. So the card says "nothing is guarding it now",
which is true in all 395 and is plainer English besides.

Checks earn their own shape because the check is the ANSWER to the obvious
objection. A player looks at the e3 bishop, sees the f-pawn still guarding it,
and concludes it was safe. It was not: the rook took it with check, the check
had to be answered, and the recapture never came. That is worth a sentence.

The first draft of those two shapes said "the king had to move first". It is
the natural thing to write and it is false: `Qxg4+` was answered by `Qg3` and
`Nxc6+` by `Be7` -- a block, not a king move. A check can be answered three
ways and the card may only claim the one the clause proved, which is that the
piece was never won back.
"""
from typing import Any, Dict, Optional, Sequence

import chess

PIECE_WORD = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king",
}

PRINCIPLE = {
    "NO_GUARD": "Before you move a piece, check what it is holding.",
    "SHORT_QUIET": "A piece with help can still fall. "
                   "Play the trade out before you trust it.",
    "SHORT_CHECK": "A guarded piece is not safe "
                   "if they can take it with check.",
}


def _left_verb(verb: str, mine: bool) -> str:
    """How the guard went away, in the plainest words available.

    The verb itself is decided by the question, so a pawn reads "pushed" here
    and in the short lead clause alike.
    """
    return f"{'you' if mine else 'they'} {verb} it"


def render_self_removal_caption(
    board_before: chess.Board,
    answer: Dict[str, Any],
    *,
    line_san: Optional[Sequence[str]] = None,
    mover_is_user: bool = True,
) -> Optional[Dict[str, Any]]:
    """One card from one `q_abandoned_own_defender` answer.

    `answer` is the dict that question returns. `board_before` must be the
    board it was asked about, so every piece word is read off the board again
    rather than trusted from the dict.
    """
    us = board_before.turn
    try:
        guard_sq = chess.parse_square(answer["guard_from"])
        lost_sq = chess.parse_square(answer["square"])
    except (KeyError, ValueError):
        return None
    guard = board_before.piece_at(guard_sq)
    lost = board_before.piece_at(lost_sq)
    if guard is None or lost is None:
        return None
    if guard.color != us or lost.color != us:
        return None

    # The shape, the verb and the check all come from the answer. This file
    # does not recompute them: it is the second surface that renders this
    # concept and the first one decided them, so recomputing here is how the
    # two surfaces end up telling a player different things.
    shape = str(answer.get("shape") or "")
    if shape not in PRINCIPLE:
        return None
    guards_left = int(answer.get("guards_left") or 0)
    check = bool(answer.get("gives_check"))

    gw = PIECE_WORD[guard.piece_type]
    lw = PIECE_WORD[lost.piece_type]
    taker = str(answer.get("taken_by") or "piece")
    gsq, lsq = answer["guard_from"], answer["square"]
    mine, theirs = ("your", "their") if mover_is_user else ("their", "your")
    Mine = mine.capitalize()
    went = _left_verb(str(answer.get("guard_verb") or "moved"), mover_is_user)

    if shape == "NO_GUARD":
        took = "took it with check" if check else "took it"
        body = (f"{Mine} {gw} on {gsq} was guarding {mine} {lw} on {lsq}. "
                f"Once {went}, nothing was guarding the {lw}, "
                f"and {theirs} {taker} {took}.")
    elif shape == "SHORT_CHECK":
        body = (f"{Mine} {gw} on {gsq} was helping to guard {mine} {lw} "
                f"on {lsq}. The {lw} still had help, so it looked safe. "
                f"But {theirs} {taker} took it with check. "
                f"{'You' if mover_is_user else 'They'} had to answer the "
                f"check, and the {lw} was gone.")
    else:
        body = (f"{Mine} {gw} on {gsq} was helping to guard {mine} {lw} "
                f"on {lsq}. After {went}, the {lw} was short of help. "
                f"{theirs.capitalize()} {taker} won it in the trades "
                f"that followed.")

    caption = f"{body} {PRINCIPLE[shape]}"
    return {
        "shape": shape,
        "caption": caption,
        "words": len(caption.split()),
        "guards_left": guards_left,
        "gives_check": check,
        "guard": gw,
        "lost": lw,
        "taker": taker,
    }


"""An opening mistake, taught as opening theory.

Mohit 2026-10-10, on 2...Bg4 in a Philidor badged "inaccuracy" at 51cp with no
explanation: "it should be captioned in as an opening teaching... which
opening, what's better in this opening... a theory to remember".

WHAT IS AND IS NOT AVAILABLE, measured before this was written:

  flagged opening-phase moves in his games        7,561
  at move 4 or later                              6,787   (89.8%)
  deepest tree in the whole curriculum            7 plies
  main_line fields                                median 4 tokens -- the
                                                  opening's NAME, not a book line
  move_ideas                                      keyed by SAN, first few moves only

So nothing authored reaches 90% of his opening mistakes, and authoring more of
the same would not either. What DOES reach them is the engine plus the board,
which is what every other lesson in this codebase already runs on. The
curriculum contributes the one thing the board cannot: the opening's name, and
an authored idea where the recommended move happens to have one.

Two attempts were measured and thrown away before this one:

  - attaching the entry's `golden_rules` directly put "Play d5 on move one"
    on a move-7 knight retreat, served Black's rule to White in a Slav, and
    had no way to choose which of four rules applied.
  - writing a competing caption named the opening and DROPPED the reason.
    "You played a5; h6 was stronger -- it attacks the bishop on g5" became
    (quoted as a worked example, not produced here)
    "In the Bishops Opening Berlin Defense, h6 is the move here." A name is
    not worth a why.

So this decorates rather than replaces: the opening name is a prefix on the
caption the pipeline already produced, and if that caption has no reason this
module does not pretend to supply one.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import chess

_CURRICULUM_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "opening_curriculum.json")
_CURRICULUM: Optional[Dict[str, Any]] = None
_BY_NAME: Optional[Dict[str, Dict[str, Any]]] = None

# The opening phase, matching how the review cards already label it.
_MAX_OPENING_MOVE = 12


def _curriculum() -> Dict[str, Any]:
    global _CURRICULUM
    if _CURRICULUM is None:
        with open(os.path.abspath(_CURRICULUM_PATH), encoding="utf-8") as fh:
            _CURRICULUM = json.load(fh)
    return _CURRICULUM


def _by_name() -> Dict[str, Dict[str, Any]]:
    """Longest authored name first, so "Italian Game Two Knights" does not
    match the bare "Italian Game" entry when the specific one exists."""
    global _BY_NAME
    if _BY_NAME is None:
        pairs = []
        for key, entry in _curriculum().items():
            name = (entry.get("name") or "").strip().lower()
            if name:
                pairs.append((name, {"key": key, **entry}))
        pairs.sort(key=lambda kv: -len(kv[0]))
        _BY_NAME = dict(pairs)
    return _BY_NAME


def lookup_opening(opening_name: Optional[str], mover_is_white: bool,
                   needs_our_side: bool = False) -> Optional[Dict[str, Any]]:
    """The curriculum entry for this opening.

    `needs_our_side` gates on the colour the entry is WRITTEN for, and is only
    correct when we are about to quote its authored prose: matching on name
    alone once served "c6 holds d5 without locking in the bishop" -- Black's
    rule -- on White's Bf4 in a Slav.

    It is wrong for the opening's NAME, which belongs to both players. Gating
    the name on colour rejected 884 of 2,798 otherwise-matchable cards to
    prevent a bug that only the prose could have.
    """
    if not opening_name:
        return None
    low = opening_name.strip().lower()
    for name, entry in _by_name().items():
        if low.startswith(name) or name in low:
            if needs_our_side:
                colour = (entry.get("color") or "").strip().lower()
                if colour in ("white", "black") and (colour == "white") != bool(mover_is_white):
                    continue
            return entry
    return None


@dataclass
class OpeningLesson:
    opening_key: str
    opening_name: str
    caption: str
    arrows: List[Dict[str, str]] = field(default_factory=list)
    authored_idea: bool = False


def _arrow(frm: str, to: str, colour: str) -> Dict[str, str]:
    return {"from": frm, "to": to, "color": colour, "teach": True}


def name_the_opening(
    caption: str,
    fen_before: str,
    move_number: int,
    best_move_san: Optional[str],
    opening_name: Optional[str],
) -> Optional[OpeningLesson]:
    """Prefix an existing opening-phase caption with the opening it belongs to.

    Only where the lesson is opening-specific, which here means: the opening
    phase, a named opening written for OUR side, and a caption that already
    names the better move. Mohit has ruled that naming the opening everywhere
    is noise -- feedback_opening_name_only_at_critical_lessons.
    """
    if not caption or not caption.strip():
        return None
    if not isinstance(move_number, int) or move_number > _MAX_OPENING_MOVE:
        return None
    if not best_move_san or best_move_san not in caption:
        return None
    try:
        board = chess.Board(fen_before)
        best = board.parse_san(str(best_move_san))
    except (ValueError, AssertionError, TypeError):
        return None
    entry = lookup_opening(opening_name, board.turn == chess.WHITE)
    if entry is None:
        return None

    display = (entry.get("name") or opening_name or "").strip()
    if display.lower() in caption.lower():
        return None                      # it already says so

    text = caption.strip()
    # Lowercasing the first character turned "Ne4 lets Qf3 attack..." into
    # "ne4 lets Qf3 attack...". A caption that opens with the move must keep
    # its capital; only an ordinary word gets folded.
    first = text.split(" ", 1)[0].rstrip(",;:.")
    _SAN = re.compile(r"^(O-O(-O)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?)$")
    if _SAN.match(first):
        out = f"In the {display}, {text}"
    else:
        out = f"In the {display}, {text[0].lower()}{text[1:]}"

    # An authored idea for the recommended move, where one exists, is the one
    # thing the curriculum has that the board does not. 36 of 476 cards.
    # The authored idea IS prose, so it only applies if the entry is written
    # for our side. The name above is not.
    own_side = lookup_opening(opening_name, board.turn == chess.WHITE,
                              needs_our_side=True)
    idea = {}
    if own_side is not None and own_side.get("key") == entry.get("key"):
        idea = ((entry.get("move_ideas") or {}).get(best_move_san) or {})
    why = (idea.get("idea") or "").strip()
    authored = False
    if why and why.rstrip(".").lower() not in out.lower():
        out = out.rstrip() + (" " if out.endswith(".") else ". ") + why
        authored = True

    arrows = [_arrow(chess.square_name(best.from_square),
                     chess.square_name(best.to_square), "blue")]
    authored_arrow = idea.get("arrow")
    if (isinstance(authored_arrow, list) and len(authored_arrow) == 2
            and board.piece_at(chess.parse_square(authored_arrow[0])) is not None):
        arrows = [_arrow(authored_arrow[0], authored_arrow[1], "blue")]
    return OpeningLesson(entry["key"], display, out, arrows, authored)

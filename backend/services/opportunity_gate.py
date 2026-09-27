"""Was the right move a tactical shape, and did the player play it?

docs/two_layer_coaching_scope.md, signed off 2026-09-28.

This is the denominator, and the denominator is the whole architecture. A count
of missed forks says nothing; a count of missed forks OUT OF THE FORKS THAT WERE
THERE is knowledge. Turning one into the other is all this module does.

WHY THE ENGINE GATE IS NOT OPTIONAL
-----------------------------------
`shape_detectors` answer "does a move of this shape exist", which is a much
weaker thing than "was this the right move". Measured on production 2026-09-28,
the difference is everything:

    loose  ("a fork-shaped move exists")   12,013 chances   11.2% taken
                                           spread across players 0.09 - 0.14
    gated  ("the engine's best move IS a   1,384 chances    51.7% taken
            fork")                         spread across players 0.38 - 0.58

The loose number measures how generous `detect_knight_fork` is. Only the gated
one measures the player. I built the loose version first and it looked like a
finding, which is why this module exists rather than each caller deciding.

THE GRAIN: POOLED, NOT PER PATTERN
----------------------------------
A single pattern's rate is NOT stable enough to describe a person. Fork
take-rate, a player's first half of games against their second:

    bar 10 chances   48 players   r = +0.41
    bar 20 chances   39 players   r = +0.33
    bar 30 chances   30 players   r = +0.57     non-monotonic -- noise

Pooled across the shapes, it is:

    bar  20 chances   54 players   r = +0.70
    bar  40 chances   53 players   r = +0.72
    bar  60 chances   50 players   r = +0.71
    bar 100 chances   46 players   r = +0.73     flat at every bar -- a trait

About fifteen chances per half at a rate near one half carries a standard error
of roughly 0.13, which flattens any real signal. So the person-level claim is
POOLED ("you are not seeing tactical shapes") and the pattern is only how the
drill gets chosen. Saying "you do not know forks" off fifteen samples would be
confidence built on noise.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import chess

from services import shape_detectors as _sd

# Every shape whose detector can name the move that executes it. Grouped by the
# name a player would recognise, not by the piece doing it -- a knight fork and a
# queen fork are the same idea to the person being coached.
_SHAPE_DETECTORS: Tuple[Tuple[str, Any], ...] = (
    ("fork", _sd.detect_knight_fork),
    ("fork", _sd.detect_bishop_fork),
    ("fork", _sd.detect_rook_fork),
    ("fork", _sd.detect_queen_fork),
    ("fork", _sd.detect_pawn_fork),
    ("free_piece", _sd.detect_free_piece),
    ("free_piece", _sd.detect_free_pawn),
    ("pin", _sd.detect_pin),
    ("skewer", _sd.detect_skewer),
)

# Measured 2026-09-28 over 555,202 moves: of 50,251 gated opportunities,
# free_piece produced 26,522 and fork 23,729. `pin` and `skewer` produced ZERO --
# the engine's best move never once matched their executing move. They stay in
# the tuple above so they light up automatically if that is fixed, and they are
# named here so a reader is not left wondering whether they were forgotten.
SILENT_WITH_THIS_GATE = frozenset({"pin", "skewer"})

# The lowest bar at which the pooled rate behaves like a trait (r = +0.70), and
# it keeps 54 of 57 players. Taken from the measurement above, not chosen.
MIN_CHANCES_TO_JUDGE = 20


def shape_of_best_move(fen: str, best_move_uci: Optional[str]) -> Optional[str]:
    """Which tactical shape the ENGINE'S BEST MOVE creates, or None.

    None means "this position is not an opportunity", which is the common case
    and the correct answer. With no engine best move there is no opportunity at
    all: a shape that exists is not a shape that was right.
    """
    if not fen or not best_move_uci:
        return None
    try:
        board = chess.Board(fen)
        best = chess.Move.from_uci(str(best_move_uci))
    except Exception:
        return None
    if best not in board.legal_moves:
        return None
    for name, detector in _SHAPE_DETECTORS:
        try:
            events = detector(board)
        except Exception:
            continue
        for event in events or ():
            executing = event.get("executing_move")
            if executing and str(executing) == str(best_move_uci):
                return name
    return None


def observe(fen: str, best_move_uci: Optional[str],
            played_uci: Optional[str]) -> Optional[Dict[str, Any]]:
    """One opportunity and whether the player took it, or None if not one.

    "Took it" is exact agreement with the engine's move. A different move that
    happens to be sound is not taking THIS chance -- the question is whether he
    saw this shape, and a good move found another way does not answer it.
    """
    shape = shape_of_best_move(fen, best_move_uci)
    if shape is None:
        return None
    return {
        "pattern": shape,
        "took": bool(played_uci) and str(played_uci) == str(best_move_uci),
    }


def pooled_knowledge(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """The player-level knowledge reading, pooled across shapes.

    `rows` are `observe` results. `judgeable` is the whole point: below
    MIN_CHANCES_TO_JUDGE the rate is noise with a decimal point, and the caller
    must say nothing rather than guess quietly.

    `by_pattern` is reported for choosing the DRILL, never for describing the
    player -- see the module docstring on grain.
    """
    rows = [r for r in (rows or ()) if r]
    chances = len(rows)
    took = sum(1 for r in rows if r.get("took"))
    by_pattern: Dict[str, Dict[str, int]] = {}
    for row in rows:
        slot = by_pattern.setdefault(str(row.get("pattern")),
                                     {"chances": 0, "took": 0})
        slot["chances"] += 1
        slot["took"] += 1 if row.get("took") else 0
    return {
        "chances": chances,
        "took": took,
        "missed": chances - took,
        # internal only: a rate is never rendered, per the no-numbers rule
        "_rate": (took / chances) if chances else None,
        "judgeable": chances >= MIN_CHANCES_TO_JUDGE,
        "by_pattern": by_pattern,
    }


def weakest_pattern(pooled: Dict[str, Any],
                    min_chances: int = 5) -> Optional[str]:
    """Which shape to DRILL, given a pooled reading.

    Deliberately separate from the diagnosis. The person-level claim comes from
    `pooled`; this only picks the exercise, so a thinner bar is acceptable here
    than for judging somebody.
    """
    candidates = [
        (slot["took"] / slot["chances"], name)
        for name, slot in (pooled.get("by_pattern") or {}).items()
        if slot.get("chances", 0) >= min_chances
    ]
    return min(candidates)[1] if candidates else None

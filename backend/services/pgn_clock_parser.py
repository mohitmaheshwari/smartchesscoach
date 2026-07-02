"""
PGN Clock Parser — extract per-move `time_spent` and `time_left` from
`%clk` annotations that chess.com + Lichess embed in every PGN.

Contract:
    parse_clocks_from_pgn(pgn) → List[Optional[float]]
        Halfmove-indexed clock-remaining in seconds. Index 0 = after
        white's move 1, Index 1 = after black's move 1, etc.
        None entries mean the annotation was missing at that position.

    parse_increment_from_pgn(pgn) → int
        Seconds of increment (e.g., 5 for "600+5"). 0 if not present.

    time_spent_at_halfmove(clocks, halfmove_idx, increment) → Optional[float]
        Seconds the player spent on that half-move.
        Formula: clocks[halfmove_idx - 2] - clocks[halfmove_idx] + increment
        Returns None for halfmove_idx < 2 (opening moves have no prior clock).

    halfmove_index(move_number, user_color) → int
        Map move_number + color to halfmove index.
        (1, "white") → 0, (1, "black") → 1, (2, "white") → 2, ...

Design notes:
- We ignore mate/stalemate/timeout-triggering last-move edge cases where
  the clock jumps to 0. Those get a `time_spent` value but not a `time_left`
  flag.
- Multi-format PGNs (chess.com, Lichess, PGN Extract) all use identical
  `%clk` syntax: `[%clk 0:09:59.1]` — hours:minutes:seconds.
- We DON'T try to detect increment from clock deltas — we rely on the
  `[TimeControl "base+increment"]` header. Chess.com always includes it.
"""
import re
from typing import List, Optional

_CLK_RE = re.compile(r"\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]")
_TC_RE = re.compile(r'\[TimeControl\s+"(\d+)\+(\d+)"\]')


def parse_clocks_from_pgn(pgn: str) -> List[Optional[float]]:
    """Return list of clock-remaining-seconds per halfmove in encounter order.

    Note: this returns a flat list of ALL `%clk` matches in order. It
    doesn't validate that every halfmove has one — chess.com's PGNs are
    reliable but we don't hard-fail if one is missing.
    """
    if not pgn:
        return []
    out: List[Optional[float]] = []
    for match in _CLK_RE.finditer(pgn):
        h, m, s = match.groups()
        try:
            secs = int(h) * 3600 + int(m) * 60 + float(s)
        except ValueError:
            secs = None
        out.append(secs)
    return out


def parse_increment_from_pgn(pgn: str) -> int:
    """Extract increment seconds from `[TimeControl "600+5"]`.
    Returns 0 if the format doesn't match (many older PGNs, correspondence)."""
    if not pgn:
        return 0
    m = _TC_RE.search(pgn)
    if m:
        try:
            return int(m.group(2))
        except ValueError:
            return 0
    return 0


def halfmove_index(move_number: int, user_color: str) -> int:
    """(1, 'white') → 0, (1, 'black') → 1, (2, 'white') → 2, ..."""
    if move_number < 1:
        return 0
    base = (move_number - 1) * 2
    return base + (0 if user_color == "white" else 1)


def time_spent_at_halfmove(
    clocks: List[Optional[float]],
    halfmove_idx: int,
    increment: int = 0,
) -> Optional[float]:
    """Compute seconds spent on the move at halfmove_idx.

    Formula: previous same-color clock - current same-color clock + increment.
    The 'previous same-color clock' is halfmove_idx - 2 (two halfmoves back).
    """
    if halfmove_idx < 2 or halfmove_idx >= len(clocks):
        return None
    prev_idx = halfmove_idx - 2
    if prev_idx < 0 or prev_idx >= len(clocks):
        return None
    prev = clocks[prev_idx]
    curr = clocks[halfmove_idx]
    if prev is None or curr is None:
        return None
    spent = prev - curr + increment
    # Clamp — sometimes the last move recorded shows time=0 (timeout),
    # producing bogus large numbers if the prior clock was near-zero
    if spent < 0:
        return 0.0
    if spent > 3600:   # more than an hour on one move is a data glitch
        return None
    return round(spent, 1)


def time_left_at_halfmove(
    clocks: List[Optional[float]], halfmove_idx: int
) -> Optional[float]:
    """Clock remaining AFTER the move at halfmove_idx (i.e., the value stored
    at that index in the PGN)."""
    if halfmove_idx < 0 or halfmove_idx >= len(clocks):
        return None
    return clocks[halfmove_idx]

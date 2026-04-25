"""
Move-Time Analyzer
==================

Extracts per-ply think-time from PGN `[%clk h:mm:ss]` annotations and
derives per-game discipline stats. Cheap (regex + arithmetic, no engine
calls). Plays into the Mirror's voice as "you rushed the critical move"
or "you took your time" signals.

Why personal-baseline comparisons (not absolute thresholds): a 2-second
move is normal in bullet, rushed in rapid. Comparing each move's time
against the SAME USER'S median sidesteps that — if you usually take 5s
but spent 1s on the worst-blunder move, that's a real "you didn't
think" signal regardless of time control.

Honest gating:
  • If the PGN has no clk tags → return None. The Mirror skips the
    time line entirely. We never fabricate.
  • Increment is added to time-elapsed per ply. Time-control format
    "300+3" gives 3s increment; we account for it so the deltas reflect
    actual think-time, not clock-display change.

Storage shape (added to db.games doc as `move_time_stats`):
  {
    "median_user_move_s": float,
    "user_move_count": int,
    "critical_move_time_s": float | None,   # time spent on worst-cp-loss move
    "critical_move_number": int | None,
    "rushed_critical": bool,                # critical < 0.5 * median user pace
    "took_time_critical": bool,             # critical > 2.0 * median user pace
  }
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CLK_RE = re.compile(r"\[%clk\s+([0-9]+):([0-9]+):([0-9]+(?:\.[0-9]+)?)\]")
# Time-control fields we expect: "300+3" / "180+0" / "60" etc.
_TC_RE = re.compile(r"^(\d+)(?:\+(\d+))?$")


def _parse_increment(time_control: Optional[str]) -> int:
    if not time_control:
        return 0
    m = _TC_RE.match(time_control.strip())
    if not m:
        return 0
    return int(m.group(2) or 0)


def _extract_clk_per_ply(pgn: str) -> List[Optional[float]]:
    """Return one entry per ply: clock seconds remaining for the player
    who just moved, or None if that ply has no clk tag.

    Walks moves in order. The clk tag immediately after a move belongs
    to that move (= time remaining AFTER making the move).
    """
    if not pgn:
        return []

    # Strip PGN headers — keep only the move text.
    lines = []
    for line in pgn.splitlines():
        if line.startswith("[") and line.endswith("]"):
            continue
        lines.append(line)
    move_text = " ".join(lines)

    # Tokenize loosely: walk through the text and pair (ply_index, clk_remaining).
    # We don't need to parse SAN — we just need to know how many plies
    # there are and which ones have clk values.
    # Approach: split by move-number markers and clk tags.
    clks: List[Optional[float]] = []
    # Each move (white or black) starts with either a number "1." or "1..."
    # OR is the second move of a numbered pair. clk tags follow move tokens.
    # Simpler: walk tokens, and on every clk tag append; insert None for
    # plies that lack one. We approximate ply count via SAN-token counting.
    # Use a regex that captures either a SAN token OR a clk annotation.
    token_re = re.compile(
        r"\{[^}]*\}|\([^)]*\)|"                # comments/variations to skip-but-scan
        r"\b\d+\.(?:\.\.)?|"                   # move numbers (1. or 1...)
        r"\$\d+|"                              # NAGs
        r"[\w+#=\-\/]+[!?]*"                   # SAN-ish tokens
    )

    # Walk tokens. A SAN token appends a None placeholder; a subsequent
    # clk-bearing comment fills the most recent placeholder. PGN
    # convention: `1. e4 {[%clk ...]}` — the clk is the time-remaining
    # AFTER playing e4, so it belongs to that move (the last one we saw).
    for tok in token_re.finditer(move_text):
        s = tok.group(0)
        if s.startswith("{") or s.startswith("("):
            m = _CLK_RE.search(s)
            if m and clks:
                h, mi, se = int(m.group(1)), int(m.group(2)), float(m.group(3))
                clks[-1] = h * 3600 + mi * 60 + se
            continue
        if re.match(r"^\d+\.(?:\.\.)?$", s) or s.startswith("$"):
            continue
        if s in ("1-0", "0-1", "1/2-1/2", "*"):
            continue
        clks.append(None)

    return clks


def _per_ply_time_spent(
    clks: List[Optional[float]],
    increment_s: int,
) -> List[Optional[float]]:
    """Convert clock-remaining values into time-spent-per-move.

    For ply k of a given side:
        time_spent[k] = clk_before[k] - clk[k] + increment

    where clk_before[k] is the same player's clock from THEIR previous
    ply (or game start if k=0). We don't know game-start clock per side,
    so the FIRST move of each side has time_spent = None unless we make
    an assumption — leave it None to stay honest.
    """
    out: List[Optional[float]] = [None] * len(clks)

    # Walk white plies (index 0, 2, 4, ...) and black plies (1, 3, 5, ...) separately.
    for side_start in (0, 1):
        prev_clk: Optional[float] = None
        for i in range(side_start, len(clks), 2):
            curr = clks[i]
            if curr is None or prev_clk is None:
                out[i] = None
            else:
                spent = (prev_clk - curr) + increment_s
                # Negative or absurd values mean the clock data was
                # inconsistent — skip rather than report nonsense.
                if spent < 0 or spent > 24 * 3600:
                    out[i] = None
                else:
                    out[i] = round(spent, 2)
            if curr is not None:
                prev_clk = curr
    return out


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def compute_move_time_stats(
    pgn: str,
    user_color: str,
    time_control: Optional[str],
    move_evaluations: Optional[List[Dict]] = None,
) -> Optional[Dict]:
    """Compute the per-game move-time discipline stats. Returns None when
    the PGN has no usable clock data — honest gating.

    Args:
        pgn: full PGN string (with clk annotations).
        user_color: "white" or "black".
        time_control: e.g. "300+3" — used to derive increment.
        move_evaluations: optional, used to identify the critical move
            (highest cp_loss). When omitted we skip the critical-move
            sub-stats but still return median pace.
    """
    clks = _extract_clk_per_ply(pgn or "")
    if not clks or all(c is None for c in clks):
        return None

    increment = _parse_increment(time_control)
    spent = _per_ply_time_spent(clks, increment)

    user_is_white = (user_color or "white").lower() == "white"
    # Cleanup: keep only finite times for the median calc (None entries
    # are kept in `spent` so ply-index lookups still align).
    user_clean_times = [
        spent[i] for i in range(len(spent))
        if ((i % 2 == 0) == user_is_white) and spent[i] is not None
    ]

    if len(user_clean_times) < 3:
        # Too few clean samples — don't report a median we can't trust.
        return None

    median_pace = _median(user_clean_times)
    if median_pace <= 0:
        return None

    stats: Dict = {
        "median_user_move_s": round(median_pace, 2),
        "user_move_count": len(user_clean_times),
        "critical_move_time_s": None,
        "critical_move_number": None,
        "rushed_critical": False,
        "took_time_critical": False,
    }

    # Pick the critical (worst-cp-loss) USER move and look up its time
    # by directly indexing into `spent` — both arrays are ply-ordered.
    if move_evaluations and len(move_evaluations) == len(spent):
        worst_cp = 0
        worst_move_num: Optional[int] = None
        worst_ply_idx: Optional[int] = None
        for idx, ev in enumerate(move_evaluations):
            cp = ev.get("cp_loss") or 0
            if cp <= worst_cp or cp >= 5000:
                continue
            fb = ev.get("fen_before") or ""
            parts = fb.split()
            active = parts[1] if len(parts) >= 2 else ""
            if (active == "w") != user_is_white:
                continue
            worst_cp = cp
            worst_move_num = ev.get("move_number")
            worst_ply_idx = idx

        if worst_ply_idx is not None:
            t = spent[worst_ply_idx]
            stats["critical_move_time_s"] = t
            stats["critical_move_number"] = worst_move_num
            if t is not None and median_pace > 0:
                if t < 0.5 * median_pace:
                    stats["rushed_critical"] = True
                elif t > 2.0 * median_pace:
                    stats["took_time_critical"] = True

    return stats

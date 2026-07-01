"""
Game Context Enricher — Theme 2.

Derives 3 small but high-value fields on each game from data that's
already stored:
  - time_control_category  — blitz | rapid | classical (parsed from time_control)
  - opponent_rating        — from PGN WhiteElo / BlackElo by user_color
  - user_rating            — same, for the user's color (canonical "what
                              elo was the user at when this game was played")

These power rating-aware coaching messaging, time-control segmentation
in stats ("your blunder rate in blitz vs rapid"), and opponent-quality
context ("your wins are mostly vs lower-rated opponents").

No new data collection — pure derivation.
"""
import re
from typing import Optional, Dict, Any

# Time-control category by base seconds (per chess.com convention)
def classify_time_control(tc: str) -> Optional[str]:
    """tc can be many forms in this corpus:
      - '900+10' / '180+2' — standard base+inc format
      - '600' / '300'       — bare base seconds (no increment)
      - 'rapid' / 'blitz' / 'bullet' / 'classical' / 'daily' — already a category
      - '1/86400'           — chess.com daily (seconds-per-move)
      - 'untimed' / '-' / '' — no time control
    Returns the category name or None for untimed/unknown.
    """
    if not tc:
        return None
    tc = str(tc).strip().lower()
    # Already-a-category strings (Lichess sometimes stores these)
    if tc in ("bullet", "blitz", "rapid", "classical", "daily", "correspondence"):
        return "correspondence" if tc == "daily" else tc
    # No time control
    if tc in ("untimed", "-", "0", "0+0"):
        return None
    # Daily (correspondence) — chess.com uses '1/N' where N is seconds per move
    if tc.startswith("1/"):
        return "daily"
    # Bare number = base seconds, no increment
    m_bare = re.match(r"^(\d+)$", tc)
    if m_bare:
        base = int(m_bare.group(1))
        inc = 0
    else:
        # Standard "base+inc" format
        m = re.match(r"^(\d+)\+(\d+)$", tc)
        if not m:
            return None
        base, inc = int(m.group(1)), int(m.group(2))
    # Estimate game duration as base + 40 * inc (40-move estimate)
    estimated = base + 40 * inc
    if estimated < 180:    return "bullet"      # < 3 min
    if estimated < 600:    return "blitz"       # < 10 min
    if estimated < 1500:   return "rapid"       # < 25 min
    return "classical"


_HEADER_RE = re.compile(r'\[(\w+)\s+"([^"]*)"\]')

def parse_pgn_headers(pgn: str) -> Dict[str, str]:
    """Extract all PGN headers as a flat dict. Lowercase keys."""
    if not pgn:
        return {}
    out = {}
    for m in _HEADER_RE.finditer(pgn):
        out[m.group(1).lower()] = m.group(2)
    return out


def _safe_int(v) -> Optional[int]:
    try:
        n = int(v)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def derive_context_fields(game_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Returns the fields to $set on this game.

    Pure function. Reads PGN + existing fields, derives:
      - time_control_category
      - white_rating, black_rating
      - user_rating, opponent_rating
    """
    pgn = game_doc.get("pgn") or ""
    headers = parse_pgn_headers(pgn)
    user_color = game_doc.get("user_color") or "white"

    white_rating = _safe_int(headers.get("whiteelo"))
    black_rating = _safe_int(headers.get("blackelo"))

    if user_color == "white":
        user_rating, opponent_rating = white_rating, black_rating
    else:
        user_rating, opponent_rating = black_rating, white_rating

    tc = game_doc.get("time_control") or headers.get("timecontrol")
    tc_cat = classify_time_control(tc) if tc else None

    out: Dict[str, Any] = {}
    if tc_cat is not None:
        out["time_control_category"] = tc_cat
    if white_rating is not None:
        out["white_rating"] = white_rating
    if black_rating is not None:
        out["black_rating"] = black_rating
    if user_rating is not None:
        out["user_rating"] = user_rating
    if opponent_rating is not None:
        out["opponent_rating"] = opponent_rating
    # Rating gap: positive = user was higher rated
    if user_rating is not None and opponent_rating is not None:
        out["rating_gap"] = user_rating - opponent_rating
    return out


def opponent_strength_label(rating_gap: int) -> str:
    """Human label for the rating gap (used in coaching messages)."""
    if rating_gap >= 200: return "much weaker"
    if rating_gap >= 75:  return "weaker"
    if rating_gap >= -75: return "evenly matched"
    if rating_gap >= -200: return "stronger"
    return "much stronger"

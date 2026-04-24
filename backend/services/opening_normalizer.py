"""
Opening Name Normalizer
=======================

chess.com / lichess store `opening` as free-text ECO-verbose names like
"Nimzowitsch Defense Scandinavian Bogoljubov Vehre Variation 4.e5" or
"Queens Pawn Opening Accelerated London System". For per-user repertoire
analysis we need to collapse those verbose names to a small set of
canonical families ("Scandinavian Defense", "London System", etc.).

Deterministic: first keyword match wins. Order matters — most specific
families first (e.g. "London" matched before "Queens Pawn" so that
"Queens Pawn Opening Accelerated London System" → London, not QP).
"""

from __future__ import annotations
from typing import Optional

# Ordered list of (keyword, canonical_name). First keyword found in the
# opening string (case-insensitive) determines the family. Tuned to the
# verbose names chess.com produces.
_PRIORITY_MATCHES = [
    # Italian family (specific before general)
    ("Fried Liver", "Italian Game"),
    ("Giuoco", "Italian Game"),
    ("Italian", "Italian Game"),
    # Ruy Lopez
    ("Ruy Lopez", "Ruy Lopez"),
    ("Spanish Game", "Ruy Lopez"),
    # Scandinavian — often buried in long verbose names
    ("Scandinavian", "Scandinavian Defense"),
    # London System — matches before Queens Pawn
    ("London System", "London System"),
    ("London", "London System"),
    # Caro-Kann
    ("Caro-Kann", "Caro-Kann"),
    ("CaroKann", "Caro-Kann"),
    # French
    ("French Defense", "French Defense"),
    ("French", "French Defense"),
    # Sicilian
    ("Sicilian", "Sicilian Defense"),
    # Queen's Gambit family
    ("Queens Gambit", "Queen's Gambit"),
    ("Queen's Gambit", "Queen's Gambit"),
    ("QGD", "Queen's Gambit"),
    ("QGA", "Queen's Gambit"),
    # Slav
    ("Slav", "Slav Defense"),
    # Indian defenses
    ("Nimzo-Indian", "Nimzo-Indian"),
    ("Nimzo", "Nimzo-Indian"),
    ("Kings Indian", "King's Indian Defense"),
    ("King's Indian", "King's Indian Defense"),
    ("Queens Indian", "Queen's Indian Defense"),
    ("Queen's Indian", "Queen's Indian Defense"),
    ("Bogo-Indian", "Bogo-Indian"),
    ("Bogo", "Bogo-Indian"),
    ("Grunfeld", "Grünfeld Defense"),
    ("Gruenfeld", "Grünfeld Defense"),
    ("Grünfeld", "Grünfeld Defense"),
    ("Catalan", "Catalan Opening"),
    ("Benoni", "Benoni Defense"),
    # 1.e4 ... defenses
    ("Alekhine", "Alekhine Defense"),
    ("Pirc", "Pirc Defense"),
    ("Modern Defense", "Modern Defense"),
    ("Nimzowitsch Defense", "Nimzowitsch Defense"),
    ("Nimzowitsch", "Nimzowitsch Defense"),
    # Flank
    ("English", "English Opening"),
    ("Reti", "Réti Opening"),
    ("Réti", "Réti Opening"),
    ("Catalan", "Catalan Opening"),
    ("Bird", "Bird's Opening"),
    # Miscellaneous
    ("Dutch", "Dutch Defense"),
    ("Vienna", "Vienna Game"),
    ("Petroff", "Petroff Defense"),
    ("Petrov", "Petroff Defense"),
    ("Philidor", "Philidor Defense"),
    ("Bishops Opening", "Bishop's Opening"),
    ("Bishop's Opening", "Bishop's Opening"),
    ("Scotch", "Scotch Game"),
    ("Four Knights", "Four Knights"),
    ("Three Knights", "Three Knights"),
    ("Budapest", "Budapest Gambit"),
    ("Blackmar-Diemer", "Blackmar-Diemer Gambit"),
    ("Englund", "Englund Gambit"),
    ("Tennison", "Tennison Gambit"),
    ("Trompowsky", "Trompowsky Attack"),
    ("Van't Kruys", "Van't Kruys Opening"),
    ("Colle", "Colle System"),
    # Generic first-move classifications (fall-through)
    ("Queens Pawn", "Queen's Pawn Opening"),
    ("Queen's Pawn", "Queen's Pawn Opening"),
    ("Kings Pawn", "King's Pawn Opening"),
    ("King's Pawn", "King's Pawn Opening"),
]


def normalize_opening(name: Optional[str]) -> str:
    """Return the canonical opening family name for a free-text opening
    string. Returns "Other" when no keyword matches or input is empty.
    """
    if not name:
        return "Other"
    lower = name.lower()
    for keyword, canonical in _PRIORITY_MATCHES:
        if keyword.lower() in lower:
            return canonical
    return "Other"


# Canonical family name → opening_curriculum.json key. Only families with
# actual lesson content are mapped. Others return None and the caller falls
# back to the Openings overview or a training route.
_CURRICULUM_KEYS = {
    "Italian Game":           "italian_game",
    "London System":          "london_system",
    "Sicilian Defense":       "sicilian_defense",
    "Caro-Kann":              "caro_kann",
    "French Defense":         "french_defense",
    "Queen's Gambit":         "queens_gambit",
    "Scandinavian Defense":   "scandinavian_defense",
    "Ruy Lopez":              "ruy_lopez",
}


def curriculum_key_for_opening(canonical_name: str, user_color: str = "") -> Optional[str]:
    """
    Map a canonical opening family name to its curriculum key, if a lesson
    exists for it. Some openings (notably Italian Game) have a distinct
    black-side variant — we use the user_color to pick the right one.

    Returns None when no curriculum entry exists, so callers can fall back
    to a generic route.
    """
    base = _CURRICULUM_KEYS.get(canonical_name)
    if not base:
        return None
    # Italian Game has a separate `italian_game_black` curriculum entry.
    color = (user_color or "").lower()
    if base == "italian_game" and color == "black":
        return "italian_game_black"
    return base


# Inverse of _CURRICULUM_KEYS. Built at import time.
_KEY_TO_CANONICAL = {v: k for k, v in _CURRICULUM_KEYS.items()}


def canonical_name_for_curriculum_key(opening_key: Optional[str]) -> Optional[str]:
    """Given a curriculum key like "italian_game" or "italian_game_black",
    return the canonical family name ("Italian Game"). Returns None when
    no mapping exists.
    """
    if not opening_key:
        return None
    key = opening_key.strip().lower()
    # Strip color suffix — both variants map to the same canonical family.
    if key.endswith("_black"):
        key = key[: -len("_black")]
    elif key.endswith("_white"):
        key = key[: -len("_white")]
    return _KEY_TO_CANONICAL.get(key)


def color_for_curriculum_key(opening_key: Optional[str]) -> Optional[str]:
    """Return "black"/"white" when the curriculum key carries an explicit
    color suffix, else None (color not constrained by the key itself)."""
    if not opening_key:
        return None
    k = opening_key.strip().lower()
    if k.endswith("_black"):
        return "black"
    if k.endswith("_white"):
        return "white"
    return None

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

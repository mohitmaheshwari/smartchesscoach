"""caption_why_heuristics — the ONE definition of "does this caption have a why".

Extracted 2026-09-22 from backend/scripts/audit_captions_for_why.py so the
audit that MEASURES the why-rule and the review queue that FIXES it cannot
drift apart. Mohit, 2026-09-22: "each blunder or mistake each side should
explain the why ... each blunder should have the why."

Three heuristics; a caption passes if ANY fires:
  H1 concrete consequence -- names a square/piece beyond the SANs themselves
  H2 causal connector     -- because / since / loses to / walks into / hangs
  H3 principle ending     -- the closing sentence is a transferable rule

Failing all three is the "X is a mistake. Y was better." shape.

If the definition changes, change it HERE. Both consumers import from this
module and nothing re-implements it.
"""
from __future__ import annotations

import re

# Compiled once.
SQUARE_RE = re.compile(r"\b[a-h][1-8]\b")  # any algebraic square reference
PIECE_NAME_RE = re.compile(
    r"\b(king|queen|rook|bishop|knight|pawn|kings|queens|rooks|bishops|knights|pawns)\b",
    re.IGNORECASE,
)
CAUSAL_CONNECTOR_RE = re.compile(
    r"\b(because|since|so that|in order to|otherwise)\b|—|"
    r"\b(loses to|walks into|leaves \w+ hanging|hangs|hits|grabs|"
    r"falls|threatens|attacks|exposes|wins the|abandons|opens)\b",
    re.IGNORECASE,
)
# Principle endings: transferable rules. Looking at the closing sentence.
PRINCIPLE_VERB_RE = re.compile(
    r"\b(always|never|before .* (check|count|look)|"
    r"when .*?, (do|play|move|take|check)|"
    r"remember|this is why|count what|look for|"
    r"avoid moving|prefer .* over|the rule is|keep your)\b",
    re.IGNORECASE,
)


def has_concrete_consequence(caption: str, played_san: str, best_san: str | None) -> bool:
    """H1: caption names a square or piece beyond what's in the SAN itself.

    "Qe2 is a mistake. O-O was better." — has 'Qe2' and 'O-O' which are the SANs.
    No additional squares or pieces referenced. Fails H1.

    "Qe2 leaves d4 hanging — Qxd4 wins the pawn" — references d4 and 'pawn'
    beyond the SAN. Passes H1.
    """
    text = caption
    # Strip the SAN itself to avoid double-counting.
    for san in (played_san, best_san or ""):
        if san:
            text = text.replace(san, " ")
    squares_mentioned = set(SQUARE_RE.findall(text))
    pieces_mentioned = bool(PIECE_NAME_RE.search(text))
    # ≥1 extra square OR a piece-type word counts as concrete.
    return len(squares_mentioned) >= 1 or pieces_mentioned


def has_causal_connector(caption: str) -> bool:
    """H2: caption uses an explanation marker."""
    return bool(CAUSAL_CONNECTOR_RE.search(caption))


def has_principle_ending(caption: str) -> bool:
    """H3: closing sentence is a transferable rule.

    Two acceptance paths:
    1. Last sentence matches an explicit principle-verb pattern
       (always/never/before X check/when X do Y/look for/count what/prefer/etc.).
    2. Caption has ≥3 sentences AND the last sentence is ≥6 words AND
       doesn't START with a SAN-like token — this catches the bank-style
       trailing principles ("Between two reasonable moves, pick ...")
       that don't fit the rigid verb patterns but ARE transferable rules
       appended after the verdict.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", caption.strip()) if s.strip()]
    if not sentences:
        return False
    last = sentences[-1]
    if PRINCIPLE_VERB_RE.search(last):
        return True
    # Path 2: 3+ sentences and a substantial trailing one
    if len(sentences) >= 3:
        words = last.split()
        if len(words) >= 6:
            first_token = words[0].rstrip(",;:.")
            # SAN starts with a piece letter (KQRBN) or file letter (a-h) or O-O
            if not re.match(r"^(O-O(-O)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8])", first_token):
                return True
    return False


def has_why(caption: str, played_san: str = "", best_san: str | None = None) -> bool:
    """True when the caption explains itself by any of the three routes."""
    if not caption or not caption.strip():
        return False
    return (has_concrete_consequence(caption, played_san, best_san)
            or has_causal_connector(caption)
            or has_principle_ending(caption))

"""
Vacuous text detector — Category 5 of the Parth-bug taxonomy.

A non-trivial chunk of Parth's bugs are coaching strings that contain
NO specific information about the position. Examples:
  - "Nd4. Something just changed on the board." (fb_53710952f696)
  - "Nf3 — just getting my knight to a better spot." when Nf3 forks
    queen+bishop (fb_81ea58440719)
  - "Position is balanced: No immediate threats or imbalances."
  - "Don't let them have all the space. Push back!"

For mistakes/inaccuracies/blunders, vacuous text is worse than silence
— it gives the user the impression they were coached when they weren't.

Detection: score the text by counting concrete signals (specific squares
mentioned, piece-on-square claims, specific tactical pattern names,
specific moves named beyond just the played move). Below threshold for
the move's severity → vacuous.

Per the cross-cutting "coach not narrator" memo: silence > fluffy
template. When a string is vacuous and the move actually deserves
real coaching, the right move is to suppress it (return empty) so
downstream surfaces fall back to other available context.
"""
from __future__ import annotations

import re
from typing import Optional


# Specific tactical / strategic pattern names — when the text mentions
# any of these IN CONTEXT (not as filler), the message has real content.
_CONCRETE_PATTERN_WORDS = {
    "fork", "forks", "pin", "pinned", "skewer", "skewers",
    "discovered", "discovery", "double attack", "battery",
    "hanging", "undefended", "trapped", "overworked",
    "promotion", "passed pawn", "outpost",  # outpost is jargon-banned
                                              # in user-facing text but is
                                              # a real concept signal here
    "back rank", "smothered", "zwischenzug", "deflection",
    "decoy", "interference", "x-ray", "removing the defender",
    "fianchetto", "isolated", "doubled", "weakness",
}

# Generic-filler phrases that flag the text as likely vacuous regardless
# of other content. Catches the specific patterns Parth complained about.
_FILLER_PHRASES = (
    "something just changed",
    "look at your pieces",
    "look for ways to improve",
    "improve your worst piece",
    "no immediate threats or imbalances",
    "position is balanced",
    "small move",
    "just getting my",
    "to a better spot",
    "look for tactical opportunities",
    "look for strategic imbalances",
    "tactical opportunities and strategic imbalances",
    "every centipawn matters",
    "control the position",
    "improve your position",
    "evaluate the position and find",
    "don't let them have all the space",
    "push back",
)

# A SAN move pattern — used to count how many specific moves are named.
_SAN_RE = re.compile(
    r"\b(?:O-O-O|O-O|"
    r"[NBRQK][a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|"
    r"[a-h]x?[a-h][1-8](?:=[NBRQ])?[+#]?|"
    r"[a-h][1-8](?:=[NBRQ])?[+#]?)\b"
)

_SQUARE_RE = re.compile(r"\b[a-h][1-8]\b")


def count_concrete_signals(text: str) -> int:
    """Count the concrete-content signals in a coaching string. Higher
    is more specific.

    Signals:
      • Distinct squares mentioned (a1-h8)
      • Distinct moves named (SAN)
      • Tactical pattern words (fork, pin, hanging, etc.)
      • "your"/"their" references (mild signal)

    Filler phrases SUBTRACT from the score — they actively dilute the
    information density.
    """
    if not text:
        return 0

    lo = text.lower()
    squares = set(m.group(0).lower() for m in _SQUARE_RE.finditer(text))
    sans = set(m.group(0) for m in _SAN_RE.finditer(text))
    patterns = sum(1 for w in _CONCRETE_PATTERN_WORDS if re.search(rf"\b{re.escape(w)}\b", lo))
    filler_hits = sum(1 for ph in _FILLER_PHRASES if ph in lo)

    score = len(squares) + len(sans) + patterns
    score -= 2 * filler_hits  # filler is more than just "missing signal"
    return score


def is_text_vacuous(
    text: str,
    severity: Optional[str] = None,
) -> bool:
    """Return True if the text is vacuous given the move's severity.

    Threshold sliders by severity:
      • mistake / blunder / inaccuracy / opp_blunder / opp_mistake:
        require >= 2 concrete signals. Real teaching needs at least
        a square and a piece, or a tactical pattern name.
      • good / best / excellent / book: lenient — quiet acknowledgment
        ("d4 — book move") is fine. Only flag if score is deeply negative
        (filler-heavy with no signal).
      • context / unknown / None: lenient — only flag if score < -1.
    """
    if not text or not text.strip():
        return True

    score = count_concrete_signals(text)
    sev = (severity or "").lower()

    if sev in ("mistake", "blunder", "inaccuracy", "opp_blunder", "opp_mistake"):
        return score < 2
    if sev in ("good", "best", "excellent", "book"):
        return score < 0
    return score < -1

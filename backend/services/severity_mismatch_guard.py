"""
severity_mismatch_guard.py — catch captions that praise/neutral-frame a blunder.

Built 2026-06-06 (overnight, CAPTION_BACKLOG #18). Forensics found captions
that say something POSITIVE on a large-cp_loss move:
  - O-O-O cp_loss 698  -> "King is safe; rook joins the game."
  - Rxf4  cp_loss 8774 -> "Your queen is the only piece doing anything."
These are actively misleading — a 1200 reads "good" on a losing move.

This is a GUARD, not an explainer: it flags when a user move's caption fails
to reflect the engine's verdict. The renderer should then suppress the
positive framing and fall to an honest "{move} is a {severity}." (a
why-predicate can fill the reason). Low misfire because it only fires on
POSITIVE framing + a real blunder + NO severity acknowledgment.
"""
import re
from typing import Optional

# Clearly-positive framing that should never appear on a blunder.
_POSITIVE = re.compile(
    r"\b(king is safe|is safe|joins the game|fights for the center|"
    r"controls the (most|center)|develops|good move|natural|solid|"
    r"improves your|keep up|slightly better|best squares?|"
    r"powerful|strong|well placed|gains space|active piece|"
    r"only piece doing anything|nice)\b",
    re.I,
)
# Words that DO acknowledge the move was bad (if present, not a mismatch).
_SEVERITY = re.compile(
    r"\b(blunder|mistake|inaccuracy|loses|loses to|drops|hangs|hanging|"
    r"walks into|worse|weak|problem|trouble|gives up|leaves your|"
    r"undefended|no defender|in danger|loose)\b",
    re.I,
)


def is_severity_mismatch(caption: Optional[str], cp_loss: Optional[int],
                         is_user: bool = True) -> bool:
    """True when a user move's caption positively/neutrally frames a real
    blunder without acknowledging it was bad. Conservative: requires positive
    framing AND no severity word AND cp_loss >= 200."""
    if not is_user or not caption:
        return False
    if (cp_loss or 0) < 200:
        return False
    if _SEVERITY.search(caption):
        return False
    return bool(_POSITIVE.search(caption))

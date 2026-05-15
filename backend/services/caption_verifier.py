"""
Caption verifier — strips hallucinated move-suggestions from LLM output.

Purpose: the LLM caption generator's prompt has explicit rules (Rule E,
Checklist 7 & 8) telling the model to only name moves from
facts.move_played or facts.best_move. gpt-4o-mini does NOT reliably
follow these. This module catches the leak in Python after the LLM
returns.

Bug class this addresses (Parth flagged 2026-05-15):
    "c5 — claims the center, but better was d5 to challenge the pawn
     directly."
        - move_played = c5
        - best_move   = Bf5
        - d5 is neither AND illegal (own pawn already on d5)
        - → strip the "but better was d5..." clause

Strategy: find alternative-suggestion clauses ("better was X",
"X was stronger", etc.). When the suggested SAN doesn't match
move_played or best_move, strip the entire clause.

Per the locked rule renderer_never_computes_chess_meaning: this is a
VERIFIER, not a renderer. New module, distinct from caption_renderer.py.
The rule's intent is to keep chess analysis out of the caption-PRODUCING
pipeline; verification of LLM output against facts is a separate
quality-control layer.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


# Phrases the LLM uses when suggesting an alternative move. When the
# alternative's SAN doesn't match the engine's best_move, the WHOLE
# clause needs stripping. Each pattern captures the SAN in group "san".
_ALT_SUGGESTION_PATTERNS = [
    # ", but better was X ..."  /  "— better was X ..."  /  "; stronger was X"
    re.compile(
        r"\s*[,;—–\-]\s*(?:but\s+|though\s+|however\s+)?"
        r"(?:better|stronger|sharper|safer|harder|sound)\s+(?:would\s+be|was|is)\s+"
        r"(?P<san>[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)"
        r"[^,.;]*",
        re.IGNORECASE,
    ),
    # ", X was better ..."  /  ", X is stronger ..."  /  ", X would be sharper"
    re.compile(
        r"\s*[,;—–\-]\s*(?:but\s+|though\s+|however\s+)?"
        r"(?P<san>[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)"
        r"\s+(?:was|is|would\s+be|would\s+have\s+been)\s+"
        r"(?:better|stronger|sharper|safer|harder)"
        r"[^,.;]*",
        re.IGNORECASE,
    ),
    # ", but X keeps the pressure ..."  / "; but X wins ..."  (action verb after alt-SAN)
    re.compile(
        r"\s*[,;—–\-]\s*(?:but|though|however)\s+"
        r"(?P<san>[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)"
        r"\s+(?:keeps?|kept|wins?|won|delivers?|gives?|sets?\s+up|creates?|threatens?)\s+"
        r"[^,.;]*",
        re.IGNORECASE,
    ),
]


def _normalize_san(san: str) -> str:
    """Drop trailing +/# markers so SAN comparison is tolerant."""
    return (san or "").rstrip("+#")


def verify_caption(caption: str, facts: Dict[str, Any]) -> str:
    """Strip alt-suggestion clauses whose suggested SAN isn't the
    engine's best_move (or move_played, for sanity).

    Args:
        caption: raw LLM output string
        facts: facts dict from build_move_facts (uses move_played, best_move)

    Returns:
        Cleaned caption. Same string if nothing to strip.
    """
    if not caption or not caption.strip():
        return caption or ""

    move_played = _normalize_san(facts.get("move_played") or "")
    best_move = _normalize_san(facts.get("best_move") or "")
    allowed = {s for s in (move_played, best_move) if s}

    # Collect spans to strip across all patterns.
    spans: List[Tuple[int, int, str]] = []  # (start, end, san_found)
    for pat in _ALT_SUGGESTION_PATTERNS:
        for m in pat.finditer(caption):
            san = _normalize_san(m.group("san"))
            if san in allowed:
                continue  # legitimate reference, leave it
            spans.append((m.start(), m.end(), san))

    if not spans:
        return caption

    # Merge overlapping spans.
    spans.sort(key=lambda x: x[0])
    merged: List[Tuple[int, int]] = []
    for start, end, _san in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Strip in reverse so earlier indices stay valid.
    result = caption
    for start, end in reversed(merged):
        result = result[:start] + result[end:]

    # Tidy up dangling whitespace / punctuation left by strips.
    result = re.sub(r"\s+([,.;:!?])", r"\1", result)
    result = re.sub(r"\s{2,}", " ", result).strip()
    result = re.sub(r"[—–\-,;]+\s*$", "", result).strip()
    if result and result[-1] not in ".!?":
        result += "."

    if result != caption:
        logger.info(
            f"[caption-verifier] stripped alt-suggestion(s) "
            f"{[s[2] for s in spans]}: '{caption}' → '{result}'"
        )
    return result

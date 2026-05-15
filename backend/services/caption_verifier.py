"""
Caption verifier — strips hallucinated entities from LLM caption output.

Refactor 2026-05-15: works against the resolver's `decision` contract
instead of raw move facts. Catches FOUR classes of LLM leak:

  1. Alt-suggestion clauses where the SAN isn't on the whitelist
  2. Opening names mentioned when focus != "opening"
     (or named opening doesn't match anchor)
  3. Shape pattern names mentioned when focus != "shape"
     (or named pattern doesn't match anchor)
  4. Advice-tail phrases at the end of the sentence

Per the locked rule renderer_never_computes_chess_meaning: this is a
VERIFIER, not a renderer. It validates LLM-generated text against the
deterministic decision contract — no chess imports needed.

INPUT
─────
    caption  : raw LLM string
    decision : output of caption_priority_resolver.resolve_priority(move)
               (allowed_moves, anchor_name, focus all used here)

OUTPUT
──────
    str — cleaned caption (same string if no strips needed)
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────
# Pattern catalogues
# ───────────────────────────────────────────────────────────────────

# All opening family names that might appear in LLM output. Kept short
# — we strip ANY of these unless they match decision.anchor_name.
_OPENING_NAMES = [
    "Italian Game", "Caro-Kann Defense", "Caro Kann Defense",
    "Sicilian Defense", "French Defense", "Scandinavian Defense",
    "Queen's Gambit", "Queens Gambit", "Slav Defense", "London System",
    "Ruy Lopez", "King's Indian Defense", "Kings Indian Defense",
    "Nimzo-Indian Defense", "Nimzo Indian Defense", "English Opening",
    "Scotch Game", "Petrov Defense", "Vienna Game", "Pirc Defense",
    "Modern Defense", "King's Gambit", "Kings Gambit",
    "Philidor Defense", "Budapest Gambit", "Dutch Defense",
    "Bird Opening", "Reti Opening", "Catalan Opening",
    "Grunfeld Defense", "Benoni Defense", "Trompowsky Attack",
    "Bogo-Indian", "Queens Indian", "Queen's Indian",
]

# Shape pattern names from data/shape_patterns.py (just the strings,
# duplicated here so we don't need a runtime import dance).
_SHAPE_NAMES = [
    "Knight Fork", "Bishop Fork", "Rook Fork", "Hidden Attack", "Pin",
    "Skewer", "Double Attack Line", "Back-Rank Trap", "Back Rank Trap",
    "h7 Attack", "Queen-Knight Mate", "Queen Knight Mate",
    "Strong Knight Square", "Weak Squares", "Free Pawn",
    "Open Long Line", "No Safe Square", "Tired Defender",
    "Free Piece", "Long Diagonal Bishop", "Remove the Guard",
    "Force the King", "In-Between Move", "Knight Mate",
    "Pawn Hole at g6", "Passed Pawn",
]


# Alt-suggestion clauses (carried over from prior version).
_ALT_SUGGESTION_PATTERNS = [
    re.compile(
        r"\s*[,;—–\-]\s*(?:but\s+|though\s+|however\s+)?"
        r"(?:better|stronger|sharper|safer|harder|sound)\s+(?:would\s+be|was|is)\s+"
        r"(?P<san>[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)"
        r"[^,.;]*",
        re.IGNORECASE,
    ),
    re.compile(
        r"\s*[,;—–\-]\s*(?:but\s+|though\s+|however\s+)?"
        r"(?P<san>[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)"
        r"\s+(?:was|is|would\s+be|would\s+have\s+been)\s+"
        r"(?:better|stronger|sharper|safer|harder)"
        r"[^,.;]*",
        re.IGNORECASE,
    ),
    re.compile(
        r"\s*[,;—–\-]\s*(?:but|though|however)\s+"
        r"(?P<san>[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)"
        r"\s+(?:keeps?|kept|wins?|won|delivers?|gives?|sets?\s+up|creates?|threatens?)\s+"
        r"[^,.;]*",
        re.IGNORECASE,
    ),
]


# Advice-tail patterns — strip the trailing clause if it ends with one
# of these instructive phrases.
_ADVICE_TAIL_PATTERNS = [
    re.compile(
        r"\s*[,;—–\-]\s*"
        r"(?:focus on|try to|consider|watch for|be careful|remember to|"
        r"keep the pressure|scan every|attack it again|reroute|just take|"
        r"look for|be ready|should\s+\w+|don't forget)"
        r"\s+[^.!?]*",
        re.IGNORECASE,
    ),
]


# ───────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────


def _normalize_san(san: str) -> str:
    return (san or "").rstrip("+#")


def _strip_spans(text: str, spans: List[Tuple[int, int]]) -> str:
    """Apply a list of (start, end) cuts to text, returning the cleaned
    string. Spans are merged and applied in reverse.
    """
    if not spans:
        return text
    spans.sort(key=lambda x: x[0])
    merged: List[Tuple[int, int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    out = text
    for s, e in reversed(merged):
        out = out[:s] + out[e:]
    return out


def _tidy(text: str) -> str:
    """Collapse extra whitespace and trailing punctuation residue."""
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"[—–\-,;]+\s*$", "", text).strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text


# ───────────────────────────────────────────────────────────────────
# Per-class verifiers
# ───────────────────────────────────────────────────────────────────


def _strip_alt_suggestions(caption: str, allowed_sans: set) -> Tuple[str, List[str]]:
    """Strip "better was X" clauses where X isn't allowed.
    Returns (new_caption, list_of_stripped_sans)."""
    stripped: List[str] = []
    spans: List[Tuple[int, int]] = []
    for pat in _ALT_SUGGESTION_PATTERNS:
        for m in pat.finditer(caption):
            san = _normalize_san(m.group("san"))
            if san in allowed_sans:
                continue
            spans.append((m.start(), m.end()))
            stripped.append(san)
    return _strip_spans(caption, spans), stripped


def _strip_disallowed_openings(caption: str, allowed_name: str) -> Tuple[str, List[str]]:
    """Strip any opening name that doesn't match allowed_name.
    Comparison is whitespace-tolerant ('Caro-Kann' vs 'Caro Kann')."""
    allowed_norm = re.sub(r"[\s\-]+", " ", (allowed_name or "")).lower().strip()
    spans: List[Tuple[int, int]] = []
    stripped: List[str] = []
    for opening in _OPENING_NAMES:
        opening_norm = re.sub(r"[\s\-]+", " ", opening).lower()
        if opening_norm == allowed_norm:
            continue
        # Match the opening name AND a small surrounding context to remove
        # awkward dangling text like " — Caro-Kann Defense."
        pat = re.compile(
            r"\s*[,;—–\-]?\s*\b" + re.escape(opening) + r"\b[^,.;]*",
            re.IGNORECASE,
        )
        for m in pat.finditer(caption):
            spans.append((m.start(), m.end()))
            stripped.append(opening)
    return _strip_spans(caption, spans), stripped


def _strip_disallowed_shapes(caption: str, allowed_name: str) -> Tuple[str, List[str]]:
    """Strip any shape pattern name that doesn't match allowed_name."""
    allowed_norm = re.sub(r"[\s\-]+", " ", (allowed_name or "")).lower().strip()
    spans: List[Tuple[int, int]] = []
    stripped: List[str] = []
    for shape in _SHAPE_NAMES:
        shape_norm = re.sub(r"[\s\-]+", " ", shape).lower()
        if shape_norm == allowed_norm:
            continue
        pat = re.compile(
            r"\s*[,;—–\-]?\s*\b" + re.escape(shape) + r"\b[^,.;]*",
            re.IGNORECASE,
        )
        for m in pat.finditer(caption):
            spans.append((m.start(), m.end()))
            stripped.append(shape)
    return _strip_spans(caption, spans), stripped


def _strip_advice_tails(caption: str) -> Tuple[str, List[str]]:
    """Strip imperative-advice clauses at the end of the sentence."""
    spans: List[Tuple[int, int]] = []
    stripped: List[str] = []
    for pat in _ADVICE_TAIL_PATTERNS:
        for m in pat.finditer(caption):
            spans.append((m.start(), m.end()))
            stripped.append(m.group(0).strip())
    return _strip_spans(caption, spans), stripped


# ───────────────────────────────────────────────────────────────────
# Public entry point
# ───────────────────────────────────────────────────────────────────


def verify_caption(caption: str, decision: Dict[str, Any]) -> str:
    """Strip hallucinated alt-suggestions, opening names, shape names,
    and advice tails from the LLM caption.

    `decision` is the resolver output. We use:
      - allowed_moves   → which SANs may be named
      - anchor_name     → the SINGLE legitimate entity name
      - focus           → drives which strip-class runs

    Returns the cleaned caption. Same string if nothing stripped.
    """
    if not caption or not caption.strip():
        return caption or ""
    if not isinstance(decision, dict):
        return caption

    allowed_moves = decision.get("allowed_moves") or []
    allowed_sans = {_normalize_san(s) for s in allowed_moves if s}

    anchor = decision.get("anchor_name") or ""
    focus = decision.get("focus", "")

    original = caption
    stripped_log: List[str] = []

    # 1. Alt-suggestions outside whitelist
    caption, stripped = _strip_alt_suggestions(caption, allowed_sans)
    if stripped:
        stripped_log.append(f"alt-sans={stripped}")

    # 2. Opening names — when focus is NOT opening, strip ALL opening names.
    #    When focus IS opening, strip everything except the anchor.
    allowed_opening = anchor if focus == "opening" else ""
    caption, stripped = _strip_disallowed_openings(caption, allowed_opening)
    if stripped:
        stripped_log.append(f"openings={stripped}")

    # 3. Shape pattern names — same: allow only when focus == shape AND matches anchor.
    allowed_shape = anchor if focus == "shape" else ""
    caption, stripped = _strip_disallowed_shapes(caption, allowed_shape)
    if stripped:
        stripped_log.append(f"shapes={stripped}")

    # 4. Advice-tail clauses
    caption, stripped = _strip_advice_tails(caption)
    if stripped:
        stripped_log.append(f"advice={stripped}")

    caption = _tidy(caption)

    if caption != original:
        logger.info(f"[caption-verifier] '{original}' → '{caption}'  stripped={stripped_log}")
    return caption

"""
Caption verifier — semantic repair layer for LLM caption output.

Evolution 2026-05-15 (bounded improvisation): the verifier is no
longer a destructive strip-everything-suspicious filter. It REPAIRS:

  • Alt-suggestion clauses ("better was X" where X isn't allowed) →
    still STRIPPED (these are pure hallucinations, no safe repair)
  • Opening name not allowed by decision focus → name REPLACED by the
    move's generic role phrase ("Italian Game" → "claims the centre")
  • Shape pattern name not allowed → name REPLACED with a neutral
    "tactical idea" phrasing (preserves the clause's information)
  • Advice-tail phrases ("consider X", "watch for Y") → still STRIPPED

The goal is to keep the LLM's voice and rhythm intact while removing
fabricated entities. Compare:

  OLD (destructive):   "c5 — Italian Game. Bishop on c4 eyes f7." → "c5."
  NEW (repair):        "c5 — Italian Game. Bishop on c4 eyes f7." →
                       "c5 claims the centre. Bishop on c4 eyes f7."

Per the locked rule renderer_never_computes_chess_meaning: this remains
a VERIFIER, not a renderer. All chess-meaning lookups (role phrase,
allowed entity names) come PRE-COMPUTED on the decision dict from the
resolver. No FENs parsed here.

INPUT
─────
    caption  : raw LLM string
    decision : output of caption_priority_resolver.resolve_priority(move)
               Uses: allowed_moves, anchor_name, secondary_anchor,
               focus, move_played, move_role_phrase.

OUTPUT
──────
    str — repaired caption (same string if no repairs needed)
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

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
    "Knight Fork", "Bishop Fork", "Rook Fork", "Pawn Fork",
    "Hidden Attack", "Pin",
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


# Canonical hyphenated forms of opening names the LLM tends to
# de-hyphenate. Word-boundary match so "Caro Kann" → "Caro-Kann"
# without affecting "Carolan" or unrelated tokens.
_OPENING_HYPHEN_CANONICAL = [
    ("Caro Kann",       "Caro-Kann"),
    ("Nimzo Indian",    "Nimzo-Indian"),
    ("Queen's Indian",  "Queen's Indian"),  # already canonical, here for symmetry
    ("Bogo Indian",     "Bogo-Indian"),
    ("Ruy Lopez",       "Ruy Lopez"),       # no hyphen by convention
    ("Kings Gambit",    "King's Gambit"),
    ("Kings Indian",    "King's Indian"),
    ("Queens Gambit",   "Queen's Gambit"),
]


def _canonicalize_openings(text: str) -> str:
    """Restore canonical hyphenation/apostrophes on opening names the
    LLM commonly rewrites. Word-boundaried so we don't damage other
    text.
    """
    out = text
    for raw, canon in _OPENING_HYPHEN_CANONICAL:
        if raw == canon:
            continue
        pat = re.compile(r"\b" + re.escape(raw) + r"\b")
        out = pat.sub(canon, out)
    return out


def _tidy(text: str) -> str:
    """Collapse extra whitespace and trailing punctuation residue."""
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"[—–\-,;]+\s*$", "", text).strip()
    text = re.sub(r"([.!?])\1+", r"\1", text)         # dedupe "..!?" → ".!?"
    text = re.sub(r"\.\s*\.", ".", text)               # ". ." → "."
    text = re.sub(r"\s{2,}", " ", text).strip()
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


def _repair_disallowed_openings(
    caption: str,
    allowed_names: List[str],
    repair_phrase: Optional[str],
) -> Tuple[str, List[str]]:
    """REPAIR (don't strip) opening names that aren't on the allowed list.

    Strategy:
      • Replace the bare name with `repair_phrase` if we have one
        (e.g. "Italian Game" → "claims the centre").
      • If no repair phrase, drop only the bare name token plus a
        trailing dangling " — " or "," — preserving any meaningful
        clause that may follow.
    """
    allowed_norms = {
        re.sub(r"[\s\-]+", " ", (n or "")).lower().strip()
        for n in (allowed_names or []) if n
    }
    edits: List[Tuple[int, int, str]] = []
    repaired_names: List[str] = []

    for opening in _OPENING_NAMES:
        opening_norm = re.sub(r"[\s\-]+", " ", opening).lower()
        if opening_norm in allowed_norms:
            continue
        # Match "[em-dash or comma] OpeningName" — narrower than the
        # old "name + everything up to next punctuation" so we leave
        # adjacent teaching clauses alive.
        pat = re.compile(
            r"(?P<lead>\s*[,;—–\-]?\s*)\b" + re.escape(opening) + r"\b",
            re.IGNORECASE,
        )
        for m in pat.finditer(caption):
            if repair_phrase:
                # "— Italian Game" → " claims the centre"  (preserve leading space, drop the dash)
                replacement = " " + repair_phrase
            else:
                replacement = ""
            edits.append((m.start(), m.end(), replacement))
            repaired_names.append(opening)

    return _apply_edits(caption, edits), repaired_names


def _repair_disallowed_shapes(
    caption: str,
    allowed_names: List[str],
) -> Tuple[str, List[str]]:
    """REPAIR shape pattern names that aren't on the allowed list.

    Most shape-name hallucinations come with a teaching clause attached
    ("Free Piece. Their rook had no defender."). Stripping the whole
    clause murders the teaching. Instead we replace only the name,
    leaving the explanatory clause intact.
    """
    allowed_norms = {
        re.sub(r"[\s\-]+", " ", (n or "")).lower().strip()
        for n in (allowed_names or []) if n
    }
    edits: List[Tuple[int, int, str]] = []
    repaired_names: List[str] = []

    for shape in _SHAPE_NAMES:
        shape_norm = re.sub(r"[\s\-]+", " ", shape).lower()
        if shape_norm in allowed_norms:
            continue
        # Two-pass: first try to consume the name PLUS surrounding
        # boilerplate ("A Knight Fork was also possible") so we don't
        # leave dangling articles. Fall back to dropping just the name.
        pat_with_boilerplate = re.compile(
            r"(?P<lead>\s*[,;—–\-]?\s*)"
            r"(?P<article>\b(?:a|an|the)\s+)?"
            r"\b" + re.escape(shape) + r"\b"
            r"(?P<tail>\s+(?:was|is|would\s+(?:be|have\s+(?:been|worked))|will\s+be)"
            r"\s+(?:also\s+)?"
            r"(?:possible|here|available|on|too|good|sharper|better))?",
            re.IGNORECASE,
        )
        for m in pat_with_boilerplate.finditer(caption):
            edits.append((m.start(), m.end(), ""))
            repaired_names.append(shape)

    return _apply_edits(caption, edits), repaired_names


def _apply_edits(text: str, edits: List[Tuple[int, int, str]]) -> str:
    """Apply (start, end, replacement) edits to text, with overlap
    handling. Later edits inside an earlier edit's range are dropped.
    """
    if not edits:
        return text
    edits.sort(key=lambda x: x[0])
    merged: List[Tuple[int, int, str]] = []
    for s, e, rep in edits:
        if merged and s < merged[-1][1]:
            continue  # overlapping/inside a previous edit — skip
        merged.append((s, e, rep))
    out = text
    for s, e, rep in reversed(merged):
        out = out[:s] + rep + out[e:]
    return out


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
    """Repair hallucinated entities and strip illegal alt-suggestions /
    advice tails from the LLM caption.

    `decision` is the resolver output. We use:
      - allowed_moves     → SANs that may appear
      - anchor_name       → primary legitimate entity
      - secondary_anchor  → optional second legitimate entity
      - focus             → drives which entity-class is allowed
      - move_role_phrase  → generic fallback used when repairing
                            an opening name ("claims the centre")

    Returns the repaired caption. Same string if no edits needed.
    """
    if not caption or not caption.strip():
        return caption or ""
    if not isinstance(decision, dict):
        return caption

    allowed_moves = decision.get("allowed_moves") or []
    allowed_sans = {_normalize_san(s) for s in allowed_moves if s}

    primary_anchor = decision.get("anchor_name") or ""
    secondary_anchor = decision.get("secondary_anchor") or ""
    focus = decision.get("focus", "")
    secondary_focus = decision.get("secondary_focus") or ""
    role_phrase = decision.get("move_role_phrase")

    # Which opening / shape names the caption is allowed to contain.
    allowed_openings: List[str] = []
    if focus == "opening" and primary_anchor:
        allowed_openings.append(primary_anchor)
    if secondary_focus == "opening" and secondary_anchor:
        allowed_openings.append(secondary_anchor)

    allowed_shapes: List[str] = []
    if focus == "shape" and primary_anchor:
        allowed_shapes.append(primary_anchor)
    if secondary_focus == "shape" and secondary_anchor:
        allowed_shapes.append(secondary_anchor)

    original = caption
    log: List[str] = []

    # 1. Alt-suggestions outside whitelist → STRIP (no safe repair)
    caption, stripped = _strip_alt_suggestions(caption, allowed_sans)
    if stripped:
        log.append(f"alt-sans={stripped}")

    # 2. Opening names → REPAIR (replace with role phrase)
    caption, repaired = _repair_disallowed_openings(caption, allowed_openings, role_phrase)
    if repaired:
        log.append(f"openings_repaired={repaired}")

    # 3. Shape pattern names → REPAIR (drop just the name)
    caption, repaired = _repair_disallowed_shapes(caption, allowed_shapes)
    if repaired:
        log.append(f"shapes_repaired={repaired}")

    # 4. Advice-tail clauses → STRIP (no safe repair)
    caption, stripped = _strip_advice_tails(caption)
    if stripped:
        log.append(f"advice={stripped}")

    # 5. Canonicalize opening names the LLM de-hyphenated.
    canonicalized = _canonicalize_openings(caption)
    if canonicalized != caption:
        log.append("opening_canonicalized")
        caption = canonicalized

    caption = _tidy(caption)

    if caption != original:
        logger.info(f"[caption-verifier] '{original}' → '{caption}'  edits={log}")
    return caption

"""
Hard validators for Truth lines and Decryption text.

Per project_decryption_voice.md, prompt discipline is not enough — voice
drifts back toward engine-speak unless verified in code on every output.
If validation fails, the caller must regenerate (Decryption) or fall
back to a guaranteed-safe variant (Truth line).
"""

import re
from typing import Tuple


# ── Word budgets (locked) ─────────────────────────────────────────────

TRUTH_LINE_MAX_WORDS = 12      # per-line cap for the 3 Truth lines
DECRYPTION_MAX_WORDS = 80      # total cap for one Decryption block
DECRYPTION_MAX_SENTENCES = 4   # sentence cap for one Decryption block


# ── Vocabulary bans ───────────────────────────────────────────────────
# Words that leak engine-think into the player surface. Hard reject.

ENGINE_WORDS = [
    "centipawn", "centipawns", " cp ", "cp loss", "evaluation", "eval ",
    "stockfish", "engine ",
    "best move was", "best move is",
    "blunder ", "mistake severity",
    "accuracy ", " cp,",
    "tactically", "positionally", "strategically",
    "compensation",
]

# Empty descriptors that explain nothing — the anti-patterns from the
# voice doc.
EMPTY_DESCRIPTORS = [
    "created pressure",
    "got into a bad position",
    "had attacking initiative",
    "improves their position",
    "you should have",
    "fortunately,", "unfortunately,", "sadly,",
]

# Abstraction words that hide instead of explain. Whole-word bans —
# Decryption must describe what was on the board, not name it with a
# vague label. From voice review 2026-05-04.
ABSTRACTION_WORDS = [
    "pressure",
    "initiative",
    "advantage",
    "compensation",
    "strong move",
    "good move",
    "weak move",
    "bad move",
    "dynamic",
    "harmonious",
    "harmonized",
    "harmony",
    "active play",
    "passive play",
]


# ── Helpers ───────────────────────────────────────────────────────────

def _word_count(s: str) -> int:
    return len(s.split())


def _sentence_count(s: str) -> int:
    return len([x for x in re.split(r"[.!?]+", s) if x.strip()])


# ── Truth-line validators ─────────────────────────────────────────────

def validate_truth_line(line: str) -> Tuple[bool, str]:
    """Validate one Truth line. Returns (ok, reason)."""
    if not line or not line.strip():
        return False, "empty line"
    wc = _word_count(line)
    if wc > TRUTH_LINE_MAX_WORDS:
        return False, f"exceeds word budget ({wc} > {TRUTH_LINE_MAX_WORDS})"
    lower = " " + line.lower() + " "  # pad so " cp " etc. match cleanly
    for word in ENGINE_WORDS:
        if word in lower:
            return False, f"contains engine word: '{word.strip()}'"
    for descriptor in EMPTY_DESCRIPTORS:
        if descriptor in lower:
            return False, f"contains empty descriptor: '{descriptor.strip()}'"
    return True, ""


def validate_truth_block(identity: str, anchor: str, trigger: str) -> Tuple[bool, str]:
    """All three Truth lines must pass.

    The anchor has an extra concreteness requirement on top of the
    word-budget + ban-list checks. See validate_anchor_concreteness.
    """
    for label, line in (("identity", identity), ("anchor", anchor), ("trigger", trigger)):
        ok, reason = validate_truth_line(line)
        if not ok:
            return False, f"{label}: {reason}"
    ok, reason = validate_anchor_concreteness(anchor)
    if not ok:
        return False, f"anchor: {reason}"
    return True, ""


# ── Anchor concreteness ──────────────────────────────────────────────
# Per voice review 2026-05-04: anchors slip into "language shortcuts"
# (e.g., "their plan was already moving") that name nothing on the
# board. Hard rule: every anchor must reference a piece, a square/file,
# or a concrete chess action.

# Concrete chess action verbs — present-, past-, and -ing forms. Treated
# as a single set for fast membership tests. Matches whole-word only.
_CONCRETE_ACTION_TOKENS = {
    # capture / exchange
    "traded", "trade", "trades", "trading",
    "captured", "captures", "capturing", "took", "takes", "taking",
    "exchanged", "exchanges", "exchanging",
    # movement / push
    "pushed", "push", "pushes", "pushing",
    "moved", "moves", "moving",
    "played", "plays", "playing",
    "walked", "walks", "walking",
    "stepped", "steps", "stepping",
    "left", "leave", "leaves", "leaving",
    # tactical
    "forked", "forks", "forking",
    "pinned", "pins", "pinning",
    "attacked", "attacks", "attacking",
    "threatened", "threatens", "threatening",
    "hung", "hangs", "hanging",
    "sacrificed", "sacrifices", "sacrificing",
    "missed", "misses", "missing",
    # defensive
    "defended", "defends", "defending",
    "blocked", "blocks", "blocking",
    "covered", "covers", "covering",
    "guarded", "guards", "guarding",
    # strategic
    "simplified", "simplifies", "simplifying",
    "developed", "develops", "developing",
    "castled", "castles", "castling",
    "opened", "opens",          # not "opening" — too generic (the phase)
    "answered", "answers", "answering",
    "allowed", "allows", "allowing",
    # decisive
    "checked", "checks",
    "mate", "mated", "mates", "mating",
    "ended", "ends", "ending",
    "gave", "gives", "giving",
    "handed", "hands", "handing",
    # plain chess-action verbs the player uses naturally
    "blundered", "blunders", "blundering",
    "slipped", "slips", "slipping",
    "missed", "misses",  # already above; safe to repeat (set dedups)
}

_BOARD_REGION_TOKENS = {
    "kingside", "king-side", "king side",
    "queenside", "queen-side", "queen side",
    "back rank", "back-rank", "backrank",
    "center", "centre",
    "diagonal", "file", "rank",
}


def validate_anchor_concreteness(anchor: str) -> Tuple[bool, str]:
    """Anchor must reference at least ONE of:
       - a chess piece (king/queen/rook/bishop/knight/pawn)
       - a square (a1–h8)
       - a file/region (h-file, back rank, kingside, etc.)
       - a concrete chess action verb (traded, pushed, walked into, ...)
       - a move SAN (single-letter piece + file/rank, e.g., Rd8+, Qxe1)
    """
    if not anchor:
        return False, "empty anchor"
    text = anchor
    lower = anchor.lower()

    if _PIECE_PATTERN.search(text):
        return True, ""
    if _SQUARE_PATTERN.search(text):
        return True, ""
    if _FILE_PATTERN.search(text):
        return True, ""
    for region in _BOARD_REGION_TOKENS:
        if region in lower:
            return True, ""

    # SAN tokens — leading uppercase piece letter + file/rank, optional
    # capture x, optional + or # for check/mate. Catches Rd8+, Qxe1#,
    # Nf3, etc. (Pawn SANs like "e4" are caught by _SQUARE_PATTERN.)
    if re.search(r"\b[KQRBN][a-h]?[1-8]?x?[a-h][1-8][+#]?\b", text):
        return True, ""

    # Concrete action verb check (token-level, case-insensitive).
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", lower)
    for t in tokens:
        if t in _CONCRETE_ACTION_TOKENS:
            return True, ""

    return False, "no piece/square/file/action verb (concreteness check failed)"


# ── Decryption validator ──────────────────────────────────────────────

# Causality markers — at least one must appear so the decryption answers
# "why couldn't the player stop it?". This is the rule-4 enforcement.
_CAUSALITY_PATTERNS = [
    r"\bbecause\b",
    r"\bcouldn'?t\b",
    r"\bno (piece|defender|response|way)\b",
    r"\bnothing (left|to)\b",
    r"\bso\b",
    r"\bthat'?s why\b",
    r"\bwith no\b",
    r"\bunable to\b",
]

_PIECE_PATTERN = re.compile(r"\b(king|queen|rook|bishop|knight|pawn|piece)s?\b", re.IGNORECASE)
_SQUARE_PATTERN = re.compile(r"\b[a-h][1-8]\b")
_FILE_PATTERN = re.compile(r"\b[a-h]-?file\b", re.IGNORECASE)
_PLAYER_REF_PATTERN = re.compile(r"\byou\b|\byour\b", re.IGNORECASE)
_CAUSALITY_RE = re.compile("|".join(_CAUSALITY_PATTERNS), re.IGNORECASE)


def _normalize(text: str) -> str:
    """Normalize curly quotes / dashes so regexes work consistently.
    The LLM emits smart quotes; we want one canonical form."""
    return (
        text
        .replace("’", "'")  # right single quotation mark
        .replace("‘", "'")  # left single quotation mark
        .replace("“", '"').replace("”", '"')  # curly double quotes
        .replace("—", "—").replace("–", "—")
    )


# Sentence 1 in a Decryption block must NOT narrate the user's move
# (banned by Decryption Voice rule 8: "Do NOT explain the move").
# Common LLM slips: "Your rook moved from X to Y", "You played Rd8",
# "You moved your rook to d8". Catch all three shapes.
_MOVE_NARRATION_PATTERNS = [
    re.compile(r"^\s*your\s+(king|queen|rook|bishop|knight|pawn|piece)\s+(moved|went|stepped|walked|landed)\b", re.IGNORECASE),
    re.compile(r"^\s*you\s+(played|moved|pushed|captured|took|dropped)\b", re.IGNORECASE),
    re.compile(r"^\s*you\s+sent\s+your\s+(king|queen|rook|bishop|knight|pawn|piece)\b", re.IGNORECASE),
]


def _first_sentence(text: str) -> str:
    parts = re.split(r"[.!?]+", text, maxsplit=1)
    return parts[0].strip() if parts else text


def validate_decryption(text: str) -> Tuple[bool, str]:
    """Validate one Decryption block. Returns (ok, reason).

    Enforces every rule from project_decryption_voice.md that can be
    checked mechanically:
      - word + sentence budget
      - no engine-words / empty-descriptor / abstraction-word leakage
      - geometry: at least one piece/square/file mentioned
      - felt-experience: at least one "you/your" reference
      - why-it-worked: at least one causality marker
    """
    if not text or not text.strip():
        return False, "empty text"

    text = _normalize(text)

    wc = _word_count(text)
    if wc > DECRYPTION_MAX_WORDS:
        return False, f"exceeds word budget ({wc} > {DECRYPTION_MAX_WORDS})"

    sc = _sentence_count(text)
    if sc > DECRYPTION_MAX_SENTENCES:
        return False, f"exceeds sentence cap ({sc} > {DECRYPTION_MAX_SENTENCES})"

    lower = " " + text.lower() + " "
    for word in ENGINE_WORDS:
        if word in lower:
            return False, f"contains engine word: '{word.strip()}'"
    for descriptor in EMPTY_DESCRIPTORS:
        if descriptor in lower:
            return False, f"contains empty descriptor: '{descriptor.strip()}'"
    # Abstraction words via word-boundary regex (catches "initiative." too).
    for word in ABSTRACTION_WORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", lower):
            return False, f"contains abstraction word: '{word}'"

    if not (_PIECE_PATTERN.search(text) or _SQUARE_PATTERN.search(text) or _FILE_PATTERN.search(text)):
        return False, "no piece/square/file mentioned (geometry check failed)"

    if not _PLAYER_REF_PATTERN.search(text):
        return False, "no 'you/your' reference (felt-experience check failed)"

    if not _CAUSALITY_RE.search(text):
        return False, "no causality marker (why-it-worked check failed)"

    # Sentence 1 must not be pure move narration — Decryption explains
    # what the position was already doing, not what the user's piece did.
    s1 = _first_sentence(text)
    for pat in _MOVE_NARRATION_PATTERNS:
        if pat.match(s1):
            return False, (
                "sentence 1 narrates the user's move "
                "(decryption must describe what was already true on the board)"
            )

    return True, ""

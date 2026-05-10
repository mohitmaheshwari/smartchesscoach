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
    # Opening-phase praise that says nothing about THIS position. Pattern:
    # echo the move + add generic compliment about the piece type. Source:
    # Parth's "same" bucket from regen-diff (fb_1382ba42cb94, fb_99a956e6356b,
    # fb_240145859bcf, etc).
    "bishops love",
    "bishop loves",
    "knights love",
    "knight loves",
    "rooks love",
    "queens love",
    "love open diagonal",
    "love active",
    "love open file",
    "active diagonal",
    "an active diagonal",
    "open diagonal ahead",
    "open file ahead",
    "an open diagonal",
    "an open file",
    "natural move",
    "natural development",
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


def _signals_after_echo_discount(text: str, played_move_san: str) -> int:
    """Count concrete signals while ignoring the played move's own SAN
    and destination square. Naming the move the coaching is literally
    about isn't real signal — it's tautology. Real opening-phase
    coaching names the consequence: opponent piece, target square,
    threat, or plan.

    Used by the opening-good vacuous threshold so "Bg7. Bishop on an
    active diagonal." (echoes Bg7 + generic praise) scores 0 instead
    of being rescued by the played move's own mention.
    """
    if not text or not played_move_san:
        return count_concrete_signals(text)

    lo = text.lower()
    squares = set(m.group(0).lower() for m in _SQUARE_RE.finditer(text))
    sans = set(m.group(0) for m in _SAN_RE.finditer(text))
    patterns = sum(1 for w in _CONCRETE_PATTERN_WORDS if re.search(rf"\b{re.escape(w)}\b", lo))
    filler_hits = sum(1 for ph in _FILLER_PHRASES if ph in lo)

    played_clean = played_move_san.rstrip("!?+#")
    for variant in {played_move_san, played_clean,
                    played_clean + "+", played_clean + "#",
                    played_clean + "!", played_clean + "?"}:
        sans.discard(variant)
    m = re.search(r"([a-h][1-8])", played_clean)
    if m:
        # Also drop a bare-square SAN match for that square (the regex
        # treats "g4" alone as a pawn-move SAN).
        sq = m.group(1).lower()
        squares.discard(sq)
        sans.discard(sq)

    score = len(squares) + len(sans) + patterns
    score -= 2 * filler_hits
    return score


def is_text_vacuous(
    text: str,
    severity: Optional[str] = None,
    played_move_san: Optional[str] = None,
    phase: Optional[str] = None,
) -> bool:
    """Return True if the text is vacuous given the move's severity.

    Threshold sliders:
      • mistake / blunder / inaccuracy / opp_blunder / opp_mistake:
        require >= 2 concrete signals. Real teaching needs at least
        a square and a piece, or a tactical pattern name. The played
        move's own SAN counts toward this baseline.
      • good / best / excellent / book in OPENING phase (text >30 chars):
        require >= 1 concrete signal AFTER echo-discounting the played
        move's own SAN/square. Catches "Bg7. Bishop on an active
        diagonal." which echoes the move + adds generic piece-type
        praise = 0 real signal. Short acks like "Nf3. Book." pass —
        they don't pretend to coach.
      • good / best / excellent / book elsewhere: lenient — only flag
        when score is deeply negative (filler-heavy with no signal).
      • context / unknown / None: lenient — only flag if score < -1.
    """
    if not text or not text.strip():
        return True

    sev = (severity or "").lower()
    ph = (phase or "").lower()

    if sev in ("mistake", "blunder", "inaccuracy", "opp_blunder", "opp_mistake"):
        return count_concrete_signals(text) < 2
    if sev in ("good", "best", "excellent", "book"):
        if ph == "opening" and played_move_san and len(text) > 30:
            # Opening-good is intentionally permissive — terse acks are
            # fine, and we don't want to flag legit dev/plan text just
            # because it doesn't hit our pattern keywords. So only flag
            # when (a) at least one filler phrase fired AND (b) echo-
            # discount reveals no real signal beyond the played move.
            # That's exactly the "echo move + generic praise" pattern in
            # Parth's same-bucket bugs (fb_1382ba42cb94 etc).
            return _signals_after_echo_discount(text, played_move_san) < 0
        return count_concrete_signals(text) < 0
    return count_concrete_signals(text) < -1


# ────────────────────────────────────────────────────────────────────────
# Sentence-level stripper — preserve content sentences, drop filler tails.
#
# `is_text_vacuous` returns a single yes/no for the whole string, which
# causes false-positive over-strips when content + filler appear together:
#
#   "This is the Nimzo Indian Defense Leningrad Variation.
#    Bishop slides to Bb4. Bishops love open diagonals!"
#
# The opening-name sentence is real teaching content; only the trailing
# "Bishops love…" clause is filler. `strip_vacuous_segments` splits on
# sentence + em-dash boundaries, runs the per-sentence vacuous check, and
# rejoins what survives. Net effect on V5 emit: less collateral damage
# when generation produced a mixed-quality caption.
# ────────────────────────────────────────────────────────────────────────

# Sentence terminators followed by whitespace. We deliberately do NOT
# split on em-dash / en-dash / hyphen — those usually act as clause
# joiners within a single sentence ("Rad1. Rook on an open file -
# controls the whole column.") and splitting them produces fragmented
# nonsense ("Rad1. controls the whole column.") when only the middle
# clause is filler.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def strip_vacuous_segments(
    text: str,
    severity: Optional[str] = None,
    played_move_san: Optional[str] = None,
    phase: Optional[str] = None,
) -> str:
    """Drop only the filler-bearing sentences from `text`, preserving
    sentences that carry real content (opening names, diagnoses,
    alternative-move recommendations).

    Returns:
      - the original `text` if it isn't flagged vacuous to begin with
        (don't transform good content)
      - "" if every sentence is filler, or if the only thing left after
        stripping is an echo-only remnant ("Bishop slides to Bh6.")
      - the rejoined non-filler sentences otherwise

    Used by emit-time guards instead of the all-or-nothing
    `is_text_vacuous → wipe` pattern, which was over-stripping captions
    where filler appeared alongside real content (the regen-diff
    revealed e.g. "This is the Nimzo Indian Defense… Bishop slides to
    Bb4. Bishops love open diagonals!" being fully nuked when only the
    trailing clause was filler).
    """
    if not text or not text.strip():
        return ""

    # Cheap path — text isn't vacuous, leave it alone.
    if not is_text_vacuous(
        text,
        severity=severity,
        played_move_san=played_move_san,
        phase=phase,
    ):
        return text

    raw_segments = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text)]
    raw_segments = [s for s in raw_segments if s]
    if not raw_segments:
        return ""

    # Drop any segment that contains a filler phrase. Keep everything
    # else verbatim — diagnostic sentences ("Bg3 is slightly passive")
    # and opening-name sentences ("This is the Nimzo Indian…") often
    # have low signal scores by our pattern-counting heuristics, but
    # they're real content. Only the filler-bearing tail is junk.
    kept: list[str] = []
    for seg in raw_segments:
        seg_clean = seg.rstrip(".!?")
        if not seg_clean:
            continue
        seg_lo = seg_clean.lower()
        if any(ph in seg_lo for ph in _FILLER_PHRASES):
            continue
        kept.append(seg_clean)

    if not kept:
        return ""

    # If the only thing left is a single sentence, decide whether it
    # carries enough content to keep:
    #   • Diagnostic severities (mistake/inaccuracy/blunder): a short
    #     diagnostic sentence like "Bg3 is slightly passive." has
    #     plain score = 1 (the played SAN) and is real review content.
    #     But "wins the bishop." has plain score = 0 — no SAN, no
    #     square, no pattern — drop it.
    #   • Good/book severities: drop pure-echo remnants ("Bishop slides
    #     to Bh6.") where echo-discount reveals zero signal beyond the
    #     played move's own mention.
    sev = (severity or "").lower()
    is_diag_severity = sev in ("mistake", "blunder", "inaccuracy",
                                "opp_blunder", "opp_mistake")
    if len(kept) == 1 and played_move_san:
        single = kept[0]
        if is_diag_severity:
            if count_concrete_signals(single) < 1:
                return ""
        else:
            if _signals_after_echo_discount(single, played_move_san) <= 0:
                return ""

    result = ". ".join(kept).strip()
    if result and not result.endswith((".", "!", "?")):
        result += "."
    return result

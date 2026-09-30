"""caption_why_heuristics — the ONE definition of "does this caption have a why".

Extracted 2026-09-22 from backend/scripts/audit_captions_for_why.py so the
audit that MEASURES the why-rule and the review queue that FIXES it cannot
drift apart. Mohit, 2026-09-22: "each blunder or mistake each side should
explain the why ... each blunder should have the why."

Two heuristics decide it; a caption passes if EITHER fires:
  H1 concrete consequence -- names a square/piece beyond the SANs themselves
  H2 causal connector     -- because / since / loses to / walks into / hangs

Failing both is the "X is a mistake. Y was better." shape.

H3 principle ending -- the closing sentence is a transferable rule -- is still
measured and still exported, but it no longer counts as a why. See `has_why`.

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
    """True when the caption explains itself FROM THIS POSITION.

    H3 is deliberately not a route. Mohit, 2026-09-30, asked whether a
    universal principle counts as a why and answered his own question:
    *"if they are not position specific, it might just fill in something
    that's completely irrelevant, and universal principles also looks like
    blubbering for no real reason."*

    A principle ending is a fine closing line UNDER a caption that has already
    said what happened here. On its own it is a sentence that would have been
    true of a different game, which is exactly the failure he is describing.

    `has_principle_ending` stays and is still exported, because the audit
    reports the three rates separately and the split is worth seeing. It just
    no longer buys a caption a pass.

    Measured cost of the change, 2026-09-30 over 31,178 mistake and blunder
    captions: 478 more cards join the review queue, on top of the 3,185
    already there. Nothing is removed from the queue by this.
    """
    if not caption or not caption.strip():
        return False
    return (has_concrete_consequence(caption, played_san, best_san)
            or has_causal_connector(caption))


# ---------------------------------------------------------------------------
# Structural classifier — what the REVIEW QUEUE uses.
#
# `has_why` above is a keyword scan and cannot be made accurate by adding
# keywords. Measured 2026-09-30 over all 203,022 mistake/blunder captions: it
# passes 87.3% while the structural classifier finds only 25.9% that say what
# was wrong with the move PLAYED. Adding its two biggest misses ("runs into",
# "allows") removes 8,818 cards from the queue of which only 1,768 deserve
# removal — the other 7,050 are genuinely bare and would just go invisible.
# See docs/missing_why_diagnosis_2026_09_30.md.
#
# So instead of scanning for explanation-ish words, SPLIT the caption at the
# alternative-move boundary and ask what is said on each side:
#
#   PLAYED_WHY   - a clause about the move actually played names a consequence
#                  ("drops the pawn after Bxe5", "loses to Qxd3+").
#   ALT_WHY_ONLY - the only reason given is a benefit of the ALTERNATIVE
#                  ("Nxd3+ was stronger - it trades his bishop"). The student
#                  still does not know what was wrong with their own move.
#   NO_WHY       - neither side carries a reason ("Bf6 is a mistake. f5 was
#                  better.").
#
# PLAYED_WHY is the only class that answers "why??". Moved here from
# scripts/caption_why_class.py (which had no importers) so this module is
# genuinely the one definition rather than nominally so.
# ---------------------------------------------------------------------------

SAN_RE = re.compile(
    r"\b(?:O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b")

# Markers that a clause states a CONSEQUENCE of the move it is attached to.
CONSEQUENCE_RE = re.compile(
    r"\b(loses? to|loses? the|drops? the|drops? a|hangs?|leaves?\b[^.]*\b"
    r"(?:undefended|hanging|loose|en prise)|leaves? your|allows?|lets? |"
    r"walks? into|runs? into|gets? (?:captured|taken|trapped|forked|pinned)|"
    r"is (?:captured|taken|trapped|met by|answered by)|traps? (?:your|his|her|their)|"
    r"gives? up|gives? away|abandons?|exposes?|weakens?|misses?|"
    r"costs? (?:you )?(?:the|a|your)|after \S+ )\b",
    re.IGNORECASE)

# The boundary that introduces the recommended alternative.
ALT_BOUNDARY_RE = re.compile(
    r"\b(was better|was stronger|was the move|is better|is stronger|"
    r"was best|would have been better|instead)\b", re.IGNORECASE)

# Generic transferable principles appended after the verdict.
PRINCIPLE_RE = re.compile(
    r"\b(always|never|before you|between two|in the opening|when defending|"
    r"look for the move|count what|remember|each piece|pick the one|"
    r"develop with|the rule is|prefer )\b", re.IGNORECASE)


def _sentences(text: str):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s.strip()]


def classify_caption_why(caption: str, played_san: str = "", best_san: str = "") -> dict:
    """Return {'why_class', 'played_clause', 'alt_clause', 'has_principle'}."""
    cap = (caption or "").strip()
    if not cap:
        return {"why_class": "EMPTY", "played_clause": "", "alt_clause": "",
                "has_principle": False}

    sents = _sentences(cap)
    played_parts, alt_parts, principle_parts = [], [], []

    for s in sents:
        if PRINCIPLE_RE.search(s) and not ALT_BOUNDARY_RE.search(s):
            principle_parts.append(s)
            continue
        m = ALT_BOUNDARY_RE.search(s)
        if m:
            # Text before the alternative's subject can still be about the played
            # move ("Qd7 is a mistake - it drops the pawn after Bxe5. Qxc4 was
            # better..."). Split the sentence at the boundary's subject SAN.
            head = s[:m.start()]
            # The alternative's own SAN usually sits immediately before the
            # boundary; anything earlier than that SAN describes the played move.
            sans = list(SAN_RE.finditer(head))
            if sans and best_san and sans[-1].group(0).rstrip("+#") == (best_san or "").rstrip("+#"):
                played_parts.append(head[:sans[-1].start()])
                alt_parts.append(s[sans[-1].start():])
            else:
                alt_parts.append(s)
        else:
            played_parts.append(s)

    played_text = " ".join(played_parts).strip()
    alt_text = " ".join(alt_parts).strip()

    # Strip the played SAN itself so "Qf6" alone is not mistaken for content.
    probe = played_text
    if played_san:
        probe = probe.replace(played_san, " ")

    if CONSEQUENCE_RE.search(probe):
        cls = "PLAYED_WHY"
    elif CONSEQUENCE_RE.search(alt_text) or re.search(r"—\s*it\s+\w+", alt_text):
        cls = "ALT_WHY_ONLY"
    else:
        cls = "NO_WHY"

    return {"why_class": cls, "played_clause": played_text, "alt_clause": alt_text,
            "has_principle": bool(principle_parts)}

"""Structural classifier: does a mistake caption explain the PLAYED move?

Not a keyword scan for "any explanation-ish word" (that scores
"You played Qf6; Nxd3+ was stronger - it trades his bishop." as HAVING a why,
because of the dash and the piece noun). Instead we SPLIT the caption at the
alternative-move boundary and ask what is said on each side:

  PLAYED_WHY   - there is a clause about the move the user actually played that
                 names a consequence ("drops the pawn after Bxe5", "loses to
                 Qxd3+", "leaves your bishop undefended").
  ALT_WHY_ONLY - the only reason given is a benefit of the ALTERNATIVE
                 ("Nxd3+ was stronger - it trades his bishop"). The student
                 still does not know what was wrong with their move.
  NO_WHY       - neither side carries a reason; verdict + optional generic
                 principle only ("Bf6 is a mistake. f5 was better.").

PLAYED_WHY is the only class that answers "why??".
"""
from __future__ import annotations

import re

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


if __name__ == "__main__":
    CASES = [
        ("You played Qf6; Nxd3+ was stronger — it trades his bishop.", "Qf6", "Nxd3+", "ALT_WHY_ONLY"),
        ("Qd7 is a mistake — it drops the pawn after Bxe5. Qxc4 was better — it wins a pawn.", "Qd7", "Qxc4", "PLAYED_WHY"),
        ("Bf6 is a mistake. f5 was better.", "Bf6", "f5", "NO_WHY"),
        ("Kf1 loses to Qxd3+. Ke2 was better.", "Kf1", "Ke2", "PLAYED_WHY"),
        ("Nd4 is a mistake. e4 was better — it attacks the knight on f3.", "Nd4", "e4", "ALT_WHY_ONLY"),
        ("Bxf7+ leaves your bishop undefended — opponent recaptures on f7. Be3 was better — it develops a piece.", "Bxf7+", "Be3", "PLAYED_WHY"),
        ("Nxe5 is a mistake. dxe5 was better. Look for the move that creates two threats.", "Nxe5", "dxe5", "NO_WHY"),
    ]
    ok = 0
    for cap, played, best, want in CASES:
        got = classify_caption_why(cap, played, best)["why_class"]
        flag = "ok " if got == want else "FAIL"
        if got == want:
            ok += 1
        print("%s want=%-13s got=%-13s %s" % (flag, want, got, cap[:70]))
    print("%d/%d" % (ok, len(CASES)))

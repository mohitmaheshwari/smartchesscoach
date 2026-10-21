"""Make a verified caption read more easily. Nothing else.

Mohit 2026-10-21, setting the boundary:

    "LLM should never reason on chess position, it will just take up the
     english from template that our engine would create and would beautify
     that, nothing else"

and then choosing the model: gpt-6-luna.

The safety property comes from that boundary, not from a prompt
-----------------------------------------------------------------
The model is never shown the position. It gets one sentence and a rating. It
cannot invent a variation it has not been given, because it has not been given
a board. That is structural; a prompt telling it to behave is not.

Which matters, because when the same model WAS shown a position and asked for
hypotheses it proposed `Nb4` and `Bb4` into a pawn that had been sitting on a3
all game, and `c5` with Black's own knight on c6 -- an illegal move. One
illegal and two hanging, out of five. It is excellent at the shape of English
and unreliable at chess, so it is given English and no chess.

The model is untrusted; the validator is the guarantee
------------------------------------------------------
Measured head to head on three real captions, gpt-6-luna changed a word that
carried meaning every time:

    "pushed" -> "moved"        a pawn push is not a piece move, and the code
                               that chose "pushed" says so in a comment
    "their own c-pawn"         dropped "own" -- which IS the lesson, the
       -> "their c-pawn"       knight is blocking its OWN pawn
    "guarding" -> "guarded"    harmless

gpt-5.6-luna was clean on the same three. That is n=3 and too thin to pick a
model on, so the model stays configurable and the VALIDATOR decides: any
output that adds or drops a chess token, or drops a protected word, is
rejected and the deterministic caption ships unchanged. A bad rewrite becomes
a rejection, never a regression, and the rejection rate is then a measurement
we can act on instead of an argument.

Cost is not a consideration: measured $0.063 per 1,000 calls. Latency is --
about 2s -- so this is for one caption on demand, never a loop over 72 cards.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

POLISH_MODEL = os.environ.get("CAPTION_POLISH_MODEL", "gpt-6-luna")
POLISH_EFFORT = os.environ.get("CAPTION_POLISH_EFFORT", "low")
POLISH_ENABLED = os.environ.get("CAPTION_POLISH_ENABLED", "0") == "1"

SYSTEM = (
    "You rewrite one chess coaching sentence so a student reads it easily.\n"
    "HARD RULES:\n"
    "- You are NOT given the position and must NOT reason about chess.\n"
    "- Never add, remove or change any move, square or piece. Keep them "
    "exactly as written.\n"
    "- Never add a new chess claim. Only rephrase what is already there.\n"
    "- Short sentences, one idea each, common words.\n"
    "- No numbers except squares and moves.\n"
    "- Keep the final coaching principle if there is one.\n"
    "Reply with the rewritten sentence only."
)

# A chess token: a square or a SAN move. These must survive untouched.
_TOKEN = re.compile(
    r"\b(?:O-O(?:-O)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b")

# Words that carry the lesson. Losing one is meaning drift, not polish, and
# the token check cannot see it because none of these is a chess token.
PROTECTED = (
    "own",        # "their OWN c-pawn" -- the whole point of that card
    "pushed",     # a pawn push is not a piece move
    "guarding",
    "blocks",
    "only",
    "not",        # negation: losing it inverts the sentence
    "never",
)

MAX_GROWTH = 1.6     # a "rewrite" twice as long is a rewrite of something else


def _tokens(text: str):
    return sorted(set(_TOKEN.findall(text or "")))


def validate(original: str, polished: str) -> Optional[str]:
    """Why the rewrite must be refused, or None when it may ship.

    Every rule here exists because something produced its failure, either in
    the measured head-to-head or in my own first version of this check.
    """
    if not polished or not polished.strip():
        return "empty"
    if len(polished.split()) < 5:
        # An earlier version of this check passed an EMPTY answer, because an
        # empty string adds no chess tokens and so satisfied the only rule
        # there was. gpt-5-mini spent its whole budget thinking and returned
        # nothing; the check said PASS.
        return "truncated"
    before, after = _tokens(original), _tokens(polished)
    added = [t for t in after if t not in before]
    dropped = [t for t in before if t not in after]
    if added:
        return f"invented chess: {added}"
    if dropped:
        return f"dropped chess: {dropped}"
    low_before, low_after = original.lower(), polished.lower()
    lost = [w for w in PROTECTED
            if re.search(rf"\b{w}\b", low_before)
            and not re.search(rf"\b{w}\b", low_after)]
    if lost:
        return f"dropped meaning: {lost}"
    if len(polished.split()) > max(12, len(original.split()) * MAX_GROWTH):
        return "grew too long"
    if re.search(r"\d", _TOKEN.sub("", polished)):
        return "introduced a number"
    return None


async def polish(caption: str, rating: Optional[int] = None,
                 *, model: Optional[str] = None) -> Dict[str, Any]:
    """Return the polished caption, or the original with the reason it was not.

    Never raises and never blocks a card. A model that is slow, down, or wrong
    leaves the deterministic sentence exactly as it was.
    """
    out: Dict[str, Any] = {
        "text": caption, "polished": False, "reason": "", "model": None,
    }
    if not POLISH_ENABLED:
        out["reason"] = "disabled"
        return out
    if not caption or not caption.strip():
        out["reason"] = "nothing to polish"
        return out

    chosen = model or POLISH_MODEL
    try:
        from llm_service import call_llm
        said = await call_llm(
            SYSTEM,
            f"Student rating: {rating or 1200}\nSentence: {caption}",
            model=chosen,
            max_tokens=2000,
            reasoning_effort=POLISH_EFFORT,
        )
    except Exception as exc:                      # noqa: BLE001
        logger.warning("[caption_polish] %s unavailable: %r", chosen, exc)
        out["reason"] = "llm_error"
        return out

    said = (said or "").strip().strip('"')
    problem = validate(caption, said)
    if problem:
        logger.info("[caption_polish] rejected (%s): %r -> %r",
                    problem, caption[:60], said[:60])
        out["reason"] = problem
        out["model"] = chosen
        return out
    out.update(text=said, polished=True, model=chosen)
    return out

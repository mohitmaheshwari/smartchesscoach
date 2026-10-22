"""The caption, written by an LLM from engine facts. Generated once, stored.

Mohit, 2026-10-22: "the answer for caption is LLM based, now, i hope you're
clear on that", and earlier in the same session: "the LLM would be only
responsible for text generation, every detail would come from our engine",
and "once the LLM are published, we will not be generating new templates for
each run, no new call per position".

So: the LLM writes, the engine supplies every fact, and the call happens ONCE
when a game is analysed. The text is stored and served deterministically
afterwards -- no model call when a page renders.

WHY THIS BEATS THE TEMPLATES, AND WHY IT IS NOT ENOUGH ON ITS OWN
-----------------------------------------------------------------
Measured on Mohit's Bd6+ card, same model, only the facts differing:

  facts the pipeline had      "Bd6+ lets your bishop be taken by Qxd6. Qxg8
                               was better, sacrificing your queen to capture
                               a rook."
  plus the refutation          "...Qxg8 instead sacrifices your queen for the
                               rook and threatens mate with Bd6#."

The first is the vague caption we already shipped. The model was never the
bottleneck -- the facts were. That is why `move_purposes` exists and why this
file refuses to write anything the facts do not contain.

WHAT IT MAY NOT DO
------------------
It may not invent a chess fact. Every square, piece and move in the output
must appear in the facts handed in, and the validator below rejects the
caption otherwise. A rejected caption is NOT silence -- the deterministic
caption the pipeline already produced stays, because coverage is first-class
and a mediocre true sentence beats nothing.

It also never touches arrows. Those are drawn from `pv_after_played` by code
that is working and that Mohit asked to leave alone.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Off until measured. Enabling it changes what every player reads.
LLM_CAPTIONS_ENABLED = os.environ.get(
    "LLM_CAPTIONS_ENABLED", "0") not in ("0", "false", "False", "")

LLM_CAPTION_MODEL = os.environ.get("LLM_CAPTION_MODEL", "gpt-6-luna")

# The repo's caption cap. caption_config.json sets 60; a teaching sentence
# for a 900 should be well under it anyway.
MAX_WORDS = 55

# Squares, piece letters with squares, SAN moves, piece names. Anything
# matching these in the output must have been in the facts.
_SAN = re.compile(
    r"\b(?:[KQRBN][a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?"
    r"|[a-h]x?[a-h][1-8](?:=[QRBN])?[+#]?"
    r"|[a-h][1-8]"
    r"|O-O(?:-O)?[+#]?)\b")
_PIECE = re.compile(r"\b(pawn|knight|bishop|rook|queen|king)s?\b", re.I)

SYSTEM = (
    "You write one or two short sentences for a chess player rated 600 to "
    "1500, explaining why the move they played was worse than the engine's "
    "choice.\n"
    "RULES:\n"
    "- Use ONLY the facts given. Never state a chess fact that is not in "
    "them. Do not invent squares, pieces or moves.\n"
    "- Lead with the most important thing. The facts are ranked; tier 4 is "
    "mate, 3 is material, 2 is safety, 1 is positional.\n"
    "- Short sentences, one idea each, common words. No jargon a 900 would "
    "not know.\n"
    "- Say what to learn, not just what happened.\n"
    "- Never mention centipawns, evaluations or numbers.\n"
    "- At most 2 sentences."
)


# A SAN already names its own piece: Bd6+ is a bishop move, Qxg8 a queen
# move, e4 a pawn move. The first version of the validator rejected the word
# "bishop" on a card whose played move was Bd6+ -- the model reading the
# facts correctly and the check being wrong about what they contain.
_SAN_PIECE = {"K": "king", "Q": "queen", "R": "rook",
              "B": "bishop", "N": "knight"}


_SQUARE = re.compile(r"[a-h][1-8]")


def _implied_pieces(text: str) -> set:
    """What a SAN already tells you, so the validator does not call it an
    invention.

    Two kinds, both found by rejecting a correct caption:

      the piece     "Bd6+" is a bishop move, so the word "bishop" is in the
                    facts even though the string is not.
      the square    "Bd6+" names d6, so "the bishop on d6" is the model
                    reading the fact, not adding one.
    """
    out = set()
    for m in _SAN.finditer(text or ""):
        san = m.group(0)
        if san.startswith("O-O"):
            out.update(("king", "rook"))
        elif san[0] in _SAN_PIECE:
            out.add(_SAN_PIECE[san[0]])
        else:
            out.add("pawn")
        sq = _SQUARE.findall(san)
        if sq:
            out.add(sq[-1])          # the destination
    return out


def _tokens(text: str) -> set:
    return set(m.group(0) for m in _SAN.finditer(text or "")) | \
        set(m.group(0).lower().rstrip("s") for m in _PIECE.finditer(text or ""))


def build_facts(
    played_san: str,
    best_san: Optional[str],
    purposes: List[Dict[str, Any]],
    *,
    severity: Optional[str] = None,
    threat: Optional[str] = None,
    punishment_line: Optional[List[str]] = None,
    opp_reply_is_clear: Optional[bool] = None,
    best_is_only_move: Optional[bool] = None,
) -> Dict[str, Any]:
    """The fact bundle handed to the model. Engine output only.

    No evaluations and no centipawns: they are not teachable and the model
    turns them into "you lost 4.4 pawns", which this repo has a commit hook
    against.
    """
    facts: Dict[str, Any] = {
        "you_played": played_san,
        "better_move": best_san,
        "what_the_better_move_achieves": [
            {"kind": p["kind"], "importance": p["tier"], "detail": p["proof"]}
            for p in (purposes or [])
        ],
    }
    if severity:
        facts["how_bad"] = severity
    if threat:
        facts["they_were_threatening"] = threat
    if punishment_line:
        facts["what_happens_after_your_move"] = list(punishment_line)[:6]
    if opp_reply_is_clear is not None:
        # The field that separates "they win your rook" from "they might".
        facts["their_best_reply_is_clearly_best"] = bool(opp_reply_is_clear)
    if best_is_only_move is not None:
        facts["the_better_move_was_the_only_good_one"] = bool(best_is_only_move)
    return facts


def validate(facts: Dict[str, Any], caption: str) -> Optional[str]:
    """Why the caption must be refused, or None when it may ship.

    The whole safety story: a fact the engine did not supply may not appear.
    The model is allowed to choose, order and phrase -- never to add.
    """
    if not caption or not caption.strip():
        return "empty"
    words = caption.split()
    if len(words) < 5:
        return "truncated"
    if len(words) > MAX_WORDS:
        return f"too long ({len(words)} words)"
    flat = _flatten(facts)
    allowed = _tokens(flat) | _implied_pieces(flat)
    used = _tokens(caption)
    invented = sorted(used - allowed)
    if invented:
        return f"invented chess not in the facts: {invented}"
    # "drops about 4.4 pawns of material" -- the decimal is the point, and  # allow-cp-loss-phrase
    # the first version of this check missed it because \d+\s* does not span
    # one. The repo has a commit hook against this phrasing: centipawns are
    # not material.
    if re.search(r"\d[\d.]*\s*(cp\b|centipawns?|pawns? of)", caption, re.I):
        return "talks in evaluations"
    return None


def _flatten(obj: Any) -> str:
    if isinstance(obj, dict):
        return " ".join(_flatten(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return " ".join(_flatten(v) for v in obj)
    return str(obj)


async def write_caption(
    facts: Dict[str, Any],
    *,
    model: Optional[str] = None,
    rating: Optional[int] = None,
) -> Dict[str, Any]:
    """One caption from the facts, or the reason there is none.

    Returns {"caption": str|None, "refused": str|None, "model": str}. The
    caller keeps its deterministic caption when `caption` is None -- this
    never produces silence, it only declines to replace.
    """
    import json

    out: Dict[str, Any] = {"caption": None, "refused": None,
                           "model": model or LLM_CAPTION_MODEL}
    if not LLM_CAPTIONS_ENABLED:
        out["refused"] = "disabled"
        return out
    if not (facts.get("what_the_better_move_achieves")
            or facts.get("they_were_threatening")
            or facts.get("what_happens_after_your_move")):
        # Nothing to write FROM. The deterministic caption stands.
        out["refused"] = "no facts to write from"
        return out

    user = json.dumps(facts, indent=1)
    if rating:
        user = f"The player is rated about {int(rating)}.\n\n{user}"
    try:
        from llm_service import call_llm
        text = await call_llm(
            SYSTEM, user, model=out["model"],
            max_tokens=2000, reasoning_effort="low")
    except Exception as exc:
        logger.warning("[llm_caption] call failed: %r", exc)
        out["refused"] = f"call failed: {type(exc).__name__}"
        return out

    text = (text or "").strip().strip('"')
    why = validate(facts, text)
    if why:
        logger.info("[llm_caption] refused (%s): %s", why, text[:120])
        out["refused"] = why
        return out
    out["caption"] = text
    return out

"""The why button's answer, written by the model from the engine's facts.

Mohit, 2026-10-29: "when we click why, it should evaluate and give an english
of it", and earlier in the same session, setting the order of operations:
"once it understands the reasons, it calls LLM and translate that into text."

So the engine resolves the reason exactly as it does today -- this module is
downstream of `punishment_resolver` and changes nothing it decides -- and the
model turns the resolved facts into English. The model is given facts and no
board, so it cannot propose a move or a variation it was not handed.

WHY FROM THE FACTS AND NOT FROM THE SENTENCE
--------------------------------------------
`services/caption_polish.py` already rewrites a finished sentence, and the
obvious move was to point it at `_phrase()`. Measured on 13 real why sentences,
gpt-6-luna, 11 shipped:

  6 of the 11 came back BYTE-IDENTICAL. `_phrase()` already writes short plain
    English, so a copywriter has nothing to do. The English was never the
    shortage -- derivable reasons were.
  1 of the 5 changes broke a fact: "Nc3 chases your queen" -> "Nc3 attacks your
    queen". FORCES_RETREAT means the queen is OBLIGED TO MOVE; "attacks" is a
    weaker, different claim, and the polish validator cannot see it because
    "chases" is not a chess token.
  2 were rejected as "truncated": "Rxa7 wins their queen." is four words, so
    any faithful rewrite falls under that validator's absolute five-word floor
    and is refused by construction -- the shortest, clearest answers are the
    ones it can never ship.

From the facts there is something to gain instead of paraphrase: the resolver
knows the line, the square, which piece changes hands and whether a chased
piece goes back where it came from, and `_phrase()` spends most of that on the
floor because twelve fixed templates cannot say twelve hundred things.

WHAT GUARDS IT
--------------
`llm_caption.validate` -- the same function, not a copy. It flattens whatever
facts dict it is given and refuses any chess token (SAN or piece noun) that is
not in them, so the safety property is one implementation serving both paths.

One guard is new here, because containment alone could not catch the failure
above: for the mechanisms whose claim lives in a VERB rather than in a piece
name, the facts state the relation and the output has to still convey it. That
is a containment check on the engine's own claim, in the same family as
caption_polish's PROTECTED list -- it is NOT a quality score, and nothing here
judges whether a sentence is good by looking for words in it.

A refusal is never silence. The caller keeps the deterministic sentence, which
says less and says nothing false.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

WHY_WORDS_ENABLED = os.environ.get("WHY_WORDS_ENABLED", "0") == "1"
WHY_WORDS_MODEL = os.environ.get("WHY_WORDS_MODEL", "gpt-6-luna")
WHY_WORDS_EFFORT = os.environ.get("WHY_WORDS_EFFORT", "low")

# Two sentences, because the answer has at most two parts: what happens, and
# what it means. The caption path caps at 55 for a card that sits in a list;
# this one is read on its own after a deliberate click.
MAX_WORDS = 45

SYSTEM = (
    "You write one or two short sentences for a chess player rated 600 to "
    "1500, explaining one move in their game. You are given facts worked "
    "out by a chess engine.\n"
    "HARD RULES:\n"
    "- You are NOT given the position. Never name a move, square or piece "
    "that is not in the facts, and never suggest a move of your own.\n"
    "- Say only what the facts say. Add no new chess claim, no evaluation, "
    "no advice about the opening or the plan.\n"
    "- `relation` is the engine's finding and your sentences must still say "
    "it. Put it in your own natural words -- do not copy the phrasing of the "
    "fact. Do not soften it either: 'forced to move' is not 'attacks', and "
    "naming a piece is not the same as saying it is won.\n"
    "- Short sentences, one idea each, common words. No numbers.\n"
    "- `whose_move` says whose move is being explained. When it is theirs, "
    "never tell the reader what they should have played.\n"
    "Reply with the sentences only."
)

# What each mechanism is CLAIMING, in words the engine owns. This is handed to
# the model as `relation` so it has the right verb available, and checked on
# the way back so it cannot trade it for a weaker one.
#
# Every mechanism the resolver can speak about is listed. The first version
# listed only the four whose claim lives in a verb, and the measured result of
# leaving WINS_MATERIAL out is in the comment below.
_RELATION: Dict[str, str] = {
    # WINS_MATERIAL was left out of this at first, on the reasoning that its
    # claim IS the piece noun and containment already guards that. Measured on
    # 14 real positions, 2 of the 3 material answers dropped the claim and
    # passed validation anyway:
    #
    #   "After a4, f4+ is available. In the line, the king takes on e3, then
    #    their rook goes to d5."
    #   "After their opponent played Nb4, Rxb2 is the move involving their
    #    knight."
    #
    # Both name the piece, so containment was satisfied; neither says it is
    # won. Containment proves a noun APPEARED, never that anything was claimed
    # about it -- and this is the mechanism behind 191 of 255 answers, so the
    # hole was in three quarters of the output.
    "WINS_MATERIAL": "the piece is won -- it changes hands for nothing like it",
    "MATE": "the side that is mated cannot avoid checkmate",
    "FORK": "one move attacks two things at once and only one can be saved",
    "TRAPPED": "the piece has no safe square to go to",
    "PROMOTES": "the pawn reaches the last row and becomes a queen",
    "FORCES_RETREAT": "the piece is forced to move away",
}

# Any ONE of these conveys the relation. Written as alternatives, not as a
# required phrase, because "forced to move", "has to move" and "must run" are
# the same finding and the model should be free to choose.
#
# Regexes, not substrings, and the boundaries are the point. A plain `in` test
# let "Nc3 wins MATErial" satisfy the MATE guard -- a material claim passing
# the check that exists to stop a mate becoming a material claim. So each
# alternative states its own boundary: `mate[sd]?\b` accepts "mate", "mated"
# and "checkmate" and refuses "material", while `forc` stays a prefix on
# purpose, to cover forced / forces / forcing.
_CONVEYS: Dict[str, str] = {
    "WINS_MATERIAL": (r"\bwins?\b|\bwon\b|\btakes?\b|\btaken\b|\bcaptur"
                      r"|\blose[sr]?\b|\blost\b|\bfalls?\b|\bgoes down\b"
                      r"|\bpicks? up\b|\bpicked up\b|\bgives? up\b|\bdrops?\b"),
    "MATE": r"\bmate[sd]?\b|\bcheckmate",
    "FORK": r"\btwo\b|\bboth\b|\bdouble",
    "TRAPPED": (r"\bno safe\b|\bnowhere\b|\bno square|\btrapped\b|\bstuck\b"
                r"|\bcan(?:not|'t)\s+move\b|\bno way out\b|\bno escape\b"),
    "PROMOTES": (r"\bqueen|\bpromot|\blast (?:row|rank)\b|\bend of the board\b"
                 r"|\bother side\b|\beighth\b|\bfirst row\b"),
    "FORCES_RETREAT": (r"\bchase|\bforc|\bmust (?:move|go|run)\b"
                       r"|\b(?:has|have|had) to (?:move|go|run)\b|\bdriv"
                       r"|\bretreat|\bruns? (?:away|back)\b|\bmoves? (?:away|back)\b"
                       r"|\bmove (?:away|back)\b|\bback off\b|\bsends?\b|\bsent\b"),
}


def conveys_relation(mechanism: str, text: str) -> Optional[str]:
    """Why the text drops the engine's finding, or None when it keeps it."""
    wanted = _CONVEYS.get((mechanism or "").upper())
    if not wanted:
        return None
    if re.search(wanted, (text or "").lower()):
        return None
    return f"dropped the {mechanism} relation"


def _owned(whose: str, named: Optional[str]) -> str:
    """'your knight' / 'two of their pawns', the same reading _phrase() uses."""
    named = (named or "").strip().lower()
    if not named:
        return f"{whose} piece"
    if named.startswith(("two ", "three ", "four ", "several ")):
        count, _, rest = named.partition(" ")
        return f"{count} of {whose} {rest}"
    return f"{whose} {named}"


def build_facts(
    punishment: Any,
    played_san: str,
    *,
    mover_is_user: bool = True,
) -> Dict[str, Any]:
    """The resolver's finding, as facts a model can read and nothing more.

    Every value here came off the board or out of the engine. `payoff_cp` is
    deliberately left OUT: it is an evaluation, the prompt forbids numbers, and
    a centipawn figure is the one thing a 600-1500 player cannot use.
    """
    p = punishment
    direction = getattr(p, "direction", "") or ""
    mechanism = (getattr(p, "mechanism", "") or "").upper()
    # "received": their reply punishes the move that was played. "missed": the
    # better move would have collected this and the played move let it go.
    theirs = direction == "received"
    # The ownership rule lives with the dataclass that defines `direction`, so
    # the template path and this one cannot drift apart. This file had its own
    # copy, and the copies DISAGREED -- which is how the template bug was
    # found: _phrase() said "your knight on e4" where these facts said
    # "their", and the board agreed with the facts.
    from services.punishment_resolver import victim_owner
    victim_whose = victim_owner(direction, mover_is_user)

    facts: Dict[str, Any] = {
        "whose_move": "the reader's" if mover_is_user else "their opponent's",
        "the_move_played": str(played_san or "").strip(),
        "relation": _RELATION.get(mechanism, ""),
        "the_move_that_does_it": str(getattr(p, "agent_move", "") or "").strip(),
    }
    facts["this_happens_after_the_move_played"] = bool(theirs)

    named = getattr(p, "victim_piece", None)
    if mechanism == "MATE" and not named:
        # A mate is by definition against a king, so "king" is a fact the
        # engine supplies and not a word the model added. Without it,
        # containment refuses "their king is mated" -- correct by its own rule
        # and wrong about the position, since that is the one piece a mate
        # always involves.
        named = "king"
    if named or mechanism in ("TRAPPED", "FORCES_RETREAT", "WINS_MATERIAL"):
        facts["the_piece_involved"] = _owned(victim_whose, named)
    square = getattr(p, "victim_square", None)
    if square:
        facts["the_square_it_is_on"] = str(square)
    if mechanism == "FORCES_RETREAT" and getattr(p, "returns_home", False):
        facts["it_goes_back_to_the_square_it_came_from"] = True
    retreat = getattr(p, "retreat_san", None)
    if retreat:
        facts["the_only_square_it_can_go_to"] = str(retreat)

    # THE LINE IS DELIBERATELY NOT HERE.
    #
    # It was, and it is what the two dropped-claim failures were made of:
    #
    #   "After a4, f4+ is available. In the line, the king takes on e3, then
    #    their rook goes to d5."
    #
    # The claim ("f4+ wins your rook") is gone and a move list is narrated in
    # its place. The relation guard cannot catch it either, because "the king
    # TAKES on e3" matches the win verb while what is taken is the king's own
    # recapture, not the victim -- no word-level check can tie a verb to the
    # right piece, and trying to is the string-matching trap.
    #
    # Withholding the line is structural instead: with no move list in the
    # facts, containment refuses every SAN in it (Kf2, fxe3+, Kxe3, Rd5) and
    # "the king" as well, so the sentence cannot be built. The line is the
    # resolver's PROOF -- it already replayed it to derive the claim -- and it
    # was never material for the sentence. This is the failure llm_caption.py
    # documents, and the first version of this file cited it and then passed
    # the line anyway.
    #
    # The cost is real and accepted: on a PROMOTES card the model read the
    # line well ("the king can take the rook with Kxg6, then the pawn reaches
    # the last row"). Buying that back means the resolver naming that capture
    # as its own fact, not handing over the list.
    return facts


def validate(facts: Dict[str, Any], text: str) -> Optional[str]:
    """Why the answer must be refused, or None when it may ship.

    Three layers, in the order they are cheap: shape, then token containment
    (shared with the caption path, not reimplemented), then the relation.
    """
    if not text or not text.strip():
        return "empty"
    words = text.split()
    if len(words) > MAX_WORDS:
        return f"too long ({len(words)} words)"
    # No absolute floor on length. caption_polish has one and it refuses every
    # faithful rewrite of a four-word answer; a short true sentence is the best
    # outcome this feature has, not a failure.
    #
    # The containment rule itself is llm_caption's, called through its own
    # helpers rather than through its validate(): that wrapper also applies a
    # five-word floor and a 55-word cap, and padding the text to slip past
    # them would be gaming another function's checks instead of reusing its
    # rule. The rule is the three lines below, and they are not duplicated
    # here -- `_tokens`, `_implied_pieces` and `_flatten` are imported.
    from services.llm_caption import _flatten, _implied_pieces, _tokens
    flat = _flatten(facts)
    invented = sorted(_tokens(text) - (_tokens(flat) | _implied_pieces(flat)))
    if invented:
        return f"invented chess not in the facts: {invented}"
    if re.search(r"\d[\d.]*\s*(cp\b|centipawns?|pawns? of)", text, re.I):
        return "talks in evaluations"
    return conveys_relation(_mechanism_of(facts), text)


def _mechanism_of(facts: Dict[str, Any]) -> str:
    """Recover the mechanism from the relation we put in the facts.

    Stored as the relation rather than the bare name because the name is
    jargon the model should never see, and a second key saying "FORCES_RETREAT"
    would be a word it could copy into the answer.
    """
    rel = str(facts.get("relation") or "")
    for mech, text in _RELATION.items():
        if rel and rel == text:
            return mech
    return ""


async def write(
    facts: Dict[str, Any],
    *,
    rating: Optional[int] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """English for these facts, or the reason there is none.

    Returns {"text": str|None, "refused": str|None, "model": str}. `text` None
    means the caller ships its template sentence unchanged -- this never
    produces silence, it only declines to replace.
    """
    out: Dict[str, Any] = {"text": None, "refused": None,
                           "model": model or WHY_WORDS_MODEL}
    if not WHY_WORDS_ENABLED:
        out["refused"] = "disabled"
        return out
    if not facts.get("the_move_that_does_it"):
        # The resolver names the move that does the damage on every mechanism
        # it can speak about. Without it there is no finding to phrase, and a
        # model handed a move list and asked why a move was bad will read
        # causality off the line -- the one failure llm_caption.py was built
        # around.
        out["refused"] = "no resolved finding"
        return out

    user = json.dumps(facts, indent=1)
    if rating:
        user = f"The player is rated about {int(rating)}.\n\n{user}"
    try:
        from llm_service import call_llm
        said = await call_llm(SYSTEM, user, model=out["model"],
                              max_tokens=2000,
                              reasoning_effort=WHY_WORDS_EFFORT)
    except Exception as exc:                      # noqa: BLE001
        logger.warning("[why_words] call failed: %r", exc)
        out["refused"] = f"call failed: {type(exc).__name__}"
        return out

    said = re.sub(r"\s+", " ", (said or "").strip().strip('"')).strip()
    problem = validate(facts, said)
    if problem:
        logger.info("[why_words] refused (%s): %s", problem, said[:140])
        out["refused"] = problem
        return out
    out["text"] = said
    return out

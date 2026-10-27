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

# The classification labels (stockfish_service.MoveClassification) that mean
# the move was actually bad. Used to decide whether a card with no known
# better move may be described as fine -- a derived opponent record has a
# cp_loss but no best_move, and "fine" would be a false fact on a blunder.
_BAD_MOVE = {"inaccuracy", "mistake", "blunder"}

# Squares, piece letters with squares, SAN moves, piece names. Anything
# matching these in the output must have been in the facts.
_SAN = re.compile(
    r"\b(?:[KQRBN][a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?"
    r"|[a-h]x?[a-h][1-8](?:=[QRBN])?[+#]?"
    r"|[a-h][1-8]"
    r"|O-O(?:-O)?[+#]?)\b")
_PIECE = re.compile(r"\b(pawn|knight|bishop|rook|queen|king)s?\b", re.I)

_COMMON = (
    "RULES:\n"
    "- You do NOT analyse chess. Every chess fact, every relationship "
    "between them and their order comes from the engine. You turn them "
    "into English and nothing else.\n"
    "- Use ONLY the facts given. Never state a chess fact that is not "
    "in them, and never work one out. Do not invent squares, pieces or "
    "moves.\n"
    "- The facts are ALREADY in order. Lead with the first one. Do not "
    "decide for yourself which matters most -- that is chess, and the "
    "engine has done it.\n"
    "- WRITE IT SO IT IS UNDERSTOOD. This is the whole reason a model "
    "writes this line instead of a template. The reader has played a few "
    "hundred games. They know the piece names and the square names and "
    "very little else.\n"
    "- Short sentences, about ten to twelve words. One idea in each.\n"
    "- Always the plainest word that is still true. Everyday words beat "
    "chess words.\n"
    "- The facts are written for an engineer. Say the same thing the way a "
    "coach says it out loud:\n"
    "    \"attacked more than they are defended\" -> \"they have more "
    "pieces hitting that square than you have guarding it\"\n"
    "    \"the mover's last bishop on the light squares\" -> \"your only "
    "bishop that could guard the light squares\"\n"
    "    \"nothing to win it back\" -> \"and you cannot take anything "
    "back\"\n"
    "- Never use these words unless you explain them in the same "
    "sentence: tempo, initiative, development, complex, structure, "
    "outpost, prophylaxis, zugzwang, fianchetto, overloaded, "
    "counterplay, passive, coordination.\n"
    # Mohit on a rendered caption: "very very very difficult english, it
    # needs to be simplest like a 10 year old can understand". Measured
    # over stored captions: "undefended" is in 51% of them and "material"
    # in 16%. Neither is a word a ten-year-old owns, and each has a plain
    # replacement that says MORE than the word it replaces.
    "- Never use these words at all; say the plain thing instead. "
    "\"undefended\" -> \"nothing is guarding it\". "
    "\"material\" -> name the piece. "
    "\"inaccuracy\" -> \"a small mistake\". "
    "\"exchange\" -> \"trade\". "
    "\"recapture\" -> \"take back\". "
    "\"centralise\" -> \"bring it to the middle\".\n"
    "- Write for a ten-year-old. Short sentences, one idea each, words a "
    "child already knows. If a sentence needs rereading, it is wrong.\n"
    "- Never more than fourteen words in one sentence. Split it instead.\n"
    "- When the facts list several squares or several pieces, name ONE as "
    "the example and drop the rest. A list of squares is not teaching. "
    "Measured: spelling out all three cost six extra words and made the "
    "sentence longer than the version this rule replaced.\n"
    "- The reader must finish the sentence knowing what to do differently "
    "next game. If the honest lesson cannot be said plainly, say the "
    "simplest true part of it and stop. Saying less plainly beats saying "
    "all of it in a sentence they reread.\n"
    "- `what_their_move_sets_up` or `what_your_move_sets_up` means the "
    "move was FINE and it prepares something. Never call it a mistake, "
    "never offer a better move, and say what is coming and what to do "
    "about it.\n"
    "- `about_this_player` is what the coach knows about the READER. Use "
    "it to say WHY the move happened, which the move alone cannot:\n"
    "    `quick_for_this_player` with `seconds_on_this_move` -> they did "
    "not look. Say the seconds plainly, once: \"you played this in four "
    "seconds\". That is the lesson on such a card, not the chess.\n"
    "    `they_have_solved_puzzles_on_this` -> they KNOW the pattern, so "
    "it is about looking, not learning. Never tell them to learn it.\n"
    "    `this_weakness_lately` is active, declining or fading. Say it in "
    "words -- \"this one keeps coming back\", \"this is getting better\". "
    "NEVER a number of past mistakes, and never a tally. No scoreboard.\n"
    "    `we_flagged_this_in_an_earlier_game` -> this exact pattern came "
    "up in one of their OWN earlier games and we showed it to them. Open "
    "by connecting the two, the way a coach would: \"we looked at this in "
    "an earlier game\". Never say which game, never say how many times.\n"
    "    `they_missed_it_last_time_too` -> they got it wrong then as well, "
    "so the lesson is the thing to repeat, plainly and without reproach. "
    "`they_got_it_right_last_time` -> they HAVE played this correctly "
    "before, so say that first; it is the most encouraging fact on the "
    "card, and it makes this a slip rather than a gap.\n"
    "    `clean_games_in_a_row` is good news and you MUST say it when it "
    "is there, in the FIRST sentence, before the mistake: \"you had five "
    "clean games before this one\". A player who is improving has to hear "
    "it on the card where they slipped, or they hear it nowhere.\n"
    "- Never scold. Nothing in `about_this_player` is an accusation; a "
    "fast move is a habit to notice, not a failing.\n"
    "- ALWAYS say what actually happened on the board -- the reply and "
    "what it hits. `about_this_player` is the FRAME around that, never a "
    "replacement for it. A card reading \"you played this in four seconds "
    "and this keeps coming back\", with no mention of the move that "
    "punished it, tells the reader nothing they can check.\n"
    "- With `about_this_player` you may use three sentences instead of "
    "two, since the frame and the board both have to fit.\n"
    "- `lesson` is the thing to teach. Say it in your own plain words. "
    "Never invent a different lesson, and never work one out from the "
    "other facts.\n"
    "- Never mention centipawns, evaluations or numbers.\n"
    "- At most 2 sentences."
)

# ONE prompt. An earlier version had two -- a separate one for opponent
# cards -- because the engine was handing over facts written from the
# MOVER's side ("attacks their pawn on e5"), which reads backwards when
# the reader did not make the move.
#
# Mohit, 2026-10-22: "why reshaping captions, it's an engine problem,
# what engine gave us is what LLM should write, why are you captioning
# again?" He is right. The fix belonged in move_purposes, whose proofs
# now name the OWNER as a fact -- "the waiting side's pawn on e5" -- and
# leave the pronouns to this layer, which is the only thing it is for.
SYSTEM = (
    "You write one or two short sentences for a chess player rated 600 "
    "to 1500, about one move in their game.\n"
    "- `mover` says WHOSE move it is. When it is the reader's, explain "
    "why their move was worse than the better one. When it is their "
    "opponent's, explain what makes the opponent's move weak and what "
    "it means for the reader -- a threat that did not come, a piece "
    "left loose, a free move gained -- and never tell the reader what "
    "they should have played instead of a move they did not make.\n"
    "- The facts say \"the mover's\" and \"the waiting side's\" rather "
    "than you and them. Turn those into the right pronouns for the "
    "reader.\n"
    + _COMMON
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
    mover_is_user: bool = True,
    severity: Optional[str] = None,
    threat: Optional[Any] = None,
    punishment_line: Optional[List[str]] = None,
    opp_reply_is_clear: Optional[bool] = None,
    best_is_only_move: Optional[bool] = None,
    reader: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """The fact bundle handed to the model. Engine output only.

    No evaluations and no centipawns: they are not teachable and the model
    turns them into "you lost 4.4 pawns", which this repo has a commit hook
    against.
    """
    who = "you_played" if mover_is_user else "your_opponent_played"
    # A PLAN card has no better move -- the move was fine, it set something
    # up. Filing its facts under "what the better move achieves" would ask
    # the model to write about an alternative that does not exist, so the
    # key says what the facts actually are.
    if best_san:
        slot = ("what_the_better_move_achieves" if mover_is_user
                else "what_your_opponent_could_have_done_instead")
    else:
        slot = ("what_your_move_sets_up" if mover_is_user
                else "what_their_move_sets_up")
    facts: Dict[str, Any] = {
        who: played_san,
        "mover": "you" if mover_is_user else "your opponent",
        slot: [
            {"kind": p["kind"], "importance": p["tier"],
             "detail": p["proof"], "lesson": p.get("lesson", "")}
            for p in (purposes or [])
        ],
    }
    if best_san:
        facts["better_move"] = best_san
    elif str(severity or "").lower() not in _BAD_MOVE:
        # Not knowing a better move is NOT the same as the move being
        # good. A derived opponent record carries a cp_loss but no
        # best_move, and keying "fine" off the missing best move alone
        # would hand the model a false fact about a move that dropped a
        # rook -- the one thing the engine must never do. When the move
        # IS bad we simply say nothing here; `how_bad` carries the truth.
        facts["this_move_was_fine"] = True
    if severity:
        facts["how_bad"] = severity
    if threat:
        # A VALIDATED threat from move_purposes.threat_check -- what the
        # reply wins, not merely what the reply is. A bare SAN used to land
        # here straight from stockfish_service.get_threat, which returns the
        # opponent's best reply and nothing more, and 79.6% of those replies
        # threaten nothing at all. Under this key the model read every one
        # of them as a threat, correctly, because the key said so.
        facts["they_were_threatening"] = threat
    if punishment_line:
        facts["what_happens_after_your_move"] = list(punishment_line)[:6]
    if opp_reply_is_clear is not None:
        # The field that separates "they win your rook" from "they might".
        facts["their_best_reply_is_clearly_best"] = bool(opp_reply_is_clear)
    if best_is_only_move is not None:
        facts["the_better_move_was_the_only_good_one"] = bool(best_is_only_move)
    if reader:
        # What the coach knows about the PLAYER, from services/reader_context.
        # The arrow already shows what happened; this is how long they took
        # over it, whether the weakness is live or fading, and whether they
        # have trained the pattern. Measured first: time is on 69.4% of
        # moves, and the median blunder of 200cp+ took SEVEN seconds.
        #
        # Never a count of past mistakes. The product does not show a
        # failure scoreboard, so the decay service's own words -- active,
        # declining, fading -- are what travel.
        facts["about_this_player"] = dict(reader)
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
            or facts.get("what_your_opponent_could_have_done_instead")
            or facts.get("what_your_move_sets_up")
            or facts.get("what_their_move_sets_up")):
        # A PROVEN PURPOSE, or nothing. A line of moves and a threat the
        # engine never verified are not a licence to explain a mistake.
        #
        # This gate used to accept `they_were_threatening` or
        # `what_happens_after_your_move` on their own, and three cards from
        # Mohit's five review games show what that produced. Each fired no
        # purpose at all, so the model was handed a move list and asked why
        # a move was bad, and it did the only thing left: read causality
        # off the line.
        #
        #   "your d6 didn't stop their knight from moving to f3"
        #   "castling was an inaccuracy because it let your opponent play
        #    Bg5"
        #
        # Nf3 and Bg5 are simply the first move of the stored line. Neither
        # is a threat, and d6 cannot stop a knight going to f3. The English
        # is right; the chess was invented because the engine gave nothing
        # else. That is the one thing this layer may never do.
        #
        # Refusing is not silence: the caller keeps its deterministic
        # caption, which says less but says nothing false. The way to get
        # an LLM caption on these cards is to give the engine a purpose
        # that fires on them.
        out["refused"] = "no proven purpose"
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

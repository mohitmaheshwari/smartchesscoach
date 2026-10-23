"""The home card's title and teaching line for a game, written by a model from
facts the engine and board already proved.

Mohit, 2026-10-23, on a card titled "You were the steadier player in that
one." for a game his opponent let him win twice: "on home page the tags should
generate the title for the game with LLM ... the title is wrong ... he was not
steadier, the player [opponent] was weak, so we should write accordingly", and
"the game should give a more broad teaching".

The old title compared each side's average mistake size. It was true and said
the wrong thing: the opponent's blunders made the player look steady, when the
real lesson was that a stronger opponent would have punished two of his moves.

The boundary is the one services/caption_polish.py set (Mohit, 2026-10-21:
"LLM should never reason on chess position"):
  - the model is given English sentences we already verified -- story lines,
    the lesson, plain facts about the result, the opponent's mistakes and the
    rating gap -- and never a board;
  - its output is UNTRUSTED. `validate` rejects any move or square that was not
    in its input, any number, any piece or mate it was not told about, a result
    that contradicts the game, and empty praise. A rejection ships the
    rule-written headline instead, never an unchecked one.

Written once per game and cached in `game_headlines`, keyed by a hash of the
facts, so the model runs again only when the facts change.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)

# v2, 2026-10-23: Mohit -- "the story from each game and tags and everything
# from move observations should go to LLM and LLM should give you a title of
# the game without naming the moves". The facts now carry the tags and the
# patterns seen in the moves, and neither the title nor the teaching may name
# a move or a square.
HEADLINE_VERSION = "game_headline.v2"
COLLECTION = "game_headlines"
MODEL = os.environ.get("GAME_HEADLINE_MODEL") or os.environ.get("CAPTION_POLISH_MODEL") or "gpt-6-luna"
EFFORT = os.environ.get("GAME_HEADLINE_EFFORT", "low")
ENABLED = os.environ.get("GAME_HEADLINE_LLM_ENABLED", "1") == "1"

TITLE_WORDS = (3, 10)
TEACHING_WORDS = (8, 40)

_TOKEN = re.compile(r"\b(?:O-O(?:-O)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)")
_PIECES = ("queen", "rook", "knight", "bishop", "king", "pawn")
# Praise the facts never contain. The old title's "steadier" is here on purpose.
_EMPTY_PRAISE = ("brilliant", "flawless", "masterpiece", "genius", "crushed", "crushing",
                 "dominated", "dominant", "steadier", "steady", "outplayed")

SYSTEM = (
    "You give a chess student's finished game its title and one teaching line.\n"
    "You are given FACTS that are already verified: the main point, the result, the "
    "game's story, its tags, and the patterns seen in the student's moves. You are NOT "
    "given the board and must NOT reason about chess.\n"
    "THE TITLE:\n"
    "- Three to ten words, sentence case.\n"
    "- Names the game the way a coach would remember it: what happened and what decided "
    "it, from the student's side. It is not advice.\n"
    "- When a MAIN POINT is given, the title says that point.\n"
    "- Prefer a pattern the facts show more than once, or the one that decided the game, "
    "over a single moment.\n"
    "- Never name a move or a square. Never use a number.\n"
    "THE TEACHING:\n"
    "- One or two short sentences, at most thirty-five words, speaking to the student as "
    "'you'.\n"
    "- Broad: what this game teaches for the next games. Never name a move or a square.\n"
    "- Be honest about the opponent. If they missed chances or made big mistakes, say the "
    "result came partly from that, and what a stronger opponent would do.\n"
    "BOTH:\n"
    "- Use only the facts. Never add a piece, pattern or event the facts do not mention.\n"
    "- Never praise without a fact behind it.\n"
    "- Very simple English for a 600 to 1500 player who may read English as a second "
    "language. Short sentences, common words. No numbers.\n"
    "- Do not copy the game's story label; it is shown separately.\n"
    'Reply with JSON only: {"title": "...", "teaching": "..."}'
)

# Pattern words the model may only use when a fact names them.
_PATTERN_WORDS = ("fork", "pin", "skewer", "sacrifice", "castle", "castled", "castling",
                  "endgame", "opening", "time")


def _count_words(n: int) -> str:
    return {0: "never", 1: "once", 2: "twice"}.get(n, "more than twice")


def main_point(story: Mapping[str, Any]) -> Optional[str]:
    """What the game was about, decided by rules from the ledger and plan.

    The model chose its own emphasis at first, and on Mohit's game wrote "You
    won when your opponent resigned" on one run and "You won after your
    opponent missed chances" on another. The second is the point he asked
    for. So the point is decided here and the model only puts it in words.
    """
    plan = story.get("plan") or {}
    ledger = story.get("ledger") or {}
    events = ledger.get("events") or []
    outcome = ledger.get("outcome")
    kind = (plan.get("type") or {}).get("id")
    let_off = any(e.get("kind") == "your_mistake" and e.get("decisive") and e.get("punished") is False
                  for e in events)
    punished_against = any(e.get("kind") == "your_mistake" and e.get("decisive") and e.get("punished")
                           for e in events)
    made_them_pay = any(e.get("kind") == "their_mistake" and e.get("decisive") and e.get("taken")
                        for e in events)
    if outcome == "win" and let_off:
        return ("the student won partly because the opponent missed the chances the student "
                "gave them")
    if outcome == "win" and kind == "came_back":
        return "the student was worse and came back to win"
    if outcome == "win" and made_them_pay:
        return "the student won by making the opponent pay for their mistakes"
    if outcome == "win" and kind == "clean_win":
        return "the student kept control and won without real trouble"
    if outcome == "loss" and kind == "slipped_away":
        return "the student had a winning position and lost it"
    if outcome == "loss" and punished_against:
        return "the opponent punished the student's big mistakes"
    if outcome == "loss" and kind == "hard_game":
        return "the opponent was better for most of the game"
    if outcome == "draw" and kind == "great_escape":
        return "the student saved a bad position"
    if outcome == "draw" and kind == "slipped_away":
        return "the student had a winning position and it became a draw"
    return None


def headline_facts(story: Mapping[str, Any], game: Mapping[str, Any],
                   observations: Optional[List[Mapping[str, Any]]] = None) -> List[str]:
    """Plain English facts, every one taken from the ledger, plan or tags."""
    plan = story.get("plan") or {}
    ledger = story.get("ledger") or {}
    tags = set((story.get("tags") or {}).get("ids") or [])
    events = ledger.get("events") or []
    facts: List[str] = []

    outcome = ledger.get("outcome")
    term = str(game.get("termination") or "")
    how = {"resignation": "by resignation", "checkmate": "by checkmate", "timeout": "on time",
           "abandonment": "when the other player left", "repetition": "by repetition",
           "stalemate": "by stalemate", "insufficient": "with too few pieces left to mate",
           "draw_agreement": "by agreement"}.get(term, "")
    if outcome == "win":
        facts.append(f"The student won {how}.".replace("  ", " ").replace(" .", "."))
    elif outcome == "loss":
        facts.append(f"The student lost {how}.".replace("  ", " ").replace(" .", "."))
    elif outcome == "draw":
        facts.append(f"The game was a draw {how}.".replace("  ", " ").replace(" .", "."))

    point = main_point(story)
    if point:
        facts.append(f"MAIN POINT: {point}.")
    if (plan.get("type") or {}).get("title"):
        facts.append(f"The game's story: {plan['type']['title']}.")

    let_off = sum(1 for e in events if e.get("kind") == "your_mistake"
                  and e.get("decisive") and e.get("punished") is False)
    punished_against = sum(1 for e in events if e.get("kind") == "your_mistake"
                           and e.get("decisive") and e.get("punished") is True)
    their_big = sum(1 for e in events if e.get("kind") == "their_mistake" and e.get("decisive"))
    taken = sum(1 for e in events if e.get("kind") == "their_mistake"
                and e.get("decisive") and e.get("taken"))
    if let_off:
        # "Decisive" is severity's decisiveness_changed: a WINNING position
        # was given up. Say exactly that, not "winning or level".
        facts.append(f"The student gave away a winning position {_count_words(let_off)}, "
                     "and the opponent did not punish it.")
    if punished_against:
        facts.append(f"The opponent punished the student's big mistakes {_count_words(punished_against)}.")
    if their_big:
        paid = (f"the student made them pay {_count_words(taken)}" if taken
                else "the student did not make them pay")
        facts.append(f"The opponent made big mistakes {_count_words(their_big)}; {paid}.")
    if "user_beat_higher_rated" in tags:
        facts.append("The opponent was rated clearly higher than the student.")
    if "user_lost_to_lower_rated" in tags:
        facts.append("The opponent was rated clearly lower than the student.")
    if "user_in_time_scramble" in tags:
        facts.append("The student ran very low on time.")

    # The whole story, chapter by chapter.
    for chapter in plan.get("chapters") or []:
        for line in chapter.get("lines") or []:
            if line.get("text"):
                facts.append(f"Story, {str(chapter.get('title') or '').lower()}: {line['text']}")
    if (plan.get("lesson") or {}).get("text"):
        facts.append("Lesson from the moves: " + plan["lesson"]["text"])

    tag_words = tag_phrases(tags)
    if tag_words:
        facts.append("Tags: " + "; ".join(tag_words) + ".")
    facts.extend(observation_facts(observations or []))
    return facts


# Tags already said another way above, or not about how the game went.
_TAG_SKIP = re.compile(r"^(result_|story_|opening_(?!played|came)|user_(let_off|lost_winning_position|"
                       r"beat_higher_rated|lost_to_lower_rated|in_time_scramble)$)")


def tag_phrases(tags) -> List[str]:
    """The game's tags as short phrases: user_never_castled -> never castled."""
    out = []
    for tag in sorted(tags or ()):
        if _TAG_SKIP.match(tag):
            continue
        phrase = re.sub(r"^user_", "", tag).replace("_", " ")
        phrase = phrase.replace(" opponent missed", ", and the opponent missed it") \
                       .replace(" opponent punished", ", and the opponent punished it")
        out.append(phrase)
    return out


# A few catalogue names read as an achievement out of context.
_MISTAKE_NAME = {"missed_mate": "Missed a forced mate"}


def _allowed(quality_id: str) -> bool:
    try:
        from services.detector_quality import QualitySurface, is_authorized

        return is_authorized(quality_id, QualitySurface.CAPTION)
    except Exception:
        return False


def observation_facts(observations: List[Mapping[str, Any]]) -> List[str]:
    """What the move observations show, as counted patterns -- never a move.

    Mistakes appear only under a name the quality gate allows a player to
    see; a shadow-graded detector's claim is never handed to the model.
    """
    from collections import Counter, defaultdict

    try:
        from services.pattern_catalog import get_pattern
    except Exception:
        get_pattern = lambda _id: None  # noqa: E731
    phases = defaultdict(list)
    good = Counter()
    for o in observations:
        subtype, pattern = o.get("subtype"), o.get("missed_pattern")
        if subtype and pattern and _allowed(f"gap:{pattern}:{subtype}"):
            name = _MISTAKE_NAME.get(subtype) or (get_pattern(subtype) or {}).get("human_name")
            if name:
                phases[name].append(o.get("phase"))
        for flag, label in (("found_best_in_critical", "Found the best move in a sharp moment"),
                            ("punished_opponent_blunder", "Punished an opponent's mistake"),
                            ("responded_to_threat", "Answered a threat")):
            if o.get(flag) is True:
                good[label] += 1
    facts = []
    for name, seen in sorted(phases.items(), key=lambda kv: -len(kv[1])):
        where = Counter(p for p in seen if p).most_common(1)
        tail = f", mostly in the {where[0][0]}" if where else ""
        facts.append(f"Pattern in the student's mistakes: {name.rstrip('.')}, {_count_words(len(seen))}{tail}.")
    for label, n in good.most_common():
        facts.append(f"Pattern in the student's good moves: {label}, {_count_words(n)}.")
    return facts


def facts_key(facts: List[str]) -> str:
    return hashlib.sha256(("\n".join(facts) + HEADLINE_VERSION).encode()).hexdigest()[:24]


def validate(facts: List[str], title: str, teaching: str, outcome: Optional[str]) -> Optional[str]:
    """Why the model's headline must be refused, or None when it may ship."""
    source = " ".join(facts)
    low_source = source.lower()
    title = (title or "").strip()
    teaching = (teaching or "").strip()
    if not title or not teaching:
        return "empty"
    tw, sw = len(title.split()), len(teaching.split())
    if not TITLE_WORDS[0] <= tw <= TITLE_WORDS[1]:
        return "title length"
    if not TEACHING_WORDS[0] <= sw <= TEACHING_WORDS[1]:
        return "teaching length"
    both = f"{title} {teaching}"
    # No move and no square anywhere (Mohit, 2026-10-23: "without naming
    # the moves"). The story lines below the headline carry the moves.
    named = sorted(set(_TOKEN.findall(both)))
    if named:
        return f"named a move: {named}"
    if re.search(r"\d", both):
        return "a number"
    low = both.lower()
    for word in _PIECES + ("mate", "checkmate", "trap", "trapped") + _PATTERN_WORDS:
        # "mate" is covered by "checkmate" in the facts, so the source check
        # is a plain substring, not a word match.
        covered = word in low_source or (word == "king" and "mate" in low_source)
        if re.search(rf"\b{word}s?\b", low) and not covered:
            return f"not in the facts: {word}"
    for word in _EMPTY_PRAISE:
        if re.search(rf"\b{word}\b", low):
            return f"empty praise: {word}"
    low_title = title.lower()
    if outcome == "loss" and re.search(r"\b(won|win|victory|beat)\b", low_title):
        return "title contradicts the result"
    if outcome == "win" and re.search(r"\b(lost|loss|defeat)\b", low_title):
        return "title contradicts the result"
    return None


def fallback_headline(story: Mapping[str, Any]) -> Dict[str, str]:
    """Rule-written title and teaching from the plan, when the model is off,
    down, or rejected."""
    plan = story.get("plan") or {}
    ledger = story.get("ledger") or {}
    events = ledger.get("events") or []
    outcome = ledger.get("outcome")
    title = (plan.get("type") or {}).get("title") or "Your game"
    let_off = any(e.get("kind") == "your_mistake" and e.get("decisive") and e.get("punished") is False
                  for e in events)
    if outcome == "win" and let_off:
        teaching = ("You won, but your opponent missed chances that a stronger player would take. "
                    "Before you move, look for their best reply.")
    elif (plan.get("lesson") or {}).get("text"):
        teaching = plan["lesson"]["text"]
    elif outcome == "loss":
        teaching = "Look at the moments where the game turned, and what you would play now."
    else:
        teaching = "Look at the moments that decided the game."
    return {"title": title, "teaching": teaching}


def sentence_case(title: str, facts: List[str]) -> str:
    """The model mixes "They Punished Your Big Mistakes" with sentence case.
    Keep the first word's capital, moves, and any word the facts themselves
    capitalise mid-sentence (opening names); lower the rest."""
    source = " ".join(facts)
    words = title.split()
    out = []
    for i, word in enumerate(words):
        core = word.strip(".,;:!?\"'’")
        keep = (i == 0 or _TOKEN.fullmatch(core) is not None
                or (core[:1].isupper() and re.search(rf"(?<![.:] )\b{re.escape(core)}\b", source)
                    and not re.search(rf"(?:^|[.:] ){re.escape(core)}\b", source)))
        out.append(word if keep else word.lower())
    return " ".join(out)


async def write_headline(facts: List[str], outcome: Optional[str]) -> Dict[str, Any]:
    """Ask the model; return its headline only if it passes `validate`."""
    out: Dict[str, Any] = {"ok": False, "reason": "", "model": MODEL}
    if not ENABLED:
        out["reason"] = "disabled"
        return out
    try:
        from llm_service import call_llm
        said = await call_llm(SYSTEM, "FACTS:\n- " + "\n- ".join(facts), model=MODEL,
                              max_tokens=2000, reasoning_effort=EFFORT)
    except Exception as exc:                      # noqa: BLE001
        logger.warning("[game_headline] %s unavailable: %r", MODEL, exc)
        out["reason"] = "llm_error"
        return out
    text = (said or "").strip()
    match = re.search(r"\{.*\}", text, re.S)
    try:
        parsed = json.loads(match.group(0)) if match else {}
    except ValueError:
        parsed = {}
    title = str(parsed.get("title") or "").strip().strip('"')
    teaching = str(parsed.get("teaching") or "").strip().strip('"')
    problem = validate(facts, title, teaching, outcome)
    if problem:
        logger.info("[game_headline] rejected (%s): %r / %r", problem, title[:60], teaching[:80])
        out["reason"] = problem
        return out
    out.update(ok=True, title=sentence_case(title, facts), teaching=teaching)
    return out


async def headline_for_game(db, game: Mapping[str, Any], story: Mapping[str, Any]) -> Dict[str, Any]:
    """The card's title and teaching: cached, model-written when it passes,
    rule-written otherwise. Never raises."""
    try:
        observations = await db["move_observations"].find(
            {"game_id": game.get("game_id")},
            {"_id": 0, "subtype": 1, "missed_pattern": 1, "phase": 1,
             "found_best_in_critical": 1, "punished_opponent_blunder": 1,
             "responded_to_threat": 1},
        ).to_list(length=None)
        facts = headline_facts(story, game, observations)
        key = facts_key(facts)
        game_id = game.get("game_id")
        cached = await db[COLLECTION].find_one({"game_id": game_id, "facts_key": key}, {"_id": 0})
        if cached:
            return cached
        outcome = (story.get("ledger") or {}).get("outcome")
        written = await write_headline(facts, outcome)
        if written.get("ok"):
            doc = {"title": written["title"], "teaching": written["teaching"], "source": "llm",
                   "model": written["model"]}
        else:
            doc = {**fallback_headline(story), "source": "rules", "reason": written.get("reason")}
        doc.update(game_id=game_id, facts_key=key, version=HEADLINE_VERSION,
                   created_at=datetime.now(timezone.utc))
        # Cache a model headline for good. A rules fallback caused by the
        # model being down is retried later rather than kept.
        if doc["source"] == "llm" or written.get("reason") not in ("llm_error",):
            await db[COLLECTION].update_one({"game_id": game_id}, {"$set": doc}, upsert=True)
        return doc
    except Exception:
        logger.warning("game headline failed", exc_info=True)
        return {**fallback_headline(story), "source": "rules", "reason": "error"}

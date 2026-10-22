"""The story plan and its words: which events to tell, under what title, and how.

docs/game_story_by_phase_scope.md (v2), steps 3 and 4. Reads only the ledger
(`services.game_ledger`) and the names the detector gate allows; it claims
nothing the ledger does not hold. Rules write every word -- no language model.

The English is for a 600 to 1500 player who may be reading in a second
language: short sentences, common words, no numbers. A move such as Kg3 is the
only place a digit may appear, because it is how a line is located.

Every verb is checked against the evidence before it is used. The first
mockup of this story said Nh3+ "took" a loose piece, and Nh3+ is a check that
takes nothing. So "took" and "won" are only used where the ledger shows a
capture or a material gain, and "trapped" only where the board proved it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PLAN_VERSION = "game_story_plan.v1"

MAX_EVENTS = 6        # three to six moments, from the scope
MIN_EVENTS = 3

WINNING = 300         # clearly better, player's side, centipawns
LEVEL = 150

# Opening verdict. "Perfect" only when every opening move was the engine's
# choice (Mohit, 2026-10-22). "Well" when no opening move cost much and the
# position is not worse. Measured over 1,000 games, every move was the
# engine's choice in 4.
_OPENING_COSTLY = 100
_OPENING_SMALL = 50


# ─── Story type ─────────────────────────────────────────────────────────


def _lead_changes(curve: Sequence[int]) -> int:
    side, changes = 0, 0
    for v in curve:
        now = 1 if v >= WINNING else -1 if v <= -WINNING else 0
        if now and side and now != side:
            changes += 1
        if now:
            side = now
    return changes


def story_type(ledger: Mapping[str, Any]) -> Dict[str, str]:
    """One type per game, chosen only when the curve and the events earn it."""
    curve = list(ledger.get("curve") or [])
    outcome = ledger.get("outcome")
    events = ledger.get("events") or []
    hi = max(curve) if curve else 0
    lo = min(curve) if curve else 0
    escapes = [e for e in events
               if e.get("kind") == "your_mistake" and e.get("decisive") and e.get("punished") is False]
    if outcome == "win" and escapes:
        if len(escapes) == 1:
            return {"id": "narrow_escape", "title": "A win with a narrow escape"}
        return {"id": "narrow_escapes", "title": "A win with narrow escapes"}
    if outcome == "win" and lo <= -WINNING:
        return {"id": "came_back", "title": "You came back"}
    if _lead_changes(curve) >= 2:
        return {"id": "up_and_down", "title": "Up and down"}
    if outcome in ("loss", "draw") and hi >= WINNING:
        return {"id": "slipped_away", "title": "It slipped away"}
    if outcome == "draw" and lo <= -WINNING:
        return {"id": "great_escape", "title": "A great escape"}
    if outcome == "win" and lo > -LEVEL:
        return {"id": "clean_win", "title": "A clean win"}
    if outcome == "loss" and hi < LEVEL:
        return {"id": "hard_game", "title": "A hard game"}
    return {"id": "game", "title": {"win": "Your win", "loss": "Your loss",
                                    "draw": "A draw"}.get(str(outcome), "Your game")}


# ─── Choosing events ────────────────────────────────────────────────────


def _score(event: Mapping[str, Any]) -> int:
    kind = event.get("kind")
    if kind == "your_mistake":
        score = 5 if event.get("decisive") else {"blunder": 3, "serious": 3}.get(event.get("tier"), 2)
        if (event.get("danger") or {}).get("kind") in (
                "queen_trapped", "queen_lost", "mate_allowed", "rook_trapped"):
            score += 1
        if event.get("punished") is False:
            score += 1
        return score
    if kind == "missed_mate":
        return 4
    if kind == "their_mistake":
        return 3 if event.get("decisive") else 1
    if kind == "your_good_move":
        return {"found_best_in_critical": 3}.get(event.get("label"), 2)
    if kind == "you_boxed_in":
        return 4 if event.get("won_it") else 3
    return 0


def _merge_punishments(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Their mistake you took and your move that took it are one moment."""
    merged, skip = [], set()
    for i, e in enumerate(events):
        if i in skip:
            continue
        if e.get("kind") == "their_mistake" and e.get("taken") and i + 1 < len(events):
            nxt = events[i + 1]
            if nxt.get("kind") == "your_good_move" and nxt.get("san") == e.get("your_answer"):
                skip.add(i + 1)
        merged.append(e)
    return merged


def choose_events(ledger: Mapping[str, Any], *, fold: bool = True) -> List[Dict[str, Any]]:
    """Three to six events, in game order, with at least one good one when
    the player did something good. `fold=False` keeps a missed chance that
    the story tells as part of the next line, for the coach notes."""
    events = _merge_punishments([dict(e) for e in ledger.get("events") or []])
    order = {id(e): i for i, e in enumerate(events)}
    ranked = sorted(events, key=lambda e: (_score(e), -order[id(e)]), reverse=True)
    chosen = [e for e in ranked if _score(e) >= 2][:MAX_EVENTS]
    if len(chosen) < MIN_EVENTS:
        chosen = ranked[:MIN_EVENTS]

    def good(e):
        return e.get("kind") in ("your_good_move", "you_boxed_in") or (
            e.get("kind") == "their_mistake" and e.get("taken"))

    if not any(good(e) for e in chosen):
        best_good = next((e for e in ranked if good(e)), None)
        if best_good is not None:
            chosen = (chosen[:-1] if len(chosen) >= MAX_EVENTS else chosen) + [best_good]
    chosen.sort(key=lambda e: order[id(e)])
    return _fold_missed_chances(chosen) if fold else chosen


def _fold_missed_chances(chosen: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Their mistake you missed, answered by a mistake of yours already in the
    story, is told once. Game 56b6c294 read "They went wrong with h4. Bxc3
    would have punished it, but you played Nxg5." and then a line about Nxg5
    itself. The coach notes still carry the missed chance."""
    kept = []
    for i, e in enumerate(chosen):
        nxt = chosen[i + 1] if i + 1 < len(chosen) else None
        if (e.get("kind") == "their_mistake" and e.get("taken") is False and nxt
                and nxt.get("kind") == "your_mistake" and nxt.get("san") == e.get("your_answer")):
            continue
        kept.append(e)
    return kept


# ─── Words ──────────────────────────────────────────────────────────────


def _named(event, names: Mapping[Tuple[Any, Any], str]) -> Optional[str]:
    if event.get("side") != "you":
        return None
    return names.get((event.get("move_number"), event.get("san")))


def _mistake_text(e: Mapping[str, Any], name: Optional[str]) -> str:
    san = e["san"]
    danger = e.get("danger") or {}
    reply = danger.get("reply")
    their = (e.get("evidence") or {}).get("their_reply")
    let_off = e.get("punished") is False
    found_it = bool(reply) and their == reply
    kind = danger.get("kind")

    if kind == "queen_trapped":
        if let_off:
            return (f"{san} nearly cost you your queen. After {reply}, she would have "
                    f"had no safe square. They played {their} instead.")
        if found_it:
            return f"{san} let {reply} trap your queen, and they found it."
        return f"{san} was a big mistake. {reply} would have trapped your queen."
    if kind == "queen_lost":
        if let_off:
            return (f"{san} could have cost you your queen. {reply} would have won it. "
                    f"They played {their} instead.")
        if found_it:
            return f"{san} let them win your queen with {reply}."
        return f"{san} was a big mistake. {reply} would have won your queen."
    if kind == "rook_trapped":
        if let_off:
            return (f"{san} nearly cost you a rook. After {reply}, it would have had "
                    f"no safe square. They played {their} instead.")
        if found_it:
            return f"{san} let {reply} trap your rook, and they found it."
        return f"{san} was a big mistake. {reply} would have trapped your rook."
    if kind == "mate_allowed":
        if let_off:
            return f"{san} allowed a forced mate. They missed it and played {their}."
        if found_it:
            return f"{san} allowed a forced mate, and they found it with {reply}."
        return f"{san} allowed a forced mate."

    if name:
        lead = f"{san}: {name.rstrip('.')}."
        if let_off:
            return f"{lead} They did not punish it."
        return lead
    if let_off:
        if e.get("decisive") and reply and their:
            return f"{san} gave them a big chance. {reply} was strong for them, but they played {their}."
        return f"{san} gave something away. They did not take it."
    if found_it:
        # "Found the best reply", not "punished": on real games the reply was
        # often a quiet move such as Kg7, and "punished it with Kg7" reads as
        # an attack that did not happen.
        return f"{san} was a mistake, and they found the best reply, {reply}."
    # "Decisive" means the move took the player out of a winning position
    # (severity.classify_severity_practical), so only then is the win gone.
    # A punished mistake in a still-winning position is only "a mistake".
    if e.get("decisive"):
        return f"{san} was a mistake, and your winning position was gone."
    return f"{san} was a mistake."


def event_text(e: Mapping[str, Any], names: Mapping[Tuple[Any, Any], str]) -> str:
    kind = e.get("kind")
    san = e.get("san")
    if kind == "your_mistake":
        return _mistake_text(e, _named(e, names))
    if kind == "missed_mate":
        best = (e.get("evidence") or {}).get("best")
        if best:
            return f"{best} would have started a forced mate. You played {san} instead."
        return f"You had a forced mate here and played {san} instead."
    if kind == "their_mistake":
        answer = e.get("your_answer")
        if e.get("taken") and answer:
            # The ledger proves the answer kept the advantage, not that it
            # attacked anything: Bf1 blocking a check counts.
            return f"They went wrong with {san}, and you found a good answer: {answer}."
        best = (e.get("evidence") or {}).get("your_best")
        if best and answer and best != answer:
            return f"They went wrong with {san}. {best} would have punished it, but you played {answer}."
        return f"They went wrong with {san}."
    if kind == "your_good_move":
        name = _named(e, names)
        if name:
            return f"{san}: {name.rstrip('.')}."
        if e.get("label") == "found_best_in_critical":
            return f"{san} was the best move in a sharp moment."
        return f"{san} was a strong move."
    if kind == "you_boxed_in":
        # Only ledger-proved claims: your move shut it in, it had almost no
        # safe square for a long stretch, and either you won it or your
        # position clearly improved while it was stuck.
        piece, square = e.get("piece"), e.get("square")
        if e.get("won_it"):
            # No square here: a boxed-in piece can still step to its one safe
            # square, so where it was shut in is not where it was taken.
            return (f"{san} shut their {piece} in. It found no way out, "
                    f"and you won it with {e['won_it']}.")
        return (f"{san} shut their {piece} on {square} in. It had almost nowhere to go "
                f"for a long time, and your position got better.")
    return str(san or "")


def _polarity(e: Mapping[str, Any]) -> str:
    kind = e.get("kind")
    if kind in ("your_good_move", "you_boxed_in") or (kind == "their_mistake" and e.get("taken")):
        return "positive"
    if kind == "their_mistake":
        return "neutral"
    return "negative"


def _line(e: Mapping[str, Any], names) -> Dict[str, Any]:
    return {
        "kind": e.get("kind"),
        "side": e.get("side"),
        "san": e.get("san"),
        "move_number": e.get("move_number"),
        "polarity": _polarity(e),
        "text": event_text(e, names),
        "fen_before": e.get("fen_before"),
        "uci": e.get("uci"),
    }


def _the(name: str) -> str:
    return name if name.lower().startswith("the ") else f"the {name}"


def opening_verdict(opening: Mapping[str, Any]) -> str:
    """perfect / well / better / worse / level. The one rule the story line
    and the game tags both read, so they cannot disagree."""
    costliest = opening.get("costliest") or {}
    cost = int(costliest.get("cp_loss") or 0)
    end = opening.get("eval_at_end")
    if opening.get("every_move_engine_best") and opening.get("name"):
        return "perfect"
    if cost < _OPENING_SMALL and end is not None and end >= -_OPENING_SMALL:
        return "well"
    if end is not None and end >= 100:
        return "better"
    if end is not None and end <= -100:
        return "worse"
    return "level"


def opening_lines(opening: Mapping[str, Any]) -> List[Dict[str, Any]]:
    name = opening.get("name")
    if not name or name == "Other":
        label = "the opening"
    else:
        label = _the(name)
    costliest = opening.get("costliest") or {}
    cost = int(costliest.get("cp_loss") or 0)
    verdict = opening_verdict(opening)
    lines = [{
        "perfect": f"You played {label} perfectly. Every move was the engine's choice.",
        "well": f"You played {label} well.",
        "better": f"You came out of {label} with the better position.",
        "worse": f"You came out of {label} worse.",
        "level": f"{label[0].upper()}{label[1:]} gave a level position.",
    }[verdict]]
    if cost >= _OPENING_COSTLY and costliest.get("san") and costliest.get("best") \
            and costliest.get("best") != costliest.get("san"):
        lines.append(f"{costliest['san']} was the costly move. {costliest['best']} was better.")
    return [{"kind": "opening", "side": "you", "san": None, "polarity": "neutral", "text": t}
            for t in lines]


_ENDINGS = {
    "win": {"resignation": "they resigned", "timeout": "they ran out of time",
            "checkmate": "you finished with checkmate", "abandonment": "they left the game"},
    "loss": {"resignation": "You resigned.", "timeout": "You ran out of time.",
             "checkmate": "You were checkmated.", "abandonment": "The game was abandoned."},
}


def finish_lines(finish: Mapping[str, Any]) -> List[Dict[str, Any]]:
    outcome = finish.get("outcome")
    term = str(finish.get("termination") or "")
    final = finish.get("final_eval")
    if outcome == "win":
        how = _ENDINGS["win"].get(term, "you won")
        text = (f"From there you stayed well ahead, and {how}." if finish.get("kept_winning")
                else f"In the end {how}.")
    elif outcome == "loss":
        how = _ENDINGS["loss"].get(term, "You lost.")
        if finish.get("was_winning_and_did_not_win"):
            text = f"You were winning at one point, but could not hold it. {how}"
        elif final is not None and final <= -WINNING:
            text = f"By the end they were well ahead. {how}"
        else:
            text = how
    elif outcome == "draw":
        text = {"repetition": "The game was drawn by repetition.",
                "stalemate": "The game ended in stalemate.",
                "insufficient": "The game was drawn: neither side had enough pieces left to mate.",
                "draw_agreement": "You agreed a draw."}.get(term, "The game was drawn.")
    else:
        text = "The game ended."
    return [{"kind": "finish", "side": None, "san": None, "polarity": "neutral", "text": text}]


# ─── The lesson ─────────────────────────────────────────────────────────

# Only when at least two events share it (Mohit, 2026-10-22). Otherwise none,
# never a generic one. Checked in this order; the first that holds is used.
_LESSONS = (
    ("mate_danger",
     lambda e: e.get("kind") == "your_mistake" and (e.get("danger") or {}).get("kind") == "mate_allowed",
     "Before every move, look at the checks your opponent could give."),
    ("queen_danger",
     lambda e: e.get("kind") == "your_mistake"
     and (e.get("danger") or {}).get("kind") in ("queen_trapped", "queen_lost"),
     "Before you move, check that your queen still has a safe square."),
    ("missed_mates",
     lambda e: e.get("kind") == "missed_mate",
     "When you are attacking, look at every check first. More than one mate went by."),
    ("let_off",
     lambda e: e.get("kind") == "your_mistake" and e.get("punished") is False and e.get("decisive"),
     "Your opponent let you off more than once. A stronger player will not, so look "
     "for their best reply before you move."),
    ("missed_punishments",
     lambda e: e.get("kind") == "their_mistake" and e.get("taken") is False and e.get("decisive"),
     "They gave you chances you did not take. When they move, ask what their move left loose."),
)


def lesson(ledger: Mapping[str, Any]) -> Optional[Dict[str, str]]:
    events = ledger.get("events") or []
    for lesson_id, matches, text in _LESSONS:
        if sum(1 for e in events if matches(e)) >= 2:
            return {"id": lesson_id, "text": text}
    return None


# ─── The plan ───────────────────────────────────────────────────────────


def plan_story(
    ledger: Mapping[str, Any],
    *,
    names: Optional[Mapping[Tuple[Any, Any], str]] = None,
) -> Dict[str, Any]:
    """The whole story: a title, three chapters, a lesson, and coach notes.

    `names` maps (move number, move) to the English name the detector gate
    allows for that move, from the moment layer. A move with no allowed name
    is described from the ledger alone.
    """
    names = dict(names or {})
    opening = ledger.get("opening") or {}
    last_opening_move = opening.get("last_move") or 0
    chosen = choose_events(ledger)
    start_events = [e for e in chosen if (e.get("move_number") or 0) <= last_opening_move]
    middle_events = [e for e in chosen if (e.get("move_number") or 0) > last_opening_move]

    start = opening_lines(opening) + [_line(e, names) for e in start_events]
    middle = [_line(e, names) for e in middle_events]
    finish = finish_lines(ledger.get("finish") or {})
    the_lesson = lesson(ledger)

    chapters = [
        {"id": "start", "title": "The start", "lines": start},
        {"id": "middle", "title": "The middle", "lines": middle},
        {"id": "finish", "title": "The finish", "lines": finish},
    ]
    moments = [line for line in start + middle if line.get("san")]
    home = ([start[0]] if start else []) + _most_important(chosen, names)[:2]
    return {
        "version": PLAN_VERSION,
        "type": story_type(ledger),
        "chapters": [c for c in chapters if c["lines"]],
        "lesson": the_lesson,
        "coach_notes": [coach_note(e, names) for e in choose_events(ledger, fold=False)],
        "home_lines": home,
        "board_move": next((m for m in _most_important(chosen, names)
                            if m.get("side") == "you" and m.get("fen_before")), None),
        "moment_count": len(moments),
    }


def _most_important(chosen, names) -> List[Dict[str, Any]]:
    order = sorted(chosen, key=_score, reverse=True)
    return [_line(e, names) for e in order]


def coach_note(e: Mapping[str, Any], names) -> Dict[str, Any]:
    """The same event, as concrete study notes: what was played, what was best."""
    ev = e.get("evidence") or {}
    danger = e.get("danger") or {}
    parts: List[str] = []
    kind = e.get("kind")
    if kind == "your_mistake":
        if ev.get("best") and ev.get("best") != e.get("san"):
            parts.append(f"Best was {ev['best']}.")
        if danger.get("reply"):
            proof = {
                "queen_trapped": f"After {danger['reply']}, every square your queen could reach was covered.",
                "rook_trapped": f"After {danger['reply']}, every square your rook could reach was covered.",
                "queen_lost": f"{danger['reply']} wins your queen in the engine's line.",
                "mate_allowed": f"{danger['reply']} starts a forced mate.",
            }.get(danger.get("kind"), f"Their strongest reply was {danger['reply']}.")
            parts.append(proof)
        if ev.get("their_reply"):
            parts.append(f"They played {ev['their_reply']}.")
    elif kind == "missed_mate":
        if ev.get("best"):
            parts.append(f"{ev['best']} starts a forced mate.")
    elif kind == "their_mistake":
        if ev.get("their_best"):
            parts.append(f"Their best was {ev['their_best']}.")
        if ev.get("your_best") and ev.get("your_best") != e.get("your_answer"):
            parts.append(f"Your best answer was {ev['your_best']}.")
        if e.get("your_answer"):
            parts.append(f"You played {e['your_answer']}.")
    elif kind == "you_boxed_in":
        parts.append(f"After {e.get('san')}, their {e.get('piece')} on {e.get('square')} "
                     f"had almost no safe square for several moves.")
        if e.get("won_it"):
            parts.append(f"You won it with {e['won_it']}.")
    elif kind == "your_good_move":
        name = _named(e, names)
        parts.append(f"{name.rstrip('.')}." if name else "The engine's choice in a sharp moment."
                     if e.get("label") == "found_best_in_critical" else "A strong move.")
    return {"kind": kind, "side": e.get("side"), "san": e.get("san"),
            "move_number": e.get("move_number"), "polarity": _polarity(e),
            "text": " ".join(parts)}

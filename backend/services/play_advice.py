"""What to play, and how the last game went for the player as a person.

docs/home_behaviour_and_clock_scope.md (Mohit, 2026-11-17: "if you find more
games I lose on time ... you should recommend me not playing bullet or blitz
... that's the sort of coaching I am looking for"; Home "should also evaluate
your behavioural detectors ... how you react").

CLOCK ADVICE. One line, only when the evidence is plain. A time control is
named only when all of these hold, measured on the player's own games:
  1. it scores clearly below the clock he plays best, in both halves of his
     games at that clock (not a phase he has grown out of);
  2. most of its losses are on time (the clock explains it);
  3. where both clocks have analysed games, his mistake rate there is not
     clearly higher (so it is the clock, not his chess).
Bullet and other unanalysed games come from skipped_game_records; for them
gate 3 cannot be read and gates 1 and 2 decide.

BEHAVIOUR. One line about the last game, only when the moment happened in it:
he was winning and did not win, and/or one mistake brought another soon after.
Measured on Mohit's newest 20 games (2026-11-17): six of nine losses came from
a winning position; a second mistake followed a blunder in eleven of the
seventeen games with one. Speed after a blunder showed no pattern, so nothing
here talks about speed.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# Locked from the 2026-11-17 sweep over all 79 players (scope, section 6):
# gap 0.08/0.12/0.15 x share 0.4/0.5/0.6 flagged 11..4 players; 0.12 and 0.5
# ("mostly on the clock" means half the losses or more) flag 7.
MIN_GAMES = 20          # per clock, both the one named and the one suggested
SCORE_GAP = 0.12        # below the best clock by this much, in both halves
TIME_SHARE = 0.5        # at least half its losses on time
SLIP_RATIO = 1.25       # mistake rate there at most this times the suggested clock's
MIN_ANALYSED = 10       # analysed games each side before gate 3 is read
SLIP_CP = 200
LEVEL_CP = 300

WINNING_CP = 300        # "you were winning": his side at least three pawns up
FOLLOW_MOVES = 5        # "soon after": within his next five moves

_TC = re.compile(r'\[TimeControl "(\d+)\+(\d+)"\]')


def clock_name(base: int, inc: int) -> str:
    minutes = {15: "¼", 30: "½", 45: "¾"}.get(base)
    if minutes is None:
        minutes = str(base // 60) if base % 60 == 0 else str(round(base / 60, 1))
    return f"{minutes}+{inc}"


def _outcome(result: Any, colour: Any) -> Optional[str]:
    r = str(result or "")
    if r in ("1/2-1/2", "½-½"):
        return "draw"
    if r in ("1-0", "0-1") and colour in ("white", "black"):
        return "win" if (r == "1-0") == (colour == "white") else "loss"
    return None


def clock_rows(games: Iterable[Mapping[str, Any]], skipped: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """One row per finished game with a base+increment clock, both sources."""
    rows: List[Dict[str, Any]] = []
    for g in games:
        m = _TC.search(str(g.get("pgn") or ""))
        out = _outcome(g.get("result"), g.get("user_color")) or g.get("game_outcome")
        if not m or out not in ("win", "loss", "draw"):
            continue
        rows.append({"clock": (int(m.group(1)), int(m.group(2))), "out": out,
                     "on_time": "time" in str(g.get("termination") or "").lower(),
                     "at": g.get("played_at_utc"), "game_id": g.get("game_id"),
                     "analysed": bool(g.get("is_analyzed"))})
    for s in skipped:
        base, inc = s.get("base_seconds"), s.get("increment_seconds")
        if base is None or inc is None or s.get("result") not in ("win", "loss", "draw") or not s.get("rated", True):
            continue
        rows.append({"clock": (int(base), int(inc)), "out": s["result"], "on_time": s.get("ending") == "time",
                     "at": s.get("played_at_utc"), "game_id": None, "analysed": False})
    return rows


def _score(rows: Sequence[Mapping[str, Any]]) -> float:
    return sum(1.0 if r["out"] == "win" else 0.5 if r["out"] == "draw" else 0.0 for r in rows) / len(rows)


def _halves(rows: Sequence[Mapping[str, Any]]) -> Tuple[List[Mapping[str, Any]], List[Mapping[str, Any]]]:
    dated = sorted((r for r in rows if isinstance(r.get("at"), datetime)), key=lambda r: r["at"])
    half = len(dated) // 2
    return dated[:half], dated[half:]


def clock_advice(rows: Sequence[Mapping[str, Any]],
                 slips: Optional[Callable[[Sequence[str]], Tuple[int, int]]] = None) -> Optional[Dict[str, Any]]:
    """The "what to play" line, or None. `slips(game_ids)` returns (mistakes
    from level positions, own moves) for analysed games; None skips gate 3."""
    by: Dict[Tuple[int, int], List[Mapping[str, Any]]] = {}
    for r in rows:
        by.setdefault(r["clock"], []).append(r)
    played = {c: rs for c, rs in by.items() if len(rs) >= MIN_GAMES}
    if len(played) < 2:
        return None
    scores = {c: _score(rs) for c, rs in played.items()}
    flagged, measured = [], {}
    for c, rs in played.items():
        others = {o: s for o, s in scores.items() if o != c}
        best = max(others, key=lambda o: (others[o], o[0]))
        losses = [r for r in rs if r["out"] == "loss"]
        on_time = sum(r["on_time"] for r in losses)
        early, late = _halves(rs)
        both_halves = bool(early and late) and all(_score(h) <= scores[best] - SCORE_GAP for h in (early, late))
        entry = {"games": len(rs), "score": round(scores[c], 3), "best": clock_name(*best),
                 "best_score": round(scores[best], 3), "losses": len(losses), "on_time": on_time,
                 "both_halves": both_halves}
        measured[clock_name(*c)] = entry
        if scores[c] > scores[best] - SCORE_GAP or not both_halves:
            continue
        if not losses or on_time / len(losses) < TIME_SHARE:
            continue
        if slips is not None:
            mine = [r["game_id"] for r in rs if r["analysed"] and r["game_id"]]
            theirs = [r["game_id"] for r in played[best] if r["analysed"] and r["game_id"]]
            if len(mine) >= MIN_ANALYSED and len(theirs) >= MIN_ANALYSED:
                (s1, m1), (s2, m2) = slips(mine), slips(theirs)
                entry["slips_per_40"] = round(s1 / max(m1, 1) * 40, 2)
                entry["best_slips_per_40"] = round(s2 / max(m2, 1) * 40, 2)
                if m1 and m2 and (s1 / m1) > SLIP_RATIO * (s2 / max(m2, 1)) and s2:
                    continue
        flagged.append((c, best))
    if not flagged:
        return None
    flagged.sort(key=lambda cb: (cb[0][0], cb[0][1]))
    names = [clock_name(*c) for c, _ in flagged]
    instead = max({b for _, b in flagged}, key=lambda b: (scores[b], b[0]))
    named = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return {
        "clocks": names,
        "instead": clock_name(*instead),
        "headline": f"Your {named} games go badly, mostly on the clock.",
        "detail": f"Your {clock_name(*instead)} games go better. Play {clock_name(*instead)} instead.",
        "measured": measured,
    }


def ids_for_mistake_check(rows: Sequence[Mapping[str, Any]]) -> List[str]:
    """Analysed game ids whose mistakes gate 3 needs, or [] when gates 1 and 2
    already name nothing (so the caller reads no observations at all)."""
    if not clock_advice(rows):
        return []
    return sorted({r["game_id"] for r in rows if r["analysed"] and r["game_id"]})


def slips_from(per_game: Mapping[str, Tuple[int, int]]) -> Callable[[Sequence[str]], Tuple[int, int]]:
    def f(ids: Sequence[str]) -> Tuple[int, int]:
        s = m = 0
        for gid in ids:
            a, b = per_game.get(gid, (0, 0))
            s, m = s + a, m + b
        return s, m
    return f


def is_slip(cp_loss: Any, eval_before: Any) -> bool:
    return (cp_loss or 0) >= SLIP_CP and isinstance(eval_before, (int, float)) and abs(eval_before) <= LEVEL_CP


def behaviour_line(game: Optional[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """One line about how the last game went for him, or None.

    `rows` are that game's move_evaluations; eval_before is from White's side.
    """
    if not game:
        return None
    colour = game.get("user_color")
    out = _outcome(game.get("result"), colour) or game.get("game_outcome")
    if colour not in ("white", "black") or out not in ("win", "loss", "draw"):
        return None
    sign = 1 if colour == "white" else -1
    own = sorted((r for r in rows if not r.get("is_opponent_move")), key=lambda r: r.get("move_number") or 0)
    evals = [sign * r["eval_before"] for r in own if isinstance(r.get("eval_before"), (int, float))]
    was_winning = out != "win" and bool(evals) and max(evals) >= WINNING_CP
    chain = None
    for i, r in enumerate(own):
        if r.get("evaluation") != "blunder":
            continue
        for nxt in own[i + 1:i + 1 + FOLLOW_MOVES]:
            if nxt.get("evaluation") in ("blunder", "mistake"):
                chain = (r.get("move"), nxt.get("move"))
                break
        if chain:
            break
    on_time = "time" in str(game.get("termination") or "").lower() and out == "loss"
    if was_winning and on_time:
        kind, headline, detail = ("winning_clock", "You were winning this game when your clock ran out.",
                                  "When you are ahead, play simple moves and keep time on your clock.")
    elif was_winning and chain:
        kind, headline, detail = ("winning_chain", "You were winning, and then one mistake brought another.",
                                  "After a mistake, stop. Look at their best reply before your next move.")
    elif was_winning:
        kind, headline, detail = ("winning", "You were winning this game and it slipped away.",
                                  "When you are ahead, check their replies before every move.")
    elif chain:
        kind, headline, detail = ("chain", "One mistake brought another soon after.",
                                  "After a mistake, stop. Look at their best reply before your next move.")
    else:
        return None
    return {"kind": kind, "headline": headline, "detail": detail, "game_id": game.get("game_id"),
            "measured": {"best_eval": max(evals) if evals else None, "chain": list(chain) if chain else None,
                         "outcome": out}}


__all__ = ["behaviour_line", "clock_advice", "clock_name", "clock_rows", "ids_for_mistake_check",
           "is_slip", "slips_from"]

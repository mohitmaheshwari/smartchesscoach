"""The coach's plan for one player: a read of how he plays and up to three
steps toward the next level, in the order they cost him games.

Mohit, 2026-11-12/13: "there should be something that keeps him hooked... that
coach knows about me, some kind of theory about him in general, how to make
him reach 1600 or whatever, plan we must have for him", and "we need to keep
tracking how a guy can reach +200".

Order of the steps = games lost or drawn from a level-or-better position
(coach_plan_service.rank_problems, PLAN-trusted detectors), the same measure
for every band, across every kind of step (a trusted habit, his costliest
opening habit, long sittings). The habit he is training now (player_coach_habit)
wins a tie. Measured 2026-11-13: for the 1834 test player the opening habit
cost 8 games and the trained habit 3, so "habit first" put the wrong step first.

Maia was measured as a "+200" tie-breaker on 2026-11-13 (55 players): a plan
mistake is only ~5% rarer 200 points up by Maia, it beats both controls in
16/52 steps at 1000-1399 and sees nothing under 1100 or at 1800+. It is
therefore NOT used to order steps here.

"The last game" line is said only when step one showed up in it. A game where
it did not show up is not proof he kept it (no opportunity count), so that
case says nothing.

Player-facing sentences carry no digits; counts stay in `measured`.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from services import coach_plan_service as cp

STEPS_SHOWN = 3
# Points at stake need at least this many finished games in the window. 2026-11-13:
# with about fifteen games the range swung from +0 to +417 on three games.
MIN_STAKE_GAMES = 20
# "Most of your lost games turn in X": the share must be a majority, over at
# least this many lost games with a deciding move.
PHASE_MIN_LOST_GAMES = 6
PHASE_MAJORITY = 0.5
OPENINGS_HOLD_MIN_GAMES = 30

PHASE_WORDS = {"opening": "opening", "middlegame": "middlegame", "endgame": "endgame"}


# ---------------------------------------------------------------------------
# "A chapter must not open for something we know he already knows."
#
# Mohit, 2026-11-26: "even best players like Magnus can sometimes let a piece
# undefended... human coaches don't give you exercise when you blunder
# something from eyesight, because they know you know this."
#
# Until 2026-11-27 the plan ranked purely by points at stake, which is
# frequency times cost. That ranks a thing he does wrong twice out of a
# hundred above a thing he has never been taught, because the first comes up
# constantly. On Mohit's own live plan it put
# `gap:piece_safety:destination_safety_exact` third -- a decision he gets
# right 4,141 times out of 4,318.
#
# The denominator is the whole point. `missed_pattern` (and so
# coach_plan_service.quality_id) is set ONLY when he missed, so counting it
# gives a numerator with nothing underneath. The structured detector fields
# carry both: `eligible` says he faced the decision, `fires` says it went
# wrong. Any detector recording quality_id + eligible + fires contributes,
# so this does not need a hardcoded list and picks up new ones for free.
# Mohit's rule, 2026-11-27: "it should be counted by opportunity exists vs
# opportunity taken... if a one move blunder exists and if that is 25%, player
# still needs to do the drill. If that's less than 25%, then we would try to
# understand why this error existed -- was this a time pressure thing, was
# this an eyesight or was player distracted, not focused... chess is also
# focus and behavioral tactics, so that's what we want to track."
#
# So the bar is a RATE over his last ten games, not a count, and not a
# percentile of other players. At or above it he drills. Below it, the error
# is real but the answer is a circumstance, not an exercise.
#
# Why ten games is enough here when twenty was not enough to detect
# improvement (see player_coach_habit.change_state): proving a big difference
# is cheap, proving absence is expensive. Measured 2026-11-27 across 65 users
# with ten analysed games, a ten-game window holds min 3, p25 35, median 44,
# max 73 piece-safety opportunities -- so 25% means about eleven fires
# against about three for a typical player. Four of the 65 cleared the bar
# (44.7%, 35.1%, 32.3%, 27.3%); the other 61 belong in the behavioural
# branch.
RATE_WINDOW_GAMES = 10
DRILL_RATE = 0.25
# Below this many opportunities the rate is noise: a player truly at 30% shows
# under 25% about a quarter of the time at n=20. The median window holds 44,
# so almost everyone clears it. NOT locked -- /lock-via-data.
MIN_OPPORTUNITIES = 20


def own_reliability(observations: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per quality_id: how often he faced this decision, how often it went wrong.

    Reads the structured detector verdicts rather than `missed_pattern`,
    because only those carry an opportunity count.
    """
    tally: Dict[str, Dict[str, Any]] = {}
    for obs in observations:
        for value in obs.values():
            if not isinstance(value, Mapping):
                continue
            qid = value.get("quality_id")
            if not qid or "eligible" not in value:
                continue
            row = tally.setdefault(str(qid), {"eligible": 0, "fired": 0})
            if value.get("eligible"):
                row["eligible"] += 1
                if value.get("fires"):
                    row["fired"] += 1
    for row in tally.values():
        row["error_rate"] = (row["fired"] / row["eligible"]) if row["eligible"] else None
    return tally


def below_drill_bar(reliability: Mapping[str, Mapping[str, Any]],
                    quality_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """The error is real but too rare to drill: ask WHY instead.

    Returns the counted evidence when the rate is under DRILL_RATE, else None
    (drill, or no usable denominator). A step is never withheld on a guess --
    absent or thin evidence returns None.

    The caller owes the player the behavioural reading in this case. Dropping
    the step and saying nothing is the wrong half of Mohit's rule.
    """
    if not quality_id:
        return None
    row = reliability.get(quality_id)
    if not row or row.get("error_rate") is None:
        return None
    if row["eligible"] < MIN_OPPORTUNITIES:
        return None
    if row["error_rate"] >= DRILL_RATE:
        return None
    return {"quality_id": quality_id,
            "opportunities": row["eligible"], "taken_wrong": row["fired"],
            "rate": round(row["error_rate"], 4),
            "drill_bar": DRILL_RATE, "needs": "behavioural_reading"}


def phase_of(fen: str, move_number: int) -> str:
    """Opening = his first twelve moves; endgame = six or fewer queens, rooks,
    bishops and knights left on the board (both sides); otherwise middlegame.
    The same split as the 2026-11-09 loss study."""
    if move_number <= 12:
        return "opening"
    board = (fen or "").split(" ")[0]
    heavy = sum(board.count(c) for c in "QRBNqrbn")
    return "endgame" if heavy <= 6 else "middlegame"


def where_lost(deciding: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """`deciding`: per lost or drawn game, his costliest move {fen, move_number, cp}."""
    counts: Dict[str, int] = {"opening": 0, "middlegame": 0, "endgame": 0}
    for d in deciding:
        counts[phase_of(d.get("fen") or "", int(d.get("move_number") or 0))] += 1
    n = sum(counts.values())
    top = max(counts, key=counts.get) if n else None
    words = None
    if n >= PHASE_MIN_LOST_GAMES:
        if counts[top] / n > PHASE_MAJORITY:
            words = f"Most of your lost games turn in the {PHASE_WORDS[top]}."
        # No majority: say nothing. "Your lost games turn in different parts
        # of the game, not just one" told the player nothing (Mohit, 2026-11-16).
    return {"words": words, "phase": top if words and counts[top] / max(n, 1) > PHASE_MAJORITY else None,
            "measured": {**counts, "lost_games": n}}


_SCORE = {"win": 1.0, "draw": 0.5, "loss": 0.0}


def _perf(score: float) -> float:
    """Rating difference implied by a score (the Elo expectation, inverted)."""
    e = min(max(score, 0.01), 0.99)
    return 400.0 * math.log10(e / (1.0 - e))


def points_at_stake(games: Mapping[str, Mapping[str, Any]], window: Sequence[str],
                    affected: Iterable[str]) -> Optional[Dict[str, Any]]:
    """What fixing a step is worth, from his own last games.

    Over the window, his score S of N games implies a performance. If every
    game the step cost had been DRAWN instead (low) or WON (high), the score
    rises and so does the implied performance; the difference is the range.
    An upper bound on one step, not a promise: it assumes nothing else changes.
    """
    scores = {gid: _SCORE.get((games.get(gid) or {}).get("outcome")) for gid in window}
    scores = {g: v for g, v in scores.items() if v is not None}
    n = len(scores)
    if n < MIN_STAKE_GAMES:
        return None
    total = sum(scores.values())
    hit = [g for g in set(affected) if g in scores]
    gain_draw = sum(max(0.0, 0.5 - scores[g]) for g in hit)
    gain_win = sum(1.0 - scores[g] for g in hit)
    base = _perf(total / n)
    return {"low": round(_perf((total + gain_draw) / n) - base),
            "high": round(_perf((total + gain_win) / n) - base),
            "games": len(hit), "window": n}


WORK_ITEMS = 3


def _review_url(game_id: str, move_number: Any) -> str:
    return f"/game/{game_id}" + (f"?move={move_number}" if move_number else "")


def _habit_work(row: Mapping[str, Any], games: Mapping[str, Mapping[str, Any]], practice_url: Optional[str]) -> Dict[str, Any]:
    """This week's work for a habit step: its moments from his own games."""
    moments = cp.choose_moments(row, WORK_ITEMS)
    find, play = [], []
    for o in moments:
        gid, mn = o.get("game_id"), o.get("move_number")
        if not gid:
            continue
        find.append({"ref": f"{gid}:{mn}", "game_id": gid, "move_number": mn, "url": _review_url(gid, mn)})
        colour = (games.get(gid) or {}).get("user_color")
        if o.get("fen_before") and colour in ("white", "black"):
            play.append({"ref": f"{gid}:{mn}", "fen": o["fen_before"], "user_color": colour, "source_game_id": gid})
    return {
        "learn": {"ref": "learn", "url": practice_url or "/learn",
                  "text": "Learn the warning sign and the rule, then practise the pattern."},
        "find": find,
        "play": play,
        "target": "In your games this week: stop before every move and use your rule.",
    }


def _problem_step(row: Mapping[str, Any], progress_by_qid: Mapping[str, Mapping[str, Any]],
                  training: bool) -> Dict[str, Any]:
    from services.player_coach_habit import PRACTICE_KEY

    kind, pattern = row["kind"], row["pattern"]
    sign = cp.sign_for(kind, pattern)
    state = progress_by_qid.get(row["quality_id"]) or {}
    return {
        "kind": "habit",
        "quality_id": row["quality_id"],
        "title": row["label"],
        "do": cp.rule_options(kind, pattern)[0]["text"],
        "sign": {"title": sign["title"], "text": sign["text"]},
        "practice_url": (f"/training/pattern/{PRACTICE_KEY[pattern or kind]}" if PRACTICE_KEY.get(pattern or kind) else None),
        "learn_url": "/learn",
        "state": state.get("state"), "state_title": state.get("title"),
        "training": training,
        "measured": {"games_lost": row["games_lost"], "games": row["games"], "moments": row["moments"]},
        "_affected": sorted({o["game_id"] for o in row.get("evidence") or [] if o.get("_costs_result")}),
        "key": f"habit:{row['quality_id']}",
        "_row": row,
    }


def build_plan(*, habit: Optional[Mapping[str, Any]], ranked: Sequence[Mapping[str, Any]],
               openings: Sequence[Mapping[str, Any]], sitting: Mapping[str, Any],
               progress: Mapping[str, Any], games: Mapping[str, Mapping[str, Any]],
               deciding: Sequence[Mapping[str, Any]], habit_check: Optional[Mapping[str, Any]],
               newest_game_id: Optional[str], observations: Iterable[Mapping[str, Any]],
               analysed_games: int, window: Sequence[str] = (),
               reliability: Optional[Mapping[str, Mapping[str, Any]]] = None,
               behaviour: Optional[Mapping[str, Mapping[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """The plan, or None when there is nothing proven to build it from."""
    # Read once. It is an Iterable, and it is needed again for the "last game"
    # line below -- iterating it twice would leave that silently empty.
    obs = list(observations)
    # His whole record when the caller read it, else what the window holds.
    # The window is capped at 60 games and cannot carry this decision on its
    # own -- see player_coach_file._reliability_pipeline.
    reliability = dict(reliability) if reliability is not None else own_reliability(obs)
    progress_by_qid = {r["quality_id"]: r for r in (progress.get("habits") or []) + (progress.get("kept") or [])}
    ranked_by_qid = {r["quality_id"]: r for r in ranked}
    # Steps withheld because he demonstrably already has them. Kept so the
    # reason is auditable, and so a later surface can say "you have these"
    # rather than the plan just going quiet.
    reliable_skips: List[Dict[str, Any]] = []

    steps: List[Dict[str, Any]] = []
    others: List[Dict[str, Any]] = []
    if habit and habit.get("quality_id") in ranked_by_qid:
        steps.append(_problem_step(ranked_by_qid[habit["quality_id"]], progress_by_qid, training=True))
    for row in ranked:
        if habit and row["quality_id"] == habit.get("quality_id"):
            continue
        if row["games_lost"] < 1:
            continue
        # No chapter opens for something he already has. Frequency times cost
        # ranks a thing he gets right 24 times out of 25 above a thing nobody
        # has taught him, because the first keeps coming up.
        under = below_drill_bar(reliability, row.get("quality_id"))
        if under:
            # The debt comes due here: say WHY, or say plainly that we cannot.
            # An unexplained reading is still a reading and is not dropped.
            read_why = (behaviour or {}).get(row.get("quality_id"))
            if read_why:
                under = {**under, "why": read_why}
            reliable_skips.append(under)
            continue
        others.append(_problem_step(row, progress_by_qid, training=False))

    if openings:
        h = openings[0]
        # The same game window as the habit steps (his newest HABIT_GAMES),
        # so the order and the points at stake measure the same thing.
        # 2026-11-16: the opening counted sixty games and the habits thirty,
        # which put a step worth +25 before one worth +51.
        in_window = set(window) if window else None
        lost_ids = [gid for gid in (h.get("measured") or {}).get("game_ids") or []
                    if (games.get(gid) or {}).get("outcome") in ("loss", "draw")
                    and (in_window is None or gid in in_window)]
        lost = len(lost_ids)
        if lost >= 1:
            side = "White" if h["side"] == "white" else "Black"
            inst = (h.get("measured") or {}).get("instances") or []
            work = {
                "learn": {"ref": "learn", "url": h.get("review_url") or "/learn",
                          "text": "See the position in your game, and the better move."},
                "find": [{"ref": f"{i['game_id']}:{i['move_number']}", "game_id": i["game_id"],
                          "move_number": i["move_number"], "url": _review_url(i["game_id"], i["move_number"])}
                         for i in inst[:WORK_ITEMS]],
                "play": [{"ref": f"{i['game_id']}:{i['move_number']}", "fen": i["fen"], "user_color": h["side"],
                          "source_game_id": i["game_id"]} for i in inst[:WORK_ITEMS]],
                "target": f"In your games this week: when you reach this position as {side}, play the green move.",
            }
            others.append({
                "kind": "opening", "title": f"Your opening as {side}",
                "key": f"opening:{h['side']}:{h.get('line')}:{h.get('idea')}",
                "work": work,
                "do": "You keep reaching this position and playing the orange move. The green move is better.",
                "san": h.get("san"), "better_san": h.get("better_san"), "line": h.get("line"),
                # The board the card draws: the clearest game, both moves as arrows.
                "fen": h.get("fen"), "side": h.get("side"),
                "played_from": h.get("played_from"), "played_to": h.get("played_to"),
                "better_from": h.get("better_from"), "better_to": h.get("better_to"),
                "review_url": h.get("review_url"),
                "learn_url": "/learn", "practice_url": None, "training": False,
                "measured": {"games_lost": lost, "games": (h.get("measured") or {}).get("games")},
                "_affected": lost_ids,
            })

    # Long sittings are a guard rail beside the plan, not a step to the next
    # level (Mohit, 2026-11-13, on the first plan: "how can this be a plan").
    guard = None
    if (sitting or {}).get("proven"):
        guard = {"title": "Stop after a long run of games",
                 "text": "Your results drop late in a long sitting. When you have played many in a row, stop."}

    win = list(window)
    candidates = steps + others
    for st in candidates:
        st["stake"] = points_at_stake(games, win, st["_affected"]) if win else None

    # A step with no affected game in the window has no evidence behind it in
    # the period it is being shown for. Mohit's live plan on 2026-11-26 put
    # `gap:piece_safety:destination_safety_exact` third with
    # stake {low: 0, high: 0, games: 0} -- "AFTER THAT, practise this", worth
    # nothing, measured over nothing, while its own text read "this shows up
    # in fewer of your games than before".
    #
    # Only dropped while an evidenced step survives, so the card never empties
    # because of this rule.
    evidenced = [st for st in candidates
                 if ((st.get("stake") or {}).get("games") or 0) >= 1]
    if evidenced and len(evidenced) < len(candidates):
        candidates = evidenced
    # Most points at stake first (the figure each step shows), so "First" is
    # never worth less than "Then"; games lost breaks ties, then the habit
    # being trained. Without enough games for points, games lost decides.
    steps = sorted(candidates, key=lambda s: (-((s.get("stake") or {}).get("high") or 0),
                                              -s["measured"]["games_lost"], not s.get("training")))[:STEPS_SHOWN]
    if not steps:
        return None
    steps[0]["this_week"] = True
    union: set = set()
    for st in steps:
        union.update(st.pop("_affected", []))
    for st in candidates:
        st.pop("_affected", None)
    total_stake = points_at_stake(games, win, union) if win else None
    for st in steps:
        row = st.pop("_row", None)
        if row is not None:
            st["work"] = _habit_work(row, games, st.get("practice_url"))

    read: List[str] = []
    phase = where_lost(deciding)
    if phase["words"]:
        read.append(phase["words"])
    # The read names step one, whatever kind it is, so it never contradicts the order.
    top = steps[0]["title"]
    read.append(f"What costs you most: {top[0].lower() + top[1:]}.")
    if openings:
        # Said only when the opening is one of the shown steps (it cost a game
        # in the window) and step one is not already it.
        if steps[0]["kind"] != "opening" and any(s["kind"] == "opening" for s in steps):
            side = "White" if openings[0]["side"] == "white" else "Black"
            read.append(f"One opening habit costs you as {side}.")
    elif analysed_games >= OPENINGS_HOLD_MIN_GAMES:
        # Only when no opening habit was found at all.
        # What was measured: no costly opening move repeats with one fix.
        # "Your openings hold up" claimed more than that (2026-11-16).
        read.append("No opening mistake keeps coming back in your games.")

    last_note = None
    if steps[0]["kind"] == "habit" and newest_game_id:
        qid = steps[0]["quality_id"]
        if any(o.get("game_id") == newest_game_id and cp.quality_id(o) == qid for o in obs):
            last_note = "Your last game: this week's step showed up again."

    return {
        "read": read,
        "steps": steps,
        # The per-game check exists for the trained habit only.
        "check": next((habit_check for s in steps if s.get("training")), None),
        "last_game_note": last_note,
        "guard": guard,
        # Errors real enough to count but under the drill bar. Each one is a
        # DEBT, not a dismissal: Mohit's rule says we owe the player why it
        # happened -- the clock, their eyes, their focus -- and these rows are
        # what a behavioural reading must be built from. Dropping the step and
        # saying nothing is the wrong half of the rule.
        "ask_why": reliable_skips,
        # Rating points the shown steps are worth together, from his last games
        # (a range: drawn instead .. won instead). The plan's claim.
        "stake": total_stake,
        "measured": {"where_lost": phase["measured"]},
        # Every opening habit that exists now, shown as a step or not. The
        # week (player_plan_week) drops a locked opening step that is not here:
        # 2026-11-16 the stricter habit rule removed openings that weekly rows
        # still pointed at, and the week kept showing them.
        "opening_keys": [f"opening:{h['side']}:{h.get('line')}:{h.get('idea')}" for h in openings],
    }

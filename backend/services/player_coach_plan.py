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

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from services import coach_plan_service as cp

STEPS_SHOWN = 3
# "Most of your lost games turn in X": the share must be a majority, over at
# least this many lost games with a deciding move.
PHASE_MIN_LOST_GAMES = 6
PHASE_MAJORITY = 0.5
OPENINGS_HOLD_MIN_GAMES = 30

PHASE_WORDS = {"opening": "opening", "middlegame": "middlegame", "endgame": "endgame"}


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
        else:
            words = "Your lost games turn in different parts of the game, not just one."
    return {"words": words, "phase": top if words and counts[top] / max(n, 1) > PHASE_MAJORITY else None,
            "measured": {**counts, "lost_games": n}}


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
    }


def build_plan(*, habit: Optional[Mapping[str, Any]], ranked: Sequence[Mapping[str, Any]],
               openings: Sequence[Mapping[str, Any]], sitting: Mapping[str, Any],
               progress: Mapping[str, Any], games: Mapping[str, Mapping[str, Any]],
               deciding: Sequence[Mapping[str, Any]], habit_check: Optional[Mapping[str, Any]],
               newest_game_id: Optional[str], observations: Iterable[Mapping[str, Any]],
               analysed_games: int) -> Optional[Dict[str, Any]]:
    """The plan, or None when there is nothing proven to build it from."""
    progress_by_qid = {r["quality_id"]: r for r in (progress.get("habits") or []) + (progress.get("kept") or [])}
    ranked_by_qid = {r["quality_id"]: r for r in ranked}

    steps: List[Dict[str, Any]] = []
    others: List[Dict[str, Any]] = []
    if habit and habit.get("quality_id") in ranked_by_qid:
        steps.append(_problem_step(ranked_by_qid[habit["quality_id"]], progress_by_qid, training=True))
    for row in ranked:
        if habit and row["quality_id"] == habit.get("quality_id"):
            continue
        if row["games_lost"] >= 1:
            others.append(_problem_step(row, progress_by_qid, training=False))

    if openings:
        h = openings[0]
        lost = sum(1 for gid in (h.get("measured") or {}).get("game_ids") or []
                   if (games.get(gid) or {}).get("outcome") in ("loss", "draw"))
        if lost >= 1:
            side = "White" if h["side"] == "white" else "Black"
            others.append({
                "kind": "opening", "title": f"Your opening as {side}",
                "do": "Play the better move in the position where your habit costs you.",
                "san": h.get("san"), "better_san": h.get("better_san"), "line": h.get("line"),
                "learn_url": "/learn", "practice_url": None, "training": False,
                "measured": {"games_lost": lost, "games": (h.get("measured") or {}).get("games")},
            })

    sm = (sitting or {}).get("measured") or {}
    if (sitting or {}).get("proven"):
        est = round((sm.get("late_games") or 0) * (sm.get("drop") or 0))
        if est >= 1:
            others.append({
                "kind": "sitting", "title": "Long sittings",
                "do": "Stop after a long run of games. Your later games go worse.",
                "learn_url": None, "practice_url": None, "training": False,
                "measured": {"games_lost": est, "late_games": sm.get("late_games"), "drop": sm.get("drop")},
            })

    steps = sorted(steps + others, key=lambda s: (-s["measured"]["games_lost"], not s.get("training")))[:STEPS_SHOWN]
    if not steps:
        return None
    steps[0]["this_week"] = True

    read: List[str] = []
    phase = where_lost(deciding)
    if phase["words"]:
        read.append(phase["words"])
    # The read names step one, whatever kind it is, so it never contradicts the order.
    top = steps[0]["title"]
    read.append(f"What costs you most: {top[0].lower() + top[1:]}.")
    if openings and steps[0]["kind"] != "opening":   # step one already says it
        read.append(f"One opening habit costs you as {'White' if openings[0]['side'] == 'white' else 'Black'}.")
    elif analysed_games >= OPENINGS_HOLD_MIN_GAMES:
        read.append("Your openings hold up.")
    if (sitting or {}).get("proven"):
        read.append("Your results drop late in long sittings.")

    last_note = None
    if steps[0]["kind"] == "habit" and newest_game_id:
        qid = steps[0]["quality_id"]
        if any(o.get("game_id") == newest_game_id and cp.quality_id(o) == qid for o in observations):
            last_note = "Your last game: this week's step showed up again."

    return {
        "read": read,
        "steps": steps,
        # The per-game check exists for the trained habit only.
        "check": next((habit_check for s in steps if s.get("training")), None),
        "last_game_note": last_note,
        "measured": {"where_lost": phase["measured"]},
    }

"""The habit a player is training, and whether each habit is changing.

docs/coach_pages_scope.md, "Learn" and "Progress". This is the self-coach door
of the academy coach plan (docs/coach_assistant_plan_scope.md, 2e): the SAME
engine (`coach_plan_service`) picks the problem, so every player at every
level is coached only on problems a PLAN-trusted detector can prove, and the
academy coach and the player see one answer, never two.

What differs from the academy plan:
  - no approval step: the plan goes straight to the player;
  - the window is his newest analysed games, not a calendar month, because a
    player outside an academy plays in bursts;
  - the habit is sticky for HABIT_KEEP_DAYS so it does not change every game.

"Is it working" is decided per player against his OWN earlier rate, with a
binomial tail test (CHANCE_P). Nothing is said as better or worse unless his
games show it beyond chance; otherwise "No clear change yet". No figure ever
reaches the player: counts stay in `measured`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import comb
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from services import coach_plan_service as cp

# Newest analysed games the habit is chosen from.
HABIT_GAMES = 30
# A chosen habit is kept this long while it is still among his top three.
HABIT_KEEP_DAYS = 14
HABIT_MOMENTS = 3
# "Where you are" = his newest PROGRESS_NOW analysed games; "where you started"
# = the PROGRESS_THEN games before them.
PROGRESS_NOW = 20
PROGRESS_THEN = 40
PROGRESS_MIN_GAMES_EACH = 10
# A habit is shown on Progress when it happened in at least this many games.
PROGRESS_MIN_HIT_GAMES = 2
# One-sided chance level for "better", "worse" and "kept".
CHANCE_P = 0.10
# Games with the problem a change must stand on (see change_state).
EVIDENCE_GAMES = 3

STATE_WORDS = {
    "better": ("Getting better", "This shows up in fewer of your games than before."),
    "worse": ("Showing up more", "This shows up in more of your recent games."),
    "same": ("Same as before", "No clear change yet."),
    "kept": ("Kept", "This has stopped showing up in your games."),
    "waiting": ("Waiting for games", "Not enough new games to tell yet."),
}

# Where a habit's practice lives today (PrescribedTraining handles each key;
# pin/fork/skewer go to the motif drill). docs/coach_pages_scope.md, Learn.
PRACTICE_KEY = {
    "landing": "piece_safety", "king_attack": "king_safety", "fork": "fork", "pin": "pin",
    "skewer": "skewer", "mate": "missed_tactic", "development": "opening_knowledge",
}


# --------------------------------------------------------------------------
# chance
# --------------------------------------------------------------------------
def _tail_le(k: int, n: int, p: float) -> float:
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))


def _tail_ge(k: int, n: int, p: float) -> float:
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def change_state(hits_now: int, n_now: int, rate_then: Optional[float],
                 min_games: int = PROGRESS_MIN_GAMES_EACH, hits_then: Optional[int] = None) -> str:
    """better / worse / same / kept / waiting, against his own earlier rate.

    Beyond the chance test, a change needs games behind it: "better" and
    "kept" need EVIDENCE_GAMES earlier games with the problem (a rate from
    one or two games is not a baseline), and "worse" needs EVIDENCE_GAMES
    recent ones. The 2026-11-12 dry run said "showing up more" for a move
    seen in no earlier game and two recent ones; that is not enough."""
    if rate_then is None or n_now < min_games:
        return "waiting"
    p = min(max(rate_then, 0.0), 1.0)
    enough_then = hits_then is None or hits_then >= EVIDENCE_GAMES
    if enough_then and hits_now == 0 and p > 0 and _tail_le(0, n_now, p) < CHANCE_P:
        return "kept"
    if enough_then and hits_now / n_now < p and _tail_le(hits_now, n_now, p) < CHANCE_P:
        return "better"
    if hits_now >= EVIDENCE_GAMES and hits_now / n_now > p and _tail_ge(hits_now, n_now, p) < CHANCE_P:
        return "worse"
    return "same"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def games_map(games_newest_first: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """game_id -> the fields coach_plan_service reads (outcome, user_color, played_at)."""
    from services.game_outcome import user_outcome

    out: Dict[str, Dict[str, Any]] = {}
    for g in games_newest_first:
        played = g.get("played_at_utc")
        out[g["game_id"]] = {
            "game_id": g["game_id"], "result": g.get("result"), "user_color": g.get("user_color"),
            "termination": g.get("termination"), "game_outcome": g.get("game_outcome"),
            "outcome": user_outcome(dict(g)),
            "played_at": played.isoformat() if isinstance(played, datetime) else str(played or ""),
        }
    return out


def _hit_games(qid: str, observations: Iterable[Mapping[str, Any]], ids: Iterable[str]) -> set:
    ids = set(ids)
    return {o["game_id"] for o in observations if o.get("game_id") in ids and cp.quality_id(o) == qid}


def _when(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# the habit
# --------------------------------------------------------------------------
def choose_habit(analysed_newest_first: Sequence[str], games: Mapping[str, Mapping[str, Any]],
                 observations: Sequence[Mapping[str, Any]], previous: Optional[Mapping[str, Any]],
                 now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """The one problem he trains now, or None when no trusted problem showed up.

    `previous` is the habit stored in his last file; it is kept while it is
    young and still among his top three, so the page does not change its mind
    after every game."""
    now = now or datetime.now(timezone.utc)
    window = list(analysed_newest_first)[:HABIT_GAMES]
    window_games = {gid: games[gid] for gid in window if gid in games}
    ranked = cp.rank_problems(window_games, [o for o in observations if o.get("game_id") in window_games])
    if not ranked:
        return None
    top = ranked[0]
    started = now
    if previous and previous.get("quality_id"):
        prev_started = _when(previous.get("started_at"))
        still_there = next((r for r in ranked[:3] if r["quality_id"] == previous["quality_id"]), None)
        if still_there and prev_started and now - prev_started <= timedelta(days=HABIT_KEEP_DAYS):
            top, started = still_there, prev_started
    baseline = (previous or {}).get("baseline") if started != now else None
    if not baseline:
        baseline = cp.baseline_for(top, window_games)
    kind, pattern = top["kind"], top["pattern"]
    sign = cp.sign_for(kind, pattern)
    rule = cp.rule_options(kind, pattern)[0]
    return {
        "quality_id": top["quality_id"],
        "label": top["label"],
        "kind": kind,
        "pattern": pattern,
        "warning_sign": {"title": sign["title"], "text": sign["text"]},
        "rule": rule["text"],
        "practice_key": PRACTICE_KEY.get(pattern or kind),
        "started_at": started,
        "baseline": baseline,
        # The moments are built with the engine in a second step (worker thread).
        "_evidence": cp.choose_moments(top, HABIT_MOMENTS + 2),
        "measured": {"games_lost": top["games_lost"], "games": top["games"],
                     "moments": top["moments"], "window_games": len(window_games)},
    }


def habit_check(habit: Mapping[str, Any], analysed_newest_first: Sequence[str],
                games: Mapping[str, Mapping[str, Any]],
                observations: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Games since the habit started: did it show up less than before?"""
    started = _when(habit.get("started_at"))
    since = [gid for gid in analysed_newest_first
             if gid in games and started and (_when(games[gid].get("played_at")) or started) > started]
    hits = _hit_games(habit["quality_id"], observations, since)
    rate_before = (habit.get("baseline") or {}).get("rate")
    state = change_state(len(hits), len(since), rate_before, min_games=5,
                         hits_then=(habit.get("baseline") or {}).get("hit_games"))
    title, words = STATE_WORDS[state]
    return {"state": state, "title": title, "words": words,
            "measured": {"games_since": len(since), "hit_games": len(hits), "rate_before": rate_before}}


# --------------------------------------------------------------------------
# progress, every trusted problem
# --------------------------------------------------------------------------
def progress(analysed_newest_first: Sequence[str], games: Mapping[str, Mapping[str, Any]],
             observations: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    ids = [gid for gid in analysed_newest_first if gid in games]
    if len(ids) < 2 * PROGRESS_MIN_GAMES_EACH:
        now_ids, then_ids = ids, []
    elif len(ids) >= PROGRESS_NOW + PROGRESS_MIN_GAMES_EACH:
        now_ids, then_ids = ids[:PROGRESS_NOW], ids[PROGRESS_NOW:PROGRESS_NOW + PROGRESS_THEN]
    else:
        half = len(ids) // 2
        now_ids, then_ids = ids[:half], ids[half:]
    rows = []
    for qid, (kind, pattern, label) in cp.PROBLEMS.items():
        hits_now = _hit_games(qid, observations, now_ids)
        hits_then = _hit_games(qid, observations, then_ids)
        if len(hits_now) + len(hits_then) < PROGRESS_MIN_HIT_GAMES:
            continue
        rate_then = (len(hits_then) / len(then_ids)) if len(then_ids) >= PROGRESS_MIN_GAMES_EACH else None
        state = change_state(len(hits_now), len(now_ids), rate_then, hits_then=len(hits_then))
        title, words = STATE_WORDS[state]
        rows.append({
            "quality_id": qid, "label": label, "kind": kind, "pattern": pattern,
            "state": state, "title": title, "words": words,
            "measured": {"now_games": len(now_ids), "now_hit_games": len(hits_now),
                         "then_games": len(then_ids), "then_hit_games": len(hits_then)},
        })
    order = {"worse": 0, "same": 1, "better": 2, "waiting": 3, "kept": 4}
    rows.sort(key=lambda r: (order[r["state"]], -r["measured"]["now_hit_games"], r["quality_id"]))
    return {
        "habits": [r for r in rows if r["state"] != "kept"],
        "kept": [r for r in rows if r["state"] == "kept"],
        "measured": {"now_games": len(now_ids), "then_games": len(then_ids)},
    }

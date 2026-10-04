"""How a player plays — the behavioural traits, described rather than graded.

Mohit: *"behaviour detection is the real story a coach understands, and
knowledge"*, and then, of the six confirmed traits, *"all of them?"*

WHY THIS IS NOT A SCORECARD
---------------------------
`services/area_grades.py` grades board areas Excellent → Needs work, and that is
right for a skill. It is wrong for a disposition. "Thinks too long — Needs work"
would be a judgement the data refuses: measured per player, thinking longer goes
with FEWER errors, not more (r = -0.56). Traits are how someone plays, not how
well. So each one gets a sentence, never a grade and never a rank.

It is also not a focus. Five focuses is no focus — the picker still names ONE
thing to work on. This says who the player is; the focus says what to do next.

THE TRAITS, AND WHY THESE SIX
-----------------------------
Each was tested for the only property that makes a trait real: it must be stable
within a player across time AND spread across players. Measured over the first
half of each player's games against their second half:

    thinks too long          0.88     clock front-loaded    0.87
    error rate               0.83     knowledge breadth     0.77
    moves fast for him       0.76     plays on when lost    0.72

Ten more candidates were measured and rejected, and they are named here so
nobody rebuilds them: tilt -- one blunder causing the next -- is 0.18 and simply
is not real; aggression failed twice, at 0.23 as forcing-move share and 0.06
measured properly through wrong-register; errs-when-forcing 0.28; too-passive is
stable at 0.58 but has a spread of 0.009, so everyone is identical and it
separates nobody. Also weak and excluded: repeats-next-game 0.68,
notices-threats 0.65, endgame-weighted 0.64, opportunism 0.50.

GAME-LEVEL CANDIDATES, TESTED 2026-09-29
---------------------------------------
A game-level measure is one binary observation per game, so it looks weak at
small samples whatever the truth. The test for noise versus a weak trait is
whether the correlation CLIMBS as the bar rises.

    conversion        0.43 -> 0.59 -> 0.72   CLIMBS -> real, and it is in CUTS
    comeback          0.12, 0.07, 0.00, 0.14 flat -> saving lost games is the
                                             opponent's doing, not a property
                                             of the player
    session fatigue   0.13, 0.31, 0.14, 0.22 bounces -> not a trait
    punches up        7 players at the lowest bar -> not measurable here

TILT BETWEEN GAMES IS INCONCLUSIVE, and the way it nearly fooled me is worth
keeping. The raw after-a-loss failure rate correlates at 0.60 across halves and
climbs beautifully -- but a control on games that did NOT follow a loss climbs
identically, 0.30 / 0.41 / 0.54 / 0.58 / 0.62. That correlation is player
strength, not tilt: it appears on any set of games.

The honest measure is the LIFT, this player's failure rate after a loss against
their own rate otherwise. Median 1.09, quartiles 0.99 and 1.36, range 0.67 to
2.57, and 20 of 47 players are more than a tenth worse after a loss. But the
lift's own stability is 0.39 over 31 players, and the sample is too thin to run
the rising bar that settled conversion. Real population effect, unproven as a
trait. Do not ship it as one without more games per player.

ERROR RATE IS CARRIED BUT NOT SPOKEN
------------------------------------
It is the most stable thing here after the clock, and it is not a diagnosis: it
is how strong the player is. Telling someone their error rate is telling them
their rating back. It stays in the payload for ranking and measurement and has
no sentence.

THE CUTS ARE QUARTILES OF A MEASURED POPULATION, 48 players, 2026-09-28:

    thinks_long          q1 0.118  median 0.139  q3 0.175
    moves_fast           q1 0.055  median 0.084  q3 0.116
    clock_front_loaded   q1 0.391  median 0.468  q3 0.608
    plays_on_when_lost   q1 0.160  median 0.207  q3 0.237
    knowledge_breadth    q1 0.300  median 0.326  q3 0.363
    error_rate           q1 0.126  median 0.152  q3 0.170

A player inside the middle half gets NO sentence for that trait, because
"you are about average at this" is not worth a line on a page. Only the ends
say anything, and they say it without comparing.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

# Measured quartiles. (low_cut, high_cut) — outside them a trait speaks.
CUTS: Dict[str, tuple] = {
    "thinks_long": (0.118, 0.175),
    "moves_fast": (0.055, 0.116),
    "clock_front_loaded": (0.391, 0.608),
    "plays_on_when_lost": (0.160, 0.237),
    "knowledge_breadth": (0.300, 0.363),
    "error_rate": (0.126, 0.170),
    # Failing to convert a winning position. Quartiles at a sample where the
    # measure is reliable (100+ winning positions): 0.29 / 0.33 / 0.38.
    "throws_away_won_games": (0.29, 0.38),
}

# Traits that need more than the usual history before they may be spoken.
#
# Conversion is a GAME-level event, so each game is one binary observation and
# the estimate is noise-limited at small samples. Measured half-half as the bar
# rose: 0.41 at 10 winning positions, 0.43 at 30, 0.44 at 60, 0.59 at 100, 0.72
# at 150 -- climbing exactly as Spearman-Brown predicts for attenuation
# (0.43 implies 0.60 at double length and 0.75 at quadruple). So the trait is
# real and the early reading was noise, not weakness.
MIN_SAMPLE = {"throws_away_won_games": 60}

# Carried for ranking and measurement, never rendered. See the module docstring.
SILENT_TRAITS = frozenset({"error_rate"})

# One sentence per end of each trait. No numbers, no grades, no comparison to
# other players. Written to be recognisable rather than flattering or damning --
# a player should read it and think "yes, that is me".
SENTENCES: Dict[str, Dict[str, str]] = {
    "thinks_long": {
        "high": "You take long thinks. When a position gets hard, you stop and work.",
        "low": "You keep moving. Long thinks are rare for you, even in sharp positions.",
    },
    "moves_fast": {
        "high": "A lot of your moves go in quickly, without a pause.",
        "low": "You give most moves a moment, rather than playing on instinct.",
    },
    "clock_front_loaded": {
        "high": "You spend most of your clock early, and finish games in a hurry.",
        "low": "You keep time back for later, so the end of the game is not rushed.",
    },
    "plays_on_when_lost": {
        "high": "You keep playing when the game has gone against you.",
        "low": "When a game turns bad, it tends to end soon after.",
    },
    "knowledge_breadth": {
        "high": "A lot of named ideas show up in your play.",
        "low": "The same few ideas carry most of your games.",
    },
    "throws_away_won_games": {
        "high": "Winning positions slip away from you more often than they should. "
                "Getting a game won is not the same as winning it.",
        "low": "When you get on top of a game, you finish it off.",
    },
}

MIN_MOVES = 400
MIN_TIMED_MOVES = 200


def describe(traits: Optional[Dict[str, float]],
             samples: Optional[Dict[str, int]] = None) -> List[Dict[str, str]]:
    """The sentences a player reads, for the traits that are at an end.

    A trait inside the middle half of the population says nothing. That is the
    honest outcome and it keeps the page short: most players will see two or
    three lines, not six.
    """
    lines: List[Dict[str, str]] = []
    samples = samples or {}
    for key, value in sorted((traits or {}).items()):
        if key in SILENT_TRAITS or key not in CUTS or value is None:
            continue
        needed = MIN_SAMPLE.get(key)
        if needed is not None and samples.get(key, 0) < needed:
            # Measurable in principle, not yet in fact for this player.
            continue
        low, high = CUTS[key]
        end = "high" if value >= high else "low" if value <= low else None
        if end is None:
            continue
        sentence = SENTENCES.get(key, {}).get(end)
        if sentence:
            lines.append({"trait": key, "end": end, "sentence": sentence})
    return lines


def build_profile(traits: Optional[Dict[str, float]],
                  moves: int, timed_moves: int,
                  samples: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """The whole payload. `measured` is false when we have not watched enough.

    Saying nothing is a real answer here. A profile built on a handful of games
    describes the games, not the person.
    """
    enough = moves >= MIN_MOVES and timed_moves >= MIN_TIMED_MOVES
    lines = describe(traits, samples) if enough else []
    if enough and traits and not lines:
        # Every trait inside the middle half. That is a real answer, not an
        # empty one -- it says the player has no pronounced tendency either
        # way -- and it beats showing a blank page to someone with hundreds of
        # games. Measured on production: 3 of 48 players land here, and one of
        # them has 21,126 observed moves.
        # THIS SENTENCE MAY ONLY CLAIM WHAT THE MIDDLE BAND LICENSES.
        #
        # It used to end "and you finish the games you should", which is the
        # `low` sentence of throws_away_won_games asserted without that trait
        # being low. Mohit, 2026-10-04: the one player on prod receiving this
        # line has a conversion rate in the THIRD quartile -- 0.357 against a
        # median of 0.33 and a high cut of 0.38 -- and 68 of his analysed
        # timeout losses were positions he was winning. The page told him he
        # finishes what he starts.
        #
        # A trait sitting inside the middle half means WE ARE NOT SPEAKING
        # about it. It does not mean the flattering end is true. Tempo is the
        # one thing this line actually checked, so tempo is all it now says.
        lines = [{
            "trait": "balanced",
            "end": "middle",
            "sentence": "Nothing about how you play stands out at either end. "
                        "You take your time about as much as you rush it.",
        }]
    return {
        "schema_version": "behaviour_profile.v1",
        "measured": bool(enough and traits),
        "reason": None if enough else "not enough games watched yet",
        "lines": lines,
        # internal only: rates are numbers and are never rendered
        "_traits": dict(traits or {}),
    }


async def compute_traits(db, user_id: str) -> Dict[str, Any]:
    """Measure this player's seven traits from stored observations and games.

    Display-only, like `area_grades`: it reads what is stored and tells nobody
    what to do next, so it needs no detector authorization. The focus still
    names exactly one thing; this describes the person.

    Returns `{"traits": {...}, "moves": int, "timed_moves": int,
    "samples": {...}}` -- the shape `build_profile` takes.
    """
    import statistics

    moves = await db.move_observations.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "move_number": 1, "time_spent_seconds": 1,
         "execution_quality": 1, "concept_used": 1, "eval_before": 1,
         "color": 1},
    ).to_list(60000)

    per_game_times: Dict[str, List[float]] = {}
    for move in moves:
        seconds = move.get("time_spent_seconds")
        if isinstance(seconds, (int, float)):
            per_game_times.setdefault(move.get("game_id"), []).append(seconds)
    median_pace = {g: statistics.median(v) for g, v in per_game_times.items() if v}

    timed = slow = fast = 0
    clock_split: Dict[str, List[float]] = {}
    for move in moves:
        seconds, game_id = move.get("time_spent_seconds"), move.get("game_id")
        pace = median_pace.get(game_id)
        if pace and pace > 0 and isinstance(seconds, (int, float)):
            timed += 1
            if seconds / pace > 3.0:
                slow += 1
            if seconds / pace < 0.25:
                fast += 1
        if isinstance(seconds, (int, float)):
            slot = clock_split.setdefault(game_id, [0.0, 0.0])
            slot[1] += seconds
            if (move.get("move_number") or 99) <= 15:
                slot[0] += seconds
    front = [early / total for early, total in clock_split.values() if total > 0]

    def own_eval(move):
        value = move.get("eval_before")
        if not isinstance(value, (int, float)):
            return None
        return value if move.get("color") == "white" else -value

    total_moves = len(moves)
    traits: Dict[str, float] = {}
    if total_moves:
        traits["plays_on_when_lost"] = sum(
            1 for m in moves if (own_eval(m) or 0) < -300) / total_moves
        traits["knowledge_breadth"] = sum(
            1 for m in moves
            if m.get("concept_used") and m["concept_used"] != "found_best_move"
        ) / total_moves
        traits["error_rate"] = sum(
            1 for m in moves
            if m.get("execution_quality") in ("mistake", "blunder")) / total_moves
    if timed:
        traits["thinks_long"] = slow / timed
        traits["moves_fast"] = fast / timed
    if front:
        traits["clock_front_loaded"] = statistics.median(front)

    # Conversion is a GAME-level trait: of the games where this player reached a
    # clearly winning position, how many did they fail to win. A per-move
    # measure cannot see it -- one catastrophic move barely moves an average.
    peak: Dict[str, float] = {}
    for move in moves:
        value = own_eval(move)
        game_id = move.get("game_id")
        if value is not None and game_id:
            if value > peak.get(game_id, -99999):
                peak[game_id] = value
    won_ids = [g for g, v in peak.items() if v >= 300]
    samples: Dict[str, int] = {}
    if won_ids:
        finished = await db.games.find(
            {"game_id": {"$in": won_ids}},
            {"_id": 0, "game_id": 1, "result": 1, "user_color": 1},
        ).to_list(5000)
        if finished:
            from services.game_outcome import user_won

            failed = sum(1 for g in finished if not user_won(g))
            traits["throws_away_won_games"] = failed / len(finished)
            samples["throws_away_won_games"] = len(finished)

    return {"traits": traits, "moves": total_moves,
            "timed_moves": timed, "samples": samples}

"""Why did this error happen, when it is too rare to drill?

Mohit, 2026-11-27: "if that's less than 25%, then we would try to understand
why this error existed, was this a time pressure thing, was this an eye sight
or was player distracted, not focused... chess is just not calculation and
tactics, chess is also focus and behavioral tactics, so that's what we want
to track."

So this is the second half of the drill rule in
`player_coach_plan.below_drill_bar`: the error is real, the rate is under the
bar, and the player is owed a circumstance rather than an exercise.

WHAT EARNED A PLACE HERE
------------------------
A cause only counts if it is commoner among the errors than among the SAME
opportunities that went fine. Measured 2026-11-27 over 1,200 analysed games
and 5,466 eligible one-move piece-safety decisions, base rate 8.29%:

    signal                             n     with   without   lift
    time pressure (<60s left)        218   14.68%    8.05%   1.82x
    unravelling (big error in last 3) 1539  10.14%    7.56%   1.34x
    late game (move 31+)             672   10.42%    7.99%   1.30x
    snap move (<= 1/3 his own pace)  382    6.02%    8.49%   0.71x

WHAT WAS REFUSED
----------------
- **Moving fast is not a cause. It is protective** (0.71x). "Eyesight" and
  "he rushed" are the same guess and this is the third time the data has
  refused it: the teaching triage had a `rushed` rule that was backwards
  (a 0-1s error is a knowledge gap 21.7% of the time against 6.8% at 30s+),
  and now a snap move is measurably SAFER than a considered one. Do not
  reintroduce it.
- **Tilt**: dead. 62.7 accuracy after a loss against 62.4 after a win, and
  63.2 after three straight losses -- above their own average.
- **Board region / where his attention was**: dead. Errors by file ran
  11.26% / 11.15% / 11.83% in the middlegame and 10.80 / 10.78 / 10.76 in
  the endgame.
- **Very low clock (<15s)** is real at 1.76x but fired on only 7 of 453
  errors. Folded into time pressure rather than claimed separately.

THE CEILING, WHICH MUST STAY VISIBLE
------------------------------------
At least one signal covers 49.7% of errors. **Nothing explains the other
50.3%**, so `not_explained` is a first-class answer and is never dressed up
as one of the others. Saying "you were distracted" because nothing else fit
would be inventing the thing the player would most resent.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Mapping, Optional, Sequence

# Measured 2026-11-27; see the module docstring. NOT locked -- /lock-via-data.
LOW_CLOCK_SECONDS = 60.0
UNRAVEL_PLIES = 3
UNRAVEL_BIG_CP = 200
LATE_GAME_MOVE = 31

# Strongest measured lift first. When several circumstances are true at once
# the strongest one is named, because naming all of them says nothing.
CAUSE_ORDER = ("time_pressure", "unravelling", "late_game")

# Player-facing, no digits (the plan's own rule), and each says what to do.
CAUSE_WORDS = {
    "time_pressure": (
        "Your clock was low",
        "This mostly happens when you are short of time. "
        "Keep enough time to check what your opponent can take."),
    "unravelling": (
        "It follows another mistake",
        "This mostly happens in the moves right after a mistake. "
        "When a move goes wrong, take your time on the next one."),
    "late_game": (
        "Late in the game",
        "This mostly happens deep into a game, when you are moving quickly. "
        "Slow down once the pieces start coming off."),
    "not_explained": (
        "No clear pattern yet",
        "These did not share a moment we can point to. "
        "Nothing to change in how you play yet."),
}


def _median(values: Sequence[float]) -> Optional[float]:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0


def prior_big_error(game_rows: Sequence[Mapping[str, Any]], index: int,
                    plies: int = UNRAVEL_PLIES,
                    big_cp: int = UNRAVEL_BIG_CP) -> bool:
    """Did HE go wrong in the few moves before this one?

    The rows must be one game, his moves, in ply order. Measured elsewhere:
    he loses 85.1cp over the three moves after a big error against 53.2cp
    after a good one, a ratio of 1.60.
    """
    for row in game_rows[max(0, index - plies):index]:
        if (row.get("cp_loss") or 0) >= big_cp:
            return True
    return False


def cause_for_move(row: Mapping[str, Any], *, after_big_error: bool,
                   low_clock_seconds: float = LOW_CLOCK_SECONDS,
                   late_game_move: int = LATE_GAME_MOVE) -> str:
    """The one circumstance to name for a single error, or not_explained.

    Deliberately has no "rushed" branch: a snap move is measurably SAFER
    than a considered one (0.71x). See the module docstring.
    """
    clock = row.get("time_left_seconds")
    if clock is not None and clock < low_clock_seconds:
        return "time_pressure"
    if after_big_error:
        return "unravelling"
    move_no = row.get("move_number")
    if move_no is not None and move_no >= late_game_move:
        return "late_game"
    return "not_explained"


def reading(error_rows_by_game: Mapping[str, Sequence[Mapping[str, Any]]],
            fired_keys: Sequence[tuple]) -> Optional[Dict[str, Any]]:
    """The circumstance behind a set of errors, or None when there are none.

    `error_rows_by_game` is every one of his moves per game, in ply order, so
    the move BEFORE an error can be read. `fired_keys` are the
    (game_id, ply) pairs where the detector fired.

    Returns the dominant cause with its share, every cause counted, and the
    unexplained count -- which is never hidden and may well be the largest.
    """
    fired = set(fired_keys)
    causes: List[str] = []
    clocks: List[float] = []
    for game_id, rows in error_rows_by_game.items():
        for i, row in enumerate(rows):
            if (game_id, row.get("ply")) not in fired:
                continue
            causes.append(cause_for_move(
                row, after_big_error=prior_big_error(rows, i)))
            if row.get("time_left_seconds") is not None:
                clocks.append(row["time_left_seconds"])
    if not causes:
        return None

    counts = Counter(causes)
    explained = [c for c in CAUSE_ORDER if counts.get(c)]
    # The dominant cause is the commonest EXPLAINED one, and it is only
    # claimed when it covers more of the errors than "we cannot say".
    top = max(explained, key=lambda c: counts[c]) if explained else None
    unexplained = counts.get("not_explained", 0)
    if top is None or counts[top] <= unexplained:
        top = "not_explained"
    title, text = CAUSE_WORDS[top]
    return {
        "cause": top,
        "title": title,
        "text": text,
        # Counts stay here; the player-facing sentences carry no digits.
        "measured": {
            "errors": len(causes),
            "by_cause": dict(counts),
            "unexplained": unexplained,
            "median_clock_seconds": _median(clocks),
        },
    }


# ---------------------------------------------------------------------------
# Tracked behaviour axes
#
# Mohit, 2026-11-27: "chess is just not calculation and tactics, chess is also
# focus and behavioral tactics, so that's what we want to track."
#
# Each axis is a rate out of chances, from a pair of booleans that
# move_observations already carries at 100% coverage. They are TRACKED, not
# used as drill gates, and that is a measured decision rather than a
# preference. Per-user rates over the last ten games, 2026-11-27:
#
#   axis                        users  p25  median  max   at/above a 25% bar
#   kept pieces safe               65   4%     6%   30%   4 of 65
#   answered their threat          59  26%    32%   64%  46 of 59
#   punished their mistake         10  41%    54%   68%   9 of 10
#   found it when it mattered      62  87%    94%  100%  62 of 62
#
# So the 25% drill bar is calibrated to piece safety and transfers to none of
# the others: it would drill almost everyone, which is the opposite of the
# rule it came from. `found it when it mattered` has a 94% median -- missing
# the best move at a critical moment is near-universal, so it measures being
# human, not a weakness, and must never be shown as a fault.
#
# Each axis's bar now comes from its OWN distribution, per level: see
# PEER_RATES and `worse_than_peers` below. No axis carries a bare absolute
# rate any more except the one Mohit set by hand, which stays exactly where
# he put it.
AXES = {
    "axis:piece_safety": {
        "title": "Keeping pieces safe",
        "good": "Your pieces stayed safe",
        # This one is the structured verdict, counted in player_coach_file.
        "pair": None,
        "peer_key": "gap:piece_safety:destination_safety_exact",
    },
    "axis:threat_answered": {
        "title": "Answering their threats",
        "good": "You answered what they threatened",
        "pair": ("ignored_opponent_threat", "responded_to_threat"),
        "peer_key": "axis:threat_answered",
    },
    "axis:punished_their_mistake": {
        "title": "Punishing their mistakes",
        "good": "You took what they gave you",
        "pair": ("missed_opponent_blunder", "punished_opponent_blunder"),
        "peer_key": "axis:punished_their_mistake",
    },
}

# Deliberately NOT an axis: was_critical_moment / found_best_in_critical.
# 94% median across 62 users. A number everyone fails is not a weakness, and
# showing it would read as "you are bad at chess".
NOT_AN_AXIS = ("found_best_in_critical",)


# ---------------------------------------------------------------------------
# "Does he still need this drill?" -- calibrated, per axis, per level
#
# Mohit, 2026-11-27: "if that is 25%, player still need to do the drill, if
# that's less than 25%, then we would try to understand why this error
# existed". He set 25% for one-move piece blunders, and it is right there:
# it picks 4 of 65 users. Transferred to the other axes it drilled 48 of 59
# and 40 of 43, which is the opposite of the rule.
#
# So the bar is now his absolute rate OR "clearly worse than players at his
# own level", whichever fires -- the second being a one-sided binomial test
# of his count against the measured rate for his rating band. Measured
# 2026-11-27 on prod, 65 users with 10+ analysed games, server-side $group:
#
#   axis                 window  pooled  beginner_low  beginner_high  intermediate
#   piece safety            10g    8.0%        14.4%          6.7%          2.7%
#   threats answered        10g   32.1%        39.2%         31.8%         26.4%
#   punished mistakes       20g   41.0%        45.7%         35.8%          -
#
# Piece safety moves 6.8x across the bands (14.4% -> 2.1%), so a pooled peer
# rate would tell a beginner he is "worse than peers" for being ordinary at
# his level -- Mohit's Magnus objection, inverted. Banding is not a
# refinement here, it is the difference between right and wrong.
#
# The advanced band (1800+) had 7 users or fewer on every axis, so it is
# absent below and falls back to pooled. MIN_BAND_USERS records the bar that
# excluded it; it is not applied at runtime.
#
# WHAT THIS RULE DOES TO MOHIT'S 25%, measured on the same 65 users:
#   piece safety      keeps all 4 that 25% picked, and adds 2 below it
#                     (19% against a 6.7% band, p=8.6e-04; 11% against
#                      2.7%, p=8.8e-03) -- both genuinely worse than peers
#   threats           4 of 59 instead of 48
#   punished          2 of 43 instead of 40
# So it is strictly more inclusive where he set it and sane where he did not.
#
# NOT locked -- /lock-via-data. Re-measure with calibrate_axis_bars2.py.
MIN_CHANCES = 20            # a rate under this is not read at all
PEER_ALPHA = 0.05           # one-sided; 0.10 would add 4 users on piece safety
MIN_BAND_USERS = 8          # how the bands below were admitted, not a runtime gate

PEER_RATES = {
    "gap:piece_safety:destination_safety_exact": {
        "window_games": 10,
        "absolute_bar": 0.25,        # Mohit's, and only here
        "pooled": 0.080,
        "bands": {"beginner_low": 0.144, "beginner_high": 0.067,
                  "intermediate": 0.027},
    },
    "axis:threat_answered": {
        "window_games": 10,
        "absolute_bar": None,
        "pooled": 0.321,
        "bands": {"beginner_low": 0.392, "beginner_high": 0.318,
                  "intermediate": 0.264},
    },
    "axis:punished_their_mistake": {
        # 1.3 chances a game: ten games reach the minimum for 10 of 65 users,
        # twenty games for 43 of 59. The axis is silent at Mohit's ten-game
        # window, so it reads twenty and says so.
        "window_games": 20,
        "absolute_bar": None,
        "pooled": 0.410,
        "bands": {"beginner_low": 0.457, "beginner_high": 0.358},
    },
    # Measured 2026-11-28 with calibrate_opportunity_bars.py, same 65 users,
    # 54,919 moves judged by services.tactic_opportunity off `fen_before`.
    # Inert until the detector earns a grade above shadow: nothing calls
    # needs_drill() with this key yet, and detector_quality forbids a shadow
    # id from reaching a plan. The numbers are here because MEASURING them is
    # the expensive half, not because the axis is live.
    #
    # THE BASIS IS `coachable`, NOT THE BOARD MISS. Both were measured:
    #
    #   basis                      pooled   b_low  b_high  inter   drills
    #   fires     (board only)      35.4%   39.2%  33.6%   32.6%   1 of 58
    #   coachable (engine agrees)    9.3%   13.6%   7.2%    4.2%   4 of 58
    #
    # The board miss rate is NOT usable as an axis and must not become one.
    # It sits near 35% for everyone, its bands move 1.2x, and the binomial
    # drills 1 of 58 users at twenty games (0 of 61 at fifteen) while a flat
    # 25% bar would drill 52. That is found_best_in_critical again: a number
    # everyone fails cannot separate anyone, and showing it reads as "you are
    # bad at chess". The reason is known and is not noise -- 39.9% of v1 fires
    # were on the engine's own best move, so `fires` counts "he found
    # something better" as a miss.
    #
    # `coachable` adds the engine witness (not the best move, labelled an
    # error, >=100cp) and behaves: bands move 3.2x, monotone across the three
    # usable ones, and the test drills 4 of 58 where the 25% bar drills 1 --
    # strictly more inclusive, the same signature the other three axes have.
    #
    # Window 20 games. Chances arrive 2.4 a game, so the minimum of 20 is
    # reached by 41 of 65 users at ten games, 61 of 63 at fifteen, 58 of 59 at
    # twenty. Ten is too thin to judge a third of the corpus; twenty costs 3
    # users against fifteen and buys the power that finds 4 players instead
    # of 2 (one of them 8/59 = 14% against a 4.2% band, p=2.9e-03, whom no
    # absolute bar would ever catch).
    #
    # The advanced band measured 7.7% on 7 users, below MIN_BAND_USERS, so it
    # pools -- same exclusion the three axes above make.
    "gap:missed_tactic:free_material": {
        "window_games": 20,
        "absolute_bar": None,          # Mohit set 25% for piece safety only
        "pooled": 0.093,
        "bands": {"beginner_low": 0.136, "beginner_high": 0.072,
                  "intermediate": 0.042},
    },
    # gap:missed_tactic:mate_in_one is deliberately ABSENT. One user of 65
    # reached 20 chances in ten games and two of 55 in thirty: 0.27 chances a
    # game cannot be a per-player rate at any window this product reads. It
    # stays a corpus-level fact, not an axis.
}


def window_games(key: str, default: int = 10) -> int:
    """How many games this axis needs to have anything to say."""
    spec = PEER_RATES.get(key)
    return int(spec["window_games"]) if spec else default


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Bin(n, p). One-sided: is he worse than his peers?

    Exact rather than normal-approximated, because the counts are small
    (20 to 60 chances) and the rates near 0.03, where the approximation is
    worst and would invent significance.
    """
    if k <= 0:
        return 1.0
    if n <= 0 or k > n:
        return 0.0 if k > n else 1.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    from math import comb
    return sum(comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i))
               for i in range(k, n + 1))


def peer_rate(key: str, band: Optional[str] = None) -> Optional[float]:
    """The measured rate for players at his level, or pooled when thin."""
    spec = PEER_RATES.get(key)
    if not spec:
        return None
    if band and band in (spec.get("bands") or {}):
        return spec["bands"][band]
    return spec.get("pooled")


def worse_than_peers(key: str, wrong: int, chances: int,
                     band: Optional[str] = None,
                     alpha: float = PEER_ALPHA) -> Optional[Dict[str, Any]]:
    """Is his rate worse than players at his level by more than luck?

    None when there is no calibration, too few chances, or he is in line with
    his level. Never guesses: an axis with no measured peer rate returns None
    rather than falling back to a number someone liked.
    """
    spec = PEER_RATES.get(key)
    if not spec or chances < MIN_CHANCES:
        return None
    peer = peer_rate(key, band)
    if peer is None:
        return None
    p = binom_sf(wrong, chances, peer)
    if p > alpha:
        return None
    return {"peer_rate": round(peer, 4), "band": band, "p_value": p,
            "rate": round(wrong / chances, 4), "basis": "worse_than_level"}


def needs_drill(key: str, wrong: int, chances: int,
                band: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Mohit's rule, calibrated: his absolute bar OR worse than his level.

    Returns why it fired, or None when the drill is not owed. The absolute
    bar is kept first and separately so his instruction survives a
    re-measurement of the bands.
    """
    if chances < MIN_CHANCES:
        return None
    spec = PEER_RATES.get(key)
    if not spec:
        return None
    rate = wrong / chances
    bar = spec.get("absolute_bar")
    if bar is not None and rate >= bar:
        return {"rate": round(rate, 4), "absolute_bar": bar,
                "basis": "at_or_above_absolute_bar"}
    return worse_than_peers(key, wrong, chances, band)


def axis_rates(rows: Sequence[Mapping[str, Any]],
               game_order: Optional[Sequence[str]] = None,
               band: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Chances and wrong turns per tracked axis, each over its OWN window.

    `game_order` is his games newest first. Each axis then counts only the
    games it needs: ten for piece safety and threats, twenty for punishing
    mistakes, which offers 1.3 chances a game and is simply silent at ten
    (10 of 65 users reached the minimum, against 43 of 59 at twenty). Pass
    None to count every row given, which is what the callers did before the
    windows were measured.

    `band` is his rating band. Given one, each axis also carries whether the
    drill is owed -- his absolute bar, or measurably worse than players at
    his level. Without one the rate is still reported; it just does not
    judge, because the pooled comparison is the wrong comparison (piece
    safety runs 14.4% in the beginner band against 2.7% at intermediate).
    """
    rows = list(rows)
    order = list(game_order) if game_order else None
    out: Dict[str, Dict[str, Any]] = {}
    for key, spec in AXES.items():
        pair = spec.get("pair")
        if not pair:
            continue
        peer_key = spec.get("peer_key") or key
        scoped = rows
        window = None
        if order is not None:
            window = window_games(peer_key)
            keep = set(order[:window])
            scoped = [r for r in rows if r.get("game_id") in keep]
        wrong_field, right_field = pair
        wrong = sum(1 for r in scoped if r.get(wrong_field))
        right = sum(1 for r in scoped if r.get(right_field))
        chances = wrong + right
        if not chances:
            continue
        row = {"title": spec["title"], "chances": chances, "wrong": wrong,
               "rate": round(wrong / chances, 4)}
        if window is not None:
            row["window_games"] = window
        peer = peer_rate(peer_key, band)
        if peer is not None:
            row["peer_rate"] = round(peer, 4)
            row["band"] = band
        if band:
            owed = needs_drill(peer_key, wrong, chances, band)
            row["needs_drill"] = bool(owed)
            if owed:
                row["why_drill"] = owed
            elif chances < MIN_CHANCES:
                # Not "he is fine" -- we have not seen enough to say.
                row["needs_drill"] = None
                row["too_few_chances"] = MIN_CHANCES
        out[key] = row
    return out

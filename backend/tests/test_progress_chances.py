"""The /progress chance rows.

Guards the three things that made the old page unusable, so they cannot
come back by accident:

  1. no flag — the old page's only source was the phase-8 gate, which
     returned enabled=0 for all 139 production users;
  2. every row has a denominator, and a row with no chances says so rather
     than reporting a rate of zero;
  3. no verdict words anywhere.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.progress_chances import (  # noqa: E402
    ALL_TIME_ONLY,
    build_pipeline,
    build_progress_chances,
)


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, *_a, **_k):
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    async def to_list(self, _n):
        return self._rows


class _Collection:
    def __init__(self, rows=None, count=0, agg=None):
        self._rows = rows or []
        self._count = count
        self._agg = agg or []

    def find(self, *_a, **_k):
        return _Cursor(list(self._rows))

    async def count_documents(self, *_a, **_k):
        return self._count

    def aggregate(self, _pipeline):
        return _Cursor(list(self._agg))


class _DB:
    def __init__(self, games, observations):
        self.games = games
        self.move_observations = observations


def _db(agg_row, game_ids=("g1", "g2"), analysed=12):
    return _DB(
        games=_Collection(rows=[{"game_id": g} for g in game_ids], count=analysed),
        observations=_Collection(agg=[agg_row] if agg_row else []),
    )


FULL = {
    "observations": 2000,
    "safety_chances": 300,
    "safety_missed": 12,
    "threat_answered": 120,
    "threat_ignored": 60,
    "punish_took": 30,
    "punish_missed": 20,
    "recent_safety_chances": 50,
    "recent_safety_missed": 1,
    "recent_threat_answered": 18,
    "recent_threat_ignored": 6,
}


def test_counts_what_was_kept_not_what_fired():
    """`fires` is the MISS. "Kept safe" is the eligible decisions it did not
    fire on, and getting this backwards would invert the whole page."""
    out = asyncio.run(build_progress_chances(_db(FULL), "u1"))
    safety = next(a for a in out["axes"] if a["key"] == "piece_safety")
    assert safety["took"] == 288          # 300 eligible - 12 fired
    assert safety["chances"] == 300
    assert safety["recent"]["took"] == 49  # 50 - 1
    assert safety["recent"]["chances"] == 50


def test_each_axis_is_out_of_its_own_chances():
    out = asyncio.run(build_progress_chances(_db(FULL), "u1"))
    by_key = {a["key"]: a for a in out["axes"]}
    assert by_key["threats"]["took"] == 120
    assert by_key["threats"]["chances"] == 180      # answered + ignored
    assert by_key["punished"]["chances"] == 50      # took + missed
    for axis in out["axes"]:
        assert axis["chances"] >= axis["took"] >= 0


def test_punished_has_no_recent_column():
    """~0.7 chances a game, so ten games give about seven. Seven chances
    must not be drawn as a rate."""
    out = asyncio.run(build_progress_chances(_db(FULL), "u1"))
    by_key = {a["key"]: a for a in out["axes"]}
    assert "recent" not in by_key["punished"]
    assert "punished" in ALL_TIME_ONLY
    assert "recent" in by_key["piece_safety"]


def test_a_player_with_nothing_says_so_rather_than_scoring_zero():
    out = asyncio.run(build_progress_chances(_db(None, game_ids=(), analysed=0), "new"))
    assert out["has_evidence"] is False
    assert out["analysed_games"] == 0
    for axis in out["axes"]:
        assert axis["chances"] == 0
        assert axis["rate"] is None          # not 0.0 — there was no chance


def test_an_axis_with_no_chances_this_week_has_no_rate():
    quiet = dict(FULL, recent_safety_chances=0, recent_safety_missed=0)
    out = asyncio.run(build_progress_chances(_db(quiet), "u1"))
    safety = next(a for a in out["axes"] if a["key"] == "piece_safety")
    assert safety["recent"]["chances"] == 0
    assert safety["recent"]["rate"] is None
    assert safety["chances"] == 300          # all-time is untouched


def test_it_is_behind_no_flag_at_all():
    """The page this feeds replaced one whose only source was the phase-8
    gate. That gate returned enabled=0 for every user in production."""
    out = asyncio.run(build_progress_chances(_db(FULL), "u1"))
    assert out["enabled"] is True
    assert "paused" not in out
    assert "reason" not in out


def test_it_never_says_better_worse_or_mastered():
    import json

    out = asyncio.run(build_progress_chances(_db(FULL), "u1"))
    text = json.dumps(out).lower()
    for word in ["better", "worse", "improv", "master", "score", "grade"]:
        assert word not in text, f"the page must not say {word!r}"


def test_found_best_in_critical_is_not_returned():
    """r=+0.50 with rating, so the data is the best of the four -- but the
    human range is 1.7% to 13.1%, so an absolute count reads as "you are bad
    at chess" to everybody. It returns relative to level, or coach-side."""
    import json

    out = asyncio.run(build_progress_chances(_db(FULL), "u1"))
    assert "critical" not in json.dumps(out).lower()


def test_the_recent_window_rides_in_the_same_pass():
    """move_observations has 765,780 documents and no (user_id, game_id)
    index, so a second windowed query measured 2,212ms against 243ms for an
    aggregate. Both columns come from one $group."""
    pipeline = build_pipeline("u1", ["g1", "g2"])
    assert len(pipeline) == 2
    assert pipeline[0]["$match"] == {"user_id": "u1"}
    group = pipeline[1]["$group"]
    assert any(k.startswith("recent_") for k in group)
    # every recent_ field is computed in that same group, not fetched again
    assert group["recent_safety_chances"]["$sum"]["$cond"][0]["$and"][0] == {
        "$in": ["$game_id", ["g1", "g2"]]
    }


def test_no_analysed_games_makes_the_window_a_constant_false():
    pipeline = build_pipeline("u1", [])
    group = pipeline[1]["$group"]
    assert group["recent_safety_chances"]["$sum"]["$cond"][0]["$and"][0] is False

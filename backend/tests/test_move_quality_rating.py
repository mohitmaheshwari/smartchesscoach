"""
Move-quality rating scorer (docs/move_quality_rating_scope.md).

Locks the pure core: move-weighted EWMA of accuracy -> a rating BAND, with a
min-games gate, recency weighting, honest band width, and clamping.

Run:  python -m pytest tests/test_move_quality_rating.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.move_quality_rating import (
    move_quality_from_series,
    _map_accuracy_to_rating,
    MIN_GAMES,
    RATING_MIN,
    RATING_MAX,
)


def _series(accs, weight=10):
    # dates as zero-padded indices so sort order == input order
    return [{"date": f"{i:03d}", "accuracy": a, "weight": weight} for i, a in enumerate(accs)]


def test_below_min_games_returns_none():
    assert move_quality_from_series(_series([60] * (MIN_GAMES - 1))) is None
    assert move_quality_from_series(_series([60] * MIN_GAMES)) is not None


def test_constant_accuracy_maps_through_the_fit():
    r = move_quality_from_series(_series([60] * 10))
    assert r["rating"] == _map_accuracy_to_rating(60) == 1076
    assert r["display"].startswith("~")
    assert r["range_low"] < r["rating"] < r["range_high"]


def test_recency_pulls_toward_recent_form():
    # 15 weak games then 15 strong games — the rating must lean toward the recent
    # strong ones, i.e. above the simple midpoint accuracy of 56.5.
    r = move_quality_from_series(_series([45] * 15 + [68] * 15))
    assert r["weighted_accuracy"] > 56.5
    assert r["rating"] > _map_accuracy_to_rating(45)


def test_band_is_wider_with_fewer_games():
    few = move_quality_from_series(_series([60] * MIN_GAMES))
    many = move_quality_from_series(_series([60] * 50))
    width_few = few["range_high"] - few["range_low"]
    width_many = many["range_high"] - many["range_low"]
    assert width_few > width_many  # honest: rougher estimate -> wider band


def test_clamps_to_sane_rating_range():
    assert move_quality_from_series(_series([95] * 10))["rating"] == RATING_MAX
    assert move_quality_from_series(_series([40] * 10))["rating"] == RATING_MIN


def test_move_weighting_lets_a_heavy_recent_game_dominate():
    # four tiny weak games + one big strong game, most recent -> accuracy near 80
    games = _series([50, 50, 50, 50], weight=1)
    games.append({"date": "099", "accuracy": 80, "weight": 500})
    r = move_quality_from_series(games)
    assert r["weighted_accuracy"] > 65


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

"""Regression tests for the PWC prediction + self-rating core logic (built 2026-06-10 overnight).

Pure logic only (no DB, no Stockfish, no network) — fast + deterministic. Covers:
  services/predict_coach_move.py  — should_fire, build_options, prediction_log_row
  services/rate_your_move.py      — quality_bucket, rating_correct, is_instructive

Run: python -m pytest backend/tests/test_predict_rate.py   (or python backend/tests/test_predict_rate.py)
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.predict_coach_move import (
    should_fire, build_options, prediction_log_row, difficulty_for, band_of,
)
from services.rate_your_move import quality_bucket, rating_correct, is_instructive


# ── predict_coach_move ─────────────────────────────────────────────────────
def test_should_fire_is_deliberately_disabled():
    """2026-06-26 Coach Conductor LAW 1 ("state, never ask"): Call-My-Move is
    parked — should_fire returns False unconditionally, BY DESIGN, until Mohit
    decides revive-or-remove (his 2026-07-14 call: keep as-is). This test locks
    the PARKED state so an accidental re-enable fails loudly; the clear-best
    firing logic is preserved below the early return for the future opt-in."""
    G = 200
    # Every combination — including the ones that used to fire — must be False.
    assert should_fire(1, G, 5, 0, 900) is False
    assert should_fire(1, G, 5, 0, 1500) is False
    assert should_fire(2, G, 5, 0, 900) is False
    assert should_fire(1, None, 5, 0, 900) is False


def test_bands():
    assert band_of(900) == "beginner"
    assert band_of(1200) == "improver"
    assert band_of(1500) == "intermediate"
    assert band_of(None) == "beginner"
    assert difficulty_for(900) == "easy"
    assert difficulty_for(1500) == "hard"


def test_build_options_always_includes_coach_move():
    mpv = [("e5", -37), ("c5", -39), ("e6", -40), ("d6", -90)]
    rng = random.Random(1)
    hard = build_options(mpv, "e5", 1500, 3, rng)
    assert "e5" in hard and len(hard) == 3
    assert "d6" not in hard                            # hard -> closest decoys, drops the far d6
    easy = build_options(mpv, "e5", 900, 3, random.Random(1))
    assert "e5" in easy and "d6" in easy               # easy -> furthest decoy included
    assert build_options(mpv, "Qh5", 1500, 3) == []    # coach move not in multipv -> no clean set


def test_prediction_log_row_correct_flag():
    miss = prediction_log_row("s", "u", 12, "fen", ["e5", "c5"], "e5", "c5", 900, "easy", "r", 0)
    assert miss["correct"] is False
    hit = prediction_log_row("s", "u", 12, "fen", ["e5", "c5"], "e5", "e5", 900, "easy", "r", 0)
    assert hit["correct"] is True


# ── rate_your_move ─────────────────────────────────────────────────────────
def test_quality_buckets():
    assert quality_bucket("best") == "good"
    assert quality_bucket("good") == "good"
    assert quality_bucket("inaccuracy") == "inaccuracy"
    assert quality_bucket("mistake") == "mistake_blunder"
    assert quality_bucket("blunder") == "mistake_blunder"
    assert quality_bucket("???") == "good"             # unknown defaults safe


def test_rating_correct():
    assert rating_correct("mistake_blunder", "blunder") is True
    assert rating_correct("good", "best") is True
    assert rating_correct("good", "blunder") is False
    assert rating_correct("inaccuracy", "inaccuracy") is True


def test_is_instructive():
    assert is_instructive("blunder") is True
    assert is_instructive("best") is True
    assert is_instructive("good") is False
    assert is_instructive("inaccuracy") is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

"""
Unit tests for the daily PRACTICE streak (Daily Fix — docs/daily_fix_scope.md).

Pure/deterministic logic, no DB required. Covers every branch of
apply_practice_completion() and practice_streak_view(), including the
1-grace-day forgiveness rule signed off 2026-06-29.

Run:  python tests/test_practice_streak.py      (from backend/)
  or: python -m pytest tests/test_practice_streak.py
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.mistake_streak_service import (  # noqa: E402
    apply_practice_completion,
    practice_streak_view,
    _default_practice_streak,
    PRACTICE_STREAK_MAX_GAP_DAYS,
)

D = date  # alias


# ----------------------------------------------------------------------------
# apply_practice_completion
# ----------------------------------------------------------------------------

def test_first_completion_starts_at_one():
    ps = apply_practice_completion(None, D(2026, 6, 29))
    assert ps["current"] == 1
    assert ps["best"] == 1
    assert ps["last_practice_date"] == "2026-06-29"
    assert ps["started_at"] == "2026-06-29"
    assert ps["grace_used"] is False


def test_same_day_is_idempotent():
    ps = apply_practice_completion(None, D(2026, 6, 29))
    ps2 = apply_practice_completion(ps, D(2026, 6, 29))
    assert ps2["current"] == 1  # not 2 — never double-counts one day
    assert ps2["best"] == 1
    assert ps2["last_practice_date"] == "2026-06-29"


def test_consecutive_days_increment():
    ps = apply_practice_completion(None, D(2026, 6, 29))
    ps = apply_practice_completion(ps, D(2026, 6, 30))
    ps = apply_practice_completion(ps, D(2026, 7, 1))
    assert ps["current"] == 3
    assert ps["best"] == 3
    assert ps["grace_used"] is False


def test_one_missed_day_is_forgiven_and_uses_grace():
    ps = apply_practice_completion(None, D(2026, 6, 29))  # 1
    ps = apply_practice_completion(ps, D(2026, 6, 30))     # 2
    # skip Jul 1, complete Jul 2 -> gap of 2 days -> forgiven
    ps = apply_practice_completion(ps, D(2026, 7, 2))
    assert ps["current"] == 3
    assert ps["grace_used"] is True
    assert ps["last_practice_date"] == "2026-07-02"


def test_grace_refreshes_after_a_clean_day():
    ps = apply_practice_completion(None, D(2026, 6, 29))  # 1
    ps = apply_practice_completion(ps, D(2026, 7, 1))      # gap2 -> 2, grace used
    assert ps["grace_used"] is True
    ps = apply_practice_completion(ps, D(2026, 7, 2))      # consecutive -> 3, grace refreshed
    assert ps["current"] == 3
    assert ps["grace_used"] is False


def test_two_missed_days_resets_to_one():
    ps = apply_practice_completion(None, D(2026, 6, 29))  # 1
    ps = apply_practice_completion(ps, D(2026, 6, 30))     # 2
    ps = apply_practice_completion(ps, D(2026, 7, 1))      # 3
    # skip Jul 2 and Jul 3, complete Jul 4 -> gap of 3 -> reset
    ps = apply_practice_completion(ps, D(2026, 7, 4))
    assert ps["current"] == 1
    assert ps["best"] == 3          # best is preserved
    assert ps["started_at"] == "2026-07-04"
    assert ps["grace_used"] is False


def test_best_preserved_across_reset_and_rebuild():
    ps = None
    for d in [D(2026, 6, 1), D(2026, 6, 2), D(2026, 6, 3), D(2026, 6, 4)]:
        ps = apply_practice_completion(ps, d)
    assert ps["best"] == 4
    ps = apply_practice_completion(ps, D(2026, 6, 20))  # big gap -> reset to 1
    assert ps["current"] == 1
    assert ps["best"] == 4


def test_accepts_iso_string_and_datetime_inputs():
    ps = apply_practice_completion(None, "2026-06-29")
    ps = apply_practice_completion(ps, "2026-06-30T14:03:00+00:00")
    assert ps["current"] == 2


def test_invalid_today_raises():
    try:
        apply_practice_completion(None, "not-a-date")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ----------------------------------------------------------------------------
# practice_streak_view
# ----------------------------------------------------------------------------

def test_view_new_user_is_zero_and_not_at_risk():
    v = practice_streak_view(None, D(2026, 6, 29))
    assert v["current"] == 0
    assert v["done_today"] is False
    assert v["at_risk"] is False


def test_view_done_today():
    ps = apply_practice_completion(None, D(2026, 6, 29))
    v = practice_streak_view(ps, D(2026, 6, 29))
    assert v["done_today"] is True
    assert v["at_risk"] is False
    assert v["current"] == 1


def test_view_not_at_risk_with_one_day_buffer():
    # completed yesterday, today not done -> gap 1 -> still a full buffer, not yet at risk
    ps = apply_practice_completion(None, D(2026, 6, 28))
    v = practice_streak_view(ps, D(2026, 6, 29))
    assert v["current"] == 1
    assert v["done_today"] is False
    assert v["at_risk"] is False


def test_view_at_risk_at_edge_of_grace():
    # completed 2 days ago, today not done -> gap 2 -> one more miss breaks it -> at risk
    ps = apply_practice_completion(None, D(2026, 6, 27))
    v = practice_streak_view(ps, D(2026, 6, 29))
    assert v["current"] == 1
    assert v["at_risk"] is True


def test_view_stale_streak_shows_zero_not_at_risk():
    # completed 3 days ago -> beyond grace -> streak already gone -> not "at risk", it's lost
    ps = apply_practice_completion(None, D(2026, 6, 26))
    v = practice_streak_view(ps, D(2026, 6, 29))
    assert v["current"] == 0
    assert v["at_risk"] is False


def test_gap_constant_is_two():
    assert PRACTICE_STREAK_MAX_GAP_DAYS == 2


def test_default_shape():
    d = _default_practice_streak()
    assert set(d.keys()) == {"current", "best", "last_practice_date", "started_at", "grace_used"}


# ----------------------------------------------------------------------------
# runner
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{passed + failed} passed"
          + (f", {failed} FAILED" if failed else " — all green"))
    sys.exit(1 if failed else 0)

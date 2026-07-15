"""
Unit tests for the Daily Fix reminder targeting + compose logic.
Pure, no DB. Run: python tests/test_daily_fix_reminder.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.daily_fix_reminder import compose_reminder, _classify, _first_name  # noqa: E402


def v(current=0, at_risk=False, done_today=False):
    return {"current": current, "at_risk": at_risk, "done_today": done_today}


def test_classify_done_today_skips():
    assert _classify(v(current=5, done_today=True)) is None


def test_classify_no_streak_skips():
    assert _classify(v(current=0)) is None


def test_classify_at_risk():
    assert _classify(v(current=3, at_risk=True)) == "streak_at_risk"


def test_classify_mid_streak_is_fix_ready():
    assert _classify(v(current=3, at_risk=False)) == "fix_ready"


def test_compose_streak_at_risk():
    m = compose_reminder("streak_at_risk", v(current=6, at_risk=True), "Alex", "https://x/home")
    assert "6-day streak" in m["subject"]
    assert "Alex" in m["html"]
    assert "https://x/home" in m["html"]
    assert "Do today's fix" in m["html"]


def test_compose_fix_ready():
    m = compose_reminder("fix_ready", v(current=2), "Sam", "https://x/home")
    assert m["subject"] == "Your daily fix is ready"
    assert "Sam" in m["html"]


def test_compose_has_no_chess_jargon():
    # voice rule: plain English for 600-1500, no jargon
    m = compose_reminder("streak_at_risk", v(current=4, at_risk=True), "Jo", "https://x/home")
    blob = (m["subject"] + m["html"]).lower()
    for jargon in ("fianchetto", "zwischenzug", "prophylaxis", "tempo", "zugzwang"):
        assert jargon not in blob


def test_first_name_extraction():
    assert _first_name({"display_name": "mohit.bhutra"}) == "Mohit"
    assert _first_name({"email": "alex_k@x.com"}) == "Alex"
    assert _first_name({}) == "there"


if __name__ == "__main__":
    tests = [x for k, x in sorted(globals().items()) if k.startswith("test_") and callable(x)]
    p = f = 0
    for t in tests:
        try:
            t(); p += 1; print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            f += 1; print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            f += 1; print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{p}/{p+f} passed" + (f", {f} FAILED" if f else " — all green"))
    sys.exit(1 if f else 0)

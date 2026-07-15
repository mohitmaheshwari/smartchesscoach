"""
Unit tests for the rush-test drill shaping (time_management drill type).
Pure logic, no DB. Run: python tests/test_rush_test_drill.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.rush_test_drill import (  # noqa: E402
    rush_teaching_line,
    shape_rush_drill_item,
)

OBS = {
    "fen_before": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1",
    "move_uci": "f3g5",
    "time_spent_seconds": 2.3,
    "time_left_seconds": 233.8,
    "cp_loss": -280,
    "game_id": "g1",
    "move_number": 7,
}
BEST = {"best_move": "O-O", "best_move_uci": "e1g1"}


def test_teaching_line_sub_second():
    line = rush_teaching_line(0.8, -300)
    assert "about a second" in line
    assert "Slow down" in line


def test_teaching_line_n_seconds():
    line = rush_teaching_line(2.3, -280)
    assert "2 seconds" in line  # rounds 2.3 -> 2


def test_teaching_line_handles_missing_time():
    line = rush_teaching_line(None, None)
    assert "quickly" in line and "Slow down" in line


def test_teaching_line_never_names_the_move():
    # voice rule: don't lead with SAN; the position is the lesson
    line = rush_teaching_line(2.3, -280)
    for token in ("Ng5", "O-O", "f3g5", "e1g1"):
        assert token not in line


def test_shape_valid_item():
    item = shape_rush_drill_item(OBS, BEST)
    assert item is not None
    assert item["drill_type"] == "rush_test"
    assert item["fen"] == OBS["fen_before"]
    assert item["solution_uci"] == "e1g1"
    assert item["solution_san"] == "O-O"
    assert item["played_uci"] == "f3g5"
    assert item["time_spent_seconds"] == 2.3
    assert item["teaching"]  # non-empty


def test_shape_skips_without_fen():
    obs = dict(OBS)
    obs["fen_before"] = None
    assert shape_rush_drill_item(obs, BEST) is None


def test_shape_skips_ungradeable():
    # no best move -> can't grade -> must not ship the drill
    assert shape_rush_drill_item(OBS, {}) is None
    assert shape_rush_drill_item(OBS, None) is None


def test_shape_accepts_uci_only_best():
    item = shape_rush_drill_item(OBS, {"best_move_uci": "e1g1"})
    assert item is not None
    assert item["solution_uci"] == "e1g1"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1; print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1; print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1; print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{passed+failed} passed" + (f", {failed} FAILED" if failed else " — all green"))
    sys.exit(1 if failed else 0)

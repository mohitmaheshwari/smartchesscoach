"""A position the engine already answers is never sent to a model (2026-11-11)."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import why_study  # noqa: E402


def _packet(played_cp, better_cp, played="e6", better="Kd8"):
    return {"played_san": played, "better_san": better,
            "after_played": {"best_replies_cp_for_mover": [{"san": "x", "cp": played_cp, "line": []}]},
            "after_better": {"best_replies_cp_for_mover": [{"san": "x", "cp": better_cp, "line": []}]}}


def test_no_real_gap_is_no_lesson_without_a_model():
    why = why_study.settled_before_the_model(_packet(-20, -12), rating=1200)
    assert why and "no real improvement" in why


def test_a_real_gap_goes_to_the_model():
    assert why_study.settled_before_the_model(_packet(-36, 96, "e5", "c3"), rating=912) is None   # e5, a true lesson


def test_a_lost_side_can_still_have_a_lesson():
    # 14...Ke7: lost either way, but Ke7 loses a whole extra bishop. Must reach the model.
    assert why_study.settled_before_the_model(_packet(-1607, -1307, "Ke7", "Bd6"), rating=912) is None


def test_missing_lines_never_settle():
    assert why_study.settled_before_the_model({"played_san": "e6", "better_san": "Kd8",
                                               "after_played": {}, "after_better": {}}) is None


ENGINE = os.environ.get("STOCKFISH_PATH")


@pytest.mark.skipif(not ENGINE or not Path(ENGINE).exists(), reason="no local engine")
def test_live_engine_settles_two_equal_opening_moves():
    # Positive control on a real board: 1.d4 against 1.e4 is no lesson at any rating band.
    packet = why_study.build_packet(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "d4",
        better_san="e4", depth=16, engine_path=ENGINE)
    assert why_study.settled_before_the_model(packet, rating=1200)

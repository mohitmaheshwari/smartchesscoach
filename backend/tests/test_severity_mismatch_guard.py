"""
Tests for severity_mismatch_guard (2026-06-06, CAPTION_BACKLOG #18).
Validated against real flagged captions: 4 fires / 0 false-fires on a
29-caption control that already names the mistake.
"""
from services.severity_mismatch_guard import is_severity_mismatch


def test_fires_on_positive_framing_of_blunder():
    assert is_severity_mismatch("O-O-O. King is safe; rook joins the game.", 698, True)
    assert is_severity_mismatch("Rxf4. Your queen on c7 is the only piece doing anything.", 8774, True)


def test_not_mismatch_when_severity_acknowledged():
    assert not is_severity_mismatch("Nbd7 is a mistake. Play O-O.", 200, True)
    assert not is_severity_mismatch("gxf4 hangs to Qxh4 winning your rook.", 564, True)


def test_not_mismatch_below_threshold_or_opp_or_empty():
    assert not is_severity_mismatch("d3. Develops the bishop, fights for the center.", 30, True)   # good move
    assert not is_severity_mismatch("King is safe; rook joins the game.", 698, False)              # opp move
    assert not is_severity_mismatch("", 698, True)                                                 # empty != mismatch
    assert not is_severity_mismatch("Qxd4 grabs the free pawn on d4.", 300, True)                  # honest why, no praise


if __name__ == "__main__":
    test_fires_on_positive_framing_of_blunder()
    test_not_mismatch_when_severity_acknowledged()
    test_not_mismatch_below_threshold_or_opp_or_empty()
    print("all severity_mismatch_guard tests passed")

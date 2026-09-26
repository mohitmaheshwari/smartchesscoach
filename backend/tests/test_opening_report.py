"""Lock the opening report to its rules. docs/opening_report_scope.md."""
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.opening_report import (  # noqa: E402
    MIN_GAMES,
    MIN_OPENING_MOVES,
    STRONG_BELOW,
    WEAK_ABOVE,
    band_for,
    build_report,
    classify_opening,
    report_lines,
)

ITALIAN = ["e4", "e5", "Nf3", "Nc6", "Bc4"]
GIUOCO = ITALIAN + ["Bc5"]


def test_a_game_is_classified_by_the_longest_line_it_follows():
    """The shared table answers "which move completed the name". A game needs
    "which opening is this", which is the longest line its moves follow."""
    assert classify_opening(ITALIAN) == "italian_game"
    assert classify_opening(GIUOCO) == "italian_giuoco_piano"


def test_extra_moves_do_not_lose_the_opening():
    """recognize_opening_from_history returns nothing unless the LAST move
    supplied is the one that completes the name, which is why it cannot be
    used here. A whole game must still classify."""
    assert classify_opening(GIUOCO + ["c3", "Nf6", "d4", "exd4"]) == "italian_giuoco_piano"


def test_an_unknown_line_classifies_as_nothing_not_as_a_guess():
    assert classify_opening(["a3", "h6", "a4", "h5"]) is None
    assert classify_opening([]) is None


def test_bands_come_from_the_measured_quartiles():
    assert band_for(STRONG_BELOW - 0.1) == "strong"
    assert band_for(STRONG_BELOW + 0.1) == "middling"
    assert band_for(WEAK_ABOVE - 0.1) == "middling"
    assert band_for(WEAK_ABOVE + 0.1) == "weak"


def test_an_opening_played_twice_is_never_ranked():
    """30% of user-and-opening pairs have one game. A rate over one game is
    noise with a decimal point."""
    rows = [{"opening": "italian_game", "opening_moves": 200, "mistakes": 60}
            for _ in range(MIN_GAMES - 1)]
    report = build_report(rows)
    assert report["openings"] == []
    assert report["not_enough_games"] == 1
    assert report["measured"] is False


def test_enough_games_but_too_few_moves_is_also_refused():
    rows = [{"opening": "italian_game", "opening_moves": 1, "mistakes": 1}
            for _ in range(MIN_GAMES + 3)]
    assert build_report(rows)["openings"] == []


def test_best_and_worst_are_the_ends_of_the_ranking():
    rows = ([{"opening": "london_system", "opening_moves": 20, "mistakes": 0}
             for _ in range(MIN_GAMES)]
            + [{"opening": "kings_gambit_accepted", "opening_moves": 20,
                "mistakes": 6} for _ in range(MIN_GAMES)])
    report = build_report(rows)
    assert report["best"] == "london_system"
    assert report["worst"] == "kings_gambit_accepted"
    assert report["openings"][0]["band"] == "strong"
    assert report["openings"][-1]["band"] == "weak"


def test_no_number_ever_reaches_the_player():
    rows = [{"opening": "italian_game", "opening_moves": 20, "mistakes": 5}
            for _ in range(MIN_GAMES)]
    lines = report_lines(build_report(rows))
    for key, value in lines.items():
        if isinstance(value, str):
            assert not re.search(r"\d", value), (key, value)
            assert "%" not in value


def test_internal_numbers_are_underscored():
    rows = [{"opening": "italian_game", "opening_moves": 20, "mistakes": 5}
            for _ in range(MIN_GAMES)]
    for row in build_report(rows)["openings"]:
        for key, value in row.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                assert key.startswith("_"), key


def test_the_copy_does_not_claim_a_winner():
    """After gating, the thinnest eligible sample is about 130 opening moves,
    so the ORDER of the top few is not stable. "You rarely slip here" survives
    a sample wobble; "your best opening" does not."""
    rows = [{"opening": "london_system", "opening_moves": 20, "mistakes": 0}
            for _ in range(MIN_GAMES)]
    lines = report_lines(build_report(rows))
    assert "best opening" not in lines["best_line"].lower()
    assert "rarely slip" in lines["best_line"].lower()


def test_the_learn_door_opens_only_when_a_tree_exists():
    rows = [{"opening": "giuoco_piano_no_tree", "opening_moves": 20,
             "mistakes": 6} for _ in range(MIN_GAMES)]
    report = build_report(rows)
    assert report_lines(report, teachable=set())["can_learn_worst"] is False
    assert report_lines(
        report, teachable={"giuoco_piano_no_tree"})["can_learn_worst"] is True


def test_a_player_with_no_eligible_opening_is_told_so_not_scored():
    """27.1% of users have no opening passing the gate. They get an honest
    silence here and the phase-level grade on the areas card."""
    out = report_lines(build_report([]))
    assert out["available"] is False
    assert "not enough games" in out["reason"]

"""The coach's landing-square check (services/landing_check.py) and the week
strip (routes/training.week_step_for). docs/training_coach_presence_scope.md.

Position: Mohit's game, move 22, where he played Be7 and the queen on c7 took it.
"""
import re

from routes.training import week_step_for
from services.landing_check import check_landing

FEN = "5r1k/2q3pp/pb4b1/1pn1pp2/7B/1BP2P2/PP2Q1PP/3R1R1K w - - 0 22"


def test_tapping_the_piece_that_wins_it_is_right_and_named_with_its_look():
    r = check_landing(FEN, "h4e7", "c7")
    assert r["eligible"] and not r["safe"] and r["correct"]
    assert r["words"] == "Right. The queen on c7 can win your bishop on e7 along a long straight line."


def test_saying_safe_when_it_can_be_won_shows_the_taker():
    r = check_landing(FEN, "h4e7", "safe")
    assert not r["correct"] and r["answer_square"] == "c7"
    assert r["words"].startswith("Look again: the queen on c7")


def test_a_safe_landing_square_is_safe_and_a_wrong_tap_is_corrected():
    assert check_landing(FEN, "b3c2", "safe")["correct"]
    wrong = check_landing(FEN, "b3c2", "c7")
    assert not wrong["correct"] and wrong["words"] == "Nothing can win your bishop there. It is safe on c2."


def test_any_piece_that_wins_it_counts_and_the_cheapest_is_named():
    # Bf6: the pawn on g7 and the rook on f8 both win the bishop.
    assert check_landing(FEN, "h4f6", "f8")["correct"]
    r = check_landing(FEN, "h4f6", "safe")
    assert r["answer_square"] == "g7" and "from close by" in r["words"]


def test_the_hint_does_the_three_looks_from_the_landing_square():
    h = check_landing(FEN, "h4e7", hint=True)
    assert [look["label"] for look in h["looks"]] == ["Pieces close by", "Knight jumps", "Long lines to the edge"]
    assert [look["found"] for look in h["looks"]] == [[], [], [{"sq": "c7", "piece": "queen"}]]
    assert "correct" not in h and "words" not in h


def test_pawn_and_king_moves_are_not_checked():
    assert check_landing(FEN, "a2a3", "safe") == {"eligible": False}
    assert check_landing(FEN, "h1g1", "safe") == {"eligible": False}
    assert check_landing(FEN, "a1a8", "safe") == {"eligible": False}  # illegal


def test_the_words_carry_no_numbers_except_squares():
    for mv, ans in [("h4e7", "c7"), ("h4e7", "safe"), ("b3c2", "safe"), ("h4f6", "safe")]:
        words = re.sub(r"\b[a-h][1-8]\b", "", check_landing(FEN, mv, ans)["words"])
        assert not re.search(r"\d", words)


def test_the_week_strip_shows_only_for_this_weeks_step_in_the_drilled_family():
    plan = {"steps": [{"key": "habit:gap:piece_safety:destination_safety_exact",
                       "quality_id": "gap:piece_safety:destination_safety_exact", "this_week": True,
                       "do": "Do the three looks before every move that puts a piece on a new square."}],
            "last_week": {"words": "Last week's step showed up again. One more week, with fresh positions."}}
    week = week_step_for("piece_safety", plan)
    assert week["do"].startswith("Do the three looks") and week["last_week"].startswith("Last week's step")
    assert week_step_for("king_safety", plan) is None
    assert week_step_for("piece_safety", {"steps": [{**plan["steps"][0], "this_week": False}]}) is None
    assert week_step_for("piece_safety", None) is None

"""The reply belongs to whoever did NOT move.

Mohit 2026-10-17, reading an opponent-mistake card: "Opponent's Bd6 is a
serious mistake ... That lets them play Qh5 with check." Qh5+ is HIS move
and the whole reason the card exists. The sentence was written for user
cards -- "you played X, that lets THEM answer" -- and hardcoded the
pronoun, so on an opponent card it handed their punishment to them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.caption_pipeline import reply_gap_sentence  # noqa: E402

CHECK = {"their_reply": "Qh5", "allows": ["check"]}
TAKE = {"their_reply": "Rxe5", "allows": ["capture"],
        "captured_piece": "pawn", "capture_square": "e5"}
BOTH = {"their_reply": "Qxf7", "allows": ["check", "capture"],
        "captured_piece": "pawn", "capture_square": "f7"}


def test_our_move_lets_them_answer():
    assert reply_gap_sentence(CHECK, mover_is_user=True) == (
        "That lets them play Qh5 with check.")


def test_their_move_lets_US_answer():
    assert reply_gap_sentence(CHECK, mover_is_user=False) == (
        "That lets you play Qh5 with check.")


def test_the_capture_form_turns_too():
    assert "lets them take" in reply_gap_sentence(TAKE, mover_is_user=True)
    assert "lets you take" in reply_gap_sentence(TAKE, mover_is_user=False)


def test_the_combined_form_turns_too():
    assert "lets them play" in reply_gap_sentence(BOTH, mover_is_user=True)
    assert "lets you play" in reply_gap_sentence(BOTH, mover_is_user=False)


def test_the_default_is_the_user_card_it_was_written_for():
    assert reply_gap_sentence(CHECK) == "That lets them play Qh5 with check."


def test_no_gap_says_nothing():
    assert reply_gap_sentence(None, mover_is_user=False) == ""
    assert reply_gap_sentence({}, mover_is_user=False) == ""
    assert reply_gap_sentence({"their_reply": "Qh5"}, mover_is_user=False) == ""

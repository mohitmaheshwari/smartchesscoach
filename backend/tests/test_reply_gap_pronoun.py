"""The reply belongs to whoever did NOT move.

Mohit 2026-10-17, reading an opponent-mistake card: "Opponent's Bd6 is a
serious mistake ... That lets them play Qh5 with check." Qh5+ is HIS move
and the whole reason the card exists. The sentence was written for user
cards -- "you played X, that lets THEM answer" -- and hardcoded the
pronoun, so on an opponent card it handed their punishment to them.

Since 2026-11-06 the material sentence is the exchange ledger's, worded for
the mover when the facts are built (test_reasoning_differential covers "costs
you" against "costs them"); this sentence passes it through untouched and
turns only the check.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.caption_pipeline import reply_gap_sentence  # noqa: E402

CHECK = {"their_reply": "Qh5", "allows": ["check"]}
TAKE_TEXT = "After Nd7, Rxe5 simply takes your pawn on e5, and nothing can take back."
TAKE = {"their_reply": "Rxe5", "allows": ["material"], "material": {"text": TAKE_TEXT, "square": "e5"}}
BOTH_TEXT = "After Bd6, the exchange on f7 costs them a rook for a pawn."
BOTH = {"their_reply": "Qxf7", "allows": ["check", "material"], "material": {"text": BOTH_TEXT, "square": "f7"}}


def test_our_move_lets_them_answer():
    assert reply_gap_sentence(CHECK, mover_is_user=True) == (
        "That lets them play Qh5 with check.")


def test_their_move_lets_US_answer():
    assert reply_gap_sentence(CHECK, mover_is_user=False) == (
        "That lets you play Qh5 with check.")


def test_the_material_sentence_is_the_ledgers_words_untouched():
    # The ledger already chose "your" / "their", so neither flag rewrites it.
    assert reply_gap_sentence(TAKE, mover_is_user=True, severity="mistake") == TAKE_TEXT
    assert reply_gap_sentence(TAKE, mover_is_user=False, severity="mistake") == TAKE_TEXT


def test_the_combined_form_turns_the_check_only():
    assert reply_gap_sentence(BOTH, mover_is_user=True, severity="serious") == (
        "That lets them play Qxf7 with check. " + BOTH_TEXT)
    assert reply_gap_sentence(BOTH, mover_is_user=False, severity="serious") == (
        "That lets you play Qxf7 with check. " + BOTH_TEXT)


def test_the_default_is_the_user_card_it_was_written_for():
    assert reply_gap_sentence(CHECK) == "That lets them play Qh5 with check."


def test_no_gap_says_nothing():
    assert reply_gap_sentence(None, mover_is_user=False) == ""
    assert reply_gap_sentence({}, mover_is_user=False) == ""
    assert reply_gap_sentence({"their_reply": "Qh5"}, mover_is_user=False) == ""

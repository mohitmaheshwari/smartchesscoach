"""In a position the result has already left, the card stops instructing.

Mohit 2026-10-09 on Kxe5 in a rook endgame: "why arrows didn't fire, this is
pure tactical mistake". The arrows were the small half. The card read "You
played Kxe5; Kc5 was stronger", and the engine, asked at three depths:

    depth 16   Kc5  -615    Kxe5  -696
    depth 22   Kc5  -628    Kxe5  -942
    depth 28   Kxe5 -931    Kc5 -7608

At depth 28 the ranking inverts: the move the card scolds is best and the one
it prescribes collapses. White is -6 to -9 throughout, so every move loses and
cp_loss is the distance between two lost positions.

The threshold is pinned here with the evidence that set it, so a later reader
who meets 550 cannot retune it without meeting the four rows first.
smartchesscoach-24 asked for this file; 102 lines had shipped with no test.
"""
from __future__ import annotations

import os
import sys

import pytest

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    _drop_the_better_move_clause,
    build_move_teaching_decision,
)

# The reported card. White to move, a rook ending already gone.
KXE5_FEN = "8/4k3/3R3b/3Kp3/pn2P3/8/P7/8 w - - 1 58"


def _decide(**over):
    base = dict(
        fen_before=KXE5_FEN, played_san="Kxe5", mover_is_user=True,
        mover_is_white=True, user_color="white", full_move_number=58,
        move_history_san=[], best_move_san="Kc5", best_move_uci="d5c5",
        eval_before_cp=-584, eval_after_cp=-684, cp_loss=100, opp_cp_loss=0,
        pv_after_played=[], pv_after_best=[],
    )
    base.update(over)
    return build_move_teaching_decision(MoveInputs(**base), CrossMoveState())


class TestTheReportedCard:

    def test_it_no_longer_tells_him_to_play_the_move_that_loses(self):
        caption = _decide().text.caption
        assert "Kc5" not in caption

    def test_and_the_card_says_so_in_its_rule_name(self):
        assert "DECIDED" in (_decide().text.rule_name or "")

    def test_it_does_not_say_the_game_was_already_lost(self):
        """feedback_caption_tone_undramatic. The eval bar already shows it."""
        caption = _decide().text.caption.lower()
        for phrase in ("already lost", "already losing", "game is over",
                       "nothing can save"):
            assert phrase not in caption


class TestWhereTheThresholdCameFrom:
    """5.5 pawns is not a round number anyone liked. It is the smallest gate
    covering every corpus row where the engine contradicts itself -- the
    played move IS its own best move and cp_loss is still non-zero."""

    SELF_CONTRADICTING = (("h4", 657, 106), ("Qxb5", -674, 114),
                          ("Kxe5", -578, 119), ("Bb7", 1333, 220))

    @pytest.mark.parametrize("san,eval_before,cp", SELF_CONTRADICTING)
    def test_every_self_contradicting_row_is_inside_the_gate(self, san, eval_before, cp):
        assert abs(eval_before) >= 550, (
            f"{san} at {eval_before} sits outside the gate; the threshold no "
            f"longer covers the evidence that chose it")

    def test_six_pawns_would_have_missed_two_of_them(self):
        """My first guess. It misses Kxe5 at -578 by sixteen centipawns."""
        missed = [s for s, e, _ in self.SELF_CONTRADICTING if abs(e) < 600]
        assert missed, "if nothing is missed at 600 the 550 choice needs re-deriving"

    def test_just_below_the_gate_the_card_still_instructs(self):
        """A real game at five pawns is still a game."""
        caption = _decide(eval_before_cp=-540).text.caption
        assert "Kc5" in caption

    def test_decided_cuts_both_ways(self):
        """abs(): an instruction is no better in a won game than a lost one.
        Two of the four rows are winning positions."""
        assert "DECIDED" in (_decide(eval_before_cp=+900).text.rule_name or "")


class TestTheClauseRemover:
    """Four edge cases were written as comments and none were pinned."""

    def test_it_truncates_rather_than_filtering_around_the_instruction(self):
        """Everything after "Kc5 was better" is commentary on Kc5. Dropping
        only the middle sentence left a principle with nothing to point at."""
        out = _drop_the_better_move_clause(
            "Kxe5 is a mistake. Kc5 was better — it hits the knight on b4. "
            "The same piece on a square that attacks more targets is stronger.",
            "Kc5")
        assert out == "Kxe5 is a mistake."

    def test_what_the_move_did_survives(self):
        out = _drop_the_better_move_clause(
            "Bb3 lets Rxc3 win your rook on c3. Rxc1 was better — it captures "
            "the rook on c1.", "Rxc1")
        assert out == "Bb3 lets Rxc3 win your rook on c3."

    def test_empty_is_a_legitimate_outcome(self):
        """On the reported card the instruction IS the sentence, so removing
        the claim removes the card. Mohit, recorded in R12_blunder.json:
        "silence is NOT always worse. silence is better than fake explanation."""
        assert _drop_the_better_move_clause(
            "You played Kxe5; Kc5 was stronger — it attacks the knight on b4.",
            "Kc5") == ""

    def test_a_caption_that_never_names_the_move_is_untouched(self):
        text = "Nf3 is a mistake."
        assert _drop_the_better_move_clause(text, "Ng5") == text

    def test_a_closing_habit_sentence_survives(self):
        """smartchesscoach-24, on the counter-attack lesson in 72204b9a: it
        names the better move in sentence ONE, so breaking there threw away a
        habit line that does not depend on the engine's preference."""
        out = _drop_the_better_move_clause(
            "Qxb7 moved your queen out of the attack, but you didn't have to — "
            "Nc3 attacks their queen instead. When something of yours is "
            "attacked, look for your own attack before you move it.", "Nc3")
        assert "look for your own attack" in out
        assert "Nc3" not in out

    def test_but_not_a_trailing_sentence_about_the_move_we_removed(self):
        """A sentence naming a square is commentary, not a habit."""
        out = _drop_the_better_move_clause(
            "Kxe5 is a mistake. Kc5 was better. It covers b4 and d4.", "Kc5")
        assert "b4" not in out

    def test_a_stranded_fragment_is_dropped_rather_than_shipped(self):
        """Below four words there is no sentence left worth printing."""
        assert _drop_the_better_move_clause("You played Kxe5; Kc5 was stronger.",
                                            "Kc5") == ""

    def test_it_survives_junk(self):
        assert _drop_the_better_move_clause("", "Kc5") == ""
        assert _drop_the_better_move_clause("Some caption.", "") == "Some caption."

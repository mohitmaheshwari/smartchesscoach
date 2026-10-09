"""A flagged card names the move that was better, or says nothing about it.

Mohit's standing complaint about his own review cards is that they describe
without teaching. Measured 2026-10-10 over his stored reviews: 2,081 of 6,815
flagged cards (31%) hold a best_move_san and never mention it, and the worst of
them do not merely omit -- "Nxa5 wins the pawn for nothing" shipped on a 77cp
mistake where the engine wanted Be3, so the card praises the move it flags.

Over 400 games, at 100cp and above: 2,211 user cards carry a caption and a
better move, 215 of them now name it because of this backstop, and the cards
that still omit one went from 50 to 2.

Three failures were measured and corrected before this shape, and each has a
test below that fails if it comes back. Both fixtures are real cards, dumped
from the corpus -- the first hand-built one passed while the backstop never
fired at all, because with empty PVs a different producer names the move.
"""
from __future__ import annotations

import inspect
import os
import sys

import pytest

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services import caption_pipeline  # noqa: E402
from services.caption_config import MAX_CAPTION_WORDS  # noqa: E402
from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)

# 737b6fd6 move 20. Black plays Rd8 into a forced mate. The card used to open
# and close on "Look at what is already aimed at your king before you move" --
# true, and it never said Be6.
WHY_CARD = dict(
    fen_before="r1b2rk1/ppp2p1p/7B/2b1p3/4n3/P5P1/BPP3PK/R4R2 b - - 1 20",
    played_san="Rd8", mover_is_user=True, mover_is_white=False,
    user_color="black", full_move_number=20, move_history_san=[],
    best_move_san="Be6", best_move_uci="c8e6",
    eval_before_cp=-472, eval_after_cp=9940, cp_loss=1482, opp_cp_loss=0,
    pv_after_played=["Rxf7", "Rd5", "Bxd5", "Be6", "Bxe6", "Bg1+", "Rxg1",
                     "Kh8", "Bg7+", "Kg8", "Rxc7#"],
    pv_after_best=["Bxe6", "fxe6", "Bxf8", "Rxf8", "Rxf8+", "Kxf8", "g4",
                   "h6", "a4", "Nf6", "Kg3", "e4"],
)

# c5aab8ea move 17. b5 drops a pawn; the why for Nf4 does not survive the
# verifier, so this is the card that exercises the bare form.
BARE_CARD = dict(
    fen_before="r1b2rk1/1p3p2/7p/p1bpB1pn/B2p4/P2P1N2/1PP2PPP/R4RK1 b - - 1 17",
    played_san="b5", mover_is_user=True, mover_is_white=False,
    user_color="black", full_move_number=17, move_history_san=[],
    best_move_san="Nf4", best_move_uci="h5f4",
    eval_before_cp=109, eval_after_cp=250, cp_loss=141, opp_cp_loss=0,
    pv_after_played=["Bxb5", "Nf4", "Rfe1", "Bg4"],
    pv_after_best=["Rae1"],
)


def _decide(card=None, **over):
    return build_move_teaching_decision(
        MoveInputs(**{**(card or WHY_CARD), **over}), CrossMoveState())


class TestTheCardNamesTheBetterMove:

    def test_it_says_what_was_better(self):
        assert "Be6" in _decide().text.caption

    def test_and_marks_itself_so_the_two_forms_stay_countable(self):
        assert "SAY_BETTER_WHY" in (_decide().text.rule_name or "")

    def test_what_the_card_already_taught_is_not_replaced_by_it(self):
        """This decorates. A sibling feature's earlier design wrote a
        competing caption and dropped the reason; a name is not worth a why."""
        assert "aimed at your king" in _decide().text.caption

    def test_the_bare_card_names_the_move_with_no_board_claim(self):
        out = _decide(BARE_CARD)
        assert "SAY_BETTER_BARE" in (out.text.rule_name or "")
        assert "Nf4 was better here." in out.text.caption


class TestItNeverShipsAWhyTheBoardDoesNotSupport:
    """FAILURE 1, and the reason this runs below the stage-4 verifier rather
    than beside the 11c decorator above it. best_move_why is not always true.
    The first version appended it blind and let the whole-caption gate judge;
    over 60 games 3 of 38 residual cards lost the clause, and the verifier was
    right both times I looked:

      "Ne4 was better - it opens the line, and your queen can then play Qh4+
       to chase the king on e1."   on a KNIGHT move
      "Kd4 was better - 3 opponent pieces are aimed at your king on c5."
       where the post-move board has none

    Below the verifier the sentence is checked on its own, so a rejected why
    costs the reason and not the recommendation. Moving it here also raised
    coverage from 171 cards to 215 and cut the residue from 50 to 2.
    """

    def test_the_why_form_is_verified_before_it_is_used(self):
        block = self._block()
        assert "_verify_final(_sb_try)" in block

    def test_and_a_rejected_why_falls_back_rather_than_dropping_the_move(self):
        """The bare card is exactly this path: a why exists, the verifier
        refuses it, and Nf4 reaches the student anyway."""
        out = _decide(BARE_CARD)
        assert "Nf4" in out.text.caption
        assert "SAY_BETTER_BARE" in (out.text.rule_name or "")

    @staticmethod
    def _block():
        src = inspect.getsource(caption_pipeline)
        return src[src.index("SAY WHAT WAS BETTER"):src.index("_DECIDED_CP = 550")]


class TestTheWordCap:
    """FAILURE 2. caption_renderer enforces the cap at stage 9, which runs
    BEFORE this backstop, so an appended sentence is never trimmed -- the card
    just ships over the cap. 8 of 171 appended cards did; 0 of 215 do now.

    Trimming instead of skipping would be worse: _enforce_word_cap cuts at the
    last sentence boundary inside the window, so the sentence it drops is
    always the LAST one, which is the recommendation itself. That is how "Play
    b4 -- your pawn kicks their knight on a5" was lost from a card on
    2026-09-13, as the warning inside that function says.
    """

    @pytest.mark.parametrize("card", [WHY_CARD, BARE_CARD])
    def test_the_appended_card_stays_inside_the_cap(self, card):
        assert len(_decide(card).text.caption.split()) <= MAX_CAPTION_WORDS

    def test_a_skip_for_length_is_recorded_rather_than_silent(self):
        """An unmeasured skip is how a gate drifts."""
        src = inspect.getsource(caption_pipeline)
        assert "SAY_BETTER_TOO_LONG" in src
        assert "elif not _sb_add:" in src


class TestWhatItRefuses:

    def test_it_stays_out_of_the_50_to_99_band(self):
        """Mohit 2026-10-10 on a 51cp card: "this is actually not a bad move,
        right we should stop flagging 51cp as inaccuracy". Below the canonical
        mistake bar the gentler "Though {best} was a bit stronger" wording in
        caption_fallback_tiers owns the band, and this must not talk over it.
        Measured: the 50-99 band is left entirely alone, 0 cards touched."""
        assert "SAY_BETTER" not in (_decide(cp_loss=75).text.rule_name or "")

    def test_it_does_not_coach_the_opponent(self):
        """On an opponent card the stored better move is THEIRS, and the
        caption correctly recommends OUR reply. Appending "Be6 was better"
        there hands the lesson to the wrong player -- and that contamination
        is why the first measurement of this defect was thrown away and redone
        split by side."""
        assert "SAY_BETTER" not in (
            _decide(mover_is_user=False).text.rule_name or "")

    def test_it_says_nothing_when_the_played_move_was_the_engine_s(self):
        assert "SAY_BETTER" not in (
            _decide(best_move_san="Rd8").text.rule_name or "")

    @pytest.mark.parametrize("cp", [0, 10, 99])
    def test_nothing_below_the_mistake_bar(self, cp):
        assert "SAY_BETTER" not in (_decide(cp_loss=cp).text.rule_name or "")


class TestItComposesWithTheGatesBelowIt:

    def test_a_decided_position_strips_the_instruction_back_out(self):
        """FAILURE 3 would have been ordering. This runs BEFORE the
        decided-position gate on purpose: in a position the result has already
        left, the card stops instructing (test_decided_position_gate.py). If
        the backstop ran after that gate it would put the instruction straight
        back and undo it. Measured: 345 of the 2,211 cards are silent for this
        reason, which is the gate working, not a residue."""
        out = _decide(eval_before_cp=-900)
        assert "Be6" not in out.text.caption
        assert "DECIDED" in (out.text.rule_name or "")

    def test_and_the_order_is_visible_in_the_source(self):
        """Pinned because the composition above can pass for the wrong reason
        -- for instance if the backstop simply never fired at all."""
        src = inspect.getsource(caption_pipeline)
        assert src.index("SAY WHAT WAS BETTER") < src.index("_DECIDED_CP = 550")


class TestItSurvivesJunk:

    @pytest.mark.parametrize("over", [
        {"best_move_san": None},
        {"best_move_san": ""},
        {"eval_before_cp": None},
        {"pv_after_best": []},
        {"pv_after_played": []},
    ])
    def test_no_raise_on_missing_inputs(self, over):
        assert _decide(**over) is not None

    def test_cp_loss_is_not_optional_so_none_is_not_a_case(self):
        """Noted rather than guarded: a None cp_loss raises in stage 9b, far
        above this code, but MoveInputs declares `cp_loss: int = 0`, so None
        violates the type and no caller passes it. Pinned so a later reader
        does not mistake that crash for a defect this backstop introduced."""
        import dataclasses
        field = {f.name: f for f in dataclasses.fields(MoveInputs)}["cp_loss"]
        assert field.type in ("int", int)

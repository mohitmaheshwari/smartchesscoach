"""A forced mate must be called a mate, not a check.

Mohit 2026-09-29, on move 31 of d75acb09, a card reading "You played Rad2;
Ka3 was the stronger move here -- Rad2 lets Qa1+ come in with check":
"caption should clearly mention about check mate."

The stored line for that move is ['Qa1+', 'Ra2', 'Qxa2#'] -- the mate is in
the card's own data, and build_verified_line_cause already returned
lesson_kind='allowed_forced_mate', mate_in=2 for it. Nothing was undetected.
The cause was computed AFTER the caption had been written and attached to a
different surface, so the sentence fell to a floor that handled "+" and "#"
with one word.
"""
import chess
import pytest

from services.caption_facts import build_verified_line_cause
from services.caption_fallback_tiers import tier23_caption

# The position Mohit reported, White to move, before 31.Rad2.
REPORTED = "1r3rk1/p4ppp/8/8/K5P1/1P1R2QP/R4P2/1q6 w - - 6 31"
PLAYED_LINE = ["Qa1+", "Ra2", "Qxa2#"]
BEST_LINE = ["Rb6", "Rd6", "Qc1+", "Rb2"]


class TestTheLineReallyIsMate:
    """Proved on the board, so the rest of the file is not testing a fiction."""

    def test_replaying_the_stored_line_ends_in_checkmate(self):
        board = chess.Board(REPORTED)
        board.push(board.parse_san("Rad2"))
        for san in PLAYED_LINE:
            board.push(board.parse_san(san))
        assert board.is_checkmate()

    def test_the_recommended_move_is_not_mated(self):
        board = chess.Board(REPORTED)
        board.push(board.parse_san("Ka3"))
        assert not board.is_checkmate()


class TestTheCauseCarriesTheMate:
    def test_it_reports_an_allowed_forced_mate_in_two(self):
        cause = build_verified_line_cause(
            fen_before=REPORTED, played_san="Rad2", best_move_san="Ka3",
            pv_after_played=tuple(PLAYED_LINE), pv_after_best=tuple(BEST_LINE),
            cp_loss=9356,
        )
        assert cause is not None
        assert cause.lesson_kind == "allowed_forced_mate"
        assert cause.mate_in == 2
        assert cause.reply_san == "Qa1+"


class TestTheFloorStopsCallingAMateACheck:
    """The floor beneath R12. Its only job here is to stop lying."""

    def _facts(self, **over):
        facts = {
            "mover_is_user": True, "played_san": "Rad2", "best_move_san": "Ka3",
            "cp_loss": 9356, "opp_reply_san": "Qa1+",
        }
        facts.update(over)
        return facts

    def test_a_forced_mate_is_named_as_mate(self):
        caption, rule = tier23_caption(
            self._facts(allows_forced_mate=True, allowed_mate_in=2,
                        allowed_mate_first_move="Qa1+"),
            flagged_mistake=True,
        )
        assert "allows mate in 2 moves" in caption
        assert "come in with check." not in caption
        assert rule == "R_TIER_mistake_floor_forced_mate"

    def test_it_says_allows_not_delivers(self):
        """The claim verifier reads a bare "checkmate" as the PLAYER mating.

        The first wording ("starts a forced checkmate") was scored as
        contradicting the stored "allowed" evidence, the floor was discarded,
        and the unsoftened R01_mate sentence shipped in its place.
        """
        from services.narrator_claim_verifier import (
            _MATE_ALLOWED_RX, _MATE_DELIVERED_RX,
        )
        caption, _ = tier23_caption(
            self._facts(allows_forced_mate=True, allowed_mate_in=2,
                        allowed_mate_first_move="Qa1+"),
            flagged_mistake=True,
        )
        # The allowed pattern is tested first, so it must be the one that hits.
        assert _MATE_ALLOWED_RX.search(caption), caption
        assert not _MATE_DELIVERED_RX.search(caption), (
            "a bare 'checkmate' reads as the player delivering it"
        )

    def test_mate_in_one_is_singular(self):
        caption, _ = tier23_caption(
            self._facts(allows_forced_mate=True, allowed_mate_in=1,
                        allowed_mate_first_move="Qa1#"),
            flagged_mistake=True,
        )
        assert "allows mate in 1 move," in caption and "moves" not in caption

    def test_a_mating_reply_is_never_described_as_a_check(self):
        caption, _ = tier23_caption(
            self._facts(opp_reply_san="Qxa2#"), flagged_mistake=True
        )
        assert "which is checkmate" in caption
        assert "come in with check" not in caption

    def test_a_plain_check_is_still_a_check(self):
        # The control: nothing about ordinary checks may change.
        caption, _ = tier23_caption(
            self._facts(opp_reply_san="Qa1+"), flagged_mistake=True
        )
        assert "come in with check." in caption
        assert "checkmate" not in caption


class TestTheFactsAreOnTheCard:
    def test_the_pipeline_publishes_the_mate_facts_before_the_caption(self):
        from services.caption_pipeline import (
            CrossMoveState, MoveInputs, build_move_teaching_decision,
        )
        decision = build_move_teaching_decision(
            MoveInputs(
                fen_before=REPORTED, played_san="Rad2", mover_is_user=True,
                mover_is_white=True, user_color="white", full_move_number=31,
                move_history_san=[], best_move_san="Ka3", best_move_uci="a4a3",
                eval_before_cp=-705, eval_after_cp=-3000, cp_loss=9356,
                opp_cp_loss=0, pv_after_played=list(PLAYED_LINE),
                pv_after_best=list(BEST_LINE),
            ),
            CrossMoveState(),
        )
        assert decision.debug_facts.get("allows_forced_mate") is True
        assert decision.debug_facts.get("allowed_mate_in") == 2
        assert decision.debug_facts.get("allowed_mate_first_move") == "Qa1+"
        assert decision.debug_facts.get("allowed_mate_word") == "moves"

"""A card must record whether it explained the move the player made.

Mohit asked for the cards that "explain the better move instead of the played
move" to be fixed. Measuring them turned out to be impossible, which is the
more important finding: nothing on a card said what it had explained.

`failure_clause` is set inside `render_rule`, which begins

    facts = dict(facts)  # don't mutate caller's dict

so every clause it derives dies with the call. The rule renderers each build a
private facts dict too. So the only way to ask "does this card explain the
played move" was to match the prose -- and I tried that twice, two different
ways, and both scored these as explaining nothing:

    "Bxf7+ leaves your bishop undefended — opponent recaptures on f7"
    "Qd2 loses to Qxf2+"
    "you moved your pawn away from defending e5"

Caption quality that cannot be counted can only be found by Mohit reading
cards, which is exactly how it has been found all year.

So `render_rule` takes an explicit `out` dict, the renderers hand the answer
back, and `TeachingMeta.explains_played` carries it. These tests pin the chain
end to end, because every link in it is the kind that fails silently.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)
from services.caption_templates import render_rule  # noqa: E402


def decide(fen, played, best, cp_loss, pv_played, mover_is_user=True):
    mw = chess.Board(fen).turn == chess.WHITE
    return build_move_teaching_decision(
        MoveInputs(
            fen_before=fen, played_san=played, mover_is_user=mover_is_user,
            mover_is_white=mw,
            user_color=("white" if mw == mover_is_user else "black"),
            full_move_number=12, move_history_san=[], best_move_san=best,
            cp_loss=cp_loss if mover_is_user else 0,
            opp_cp_loss=None if mover_is_user else cp_loss,
            pv_after_played=list(pv_played), pv_after_best=[]),
        CrossMoveState())


class TestRenderRuleReportsWhatItChose:
    def test_it_still_does_not_mutate_the_caller(self):
        """The copy is deliberate and must stay. The provenance goes through
        `out` precisely so that contract is not broken to get it."""
        facts = {"played_san": "Qd2", "best_move_san": "Qd3",
                 "mover_is_user": True, "opp_reply_san": "Qxf2+",
                 "opp_reply_san_is_check": True, "cp_loss": 400,
                 "severity_practical": "blunder", "best_move_san_differs": True}
        before = dict(facts)
        render_rule("R12_blunder", facts)
        assert facts == before, "render_rule must not mutate the caller's dict"

    def test_out_receives_the_clause(self):
        out = {}
        facts = {"played_san": "Qd2", "best_move_san": "Qd3",
                 "mover_is_user": True, "opp_reply_san": "Qxf2+",
                 "opp_reply_san_is_check": True, "cp_loss": 400,
                 "severity_practical": "blunder", "best_move_san_differs": True}
        cap = render_rule("R12_blunder", facts, out=out)
        assert cap and "loses to Qxf2+" in cap
        assert out.get("explains_played_clause") == "failure_walks_into_check"

    def test_out_is_optional(self):
        """Every other caller passes nothing and must keep working."""
        facts = {"played_san": "Qd2", "best_move_san": "Qd3",
                 "mover_is_user": True, "cp_loss": 400,
                 "severity_practical": "blunder", "best_move_san_differs": True}
        render_rule("R12_blunder", facts)   # must not raise


class TestTheCardCarriesIt:
    def test_a_card_that_explains_says_which_clause(self):
        d = decide("5rk1/1pp3p1/3qp2p/p3p3/P3Pn2/N1P2N1P/1PQ2BP1/6K1 w - - 0 24",
                   "Qd2", "Qd3", 9148, ["Qxf2+", "Kh1", "Qxf3"])
        assert "loses to Qxf2+" in (d.text.caption or "")
        assert d.teaching_meta.explains_played == "failure_walks_into_check"

    def test_a_mate_card_records_the_mate(self):
        d = decide("r1bqk2r/pppp1pp1/2n5/4P2p/2BP1Qn1/5N2/PP3PPP/RN3RK1 b kq - 1 11",
                   "Nb4", "O-O", 9735, ["Qxf7#"])
        assert d.teaching_meta.explains_played == "mate"

    def test_a_splice_records_itself(self):
        """The splices run after the renderer and edit the caption directly,
        so they would be invisible to any facts-only check."""
        d = decide("r2qkb1r/ppp2ppp/2n1pn2/3p1b2/3P4/P3PN2/1PP1BPPP/RNBQK2R w KQkq - 0 6",
                   "Nc3", "O-O", 55, ["a6", "Nh4", "g6", "Nb1"])
        assert d.teaching_meta.explains_played in ("plan_blocked", "move_undone")

    def test_a_good_move_records_nothing(self):
        d = decide(chess.STARTING_FEN, "e4", "d4", 0, ["e5", "Nf3", "Nc6"])
        assert d.teaching_meta.explains_played is None


class TestTheFieldIsHonest:
    def test_it_is_a_clause_name_not_prose(self):
        """A sentence here would make the field unusable for counting, which
        is the only reason it exists."""
        d = decide("5rk1/1pp3p1/3qp2p/p3p3/P3Pn2/N1P2N1P/1PQ2BP1/6K1 w - - 0 24",
                   "Qd2", "Qd3", 9148, ["Qxf2+", "Kh1", "Qxf3"])
        value = d.teaching_meta.explains_played
        assert value and len(value.split()) == 1, value
        assert " " not in value

    def test_it_never_claims_more_than_the_caption_shows(self):
        """If the field names a clause, the caption must be non-empty. A card
        that explains nothing and claims to is worse than one that says so."""
        for args in (
            ("5rk1/1pp3p1/3qp2p/p3p3/P3Pn2/N1P2N1P/1PQ2BP1/6K1 w - - 0 24",
             "Qd2", "Qd3", 9148, ["Qxf2+", "Kh1", "Qxf3"]),
            ("r1bqk2r/pppp1pp1/2n5/4P2p/2BP1Qn1/5N2/PP3PPP/RN3RK1 b kq - 1 11",
             "Nb4", "O-O", 9735, ["Qxf7#"]),
        ):
            d = decide(*args)
            if d.teaching_meta.explains_played:
                assert (d.text.caption or "").strip(), args

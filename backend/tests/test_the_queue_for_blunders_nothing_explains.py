"""The residue, served to a human instead of guessed at.

Mohit 2026-10-10, after we walked the funnel over 100 games / 2,383 flagged
moves (both sides): "put those 28 on a detector-review page under different
tab, may be".

The funnel: the engine's own line explains 28.0%, six deterministic board
families would cover a further 40.5%, and 31.5% have nothing. At blunder
level that residue is 69 moves, and reading them with Stockfish put 41 within
reach of work already planned. The rest are positions where no material
changes hands, nobody is checked, nobody is mated, and no family fires -- the
player is just worse afterwards.

A detector cannot answer "what is the lesson here". That is the question this
queue asks.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.blunder_families import all_families, first_family  # noqa: E402

# A REAL card from the residue, copied out of the scan rather than written by
# hand. The first version of this fixture was invented from a printed sample
# and the producer correctly refused it -- an invented position does not
# behave like the one it was copied from. 278cp, and the engine's line does
# nothing you can point at.
QUIET = dict(
    fen_before="r2qk2r/ppp1bppp/2n1p3/3p1b2/3PnB2/2PBPN2/PP3PPP/RN1Q1RK1 w kq - 4 8",
    move="Nbd2", best_move="Qb3", cp_loss=278,
    pv_after_played=["g5", "Be5", "f6", "Nxe4", "dxe4", "Bxe4", "Bxe4", "Nxg5"],
    pv_after_best=["Qb3", "Qd7", "Bb5", "f6", "Nh4", "g5", "Nxf5", "exf5"],
    move_number=8, is_opponent_move=True,
    move_uci=None, fen_after=None, mate_info=None,
)


def _produce(move):
    from routes.admin_detector_review import _producers
    board = chess.Board(move["fen_before"])
    return _producers()["unexplained_blunder"](move, board.turn, {})


class TestTheQueueExists:
    def test_it_is_registered_so_the_page_shows_a_tab(self):
        from routes.admin_detector_review import _producers
        assert "unexplained_blunder" in _producers()


class TestWhatItServes:
    def test_it_serves_a_blunder_nothing_explains(self):
        out = _produce(dict(QUIET))
        assert out is not None
        claim, payload = out
        assert "What is the lesson here?" in claim
        assert payload["cp_loss"] == 278
        assert payload["best_move"] == "Qb3"
        assert payload["confidence"] == "uncertain", "every card needs a human"

    def test_the_claim_says_which_line_it_judged(self):
        """It judges the STORED line. Some of these resolve under a deeper
        search, so the card must not claim more than it checked."""
        claim, _ = _produce(dict(QUIET))
        assert "8-ply line we stored" in claim

    def test_it_refuses_anything_under_blunder(self):
        m = dict(QUIET, cp_loss=120)
        assert _produce(m) is None

    def test_it_refuses_a_move_the_engine_agreed_with(self):
        m = dict(QUIET, best_move="Nbd2")
        assert _produce(m) is None

    def test_it_refuses_when_the_line_wins_material(self):
        """If something happens, it is not this queue's problem."""
        m = dict(QUIET, pv_after_played=["Qxd4", "cxd4", "Nxd4", "Qa4+"])
        assert _produce(m) is None


class TestTheFamiliesItDefersTo:
    """If a family fires, the card belongs to that family, not here."""

    def test_a_family_match_is_not_served(self):
        fen = "r1r3k1/ppQ1ppbp/2n3p1/3q4/3P4/4BN2/PPP2PPP/2KN3R w - - 1 14"
        assert first_family(fen, "Qxb7", "Nc3") is not None
        m = dict(QUIET, fen_before=fen, move="Qxb7", best_move="Nc3",
                 cp_loss=300, pv_after_played=["Qxa2", "Kd2", "Rab8", "Qd7"])
        assert _produce(m) is None

    def test_the_families_only_fire_where_the_engine_move_does_not(self):
        """The whole honesty of a family is the comparison. A move compared
        against itself can never be in one."""
        fen = "r1r3k1/ppQ1ppbp/2n3p1/3q4/3P4/4BN2/PPP2PPP/2KN3R w - - 1 14"
        assert all_families(fen, "Qxb7", "Qxb7") == []

    def test_bad_input_is_silent_not_loud(self):
        assert all_families("not a fen", "Qxb7", "Nc3") == []
        assert first_family("not a fen", "Qxb7", "Nc3") is None

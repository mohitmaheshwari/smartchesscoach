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

from services.blunder_families import (  # noqa: E402
    all_families,
    first_family,
    is_unexplained,
)

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


def _unexplained(card):
    return is_unexplained(card["fen_before"], card["move"], card["best_move"],
                          card["pv_after_played"], card["pv_after_best"])


class TestTheQueueExists:
    def test_the_page_can_reach_it(self):
        """It lives on the geometry-gaps page beside the other two queues,
        not on detector-review where I first put it. Mohit 2026-10-10: "we
        already have geometrty-gaps page, we shuld hae put in there"."""
        from routes.admin_positional_reasons import router
        paths = {r.path for r in router.routes}
        assert "/admin/geometry-gaps/unexplained/next" in paths
        assert "/admin/geometry-gaps/unexplained" in paths
        assert "/admin/geometry-gaps/unexplained/results" in paths

    def test_it_is_not_on_the_detector_review_page_any_more(self):
        from routes.admin_detector_review import _producers
        assert "unexplained_blunder" not in _producers()

    def test_its_rulings_do_not_touch_the_no_why_queue(self):
        """Both queues can see the same card. caption_why_authoring is
        upserted on {"key": key} with no queue field and its results endpoint
        reads every row, so sharing it would collide and skew those stats."""
        import inspect
        from routes import admin_positional_reasons as mod
        src = inspect.getsource(mod.author_unexplained_blunder)
        assert "unexplained_blunder_authoring" in src
        assert "caption_why_authoring" not in src


class TestWhatItServes:
    def test_it_serves_a_blunder_nothing_explains(self):
        assert _unexplained(QUIET) is True

    def test_the_question_names_the_line_it_judged(self):
        """It judges the STORED line. Some of these resolve under a deeper
        search, so the card must not claim more than it checked."""
        import inspect
        from routes import admin_positional_reasons as mod
        src = inspect.getsource(mod.next_unexplained_blunder)
        assert "line we stored" in src
        assert "len(pv_played)" in src, "the ply count must be the real one"

    def test_it_refuses_a_move_the_engine_agreed_with(self):
        assert _unexplained(dict(QUIET, best_move="Nbd2")) is False

    def test_it_refuses_when_the_line_wins_material(self):
        """If something happens, it is not this queue's problem."""
        assert _unexplained(
            dict(QUIET, pv_after_played=["Qxd4", "cxd4", "Nxd4", "Qa4+"])) is False

    def test_it_refuses_a_line_that_is_too_short_to_judge(self):
        assert _unexplained(dict(QUIET, pv_after_played=["g5"])) is False


class TestTheFamiliesItDefersTo:
    """If a family fires, the card belongs to that family, not here."""

    def test_a_family_match_is_not_served(self):
        fen = "r1r3k1/ppQ1ppbp/2n3p1/3q4/3P4/4BN2/PPP2PPP/2KN3R w - - 1 14"
        assert first_family(fen, "Qxb7", "Nc3") is not None
        assert is_unexplained(fen, "Qxb7", "Nc3",
                              ["Qxa2", "Kd2", "Rab8", "Qd7"], []) is False

    def test_the_families_only_fire_where_the_engine_move_does_not(self):
        """The whole honesty of a family is the comparison. A move compared
        against itself can never be in one."""
        fen = "r1r3k1/ppQ1ppbp/2n3p1/3q4/3P4/4BN2/PPP2PPP/2KN3R w - - 1 14"
        assert all_families(fen, "Qxb7", "Qxb7") == []

    def test_bad_input_is_silent_not_loud(self):
        assert all_families("not a fen", "Qxb7", "Nc3") == []
        assert first_family("not a fen", "Qxb7", "Nc3") is None

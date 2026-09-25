"""Tests for the on-demand "Why" button and the both-sides scoreboard.

The property under test is mostly a NEGATIVE one: the feature exists to
stop the system manufacturing a reason it cannot derive, so the tests
that matter most are the ones asserting it stays quiet.
"""

import os
import sys

import chess
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.game_summary_service import build_move_scoreboard  # noqa: E402
from services.punishment_resolver import _net_victim_loss  # noqa: E402
from services.why_on_demand import _arrows, _phrase, explain  # noqa: E402


class _Stub:
    """Minimal stand-in for Punishment; _phrase only reads these fields."""

    def __init__(self, direction, mechanism, victim_piece=None,
                 agent_move="Nf3", victim_square=None, returns_home=False):
        self.direction = direction
        self.mechanism = mechanism
        self.victim_piece = victim_piece
        self.agent_move = agent_move
        self.victim_square = victim_square
        self.returns_home = returns_home


# --------------------------------------------------------------------------
# _net_victim_loss: which piece the victim is genuinely down
# --------------------------------------------------------------------------

def test_even_trade_names_no_piece():
    """A knight for a knight is not a piece anyone lost.

    Without this, WINS_MATERIAL would name a victim on every exchange
    and the caption would claim a loss the player did not suffer.
    """
    pre = chess.Board()
    after = chess.Board()
    after.remove_piece_at(chess.G8)   # black knight
    after.remove_piece_at(chess.G1)   # white knight
    assert _net_victim_loss(pre, after, chess.BLACK, chess.WHITE) is None


def test_knight_for_pawn_names_the_knight():
    pre = chess.Board()
    after = chess.Board()
    after.remove_piece_at(chess.G8)   # black loses a knight
    after.remove_piece_at(chess.A2)   # white loses only a pawn
    assert _net_victim_loss(pre, after, chess.BLACK, chess.WHITE) == "knight"


def test_nothing_lost_names_nothing():
    pre = chess.Board()
    assert _net_victim_loss(pre, chess.Board(), chess.BLACK, chess.WHITE) is None


def test_queen_survives_cancellation_against_a_rook():
    pre = chess.Board()
    after = chess.Board()
    after.remove_piece_at(chess.D8)   # black queen
    after.remove_piece_at(chess.A1)   # white rook
    assert _net_victim_loss(pre, after, chess.BLACK, chess.WHITE) == "queen"


# --------------------------------------------------------------------------
# _phrase: never dress an unknown up as a known
# --------------------------------------------------------------------------

def test_unnamed_material_never_says_piece():
    """"wins your piece" is a sentence with no information in it.

    It shipped for months because the `or "piece"` fallback could not
    fail. When the resolver cannot name the loss we say "material".
    """
    for direction in ("received", "missed"):
        text = _phrase(_Stub(direction, "WINS_MATERIAL"), "Qd3")
        assert text is not None
        assert "piece" not in text
        assert "material" in text


def test_named_material_uses_the_name():
    text = _phrase(_Stub("received", "WINS_MATERIAL", victim_piece="knight",
                         agent_move="Bxe5"), "Qd3")
    assert "knight" in text
    assert "material" not in text


def test_unknown_mechanism_returns_none_not_filler():
    assert _phrase(_Stub("received", "SOMETHING_NEW"), "Qd3") is None


def test_no_numeric_quantities_in_any_phrase():
    """No centipawns, no counts, no "2 pawns".

    Digits inside a move name (Nf3) or a square (e5) are the board's own
    vocabulary and stay; a NUMBER is what must never appear.
    """
    for direction in ("received", "missed"):
        for mech in ("MATE", "WINS_MATERIAL", "FORK", "TRAPPED",
                     "PROMOTES", "FORCES_RETREAT"):
            text = _phrase(_Stub(direction, mech, victim_piece="rook",
                                 victim_square="e5", agent_move="Nf3"), "Qd3")
            if not text:
                continue
            stripped = text.replace("Qd3", "").replace("e5", "").replace("Nf3", "")
            assert not any(ch.isdigit() for ch in stripped), (mech, text)
            # and no spelled-out counts either
            for word in (" two pawns", " three pawns", " a pawn and"):
                assert word not in text.lower(), (mech, text)


# --------------------------------------------------------------------------
# explain(): silence is a valid answer
# --------------------------------------------------------------------------

def test_explain_returns_none_with_nothing_to_go_on():
    assert explain(chess.STARTING_FEN, "e4", [], []) is None


def test_explain_refuses_a_candidate_that_is_much_worse():
    """The closeness gate must not be bypassed to get a tidier story.

    Candidate 2 is explainable-looking but a long way behind candidate 1,
    so the loop has to stop rather than recommend it.
    """
    board = chess.Board()
    cands = [
        {"move_san": "e4", "eval_cp": 30, "line_san": ["e4", "e5"]},
        {"move_san": "a4", "eval_cp": -400, "line_san": ["a4", "e5"]},
    ]
    assert explain(board.fen(), "h4", [], cands) is None


def test_explain_has_no_fen_no_answer():
    assert explain("", "e4", [], []) is None
    assert explain(chess.STARTING_FEN, "", [], []) is None


# --------------------------------------------------------------------------
# _arrows: built from the board, never from the sentence
# --------------------------------------------------------------------------

def test_arrows_come_from_pushing_moves():
    arrows = _arrows(chess.STARTING_FEN, ["e4", "e5", "Nf3"])
    assert [a["from"] for a in arrows] == ["e2", "e7", "g1"]
    assert [a["to"] for a in arrows] == ["e4", "e5", "f3"]


def test_arrows_stop_at_an_illegal_move_rather_than_guess():
    arrows = _arrows(chess.STARTING_FEN, ["e4", "Qxh8", "Nf3"])
    assert len(arrows) == 1


# --------------------------------------------------------------------------
# build_move_scoreboard: both sides, nothing dropped
# --------------------------------------------------------------------------

def _mv(n, san, severity, is_user):
    return {"move_number": n, "move_san": san, "severity": severity,
            "is_user_move": is_user, "phase": "middlegame", "plan": {}}


def test_scoreboard_keeps_every_moment_not_just_the_top_three():
    """GameSummary caps at 3 user + 2 opponent. A section whose point is
    completeness must not inherit that cap."""
    v5 = [_mv(i, f"N{i}", "blunder", True) for i in range(1, 6)]
    v5 += [_mv(i, f"B{i}", "opp_blunder", False) for i in range(6, 10)]
    out = build_move_scoreboard(v5)
    assert len(out["moments"]) == 9
    assert out["you"]["blunder"] == 5
    assert out["opponent"]["blunder"] == 4


def test_scoreboard_ignores_good_moves():
    v5 = [_mv(1, "e4", "good", True), _mv(2, "e5", "good", False),
          _mv(3, "Qh5", "mistake", True)]
    out = build_move_scoreboard(v5)
    assert len(out["moments"]) == 1
    assert out["moments"][0]["move_san"] == "Qh5"


def test_scoreboard_labels_the_two_sides():
    v5 = [_mv(1, "Qh5", "mistake", True), _mv(2, "Nf6", "opp_mistake", False)]
    out = build_move_scoreboard(v5)
    sides = {m["side"] for m in out["moments"]}
    assert sides == {"you", "opponent"}


def test_scoreboard_is_in_move_order():
    v5 = [_mv(9, "Rd1", "blunder", True), _mv(2, "Qh5", "mistake", True),
          _mv(5, "Nf6", "opp_mistake", False)]
    out = build_move_scoreboard(v5)
    assert [m["move_number"] for m in out["moments"]] == [2, 5, 9]


def test_scoreboard_empty_input_is_safe():
    out = build_move_scoreboard([])
    assert out["moments"] == []

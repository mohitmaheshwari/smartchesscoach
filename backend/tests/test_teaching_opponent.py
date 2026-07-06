"""
Teaching-opponent punish-override + skill floor (docs/teaching_opponent_scope.md).

A teaching opponent must be weak in DEPTH but sound in FUNDAMENTALS: it should
punish a student's hang (that's where the lesson lands), not miss free material
like Stockfish skill 0 does. These lock that behaviour.

Run:  python -m pytest tests/test_teaching_opponent.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess
from coach_play.coach_opponent import CoachOpponent, TEACHING_SKILL_FLOOR


def _chosen(fen: str, proposed_uci: str) -> str:
    """Return the SAN the punish-override picks, given the weak engine's proposal."""
    opp = CoachOpponent(user_rating=1000)
    b = chess.Board(fen)
    return b.san(opp._apply_punish_override(b, chess.Move.from_uci(proposed_uci)))


def test_punishes_a_hung_piece(monkeypatch):
    # Black left a knight hanging on e5; the weak engine proposed a quiet pawn move.
    # The opponent must take the free knight instead — the lesson.
    monkeypatch.setenv("PWC_TEACHING_OPPONENT", "true")
    assert _chosen("6k1/8/8/4n3/8/5N2/P7/6K1 w - - 0 1", "a2a3") == "Nxe5"


def test_ignores_when_nothing_hangs(monkeypatch):
    monkeypatch.setenv("PWC_TEACHING_OPPONENT", "true")
    assert _chosen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "g1f3") == "Nf3"


def test_lets_single_pawn_slip_go_below_floor(monkeypatch):
    # A hanging pawn is only ~100cp — below the 200 floor. We let it go so the
    # opponent stays beatable and the lesson stays focused on real blunders.
    monkeypatch.setenv("PWC_TEACHING_OPPONENT", "true")
    assert _chosen("6k1/8/8/4p3/3P4/8/8/6K1 w - - 0 1", "g1h1") == "Kh1"


def test_does_not_punish_into_a_desperado(monkeypatch):
    # Nxf6 wins a knight, but the knight was blocking the d-file — taking it opens
    # ...Rxd1 winning the queen. SEE on f6 alone can't see that, so the override's
    # material_hung_after guard must refuse the substitution.
    monkeypatch.setenv("PWC_TEACHING_OPPONENT", "true")
    assert _chosen("1k1r4/8/5n2/3N4/8/8/7P/3Q2K1 w - - 0 1", "h2h3") == "h3"


def test_flag_off_is_a_no_op(monkeypatch):
    monkeypatch.delenv("PWC_TEACHING_OPPONENT", raising=False)
    # Same hung-knight position; with the flag off the coach keeps its weak move.
    assert _chosen("6k1/8/8/4n3/8/5N2/P7/6K1 w - - 0 1", "a2a3") == "a3"


def test_skill_floor_only_lifts_when_enabled(monkeypatch):
    monkeypatch.setenv("PWC_TEACHING_OPPONENT", "true")
    assert CoachOpponent(user_rating=556).skill_level == TEACHING_SKILL_FLOOR  # 3, not random-0
    monkeypatch.delenv("PWC_TEACHING_OPPONENT", raising=False)
    assert CoachOpponent(user_rating=556).skill_level == 0  # unchanged when off


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

"""v159 (2026-09-15): compute_severity_for_move must never fault-frame a
move that IS the engine's top choice, and must never fault-frame mate.

Source: the 426 user-flagged moves that carry FEN + caption + complaint.
At depth 16, 67 of them were the engine's own top move, ~15 captioned as
a fault -- including "Opponent's Rxd6 is an inaccuracy. Play Rxd6" and
Qf8# captioned "Weak Squares". The pre-existing downgrade lived inline in
game_decryption_v5_service.py gated on `is_user`, so opponent moves and
the whole PWC path were never covered.
"""
import chess
import pytest

from services.caption_pipeline import compute_severity_for_move


def _sev(board, played_san, *, is_user, cp_loss, best_move_san=None):
    move = board.parse_san(played_san)
    return compute_severity_for_move(
        cp_loss=cp_loss,
        opp_cp_loss=cp_loss,
        is_user=is_user,
        is_white=board.turn == chess.WHITE,
        user_color="white" if is_user else "black",
        mate_sentinel_eval_cp=None,
        user_eval_before_white_pov=0,
        user_eval_after_white_pov=-cp_loss,
        opp_eval_before=0,
        opp_eval_after=-cp_loss,
        board_before=board,
        played_move=move,
        prev_move=None,
        best_move_san=best_move_san,
        played_san=played_san,
    )


START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MATE_IN_1 = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"


def test_user_move_equal_to_best_is_not_a_fault():
    r = _sev(chess.Board(START), "e4", is_user=True, cp_loss=250, best_move_san="e4")
    assert r.is_best_equals_played is True
    assert r.severity_user_facing == "good"
    assert r.severity_canonical == "good"


def test_opponent_move_equal_to_best_is_not_a_fault():
    """The gap that shipped: the old inline guard was `is_user`-only."""
    r = _sev(chess.Board(START), "e4", is_user=False, cp_loss=250, best_move_san="e4")
    assert r.is_best_equals_played is True
    assert r.severity_user_facing == "context"
    assert not r.severity_user_facing.startswith("opp_")


def test_best_move_annotations_are_ignored_when_matching():
    r = _sev(chess.Board(START), "e4", is_user=True, cp_loss=250, best_move_san="e4!")
    assert r.is_best_equals_played is True


def test_checkmate_is_never_a_fault():
    r = _sev(chess.Board(MATE_IN_1), "Ra8#", is_user=True, cp_loss=900, best_move_san=None)
    assert r.played_is_mate is True
    assert r.severity_user_facing == "good"


def test_opponent_checkmate_is_never_a_fault():
    r = _sev(chess.Board(MATE_IN_1), "Ra8#", is_user=False, cp_loss=900, best_move_san=None)
    assert r.played_is_mate is True
    assert r.severity_user_facing == "context"


# ── Coverage guards: a real mistake must STILL be a mistake ──────────

def test_real_blunder_is_untouched():
    r = _sev(chess.Board(START), "e4", is_user=True, cp_loss=400, best_move_san="d4")
    assert r.is_best_equals_played is False
    assert r.played_is_mate is False
    assert r.severity_canonical == "blunder"


def test_opponent_real_blunder_still_flagged():
    r = _sev(chess.Board(START), "e4", is_user=False, cp_loss=400, best_move_san="d4")
    assert r.severity_user_facing == "opp_blunder"


def test_missing_best_move_does_not_downgrade():
    """Right-or-silent: with no engine truth we never guess it was best."""
    r = _sev(chess.Board(START), "e4", is_user=True, cp_loss=400, best_move_san=None)
    assert r.is_best_equals_played is False
    assert r.severity_canonical == "blunder"


def test_empty_best_move_string_does_not_downgrade():
    r = _sev(chess.Board(START), "e4", is_user=True, cp_loss=400, best_move_san="")
    assert r.is_best_equals_played is False
    assert r.severity_canonical == "blunder"


# ── PWC path: build_move_teaching_decision classifies severity itself ──
# It never reaches compute_severity_for_move, so the guard has to hold
# here independently or Play-with-Coach stays unguarded.

from services.caption_pipeline import (  # noqa: E402
    build_move_teaching_decision,
    CrossMoveState,
    MoveInputs,
)


def _decide(fen, played_san, *, best_move_san, cp_loss, mover_is_user=True):
    board = chess.Board(fen)
    inputs = MoveInputs(
        fen_before=fen,
        played_san=played_san,
        mover_is_user=mover_is_user,
        mover_is_white=board.turn == chess.WHITE,
        user_color="white" if board.turn == chess.WHITE else "black",
        full_move_number=board.fullmove_number,
        move_history_san=[],
        best_move_san=best_move_san,
        cp_loss=cp_loss,
        opp_cp_loss=cp_loss,
    )
    return build_move_teaching_decision(inputs, CrossMoveState())


def test_pwc_user_move_equal_to_best_is_not_a_fault():
    d = _decide(START, "e4", best_move_san="e4", cp_loss=300)
    assert d.teaching_meta.severity_canonical == "good"
    assert d.teaching_meta.severity == "good"


def test_pwc_opponent_move_equal_to_best_is_not_a_fault():
    d = _decide(START, "e4", best_move_san="e4", cp_loss=300, mover_is_user=False)
    assert d.teaching_meta.severity_canonical == "good"
    assert not d.teaching_meta.severity.startswith("opp_")


def test_pwc_checkmate_is_not_a_fault():
    d = _decide(MATE_IN_1, "Ra8#", best_move_san=None, cp_loss=900)
    assert d.teaching_meta.severity_canonical == "good"


def test_pwc_real_blunder_still_flagged():
    """Coverage guard: a genuine mistake must survive untouched."""
    d = _decide(START, "e4", best_move_san="d4", cp_loss=400)
    assert d.teaching_meta.severity_canonical == "blunder"

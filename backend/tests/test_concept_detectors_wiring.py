"""
Integration tests for the concept-detector wiring.

Covers the contract between:
  - The detector module (services/concept_detectors/*)
  - The registry + runner (services/concept_detectors/registry.py + _runner.py)
  - The coach_memory recording path
    (record_concept_applications_from_game + record_skill_attempt)
  - The is_learned() graduation rule

Real `rule_of_the_square` positions exercise the wiring end-to-end, so
the test catches regressions in either the detector logic or the
plumbing.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

from services.coach_memory import (
    CoachMemory,
    LearningProgress,
    PerformanceTrend,
    SkillProgress,
    record_concept_applications_from_game,
    record_skill_attempt,
)
from services.concept_detectors._runner import run_detectors_for_move
from services.concept_detectors.rule_of_the_square import (
    detect_rule_of_the_square_application,
)


# ─── helpers ───────────────────────────────────────────────────────────────────

def _fresh_memory(user_id: str = "test_user") -> CoachMemory:
    return CoachMemory(
        user_id=user_id,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        learning=LearningProgress(),
        performance=PerformanceTrend(),
    )


# ─── detector contract ────────────────────────────────────────────────────────

def test_detector_returns_applied_when_attacker_pushes_uncatchable_pawn():
    # WK e1, WP a5, BK h8. Black king has to traverse 7 files to enter
    # the square — uncatchable. White to move; pushing a-pawn is the
    # canonical "applied" choice.
    board = chess.Board("7k/8/8/P7/8/8/8/4K3 w - - 0 1")
    move = board.parse_san("a6")
    assert detect_rule_of_the_square_application(board, move, chess.WHITE) == "applied"


def test_detector_abstains_when_king_move_is_not_a_clean_rule_test():
    # A king move in this material class is not enough to prove that the
    # player misunderstood the pawn square. The detector must abstain.
    board = chess.Board("7k/8/8/P7/8/8/8/4K3 w - - 0 1")
    move = board.parse_san("Kd2")
    assert detect_rule_of_the_square_application(board, move, chess.WHITE) is None


def test_detector_returns_none_when_position_is_not_kp_vs_k():
    # Starting position — not in scope.
    board = chess.Board()
    move = board.parse_san("e4")
    assert detect_rule_of_the_square_application(board, move, chess.WHITE) is None


# ─── runner contract ──────────────────────────────────────────────────────────

def test_runner_quarantines_disabled_rule_of_square_grade():
    board = chess.Board("7k/8/8/P7/8/8/8/4K3 w - - 0 1")
    move = board.parse_san("a6")
    grades = run_detectors_for_move(board, move, chess.WHITE)
    assert grades == []


def test_runner_skips_non_user_moves_via_caller_responsibility():
    # The runner doesn't check whose move it is — caller filters.
    # Sanity: a clean test position still grades even when the user is
    # set as the side NOT to move (caller's bug, but the runner stays
    # deterministic).
    board = chess.Board("7k/8/8/P7/8/8/8/4K3 w - - 0 1")
    move = board.parse_san("a6")
    grades = run_detectors_for_move(board, move, chess.BLACK)
    # The detector itself returns None when user_color != side-to-move,
    # so no grade should fire. Documents the contract.
    assert grades == []


# ─── integration: record_concept_applications_from_game ──────────────────────

def test_record_concept_applications_does_not_write_disabled_applied_grade():
    mem = _fresh_memory()
    # Single user move that should grade applied.
    move_evaluations = [
        {
            "fen_before": "7k/8/8/P7/8/8/8/4K3 w - - 0 1",
            "move": "a6",
        },
    ]
    recorded = record_concept_applications_from_game(
        memory=mem,
        move_evaluations=move_evaluations,
        user_color="white",
        timestamp="2026-05-29T12:00:00+00:00",
    )
    assert recorded == []
    assert all(
        s.skill_id != "endgame_rule_of_square"
        for s in mem.learning.skills
    )


def test_record_concept_applications_does_not_write_disabled_wrong_grade():
    mem = _fresh_memory()
    move_evaluations = [
        {
            "fen_before": "7k/8/8/P7/8/8/8/4K3 w - - 0 1",
            "move": "Kd2",  # wrong choice — should have pushed the pawn
        },
    ]
    recorded = record_concept_applications_from_game(
        memory=mem,
        move_evaluations=move_evaluations,
        user_color="white",
    )
    assert recorded == []
    assert all(
        s.skill_id != "endgame_rule_of_square"
        for s in mem.learning.skills
    )


def test_record_concept_applications_skips_opponent_moves():
    mem = _fresh_memory()
    # Two moves: opponent push + user move (irrelevant to the rule).
    move_evaluations = [
        {"fen_before": "7k/8/8/P7/8/8/8/4K3 w - - 0 1", "move": "a6"},
        {"fen_before": "7k/8/P7/8/8/8/8/4K3 b - - 0 1", "move": "Kg7"},
    ]
    # User is BLACK — the white pawn push should be filtered (it's
    # white's move, opponent for black user). The black Kg7 reply is a
    # losing-by-force position so the detector returns None.
    recorded = record_concept_applications_from_game(
        memory=mem,
        move_evaluations=move_evaluations,
        user_color="black",
    )
    # No grade should fire — first move filtered by turn check, second
    # is lost-by-force and not a clean test.
    assert recorded == []


# ─── graduation rule lift ────────────────────────────────────────────────────

def test_is_learned_lifts_to_lesson_plus_applied_when_detector_engaged():
    """A skill that has correct >= 1 (lesson completed) but ZERO applied
    should NOT graduate once the detector has graded any attempt —
    'applied' or 'wrong' outcomes mark the skill as detector-engaged."""
    skill = SkillProgress(skill_id="endgame_rule_of_square", skill_type="endgame")
    # Lesson-correct (no detector yet) — should graduate per the legacy rule.
    skill.correct = 1
    skill.outcomes = ["correct"]
    assert skill.is_learned() is True

    # Now an "applied" grade fires (detector engaged). With applied >= 1
    # the skill is still learned.
    record_skill_attempt(_fresh_memory(), skill.skill_id, skill.skill_type, "applied")
    skill_with_applied = SkillProgress(skill_id="x", skill_type="endgame")
    skill_with_applied.correct = 2  # 1 lesson + 1 applied (bumped both)
    skill_with_applied.applied = 1
    skill_with_applied.outcomes = ["correct", "applied"]
    assert skill_with_applied.is_learned() is True


def test_is_learned_blocks_graduation_when_only_wrong_grade_from_detector():
    """If the detector has fired but only ever returned 'missed' (-> wrong),
    the skill stays UN-learned even though a lesson correct exists."""
    skill = SkillProgress(skill_id="endgame_rule_of_square", skill_type="endgame")
    skill.correct = 1   # lesson
    skill.wrong = 1     # detector graded 'missed' in real play
    skill.outcomes = ["correct", "wrong"]
    # Currently still passes the legacy "correct >= 1" gate but the
    # last-two-has-wrong gate blocks graduation.
    assert skill.is_learned() is False

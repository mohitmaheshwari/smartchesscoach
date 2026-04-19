"""
Tests for Engine 2's game → skill-attempt pipeline.

Without these attempts being recorded every game, tier-1 skills like
pre_move_check / hanging_piece / opponent_threat never accrue stats,
so pick_next_skill cycles on the same one forever. These tests verify
the recorder produces the right outcomes for realistic game shapes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.coach_memory import (
    CoachMemory,
    LearningProgress,
    PerformanceTrend,
    record_engine2_skills_from_game,
)
from services.engine2_skill_builder import pick_next_skill, find_ready_skills


def _fresh_memory() -> CoachMemory:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    m = CoachMemory(user_id="test_user", created_at=now, updated_at=now)
    m.learning = LearningProgress()
    m.performance = PerformanceTrend()
    return m


def _find_skill(memory, skill_id):
    return next((s for s in memory.learning.skills if s.skill_id == skill_id), None)


# ─── TIER-1 RECORDING ─────────────────────────────────────────────────


def test_clean_quiet_game_only_records_pre_move_check():
    """
    A clean game with no tactical events = no opportunity for fork/pin/hanging.
    We should NOT credit those skills. Only pre_move_check (meta-habit) and
    opening_principles (always applicable with accuracy signal) should record.
    """
    mem = _fresh_memory()
    recorded = record_engine2_skills_from_game(
        memory=mem,
        user_rating=800,
        mistake_types=[],
        blunders=0,
        accuracy=85.0,
        game_result="win",
        was_winning=False,
        endgame_reached=False,
    )
    # pre_move_check always records (meta-skill)
    assert _find_skill(mem, "pre_move_check").correct == 1
    # No evidence for these → not recorded
    assert _find_skill(mem, "hanging_piece") is None
    assert _find_skill(mem, "opponent_threat") is None
    assert _find_skill(mem, "king_safety") is None
    assert _find_skill(mem, "fork") is None
    assert _find_skill(mem, "pin") is None


def test_avoided_threat_credits_hanging_and_opponent_threat():
    """Positive evidence from classifier → both hanging_piece and opponent_threat credit."""
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=800,
        mistake_types=["avoided_threat"],
        blunders=0,
        accuracy=80.0,
        game_result="win",
        was_winning=False,
        endgame_reached=False,
    )
    assert _find_skill(mem, "hanging_piece").correct == 1
    assert _find_skill(mem, "opponent_threat").correct == 1


def test_avoided_threat_also_credits_king_safety():
    """avoided_threat is threat-handling in general — also demonstrates king safety."""
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=900,
        mistake_types=["avoided_threat"],
        blunders=0,
        accuracy=80.0,
        game_result="win",
        was_winning=False,
        endgame_reached=False,
    )
    assert _find_skill(mem, "king_safety").correct == 1


def test_king_safety_skips_when_no_king_event():
    """No king_safety_error and no avoided_threat → skill not recorded."""
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=900,
        mistake_types=["executed_fork"],  # Tactical event, unrelated to king
        blunders=0,
        accuracy=80.0,
        game_result="win",
        was_winning=False,
        endgame_reached=False,
    )
    assert _find_skill(mem, "king_safety") is None


def test_executed_fork_credits_free_piece_capture():
    """Forks/pins/skewers all win material — they demonstrate the 'take free material' skill."""
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=900,
        mistake_types=["executed_fork"],
        blunders=0,
        accuracy=80.0,
        game_result="win",
        was_winning=False,
        endgame_reached=False,
    )
    assert _find_skill(mem, "free_piece_capture").correct == 1


def test_missed_tactic_marks_free_piece_capture_wrong():
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=900,
        mistake_types=["missed_winning_tactic"],
        blunders=1,
        accuracy=65.0,
        game_result="loss",
        was_winning=False,
        endgame_reached=False,
    )
    assert _find_skill(mem, "free_piece_capture").wrong == 1


def test_hanging_piece_mistake_marks_wrong():
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=800,
        mistake_types=["hanging_piece"],
        blunders=1,
        accuracy=65.0,
        game_result="loss",
        was_winning=False,
        endgame_reached=False,
    )
    assert _find_skill(mem, "hanging_piece").wrong == 1
    assert _find_skill(mem, "pre_move_check").wrong == 1  # Any blunder = wrong on pmc


def test_ignored_threat_marks_opponent_threat_wrong():
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=1000,
        mistake_types=["ignored_threat"],
        blunders=1,
        accuracy=60.0,
        game_result="loss",
        was_winning=False,
        endgame_reached=False,
    )
    assert _find_skill(mem, "opponent_threat").wrong == 1


def test_rating_out_of_range_skips_skill():
    """User at 1700 shouldn't get pre_move_check attempts (range 400-1400)."""
    mem = _fresh_memory()
    recorded = record_engine2_skills_from_game(
        memory=mem,
        user_rating=1700,
        mistake_types=[],
        blunders=0,
        accuracy=85.0,
        game_result="win",
        was_winning=False,
        endgame_reached=False,
    )
    assert "pre_move_check" not in recorded
    assert _find_skill(mem, "pre_move_check") is None


# ─── TIER-2 RECORDING ─────────────────────────────────────────────────


def test_walked_into_fork_marks_fork_wrong():
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=1000,
        mistake_types=["walked_into_fork"],
        blunders=1,
        accuracy=62.0,
        game_result="loss",
        was_winning=False,
        endgame_reached=False,
    )
    assert _find_skill(mem, "fork").wrong == 1


def test_no_fork_event_means_no_fork_record():
    """Critical contrast: if the game has no fork event, fork is NOT recorded."""
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=1000,
        mistake_types=["hanging_piece"],  # Different event type
        blunders=1,
        accuracy=65.0,
        game_result="loss",
        was_winning=False,
        endgame_reached=False,
    )
    assert _find_skill(mem, "fork") is None


def test_missed_pin_marks_pin_wrong():
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=1200,
        mistake_types=["missed_pin"],
        blunders=0,
        accuracy=70.0,
        game_result="draw",
        was_winning=False,
        endgame_reached=False,
    )
    assert _find_skill(mem, "pin").wrong == 1


def test_executed_fork_marks_fork_correct():
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=1000,
        mistake_types=["executed_fork"],
        blunders=0,
        accuracy=80.0,
        game_result="win",
        was_winning=True,
        endgame_reached=False,
    )
    assert _find_skill(mem, "fork").correct == 1


# ─── CONVERSION RECORDING ─────────────────────────────────────────────


def test_was_winning_and_lost_marks_conversion_wrong():
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=1200,
        mistake_types=["failed_conversion"],
        blunders=1,
        accuracy=65.0,
        game_result="loss",
        was_winning=True,
        endgame_reached=False,
    )
    assert _find_skill(mem, "conversion").wrong == 1


def test_was_winning_and_won_marks_conversion_correct():
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=1200,
        mistake_types=[],
        blunders=0,
        accuracy=82.0,
        game_result="win",
        was_winning=True,
        endgame_reached=False,
    )
    assert _find_skill(mem, "conversion").correct == 1


# ─── ENDGAME SKILLS ───────────────────────────────────────────────────


def test_simple_mates_only_when_endgame_reached():
    mem = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem,
        user_rating=800,
        mistake_types=[],
        blunders=0,
        accuracy=85.0,
        game_result="win",
        was_winning=False,
        endgame_reached=False,  # Short game, no endgame
    )
    assert _find_skill(mem, "simple_mates") is None

    # Now with endgame
    mem2 = _fresh_memory()
    record_engine2_skills_from_game(
        memory=mem2,
        user_rating=800,
        mistake_types=[],
        blunders=0,
        accuracy=85.0,
        game_result="win",
        was_winning=False,
        endgame_reached=True,
    )
    assert _find_skill(mem2, "simple_mates").correct == 1


# ─── GRADUATION THROUGH ENGINE 2 ──────────────────────────────────────


def test_learned_skill_demotes_on_backslide():
    """If a skill was learned but the user now fails repeatedly, demote it.
    This matters because 'learned' is a current-state signal, not a badge."""
    from services.coach_memory import record_skill_attempt
    mem = _fresh_memory()

    # Build to a "learned" state: 5 seen, all correct
    for _ in range(5):
        record_skill_attempt(mem, "fork", "concept", "correct")
    fork = _find_skill(mem, "fork")
    assert fork.is_learned()
    assert "fork" in mem.learning.concepts_mastered

    # Now backslide — two wrongs in a row
    record_skill_attempt(mem, "fork", "concept", "wrong")
    record_skill_attempt(mem, "fork", "concept", "wrong")

    # Should be demoted
    fork = _find_skill(mem, "fork")
    assert fork.learned_at is None
    assert "fork" not in mem.learning.concepts_mastered


def test_five_clean_games_learn_pre_move_check():
    """pre_move_check is the meta-skill that records every game.
    5 seen, 3 correct, no recent fail → learned."""
    mem = _fresh_memory()
    for _ in range(5):
        record_engine2_skills_from_game(
            memory=mem,
            user_rating=800,
            mistake_types=[],
            blunders=0,
            accuracy=85.0,
            game_result="win",
            was_winning=False,
            endgame_reached=False,
        )
    pmc = _find_skill(mem, "pre_move_check")
    assert pmc.seen == 5
    assert pmc.correct == 5
    assert pmc.is_learned()
    assert "pre_move_check" in mem.learning.concepts_mastered


def test_quiet_games_do_not_graduate_hanging_piece():
    """CRITICAL: if fork never came up, 5 quiet games should NOT graduate fork.
    This is the whole point of opportunity-gating — no false learning credit."""
    mem = _fresh_memory()
    for _ in range(5):
        record_engine2_skills_from_game(
            memory=mem,
            user_rating=1000,
            mistake_types=[],  # No fork events, no threat events
            blunders=0,
            accuracy=75.0,
            game_result="win",
            was_winning=False,
            endgame_reached=False,
        )
    # fork should have NO recorded attempts
    assert _find_skill(mem, "fork") is None
    assert "fork" not in mem.learning.concepts_mastered
    # hanging_piece: also no recorded attempts (no hang event, no avoid event)
    assert _find_skill(mem, "hanging_piece") is None


def test_demonstrated_skill_over_5_games_learns_it():
    """When user actually demonstrates the skill (avoided threats) 5 times
    with 3 correct and no recent fail → learned."""
    mem = _fresh_memory()
    for _ in range(5):
        record_engine2_skills_from_game(
            memory=mem,
            user_rating=1000,
            mistake_types=["avoided_threat"],  # demonstrates opponent_threat
            blunders=0,
            accuracy=80.0,
            game_result="win",
            was_winning=False,
            endgame_reached=False,
        )
    ot = _find_skill(mem, "opponent_threat")
    assert ot.seen == 5
    assert ot.correct == 5
    assert ot.is_learned()


def test_engine2_progression_after_demonstrated_skills():
    """Once tier-1 skills are demonstrated enough, tier-2 unlocks."""
    mem = _fresh_memory()
    # 5 games with evidence of pre_move_check + avoided_threat +
    # plus hanging-related positive signal
    for _ in range(5):
        record_engine2_skills_from_game(
            memory=mem,
            user_rating=900,
            mistake_types=["avoided_threat"],
            blunders=0,
            accuracy=82.0,
            game_result="win",
            was_winning=False,
            endgame_reached=False,
        )
    # pre_move_check and hanging_piece should be learned
    assert "pre_move_check" in mem.learning.concepts_mastered
    assert "hanging_piece" in mem.learning.concepts_mastered
    # fork was untested → should NOT be learned
    assert "fork" not in mem.learning.concepts_mastered


# ─── SMOKE RUNNER ─────────────────────────────────────────────────────


def _smoke():
    passed = 0
    failed = []
    tests = [n for n in globals() if n.startswith("test_")]
    for name in tests:
        try:
            globals()[name]()
            passed += 1
            print(f"  PASS: {name}")
        except AssertionError as e:
            failed.append((name, str(e)))
            print(f"  FAIL: {name} — {e}")
        except Exception as e:
            failed.append((name, f"{type(e).__name__}: {e}"))
            print(f"  ERROR: {name} — {type(e).__name__}: {e}")
    print()
    print(f"Results: {passed}/{len(tests)} passed, {len(failed)} failed")
    for n, e in failed:
        print(f"  - {n}: {e}")
    return len(failed) == 0


if __name__ == "__main__":
    sys.exit(0 if _smoke() else 1)

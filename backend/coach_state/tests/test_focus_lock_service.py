"""
Unit Tests for Focus Lock Service - Step 9

Tests 3 simulated lock runs:
1. Successful completion (compliance >= 75%)
2. Extended (compliance < 75%, first failure)
3. Strict mode triggered (declining trend + active lock)

Plus compliance calculation tests for each lesson key.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from coach_state.focus_lock_service import (
    ComplianceResult,
    ComplianceLevel,
    FocusLock,
    calculate_forcing_compliance,
    calculate_calculation_compliance,
    calculate_threat_compliance,
    calculate_compliance,
    create_focus_lock,
    update_lock_after_game,
    check_lock_exit,
    apply_strict_mode_tone,
    should_activate_lock,
    get_lock_ui_state,
    get_lock_copy,
    STRONG_COMPLIANCE,
    PARTIAL_COMPLIANCE,
    COMPLETION_COMPLIANCE_THRESHOLD,
)


# =============================================================================
# COMPLIANCE CALCULATION TESTS
# =============================================================================

class TestForcingCompliance:
    """Test FORCING_BLIND compliance calculation."""
    
    def test_perfect_compliance(self):
        """Player found all forcing moves."""
        moves = [
            {"is_user_move": True, "engine_best_move": "e5f7", "move_uci": "e5f7", 
             "engine_best_move_data": {"gives_check": True}, "cp_loss": 0, "move_number": 1},
            {"is_user_move": True, "engine_best_move": "d4e5", "move_uci": "d4e5",
             "engine_best_move_data": {"is_capture": True}, "cp_loss": 10, "move_number": 2},
            {"is_user_move": True, "engine_best_move": "f3g5", "move_uci": "f3g5",
             "engine_best_move_data": {"gives_check": True}, "cp_loss": 0, "move_number": 3},
        ]
        
        result = calculate_forcing_compliance(moves)
        
        assert result.compliance_score == 1.0
        assert result.interpretation == ComplianceLevel.STRONG
        assert result.passed is True
    
    def test_partial_compliance(self):
        """Player missed some forcing moves."""
        moves = [
            {"is_user_move": True, "engine_best_move": "e5f7", "move_uci": "e5f7",
             "engine_best_move_data": {"gives_check": True}, "cp_loss": 0, "move_number": 1},
            {"is_user_move": True, "engine_best_move": "d4e5", "move_uci": "a2a3",
             "engine_best_move_data": {"is_capture": True}, "cp_loss": 150, "move_number": 2},
            {"is_user_move": True, "engine_best_move": "f3g5", "move_uci": "f3g5",
             "engine_best_move_data": {"gives_check": True}, "cp_loss": 0, "move_number": 3},
            {"is_user_move": True, "engine_best_move": "h2h4", "move_uci": "h2h4",
             "engine_best_move_data": {"is_capture": True}, "cp_loss": 0, "move_number": 4},
        ]
        
        result = calculate_forcing_compliance(moves)
        
        # 1 missed out of 4 opportunities = 75%
        assert result.compliance_score == 0.75
        assert result.interpretation == ComplianceLevel.PARTIAL
    
    def test_failed_compliance(self):
        """Player missed most forcing moves."""
        moves = [
            {"is_user_move": True, "engine_best_move": "e5f7", "move_uci": "a2a3",
             "engine_best_move_data": {"gives_check": True}, "cp_loss": 200, "move_number": 1},
            {"is_user_move": True, "engine_best_move": "d4e5", "move_uci": "b2b3",
             "engine_best_move_data": {"is_capture": True}, "cp_loss": 150, "move_number": 2},
            {"is_user_move": True, "engine_best_move": "f3g5", "move_uci": "c2c3",
             "engine_best_move_data": {"gives_check": True}, "cp_loss": 180, "move_number": 3},
        ]
        
        result = calculate_forcing_compliance(moves)
        
        # 3 missed out of 3 = 0%
        assert result.compliance_score == 0.0
        assert result.interpretation == ComplianceLevel.FAILED
        assert result.passed is False
    
    def test_insufficient_data(self):
        """Not enough forcing opportunities - return benefit of doubt."""
        moves = [
            {"is_user_move": True, "engine_best_move": "a2a3", "move_uci": "a2a3",
             "engine_best_move_data": {}, "cp_loss": 0, "move_number": 1},
            {"is_user_move": True, "engine_best_move": "b2b3", "move_uci": "b2b3",
             "engine_best_move_data": {}, "cp_loss": 0, "move_number": 2},
        ]
        
        result = calculate_forcing_compliance(moves)
        
        assert result.compliance_score == 1.0
        assert result.details.get("insufficient_data") is True


class TestCalculationCompliance:
    """Test STOPPED_CALCULATION_EARLY compliance calculation."""
    
    def test_calculated_deeply(self):
        """Player calculated all critical moments correctly."""
        moves = [
            {"is_user_move": True, "score_before": 100, "eval_after_best": 300,
             "move_uci": "e4e5", "engine_top_moves": ["e4e5", "d4d5"], "cp_loss": 20, "move_number": 1},
            {"is_user_move": True, "score_before": 0, "eval_after_best": 200,
             "move_uci": "f3f7", "engine_top_moves": ["f3f7"], "cp_loss": 0, "move_number": 2},
        ]
        
        result = calculate_calculation_compliance(moves)
        
        assert result.compliance_score == 1.0
        assert result.interpretation == ComplianceLevel.STRONG


class TestThreatCompliance:
    """Test THREAT_VERIFICATION compliance calculation."""
    
    def test_threats_verified(self):
        """Player addressed all threats."""
        moves = [
            {"is_user_move": True, "opponent_best_reply": {"gives_check": True},
             "cp_loss": 0, "addresses_threat": True, "move_number": 1},
            {"is_user_move": True, "opponent_best_reply": {"material_gain": 150},
             "cp_loss": 10, "addresses_threat": True, "move_number": 2},
            {"is_user_move": True, "opponent_best_reply": {"gives_check": True},
             "cp_loss": 0, "addresses_threat": True, "move_number": 3},
        ]
        
        result = calculate_threat_compliance(moves)
        
        assert result.compliance_score == 1.0
        assert result.interpretation == ComplianceLevel.STRONG


# =============================================================================
# SIMULATED LOCK RUN 1: SUCCESSFUL COMPLETION
# =============================================================================

class TestSimulatedLockSuccessful:
    """
    Simulate a successful lock completion.
    
    User plays 5 games with good compliance (>=75% average).
    Lock should complete with "Rule mastered." message.
    """
    
    def test_successful_lock_completion(self):
        """Complete lock with strong compliance."""
        # Create lock
        lock = create_focus_lock("FORCING_BLIND", games=5)
        assert lock.state == "ACTIVE"
        assert lock.games_required == 5
        
        # Simulate 5 games with good compliance
        compliance_scores = [0.85, 0.80, 0.75, 0.90, 0.80]  # avg = 0.82
        
        for i, score in enumerate(compliance_scores):
            compliance = ComplianceResult(
                lesson_key="FORCING_BLIND",
                total_opportunities=4,
                missed_count=int((1 - score) * 4),
                compliance_score=score,
                interpretation=ComplianceLevel.STRONG if score >= 0.8 else ComplianceLevel.PARTIAL,
            )
            
            lock = update_lock_after_game(lock, compliance)
            
            if i < 4:  # Not yet complete
                assert lock.state in ("ACTIVE", "STRICT")
                assert lock.games_completed == i + 1
        
        # After 5 games with good compliance
        assert lock.state == "COMPLETED"
        assert lock.average_compliance >= COMPLETION_COMPLIANCE_THRESHOLD
        
        # Check exit
        exit_info = check_lock_exit(lock)
        assert exit_info["should_exit"] is True
        assert exit_info["exit_type"] == "success"
        assert "mastered" in exit_info["headline"].lower()
        assert exit_info["reward"] == "+1 Discipline Level"


# =============================================================================
# SIMULATED LOCK RUN 2: EXTENDED (PARTIAL COMPLIANCE)
# =============================================================================

class TestSimulatedLockExtended:
    """
    Simulate a lock that needs extension.
    
    User plays 5 games but compliance is below 75%.
    Lock should extend by 3 games.
    """
    
    def test_lock_extension(self):
        """Lock extends when compliance insufficient."""
        lock = create_focus_lock("FORCING_BLIND", games=5)
        
        # Simulate 5 games with poor compliance
        compliance_scores = [0.60, 0.55, 0.70, 0.65, 0.60]  # avg = 0.62
        
        for score in compliance_scores:
            compliance = ComplianceResult(
                lesson_key="FORCING_BLIND",
                total_opportunities=4,
                missed_count=int((1 - score) * 4),
                compliance_score=score,
                interpretation=ComplianceLevel.PARTIAL if score >= 0.6 else ComplianceLevel.FAILED,
            )
            lock = update_lock_after_game(lock, compliance)
        
        # After 5 games with poor compliance - should extend
        assert lock.state == "EXTENDED"
        assert lock.games_required == 8  # 5 + 3 extension
        assert lock.failure_count == 1
        
        # Check exit info
        exit_info = check_lock_exit(lock)
        assert exit_info["should_exit"] is False
        assert exit_info["exit_type"] == "extended"
        assert "Almost there" in exit_info["headline"]


# =============================================================================
# SIMULATED LOCK RUN 3: STRICT MODE TRIGGERED
# =============================================================================

class TestSimulatedLockStrictMode:
    """
    Simulate strict mode activation.
    
    User is on active lock with declining trend.
    Strict mode should activate.
    """
    
    def test_strict_mode_activation(self):
        """Strict mode activates on declining trend."""
        lock = create_focus_lock("FORCING_BLIND", games=5)
        
        # First game with declining trend
        compliance = ComplianceResult(
            lesson_key="FORCING_BLIND",
            total_opportunities=4,
            missed_count=2,
            compliance_score=0.50,
            interpretation=ComplianceLevel.FAILED,
        )
        
        # Update with declining trend
        lock = update_lock_after_game(lock, compliance, trend="declining")
        
        # Should trigger strict mode
        assert lock.strict_mode is True
        assert lock.state == "STRICT"
        assert "slipping" in lock.headline.lower()
    
    def test_strict_mode_tone_adjustment(self):
        """Strict mode removes encouragement."""
        text = "You're improving. Keep building this pattern. Check forcing moves first."
        
        result = apply_strict_mode_tone(text, "Developing", strict_mode=True)
        
        assert "improving" not in result
        assert "Keep building" not in result
        assert "forcing moves" in result
    
    def test_strict_mode_sentence_budget(self):
        """Strict mode enforces sentence limit."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
        
        # Advanced tier has budget of 1 sentence in strict mode
        result = apply_strict_mode_tone(text, "Advanced", strict_mode=True)
        
        sentences = [s for s in result.split(".") if s.strip()]
        assert len(sentences) <= 1


# =============================================================================
# LOCK LIFECYCLE TESTS
# =============================================================================

class TestLockLifecycle:
    """Test focus lock creation and state transitions."""
    
    def test_create_lock(self):
        """Create new focus lock."""
        lock = create_focus_lock("FORCING_BLIND", games=5)
        
        assert lock.lesson_key == "FORCING_BLIND"
        assert lock.state == "ACTIVE"
        assert lock.games_required == 5
        assert lock.games_completed == 0
        assert lock.compliance_scores == []
        assert lock.strict_mode is False
        assert "locked for 5 games" in lock.headline.lower()
    
    def test_failed_twice_triggers_deep_review(self):
        """After 2 failures, lock fails and requires deep review."""
        lock = create_focus_lock("FORCING_BLIND", games=5)
        
        # First failure cycle (5 games, poor compliance)
        for _ in range(5):
            compliance = ComplianceResult(
                lesson_key="FORCING_BLIND",
                total_opportunities=4,
                missed_count=3,
                compliance_score=0.25,
                interpretation=ComplianceLevel.FAILED,
            )
            lock = update_lock_after_game(lock, compliance)
        
        assert lock.state == "EXTENDED"
        assert lock.failure_count == 1
        assert lock.games_required == 8  # Extended by 3
        
        # Second failure cycle - need to complete to games_required (8)
        # Current games_completed is 5, need 3 more
        for _ in range(3):
            compliance = ComplianceResult(
                lesson_key="FORCING_BLIND",
                total_opportunities=4,
                missed_count=3,
                compliance_score=0.25,
                interpretation=ComplianceLevel.FAILED,
            )
            lock = update_lock_after_game(lock, compliance)
        
        assert lock.state == "FAILED"
        assert lock.failure_count == 2
        
        exit_info = check_lock_exit(lock)
        assert exit_info["should_exit"] is True
        assert exit_info["exit_type"] == "failed"
        assert exit_info["next_action"] == "DEEP_SESSION"


class TestLockUIState:
    """Test UI state generation."""
    
    def test_active_lock_ui(self):
        """Get UI state for active lock."""
        lock = create_focus_lock("FORCING_BLIND", games=5)
        
        # Add some compliance
        lock = FocusLock(
            lesson_key=lock.lesson_key,
            state="ACTIVE",
            games_required=5,
            games_completed=2,
            compliance_scores=[0.80, 0.75],
            strict_mode=False,
            failure_count=0,
            created_at=lock.created_at,
            updated_at=lock.updated_at,
            headline=lock.headline,
            message=lock.message,
        )
        
        ui_state = get_lock_ui_state(lock)
        
        assert ui_state["active"] is True
        assert ui_state["lesson_key"] == "FORCING_BLIND"
        assert ui_state["progress"]["completed"] == 2
        assert ui_state["progress"]["required"] == 5
        assert ui_state["compliance"]["average"] == 78  # (0.80 + 0.75) / 2 * 100
        assert ui_state["cta"] == "Start Next Game"
    
    def test_completed_lock_ui(self):
        """Completed lock returns None for UI."""
        lock = create_focus_lock("FORCING_BLIND", games=5)
        lock = FocusLock(
            lesson_key=lock.lesson_key,
            state="COMPLETED",
            games_required=5,
            games_completed=5,
            compliance_scores=[0.80, 0.85, 0.90, 0.85, 0.80],
            strict_mode=False,
            failure_count=0,
            created_at=lock.created_at,
            updated_at=lock.updated_at,
            headline="Rule mastered.",
            message="Lock lifted.",
        )
        
        ui_state = get_lock_ui_state(lock)
        
        assert ui_state is None


class TestLockActivation:
    """Test lock activation conditions."""
    
    def test_should_activate_on_plateau(self):
        """Lock should activate for PLATEAU with valid lesson."""
        assert should_activate_lock("PLATEAU", "FORCING_BLIND") is True
        assert should_activate_lock("PLATEAU", "STOPPED_CALCULATION_EARLY") is True
    
    def test_should_activate_on_confidence_illusion(self):
        """Lock should activate for CONFIDENCE_ILLUSION."""
        assert should_activate_lock("CONFIDENCE_ILLUSION", "THREAT_VERIFICATION") is True
    
    def test_should_not_activate_on_breakthrough(self):
        """Lock should NOT activate for positive states."""
        assert should_activate_lock("BREAKTHROUGH", "FORCING_BLIND") is False
        assert should_activate_lock("STABLE_GROWTH", "FORCING_BLIND") is False
        assert should_activate_lock("NORMAL", "FORCING_BLIND") is False
    
    def test_should_not_activate_for_invalid_lesson(self):
        """Lock should NOT activate for unsupported lesson keys."""
        assert should_activate_lock("PLATEAU", "UNKNOWN_LESSON") is False
        assert should_activate_lock("PLATEAU", None) is False


class TestComplianceDispatcher:
    """Test compliance calculation dispatcher."""
    
    def test_dispatches_to_correct_calculator(self):
        """Dispatcher routes to correct calculation function."""
        moves = [
            {"is_user_move": True, "engine_best_move": "e5f7", "move_uci": "e5f7",
             "engine_best_move_data": {"gives_check": True}, "cp_loss": 0, "move_number": 1},
        ] * 4
        
        # Each lesson key should use its specific calculator
        forcing_result = calculate_compliance("FORCING_BLIND", moves)
        assert forcing_result.lesson_key == "FORCING_BLIND"
        
        calc_result = calculate_compliance("STOPPED_CALCULATION_EARLY", moves)
        assert calc_result.lesson_key == "STOPPED_CALCULATION_EARLY"
        
        threat_result = calculate_compliance("THREAT_VERIFICATION", moves)
        assert threat_result.lesson_key == "THREAT_VERIFICATION"

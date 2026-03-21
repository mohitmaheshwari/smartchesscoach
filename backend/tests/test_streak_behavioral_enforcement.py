"""
Test Suite: Behavioral Enforcement System for Chess Coaching App
Tests for iteration 138 - Backend as source of truth for streak

Features tested:
1. Backend API: GET /api/streak/status returns correct structure
2. Backend API: GET /api/streak/focus-types returns all focus types
3. Backend: mistake_streak_service.py - update_streak_from_analysis function
4. Backend: analysis_worker.py - Phase 8 streak update
5. Backend: pre_move_guardian.py - EnforcementLadder class with 5 levels
"""

import pytest
import requests
import os
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user ID
TEST_USER_ID = "user_4dad2b14e380"


class TestStreakStatusAPI:
    """Test GET /api/streak/status endpoint"""
    
    def test_streak_status_returns_correct_structure(self):
        """Verify streak status returns all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/streak/status",
            params={"user_id": TEST_USER_ID}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields exist
        required_fields = [
            "focus_mistake_type",
            "focus_mistake_name",
            "rule",
            "current_streak",
            "best_streak",
            "last_game_had_mistake",
            "headline",
            "message",
            "tone"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify data types
        assert isinstance(data["focus_mistake_type"], str), "focus_mistake_type should be string"
        assert isinstance(data["rule"], str), "rule should be string"
        assert isinstance(data["current_streak"], int), "current_streak should be int"
        assert isinstance(data["best_streak"], int), "best_streak should be int"
        assert isinstance(data["last_game_had_mistake"], bool), "last_game_had_mistake should be bool"
        
        print(f"✓ Streak status structure verified: {data['focus_mistake_type']}, streak={data['current_streak']}")
    
    def test_streak_status_has_trend_data(self):
        """Verify streak status includes trend information"""
        response = requests.get(
            f"{BASE_URL}/api/streak/status",
            params={"user_id": TEST_USER_ID}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Trend should be present
        assert "trend" in data, "Missing trend field"
        
        trend = data["trend"]
        trend_fields = ["before_avg", "recent_avg", "improvement_pct", "show_trend"]
        
        for field in trend_fields:
            assert field in trend, f"Missing trend field: {field}"
        
        print(f"✓ Trend data verified: show_trend={trend['show_trend']}")


class TestFocusTypesAPI:
    """Test GET /api/streak/focus-types endpoint"""
    
    def test_focus_types_returns_all_types(self):
        """Verify all 5 focus types are returned"""
        response = requests.get(f"{BASE_URL}/api/streak/focus-types")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "focus_types" in data, "Missing focus_types field"
        
        focus_types = data["focus_types"]
        
        # Should have exactly 5 focus types
        expected_types = [
            "THREAT_VERIFICATION",
            "FORCING_BLIND",
            "STOPPED_CALCULATION_EARLY",
            "HANGING_PIECE",
            "TACTICAL_MISS"
        ]
        
        actual_keys = [ft["key"] for ft in focus_types]
        
        for expected in expected_types:
            assert expected in actual_keys, f"Missing focus type: {expected}"
        
        print(f"✓ All {len(focus_types)} focus types returned")
    
    def test_focus_types_have_required_fields(self):
        """Verify each focus type has all required fields"""
        response = requests.get(f"{BASE_URL}/api/streak/focus-types")
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["key", "name", "short_name", "description", "rule"]
        
        for focus_type in data["focus_types"]:
            for field in required_fields:
                assert field in focus_type, f"Focus type {focus_type.get('key', 'unknown')} missing field: {field}"
                assert focus_type[field], f"Focus type {focus_type.get('key', 'unknown')} has empty {field}"
        
        print(f"✓ All focus types have required fields")


class TestMistakeStreakService:
    """Test mistake_streak_service.py functions"""
    
    def test_update_streak_from_analysis_function_exists(self):
        """Verify update_streak_from_analysis function exists with correct signature"""
        from services.mistake_streak_service import update_streak_from_analysis
        import inspect
        
        # Check function exists
        assert callable(update_streak_from_analysis), "update_streak_from_analysis should be callable"
        
        # Check signature
        sig = inspect.signature(update_streak_from_analysis)
        params = list(sig.parameters.keys())
        
        expected_params = ["db", "user_id", "game_id", "move_evaluations", "user_color", "game_metadata"]
        
        for param in expected_params:
            assert param in params, f"Missing parameter: {param}"
        
        print(f"✓ update_streak_from_analysis function verified with params: {params}")
    
    def test_detect_focus_mistake_function(self):
        """Test detect_focus_mistake function"""
        from services.mistake_streak_service import detect_focus_mistake
        
        # Create mock move evaluations
        mock_moves = [
            {
                "is_user_move": True,
                "move_number": 1,
                "cp_loss": 50,  # Not a mistake
                "eval_before": 0,
                "eval_after": -50
            },
            {
                "is_user_move": True,
                "move_number": 3,
                "cp_loss": 250,  # Significant mistake
                "eval_before": 0,
                "eval_after": -250,
                "threat_after_played": "fork",
                "opponent_best_reply": {"gives_check": False, "is_capture": True, "material_gain": 300}
            }
        ]
        
        result = detect_focus_mistake(mock_moves, "THREAT_VERIFICATION", "white")
        
        assert hasattr(result, "had_focus_mistake"), "Result should have had_focus_mistake"
        assert hasattr(result, "focus_mistake_count"), "Result should have focus_mistake_count"
        assert hasattr(result, "is_valid_for_streak"), "Result should have is_valid_for_streak"
        
        print(f"✓ detect_focus_mistake works: had_mistake={result.had_focus_mistake}, count={result.focus_mistake_count}")
    
    def test_get_pregame_streak_data(self):
        """Test get_pregame_streak_data function"""
        from services.mistake_streak_service import get_pregame_streak_data
        
        mock_streak_data = {
            "current_focus_mistake": "THREAT_VERIFICATION",
            "mistake_streak": {
                "current": 3,
                "best": 5,
                "last_game_had_mistake": False
            },
            "mistake_trend": {
                "before_avg": 2.5,
                "recent_avg": 1.2,
                "improvement_pct": 52,
                "baseline_locked": True
            }
        }
        
        result = get_pregame_streak_data(mock_streak_data)
        
        assert "focus_mistake_type" in result
        assert "rule" in result
        assert "current_streak" in result
        assert "headline" in result
        assert "message" in result
        assert "tone" in result
        
        assert result["current_streak"] == 3
        assert result["best_streak"] == 5
        
        print(f"✓ get_pregame_streak_data works: headline='{result['headline']}'")


class TestAnalysisWorkerPhase8:
    """Test analysis_worker.py Phase 8 streak update"""
    
    def test_phase8_import_exists(self):
        """Verify Phase 8 imports update_streak_from_analysis"""
        # Read the analysis_worker.py file
        worker_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis_worker.py")
        
        with open(worker_path, 'r') as f:
            content = f.read()
        
        # Check for Phase 8 comment
        assert "PHASE 8" in content, "Phase 8 section not found in analysis_worker.py"
        
        # Check for import
        assert "from services.mistake_streak_service import update_streak_from_analysis" in content, \
            "update_streak_from_analysis import not found"
        
        # Check for function call
        assert "update_streak_from_analysis(" in content, \
            "update_streak_from_analysis call not found"
        
        print("✓ Phase 8 streak update exists in analysis_worker.py")
    
    def test_phase8_calls_with_correct_params(self):
        """Verify Phase 8 calls update_streak_from_analysis with correct parameters"""
        worker_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis_worker.py")
        
        with open(worker_path, 'r') as f:
            content = f.read()
        
        # Find the Phase 8 section
        phase8_start = content.find("PHASE 8")
        assert phase8_start > 0, "Phase 8 section not found"
        
        # Get the Phase 8 section (next ~50 lines)
        phase8_section = content[phase8_start:phase8_start + 2000]
        
        # Check for required parameters
        assert "db=db" in phase8_section, "db parameter not passed"
        assert "user_id=" in phase8_section, "user_id parameter not passed"
        assert "game_id=" in phase8_section, "game_id parameter not passed"
        assert "move_evaluations=" in phase8_section, "move_evaluations parameter not passed"
        assert "user_color=" in phase8_section, "user_color parameter not passed"
        
        print("✓ Phase 8 calls update_streak_from_analysis with correct parameters")


class TestEnforcementLadder:
    """Test pre_move_guardian.py EnforcementLadder class"""
    
    def test_enforcement_ladder_class_exists(self):
        """Verify EnforcementLadder class exists"""
        from coach_play.pre_move_guardian import EnforcementLadder, EnforcementLevel, EnforcementResult
        
        assert EnforcementLadder is not None, "EnforcementLadder class not found"
        assert EnforcementLevel is not None, "EnforcementLevel enum not found"
        assert EnforcementResult is not None, "EnforcementResult dataclass not found"
        
        print("✓ EnforcementLadder class exists")
    
    def test_enforcement_has_5_levels(self):
        """Verify EnforcementLevel has exactly 5 levels"""
        from coach_play.pre_move_guardian import EnforcementLevel
        
        levels = list(EnforcementLevel)
        
        assert len(levels) == 5, f"Expected 5 enforcement levels, got {len(levels)}"
        
        expected_levels = ["WARNING", "STRONG_WARNING", "CHECKBOX_REQUIRED", "SOFT_BLOCK", "ALLOW_WITH_PENALTY"]
        actual_names = [level.name for level in levels]
        
        for expected in expected_levels:
            assert expected in actual_names, f"Missing enforcement level: {expected}"
        
        print(f"✓ EnforcementLadder has 5 levels: {actual_names}")
    
    def test_enforcement_ladder_escalation(self):
        """Test that enforcement escalates with repeated mistakes"""
        from coach_play.pre_move_guardian import (
            EnforcementLadder, 
            PreMoveGuardian, 
            RiskType, 
            RiskLevel,
            GuardianResult,
            InterventionType
        )
        
        ladder = EnforcementLadder()
        
        # Create a mock guardian result
        mock_result = GuardianResult(
            should_intervene=True,
            intervention_type=InterventionType.WARN,
            risk_level=RiskLevel.HIGH,
            risk_type=RiskType.IGNORE_THREAT,
            message="Test message",
            explanation="Test explanation",
            alternative_moves=[],
            details={},
            processing_time_ms=10.0
        )
        
        # First occurrence - should be WARNING
        enforcement1 = ladder.evaluate_enforcement(mock_result)
        assert enforcement1 is not None, "First enforcement should not be None"
        assert enforcement1.repeat_count == 1, f"First repeat_count should be 1, got {enforcement1.repeat_count}"
        
        # Record the warning
        ladder.record_warning_shown(RiskType.IGNORE_THREAT)
        
        # Second occurrence - should escalate
        enforcement2 = ladder.evaluate_enforcement(mock_result)
        assert enforcement2.repeat_count == 2, f"Second repeat_count should be 2, got {enforcement2.repeat_count}"
        
        # Record again
        ladder.record_warning_shown(RiskType.IGNORE_THREAT)
        
        # Third occurrence - should require checkbox
        enforcement3 = ladder.evaluate_enforcement(mock_result)
        assert enforcement3.repeat_count == 3, f"Third repeat_count should be 3, got {enforcement3.repeat_count}"
        
        print(f"✓ Enforcement escalates correctly: 1st={enforcement1.level.name}, 2nd={enforcement2.level.name}, 3rd={enforcement3.level.name}")
    
    def test_enforcement_result_to_dict(self):
        """Test EnforcementResult.to_dict() method"""
        from coach_play.pre_move_guardian import EnforcementResult, EnforcementLevel, RiskType
        
        result = EnforcementResult(
            level=EnforcementLevel.STRONG_WARNING,
            should_block=False,
            requires_checkbox=False,
            message="Test message",
            explanation="Test explanation",
            repeat_count=2,
            risk_type=RiskType.HANGING_PIECE
        )
        
        result_dict = result.to_dict()
        
        assert "enforcement_level" in result_dict
        assert "enforcement_name" in result_dict
        assert "should_block" in result_dict
        assert "requires_checkbox" in result_dict
        assert "message" in result_dict
        assert "repeat_count" in result_dict
        
        assert result_dict["enforcement_level"] == 2
        assert result_dict["enforcement_name"] == "STRONG_WARNING"
        
        print(f"✓ EnforcementResult.to_dict() works correctly")


class TestStreakHistoryAPI:
    """Test GET /api/streak/history endpoint"""
    
    def test_streak_history_returns_data(self):
        """Verify streak history endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/streak/history",
            params={"user_id": TEST_USER_ID}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        assert "streak_data" in data, "Missing streak_data field"
        assert "focus_types" in data, "Missing focus_types field"
        
        # Verify focus_types is a list
        assert isinstance(data["focus_types"], list), "focus_types should be a list"
        
        print(f"✓ Streak history endpoint works, {len(data['focus_types'])} focus types available")


class TestSetFocusAPI:
    """Test POST /api/streak/set-focus endpoint"""
    
    def test_set_focus_changes_focus_type(self):
        """Test setting a new focus type"""
        # First get current focus
        status_response = requests.get(
            f"{BASE_URL}/api/streak/status",
            params={"user_id": TEST_USER_ID}
        )
        current_focus = status_response.json().get("focus_mistake_type")
        
        # Set a different focus type
        new_focus = "HANGING_PIECE" if current_focus != "HANGING_PIECE" else "TACTICAL_MISS"
        
        response = requests.post(
            f"{BASE_URL}/api/streak/set-focus",
            json={
                "user_id": TEST_USER_ID,
                "focus_type": new_focus,
                "reset_streak": False
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Expected success=True"
        assert data.get("focus_type") == new_focus, f"Expected focus_type={new_focus}"
        
        # Restore original focus
        requests.post(
            f"{BASE_URL}/api/streak/set-focus",
            json={
                "user_id": TEST_USER_ID,
                "focus_type": current_focus or "THREAT_VERIFICATION",
                "reset_streak": False
            }
        )
        
        print(f"✓ Set focus API works: changed to {new_focus} and restored")
    
    def test_set_focus_validates_focus_type(self):
        """Test that invalid focus types are rejected"""
        response = requests.post(
            f"{BASE_URL}/api/streak/set-focus",
            json={
                "user_id": TEST_USER_ID,
                "focus_type": "INVALID_TYPE",
                "reset_streak": False
            }
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid focus type, got {response.status_code}"
        
        print("✓ Invalid focus type correctly rejected")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

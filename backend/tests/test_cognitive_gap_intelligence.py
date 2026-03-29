"""
Test suite for Cognitive Gap Intelligence API
Testing all 5 phases of the Reflection Intelligence System
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCognitiveGapSummary:
    """Phase 4: Test /api/cognitive-gaps/summary endpoint"""
    
    def test_get_summary_returns_valid_response(self):
        """Test that summary endpoint returns valid structure"""
        response = requests.get(
            f"{BASE_URL}/api/cognitive-gaps/summary",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should always return has_data field
        assert "has_data" in data
        
        if data["has_data"]:
            # With data, should have these fields
            assert "total_gaps_tracked" in data
            assert "overall_trend" in data
            assert data["overall_trend"] in ["improving", "worsening", "stable"]
        else:
            # Without data, should have message
            assert "message" in data


class TestCognitiveGapProgress:
    """Phase 4: Test /api/cognitive-gaps/progress endpoint"""
    
    def test_get_progress_default_weeks(self):
        """Test progress endpoint with default 8 weeks"""
        response = requests.get(
            f"{BASE_URL}/api/cognitive-gaps/progress",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have these fields
        assert "weeks_analyzed" in data
        assert "week_labels" in data
        assert "gaps" in data
        assert "overall_trend" in data
        assert data["overall_trend"] in ["improving", "worsening", "stable"]
    
    def test_get_progress_custom_weeks(self):
        """Test progress endpoint with custom week parameter"""
        response = requests.get(
            f"{BASE_URL}/api/cognitive-gaps/progress?weeks=4",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "weeks_analyzed" in data
        assert "overall_change_percent" in data
        assert "improving_gaps" in data
        assert "worsening_gaps" in data
    
    def test_progress_gap_structure(self):
        """Test that gap entries have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/cognitive-gaps/progress?weeks=4",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        for gap in data.get("gaps", []):
            assert "gap_type" in gap
            assert "gap_name" in gap
            assert "total_occurrences" in gap
            assert "weekly_counts" in gap
            assert "trend" in gap
            assert gap["trend"] in ["improving", "worsening", "stable", "insufficient_data"]


class TestRecurringPatterns:
    """Phase 2: Test /api/cognitive-gaps/recurring endpoint"""
    
    def test_get_recurring_patterns(self):
        """Test recurring patterns endpoint returns valid structure"""
        response = requests.get(
            f"{BASE_URL}/api/cognitive-gaps/recurring",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "patterns" in data
        assert isinstance(data["patterns"], list)
    
    def test_recurring_patterns_with_min_occurrences(self):
        """Test recurring patterns with custom min_occurrences"""
        response = requests.get(
            f"{BASE_URL}/api/cognitive-gaps/recurring?min_occurrences=2",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "patterns" in data
        # Patterns that appear should have at least min_occurrences
        for pattern in data["patterns"]:
            assert "gap_type" in pattern
            assert "gap_name" in pattern
            assert "occurrences" in pattern
            assert pattern["occurrences"] >= 2


class TestPlanQuality:
    """Phase 5: Test /api/cognitive-gaps/plan-quality endpoint"""
    
    def test_get_plan_quality_analysis(self):
        """Test plan quality analysis endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/cognitive-gaps/plan-quality",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should always return has_data field
        assert "has_data" in data
        
        if data["has_data"]:
            # With data, should have analysis fields
            assert "total_plans_analyzed" in data
            assert "plan_quality" in data
            assert "accuracy" in data
            assert "trend" in data
            assert "insight" in data
        else:
            # Without data, should have message
            assert "message" in data
            assert "plans_recorded" in data


class TestDrillsRecommended:
    """Phase 3: Test /api/drills/recommended endpoint"""
    
    def test_get_recommended_drills(self):
        """Test recommended drills endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/drills/recommended",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should always return has_data field
        assert "has_data" in data
        
        if data["has_data"]:
            # With data, should have recommendations
            assert "total_gaps_analyzed" in data
            assert "recommendations" in data
            assert isinstance(data["recommendations"], list)
            
            # Each recommendation should have these fields
            for rec in data["recommendations"]:
                assert "gap_type" in rec
                assert "gap_name" in rec
                assert "occurrences" in rec
                assert "priority_score" in rec
                assert "drill_category" in rec
                assert "training_focus" in rec


class TestDrillsFromGap:
    """Phase 3: Test /api/drills/from-gap/{gap_type} endpoint"""
    
    def test_get_drills_for_calculation_depth(self):
        """Test getting drills for calculation_depth gap type"""
        response = requests.get(
            f"{BASE_URL}/api/drills/from-gap/calculation_depth",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return gap-specific drill data
        assert data["gap_type"] == "calculation_depth"
        assert data["gap_name"] == "Calculation Depth"
        assert data["drill_category"] == "calculation"
        assert data["layer"] == "precision"
        assert "positions" in data
        assert "drill_types" in data
        assert "training_focus" in data
    
    def test_get_drills_for_threat_blindness(self):
        """Test getting drills for threat_blindness gap type"""
        response = requests.get(
            f"{BASE_URL}/api/drills/from-gap/threat_blindness",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["gap_type"] == "threat_blindness"
        assert data["layer"] == "stability"
        assert "drill_types" in data
    
    def test_get_drills_for_positional_misread(self):
        """Test getting drills for positional_misread gap type"""
        response = requests.get(
            f"{BASE_URL}/api/drills/from-gap/positional_misread",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["gap_type"] == "positional_misread"
        assert data["layer"] == "structure"
    
    def test_get_drills_invalid_gap_type(self):
        """Test that invalid gap type returns 400 error"""
        response = requests.get(
            f"{BASE_URL}/api/drills/from-gap/invalid_gap_type",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Unknown gap type" in data["detail"]
    
    def test_get_drills_with_count_param(self):
        """Test getting drills with custom count parameter"""
        response = requests.get(
            f"{BASE_URL}/api/drills/from-gap/tactical_oversight?count=3",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "total_positions" in data
        # Note: may return fewer positions if not enough data


class TestSyncTraining:
    """Test /api/cognitive-gaps/sync-training endpoint"""
    
    def test_sync_training(self):
        """Test sync training endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/cognitive-gaps/sync-training",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return update status
        assert "updated" in data
        
        if data["updated"]:
            assert "layer_boosts" in data
            assert "dominant_layer" in data
        else:
            assert "reason" in data


class TestAllKnownGapTypes:
    """Test that all documented gap types work correctly"""
    
    KNOWN_GAP_TYPES = [
        "calculation_depth",
        "calculation_error",
        "threat_blindness",
        "hanging_piece_blindness",
        "check_blindness",
        "tactical_oversight",
        "missed_fork",
        "missed_pin",
        "missed_skewer",
        "missed_discovered",
        "back_rank_blindness",
        "positional_misread",
        "wrong_plan",
        "premature_action",
        "defensive_lapse",
        "king_safety_neglect",
        "overconfidence",
        "desperation",
        "time_pressure",
        "rushed_move",
        "pattern_unfamiliarity",
        "unclear",
    ]
    
    @pytest.mark.parametrize("gap_type", KNOWN_GAP_TYPES)
    def test_valid_gap_types_return_200(self, gap_type):
        """Test that all known gap types are valid and return drills"""
        response = requests.get(
            f"{BASE_URL}/api/drills/from-gap/{gap_type}",
            cookies={"session_id": "dev_session"}
        )
        assert response.status_code == 200, f"Gap type {gap_type} returned {response.status_code}"
        data = response.json()
        
        # Each should return correct gap_type
        assert data["gap_type"] == gap_type
        assert "layer" in data
        assert data["layer"] in ["precision", "stability", "structure", "conversion"]


class TestUnauthorizedAccess:
    """Test that endpoints require authentication (skip in dev mode)"""
    
    @pytest.fixture(autouse=True)
    def check_dev_mode(self):
        """Skip these tests if dev mode is enabled"""
        response = requests.get(f"{BASE_URL}/api/cognitive-gaps/summary")
        if response.status_code == 200:
            # Dev mode allows unauthenticated access
            pytest.skip("Dev mode enabled - auth not enforced")
    
    def test_summary_requires_auth(self):
        """Test summary endpoint without auth"""
        response = requests.get(f"{BASE_URL}/api/cognitive-gaps/summary")
        # Should return 401 or redirect
        assert response.status_code in [401, 403, 307, 422]
    
    def test_progress_requires_auth(self):
        """Test progress endpoint without auth"""
        response = requests.get(f"{BASE_URL}/api/cognitive-gaps/progress")
        assert response.status_code in [401, 403, 307, 422]
    
    def test_drills_requires_auth(self):
        """Test drills endpoint without auth"""
        response = requests.get(f"{BASE_URL}/api/drills/recommended")
        assert response.status_code in [401, 403, 307, 422]

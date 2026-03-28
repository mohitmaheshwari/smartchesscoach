"""
Test suite for Focus Mastery API and Service.

Tests the /api/missions/focus-mastery endpoint and the focus_mastery_service.py
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture
def api_session():
    """Create a session and perform dev login."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Dev login to get cookie-based auth
    login_resp = session.get(f"{BASE_URL}/api/auth/dev-login", allow_redirects=True)
    # Dev login sets a cookie - session will retain it
    
    return session


class TestFocusMasteryAPI:
    """Tests for the /api/missions/focus-mastery endpoint."""
    
    def test_focus_mastery_endpoint_returns_200(self, api_session):
        """Focus mastery endpoint should return 200 for authenticated users."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_focus_mastery_returns_focus_mastery_field(self, api_session):
        """Response should contain focus_mastery field with comprehensive data."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        assert "focus_mastery" in data, "Response should contain 'focus_mastery' field"
    
    def test_focus_mastery_returns_masteries_legacy_field(self, api_session):
        """Response should contain masteries field for backwards compatibility."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        assert "masteries" in data, "Response should contain 'masteries' legacy field"
    
    def test_focus_mastery_contains_user_id(self, api_session):
        """focus_mastery should contain user_id field."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        assert "user_id" in fm, "focus_mastery should contain 'user_id'"
    
    def test_focus_mastery_contains_patterns(self, api_session):
        """focus_mastery should contain patterns dict with pattern data."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        assert "patterns" in fm, "focus_mastery should contain 'patterns'"
        assert isinstance(fm["patterns"], dict), "patterns should be a dict"
    
    def test_focus_mastery_contains_overall_mastery(self, api_session):
        """focus_mastery should contain overall_mastery score."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        assert "overall_mastery" in fm, "focus_mastery should contain 'overall_mastery'"
        assert isinstance(fm["overall_mastery"], (int, float)), "overall_mastery should be a number"
        assert 0 <= fm["overall_mastery"] <= 100, "overall_mastery should be between 0-100"
    
    def test_focus_mastery_contains_overall_level(self, api_session):
        """focus_mastery should contain overall_level (master/proficient/competent/developing/novice)."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        assert "overall_level" in fm, "focus_mastery should contain 'overall_level'"
        
        valid_levels = ["master", "proficient", "competent", "developing", "novice"]
        assert fm["overall_level"] in valid_levels, f"overall_level should be one of {valid_levels}"
    
    def test_focus_mastery_contains_top_strength(self, api_session):
        """focus_mastery should contain top_strength with pattern and score."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        assert "top_strength" in fm, "focus_mastery should contain 'top_strength'"
        
        ts = fm.get("top_strength")
        if ts is not None:  # Can be None if no data
            assert "pattern" in ts, "top_strength should have 'pattern' field"
            assert "name" in ts, "top_strength should have 'name' field"
            assert "score" in ts, "top_strength should have 'score' field"
    
    def test_focus_mastery_contains_biggest_gap(self, api_session):
        """focus_mastery should contain biggest_gap with pattern and score."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        assert "biggest_gap" in fm, "focus_mastery should contain 'biggest_gap'"
        
        bg = fm.get("biggest_gap")
        if bg is not None:  # Can be None if no data
            assert "pattern" in bg, "biggest_gap should have 'pattern' field"
            assert "name" in bg, "biggest_gap should have 'name' field"
            assert "score" in bg, "biggest_gap should have 'score' field"
    
    def test_focus_mastery_contains_recommended_focus(self, api_session):
        """focus_mastery should contain recommended_focus pattern key."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        assert "recommended_focus" in fm, "focus_mastery should contain 'recommended_focus'"
    
    def test_focus_mastery_patterns_have_required_fields(self, api_session):
        """Each pattern in patterns dict should have required fields."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        patterns = fm.get("patterns", {})
        
        required_fields = [
            "pattern_key", "name", "category", "description", "protocol",
            "mastery_score", "mastery_level", "trend", "occurrences_recent",
            "occurrences_total", "last_occurrence", "improvement_rate"
        ]
        
        for pattern_key, pattern_data in patterns.items():
            for field in required_fields:
                assert field in pattern_data, f"Pattern '{pattern_key}' missing required field '{field}'"
    
    def test_focus_mastery_patterns_have_valid_mastery_level(self, api_session):
        """Each pattern should have a valid mastery_level."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        patterns = fm.get("patterns", {})
        
        valid_levels = ["master", "proficient", "competent", "developing", "novice"]
        
        for pattern_key, pattern_data in patterns.items():
            level = pattern_data.get("mastery_level")
            assert level in valid_levels, f"Pattern '{pattern_key}' has invalid mastery_level '{level}'"
    
    def test_focus_mastery_patterns_have_valid_trend(self, api_session):
        """Each pattern should have a valid trend value."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        patterns = fm.get("patterns", {})
        
        valid_trends = ["improving", "stable", "declining"]
        
        for pattern_key, pattern_data in patterns.items():
            trend = pattern_data.get("trend")
            assert trend in valid_trends, f"Pattern '{pattern_key}' has invalid trend '{trend}'"
    
    def test_focus_mastery_contains_total_patterns_tracked(self, api_session):
        """focus_mastery should contain total_patterns_tracked count."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        assert "total_patterns_tracked" in fm, "focus_mastery should contain 'total_patterns_tracked'"
        assert isinstance(fm["total_patterns_tracked"], int), "total_patterns_tracked should be int"
        assert fm["total_patterns_tracked"] >= 0, "total_patterns_tracked should be non-negative"
    
    def test_focus_mastery_contains_active_patterns(self, api_session):
        """focus_mastery should contain active_patterns list."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        assert "active_patterns" in fm, "focus_mastery should contain 'active_patterns'"
        assert isinstance(fm["active_patterns"], list), "active_patterns should be a list"


class TestFocusMasteryPatternDetails:
    """Tests for pattern-specific data in focus_mastery response."""
    
    def test_pattern_mastery_score_is_valid_range(self, api_session):
        """mastery_score should be between 0-100."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        patterns = fm.get("patterns", {})
        
        for pattern_key, pattern_data in patterns.items():
            score = pattern_data.get("mastery_score", 0)
            assert 0 <= score <= 100, f"Pattern '{pattern_key}' has invalid score {score}"
    
    def test_pattern_protocol_is_list(self, api_session):
        """protocol field should be a list of steps."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        patterns = fm.get("patterns", {})
        
        for pattern_key, pattern_data in patterns.items():
            protocol = pattern_data.get("protocol", [])
            assert isinstance(protocol, list), f"Pattern '{pattern_key}' protocol should be a list"
            # Protocol steps should be non-empty strings
            for step in protocol:
                assert isinstance(step, str) and len(step) > 0, f"Protocol steps should be non-empty strings"
    
    def test_pattern_category_is_valid(self, api_session):
        """category should be one of tactical/positional/decision."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        patterns = fm.get("patterns", {})
        
        valid_categories = ["tactical", "positional", "decision"]
        
        for pattern_key, pattern_data in patterns.items():
            category = pattern_data.get("category")
            assert category in valid_categories, f"Pattern '{pattern_key}' has invalid category '{category}'"
    
    def test_known_patterns_are_present(self, api_session):
        """Known cognitive patterns should be present in response."""
        response = api_session.get(f"{BASE_URL}/api/missions/focus-mastery")
        assert response.status_code == 200
        
        data = response.json()
        fm = data.get("focus_mastery", {})
        patterns = fm.get("patterns", {})
        
        # These patterns are defined in focus_mastery_service.py
        expected_patterns = [
            "check_captures_threats",
            "scan_for_pins",
            "calculate_forcing_moves",
            "look_for_forks",
            "piece_activity_check",
            "king_safety_awareness",
            "pawn_structure_thinking",
            "avoid_hope_chess",
            "slow_down_critical",
            "prophylaxis_thinking",
        ]
        
        for expected in expected_patterns:
            assert expected in patterns, f"Expected pattern '{expected}' not found in response"

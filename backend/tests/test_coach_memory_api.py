"""
Test Coach Memory API - GET /api/coach/memory endpoint
Tests the new CoachMemoryPanel backend integration.

Tests:
1. GET /api/coach/memory returns context with required fields
2. watch_for patterns contain name, count, improving fields
3. focus_suggestion is returned when available
4. games_played count is returned
5. last_game_insights is returned
6. avg_accuracy is returned
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://coach-memory-1.preview.emergentagent.com')


class TestCoachMemoryAPI:
    """Test GET /api/coach/memory endpoint"""
    
    def test_coach_memory_endpoint_returns_200(self, authenticated_session):
        """GET /api/coach/memory returns 200 OK"""
        response = authenticated_session.get(f"{BASE_URL}/api/coach/memory")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_coach_memory_returns_greeting(self, authenticated_session):
        """Response includes greeting field"""
        response = authenticated_session.get(f"{BASE_URL}/api/coach/memory")
        data = response.json()
        
        assert "greeting" in data, "Response missing 'greeting' field"
        assert isinstance(data["greeting"], str), "Greeting should be a string"
        assert len(data["greeting"]) > 0, "Greeting should not be empty"
    
    def test_coach_memory_returns_context(self, authenticated_session):
        """Response includes context object"""
        response = authenticated_session.get(f"{BASE_URL}/api/coach/memory")
        data = response.json()
        
        assert "context" in data, "Response missing 'context' field"
        assert isinstance(data["context"], dict), "Context should be a dict"
    
    def test_coach_memory_context_has_games_played(self, authenticated_session):
        """Context includes games_played count"""
        response = authenticated_session.get(f"{BASE_URL}/api/coach/memory")
        data = response.json()
        
        context = data.get("context", {})
        assert "games_played" in context, "Context missing 'games_played'"
        assert isinstance(context["games_played"], (int, float)), "games_played should be numeric"
    
    def test_coach_memory_context_has_avg_accuracy(self, authenticated_session):
        """Context includes avg_accuracy"""
        response = authenticated_session.get(f"{BASE_URL}/api/coach/memory")
        data = response.json()
        
        context = data.get("context", {})
        assert "avg_accuracy" in context, "Context missing 'avg_accuracy'"
        assert isinstance(context["avg_accuracy"], (int, float)), "avg_accuracy should be numeric"
    
    def test_coach_memory_context_has_watch_for(self, authenticated_session):
        """Context includes watch_for array"""
        response = authenticated_session.get(f"{BASE_URL}/api/coach/memory")
        data = response.json()
        
        context = data.get("context", {})
        assert "watch_for" in context, "Context missing 'watch_for'"
        assert isinstance(context["watch_for"], list), "watch_for should be a list"
    
    def test_coach_memory_watch_for_pattern_structure(self, authenticated_session):
        """watch_for patterns have name, count, improving fields"""
        response = authenticated_session.get(f"{BASE_URL}/api/coach/memory")
        data = response.json()
        
        watch_for = data.get("context", {}).get("watch_for", [])
        
        # If there are patterns, verify structure
        if len(watch_for) > 0:
            pattern = watch_for[0]
            assert "name" in pattern, "Pattern missing 'name' field"
            assert "count" in pattern, "Pattern missing 'count' field"
            assert "improving" in pattern, "Pattern missing 'improving' field"
            
            assert isinstance(pattern["name"], str), "Pattern name should be string"
            assert isinstance(pattern["count"], (int, float)), "Pattern count should be numeric"
            assert isinstance(pattern["improving"], bool), "Pattern improving should be boolean"
    
    def test_coach_memory_context_has_focus_suggestion(self, authenticated_session):
        """Context includes focus_suggestion field (can be null)"""
        response = authenticated_session.get(f"{BASE_URL}/api/coach/memory")
        data = response.json()
        
        context = data.get("context", {})
        # focus_suggestion can be null/None, but should be in the response
        assert "focus_suggestion" in context, "Context missing 'focus_suggestion'"
    
    def test_coach_memory_context_has_last_game_insights(self, authenticated_session):
        """Context includes last_game_insights array"""
        response = authenticated_session.get(f"{BASE_URL}/api/coach/memory")
        data = response.json()
        
        context = data.get("context", {})
        assert "last_game_insights" in context, "Context missing 'last_game_insights'"
        assert isinstance(context["last_game_insights"], list), "last_game_insights should be a list"
    
    def test_coach_memory_context_has_openings_known(self, authenticated_session):
        """Context includes openings_known array"""
        response = authenticated_session.get(f"{BASE_URL}/api/coach/memory")
        data = response.json()
        
        context = data.get("context", {})
        assert "openings_known" in context, "Context missing 'openings_known'"
        assert isinstance(context["openings_known"], list), "openings_known should be a list"
    
    def test_coach_memory_context_has_improving_flag(self, authenticated_session):
        """Context includes improving boolean flag"""
        response = authenticated_session.get(f"{BASE_URL}/api/coach/memory")
        data = response.json()
        
        context = data.get("context", {})
        assert "improving" in context, "Context missing 'improving'"
        assert isinstance(context["improving"], bool), "improving should be boolean"
    
    def test_coach_memory_returns_valid_response_unauthenticated(self, api_client):
        """GET /api/coach/memory works in dev mode (dev user fallback)"""
        response = api_client.get(f"{BASE_URL}/api/coach/memory")
        
        # In dev mode, should return 200 with dev user data
        # Note: Auth is bypassed in dev mode for easier testing
        assert response.status_code == 200, f"Expected 200 (dev mode), got {response.status_code}"
        data = response.json()
        assert "context" in data, "Dev mode should return valid context"


class TestCoachMemoryUpdateAPI:
    """Test POST /api/coach/memory/update endpoint"""
    
    def test_memory_update_returns_success(self, authenticated_session):
        """POST /api/coach/memory/update returns success response"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/memory/update",
            json={
                "session_id": None,  # Can be null for testing
                "game_result": "win",
                "accuracy": 85.0,
                "blunders": 1,
                "mistakes": 2,
                "habits_violated": [],
                "habits_improved": [],
                "performance_rating": 1200
            }
        )
        
        # Should return success
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") is True, "Response should indicate success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

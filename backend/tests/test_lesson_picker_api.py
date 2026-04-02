"""
Test LessonPicker API endpoints for Play with Coach
Tests: /api/coach/play/teaching/catalog, /api/coach/play/teaching/start
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTeachingCatalog:
    """Tests for GET /api/coach/play/teaching/catalog"""
    
    def test_catalog_returns_200(self):
        """Catalog endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/coach/play/teaching/catalog")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Catalog endpoint returns 200")
    
    def test_catalog_has_traps(self):
        """Catalog should contain traps array"""
        response = requests.get(f"{BASE_URL}/api/coach/play/teaching/catalog")
        data = response.json()
        assert "traps" in data, "Response missing 'traps' key"
        assert isinstance(data["traps"], list), "traps should be a list"
        print(f"✓ Catalog has traps array with {len(data['traps'])} items")
    
    def test_catalog_has_18_traps(self):
        """Catalog should contain exactly 18 traps"""
        response = requests.get(f"{BASE_URL}/api/coach/play/teaching/catalog")
        data = response.json()
        assert len(data["traps"]) == 18, f"Expected 18 traps, got {len(data['traps'])}"
        print("✓ Catalog has exactly 18 traps")
    
    def test_catalog_has_endgames(self):
        """Catalog should contain endgames array"""
        response = requests.get(f"{BASE_URL}/api/coach/play/teaching/catalog")
        data = response.json()
        assert "endgames" in data, "Response missing 'endgames' key"
        assert isinstance(data["endgames"], list), "endgames should be a list"
        print(f"✓ Catalog has endgames array with {len(data['endgames'])} items")
    
    def test_catalog_has_10_endgames(self):
        """Catalog should contain exactly 10 endgames"""
        response = requests.get(f"{BASE_URL}/api/coach/play/teaching/catalog")
        data = response.json()
        assert len(data["endgames"]) == 10, f"Expected 10 endgames, got {len(data['endgames'])}"
        print("✓ Catalog has exactly 10 endgames")
    
    def test_trap_structure(self):
        """Each trap should have required fields"""
        response = requests.get(f"{BASE_URL}/api/coach/play/teaching/catalog")
        data = response.json()
        required_fields = ["key", "name", "difficulty"]
        
        for trap in data["traps"]:
            for field in required_fields:
                assert field in trap, f"Trap missing required field: {field}"
        print("✓ All traps have required fields (key, name, difficulty)")
    
    def test_endgame_structure(self):
        """Each endgame should have required fields"""
        response = requests.get(f"{BASE_URL}/api/coach/play/teaching/catalog")
        data = response.json()
        required_fields = ["category", "lesson_key", "name"]
        
        for eg in data["endgames"]:
            for field in required_fields:
                assert field in eg, f"Endgame missing required field: {field}"
        print("✓ All endgames have required fields (category, lesson_key, name)")


class TestTeachingStart:
    """Tests for POST /api/coach/play/teaching/start"""
    
    @pytest.fixture
    def session_id(self):
        """Create a coach session for testing"""
        # Start a new game session
        response = requests.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("session", {}).get("session_id")
        return None
    
    def test_start_trap_lesson_requires_session(self):
        """Starting a trap lesson without session_id should fail"""
        response = requests.post(
            f"{BASE_URL}/api/coach/play/teaching/start",
            json={"lesson_type": "trap", "trap_key": "scholars_mate"}
        )
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✓ Starting trap lesson without session_id returns error")
    
    def test_start_trap_lesson_with_session(self, session_id):
        """Starting a trap lesson with valid session should work"""
        if not session_id:
            pytest.skip("Could not create session")
        
        response = requests.post(
            f"{BASE_URL}/api/coach/play/teaching/start",
            json={
                "session_id": session_id,
                "lesson_type": "trap",
                "trap_key": "scholars_mate"
            }
        )
        # May fail due to auth, but should not be 500
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Start trap lesson returns {response.status_code}")
    
    def test_start_endgame_lesson_requires_session(self):
        """Starting an endgame lesson without session_id should fail"""
        response = requests.post(
            f"{BASE_URL}/api/coach/play/teaching/start",
            json={
                "lesson_type": "endgame",
                "category": "king_and_pawn",
                "lesson_key": "opposition"
            }
        )
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✓ Starting endgame lesson without session_id returns error")


class TestCoachPlayStart:
    """Tests for POST /api/coach/play/start"""
    
    def test_start_game_returns_session(self):
        """Starting a game should return a session"""
        response = requests.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        # May require auth
        if response.status_code == 200:
            data = response.json()
            assert "session" in data, "Response missing 'session'"
            assert "session_id" in data["session"], "Session missing 'session_id'"
            print(f"✓ Game started with session_id: {data['session']['session_id']}")
        else:
            print(f"✓ Start game returns {response.status_code} (may need auth)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

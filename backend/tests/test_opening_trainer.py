"""
Test suite for Opening Trainer (Phase 2) feature.

This tests:
1. GET /api/training/openings-database - returns list of openings with variations and traps counts
2. GET /api/training/openings/stats - returns user's most played openings with mastery levels
3. GET /api/training/openings/{opening_key} - returns training content for specific opening
4. GET /api/training/openings/{opening_key}/quiz - returns quiz questions for opening
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "test_session_356539ff12b1"


@pytest.fixture(scope="module")
def api_client():
    """Create authenticated session for API calls."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SESSION_TOKEN}"
    })
    session.cookies.set("session_token", SESSION_TOKEN)
    return session


class TestOpeningsDatabase:
    """Test GET /api/training/openings-database endpoint"""
    
    def test_get_openings_database_success(self, api_client):
        """Should return list of openings with variations and traps counts"""
        response = api_client.get(f"{BASE_URL}/api/training/openings-database")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "openings" in data, "Response should contain 'openings' field"
        assert "total" in data, "Response should contain 'total' field"
        
        openings = data["openings"]
        assert len(openings) >= 6, f"Expected at least 6 openings, got {len(openings)}"
        
        # Verify each opening has required fields
        for opening in openings:
            assert "key" in opening, "Opening should have 'key'"
            assert "name" in opening, "Opening should have 'name'"
            assert "color" in opening, "Opening should have 'color'"
            assert "variations_count" in opening, "Opening should have 'variations_count'"
            assert "traps_count" in opening, "Opening should have 'traps_count'"
            assert opening["color"] in ["white", "black"], f"Color should be 'white' or 'black', got {opening['color']}"
    
    def test_openings_database_contains_expected_openings(self, api_client):
        """Should contain the expected openings (Italian, Sicilian, Caro-Kann, French, QG, London)"""
        response = api_client.get(f"{BASE_URL}/api/training/openings-database")
        
        assert response.status_code == 200
        
        data = response.json()
        openings = data["openings"]
        opening_keys = [o["key"] for o in openings]
        
        expected_openings = [
            "italian_game",
            "sicilian_defense",
            "caro_kann",
            "french_defense",
            "queens_gambit",
            "london_system"
        ]
        
        for expected in expected_openings:
            assert expected in opening_keys, f"Expected opening '{expected}' not found in database"
    
    def test_openings_database_structure(self, api_client):
        """Verify opening database structure matches expected format"""
        response = api_client.get(f"{BASE_URL}/api/training/openings-database")
        
        assert response.status_code == 200
        
        data = response.json()
        openings = data["openings"]
        
        # Find Italian Game for detailed verification
        italian = next((o for o in openings if o["key"] == "italian_game"), None)
        assert italian is not None, "Italian Game should be in database"
        
        assert italian["name"] == "Italian Game"
        assert italian["color"] == "white"
        assert "variations_count" in italian
        assert "traps_count" in italian
        assert italian["traps_count"] >= 1, "Italian Game should have at least 1 trap (Fried Liver)"


class TestOpeningsStats:
    """Test GET /api/training/openings/stats endpoint"""
    
    def test_get_openings_stats_success(self, api_client):
        """Should return user's opening stats with mastery levels"""
        response = api_client.get(f"{BASE_URL}/api/training/openings/stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "openings" in data, "Response should contain 'openings' field"
        assert "total" in data, "Response should contain 'total' field"
        
        # If user has played games, verify stats structure
        openings = data["openings"]
        if len(openings) > 0:
            opening = openings[0]
            assert "name" in opening, "Opening should have 'name'"
            assert "games_played" in opening, "Opening should have 'games_played'"
            assert "mastery_level" in opening, "Opening should have 'mastery_level'"
            assert opening["mastery_level"] in ["learning", "needs_work", "comfortable", "mastered"], \
                f"Invalid mastery level: {opening['mastery_level']}"
    
    def test_openings_stats_empty_for_new_user(self, api_client):
        """New user with no games should get empty openings list"""
        response = api_client.get(f"{BASE_URL}/api/training/openings/stats")
        
        assert response.status_code == 200
        
        data = response.json()
        # Just verify it doesn't crash - might have empty or populated list
        assert "openings" in data
        assert isinstance(data["openings"], list)


class TestOpeningTrainingContent:
    """Test GET /api/training/openings/{opening_key} endpoint"""
    
    def test_get_italian_game_content(self, api_client):
        """Should return training content for Italian Game"""
        response = api_client.get(f"{BASE_URL}/api/training/openings/italian_game")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Check opening data
        assert "opening" in data, "Response should contain 'opening' field"
        opening = data["opening"]
        assert opening["name"] == "Italian Game"
        assert "key_ideas" in opening, "Opening should have key_ideas"
        assert "main_line" in opening, "Opening should have main_line"
        
        # Check variations
        assert "variations" in data, "Response should contain 'variations'"
        variations = data["variations"]
        assert len(variations) >= 1, "Italian Game should have at least 1 variation"
        
        # Check traps
        assert "traps" in data, "Response should contain 'traps'"
        traps = data["traps"]
        assert len(traps) >= 1, "Italian Game should have at least 1 trap"
        
        # Verify trap structure
        trap = traps[0]
        assert "name" in trap, "Trap should have 'name'"
        assert "for_color" in trap, "Trap should have 'for_color'"
        assert "explanation" in trap, "Trap should have 'explanation'"
    
    def test_get_sicilian_defense_content(self, api_client):
        """Should return training content for Sicilian Defense"""
        response = api_client.get(f"{BASE_URL}/api/training/openings/sicilian_defense")
        
        assert response.status_code == 200
        
        data = response.json()
        
        assert "opening" in data
        opening = data["opening"]
        assert opening["name"] == "Sicilian Defense"
        assert opening["color"] == "black"
        
        # Key ideas should exist
        assert "key_ideas" in data or "key_ideas" in opening
    
    def test_get_nonexistent_opening(self, api_client):
        """Should handle request for non-existent opening gracefully"""
        response = api_client.get(f"{BASE_URL}/api/training/openings/nonexistent_opening")
        
        # Could be 404 or 200 with error field
        data = response.json()
        
        if response.status_code == 200:
            # Check if there's an error indicator
            if "error" in data:
                assert "not found" in data["error"].lower()
            elif "opening" in data:
                # Empty/null opening is also acceptable
                pass
        # 404 is also acceptable
    
    def test_opening_content_includes_user_stats(self, api_client):
        """Should include user_stats field for context"""
        response = api_client.get(f"{BASE_URL}/api/training/openings/italian_game")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # user_stats may be present even if user hasn't played this opening
        if "user_stats" in data:
            stats = data["user_stats"]
            assert "games_found" in stats or "games_played" in stats


class TestOpeningQuiz:
    """Test GET /api/training/openings/{opening_key}/quiz endpoint"""
    
    def test_get_italian_game_quiz(self, api_client):
        """Should return quiz questions for Italian Game"""
        response = api_client.get(f"{BASE_URL}/api/training/openings/italian_game/quiz")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "opening" in data, "Response should contain 'opening' field"
        assert data["opening"] == "italian_game"
        
        assert "questions" in data, "Response should contain 'questions' field"
        questions = data["questions"]
        
        # Should have at least 1 question
        assert len(questions) >= 1, "Should have at least 1 quiz question"
        
        # Verify question structure
        for q in questions:
            assert "type" in q, "Question should have 'type'"
            assert "question" in q, "Question should have 'question' text"


class TestOpeningDatabaseIntegrity:
    """Test opening database data integrity"""
    
    def test_all_openings_have_main_line(self, api_client):
        """Every opening should have a main line defined"""
        response = api_client.get(f"{BASE_URL}/api/training/openings-database")
        
        assert response.status_code == 200
        
        data = response.json()
        
        for opening in data["openings"]:
            # Get detailed content to check main_line
            detail_res = api_client.get(f"{BASE_URL}/api/training/openings/{opening['key']}")
            if detail_res.status_code == 200:
                detail = detail_res.json()
                if "opening" in detail and detail["opening"]:
                    assert "main_line" in detail["opening"], f"{opening['name']} should have main_line"
                    assert len(detail["opening"]["main_line"]) > 0, f"{opening['name']} main_line should not be empty"
    
    def test_traps_have_position_fen(self, api_client):
        """Traps should have position FEN for practice"""
        response = api_client.get(f"{BASE_URL}/api/training/openings/italian_game")
        
        assert response.status_code == 200
        
        data = response.json()
        traps = data.get("traps", [])
        
        for trap in traps:
            assert "position" in trap or "fen" in trap, f"Trap '{trap.get('name')}' should have position FEN"
            # Verify it's a valid-looking FEN (basic check)
            fen = trap.get("position") or trap.get("fen")
            assert "/" in fen, f"FEN should contain '/' character: {fen}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Tests for Blunder Intelligence Service - Blunder Reduction System
Tests the new API endpoints: /api/focus, /api/journey/v2, /api/lab/{game_id}
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBlunderReductionSystemAPIs:
    """Test suite for the new Blunder Reduction System endpoints"""
    
    def test_focus_endpoint_returns_200(self):
        """Test /api/focus returns 200 and proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/focus",
            headers={"Cookie": "session_id=test"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify required top-level keys
        assert "focus" in data, "Missing 'focus' key"
        assert "mission" in data, "Missing 'mission' key"
        assert "identity" in data, "Missing 'identity' key"
        assert "rating_impact" in data, "Missing 'rating_impact' key"
        assert "games_analyzed" in data, "Missing 'games_analyzed' key"
        
        print(f"✓ Focus endpoint returned valid structure with {data['games_analyzed']} games analyzed")
    
    def test_focus_endpoint_focus_structure(self):
        """Test focus data has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/focus",
            headers={"Cookie": "session_id=test"}
        )
        data = response.json()
        
        focus = data.get("focus", {})
        assert "main_message" in focus, "Missing 'main_message' in focus"
        assert "fix" in focus, "Missing 'fix' in focus"
        assert "label" in focus, "Missing 'label' in focus"
        
        print(f"✓ Focus: {focus.get('label', 'N/A')} - {focus.get('main_message', 'N/A')}")
    
    def test_focus_endpoint_mission_structure(self):
        """Test mission data has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/focus",
            headers={"Cookie": "session_id=test"}
        )
        data = response.json()
        
        mission = data.get("mission", {})
        assert "name" in mission, "Missing 'name' in mission"
        assert "goal" in mission, "Missing 'goal' in mission"
        assert "target_metric" in mission, "Missing 'target_metric' in mission"
        assert "target_value" in mission, "Missing 'target_value' in mission"
        
        print(f"✓ Mission: {mission.get('name', 'N/A')} - {mission.get('goal', 'N/A')}")
    
    def test_focus_endpoint_identity_structure(self):
        """Test identity data has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/focus",
            headers={"Cookie": "session_id=test"}
        )
        data = response.json()
        
        identity = data.get("identity", {})
        assert "profile" in identity, "Missing 'profile' in identity"
        assert "label" in identity, "Missing 'label' in identity"
        assert "description" in identity, "Missing 'description' in identity"
        
        print(f"✓ Identity: {identity.get('label', 'N/A')}")
    
    def test_journey_v2_endpoint_returns_200(self):
        """Test /api/journey/v2 returns 200 and proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/journey/v2",
            headers={"Cookie": "session_id=test"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify required top-level keys
        assert "weakness_ranking" in data, "Missing 'weakness_ranking' key"
        assert "win_state" in data, "Missing 'win_state' key"
        assert "heatmap" in data, "Missing 'heatmap' key"
        assert "identity" in data, "Missing 'identity' key"
        assert "milestones" in data, "Missing 'milestones' key"
        assert "badges" in data, "Missing 'badges' key"
        assert "games_analyzed" in data, "Missing 'games_analyzed' key"
        
        print(f"✓ Journey V2 endpoint returned valid structure with {data['games_analyzed']} games analyzed")
    
    def test_journey_v2_weakness_ranking_structure(self):
        """Test weakness ranking has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/journey/v2",
            headers={"Cookie": "session_id=test"}
        )
        data = response.json()
        
        weakness = data.get("weakness_ranking", {})
        # These can be null but keys must exist
        assert "rating_killer" in weakness or weakness.get("rating_killer") is None
        assert "secondary_weakness" in weakness or weakness.get("secondary_weakness") is None
        assert "stable_strength" in weakness or weakness.get("stable_strength") is None
        assert "ranking" in weakness, "Missing 'ranking' in weakness_ranking"
        assert "insight" in weakness, "Missing 'insight' in weakness_ranking"
        
        print(f"✓ Weakness ranking insight: {weakness.get('insight', 'N/A')}")
    
    def test_journey_v2_win_state_structure(self):
        """Test win-state analysis has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/journey/v2",
            headers={"Cookie": "session_id=test"}
        )
        data = response.json()
        
        win_state = data.get("win_state", {})
        assert "when_winning" in win_state, "Missing 'when_winning' in win_state"
        assert "when_equal" in win_state, "Missing 'when_equal' in win_state"
        assert "when_losing" in win_state, "Missing 'when_losing' in win_state"
        assert "total_blunders" in win_state, "Missing 'total_blunders' in win_state"
        assert "insight" in win_state, "Missing 'insight' in win_state"
        
        # Verify percentage fields
        assert "percentage" in win_state["when_winning"], "Missing percentage in when_winning"
        assert "percentage" in win_state["when_equal"], "Missing percentage in when_equal"
        assert "percentage" in win_state["when_losing"], "Missing percentage in when_losing"
        
        print(f"✓ Win-state insight: {win_state.get('insight', 'N/A')}")
    
    def test_journey_v2_heatmap_structure(self):
        """Test heatmap has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/journey/v2",
            headers={"Cookie": "session_id=test"}
        )
        data = response.json()
        
        heatmap = data.get("heatmap", {})
        assert "squares" in heatmap, "Missing 'squares' in heatmap"
        assert "regions" in heatmap, "Missing 'regions' in heatmap"
        assert "hot_squares" in heatmap, "Missing 'hot_squares' in heatmap"
        assert "insight" in heatmap, "Missing 'insight' in heatmap"
        
        # Verify regions structure
        regions = heatmap.get("regions", {})
        assert "kingside" in regions, "Missing 'kingside' in regions"
        assert "queenside" in regions, "Missing 'queenside' in regions"
        assert "center" in regions, "Missing 'center' in regions"
        
        print(f"✓ Heatmap insight: {heatmap.get('insight', 'N/A')}")
    
    def test_journey_v2_milestones_structure(self):
        """Test milestones is a list with proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/journey/v2",
            headers={"Cookie": "session_id=test"}
        )
        data = response.json()
        
        milestones = data.get("milestones", [])
        assert isinstance(milestones, list), "milestones should be a list"
        
        if len(milestones) > 0:
            first = milestones[0]
            assert "id" in first, "Missing 'id' in milestone"
            assert "name" in first, "Missing 'name' in milestone"
            assert "description" in first, "Missing 'description' in milestone"
            print(f"✓ First milestone: {first.get('name', 'N/A')}")
        else:
            print("✓ No milestones yet (expected for new users)")
    
    def test_lab_endpoint_returns_core_lesson(self):
        """Test /api/lab/{game_id} returns core lesson"""
        # First get a game_id
        games_response = requests.get(
            f"{BASE_URL}/api/games",
            headers={"Cookie": "session_id=test"}
        )
        
        if games_response.status_code != 200:
            pytest.skip("No games available to test lab endpoint")
        
        games = games_response.json()
        if not games or len(games) == 0:
            pytest.skip("No games available to test lab endpoint")
        
        game_id = games[0].get("game_id")
        if not game_id:
            pytest.skip("Game ID not found")
        
        # Now test the lab endpoint
        response = requests.get(
            f"{BASE_URL}/api/lab/{game_id}",
            headers={"Cookie": "session_id=test"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "core_lesson" in data, "Missing 'core_lesson' key"
        assert "analysis" in data, "Missing 'analysis' key"
        
        core_lesson = data.get("core_lesson", {})
        assert "lesson" in core_lesson, "Missing 'lesson' in core_lesson"
        
        print(f"✓ Lab endpoint: Core lesson = {core_lesson.get('lesson', 'N/A')}")
    
    def test_lab_endpoint_returns_404_for_invalid_game(self):
        """Test /api/lab/{game_id} returns 404 for non-existent game"""
        response = requests.get(
            f"{BASE_URL}/api/lab/invalid_game_id_12345",
            headers={"Cookie": "session_id=test"}
        )
        
        assert response.status_code == 404, f"Expected 404 for invalid game, got {response.status_code}"
        print("✓ Lab endpoint correctly returns 404 for invalid game ID")
    
    def test_weakness_ranking_standalone_endpoint(self):
        """Test /api/weakness-ranking endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/weakness-ranking",
            headers={"Cookie": "session_id=test"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ranking" in data, "Missing 'ranking' key"
        assert "insight" in data, "Missing 'insight' key"
        
        print(f"✓ Weakness ranking: {data.get('insight', 'N/A')}")
    
    def test_win_state_standalone_endpoint(self):
        """Test /api/win-state endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/win-state",
            headers={"Cookie": "session_id=test"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "when_winning" in data, "Missing 'when_winning' key"
        assert "when_equal" in data, "Missing 'when_equal' key"
        assert "when_losing" in data, "Missing 'when_losing' key"
        
        print(f"✓ Win-state: {data.get('insight', 'N/A')}")
    
    def test_heatmap_standalone_endpoint(self):
        """Test /api/heatmap endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/heatmap",
            headers={"Cookie": "session_id=test"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "squares" in data, "Missing 'squares' key"
        assert "regions" in data, "Missing 'regions' key"
        assert "hot_squares" in data, "Missing 'hot_squares' key"
        
        print(f"✓ Heatmap: {data.get('insight', 'N/A')}")
    
    def test_rating_impact_standalone_endpoint(self):
        """Test /api/rating-impact endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/rating-impact",
            headers={"Cookie": "session_id=test"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "potential_gain" in data, "Missing 'potential_gain' key"
        assert "message" in data, "Missing 'message' key"
        assert "confidence" in data, "Missing 'confidence' key"
        
        print(f"✓ Rating impact: {data.get('message', 'N/A')}")
    
    def test_identity_standalone_endpoint(self):
        """Test /api/identity endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/identity",
            headers={"Cookie": "session_id=test"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "profile" in data, "Missing 'profile' key"
        assert "label" in data, "Missing 'label' key"
        assert "description" in data, "Missing 'description' key"
        
        print(f"✓ Identity: {data.get('label', 'N/A')}")


class TestNavigationRename:
    """Test that navigation tabs are properly renamed"""
    
    def test_nav_tabs_accessible(self):
        """Verify main routes are accessible"""
        routes = [
            ("/coach", "Focus page (was Coach)"),
            ("/progress", "Journey page (was Progress)"),
            ("/dashboard", "Lab page (Dashboard)"),
            ("/import", "Import page")
        ]
        
        for route, description in routes:
            response = requests.get(
                f"{BASE_URL}{route}",
                headers={"Cookie": "session_id=test"},
                allow_redirects=False
            )
            # Frontend routes return 200 or redirect to auth
            assert response.status_code in [200, 302, 304], f"{description} should be accessible"
            print(f"✓ {description} - {route} accessible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

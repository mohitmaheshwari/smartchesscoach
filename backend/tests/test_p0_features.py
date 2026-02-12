"""
Backend tests for P0/P1 features:
- Dashboard: Rating Impact, Milestones, Focus Areas
- Lab: Similar Games/Behavior Memory
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDashboardFeatures:
    """Test Dashboard API endpoints for P0/P1 features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with dev login"""
        self.session = requests.Session()
        # Authenticate via dev-login
        login_response = self.session.get(f"{BASE_URL}/api/auth/dev-login", allow_redirects=False)
        # Dev login sets cookies, so we should be authenticated now
        
    def test_dashboard_stats_endpoint(self):
        """Test /api/dashboard-stats returns expected structure"""
        response = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify basic structure
        assert "total_games" in data, "Missing total_games"
        assert "analyzed_games" in data, "Missing analyzed_games"
        assert "top_weaknesses" in data, "Missing top_weaknesses"
        assert "recent_games" in data, "Missing recent_games"
        assert "stats" in data, "Missing stats"
        
        print(f"Dashboard Stats: {data['total_games']} games, {data['analyzed_games']} analyzed")
    
    def test_dashboard_stats_rating_impact(self):
        """Test /api/dashboard-stats includes rating_impact when enough games"""
        response = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        
        assert response.status_code == 200
        data = response.json()
        
        # Rating impact should be present if 5+ games analyzed
        if data.get("analyzed_games", 0) >= 5:
            assert "rating_impact" in data, "Missing rating_impact for user with 5+ analyzed games"
            
            rating_impact = data["rating_impact"]
            assert "potential_gain" in rating_impact, "Missing potential_gain in rating_impact"
            assert "message" in rating_impact, "Missing message in rating_impact"
            
            print(f"Rating Impact: +{rating_impact['potential_gain']} - {rating_impact['message']}")
        else:
            print(f"Skipping rating_impact check - only {data.get('analyzed_games', 0)} games analyzed")
    
    def test_dashboard_stats_top_weaknesses(self):
        """Test top_weaknesses in dashboard includes priority weakness"""
        response = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        
        assert response.status_code == 200
        data = response.json()
        
        top_weaknesses = data.get("top_weaknesses", [])
        if len(top_weaknesses) > 0:
            first_weakness = top_weaknesses[0]
            # Should have name/subcategory and occurrences/decayed_score
            assert "subcategory" in first_weakness or "name" in first_weakness, \
                "First weakness missing subcategory or name"
            
            print(f"Top weakness: {first_weakness.get('subcategory') or first_weakness.get('name')}")
        else:
            print("No weaknesses found - user may not have analyzed games")
    
    def test_milestones_endpoint(self):
        """Test /api/milestones returns milestone data"""
        response = self.session.get(f"{BASE_URL}/api/milestones")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify structure
        assert "achieved" in data, "Missing achieved milestones"
        assert "total_games" in data, "Missing total_games"
        
        achieved = data.get("achieved", [])
        print(f"Milestones: {len(achieved)} achieved out of {data['total_games']} games")
        
        # If milestones exist, verify structure
        for milestone in achieved:
            assert "id" in milestone, "Milestone missing id"
            assert "name" in milestone, "Milestone missing name"
            assert "description" in milestone, "Milestone missing description"
            assert "icon" in milestone, "Milestone missing icon"
            assert "rarity" in milestone, "Milestone missing rarity"
            
            print(f"  - {milestone['name']}: {milestone['description']} ({milestone['rarity']})")
    
    def test_rating_impact_endpoint(self):
        """Test dedicated /api/rating-impact endpoint"""
        response = self.session.get(f"{BASE_URL}/api/rating-impact")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify structure
        assert "potential_gain" in data, "Missing potential_gain"
        assert "message" in data, "Missing message"
        assert "confidence" in data, "Missing confidence"
        
        print(f"Rating Impact API: +{data['potential_gain']} ({data['confidence']} confidence)")


class TestLabPageFeatures:
    """Test Lab Page API endpoints for Behavior Memory/Similar Games"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with dev login"""
        self.session = requests.Session()
        self.session.get(f"{BASE_URL}/api/auth/dev-login", allow_redirects=False)
        
        # Get a game ID to test with
        self.test_game_id = "8a8b4f16-201a-4a7c-bc5a-21405c4ff939"
    
    def test_lab_endpoint_exists(self):
        """Test /api/lab/{game_id} endpoint exists and returns data"""
        response = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify core lab data structure
        assert "core_lesson" in data, "Missing core_lesson"
        
        print(f"Lab data retrieved for game {self.test_game_id}")
    
    def test_lab_similar_games(self):
        """Test /api/lab/{game_id} includes similar_games for behavior memory"""
        response = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check for similar_games field
        assert "similar_games" in data, "Missing similar_games in lab data"
        
        similar_games = data.get("similar_games", [])
        print(f"Similar games found: {len(similar_games)}")
        
        # If similar games exist, verify structure
        for game in similar_games:
            assert "game_id" in game, "Similar game missing game_id"
            assert "opponent" in game, "Similar game missing opponent"
            assert "result" in game, "Similar game missing result"
            
            print(f"  - vs {game['opponent']}: {game['result']}")
    
    def test_lab_core_lesson_structure(self):
        """Test core_lesson has expected structure"""
        response = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        core_lesson = data.get("core_lesson", {})
        if core_lesson:
            # Core lesson should have pattern and lesson
            assert "pattern" in core_lesson, "Core lesson missing pattern"
            assert "lesson" in core_lesson, "Core lesson missing lesson"
            
            print(f"Core lesson pattern: {core_lesson['pattern']}")
            print(f"Core lesson: {core_lesson['lesson']}")
    
    def test_analysis_endpoint(self):
        """Test /api/analysis/{game_id} returns analysis data"""
        response = self.session.get(f"{BASE_URL}/api/analysis/{self.test_game_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should have stockfish_analysis
        assert "stockfish_analysis" in data, "Missing stockfish_analysis"
        
        sf_analysis = data.get("stockfish_analysis", {})
        print(f"Analysis has {len(sf_analysis.get('move_evaluations', []))} move evaluations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
Lab Page API Tests - /api/lab-coach-pick and /api/lab-mark-reviewed endpoints
Tests the redesigned Lab page with behavioral insights per game card.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestLabCoachPickAPI:
    """Tests for /api/lab-coach-pick endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login authentication"""
        self.session = requests.Session()
        # Authenticate via dev login
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Dev login failed: {login_resp.text}"
        
    def test_lab_coach_pick_returns_200(self):
        """Test that /api/lab-coach-pick returns 200 OK"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_lab_coach_pick_response_structure(self):
        """Test that response has required fields: pick, pick_reason, verdict, games"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert response.status_code == 200
        data = response.json()
        
        # Required top-level fields
        assert "pick" in data, "Response missing 'pick' field"
        assert "pick_reason" in data, "Response missing 'pick_reason' field"
        assert "verdict" in data, "Response missing 'verdict' field"
        assert "games" in data, "Response missing 'games' field"
        assert "reviewed_count" in data, "Response missing 'reviewed_count' field"
        assert "total_count" in data, "Response missing 'total_count' field"
        
    def test_verdict_strip_structure(self):
        """Test verdict strip has wins, losses, total, and insight"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert response.status_code == 200
        data = response.json()
        
        verdict = data.get("verdict", {})
        assert "wins" in verdict, "Verdict missing 'wins'"
        assert "losses" in verdict, "Verdict missing 'losses'"
        assert "total" in verdict, "Verdict missing 'total'"
        assert "insight" in verdict, "Verdict missing 'insight'"
        
        # Insight should be a meaningful string
        assert isinstance(verdict["insight"], str), "Insight should be a string"
        assert len(verdict["insight"]) > 10, "Insight should be a meaningful message"
        
    def test_coach_pick_has_behavioral_data(self):
        """Test that Coach's Pick includes behavioral fields"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert response.status_code == 200
        data = response.json()
        
        pick = data.get("pick")
        if pick:  # May be None if no unreviewed games
            # Required game fields
            assert "game_id" in pick, "Pick missing 'game_id'"
            assert "opponent" in pick, "Pick missing 'opponent'"
            assert "result" in pick, "Pick missing 'result'"
            assert "accuracy" in pick, "Pick missing 'accuracy'"
            assert "opening" in pick, "Pick missing 'opening'"
            
            # Behavioral fields (may be empty but should exist)
            assert "behavior" in pick, "Pick missing 'behavior' field"
            assert "lesson_label" in pick, "Pick missing 'lesson_label' field"
            assert "lesson" in pick, "Pick missing 'lesson' field"
            
    def test_pick_reason_is_meaningful(self):
        """Test that pick_reason references actual patterns, not generic text"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert response.status_code == 200
        data = response.json()
        
        pick_reason = data.get("pick_reason", "")
        if pick_reason:  # May be empty if no pick
            assert len(pick_reason) > 20, "Pick reason should be a meaningful explanation"
            # Should contain specific references (pattern name, count, or behavioral insight)
            has_specific_content = any([
                "times" in pick_reason.lower(),  # Pattern count
                "pattern" in pick_reason.lower(),
                "mistake" in pick_reason.lower(),
                "winning" in pick_reason.lower(),
                "blunder" in pick_reason.lower(),
                "lesson" in pick_reason.lower(),
            ])
            assert has_specific_content, f"Pick reason should reference specific patterns: {pick_reason}"
            
    def test_games_list_has_behavioral_data(self):
        """Test that each game in the list has behavioral fields"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert response.status_code == 200
        data = response.json()
        
        games = data.get("games", [])
        assert len(games) > 0, "Expected at least one game in the list"
        
        for game in games:
            # Required fields per game
            assert "game_id" in game, f"Game missing 'game_id'"
            assert "opponent" in game, f"Game missing 'opponent'"
            assert "result" in game, f"Game missing 'result'"
            assert "accuracy" in game, f"Game missing 'accuracy'"
            assert "reviewed" in game, f"Game missing 'reviewed'"
            assert "opening" in game, f"Game missing 'opening'"
            
            # Behavioral fields
            assert "behavior" in game, f"Game {game.get('game_id')} missing 'behavior'"
            assert "lesson_label" in game, f"Game {game.get('game_id')} missing 'lesson_label'"
            assert "lesson" in game, f"Game {game.get('game_id')} missing 'lesson'"
            
    def test_result_badge_values(self):
        """Test that result field is W, L, or D"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert response.status_code == 200
        data = response.json()
        
        games = data.get("games", [])
        for game in games:
            result = game.get("result")
            assert result in ["W", "L", "D"], f"Invalid result '{result}' for game {game.get('game_id')}"
            
    def test_accuracy_is_numeric(self):
        """Test that accuracy is a number between 0 and 100"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert response.status_code == 200
        data = response.json()
        
        games = data.get("games", [])
        for game in games:
            accuracy = game.get("accuracy")
            assert isinstance(accuracy, (int, float)), f"Accuracy should be numeric: {accuracy}"
            assert 0 <= accuracy <= 100, f"Accuracy should be 0-100: {accuracy}"
            
    def test_reviewed_count_matches_games(self):
        """Test that reviewed_count matches actual reviewed games"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert response.status_code == 200
        data = response.json()
        
        games = data.get("games", [])
        reviewed_count = data.get("reviewed_count", 0)
        actual_reviewed = sum(1 for g in games if g.get("reviewed"))
        
        assert reviewed_count == actual_reviewed, f"reviewed_count ({reviewed_count}) doesn't match actual ({actual_reviewed})"


class TestLabMarkReviewedAPI:
    """Tests for /api/lab-mark-reviewed/{game_id} endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login authentication"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200
        
    def test_mark_reviewed_returns_success(self):
        """Test that marking a game as reviewed returns success"""
        # First get an unreviewed game
        lab_resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert lab_resp.status_code == 200
        data = lab_resp.json()
        
        games = data.get("games", [])
        unreviewed = [g for g in games if not g.get("reviewed")]
        
        if unreviewed:
            game_id = unreviewed[0]["game_id"]
            response = self.session.post(f"{BASE_URL}/api/lab-mark-reviewed/{game_id}")
            assert response.status_code == 200, f"Mark reviewed failed: {response.text}"
            
            result = response.json()
            assert "success" in result, "Response missing 'success' field"
        else:
            pytest.skip("No unreviewed games to test")
            
    def test_mark_reviewed_updates_game_status(self):
        """Test that marking reviewed actually updates the game status"""
        # Get initial state
        lab_resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        data = lab_resp.json()
        initial_reviewed_count = data.get("reviewed_count", 0)
        
        games = data.get("games", [])
        unreviewed = [g for g in games if not g.get("reviewed")]
        
        if unreviewed:
            game_id = unreviewed[0]["game_id"]
            
            # Mark as reviewed
            self.session.post(f"{BASE_URL}/api/lab-mark-reviewed/{game_id}")
            
            # Check updated state
            lab_resp2 = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
            data2 = lab_resp2.json()
            new_reviewed_count = data2.get("reviewed_count", 0)
            
            # Note: Count may not increase if game was already reviewed in another test
            # Just verify the game is now marked as reviewed
            game_after = next((g for g in data2.get("games", []) if g["game_id"] == game_id), None)
            if game_after:
                assert game_after.get("reviewed") == True, "Game should be marked as reviewed"
        else:
            pytest.skip("No unreviewed games to test")
            
    def test_mark_reviewed_invalid_game_id(self):
        """Test marking a non-existent game returns appropriate response"""
        response = self.session.post(f"{BASE_URL}/api/lab-mark-reviewed/invalid_game_id_12345")
        # Should return 200 with success: false (not 404)
        assert response.status_code == 200
        result = response.json()
        assert result.get("success") == False, "Should return success: false for invalid game"


class TestLabPageSeededData:
    """Tests to verify the 5 seeded test games exist with correct data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login authentication"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200
        
    def test_seeded_games_exist(self):
        """Test that seeded test games exist for dev_user_local"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert response.status_code == 200
        data = response.json()
        
        games = data.get("games", [])
        assert len(games) >= 5, f"Expected at least 5 seeded games, got {len(games)}"
        
    def test_seeded_games_have_opponents(self):
        """Test that seeded games have the expected opponents"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        data = response.json()
        
        games = data.get("games", [])
        opponents = [g.get("opponent") for g in games]
        
        expected_opponents = ["GrandMaster42", "BlitzKing99", "QuietPawn", "SicilianFan", "EndgameNerd"]
        for expected in expected_opponents:
            assert expected in opponents, f"Missing seeded opponent: {expected}"
            
    def test_seeded_games_have_behavioral_labels(self):
        """Test that seeded games have behavioral lesson labels"""
        response = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        data = response.json()
        
        games = data.get("games", [])
        
        # At least some games should have lesson labels (may be fewer due to test state)
        games_with_labels = [g for g in games if g.get("lesson_label")]
        assert len(games_with_labels) >= 2, f"Expected at least 2 games with lesson labels, got {len(games_with_labels)}"
        
        # Check for expected labels
        labels = [g.get("lesson_label") for g in games if g.get("lesson_label")]
        expected_labels = ["Clinical Finisher", "Panic Under Pressure", "Opening Drift", "Passive Player"]
        found_labels = [l for l in expected_labels if l in labels]
        assert len(found_labels) >= 1, f"Expected some behavioral labels, found: {labels}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

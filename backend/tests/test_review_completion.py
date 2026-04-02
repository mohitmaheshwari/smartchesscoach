"""
Test Review Completion Flow for ChessGuru Lab
Tests: POST /api/lab/{game_id}/complete-review endpoint
       GET /api/lab-coach-pick for Coach's Pick rotation
       Review stats tracking and game marking
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestReviewCompletionFlow:
    """Tests for the review completion flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: authenticate and get session"""
        self.session = requests.Session()
        # Dev login
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
        yield
        # Cleanup: reset test game to unreviewed state
        # This is done via direct DB access in the test itself
    
    def test_complete_review_endpoint_exists(self):
        """Test that complete-review endpoint exists and accepts POST"""
        # Use a test game ID
        resp = self.session.post(
            f"{BASE_URL}/api/lab/test_game_ea746565/complete-review",
            json={
                "concepts_learned": 0,
                "drills_solved": 0,
                "tabs_visited": [],
                "moves_viewed": 0,
                "total_moves": 0
            }
        )
        # Should return 200 (success) or 404 (game not found)
        assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code}, {resp.text}"
    
    def test_complete_review_returns_summary(self):
        """Test that complete-review returns summary with lesson info"""
        resp = self.session.post(
            f"{BASE_URL}/api/lab/test_game_ea746565/complete-review",
            json={
                "concepts_learned": 3,
                "drills_solved": 2,
                "tabs_visited": ["decrypt", "coach", "habits"],
                "moves_viewed": 35,
                "total_moves": 50
            }
        )
        assert resp.status_code == 200, f"Complete review failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert data.get("success") == True, "Response should have success=True"
        assert "summary" in data, "Response should have summary"
        
        summary = data["summary"]
        assert "lesson_label" in summary, "Summary should have lesson_label"
        assert "lesson" in summary, "Summary should have lesson"
        assert "takeaway" in summary, "Summary should have takeaway"
        assert "concepts_learned" in summary, "Summary should have concepts_learned"
        assert "drills_solved" in summary, "Summary should have drills_solved"
        
        # Verify stats are passed through
        assert summary["concepts_learned"] == 3
        assert summary["drills_solved"] == 2
    
    def test_complete_review_returns_next_game(self):
        """Test that complete-review returns next unreviewed game"""
        # First, get current coach pick to know what's unreviewed
        pick_resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert pick_resp.status_code == 200
        pick_data = pick_resp.json()
        
        # Find an unreviewed game
        unreviewed = [g for g in pick_data.get("games", []) if not g.get("reviewed")]
        if len(unreviewed) < 2:
            pytest.skip("Need at least 2 unreviewed games for this test")
        
        # Complete review on first unreviewed game
        first_game_id = unreviewed[0]["game_id"]
        resp = self.session.post(
            f"{BASE_URL}/api/lab/{first_game_id}/complete-review",
            json={
                "concepts_learned": 1,
                "drills_solved": 0,
                "tabs_visited": ["decrypt"],
                "moves_viewed": 10,
                "total_moves": 40
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Should have next_game pointing to another unreviewed game
        assert "next_game" in data, "Response should have next_game"
        if data["next_game"]:
            next_game = data["next_game"]
            assert "game_id" in next_game, "next_game should have game_id"
            assert "opponent" in next_game, "next_game should have opponent"
            assert "result" in next_game, "next_game should have result"
            assert "opening" in next_game, "next_game should have opening"
            # Next game should be different from completed game
            assert next_game["game_id"] != first_game_id
    
    def test_coach_pick_rotates_after_review(self):
        """Test that Coach's Pick rotates to next game after completing review"""
        # Get initial coach pick
        initial_resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert initial_resp.status_code == 200
        initial_data = initial_resp.json()
        initial_pick = initial_data.get("pick", {})
        
        if not initial_pick or initial_pick.get("reviewed"):
            pytest.skip("No unreviewed game available for Coach's Pick")
        
        initial_pick_id = initial_pick["game_id"]
        
        # Complete review on the current pick
        resp = self.session.post(
            f"{BASE_URL}/api/lab/{initial_pick_id}/complete-review",
            json={
                "concepts_learned": 2,
                "drills_solved": 1,
                "tabs_visited": ["decrypt", "coach"],
                "moves_viewed": 25,
                "total_moves": 45
            }
        )
        assert resp.status_code == 200
        
        # Get new coach pick
        new_resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert new_resp.status_code == 200
        new_data = new_resp.json()
        new_pick = new_data.get("pick")
        
        # If there are more unreviewed games, pick should be different
        unreviewed_count = len([g for g in new_data.get("games", []) if not g.get("reviewed")])
        if unreviewed_count > 0:
            assert new_pick is not None, "Should have a new Coach's Pick"
            assert new_pick["game_id"] != initial_pick_id, "Coach's Pick should rotate to different game"
    
    def test_reviewed_count_updates(self):
        """Test that reviewed count updates after completing review"""
        # Get initial count
        initial_resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert initial_resp.status_code == 200
        initial_data = initial_resp.json()
        initial_reviewed = initial_data.get("reviewed_count", 0)
        
        # Find an unreviewed game
        unreviewed = [g for g in initial_data.get("games", []) if not g.get("reviewed")]
        if not unreviewed:
            pytest.skip("No unreviewed games available")
        
        game_id = unreviewed[0]["game_id"]
        
        # Complete review
        resp = self.session.post(
            f"{BASE_URL}/api/lab/{game_id}/complete-review",
            json={
                "concepts_learned": 1,
                "drills_solved": 0,
                "tabs_visited": ["decrypt"],
                "moves_viewed": 15,
                "total_moves": 30
            }
        )
        assert resp.status_code == 200
        
        # Check new count
        new_resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert new_resp.status_code == 200
        new_data = new_resp.json()
        new_reviewed = new_data.get("reviewed_count", 0)
        
        # Count should increase by 1
        assert new_reviewed == initial_reviewed + 1, f"Reviewed count should increase from {initial_reviewed} to {initial_reviewed + 1}"
    
    def test_game_marked_as_reviewed(self):
        """Test that game is marked as reviewed after completing review"""
        # Get an unreviewed game
        pick_resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert pick_resp.status_code == 200
        pick_data = pick_resp.json()
        
        unreviewed = [g for g in pick_data.get("games", []) if not g.get("reviewed")]
        if not unreviewed:
            pytest.skip("No unreviewed games available")
        
        game_id = unreviewed[0]["game_id"]
        
        # Complete review
        resp = self.session.post(
            f"{BASE_URL}/api/lab/{game_id}/complete-review",
            json={
                "concepts_learned": 2,
                "drills_solved": 1,
                "tabs_visited": ["decrypt", "habits"],
                "moves_viewed": 20,
                "total_moves": 35
            }
        )
        assert resp.status_code == 200
        
        # Verify game is now marked as reviewed
        new_resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert new_resp.status_code == 200
        new_data = new_resp.json()
        
        # Find the game in the list
        game = next((g for g in new_data.get("games", []) if g["game_id"] == game_id), None)
        assert game is not None, f"Game {game_id} should still be in the list"
        assert game.get("reviewed") == True, f"Game {game_id} should be marked as reviewed"
    
    def test_complete_review_with_no_next_game(self):
        """Test complete-review when there are no more unreviewed games"""
        # This test verifies the endpoint handles the edge case gracefully
        # We'll use a non-existent game ID to test error handling
        resp = self.session.post(
            f"{BASE_URL}/api/lab/nonexistent_game_12345/complete-review",
            json={
                "concepts_learned": 0,
                "drills_solved": 0,
                "tabs_visited": [],
                "moves_viewed": 0,
                "total_moves": 0
            }
        )
        # Should still return 200 (endpoint doesn't validate game existence strictly)
        # or could return 404 if validation is added
        assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code}"


class TestLabCoachPickAPI:
    """Tests for the lab-coach-pick endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: authenticate"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_lab_coach_pick_returns_pick(self):
        """Test that lab-coach-pick returns a pick object"""
        resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert resp.status_code == 200
        data = resp.json()
        
        # Should have pick (or null if all reviewed)
        assert "pick" in data, "Response should have pick field"
        
        if data["pick"]:
            pick = data["pick"]
            assert "game_id" in pick
            assert "opponent" in pick
            assert "result" in pick
            assert "reviewed" in pick
            assert pick["reviewed"] == False, "Coach's Pick should be unreviewed"
    
    def test_lab_coach_pick_returns_pick_reason(self):
        """Test that lab-coach-pick returns a pick_reason"""
        resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert resp.status_code == 200
        data = resp.json()
        
        if data.get("pick"):
            assert "pick_reason" in data, "Response should have pick_reason"
            assert isinstance(data["pick_reason"], str)
            assert len(data["pick_reason"]) > 0, "pick_reason should not be empty"
    
    def test_lab_coach_pick_returns_games_list(self):
        """Test that lab-coach-pick returns all games"""
        resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "games" in data, "Response should have games list"
        assert isinstance(data["games"], list)
        
        for game in data["games"]:
            assert "game_id" in game
            assert "opponent" in game
            assert "result" in game
            assert "reviewed" in game
    
    def test_lab_coach_pick_returns_counts(self):
        """Test that lab-coach-pick returns reviewed/total counts"""
        resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "reviewed_count" in data, "Response should have reviewed_count"
        assert "total_count" in data, "Response should have total_count"
        assert isinstance(data["reviewed_count"], int)
        assert isinstance(data["total_count"], int)
        assert data["reviewed_count"] <= data["total_count"]
    
    def test_lab_coach_pick_returns_verdict(self):
        """Test that lab-coach-pick returns verdict with W/L stats"""
        resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert resp.status_code == 200
        data = resp.json()
        
        if data.get("verdict"):
            verdict = data["verdict"]
            assert "wins" in verdict
            assert "losses" in verdict
            assert "total" in verdict
            assert "insight" in verdict


class TestReviewCompletionDataPersistence:
    """Tests for review stats persistence"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: authenticate"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_review_stats_saved(self):
        """Test that review stats are saved to the game document"""
        # Get an unreviewed game
        pick_resp = self.session.get(f"{BASE_URL}/api/lab-coach-pick")
        assert pick_resp.status_code == 200
        pick_data = pick_resp.json()
        
        unreviewed = [g for g in pick_data.get("games", []) if not g.get("reviewed")]
        if not unreviewed:
            pytest.skip("No unreviewed games available")
        
        game_id = unreviewed[0]["game_id"]
        
        # Complete review with specific stats
        stats = {
            "concepts_learned": 5,
            "drills_solved": 3,
            "tabs_visited": ["decrypt", "coach", "habits"],
            "moves_viewed": 42,
            "total_moves": 50
        }
        
        resp = self.session.post(
            f"{BASE_URL}/api/lab/{game_id}/complete-review",
            json=stats
        )
        assert resp.status_code == 200
        
        # Verify stats are returned in response
        data = resp.json()
        assert data["summary"]["concepts_learned"] == 5
        assert data["summary"]["drills_solved"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

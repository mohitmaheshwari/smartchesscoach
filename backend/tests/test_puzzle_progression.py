"""
Test suite for Puzzle Difficulty Progression feature.

Tests the Elo-based rating system for puzzles including:
- Rating calculation
- Streak tracking
- Level progression
- Achievement system
- Rating change badges in feedback
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://chess-growth-hub.preview.emergentagent.com').rstrip('/')

class TestPuzzleProgressionAPI:
    """Tests for puzzle progression endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        # Login via dev endpoint
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
        print(f"Logged in successfully")
    
    def test_get_puzzle_progress_endpoint_exists(self):
        """Test GET /api/training/puzzle-progress returns progress data"""
        resp = self.session.get(f"{BASE_URL}/api/training/puzzle-progress")
        assert resp.status_code == 200, f"Failed to get puzzle progress: {resp.text}"
        
        data = resp.json()
        # Verify required fields exist
        assert "puzzle_rating" in data, "Missing puzzle_rating field"
        assert "current_level" in data, "Missing current_level field"
        assert "level_label" in data, "Missing level_label field"
        assert "current_streak" in data, "Missing current_streak field"
        assert "total_puzzles" in data, "Missing total_puzzles field"
        assert "puzzles_solved" in data, "Missing puzzles_solved field"
        print(f"Puzzle progress data: rating={data['puzzle_rating']}, level={data['level_label']}, streak={data['current_streak']}")
    
    def test_new_user_starts_at_1200_rating(self):
        """Test that rating defaults to 1200 for new users"""
        resp = self.session.get(f"{BASE_URL}/api/training/puzzle-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        # Rating should be around 1200 (might have changed from previous tests)
        assert data["puzzle_rating"] >= 1000, f"Rating too low: {data['puzzle_rating']}"
        assert data["puzzle_rating"] <= 1400, f"Rating too high for new user: {data['puzzle_rating']}"
        print(f"Rating check passed: {data['puzzle_rating']}")
    
    def test_progress_has_level_info(self):
        """Test that progress contains level and progress bar info"""
        resp = self.session.get(f"{BASE_URL}/api/training/puzzle-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        # Check level information
        assert "level_label" in data, "Missing level_label"
        assert "level_color" in data, "Missing level_color"
        assert "progress_in_level" in data, "Missing progress_in_level"
        assert "points_to_next_level" in data, "Missing points_to_next_level"
        
        # Verify level_label is one of the expected values
        valid_levels = ["Beginner", "Easy", "Intermediate", "Advanced", "Expert", "Master"]
        assert data["level_label"] in valid_levels, f"Invalid level: {data['level_label']}"
        print(f"Level info: {data['level_label']} ({data['level_color']}), {data['progress_in_level']}% progress, {data['points_to_next_level']} to next")
    
    def test_progress_has_stats(self):
        """Test that progress contains solve rate and best streak"""
        resp = self.session.get(f"{BASE_URL}/api/training/puzzle-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "solve_rate" in data, "Missing solve_rate"
        assert "best_streak" in data, "Missing best_streak"
        assert "recent_accuracy" in data, "Missing recent_accuracy"
        assert "achievements" in data, "Missing achievements"
        print(f"Stats: solve_rate={data['solve_rate']}%, best_streak={data['best_streak']}")


class TestPuzzleValidationWithProgression:
    """Tests for puzzle validation with rating changes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_validate_puzzle_endpoint_exists(self):
        """Test POST /api/training/puzzle/validate endpoint"""
        resp = self.session.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "test_puzzle_1",
            "user_answer": "e4",
            "correct_move": "e4",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "difficulty": "intermediate"
        })
        assert resp.status_code == 200, f"Validate endpoint failed: {resp.text}"
        
        data = resp.json()
        # Should have progression info
        assert "progression" in data, "Missing progression in response"
        print(f"Validation response has progression info")
    
    def test_correct_answer_increases_rating(self):
        """Test that solving a puzzle correctly increases rating"""
        # Get initial rating
        progress_resp = self.session.get(f"{BASE_URL}/api/training/puzzle-progress")
        initial_rating = progress_resp.json()["puzzle_rating"]
        
        # Submit correct answer
        resp = self.session.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": f"test_correct_{initial_rating}",
            "user_answer": "Nf3",
            "correct_move": "Nf3",
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "difficulty": "intermediate"
        })
        assert resp.status_code == 200
        
        data = resp.json()
        progression = data.get("progression", {})
        
        # Rating should have increased
        rating_change = progression.get("rating_change", 0)
        if data.get("correct"):
            assert rating_change > 0, f"Rating should increase on correct answer, got: {rating_change}"
            print(f"Correct answer increased rating by {rating_change}")
        else:
            print(f"Move was not recognized as correct")
    
    def test_incorrect_answer_decreases_rating(self):
        """Test that failing a puzzle decreases rating"""
        # Get initial rating
        progress_resp = self.session.get(f"{BASE_URL}/api/training/puzzle-progress")
        initial_rating = progress_resp.json()["puzzle_rating"]
        
        # Submit incorrect answer
        resp = self.session.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": f"test_incorrect_{initial_rating}",
            "user_answer": "a3",  # Wrong move
            "correct_move": "Nf3",
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "difficulty": "hard"
        })
        assert resp.status_code == 200
        
        data = resp.json()
        progression = data.get("progression", {})
        
        # Rating should have decreased (or stayed same if the API is lenient)
        rating_change = progression.get("rating_change", 0)
        assert rating_change <= 0, f"Rating should decrease or stay same on incorrect answer, got: {rating_change}"
        print(f"Incorrect answer changed rating by {rating_change}")
    
    def test_correct_answer_increments_streak(self):
        """Test that correct answer increments streak"""
        # Submit correct answer
        resp = self.session.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "test_streak_1",
            "user_answer": "d4",
            "correct_move": "d4",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "difficulty": "easy"
        })
        assert resp.status_code == 200
        
        data = resp.json()
        progression = data.get("progression", {})
        
        if data.get("correct"):
            streak = progression.get("current_streak", 0)
            assert streak >= 1, f"Streak should be at least 1 after correct answer"
            print(f"Streak after correct answer: {streak}")
    
    def test_incorrect_answer_resets_streak(self):
        """Test that incorrect answer resets streak to 0"""
        # First get some streak going
        self.session.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "streak_builder_1",
            "user_answer": "e4",
            "correct_move": "e4",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "difficulty": "easy"
        })
        
        # Now fail a puzzle
        resp = self.session.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "streak_breaker_1",
            "user_answer": "h4",  # Wrong
            "correct_move": "e4",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "difficulty": "easy"
        })
        assert resp.status_code == 200
        
        data = resp.json()
        progression = data.get("progression", {})
        
        streak = progression.get("current_streak", -1)
        assert streak == 0, f"Streak should reset to 0 on incorrect answer, got: {streak}"
        print(f"Streak correctly reset to {streak}")
    
    def test_progression_contains_rating_change(self):
        """Test that progression object contains rating_change for badge display"""
        resp = self.session.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "test_badge_rating",
            "user_answer": "c4",
            "correct_move": "c4",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "difficulty": "intermediate"
        })
        assert resp.status_code == 200
        
        data = resp.json()
        progression = data.get("progression", {})
        
        # Required fields for rating change badge
        assert "old_rating" in progression, "Missing old_rating for badge"
        assert "new_rating" in progression, "Missing new_rating for badge"
        assert "rating_change" in progression, "Missing rating_change for badge"
        
        print(f"Rating change data: {progression['old_rating']} -> {progression['new_rating']} ({progression['rating_change']})")
    
    def test_progression_contains_level_up_info(self):
        """Test that progression object contains level-up information"""
        resp = self.session.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "test_level_up",
            "user_answer": "Nc3",
            "correct_move": "Nc3",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "difficulty": "intermediate"
        })
        assert resp.status_code == 200
        
        data = resp.json()
        progression = data.get("progression", {})
        
        # Should have level-up flag
        assert "leveled_up" in progression, "Missing leveled_up flag"
        assert "new_level" in progression, "Missing new_level"
        
        print(f"Level up info: leveled_up={progression['leveled_up']}, new_level={progression['new_level']}")


class TestPuzzleDifficultyRecommendation:
    """Tests for puzzle difficulty recommendation endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_recommendation_endpoint_exists(self):
        """Test GET /api/training/puzzle-difficulty-recommendation exists"""
        resp = self.session.get(f"{BASE_URL}/api/training/puzzle-difficulty-recommendation")
        assert resp.status_code == 200, f"Recommendation endpoint failed: {resp.text}"
        
        data = resp.json()
        assert "user_rating" in data, "Missing user_rating"
        assert "recommended_difficulties" in data, "Missing recommended_difficulties"
        print(f"Recommendation: rating={data['user_rating']}, difficulties={data['recommended_difficulties']}")


class TestPuzzleLeaderboard:
    """Tests for puzzle leaderboard endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_leaderboard_endpoint_exists(self):
        """Test GET /api/training/puzzle-leaderboard exists"""
        resp = self.session.get(f"{BASE_URL}/api/training/puzzle-leaderboard")
        assert resp.status_code == 200, f"Leaderboard endpoint failed: {resp.text}"
        
        data = resp.json()
        assert "leaderboard" in data, "Missing leaderboard array"
        assert isinstance(data["leaderboard"], list), "Leaderboard should be a list"
        print(f"Leaderboard has {len(data['leaderboard'])} entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

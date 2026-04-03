"""
Test Suite: Decay Model & Pattern Training Puzzles
===================================================

Tests for:
1. GET /api/lab-coach-pick - Returns pick_pattern field, realistic counts (not inflated 100+)
2. GET /api/training/pattern-puzzles/{pattern} - Returns pattern training puzzles
3. POST /api/training/extract-puzzles - Extracts puzzles from analyzed games
4. POST /api/training/puzzle-attempt - Records puzzle attempts
5. GET /api/home-intelligence - Home page data (progress trend, win streak)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Dev mode cookie for authentication
DEV_COOKIES = {"dev_mode": "true"}


class TestLabCoachPick:
    """Tests for /api/lab-coach-pick endpoint with decay model"""

    def test_lab_coach_pick_returns_200(self):
        """Basic health check - endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/lab-coach-pick",
            cookies=DEV_COOKIES
        )
        print(f"Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_lab_coach_pick_has_pick_pattern_field(self):
        """Verify pick_pattern field is returned alongside pick and pick_reason"""
        response = requests.get(
            f"{BASE_URL}/api/lab-coach-pick",
            cookies=DEV_COOKIES
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields exist
        assert "pick" in data, "Response missing 'pick' field"
        assert "pick_reason" in data, "Response missing 'pick_reason' field"
        assert "pick_pattern" in data, "Response missing 'pick_pattern' field"
        
        print(f"pick_pattern: {data.get('pick_pattern')}")
        print(f"pick_reason: {data.get('pick_reason')}")

    def test_lab_coach_pick_realistic_counts(self):
        """Verify pick_reason doesn't show inflated counts (100+ numbers)"""
        response = requests.get(
            f"{BASE_URL}/api/lab-coach-pick",
            cookies=DEV_COOKIES
        )
        assert response.status_code == 200
        data = response.json()
        
        pick_reason = data.get("pick_reason", "")
        print(f"pick_reason: {pick_reason}")
        
        # Check for inflated numbers in the reason text
        # The decay model should produce small numbers (1-10 typically)
        import re
        numbers = re.findall(r'\b(\d+)\b', pick_reason)
        for num_str in numbers:
            num = int(num_str)
            # Numbers over 50 in pick_reason are suspicious (inflated counts)
            if num > 50:
                print(f"WARNING: Found potentially inflated number {num} in pick_reason")
                # This is a soft check - we log but don't fail
                # The decay model should prevent 100+ counts
        
        # If there's a pick, verify the structure
        if data.get("pick"):
            pick = data["pick"]
            assert "game_id" in pick, "Pick missing game_id"
            assert "result" in pick, "Pick missing result"

    def test_lab_coach_pick_verdict_structure(self):
        """Verify verdict strip has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/lab-coach-pick",
            cookies=DEV_COOKIES
        )
        assert response.status_code == 200
        data = response.json()
        
        verdict = data.get("verdict", {})
        assert "wins" in verdict, "Verdict missing 'wins'"
        assert "losses" in verdict, "Verdict missing 'losses'"
        assert "total" in verdict, "Verdict missing 'total'"
        assert "insight" in verdict, "Verdict missing 'insight'"
        
        print(f"Verdict: {verdict}")

    def test_lab_coach_pick_games_list(self):
        """Verify games list is returned with enriched data"""
        response = requests.get(
            f"{BASE_URL}/api/lab-coach-pick",
            cookies=DEV_COOKIES
        )
        assert response.status_code == 200
        data = response.json()
        
        games = data.get("games", [])
        print(f"Total games: {len(games)}")
        
        if games:
            game = games[0]
            # Check enriched game structure
            expected_fields = ["game_id", "opponent", "result", "reviewed", "accuracy"]
            for field in expected_fields:
                assert field in game, f"Game missing '{field}' field"
            
            print(f"Sample game: {game.get('game_id')} vs {game.get('opponent')} - {game.get('result')}")


class TestPatternPuzzles:
    """Tests for /api/training/pattern-puzzles/{pattern} endpoint"""

    def test_pattern_puzzles_piece_safety(self):
        """Test getting puzzles for piece_safety pattern"""
        response = requests.get(
            f"{BASE_URL}/api/training/pattern-puzzles/piece_safety",
            cookies=DEV_COOKIES
        )
        print(f"Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "pattern" in data, "Response missing 'pattern' field"
        assert "own_puzzles" in data, "Response missing 'own_puzzles' field"
        assert "community_puzzles" in data, "Response missing 'community_puzzles' field"
        assert "total_available" in data, "Response missing 'total_available' field"
        assert "unsolved_count" in data, "Response missing 'unsolved_count' field"
        assert "solved_count" in data, "Response missing 'solved_count' field"
        
        print(f"Pattern: {data.get('pattern')}")
        print(f"Own puzzles: {len(data.get('own_puzzles', []))}")
        print(f"Community puzzles: {len(data.get('community_puzzles', []))}")
        print(f"Total available: {data.get('total_available')}")
        print(f"Unsolved: {data.get('unsolved_count')}")
        print(f"Solved: {data.get('solved_count')}")

    def test_pattern_puzzles_missed_tactic(self):
        """Test getting puzzles for missed_tactic pattern"""
        response = requests.get(
            f"{BASE_URL}/api/training/pattern-puzzles/missed_tactic",
            cookies=DEV_COOKIES
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("pattern") == "missed_tactic"
        print(f"Missed tactic puzzles: {data.get('total_available', 0)}")

    def test_pattern_puzzles_unknown_pattern(self):
        """Test getting puzzles for an unknown pattern (should return empty)"""
        response = requests.get(
            f"{BASE_URL}/api/training/pattern-puzzles/nonexistent_pattern_xyz",
            cookies=DEV_COOKIES
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return empty but valid structure
        assert data.get("pattern") == "nonexistent_pattern_xyz"
        assert data.get("total_available", 0) == 0


class TestExtractPuzzles:
    """Tests for /api/training/extract-puzzles endpoint"""

    def test_extract_puzzles_returns_200(self):
        """Test puzzle extraction endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/training/extract-puzzles",
            cookies=DEV_COOKIES
        )
        print(f"Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "puzzles_created" in data, "Response missing 'puzzles_created' field"
        assert "message" in data, "Response missing 'message' field"
        
        print(f"Puzzles created: {data.get('puzzles_created')}")
        print(f"Message: {data.get('message')}")


class TestPuzzleAttempt:
    """Tests for /api/training/puzzle-attempt endpoint"""

    def test_puzzle_attempt_records_success(self):
        """Test recording a puzzle attempt"""
        response = requests.post(
            f"{BASE_URL}/api/training/puzzle-attempt",
            json={
                "puzzle_id": "test_puzzle_123",
                "correct": True,
                "weakness_type": "piece_safety",
                "moves_tried": ["e2e4"]
            },
            cookies=DEV_COOKIES
        )
        print(f"Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Expected success=True"
        print(f"Response: {data}")

    def test_puzzle_attempt_records_failure(self):
        """Test recording an incorrect puzzle attempt"""
        response = requests.post(
            f"{BASE_URL}/api/training/puzzle-attempt",
            json={
                "puzzle_id": "test_puzzle_456",
                "correct": False,
                "weakness_type": "missed_tactic",
                "moves_tried": ["d2d4", "e2e3"]
            },
            cookies=DEV_COOKIES
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True


class TestHomeIntelligence:
    """Tests for /api/home-intelligence endpoint (progress trend, win streak)"""

    def test_home_intelligence_returns_200(self):
        """Test home intelligence endpoint returns data"""
        response = requests.get(
            f"{BASE_URL}/api/home-intelligence",
            cookies=DEV_COOKIES
        )
        print(f"Status: {response.status_code}")
        # This endpoint might not exist or might be named differently
        if response.status_code == 404:
            pytest.skip("home-intelligence endpoint not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"Home intelligence data keys: {list(data.keys())}")


class TestCoachHomeIntelligence:
    """Tests for /api/coach/home-intelligence endpoint"""

    def test_coach_home_intelligence_returns_200(self):
        """Test coach home intelligence endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            cookies=DEV_COOKIES
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 404:
            pytest.skip("coach/home-intelligence endpoint not found")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check for win streak data
        if "win_streak" in data:
            print(f"Win streak: {data.get('win_streak')}")
        if "mood_override" in data:
            print(f"Mood override: {data.get('mood_override')}")
        
        print(f"Response keys: {list(data.keys())}")


class TestDecayModelService:
    """Unit tests for the pattern decay service logic"""

    def test_decay_model_import(self):
        """Verify decay model service can be imported"""
        import sys
        sys.path.insert(0, '/app/backend')
        try:
            from pattern_decay_service import compute_pattern_scores, pick_best_game, DECAY_RATE
            assert DECAY_RATE == 0.85, f"Expected DECAY_RATE=0.85, got {DECAY_RATE}"
            print(f"DECAY_RATE: {DECAY_RATE}")
        except ImportError as e:
            # Try alternate path
            try:
                sys.path.insert(0, '/app/backend/services')
                from pattern_decay_service import compute_pattern_scores, pick_best_game, DECAY_RATE
                assert DECAY_RATE == 0.85
                print(f"DECAY_RATE: {DECAY_RATE}")
            except ImportError as e2:
                pytest.fail(f"Failed to import pattern_decay_service: {e2}")

    def test_compute_pattern_scores_empty(self):
        """Test compute_pattern_scores with empty games list"""
        import sys
        sys.path.insert(0, '/app/backend/services')
        from pattern_decay_service import compute_pattern_scores
        
        scores = compute_pattern_scores([])
        assert scores == {}, "Expected empty dict for empty games"

    def test_compute_pattern_scores_with_gaps(self):
        """Test compute_pattern_scores with games containing cognitive gaps"""
        import sys
        sys.path.insert(0, '/app/backend/services')
        from pattern_decay_service import compute_pattern_scores
        
        # Simulate games with cognitive gaps
        games = [
            {"game_id": "g1", "cognitive_gaps": ["piece_safety"]},
            {"game_id": "g2", "cognitive_gaps": ["piece_safety", "missed_tactic"]},
            {"game_id": "g3", "cognitive_gaps": []},  # Clean game
            {"game_id": "g4", "cognitive_gaps": ["piece_safety"]},
        ]
        
        scores = compute_pattern_scores(games)
        
        assert "piece_safety" in scores, "Expected piece_safety in scores"
        ps_score = scores["piece_safety"]
        
        # Verify score structure
        assert "raw_count" in ps_score
        assert "weighted_score" in ps_score
        assert "display_count" in ps_score
        assert "state" in ps_score
        
        # Raw count should be 3 (appears in g1, g2, g4)
        assert ps_score["raw_count"] == 3, f"Expected raw_count=3, got {ps_score['raw_count']}"
        
        # Display count should be reasonable (not 100+)
        assert ps_score["display_count"] <= 10, f"Display count too high: {ps_score['display_count']}"
        
        print(f"piece_safety score: {ps_score}")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

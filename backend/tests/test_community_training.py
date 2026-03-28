"""
Community Intelligence Training Tests
=====================================

Tests for the Community Training feature:
- GET /api/training/community-feed - Returns positions with source_user_name, source_user_rating, pattern_type
- POST /api/training/solve-attempt - Returns solved, correct_move, pattern_type
- GET /api/training/pattern-stats - Returns pattern-level stats
- GET /api/training/community-count - Returns total position count

Seeded data:
- 8 community positions from fake users (Ravi 1180, Anika 1250, Marco 1320, Elena 1150, Kai 1400)
- Position comm_001 has been solved (Qxf7# checkmate)
- Position comm_002 has incorrect attempt (e7e5, correct: d7d5)
- Position comm_003: fen='r2qkb1r/ppp2ppp/2np1n2/4p1B1/2B1P3/3P1N2/PPP2PPP/RN1QK2R b KQkq - 0 5', best_move_uci='f8e7', best_move_san='Be7'
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCommunityTrainingEndpoints:
    """Test Community Training API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        # Dev login to get session cookie
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Dev login failed: {login_resp.text}"
        self.user = login_resp.json().get("user", {})
    
    def test_community_count_endpoint(self):
        """GET /api/training/community-count returns total position count"""
        response = self.session.get(f"{BASE_URL}/api/training/community-count")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "count" in data, "Response should have 'count' field"
        assert isinstance(data["count"], int), "Count should be an integer"
        assert data["count"] >= 0, "Count should be non-negative"
        
        print(f"Community position count: {data['count']}")
    
    def test_community_feed_endpoint(self):
        """GET /api/training/community-feed returns positions with required fields"""
        response = self.session.get(f"{BASE_URL}/api/training/community-feed?limit=12")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "positions" in data, "Response should have 'positions' field"
        assert "total" in data, "Response should have 'total' field"
        assert "own_count" in data, "Response should have 'own_count' field"
        assert "community_count" in data, "Response should have 'community_count' field"
        assert "pattern_stats" in data, "Response should have 'pattern_stats' field"
        
        print(f"Feed: {data['total']} positions ({data['own_count']} own, {data['community_count']} community)")
        
        # If positions exist, verify their structure
        if data["positions"]:
            pos = data["positions"][0]
            
            # Required fields for community positions
            assert "position_id" in pos, "Position should have 'position_id'"
            assert "fen" in pos, "Position should have 'fen'"
            assert "best_move_san" in pos, "Position should have 'best_move_san'"
            assert "best_move_uci" in pos, "Position should have 'best_move_uci'"
            assert "pattern_type" in pos, "Position should have 'pattern_type'"
            assert "difficulty" in pos, "Position should have 'difficulty'"
            assert "source_type" in pos, "Position should have 'source_type'"
            
            # Source attribution fields
            assert "source_user_name" in pos, "Position should have 'source_user_name'"
            assert "source_user_rating" in pos, "Position should have 'source_user_rating'"
            
            print(f"First position: {pos['position_id']}, pattern: {pos['pattern_type']}, difficulty: {pos['difficulty']}")
            print(f"Source: {pos['source_user_name']} ({pos['source_user_rating']})")
    
    def test_community_feed_position_fields(self):
        """Verify community positions have all required fields for UI display"""
        response = self.session.get(f"{BASE_URL}/api/training/community-feed?limit=12")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check community positions specifically
        community_positions = [p for p in data.get("positions", []) if p.get("source_type") == "community"]
        
        if community_positions:
            pos = community_positions[0]
            
            # Verify source attribution for community positions
            assert pos.get("source_user_name"), "Community position should have source_user_name"
            assert pos.get("source_user_rating"), "Community position should have source_user_rating"
            assert isinstance(pos["source_user_rating"], (int, float)), "Rating should be numeric"
            
            # Verify pattern and difficulty badges
            assert pos.get("pattern_type") in [
                "checkmate_pattern", "hanging_piece", "fork", "pin", "skewer", 
                "back_rank", "positional", "tactical"
            ], f"Unexpected pattern_type: {pos.get('pattern_type')}"
            
            assert pos.get("difficulty") in ["easy", "medium", "hard"], f"Unexpected difficulty: {pos.get('difficulty')}"
            
            print(f"Community position verified: {pos['position_id']}")
            print(f"  From: {pos['source_user_name']}, {pos['source_user_rating']}")
            print(f"  Pattern: {pos['pattern_type']}, Difficulty: {pos['difficulty']}")
    
    def test_pattern_stats_endpoint(self):
        """GET /api/training/pattern-stats returns pattern-level stats"""
        response = self.session.get(f"{BASE_URL}/api/training/pattern-stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "patterns" in data, "Response should have 'patterns' field"
        assert isinstance(data["patterns"], list), "Patterns should be a list"
        
        # If stats exist, verify their structure
        if data["patterns"]:
            stat = data["patterns"][0]
            assert "pattern" in stat, "Stat should have 'pattern' field"
            assert "total_attempts" in stat, "Stat should have 'total_attempts' field"
            assert "total_solved" in stat, "Stat should have 'total_solved' field"
            assert "solve_rate" in stat, "Stat should have 'solve_rate' field"
            
            print(f"Pattern stats: {len(data['patterns'])} patterns tracked")
            for s in data["patterns"][:3]:
                print(f"  {s['pattern']}: {s['total_solved']}/{s['total_attempts']} ({s['solve_rate']}%)")
    
    def test_solve_attempt_correct_move(self):
        """POST /api/training/solve-attempt with correct move returns solved=True"""
        # Use comm_003 which has known best_move_uci='f8e7'
        payload = {
            "position_id": "comm_003",
            "user_move": "f8e7",  # Correct move in UCI format
            "time_taken_seconds": 5
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/training/solve-attempt",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "solved" in data, "Response should have 'solved' field"
        assert "correct_move" in data, "Response should have 'correct_move' field"
        assert "pattern_type" in data, "Response should have 'pattern_type' field"
        
        # Verify correct move was recognized
        assert data["solved"] == True, f"Expected solved=True for correct move, got {data['solved']}"
        assert data["correct_move"] == "Be7", f"Expected correct_move='Be7', got {data['correct_move']}"
        
        print(f"Solve attempt result: solved={data['solved']}, correct_move={data['correct_move']}")
        print(f"Pattern: {data['pattern_type']}")
        
        if "miss_rate_at_your_level" in data and data["miss_rate_at_your_level"] is not None:
            print(f"Miss rate at your level: {data['miss_rate_at_your_level']}%")
    
    def test_solve_attempt_incorrect_move(self):
        """POST /api/training/solve-attempt with incorrect move returns solved=False"""
        # Use comm_003 with an incorrect move
        payload = {
            "position_id": "comm_003",
            "user_move": "e7e5",  # Incorrect move
            "time_taken_seconds": 3
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/training/solve-attempt",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "solved" in data, "Response should have 'solved' field"
        assert "correct_move" in data, "Response should have 'correct_move' field"
        
        # Verify incorrect move was recognized
        assert data["solved"] == False, f"Expected solved=False for incorrect move, got {data['solved']}"
        
        print(f"Incorrect attempt result: solved={data['solved']}, correct_move={data['correct_move']}")
    
    def test_solve_attempt_invalid_position(self):
        """POST /api/training/solve-attempt with invalid position_id returns error"""
        payload = {
            "position_id": "nonexistent_position",
            "user_move": "e2e4",
            "time_taken_seconds": 1
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/training/solve-attempt",
            json=payload
        )
        
        # Should return 200 with error in response body (based on service implementation)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "error" in data, "Response should have 'error' field for invalid position"
        print(f"Invalid position error: {data['error']}")
    
    def test_feed_limit_parameter(self):
        """GET /api/training/community-feed respects limit parameter"""
        # Test with small limit
        response = self.session.get(f"{BASE_URL}/api/training/community-feed?limit=3")
        
        assert response.status_code == 200
        data = response.json()
        
        # Total should not exceed limit
        assert data["total"] <= 3, f"Expected at most 3 positions, got {data['total']}"
        assert len(data["positions"]) <= 3, f"Expected at most 3 positions in list"
        
        print(f"Limit test: requested 3, got {len(data['positions'])} positions")
    
    def test_seeded_positions_exist(self):
        """Verify seeded community positions exist in the database"""
        response = self.session.get(f"{BASE_URL}/api/training/community-count")
        
        assert response.status_code == 200
        data = response.json()
        
        # According to the context, 8 positions were seeded
        assert data["count"] >= 8, f"Expected at least 8 seeded positions, got {data['count']}"
        
        print(f"Seeded positions verified: {data['count']} total positions")


class TestCommunityTrainingIntegration:
    """Integration tests for the full training flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200
    
    def test_full_training_flow(self):
        """Test complete training flow: fetch feed -> solve -> check stats"""
        # Step 1: Get training feed
        feed_resp = self.session.get(f"{BASE_URL}/api/training/community-feed?limit=5")
        assert feed_resp.status_code == 200
        feed_data = feed_resp.json()
        
        if not feed_data["positions"]:
            pytest.skip("No positions available for testing")
        
        # Step 2: Get a position to solve
        position = feed_data["positions"][0]
        print(f"Testing with position: {position['position_id']}")
        print(f"  FEN: {position['fen']}")
        print(f"  Best move: {position['best_move_san']} ({position['best_move_uci']})")
        
        # Step 3: Submit correct solve attempt
        solve_resp = self.session.post(
            f"{BASE_URL}/api/training/solve-attempt",
            json={
                "position_id": position["position_id"],
                "user_move": position["best_move_uci"],
                "time_taken_seconds": 10
            }
        )
        assert solve_resp.status_code == 200
        solve_data = solve_resp.json()
        
        # Should be solved correctly
        if "error" not in solve_data:
            assert solve_data["solved"] == True, "Correct move should be solved"
            print(f"  Solved correctly: {solve_data['correct_move']}")
        
        # Step 4: Check pattern stats updated
        stats_resp = self.session.get(f"{BASE_URL}/api/training/pattern-stats")
        assert stats_resp.status_code == 200
        stats_data = stats_resp.json()
        
        print(f"Pattern stats after solve: {len(stats_data['patterns'])} patterns")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

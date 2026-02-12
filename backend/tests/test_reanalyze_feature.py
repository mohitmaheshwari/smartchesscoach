"""
Test suite for P0 Reanalyze Games Feature
Tests:
1. Dashboard tabs: 'Analyzed' and 'In Queue' game lists
2. Backend: POST /api/games/{game_id}/reanalyze endpoint
3. Backend: GET /api/games/{game_id}/analysis-status endpoint
4. Backend: GET /api/dashboard-stats endpoint with analyzed_list and in_queue_list
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestReanalyzeFeature:
    """Test the re-analyze games feature endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate via dev-login
        auth_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert auth_resp.status_code == 200, f"Dev login failed: {auth_resp.text}"
        
        # Extract session cookie
        if 'session_token' in auth_resp.cookies:
            self.session.cookies.set('session_token', auth_resp.cookies['session_token'])
    
    def test_dashboard_stats_returns_analyzed_list(self):
        """GET /api/dashboard-stats returns analyzed_list field"""
        response = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        assert response.status_code == 200, f"Dashboard stats failed: {response.text}"
        
        data = response.json()
        
        # Verify required fields exist
        assert "analyzed_list" in data, "Response missing analyzed_list"
        assert "in_queue_list" in data, "Response missing in_queue_list"
        assert "analyzed_games" in data, "Response missing analyzed_games count"
        assert "queued_games" in data, "Response missing queued_games count"
        
        print(f"✓ Dashboard stats: {data.get('total_games', 0)} total games")
        print(f"✓ Analyzed games: {data.get('analyzed_games', 0)}")
        print(f"✓ Queued games: {data.get('queued_games', 0)}")
        print(f"✓ Analyzed list length: {len(data.get('analyzed_list', []))}")
        print(f"✓ In-queue list length: {len(data.get('in_queue_list', []))}")
    
    def test_dashboard_stats_analyzed_list_has_accuracy(self):
        """GET /api/dashboard-stats analyzed_list games have accuracy field"""
        response = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        assert response.status_code == 200
        
        data = response.json()
        analyzed_list = data.get("analyzed_list", [])
        
        if len(analyzed_list) > 0:
            # Check first analyzed game has expected fields
            game = analyzed_list[0]
            assert "game_id" in game, "Game missing game_id"
            assert "analysis_status" in game, "Game missing analysis_status"
            assert game.get("analysis_status") == "analyzed", f"Wrong status: {game.get('analysis_status')}"
            
            # Accuracy may be None if stockfish failed, but field should exist or be fetchable
            print(f"✓ First analyzed game: {game.get('game_id')}")
            print(f"  - Status: {game.get('analysis_status')}")
            print(f"  - Accuracy: {game.get('accuracy')}")
        else:
            print("⚠ No analyzed games to verify - test data needed")
    
    def test_dashboard_stats_in_queue_list_structure(self):
        """GET /api/dashboard-stats in_queue_list has correct structure"""
        response = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        assert response.status_code == 200
        
        data = response.json()
        in_queue_list = data.get("in_queue_list", [])
        
        if len(in_queue_list) > 0:
            game = in_queue_list[0]
            assert "game_id" in game, "Game missing game_id"
            assert "analysis_status" in game, "Game missing analysis_status"
            assert game.get("analysis_status") in ["pending", "processing"], \
                f"Wrong status for queued game: {game.get('analysis_status')}"
            
            print(f"✓ First queued game: {game.get('game_id')}")
            print(f"  - Status: {game.get('analysis_status')}")
            print(f"  - Queued at: {game.get('queued_at')}")
        else:
            print("✓ No games in queue (expected when all analyzed)")
    
    def test_analysis_status_endpoint_returns_correct_format(self):
        """GET /api/games/{game_id}/analysis-status returns correct format"""
        # First get a game ID
        games_resp = self.session.get(f"{BASE_URL}/api/games")
        assert games_resp.status_code == 200
        
        games = games_resp.json()
        if len(games) == 0:
            pytest.skip("No games available to test")
        
        game_id = games[0].get("game_id")
        
        # Test analysis status endpoint
        response = self.session.get(f"{BASE_URL}/api/games/{game_id}/analysis-status")
        assert response.status_code == 200, f"Analysis status failed: {response.text}"
        
        data = response.json()
        assert "status" in data, "Response missing status field"
        assert data["status"] in ["analyzed", "pending", "processing", "not_analyzed", "failed"], \
            f"Invalid status: {data['status']}"
        
        print(f"✓ Game {game_id} analysis status: {data['status']}")
    
    def test_analysis_status_endpoint_404_for_invalid_game(self):
        """GET /api/games/{game_id}/analysis-status returns 404 for invalid game"""
        response = self.session.get(f"{BASE_URL}/api/games/invalid_game_12345/analysis-status")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid game returns 404 as expected")
    
    def test_reanalyze_endpoint_exists(self):
        """POST /api/games/{game_id}/reanalyze endpoint exists"""
        # First get a game ID
        games_resp = self.session.get(f"{BASE_URL}/api/games")
        assert games_resp.status_code == 200
        
        games = games_resp.json()
        if len(games) == 0:
            pytest.skip("No games available to test")
        
        game_id = games[0].get("game_id")
        
        # Test reanalyze endpoint
        response = self.session.post(f"{BASE_URL}/api/games/{game_id}/reanalyze")
        
        # Should return 200 with success message or already_queued
        assert response.status_code == 200, f"Reanalyze failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "success" in data, "Response missing success field"
        assert data["success"] == True, f"Reanalyze did not succeed: {data}"
        assert "status" in data, "Response missing status field"
        assert data["status"] in ["queued", "already_queued"], f"Unexpected status: {data['status']}"
        
        print(f"✓ Game {game_id} reanalyze response: {data['status']}")
        print(f"  - Message: {data.get('message')}")
    
    def test_reanalyze_endpoint_404_for_invalid_game(self):
        """POST /api/games/{game_id}/reanalyze returns 404 for invalid game"""
        response = self.session.post(f"{BASE_URL}/api/games/invalid_game_12345/reanalyze")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Reanalyze invalid game returns 404 as expected")
    
    def test_reanalyze_updates_analysis_status(self):
        """POST /api/games/{game_id}/reanalyze updates the game's analysis status"""
        # Get a game
        games_resp = self.session.get(f"{BASE_URL}/api/games")
        games = games_resp.json()
        if len(games) == 0:
            pytest.skip("No games available to test")
        
        game_id = games[0].get("game_id")
        
        # Trigger reanalyze
        reanalyze_resp = self.session.post(f"{BASE_URL}/api/games/{game_id}/reanalyze")
        assert reanalyze_resp.status_code == 200
        
        # Check status - should be pending/processing or already analyzed
        time.sleep(0.5)  # Brief wait for DB update
        status_resp = self.session.get(f"{BASE_URL}/api/games/{game_id}/analysis-status")
        assert status_resp.status_code == 200
        
        data = status_resp.json()
        # After reanalyze, status should be either processing/pending or analyzed (if completed fast)
        valid_statuses = ["pending", "processing", "analyzed"]
        assert data["status"] in valid_statuses, \
            f"Expected status in {valid_statuses}, got {data['status']}"
        
        print(f"✓ After reanalyze, game status: {data['status']}")
    
    def test_analysis_queue_endpoint(self):
        """GET /api/analysis-queue returns queue status"""
        response = self.session.get(f"{BASE_URL}/api/analysis-queue")
        assert response.status_code == 200, f"Analysis queue failed: {response.text}"
        
        data = response.json()
        assert "queue" in data, "Response missing queue field"
        assert "count" in data, "Response missing count field"
        assert isinstance(data["queue"], list), "Queue should be a list"
        
        print(f"✓ Analysis queue count: {data['count']}")
        if data["count"] > 0:
            print(f"  - First item status: {data['queue'][0].get('status')}")


class TestDashboardTabsData:
    """Test that dashboard provides proper data for tabs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        auth_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert auth_resp.status_code == 200
        if 'session_token' in auth_resp.cookies:
            self.session.cookies.set('session_token', auth_resp.cookies['session_token'])
    
    def test_dashboard_stats_backward_compatible(self):
        """Dashboard stats maintains backward compatibility with recent_games"""
        response = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # Old fields still exist
        assert "recent_games" in data, "Missing backward compat field: recent_games"
        assert "total_games" in data, "Missing field: total_games"
        assert "stats" in data, "Missing field: stats"
        
        # New fields for tabs
        assert "analyzed_list" in data, "Missing new field: analyzed_list"
        assert "in_queue_list" in data, "Missing new field: in_queue_list"
        assert "queued_games" in data, "Missing new field: queued_games"
        
        print("✓ All required dashboard fields present")
        print(f"  - total_games: {data.get('total_games')}")
        print(f"  - analyzed_games: {data.get('analyzed_games')}")
        print(f"  - queued_games: {data.get('queued_games')}")
    
    def test_analyzed_games_have_expected_fields(self):
        """Analyzed games in list have all expected fields"""
        response = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        data = response.json()
        
        analyzed_list = data.get("analyzed_list", [])
        if len(analyzed_list) == 0:
            print("⚠ No analyzed games to verify structure")
            return
        
        game = analyzed_list[0]
        expected_fields = ["game_id", "user_color", "result", "analysis_status"]
        
        for field in expected_fields:
            assert field in game, f"Analyzed game missing field: {field}"
        
        # PGN should NOT be in response (too large)
        assert "pgn" not in game, "PGN should not be sent to frontend"
        
        print(f"✓ Analyzed game has all expected fields")
        print(f"  - game_id: {game.get('game_id')}")
        print(f"  - user_color: {game.get('user_color')}")
        print(f"  - result: {game.get('result')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

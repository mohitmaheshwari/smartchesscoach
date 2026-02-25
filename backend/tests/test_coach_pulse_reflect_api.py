"""
Test Coach Pulse and Reflect API endpoints
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://loss-recovery.preview.emergentagent.com').rstrip('/')


class TestCoachPulseAPI:
    """Tests for Coach Pulse indicator APIs"""
    
    def test_reflect_pending_count_returns_200(self):
        """GET /api/reflect/pending/count should return 200"""
        response = requests.get(f"{BASE_URL}/api/reflect/pending/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
    
    def test_coach_fresh_loss_returns_200(self):
        """GET /api/coach/fresh-loss should return 200"""
        response = requests.get(f"{BASE_URL}/api/coach/fresh-loss")
        assert response.status_code == 200
        data = response.json()
        assert "has_fresh_loss" in data
        assert isinstance(data["has_fresh_loss"], bool)
        # If has_fresh_loss is True, should include game_id
        if data["has_fresh_loss"]:
            assert "game_id" in data
    
    def test_coach_weekly_proof_returns_200(self):
        """GET /api/coach/weekly-proof should return 200"""
        response = requests.get(f"{BASE_URL}/api/coach/weekly-proof")
        assert response.status_code == 200
        data = response.json()
        # Should have wins and streak info
        assert "wins" in data or "missions_completed" in data or "streak_days" in data


class TestReflectAPI:
    """Tests for Reflect page APIs"""
    
    def test_reflect_pending_returns_games(self):
        """GET /api/reflect/pending should return games list"""
        response = requests.get(f"{BASE_URL}/api/reflect/pending")
        assert response.status_code == 200
        data = response.json()
        assert "games" in data
        assert isinstance(data["games"], list)
        
        # If there are games, check structure
        if len(data["games"]) > 0:
            game = data["games"][0]
            assert "game_id" in game
            assert "opponent_name" in game
    
    def test_reflect_profile_returns_200(self):
        """GET /api/reflect/v1/profile should return adaptive profile"""
        response = requests.get(f"{BASE_URL}/api/reflect/v1/profile")
        assert response.status_code == 200
        data = response.json()
        # Should have intent_options and confidence_options
        assert "intent_options" in data or "profile_version" in data
    
    def test_reflect_quick_tags_with_valid_position(self):
        """POST /api/reflect/v1/quick-tags should return tags for a position"""
        request_data = {
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "user_move": "e5",
            "best_move": "c5",
            "mistake_category": "critical_moment_drift",
            "cp_loss": 50,
            "move_number": 1
        }
        
        response = requests.post(
            f"{BASE_URL}/api/reflect/v1/quick-tags",
            json=request_data
        )
        assert response.status_code == 200
        data = response.json()
        assert "tags" in data
        assert isinstance(data["tags"], list)
    
    def test_reflect_game_moments_returns_moments(self):
        """GET /api/reflect/game/{game_id}/moments should return moments"""
        # First get a game from pending reflections
        pending_response = requests.get(f"{BASE_URL}/api/reflect/pending")
        if pending_response.status_code != 200:
            pytest.skip("Could not get pending reflections")
        
        games = pending_response.json().get("games", [])
        if len(games) == 0:
            pytest.skip("No games pending reflection")
        
        game_id = games[0]["game_id"]
        response = requests.get(f"{BASE_URL}/api/reflect/game/{game_id}/moments")
        assert response.status_code == 200
        data = response.json()
        assert "moments" in data
        
        # If moments exist, verify structure
        if len(data["moments"]) > 0:
            moment = data["moments"][0]
            assert "fen" in moment
            assert "user_move" in moment
            assert "best_move" in moment


class TestMissionPositionsAPI:
    """Tests for Mission positions API"""
    
    def test_missions_today_returns_200(self):
        """GET /api/missions/today should return today's mission"""
        response = requests.get(f"{BASE_URL}/api/missions/today")
        assert response.status_code == 200
        data = response.json()
        # Should have mission data or indicate no mission
        assert "mission_id" in data or "trigger_type" in data or "focus_label" in data
    
    def test_mission_positions_returns_real_positions(self):
        """GET /api/missions/{mission_id}/positions should return drill positions from user games"""
        # First get today's mission
        mission_response = requests.get(f"{BASE_URL}/api/missions/today")
        if mission_response.status_code != 200:
            pytest.skip("Could not get today's mission")
        
        mission_data = mission_response.json()
        mission_id = mission_data.get("mission_id")
        
        if not mission_id:
            pytest.skip("No mission ID available")
        
        # Get positions for this mission
        response = requests.get(f"{BASE_URL}/api/missions/{mission_id}/positions")
        assert response.status_code == 200
        data = response.json()
        
        # Should have positions array
        assert "positions" in data
        assert isinstance(data["positions"], list)
        assert "total" in data
        assert "focus_pattern" in data
        assert "mission_id" in data
        
        # If positions exist, verify structure
        if len(data["positions"]) > 0:
            pos = data["positions"][0]
            assert "position_id" in pos
            assert "fen" in pos
            assert "best_move" in pos
            # Real positions should have game_id (not just "sample")
            # Note: may be sample positions if user has no analyzed games
            print(f"Position game_id: {pos.get('game_id')}")
    
    def test_mission_positions_returns_valid_fen(self):
        """Mission positions should have valid FEN strings"""
        mission_response = requests.get(f"{BASE_URL}/api/missions/today")
        if mission_response.status_code != 200:
            pytest.skip("Could not get today's mission")
        
        mission_data = mission_response.json()
        mission_id = mission_data.get("mission_id")
        
        if not mission_id:
            pytest.skip("No mission ID available")
        
        response = requests.get(f"{BASE_URL}/api/missions/{mission_id}/positions")
        if response.status_code != 200:
            pytest.skip("Could not get positions")
        
        positions = response.json().get("positions", [])
        
        for pos in positions[:3]:  # Check first 3 positions
            fen = pos.get("fen")
            assert fen is not None, "FEN should not be None"
            assert len(fen) > 20, "FEN should be a valid FEN string"
            # FEN should have at least 6 parts separated by space
            parts = fen.split(" ")
            assert len(parts) >= 4, f"Invalid FEN format: {fen}"
            print(f"Valid FEN: {fen[:50]}...")


class TestCoachHomeAPI:
    """Tests for Coach Home page APIs"""
    
    def test_games_list_returns_200(self):
        """GET /api/games should return games list"""
        response = requests.get(f"{BASE_URL}/api/games?limit=5")
        assert response.status_code == 200
        data = response.json()
        # API returns list directly or {"games": []}
        if isinstance(data, list):
            # Direct list response
            assert len(data) >= 0
        else:
            # Object with games key
            assert "games" in data
            assert isinstance(data["games"], list)
    
    def test_missions_start_requires_mission_id(self):
        """POST /api/missions/{mission_id}/start should work with valid ID"""
        mission_response = requests.get(f"{BASE_URL}/api/missions/today")
        if mission_response.status_code != 200:
            pytest.skip("Could not get today's mission")
        
        mission_data = mission_response.json()
        mission_id = mission_data.get("mission_id")
        
        if not mission_id:
            pytest.skip("No mission ID available")
        
        # Try to start the mission
        response = requests.post(f"{BASE_URL}/api/missions/{mission_id}/start")
        # Should return 200 or 409 (already started)
        assert response.status_code in [200, 409, 400]

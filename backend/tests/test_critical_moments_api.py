"""
Test Critical Moments API - Deep Strategy Endpoint

Tests the /api/lab/{game_id}/deep-strategy endpoint which powers
the Critical Moments feature in the game review page.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://chess-habit-forge.preview.emergentagent.com').rstrip('/')
GAME_ID = 'ae58fb15-ca1d-43e7-a46f-12dce04959bb'


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestDeepStrategyEndpoint:
    """Tests for the /lab/{game_id}/deep-strategy endpoint"""
    
    def test_deep_strategy_returns_200(self, api_client):
        """Verify endpoint returns 200 OK"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        assert response.status_code == 200
    
    def test_deep_strategy_returns_critical_moments(self, api_client):
        """Verify response contains critical_moments array"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        data = response.json()
        
        assert "critical_moments" in data
        assert isinstance(data["critical_moments"], list)
        assert len(data["critical_moments"]) > 0
    
    def test_critical_moment_has_required_fields(self, api_client):
        """Verify each critical moment has required fields"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        data = response.json()
        
        for moment in data["critical_moments"]:
            # Required fields for Critical Moments feature
            assert "move_number" in moment, "Missing move_number"
            assert "fen" in moment, "Missing fen"
            assert "your_move" in moment, "Missing your_move"
            assert "best_move" in moment, "Missing best_move"
            assert "cp_loss" in moment, "Missing cp_loss"
    
    def test_critical_moment_has_position_analysis(self, api_client):
        """Verify moments include position analysis for hints"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        data = response.json()
        
        # At least one moment should have position_analysis
        has_position_analysis = any(
            "position_analysis" in moment 
            for moment in data["critical_moments"]
        )
        assert has_position_analysis, "No moments have position_analysis"
    
    def test_critical_moment_has_insight(self, api_client):
        """Verify moments include insight object with explanations"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        data = response.json()
        
        # Check first moment has insight
        first_moment = data["critical_moments"][0]
        assert "insight" in first_moment, "Missing insight object"
        
        insight = first_moment["insight"]
        # Should have what_best_move_achieves for "Why it works" explanation
        assert "what_best_move_achieves" in insight, "Missing what_best_move_achieves"
    
    def test_critical_moment_has_pv_after_best(self, api_client):
        """Verify moments include principal variation for Play Line feature"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        data = response.json()
        
        # At least one moment should have pv_after_best
        has_pv = any(
            "pv_after_best" in moment 
            for moment in data["critical_moments"]
        )
        assert has_pv, "No moments have pv_after_best for Play Line feature"
    
    def test_critical_moments_sorted_by_severity(self, api_client):
        """Verify moments are sorted by cp_loss (most severe first)"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        data = response.json()
        
        moments = data["critical_moments"]
        cp_losses = [abs(m["cp_loss"]) for m in moments]
        
        # Should be sorted in descending order (most severe first)
        assert cp_losses == sorted(cp_losses, reverse=True), \
            "Critical moments not sorted by severity"
    
    def test_deep_strategy_limited_to_5_moments(self, api_client):
        """Verify only top 5 moments are returned"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        data = response.json()
        
        assert len(data["critical_moments"]) <= 5, \
            "More than 5 critical moments returned"
    
    def test_deep_strategy_has_total_mistakes_count(self, api_client):
        """Verify response includes total_mistakes count"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        data = response.json()
        
        assert "total_mistakes" in data
        assert isinstance(data["total_mistakes"], int)


class TestMomentFields:
    """Test specific fields in critical moments"""
    
    def test_first_moment_move_34_best_is_qf4(self, api_client):
        """Verify first moment (Move 34) has correct best move"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        data = response.json()
        
        # Find moment for move 34
        move_34 = next(
            (m for m in data["critical_moments"] if m["move_number"] == 34),
            None
        )
        
        assert move_34 is not None, "Move 34 not found in critical moments"
        assert move_34["best_move"] == "Qf4", \
            f"Best move should be Qf4, got {move_34['best_move']}"
        assert move_34["your_move"] == "Qe5", \
            f"Your move should be Qe5, got {move_34['your_move']}"
    
    def test_moment_fen_is_valid(self, api_client):
        """Verify FEN strings are valid"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        data = response.json()
        
        for moment in data["critical_moments"]:
            fen = moment["fen"]
            # Basic FEN validation
            assert fen.count('/') == 7, f"Invalid FEN (wrong slash count): {fen}"
            parts = fen.split(' ')
            assert len(parts) >= 4, f"Invalid FEN (missing parts): {fen}"
    
    def test_cp_loss_is_negative_or_positive_int(self, api_client):
        """Verify cp_loss is an integer"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}/deep-strategy")
        data = response.json()
        
        for moment in data["critical_moments"]:
            cp_loss = moment["cp_loss"]
            assert isinstance(cp_loss, int), f"cp_loss should be int, got {type(cp_loss)}"


class TestLabEndpoint:
    """Tests for the /lab/{game_id} base endpoint"""
    
    def test_lab_endpoint_returns_200(self, api_client):
        """Verify lab endpoint returns 200 OK"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}")
        assert response.status_code == 200
    
    def test_lab_endpoint_has_core_lesson(self, api_client):
        """Verify lab endpoint includes core lesson"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}")
        data = response.json()
        
        assert "core_lesson" in data
    
    def test_lab_endpoint_has_pattern_context(self, api_client):
        """Verify lab endpoint includes pattern context"""
        response = api_client.get(f"{BASE_URL}/api/lab/{GAME_ID}")
        data = response.json()
        
        assert "pattern_context" in data


class TestErrorHandling:
    """Test error handling for invalid requests"""
    
    def test_invalid_game_id_returns_404(self, api_client):
        """Verify invalid game ID returns 404"""
        response = api_client.get(f"{BASE_URL}/api/lab/invalid-game-id-12345/deep-strategy")
        assert response.status_code == 404
    
    def test_lab_invalid_game_id_returns_404(self, api_client):
        """Verify invalid game ID returns 404 for base lab endpoint"""
        response = api_client.get(f"{BASE_URL}/api/lab/invalid-game-id-12345")
        assert response.status_code == 404

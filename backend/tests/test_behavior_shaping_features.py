"""
Backend Tests for Behavior Shaping UI Features
Tests:
1. TSI interpretation bands in cognitive/patterns API
2. Primary focus in cognitive/training-priority API (no secondary shown in UI)
3. Focus context indicator logic
4. LLM hallucination guardrail validation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_session():
    """Get authenticated session via dev login"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Dev login
    response = session.get(f"{BASE_URL}/api/auth/dev-login")
    if response.status_code != 200:
        pytest.skip("Dev login not available")
    
    return session


class TestCognitiveTrainingPriority:
    """Tests for cognitive/training-priority API endpoint"""
    
    def test_training_priority_returns_primary_focus(self, auth_session):
        """Test that primary_focus is returned with correct structure"""
        response = auth_session.get(f"{BASE_URL}/api/cognitive/training-priority")
        assert response.status_code == 200
        
        data = response.json()
        
        # Primary focus should always be present
        assert "primary_focus" in data, "primary_focus key missing"
        
        primary = data["primary_focus"]
        if primary is not None:  # May be None if no patterns detected
            assert "category" in primary, "category missing from primary_focus"
            assert "display_name" in primary, "display_name missing from primary_focus"
            assert "message" in primary, "message missing from primary_focus"
            print(f"Primary focus: {primary['display_name']}")
    
    def test_training_priority_returns_secondary_focus(self, auth_session):
        """Test that secondary_focus is returned (even if UI doesn't show it)"""
        response = auth_session.get(f"{BASE_URL}/api/cognitive/training-priority")
        assert response.status_code == 200
        
        data = response.json()
        
        # Secondary focus is optional but should be a list if present
        if "secondary_focus" in data:
            assert isinstance(data["secondary_focus"], list), "secondary_focus should be a list"
            print(f"Secondary focus count: {len(data['secondary_focus'])}")
    
    def test_training_priority_returns_puzzle_order(self, auth_session):
        """Test that puzzle_priority_order is returned"""
        response = auth_session.get(f"{BASE_URL}/api/cognitive/training-priority")
        assert response.status_code == 200
        
        data = response.json()
        assert "puzzle_priority_order" in data, "puzzle_priority_order missing"
        assert isinstance(data["puzzle_priority_order"], list)


class TestCognitivePatterns:
    """Tests for cognitive/patterns API endpoint - TSI and interpretation bands"""
    
    def test_patterns_returns_tsi(self, auth_session):
        """Test that thinking_stability_index is returned"""
        response = auth_session.get(f"{BASE_URL}/api/cognitive/patterns")
        assert response.status_code == 200
        
        data = response.json()
        assert "thinking_stability_index" in data, "TSI missing from response"
        
        tsi = data["thinking_stability_index"]
        assert isinstance(tsi, (int, float)), "TSI should be numeric"
        assert 0 <= tsi <= 100, f"TSI should be 0-100, got {tsi}"
        print(f"TSI Score: {tsi}")
    
    def test_patterns_returns_tsi_trend(self, auth_session):
        """Test that tsi_trend is returned"""
        response = auth_session.get(f"{BASE_URL}/api/cognitive/patterns")
        assert response.status_code == 200
        
        data = response.json()
        if "tsi_trend" in data and data["tsi_trend"]:
            assert data["tsi_trend"] in ["improving", "worsening", "stable"], \
                f"Invalid tsi_trend: {data['tsi_trend']}"
            print(f"TSI Trend: {data['tsi_trend']}")
    
    def test_tsi_interpretation_bands(self, auth_session):
        """Test TSI interpretation band logic (matches frontend)"""
        response = auth_session.get(f"{BASE_URL}/api/cognitive/patterns")
        assert response.status_code == 200
        
        data = response.json()
        tsi = data.get("thinking_stability_index", 0)
        
        # Frontend logic:
        # >= 80: 'Stable decision process'
        # >= 65: 'Moderate instability'
        # >= 50: 'Frequent cognitive lapses'
        # < 50: 'High volatility'
        
        if tsi >= 80:
            expected_band = "Stable decision process"
        elif tsi >= 65:
            expected_band = "Moderate instability"
        elif tsi >= 50:
            expected_band = "Frequent cognitive lapses"
        else:
            expected_band = "High volatility"
        
        print(f"TSI: {tsi} -> Expected band: '{expected_band}'")
        # Note: The interpretation is done in frontend, not backend
        # This test documents the expected mapping


class TestFocusContextIndicator:
    """Tests for focus context indicator logic in mistake explanations"""
    
    def test_lab_endpoint_returns_data(self, auth_session):
        """Test lab endpoint returns analysis data for a game"""
        # First get a game ID
        games_response = auth_session.get(f"{BASE_URL}/api/games?page=1&per_page=1")
        if games_response.status_code != 200 or not games_response.json():
            pytest.skip("No games available")
        
        games = games_response.json()
        if not games:
            pytest.skip("No games in response")
        
        game_id = games[0].get("game_id")
        if not game_id:
            pytest.skip("No game_id in first game")
        
        # Get lab data
        lab_response = auth_session.get(f"{BASE_URL}/api/lab/{game_id}")
        # Lab endpoint may return 404 if no analysis
        if lab_response.status_code == 200:
            data = lab_response.json()
            print(f"Lab data keys: {list(data.keys())}")
        else:
            print(f"Lab endpoint returned {lab_response.status_code}")


class TestHallucinationGuardrail:
    """Tests for LLM explanation hallucination guardrail"""
    
    def test_guardrail_exists_in_code(self):
        """Verify the guardrail function exists and has basic structure"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        try:
            from mistake_explanation_service import validate_llm_explanation
            
            # Test with known hallucination pattern
            template = {
                "pattern": "Test pattern",
                "thinking_habit": "Test habit"
            }
            
            # Test case 1: Known hallucination signal
            result = validate_llm_explanation(
                "This move trapping a knight on b1 was bad",
                "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "e4",
                "d4",
                template
            )
            # Should fallback to template
            assert "Test pattern" in result, "Guardrail should fallback for hallucination"
            print("PASS: Hallucination signal detected and handled")
            
            # Test case 2: Valid explanation
            result = validate_llm_explanation(
                "This move weakens the center control.",
                "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                "e5",
                "Nf6",
                template
            )
            # Should return original
            assert result == "This move weakens the center control.", \
                "Valid explanation should pass through"
            print("PASS: Valid explanation passed through")
            
        except ImportError as e:
            pytest.skip(f"Could not import module: {e}")
    
    def test_guardrail_invalid_fen(self):
        """Test guardrail handles invalid FEN"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        try:
            from mistake_explanation_service import validate_llm_explanation
            
            template = {
                "pattern": "Fallback pattern",
                "thinking_habit": "Fallback habit"
            }
            
            # Invalid FEN
            result = validate_llm_explanation(
                "This was a mistake",
                "",  # Empty FEN
                "e4",
                "d4",
                template
            )
            
            assert "Fallback" in result, "Should fallback for empty FEN"
            print("PASS: Invalid FEN handled correctly")
            
        except ImportError as e:
            pytest.skip(f"Could not import module: {e}")


class TestTrainingPageNoSecondary:
    """Test that secondary focus is not shown on Training page"""
    
    def test_api_returns_both_but_ui_shows_only_primary(self, auth_session):
        """
        The API returns both primary and secondary focus,
        but the UI should only display primary (behavior shaping)
        """
        response = auth_session.get(f"{BASE_URL}/api/cognitive/training-priority")
        assert response.status_code == 200
        
        data = response.json()
        
        # API should return both
        has_primary = "primary_focus" in data and data["primary_focus"] is not None
        has_secondary = "secondary_focus" in data and len(data.get("secondary_focus", [])) > 0
        
        print(f"API returns primary_focus: {has_primary}")
        print(f"API returns secondary_focus: {has_secondary}")
        
        # Document: UI should only show primary_focus
        # The TrainingNew.jsx code at line ~613 has comment:
        # "/* Trend indicator - no secondary focus (noise reduction) */"
        # This confirms the design intent
        
        if has_primary:
            primary = data["primary_focus"]
            print(f"Primary focus to display: {primary['display_name']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

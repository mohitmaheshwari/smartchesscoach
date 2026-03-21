"""
Tests for Cognitive Gap Analysis API endpoint.

Tests the /api/games/{game_id}/move/{move_number}/analyze-gap endpoint
which provides precise diagnosis of WHY a move was a mistake.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://mistake-tracker-3.preview.emergentagent.com')


@pytest.fixture
def authenticated_session():
    """Session with dev login authentication"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Authenticate via dev login
    res = session.get(f"{BASE_URL}/api/auth/dev-login")
    if res.status_code != 200:
        pytest.skip("Dev login failed - skipping authenticated tests")
    
    return session


@pytest.fixture
def pending_game_with_moments(authenticated_session):
    """Get a game with pending reflection moments"""
    res = authenticated_session.get(f"{BASE_URL}/api/reflect/pending")
    if res.status_code != 200:
        pytest.skip("Could not fetch pending games")
    
    data = res.json()
    games = data.get("games", [])
    
    if not games:
        pytest.skip("No pending games for reflection")
    
    game_id = games[0]["game_id"]
    
    # Get moments for this game
    res = authenticated_session.get(f"{BASE_URL}/api/reflect/game/{game_id}/moments")
    if res.status_code != 200:
        pytest.skip("Could not fetch game moments")
    
    moments_data = res.json()
    moments = moments_data.get("moments", [])
    
    if not moments:
        pytest.skip("No moments found in game")
    
    return {
        "game_id": game_id,
        "moments": moments,
        "first_moment": moments[0]
    }


class TestCognitiveGapAnalysisEndpoint:
    """Test suite for /api/games/{game_id}/move/{move_number}/analyze-gap endpoint"""
    
    def test_endpoint_returns_200_with_valid_input(self, authenticated_session, pending_game_with_moments):
        """Test that the endpoint returns 200 with valid game_id and move_number"""
        game_id = pending_game_with_moments["game_id"]
        move_number = pending_game_with_moments["first_moment"]["move_number"]
        
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{move_number}/analyze-gap",
            json={
                "user_stated_plan": "I was trying to attack",
                "user_hypothesis_category": "attack",
                "user_confidence": "somewhat_sure"
            }
        )
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    
    def test_response_contains_required_fields(self, authenticated_session, pending_game_with_moments):
        """Test that response contains all required fields for cognitive gap analysis"""
        game_id = pending_game_with_moments["game_id"]
        move_number = pending_game_with_moments["first_moment"]["move_number"]
        
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{move_number}/analyze-gap",
            json={
                "user_stated_plan": "I was trying to defend my king",
                "user_hypothesis_category": "defend",
                "user_confidence": "very_sure"
            }
        )
        
        assert res.status_code == 200
        data = res.json()
        
        # Check top-level fields
        assert "move_number" in data, "Response missing 'move_number'"
        assert "user_move" in data, "Response missing 'user_move'"
        assert "best_move" in data, "Response missing 'best_move'"
        assert "cp_loss" in data, "Response missing 'cp_loss'"
        assert "gap_analysis" in data, "Response missing 'gap_analysis'"
        assert "coaching_message" in data, "Response missing 'coaching_message'"
    
    def test_gap_analysis_structure(self, authenticated_session, pending_game_with_moments):
        """Test that gap_analysis contains proper structure"""
        game_id = pending_game_with_moments["game_id"]
        move_number = pending_game_with_moments["first_moment"]["move_number"]
        
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{move_number}/analyze-gap",
            json={
                "user_stated_plan": "I wanted to win material",
                "user_hypothesis_category": "win_material",
                "user_confidence": "guessing"
            }
        )
        
        assert res.status_code == 200
        data = res.json()
        gap = data.get("gap_analysis", {})
        
        # Check gap_analysis structure
        assert "primary_gap" in gap, "gap_analysis missing 'primary_gap'"
        assert "confidence" in gap, "gap_analysis missing 'confidence'"
        assert "evidence" in gap, "gap_analysis missing 'evidence'"
        assert "explanation" in gap, "gap_analysis missing 'explanation'"
        assert "coaching_focus" in gap, "gap_analysis missing 'coaching_focus'"
        
        # Validate confidence is a float between 0 and 1
        assert isinstance(gap["confidence"], (int, float)), "Confidence should be numeric"
        assert 0 <= gap["confidence"] <= 1, f"Confidence {gap['confidence']} should be between 0 and 1"
        
        # Validate primary_gap is a non-empty string
        assert isinstance(gap["primary_gap"], str), "primary_gap should be a string"
        assert len(gap["primary_gap"]) > 0, "primary_gap should not be empty"
    
    def test_valid_gap_types_returned(self, authenticated_session, pending_game_with_moments):
        """Test that primary_gap returns valid gap type from CognitiveGap enum"""
        game_id = pending_game_with_moments["game_id"]
        move_number = pending_game_with_moments["first_moment"]["move_number"]
        
        valid_gap_types = [
            "calculation_depth", "calculation_error",
            "threat_blindness", "hanging_piece_blindness", "check_blindness",
            "tactical_oversight", "missed_fork", "missed_pin", "missed_skewer",
            "missed_discovered", "back_rank_blindness",
            "positional_misread", "wrong_plan", "premature_action",
            "defensive_lapse", "king_safety_neglect",
            "overconfidence", "desperation",
            "time_pressure", "rushed_move",
            "pattern_unfamiliarity", "unclear"
        ]
        
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{move_number}/analyze-gap",
            json={
                "user_stated_plan": "I thought this move was safe",
                "user_hypothesis_category": "defend",
                "user_confidence": "somewhat_sure"
            }
        )
        
        assert res.status_code == 200
        data = res.json()
        gap = data.get("gap_analysis", {})
        
        primary_gap = gap.get("primary_gap", "")
        assert primary_gap in valid_gap_types, f"'{primary_gap}' is not a valid gap type"
    
    def test_different_user_inputs_affect_analysis(self, authenticated_session, pending_game_with_moments):
        """Test that different user inputs can affect the analysis"""
        game_id = pending_game_with_moments["game_id"]
        move_number = pending_game_with_moments["first_moment"]["move_number"]
        
        # Test with attack intent
        res1 = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{move_number}/analyze-gap",
            json={
                "user_stated_plan": "I was attacking the queen",
                "user_hypothesis_category": "attack",
                "user_confidence": "very_sure"
            }
        )
        
        # Test with defend intent
        res2 = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{move_number}/analyze-gap",
            json={
                "user_stated_plan": "I was trying to protect my pieces",
                "user_hypothesis_category": "defend",
                "user_confidence": "guessing"
            }
        )
        
        assert res1.status_code == 200
        assert res2.status_code == 200
        
        # Both should return valid analysis
        data1 = res1.json()
        data2 = res2.json()
        
        assert "gap_analysis" in data1
        assert "gap_analysis" in data2
        
        # Explanation should exist in both
        assert data1["gap_analysis"].get("explanation")
        assert data2["gap_analysis"].get("explanation")
    
    def test_endpoint_without_optional_params(self, authenticated_session, pending_game_with_moments):
        """Test that endpoint works with minimal/empty optional parameters"""
        game_id = pending_game_with_moments["game_id"]
        move_number = pending_game_with_moments["first_moment"]["move_number"]
        
        # Test with empty body
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{move_number}/analyze-gap",
            json={}
        )
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        # Should still return gap analysis
        assert "gap_analysis" in data
        assert data["gap_analysis"].get("primary_gap")
    
    def test_endpoint_with_null_params(self, authenticated_session, pending_game_with_moments):
        """Test that endpoint handles null parameters gracefully"""
        game_id = pending_game_with_moments["game_id"]
        move_number = pending_game_with_moments["first_moment"]["move_number"]
        
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{move_number}/analyze-gap",
            json={
                "user_stated_plan": None,
                "user_hypothesis_category": None,
                "user_confidence": None
            }
        )
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        assert "gap_analysis" in data
    
    def test_invalid_game_id_returns_404(self, authenticated_session):
        """Test that invalid game_id returns 404"""
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/non-existent-game-id-12345/move/10/analyze-gap",
            json={"user_stated_plan": "test"}
        )
        
        assert res.status_code == 404
    
    def test_invalid_move_number_returns_404(self, authenticated_session, pending_game_with_moments):
        """Test that invalid move_number returns 404"""
        game_id = pending_game_with_moments["game_id"]
        
        # Use a move number that definitely doesn't exist
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/999/analyze-gap",
            json={"user_stated_plan": "test"}
        )
        
        assert res.status_code == 404
    
    def test_unauthenticated_request_handled(self):
        """Test that unauthenticated request is handled properly (401/403/404)"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Use a fake game_id - endpoint may return 401/403 for auth or 404 for not found
        # Either is acceptable as long as it doesn't return 200 with data
        res = session.post(
            f"{BASE_URL}/api/games/test-game-id/move/10/analyze-gap",
            json={"user_stated_plan": "test"}
        )
        
        # Should NOT return 200 success for unauthenticated request
        assert res.status_code in [401, 403, 404], f"Expected auth error or 404, got {res.status_code}"
        
        # If we get data, it should not contain gap_analysis (meaning no leak of data)
        if res.status_code == 200:
            data = res.json()
            assert "gap_analysis" not in data or data.get("error"), "Should not return valid gap_analysis for unauthenticated"
    
    def test_coaching_message_is_concise(self, authenticated_session, pending_game_with_moments):
        """Test that coaching_message is a concise actionable string"""
        game_id = pending_game_with_moments["game_id"]
        move_number = pending_game_with_moments["first_moment"]["move_number"]
        
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{move_number}/analyze-gap",
            json={
                "user_stated_plan": "I was trying to create a threat",
                "user_hypothesis_category": "attack",
                "user_confidence": "somewhat_sure"
            }
        )
        
        assert res.status_code == 200
        data = res.json()
        
        coaching_message = data.get("coaching_message", "")
        
        # Should be a non-empty string
        assert isinstance(coaching_message, str)
        assert len(coaching_message) > 0, "coaching_message should not be empty"
        
        # Should be concise (less than 200 chars)
        assert len(coaching_message) < 200, f"coaching_message too long: {len(coaching_message)} chars"
    
    def test_explanation_is_human_readable(self, authenticated_session, pending_game_with_moments):
        """Test that explanation is human-readable and provides clear insight"""
        game_id = pending_game_with_moments["game_id"]
        move_number = pending_game_with_moments["first_moment"]["move_number"]
        
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{move_number}/analyze-gap",
            json={
                "user_stated_plan": "Defending my king from attack",
                "user_hypothesis_category": "defend",
                "user_confidence": "very_sure"
            }
        )
        
        assert res.status_code == 200
        data = res.json()
        gap = data.get("gap_analysis", {})
        
        explanation = gap.get("explanation", "")
        
        # Should be a substantial explanation
        assert isinstance(explanation, str)
        assert len(explanation) > 20, f"explanation too short: '{explanation}'"
        
        # Should form complete sentences (ends with period or similar)
        assert explanation[-1] in ".!?", f"explanation should end with punctuation: '{explanation}'"
    
    def test_evidence_references_position(self, authenticated_session, pending_game_with_moments):
        """Test that evidence references concrete details from the position"""
        game_id = pending_game_with_moments["game_id"]
        move_number = pending_game_with_moments["first_moment"]["move_number"]
        
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{move_number}/analyze-gap",
            json={
                "user_stated_plan": "I wanted to simplify the position",
                "user_hypothesis_category": "trade_simplify",
                "user_confidence": "somewhat_sure"
            }
        )
        
        assert res.status_code == 200
        data = res.json()
        gap = data.get("gap_analysis", {})
        
        evidence = gap.get("evidence", "")
        
        # Should provide some evidence
        assert isinstance(evidence, str)
        assert len(evidence) > 0, "evidence should not be empty"


class TestCognitiveGapWithDifferentMoves:
    """Test cognitive gap analysis across different move types"""
    
    def test_analyze_blunder_move(self, authenticated_session, pending_game_with_moments):
        """Test analysis of a blunder move"""
        game_id = pending_game_with_moments["game_id"]
        
        # Find a blunder move
        blunder_moment = None
        for moment in pending_game_with_moments["moments"]:
            if moment.get("type") == "blunder":
                blunder_moment = moment
                break
        
        if not blunder_moment:
            pytest.skip("No blunder moments found")
        
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{blunder_moment['move_number']}/analyze-gap",
            json={
                "user_stated_plan": "I thought this was safe",
                "user_hypothesis_category": "defend",
                "user_confidence": "very_sure"
            }
        )
        
        assert res.status_code == 200
        data = res.json()
        
        # Blunders typically have high cp_loss
        assert data.get("cp_loss", 0) >= 100, f"Expected high cp_loss for blunder, got {data.get('cp_loss')}"
        
        # Should identify some gap
        gap = data.get("gap_analysis", {})
        assert gap.get("primary_gap") != "unclear", "Should identify specific gap for blunder"
    
    def test_analyze_mistake_move(self, authenticated_session, pending_game_with_moments):
        """Test analysis of a mistake move"""
        game_id = pending_game_with_moments["game_id"]
        
        # Find a mistake move
        mistake_moment = None
        for moment in pending_game_with_moments["moments"]:
            if moment.get("type") == "mistake":
                mistake_moment = moment
                break
        
        if not mistake_moment:
            pytest.skip("No mistake moments found")
        
        res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{mistake_moment['move_number']}/analyze-gap",
            json={
                "user_stated_plan": "I was developing my pieces",
                "user_hypothesis_category": "improve_pieces",
                "user_confidence": "somewhat_sure"
            }
        )
        
        assert res.status_code == 200
        data = res.json()
        
        # Should have valid analysis
        gap = data.get("gap_analysis", {})
        assert "primary_gap" in gap
        assert "explanation" in gap


class TestCognitiveGapIntegration:
    """Integration tests for cognitive gap feature"""
    
    def test_gap_analysis_integrates_with_reflection_submit(self, authenticated_session, pending_game_with_moments):
        """Test that gap analysis can be used in reflection submission flow"""
        game_id = pending_game_with_moments["game_id"]
        moment = pending_game_with_moments["first_moment"]
        
        # Step 1: Get cognitive gap analysis
        gap_res = authenticated_session.post(
            f"{BASE_URL}/api/games/{game_id}/move/{moment['move_number']}/analyze-gap",
            json={
                "user_stated_plan": "I wanted to attack the opponent",
                "user_hypothesis_category": "attack",
                "user_confidence": "somewhat_sure"
            }
        )
        
        assert gap_res.status_code == 200
        gap_data = gap_res.json()
        
        # Verify the data can be used in reflection
        assert "gap_analysis" in gap_data
        
        # The gap_analysis should be suitable for inclusion in reflection submission
        gap_analysis = gap_data["gap_analysis"]
        assert "primary_gap" in gap_analysis
        assert "explanation" in gap_analysis

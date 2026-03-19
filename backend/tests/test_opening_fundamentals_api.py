"""
Test Opening Fundamentals API
=============================

Tests the /api/analysis/{game_id}/opening-fundamentals endpoint.
This endpoint analyzes a game's opening for fundamental principle violations/adherences.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def auth_session(api_client):
    """Get authenticated session via dev login"""
    response = api_client.get(f"{BASE_URL}/api/auth/dev-login")
    if response.status_code == 200:
        # Session cookie is set by the response
        return api_client
    pytest.skip("Dev login failed - skipping authenticated tests")


@pytest.fixture
def test_game_id(auth_session):
    """Get a game ID to test with"""
    response = auth_session.get(f"{BASE_URL}/api/games")
    if response.status_code == 200:
        games = response.json()
        if games and len(games) > 0:
            return games[0].get('game_id')
    pytest.skip("No games available for testing")


class TestOpeningFundamentalsAPI:
    """Test suite for Opening Fundamentals API endpoint"""

    def test_endpoint_returns_200_for_valid_game(self, auth_session, test_game_id):
        """Test that endpoint returns 200 for a valid game ID"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/{test_game_id}/opening-fundamentals")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_response_has_required_fields(self, auth_session, test_game_id):
        """Test that response contains all required fields"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/{test_game_id}/opening-fundamentals")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required fields
        assert 'score' in data, "Response missing 'score' field"
        assert 'violations' in data, "Response missing 'violations' field"
        assert 'adherences' in data, "Response missing 'adherences' field"
        assert 'summary' in data, "Response missing 'summary' field"
        assert 'total_violations' in data, "Response missing 'total_violations' field"

    def test_score_is_valid_percentage(self, auth_session, test_game_id):
        """Test that score is a valid percentage (0-100)"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/{test_game_id}/opening-fundamentals")
        assert response.status_code == 200
        
        data = response.json()
        score = data.get('score')
        
        assert isinstance(score, (int, float)), "Score should be a number"
        assert 0 <= score <= 100, f"Score {score} should be between 0 and 100"

    def test_violations_is_list(self, auth_session, test_game_id):
        """Test that violations is a list"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/{test_game_id}/opening-fundamentals")
        assert response.status_code == 200
        
        data = response.json()
        violations = data.get('violations')
        
        assert isinstance(violations, list), "Violations should be a list"

    def test_adherences_is_list(self, auth_session, test_game_id):
        """Test that adherences is a list"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/{test_game_id}/opening-fundamentals")
        assert response.status_code == 200
        
        data = response.json()
        adherences = data.get('adherences')
        
        assert isinstance(adherences, list), "Adherences should be a list"

    def test_violation_has_required_fields(self, auth_session, test_game_id):
        """Test that each violation has required fields (if any exist)"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/{test_game_id}/opening-fundamentals")
        assert response.status_code == 200
        
        data = response.json()
        violations = data.get('violations', [])
        
        # Only test if there are violations
        for violation in violations:
            assert 'principle' in violation, "Violation missing 'principle' field"
            assert 'principle_name' in violation, "Violation missing 'principle_name' field"
            assert 'move_number' in violation, "Violation missing 'move_number' field"
            assert 'explanation' in violation, "Violation missing 'explanation' field"
            assert 'teaching' in violation, "Violation missing 'teaching' field"
            assert 'severity' in violation, "Violation missing 'severity' field"
            assert 'what_to_think' in violation, "Violation missing 'what_to_think' field"

    def test_adherence_has_required_fields(self, auth_session, test_game_id):
        """Test that each adherence has required fields (if any exist)"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/{test_game_id}/opening-fundamentals")
        assert response.status_code == 200
        
        data = response.json()
        adherences = data.get('adherences', [])
        
        # Only test if there are adherences
        for adherence in adherences:
            assert 'principle' in adherence, "Adherence missing 'principle' field"
            assert 'message' in adherence, "Adherence missing 'message' field"

    def test_summary_is_non_empty_string(self, auth_session, test_game_id):
        """Test that summary is a non-empty string"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/{test_game_id}/opening-fundamentals")
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get('summary')
        
        assert isinstance(summary, str), "Summary should be a string"
        assert len(summary) > 0, "Summary should not be empty"

    def test_total_violations_matches_list_length(self, auth_session, test_game_id):
        """Test that total_violations count matches violations list length"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/{test_game_id}/opening-fundamentals")
        assert response.status_code == 200
        
        data = response.json()
        total_violations = data.get('total_violations')
        violations = data.get('violations', [])
        
        assert total_violations == len(violations), \
            f"total_violations ({total_violations}) should match violations list length ({len(violations)})"

    def test_returns_404_for_invalid_game(self, auth_session):
        """Test that endpoint returns 404 for invalid game ID"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/invalid-game-id/opening-fundamentals")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_requires_authentication(self, api_client):
        """Test that endpoint requires authentication (returns 401 or 404)"""
        response = api_client.get(f"{BASE_URL}/api/analysis/some-game-id/opening-fundamentals")
        # Without auth, should return 401 (unauthorized) or 404 (game not found for user)
        assert response.status_code in [401, 404], \
            f"Expected 401 or 404, got {response.status_code}"


class TestOpeningPrincipleValues:
    """Test suite for validating opening principle values"""

    VALID_PRINCIPLES = [
        'same_piece_twice',
        'castle_early', 
        'develop_minor_pieces',
        'queen_out_early',
        'center_control',
        'develop_before_attack',
        'connect_rooks',
        'unnecessary_pawn_moves',
        'king_safety',
        'develop_toward_center'
    ]

    VALID_SEVERITIES = ['minor', 'moderate', 'major']

    def test_violations_have_valid_principle(self, auth_session, test_game_id):
        """Test that all violations have valid principle values"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/{test_game_id}/opening-fundamentals")
        assert response.status_code == 200
        
        data = response.json()
        violations = data.get('violations', [])
        
        for violation in violations:
            principle = violation.get('principle')
            assert principle in self.VALID_PRINCIPLES, \
                f"Invalid principle '{principle}'. Valid: {self.VALID_PRINCIPLES}"

    def test_violations_have_valid_severity(self, auth_session, test_game_id):
        """Test that all violations have valid severity values"""
        response = auth_session.get(f"{BASE_URL}/api/analysis/{test_game_id}/opening-fundamentals")
        assert response.status_code == 200
        
        data = response.json()
        violations = data.get('violations', [])
        
        for violation in violations:
            severity = violation.get('severity')
            assert severity in self.VALID_SEVERITIES, \
                f"Invalid severity '{severity}'. Valid: {self.VALID_SEVERITIES}"

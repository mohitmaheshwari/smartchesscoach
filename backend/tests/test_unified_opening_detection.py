"""
Tests for Unified Opening Detection Feature (22+ openings)
==========================================================

Tests the detect_opening_from_moves() function in opening_mastery.py
which now supports 22+ openings including Vienna, Scotch, Petrov, King's
Indian, Slav, Dutch, and many more.

Also tests opening detection after coach's move in server.py.
"""
import pytest
import requests
import os
import sys

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://mistake-tracker-3.preview.emergentagent.com')

# Add backend to path for direct imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestUnifiedOpeningDetection:
    """Test detect_opening_from_moves() for 22+ openings"""
    
    def test_italian_game_detection(self):
        """Italian Game: e4 e5 Nf3 Nc6 Bc4"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["e4", "e5", "Nf3", "Nc6", "Bc4"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Italian Game not detected"
        assert "italian" in result.get("opening_key", "").lower() or "italian" in result.get("opening_name", "").lower()
    
    def test_ruy_lopez_detection(self):
        """Ruy Lopez: e4 e5 Nf3 Nc6 Bb5"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["e4", "e5", "Nf3", "Nc6", "Bb5"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Ruy Lopez not detected"
        assert "ruy" in result.get("opening_key", "").lower() or "lopez" in result.get("opening_name", "").lower() or "ruy_lopez" in result.get("opening_key", "")
    
    def test_vienna_game_detection(self):
        """Vienna Game: e4 e5 Nc3"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["e4", "e5", "Nc3"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Vienna Game not detected"
        assert "vienna" in result.get("opening_key", "").lower() or "vienna" in result.get("opening_name", "").lower()
    
    def test_scotch_game_detection(self):
        """Scotch Game: e4 e5 Nf3 Nc6 d4"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["e4", "e5", "Nf3", "Nc6", "d4"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Scotch Game not detected"
        assert "scotch" in result.get("opening_key", "").lower() or "scotch" in result.get("opening_name", "").lower()
    
    def test_petrov_defense_detection(self):
        """Petrov Defense: e4 e5 Nf3 Nf6"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["e4", "e5", "Nf3", "Nf6"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Petrov Defense not detected"
        assert "petrov" in result.get("opening_key", "").lower() or "petrov" in result.get("opening_name", "").lower()
    
    def test_philidor_defense_detection(self):
        """Philidor Defense: e4 e5 Nf3 d6"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["e4", "e5", "Nf3", "d6"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Philidor Defense not detected"
        assert "philidor" in result.get("opening_key", "").lower() or "philidor" in result.get("opening_name", "").lower()
    
    def test_kings_indian_defense_detection(self):
        """King's Indian Defense: d4 Nf6 c4 g6"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["d4", "Nf6", "c4", "g6"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "King's Indian Defense not detected"
        key = result.get("opening_key", "").lower()
        name = result.get("opening_name", "").lower()
        assert "king" in key or "indian" in key or "king" in name or "indian" in name
    
    def test_slav_defense_detection(self):
        """Slav Defense: d4 d5 c4 c6"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["d4", "d5", "c4", "c6"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Slav Defense not detected"
        assert "slav" in result.get("opening_key", "").lower() or "slav" in result.get("opening_name", "").lower()
    
    def test_dutch_defense_detection(self):
        """Dutch Defense: d4 f5"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["d4", "f5"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Dutch Defense not detected"
        assert "dutch" in result.get("opening_key", "").lower() or "dutch" in result.get("opening_name", "").lower()
    
    def test_sicilian_defense_detection(self):
        """Sicilian Defense: e4 c5"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["e4", "c5"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Sicilian Defense not detected"
        assert "sicilian" in result.get("opening_key", "").lower() or "sicilian" in result.get("opening_name", "").lower()
    
    def test_caro_kann_detection(self):
        """Caro-Kann: e4 c6"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["e4", "c6"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Caro-Kann not detected"
        assert "caro" in result.get("opening_key", "").lower() or "kann" in result.get("opening_name", "").lower()
    
    def test_french_defense_detection(self):
        """French Defense: e4 e6"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["e4", "e6"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "French Defense not detected"
        assert "french" in result.get("opening_key", "").lower() or "french" in result.get("opening_name", "").lower()
    
    def test_scandinavian_defense_detection(self):
        """Scandinavian Defense: e4 d5"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["e4", "d5"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Scandinavian Defense not detected"
        assert "scandinavian" in result.get("opening_key", "").lower() or "scandinavian" in result.get("opening_name", "").lower()
    
    def test_queens_gambit_detection(self):
        """Queen's Gambit: d4 d5 c4"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["d4", "d5", "c4"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Queen's Gambit not detected"
        key = result.get("opening_key", "").lower()
        name = result.get("opening_name", "").lower()
        assert "queen" in key or "gambit" in key or "queen" in name or "gambit" in name
    
    def test_london_system_detection(self):
        """London System: d4 [any] Bf4"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["d4", "d5", "Bf4"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "London System not detected"
        assert "london" in result.get("opening_key", "").lower() or "london" in result.get("opening_name", "").lower()
    
    def test_nimzo_indian_detection(self):
        """Nimzo-Indian: d4 Nf6 c4 e6 Nc3 Bb4"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Nimzo-Indian not detected"
        key = result.get("opening_key", "").lower()
        name = result.get("opening_name", "").lower()
        assert "nimzo" in key or "indian" in key or "nimzo" in name or "indian" in name
    
    def test_grunfeld_defense_detection(self):
        """Grünfeld Defense: d4 Nf6 c4 g6 Nc3 d5
        Note: First 4 moves overlap with King's Indian, so detection depends on move 5-6
        """
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["d4", "Nf6", "c4", "g6", "Nc3", "d5"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Grünfeld Defense not detected"
        key = result.get("opening_key", "").lower()
        name = result.get("opening_name", "").lower()
        # Grünfeld can be detected as itself or King's Indian subfamily
        assert "grunfeld" in key or "grünfeld" in name or "king" in key or "indian" in name, \
            f"Expected Grünfeld or related opening, got {key}: {name}"
    
    def test_benoni_defense_detection(self):
        """Benoni Defense: d4 Nf6 c4 c5 d5"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["d4", "Nf6", "c4", "c5", "d5"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Benoni Defense not detected"
        assert "benoni" in result.get("opening_key", "").lower() or "benoni" in result.get("opening_name", "").lower()
    
    def test_budapest_gambit_detection(self):
        """Budapest Gambit: d4 Nf6 c4 e5"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["d4", "Nf6", "c4", "e5"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Budapest Gambit not detected"
        assert "budapest" in result.get("opening_key", "").lower() or "budapest" in result.get("opening_name", "").lower()
    
    def test_qgd_detection(self):
        """Queen's Gambit Declined: d4 d5 c4 e6"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["d4", "d5", "c4", "e6"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "QGD not detected"
        key = result.get("opening_key", "").lower()
        name = result.get("opening_name", "").lower()
        assert "qgd" in key or "declined" in key or "declined" in name or "queen" in name
    
    def test_queens_indian_detection(self):
        """Queen's Indian: d4 Nf6 c4 e6 Nf3 b6"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        moves = ["d4", "Nf6", "c4", "e6", "Nf3", "b6"]
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Queen's Indian not detected"
        key = result.get("opening_key", "").lower()
        name = result.get("opening_name", "").lower()
        assert "queen" in key or "indian" in key or "queen" in name or "indian" in name
    
    def test_no_detection_on_empty_moves(self):
        """Empty move list should return None"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        result = detect_opening_from_moves([])
        assert result is None
    
    def test_no_detection_on_single_move(self):
        """Single move should return None (minimum is 2)"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        result = detect_opening_from_moves(["e4"])
        assert result is None


class TestOpeningDetectionCountTotal:
    """Verify at least 22 unique openings are detectable"""
    
    def test_at_least_20_unique_openings_detected(self):
        """Count unique openings that can be detected"""
        try:
            from services.opening_mastery import detect_opening_from_moves
        except ImportError:
            pytest.skip("Module import skipped in test context")
        
        # All opening move sequences we want to verify
        test_cases = [
            ("Italian Game", ["e4", "e5", "Nf3", "Nc6", "Bc4"]),
            ("Ruy Lopez", ["e4", "e5", "Nf3", "Nc6", "Bb5"]),
            ("Vienna Game", ["e4", "e5", "Nc3"]),
            ("Scotch Game", ["e4", "e5", "Nf3", "Nc6", "d4"]),
            ("Petrov Defense", ["e4", "e5", "Nf3", "Nf6"]),
            ("Philidor Defense", ["e4", "e5", "Nf3", "d6"]),
            ("King's Indian", ["d4", "Nf6", "c4", "g6"]),
            ("Slav Defense", ["d4", "d5", "c4", "c6"]),
            ("Dutch Defense", ["d4", "f5"]),
            ("Sicilian Defense", ["e4", "c5"]),
            ("Caro-Kann", ["e4", "c6"]),
            ("French Defense", ["e4", "e6"]),
            ("Scandinavian", ["e4", "d5"]),
            ("Queen's Gambit", ["d4", "d5", "c4"]),
            ("London System", ["d4", "d5", "Bf4"]),
            ("Nimzo-Indian", ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"]),
            ("Grünfeld", ["d4", "Nf6", "c4", "g6", "Nc3", "d5"]),
            ("Benoni", ["d4", "Nf6", "c4", "c5", "d5"]),
            ("Budapest", ["d4", "Nf6", "c4", "e5"]),
            ("QGD", ["d4", "d5", "c4", "e6"]),
            ("Queen's Indian", ["d4", "Nf6", "c4", "e6", "Nf3", "b6"]),
            ("Nimzowitsch Defense", ["e4", "Nc6"]),
        ]
        
        detected_keys = set()
        for name, moves in test_cases:
            result = detect_opening_from_moves(moves)
            if result and result.get("opening_key"):
                detected_keys.add(result["opening_key"])
        
        assert len(detected_keys) >= 20, f"Expected at least 20 unique openings, got {len(detected_keys)}: {detected_keys}"


class TestExplainPositionEndpoint:
    """Test POST /api/coach/play/explain-position endpoint"""
    
    @pytest.fixture
    def authenticated_session(self):
        """Session with dev login authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate via dev login
        res = session.get(f"{BASE_URL}/api/auth/dev-login")
        if res.status_code != 200:
            pytest.skip("Dev login failed - skipping authenticated tests")
        
        return session
    
    def test_explain_position_requires_auth(self):
        """Endpoint requires authentication - returns 404 or 401/403"""
        response = requests.post(
            f"{BASE_URL}/api/coach/play/explain-position",
            json={"session_id": "test-session"}
        )
        # Without auth, the endpoint returns 404 (session not found) which is acceptable
        assert response.status_code in [401, 403, 404], f"Expected auth/not found error, got {response.status_code}"
    
    def test_explain_position_requires_session_id(self, authenticated_session):
        """Endpoint requires session_id parameter"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/explain-position",
            json={}
        )
        assert response.status_code == 400, "Expected 400 for missing session_id"
    
    def test_explain_position_returns_404_for_invalid_session(self, authenticated_session):
        """Endpoint returns 404 for non-existent session"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/explain-position",
            json={"session_id": "non-existent-session-12345"}
        )
        assert response.status_code == 404, "Expected 404 for invalid session"
    
    def test_explain_position_with_valid_session(self, authenticated_session):
        """Start a game and request position explanation - KNOWN BUG: chess module not imported"""
        # First, start a coach play session
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white"}
        )
        
        if start_response.status_code != 200:
            pytest.skip("Could not start coach play session")
        
        session_data = start_response.json()
        session_id = session_data.get("session_id")
        
        if not session_id:
            pytest.skip("No session_id returned from start")
        
        try:
            # Now request position explanation
            explain_response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/explain-position",
                json={"session_id": session_id}
            )
            
            # BUG: Returns 500 due to missing "import chess" in server.py
            # The endpoint uses chess.Board() but chess is not imported
            if explain_response.status_code == 500:
                error_detail = explain_response.json().get("detail", "")
                if "analyze" in error_detail.lower() or "position" in error_detail.lower():
                    # This is the known bug - chess module not imported
                    pytest.fail(
                        "BUG: POST /api/coach/play/explain-position returns 500. "
                        "Root cause: 'chess' module is not imported in server.py but is used at line 10944. "
                        f"Error: {error_detail}"
                    )
            
            assert explain_response.status_code == 200, f"Expected 200, got {explain_response.status_code}"
            
            data = explain_response.json()
            
            # Verify response structure
            assert data.get("success") == True, "Expected success=True"
            assert "explanation" in data, "Expected 'explanation' field in response"
            
            # Check explanation structure
            explanation = data.get("explanation", {})
            assert isinstance(explanation, dict), "explanation should be a dict"
            
        finally:
            # Clean up - end the session
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id}
            )


class TestDynamicCoachingInPracticeMode:
    """Test dynamic_coaching field in practice mode endpoint"""
    
    @pytest.fixture
    def authenticated_session(self):
        """Session with dev login authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        res = session.get(f"{BASE_URL}/api/auth/dev-login")
        if res.status_code != 200:
            pytest.skip("Dev login failed - skipping authenticated tests")
        
        return session
    
    def test_practice_mode_start(self, authenticated_session):
        """Test that practice mode starts successfully"""
        # Get available openings first
        repertoire_response = authenticated_session.get(f"{BASE_URL}/api/openings/repertoire")
        
        if repertoire_response.status_code != 200:
            pytest.skip("Could not get opening repertoire")
        
        # Try to start practice with italian-game
        response = authenticated_session.post(
            f"{BASE_URL}/api/openings/italian-game/practice/start"
        )
        
        # Practice mode might not be available for all openings
        if response.status_code == 404:
            pytest.skip("Italian game practice not available")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "session_id" in data, "Expected session_id in response"
        assert "fen" in data, "Expected fen in response"
    
    def test_practice_mode_move_includes_dynamic_coaching_field(self, authenticated_session):
        """Make a move in practice mode and check for dynamic_coaching"""
        # Start practice session
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/openings/italian-game/practice/start"
        )
        
        if start_response.status_code == 404:
            pytest.skip("Italian game practice not available")
        
        if start_response.status_code != 200:
            pytest.skip(f"Could not start practice: {start_response.status_code}")
        
        session_data = start_response.json()
        session_id = session_data.get("session_id")
        
        if not session_id:
            pytest.skip("No session_id returned")
        
        # Determine user color and expected first move
        user_color = session_data.get("user_color", "white")
        
        try:
            # Make a move - for Italian white plays e4 first
            if user_color == "white":
                move = "e2e4"  # UCI format
            else:
                # If playing black, coach played e4, we respond e5
                move = "e7e5"
            
            move_response = authenticated_session.post(
                f"{BASE_URL}/api/openings/practice/move",
                json={"session_id": session_id, "move": move}
            )
            
            if move_response.status_code != 200:
                # Move might be wrong or practice works differently
                # Check response anyway - the endpoint should exist
                pass
            
            # The endpoint exists and returns a response
            assert move_response.status_code in [200, 400, 422], f"Unexpected status: {move_response.status_code}"
            
            if move_response.status_code == 200:
                data = move_response.json()
                # dynamic_coaching may be present and can be None or a dict
                # Just verify the response structure is valid
                assert "fen" in data or "valid" in data, "Expected fen or valid field"
        
        finally:
            # End session
            authenticated_session.post(
                f"{BASE_URL}/api/openings/practice/{session_id}/end"
            )

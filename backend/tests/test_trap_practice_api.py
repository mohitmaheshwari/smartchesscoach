"""
Tests for Trap Practice API endpoints and trap library functionality.

Tests the following features:
- Trap library statistics API
- Trap filtering by difficulty
- Checkmate traps retrieval
- Opening lesson with traps data
- Trap data structure validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://json-body-issue.preview.emergentagent.com')


class TestTrapLibraryAPI:
    """Tests for trap library API endpoints"""

    @pytest.fixture
    def session(self):
        """Create a session with dev login authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate via dev login
        res = session.get(f"{BASE_URL}/api/auth/dev-login")
        if res.status_code != 200:
            pytest.skip("Dev login failed - skipping authenticated tests")
        
        return session

    def test_trap_statistics_endpoint_returns_valid_data(self, session):
        """Test GET /api/traps/statistics returns trap library stats"""
        res = session.get(f"{BASE_URL}/api/traps/statistics")
        
        assert res.status_code == 200
        data = res.json()
        
        # Verify response structure
        assert "total_traps" in data
        assert "checkmate_traps" in data
        assert "by_difficulty" in data
        assert "by_result" in data
        assert "by_opening" in data
        
        # Verify we have traps in the library
        assert data["total_traps"] > 0
        assert data["checkmate_traps"] > 0
        
        # Verify difficulty levels exist
        difficulties = data["by_difficulty"]
        assert "beginner" in difficulties
        assert "intermediate" in difficulties
        assert "advanced" in difficulties
        
        # Verify result types exist
        results = data["by_result"]
        assert "checkmate" in results
        assert results["checkmate"] > 0

    def test_checkmate_traps_endpoint_returns_checkmate_traps(self, session):
        """Test GET /api/traps/checkmates returns only checkmate traps"""
        res = session.get(f"{BASE_URL}/api/traps/checkmates")
        
        assert res.status_code == 200
        data = res.json()
        
        assert "traps" in data
        traps = data["traps"]
        
        # Verify we got checkmate traps
        assert len(traps) > 0
        
        # All returned traps should be checkmates
        for trap in traps:
            assert trap["result_type"] == "checkmate"
            assert "name" in trap
            assert "description" in trap
            assert "trap_line" in trap
            assert "opening_key" in trap

    def test_traps_by_difficulty_beginner(self, session):
        """Test GET /api/traps/difficulty/beginner returns beginner traps"""
        res = session.get(f"{BASE_URL}/api/traps/difficulty/beginner")
        
        assert res.status_code == 200
        data = res.json()
        
        assert "traps" in data
        traps = data["traps"]
        
        # All returned traps should be beginner
        for trap in traps:
            assert trap["difficulty"] == "beginner"

    def test_traps_by_difficulty_intermediate(self, session):
        """Test GET /api/traps/difficulty/intermediate returns intermediate traps"""
        res = session.get(f"{BASE_URL}/api/traps/difficulty/intermediate")
        
        assert res.status_code == 200
        data = res.json()
        
        assert "traps" in data
        traps = data["traps"]
        
        # Should have intermediate traps
        assert len(traps) > 0
        
        # All returned traps should be intermediate
        for trap in traps:
            assert trap["difficulty"] == "intermediate"

    def test_traps_by_difficulty_advanced(self, session):
        """Test GET /api/traps/difficulty/advanced returns advanced traps"""
        res = session.get(f"{BASE_URL}/api/traps/difficulty/advanced")
        
        assert res.status_code == 200
        data = res.json()
        
        assert "traps" in data
        traps = data["traps"]
        
        # All returned traps should be advanced
        for trap in traps:
            assert trap["difficulty"] == "advanced"

    def test_traps_by_difficulty_invalid_returns_400(self, session):
        """Test GET /api/traps/difficulty/invalid returns 400"""
        res = session.get(f"{BASE_URL}/api/traps/difficulty/invalid")
        
        assert res.status_code == 400


class TestOpeningLessonTrapsAPI:
    """Tests for opening lesson endpoint that includes traps"""

    @pytest.fixture
    def session(self):
        """Create a session with dev login authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate via dev login
        res = session.get(f"{BASE_URL}/api/auth/dev-login")
        if res.status_code != 200:
            pytest.skip("Dev login failed - skipping authenticated tests")
        
        return session

    def test_italian_game_lesson_includes_traps(self, session):
        """Test GET /api/openings/italian-game includes trap data"""
        res = session.get(f"{BASE_URL}/api/openings/italian-game")
        
        assert res.status_code == 200
        data = res.json()
        
        # Verify opening data structure
        assert "opening" in data
        opening = data["opening"]
        
        assert opening["name"] == "Italian Game"
        assert "traps" in opening
        
        # Italian Game should have traps
        traps = opening["traps"]
        assert len(traps) > 0
        
        # Verify trap structure
        for trap in traps:
            assert "name" in trap
            assert "description" in trap
            assert "setup_moves" in trap
            assert "trap_line" in trap
            assert "result_type" in trap
            assert "difficulty" in trap

    def test_italian_game_has_fried_liver_trap(self, session):
        """Test Italian Game includes the famous Fried Liver Attack trap"""
        res = session.get(f"{BASE_URL}/api/openings/italian-game")
        
        assert res.status_code == 200
        opening = res.json()["opening"]
        traps = opening["traps"]
        
        # Find Fried Liver Attack
        fried_liver = next((t for t in traps if "Fried Liver" in t["name"]), None)
        
        assert fried_liver is not None
        assert fried_liver["result_type"] == "wins_material"
        assert fried_liver["difficulty"] == "intermediate"
        assert len(fried_liver["setup_moves"]) > 0
        assert len(fried_liver["trap_line"]) > 0

    def test_italian_game_has_legals_mate_trap(self, session):
        """Test Italian Game includes Legal's Mate trap"""
        res = session.get(f"{BASE_URL}/api/openings/italian-game")
        
        assert res.status_code == 200
        opening = res.json()["opening"]
        traps = opening["traps"]
        
        # Find Legal's Mate
        legals_mate = next((t for t in traps if "Legal" in t["name"]), None)
        
        assert legals_mate is not None
        assert legals_mate["result_type"] == "checkmate"
        assert legals_mate["difficulty"] == "intermediate"

    def test_sicilian_defense_lesson_includes_traps(self, session):
        """Test GET /api/openings/sicilian-defense includes trap data"""
        res = session.get(f"{BASE_URL}/api/openings/sicilian-defense")
        
        assert res.status_code == 200
        data = res.json()
        
        opening = data["opening"]
        assert opening["name"] == "Sicilian Defense"
        assert "traps" in opening
        
        # Sicilian should have traps (Siberian Trap, Magnus Smith Trap)
        traps = opening["traps"]
        assert len(traps) > 0

    def test_trap_line_has_move_explanations(self, session):
        """Test that trap_line contains move explanations"""
        res = session.get(f"{BASE_URL}/api/openings/italian-game")
        
        assert res.status_code == 200
        opening = res.json()["opening"]
        traps = opening["traps"]
        
        # Check first trap's trap_line
        trap = traps[0]
        trap_line = trap["trap_line"]
        
        assert len(trap_line) > 0
        for move_data in trap_line:
            assert "move" in move_data
            assert "explanation" in move_data
            assert len(move_data["move"]) > 0
            assert len(move_data["explanation"]) > 0


class TestOpeningsLibraryAPI:
    """Tests for openings library API"""

    @pytest.fixture
    def session(self):
        """Create a session with dev login authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate via dev login
        res = session.get(f"{BASE_URL}/api/auth/dev-login")
        if res.status_code != 200:
            pytest.skip("Dev login failed - skipping authenticated tests")
        
        return session

    def test_openings_library_returns_all_openings(self, session):
        """Test GET /api/openings/library returns opening list"""
        res = session.get(f"{BASE_URL}/api/openings/library")
        
        assert res.status_code == 200
        data = res.json()
        
        assert "openings" in data
        openings = data["openings"]
        
        # Should have multiple openings
        assert len(openings) > 5
        
        # Verify opening structure
        for opening in openings:
            assert "key" in opening
            assert "name" in opening
            assert "eco" in opening
            assert "color" in opening
            assert "description" in opening
            assert "trap_count" in opening

    def test_openings_library_includes_trap_counts(self, session):
        """Test that opening library includes trap counts"""
        res = session.get(f"{BASE_URL}/api/openings/library")
        
        assert res.status_code == 200
        openings = res.json()["openings"]
        
        # Italian Game should have traps
        italian = next((o for o in openings if o["key"] == "italian-game"), None)
        assert italian is not None
        assert italian["trap_count"] > 0
        
        # Sicilian should have traps
        sicilian = next((o for o in openings if o["key"] == "sicilian-defense"), None)
        assert sicilian is not None
        assert sicilian["trap_count"] > 0

    def test_opening_match_endpoint(self, session):
        """Test GET /api/openings/match finds correct library key"""
        # Test matching "Giuoco Piano" to "italian-game"
        res = session.get(f"{BASE_URL}/api/openings/match", params={"opening_name": "Giuoco Piano"})
        
        assert res.status_code == 200
        data = res.json()
        
        assert data["found"] == True
        assert data["library_key"] == "italian-game"

    def test_opening_match_by_eco(self, session):
        """Test GET /api/openings/match finds opening by ECO code"""
        res = session.get(f"{BASE_URL}/api/openings/match", params={"opening_name": "some opening", "eco": "C54"})
        
        assert res.status_code == 200
        data = res.json()
        
        # C54 is in Italian Game range
        assert data["found"] == True
        assert data["library_key"] == "italian-game"


class TestTrapSuggestAPI:
    """Tests for trap suggestion based on position"""

    @pytest.fixture
    def session(self):
        """Create a session with dev login authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate via dev login
        res = session.get(f"{BASE_URL}/api/auth/dev-login")
        if res.status_code != 200:
            pytest.skip("Dev login failed - skipping authenticated tests")
        
        return session

    def test_trap_suggest_finds_trap_from_position(self, session):
        """Test POST /api/traps/suggest finds available trap"""
        # Moves that lead to Fried Liver setup
        moves = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"]
        
        res = session.post(f"{BASE_URL}/api/traps/suggest", json=moves)
        
        assert res.status_code == 200
        data = res.json()
        
        # Should find the Fried Liver Attack opportunity
        assert data["trap_available"] == True
        assert data["trap"] is not None
        
        trap = data["trap"]
        assert trap["name"] is not None
        assert "opening_key" in trap

    def test_trap_suggest_no_trap_from_random_position(self, session):
        """Test POST /api/traps/suggest returns no trap for random moves"""
        # Random moves that don't match any trap setup
        moves = ["a3", "h6", "b3", "g6"]
        
        res = session.post(f"{BASE_URL}/api/traps/suggest", json=moves)
        
        assert res.status_code == 200
        data = res.json()
        
        # Should not find any trap
        assert data["trap_available"] == False
        assert data["trap"] is None

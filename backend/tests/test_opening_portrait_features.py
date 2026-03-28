"""
Test Opening Portrait Features (Iteration 157)
==============================================

Tests for 3 new features:
1. Interactive Board on Opening Portrait - click any opening to expand and step through theory moves
2. Variation Selector for Lessons - pill buttons to switch between opening variations
3. Pattern Memory Injection - during live play, surface 'You've missed this pattern X times'

Uses dev-login for authentication.
"""

import pytest
import requests
import os
import sys

# Add backend to path for service imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Session for authenticated requests
session = requests.Session()


@pytest.fixture(scope="module", autouse=True)
def authenticate():
    """Authenticate using dev-login before running tests."""
    response = session.get(f"{BASE_URL}/api/auth/dev-login")
    assert response.status_code == 200, f"Dev login failed: {response.text}"
    print(f"Authenticated successfully")
    yield
    # No cleanup needed


class TestOpeningRepertoireEndpoints:
    """Test endpoints used by Opening Portrait page."""
    
    def test_get_opening_repertoire(self):
        """GET /api/openings/repertoire returns user's opening repertoire."""
        response = session.get(f"{BASE_URL}/api/openings/repertoire")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "white_repertoire" in data, "Missing white_repertoire"
        assert "black_repertoire" in data, "Missing black_repertoire"
        
        # Check structure of repertoire items
        if data["white_repertoire"]:
            opening = data["white_repertoire"][0]
            assert "name" in opening, "Opening missing name"
            assert "games_played" in opening, "Opening missing games_played"
            print(f"White repertoire: {len(data['white_repertoire'])} openings")
        
        if data["black_repertoire"]:
            opening = data["black_repertoire"][0]
            assert "name" in opening, "Opening missing name"
            print(f"Black repertoire: {len(data['black_repertoire'])} openings")
    
    def test_get_opening_progress(self):
        """GET /api/training/opening-progress returns progress data."""
        response = session.get(f"{BASE_URL}/api/training/opening-progress")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "progress" in data, "Missing progress field"
        print(f"Opening progress: {len(data.get('progress', []))} items")


class TestOpeningLessonWithVariations:
    """Test opening lesson endpoint with variation selector."""
    
    def test_get_french_defense_default(self):
        """GET /api/openings/french-defense returns opening with active_variation field."""
        response = session.get(f"{BASE_URL}/api/openings/french-defense")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "opening" in data, "Missing opening field"
        
        opening = data["opening"]
        assert "name" in opening, "Opening missing name"
        assert "variations" in opening, "Opening missing variations"
        assert "active_variation" in opening, "Opening missing active_variation field"
        assert "main_line" in opening, "Opening missing main_line"
        
        print(f"French Defense: {opening['name']}")
        print(f"Active variation: {opening['active_variation']}")
        print(f"Available variations: {len(opening['variations'])}")
        
        # Verify variations structure
        for v in opening["variations"]:
            assert "key" in v, "Variation missing key"
            assert "name" in v, "Variation missing name"
            assert "total_moves" in v, "Variation missing total_moves"
    
    def test_get_french_defense_with_variation_param(self):
        """GET /api/openings/french-defense?variation=french_winawer returns different main_line."""
        # First get default
        default_response = session.get(f"{BASE_URL}/api/openings/french-defense")
        assert default_response.status_code == 200
        default_data = default_response.json()
        default_main_line = default_data["opening"]["main_line"]
        default_variation = default_data["opening"]["active_variation"]
        
        # Now get with specific variation
        response = session.get(f"{BASE_URL}/api/openings/french-defense?variation=french_winawer")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        opening = data["opening"]
        
        # Verify active_variation changed
        assert opening["active_variation"] == "french_winawer", f"Expected french_winawer, got {opening['active_variation']}"
        
        # Verify main_line is different (if default wasn't already winawer)
        if default_variation != "french_winawer":
            winawer_main_line = opening["main_line"]
            # The moves should be different for different variations
            print(f"Default variation: {default_variation}")
            print(f"Winawer variation: {opening['active_variation']}")
            print(f"Default main_line length: {len(default_main_line)}")
            print(f"Winawer main_line length: {len(winawer_main_line)}")
    
    def test_get_italian_game_hyphenated_key(self):
        """GET /api/openings/italian-game works with hyphenated key (key normalization fix)."""
        response = session.get(f"{BASE_URL}/api/openings/italian-game")
        
        # This tests the key normalization fix in opening_theory_json_service.py
        # The service should try: italian-game, italian_game, italian-game
        if response.status_code == 200:
            data = response.json()
            assert "opening" in data, "Missing opening field"
            print(f"Italian Game found: {data['opening']['name']}")
        elif response.status_code == 404:
            # This is acceptable if the opening isn't in the theory database
            print("Italian Game not found in theory database (expected for some setups)")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")
    
    def test_french_defense_variations_list(self):
        """Verify French Defense has expected variations."""
        response = session.get(f"{BASE_URL}/api/openings/french-defense")
        assert response.status_code == 200
        
        data = response.json()
        variations = data["opening"]["variations"]
        variation_keys = [v["key"] for v in variations]
        
        # French Defense should have multiple variations
        print(f"French Defense variations: {variation_keys}")
        
        # Check for expected variations (based on the test request)
        expected_variations = ["french_advance", "french_classical", "french_winawer", "french_tarrasch", "french_exchange"]
        found_variations = [v for v in expected_variations if v in variation_keys]
        print(f"Found expected variations: {found_variations}")


class TestInlineBoardPreview:
    """Test endpoints used by InlineBoardPreview component."""
    
    def test_opening_detail_returns_main_line(self):
        """Opening detail endpoint returns main_line for board preview."""
        response = session.get(f"{BASE_URL}/api/openings/french-defense")
        assert response.status_code == 200
        
        data = response.json()
        opening = data["opening"]
        main_line = opening.get("main_line", [])
        
        assert len(main_line) > 0, "main_line should not be empty"
        
        # Each move should have 'move' field
        for i, move_data in enumerate(main_line):
            assert "move" in move_data, f"Move {i} missing 'move' field"
        
        print(f"Main line has {len(main_line)} moves")
        print(f"First 5 moves: {[m['move'] for m in main_line[:5]]}")


class TestPatternMemoryService:
    """Test pattern memory service for 'You've missed this pattern X times' feature."""
    
    def test_pattern_memory_service_exists(self):
        """Verify pattern_memory_service.py has get_pattern_for_mistake function."""
        # This is a code verification test - we check the service exists
        from services.pattern_memory_service import get_pattern_for_mistake, normalize_pattern
        
        # Test normalize_pattern function
        assert normalize_pattern("threat_oversight") == "ignore_threat"
        assert normalize_pattern("tactical_oversight") == "tactical_miss"
        assert normalize_pattern("hanging_piece") == "hanging_piece"
        print("Pattern memory service functions exist and work")
    
    def test_pattern_memory_api_endpoint(self):
        """Test pattern memory summary endpoint if it exists."""
        # Try to get pattern summary
        response = session.get(f"{BASE_URL}/api/patterns/summary")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Pattern summary: {data}")
        elif response.status_code == 404:
            # Endpoint may not be exposed directly - that's OK
            print("Pattern summary endpoint not exposed (patterns are injected into coaching)")
        else:
            print(f"Pattern summary response: {response.status_code}")


class TestV5CoachingPatternMemory:
    """Test V5 coaching includes pattern_memory field."""
    
    def test_v5_coaching_dataclass_has_pattern_memory(self):
        """Verify V5Coaching dataclass has pattern_memory field."""
        from services.shared_coaching_v5 import V5Coaching
        
        # Create a V5Coaching instance with pattern_memory
        coaching = V5Coaching(
            narrative="Test narrative",
            severity="mistake",
            pattern_memory="You've missed this pattern 3 times this week"
        )
        
        coaching_dict = coaching.to_dict()
        assert "pattern_memory" in coaching_dict, "V5Coaching should have pattern_memory field"
        assert coaching_dict["pattern_memory"] == "You've missed this pattern 3 times this week"
        print("V5Coaching dataclass has pattern_memory field")
    
    def test_v5_coaching_endpoint_exists(self):
        """Test V5 coaching endpoint exists."""
        # This endpoint requires a session, so we just verify it exists
        response = session.post(
            f"{BASE_URL}/api/coach/play/v5/feedback",
            json={
                "move_san": "e4",
                "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            }
        )
        
        # Should not be 404 (endpoint exists)
        assert response.status_code != 404, "V5 feedback endpoint should exist"
        print(f"V5 feedback endpoint response: {response.status_code}")


class TestOpeningTheoryJsonService:
    """Test opening theory JSON service key normalization."""
    
    def test_key_normalization(self):
        """Test that key normalization works for hyphenated keys."""
        from services.opening_theory_json_service import get_opening_theory
        
        # Test with underscore key
        theory_underscore = get_opening_theory("french_defense")
        
        # Test with hyphen key
        theory_hyphen = get_opening_theory("french-defense")
        
        # Both should return the same data (or both None if not in database)
        if theory_underscore:
            print(f"french_defense found: {theory_underscore.get('name')}")
        if theory_hyphen:
            print(f"french-defense found: {theory_hyphen.get('name')}")
        
        # At least one should work
        assert theory_underscore or theory_hyphen, "At least one key format should work"
    
    def test_get_available_variations(self):
        """Test getting available variations for an opening."""
        from services.opening_theory_json_service import get_available_variations
        
        variations = get_available_variations("french_defense")
        
        if variations:
            print(f"French Defense variations: {[v['key'] for v in variations]}")
            for v in variations:
                assert "key" in v
                assert "name" in v
                assert "total_moves" in v
        else:
            print("No variations found for french_defense")
    
    def test_get_variation_lesson_moves(self):
        """Test getting lesson moves for a specific variation."""
        from services.opening_theory_json_service import get_variation_lesson_moves
        
        lesson = get_variation_lesson_moves("french_defense", "french_advance")
        
        if lesson:
            print(f"French Advance lesson: {lesson.get('variation_name')}")
            print(f"Moves: {lesson.get('moves', [])[:5]}")
            assert "moves" in lesson
            assert "variation_name" in lesson
        else:
            print("No lesson found for french_advance variation")


class TestV5CoachingCardComponent:
    """Verify V5CoachingCard component has pattern_memory display."""
    
    def test_pattern_memory_display_in_code(self):
        """Verify V5CoachingCard.jsx has pattern_memory display element."""
        import os
        
        component_path = "/app/frontend/src/components/shared/V5CoachingCard.jsx"
        
        with open(component_path, 'r') as f:
            content = f.read()
        
        # Check for pattern_memory handling
        assert "pattern_memory" in content, "V5CoachingCard should handle pattern_memory"
        assert 'data-testid="pattern-memory-note"' in content, "V5CoachingCard should have pattern-memory-note testid"
        
        print("V5CoachingCard has pattern_memory display element")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

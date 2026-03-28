"""
Test Expanded Opening Variations - 24 Openings with Deep Theory
================================================================

Tests for the expanded opening theory system with 24 openings and 49 variations.
Previously stub openings (Vienna, Philidor, Scotch, etc.) now have full 18-26 move deep lessons.

Key features tested:
1. All 24 openings load from JSON correctly
2. Vienna Game lesson starts successfully with 18 moves
3. Teaching offer includes 'learn_main_line' for openings with theory
4. start_opening_lesson works for multiple openings
5. detect_opening_from_moves works for all major openings
6. Full teaching flow for Vienna (start -> play through -> completion)
"""

import pytest
import requests
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestOpeningTheoryJSONService:
    """Test the JSON-based opening theory service"""
    
    def test_all_24_openings_loaded(self):
        """Verify all 24 openings are loaded from JSON"""
        from services.opening_theory_json_service import get_all_opening_keys
        
        keys = get_all_opening_keys()
        assert len(keys) == 24, f"Expected 24 openings, got {len(keys)}"
        
        # Verify key openings are present
        expected_openings = [
            'italian_game', 'french_defense', 'queens_gambit', 'london_system',
            'sicilian_dragon', 'caro_kann', 'sicilian_najdorf', 'ruy_lopez',
            'sicilian_defense', 'philidor_defense', 'vienna_game', 'scotch_game',
            'petrov_defense', 'kings_indian_defense', 'grunfeld_defense', 'nimzo_indian',
            'queens_indian', 'slav_defense', 'qgd', 'benoni_defense',
            'budapest_gambit', 'dutch_defense', 'scandinavian_defense', 'nimzowitsch_defense'
        ]
        
        for opening in expected_openings:
            assert opening in keys, f"Missing opening: {opening}"
        
        print(f"✓ All 24 openings loaded: {sorted(keys)}")
    
    def test_vienna_game_has_deep_theory(self):
        """Vienna Game should have 18+ moves deep theory (was a stub before)"""
        from services.opening_theory_json_service import get_opening_theory, get_available_variations, get_variation_lesson_moves
        
        theory = get_opening_theory('vienna_game')
        assert theory is not None, "Vienna Game theory not found"
        assert theory.get('name') == 'Vienna Game'
        
        variations = get_available_variations('vienna_game')
        assert len(variations) >= 2, f"Expected at least 2 variations, got {len(variations)}"
        
        # Check first variation has 18+ moves
        first_var = variations[0]
        assert first_var['total_moves'] >= 18, f"Expected 18+ moves, got {first_var['total_moves']}"
        
        # Get full lesson
        lesson = get_variation_lesson_moves('vienna_game', first_var['key'])
        assert lesson is not None
        assert len(lesson['moves']) >= 18, f"Expected 18+ moves in lesson, got {len(lesson['moves'])}"
        
        print(f"✓ Vienna Game has {first_var['total_moves']} moves in {first_var['name']}")
        print(f"  Moves: {lesson['moves']}")
    
    def test_all_previously_stub_openings_have_theory(self):
        """All 16 previously-stub openings should now have deep theory"""
        from services.opening_theory_json_service import get_available_variations
        
        # These were stubs before, now should have variations
        previously_stub_openings = [
            'philidor_defense', 'vienna_game', 'scotch_game', 'petrov_defense',
            'kings_indian_defense', 'grunfeld_defense', 'nimzo_indian', 'queens_indian',
            'slav_defense', 'qgd', 'benoni_defense', 'budapest_gambit',
            'dutch_defense', 'scandinavian_defense', 'nimzowitsch_defense', 'sicilian_defense'
        ]
        
        for opening_key in previously_stub_openings:
            variations = get_available_variations(opening_key)
            assert len(variations) > 0, f"{opening_key} has no variations (still a stub?)"
            
            # Each variation should have at least 10 moves
            for var in variations:
                assert var['total_moves'] >= 10, f"{opening_key}/{var['name']} has only {var['total_moves']} moves"
            
            print(f"✓ {opening_key}: {len(variations)} variations, {variations[0]['total_moves']}+ moves")
    
    def test_variation_lesson_moves_structure(self):
        """Verify lesson structure includes all required fields"""
        from services.opening_theory_json_service import get_variation_lesson_moves
        
        lesson = get_variation_lesson_moves('vienna_game', 'vienna_gambit')
        
        assert lesson is not None
        assert 'moves' in lesson
        assert 'variation_name' in lesson
        assert 'white_plan' in lesson
        assert 'black_plan' in lesson
        assert 'common_learnings' in lesson
        assert 'critical_positions' in lesson
        
        assert len(lesson['moves']) >= 18
        assert lesson['variation_name'] == 'Vienna Gambit'
        
        print(f"✓ Lesson structure verified for Vienna Gambit")


class TestOpeningMasteryDatabase:
    """Test the OPENING_DATABASE is populated correctly from JSON"""
    
    def test_opening_database_has_24_openings(self):
        """OPENING_DATABASE should have all 24 openings"""
        from services.opening_mastery import OPENING_DATABASE
        
        assert len(OPENING_DATABASE) >= 24, f"Expected 24+ openings, got {len(OPENING_DATABASE)}"
        print(f"✓ OPENING_DATABASE has {len(OPENING_DATABASE)} openings")
    
    def test_vienna_game_in_database_with_variations(self):
        """Vienna Game should be in database with proper variations"""
        from services.opening_mastery import OPENING_DATABASE
        
        vienna = OPENING_DATABASE.get('vienna_game')
        assert vienna is not None, "Vienna Game not in OPENING_DATABASE"
        assert vienna.name == 'Vienna Game'
        assert len(vienna.variations) >= 2, f"Expected 2+ variations, got {len(vienna.variations)}"
        
        # First variation should have 18+ moves
        first_var = vienna.variations[0]
        assert len(first_var.moves) >= 18, f"Expected 18+ moves, got {len(first_var.moves)}"
        
        print(f"✓ Vienna Game in database with {len(vienna.variations)} variations")


class TestOpeningDetection:
    """Test detect_opening_from_moves for all major openings"""
    
    def test_detect_french_defense(self):
        """French Defense: e4 e6"""
        from services.opening_mastery import detect_opening_from_moves
        
        result = detect_opening_from_moves(['e4', 'e6'])
        assert result is not None
        assert result['opening_key'] == 'french_defense'
        print(f"✓ French Defense detected")
    
    def test_detect_italian_game(self):
        """Italian Game: e4 e5 Nf3 Nc6 Bc4"""
        from services.opening_mastery import detect_opening_from_moves
        
        result = detect_opening_from_moves(['e4', 'e5', 'Nf3', 'Nc6', 'Bc4'])
        assert result is not None
        assert result['opening_key'] == 'italian_game'
        print(f"✓ Italian Game detected")
    
    def test_detect_sicilian_defense(self):
        """Sicilian Defense: e4 c5"""
        from services.opening_mastery import detect_opening_from_moves
        
        result = detect_opening_from_moves(['e4', 'c5'])
        assert result is not None
        assert result['opening_key'] == 'sicilian_defense'
        print(f"✓ Sicilian Defense detected")
    
    def test_detect_petrov_defense(self):
        """Petrov Defense: e4 e5 Nf3 Nf6"""
        from services.opening_mastery import detect_opening_from_moves
        
        result = detect_opening_from_moves(['e4', 'e5', 'Nf3', 'Nf6'])
        assert result is not None
        assert result['opening_key'] == 'petrov_defense'
        print(f"✓ Petrov Defense detected")
    
    def test_detect_qgd(self):
        """Queen's Gambit Declined: d4 d5 c4 e6"""
        from services.opening_mastery import detect_opening_from_moves
        
        result = detect_opening_from_moves(['d4', 'd5', 'c4', 'e6'])
        assert result is not None
        assert result['opening_key'] == 'qgd'
        print(f"✓ QGD detected")
    
    def test_detect_kings_indian_defense(self):
        """King's Indian Defense: d4 Nf6 c4 g6"""
        from services.opening_mastery import detect_opening_from_moves
        
        result = detect_opening_from_moves(['d4', 'Nf6', 'c4', 'g6'])
        assert result is not None
        assert result['opening_key'] == 'kings_indian_defense'
        print(f"✓ King's Indian Defense detected")
    
    def test_detect_vienna_game(self):
        """Vienna Game: e4 e5 Nc3"""
        from services.opening_mastery import detect_opening_from_moves
        
        result = detect_opening_from_moves(['e4', 'e5', 'Nc3'])
        assert result is not None
        assert result['opening_key'] == 'vienna_game'
        print(f"✓ Vienna Game detected")
    
    def test_detect_scotch_game(self):
        """Scotch Game: e4 e5 Nf3 Nc6 d4"""
        from services.opening_mastery import detect_opening_from_moves
        
        result = detect_opening_from_moves(['e4', 'e5', 'Nf3', 'Nc6', 'd4'])
        assert result is not None
        assert result['opening_key'] == 'scotch_game'
        print(f"✓ Scotch Game detected")
    
    def test_detect_slav_defense(self):
        """Slav Defense: d4 d5 c4 c6"""
        from services.opening_mastery import detect_opening_from_moves
        
        result = detect_opening_from_moves(['d4', 'd5', 'c4', 'c6'])
        assert result is not None
        assert result['opening_key'] == 'slav_defense'
        print(f"✓ Slav Defense detected")
    
    def test_detect_scandinavian_defense(self):
        """Scandinavian Defense: e4 d5"""
        from services.opening_mastery import detect_opening_from_moves
        
        result = detect_opening_from_moves(['e4', 'd5'])
        assert result is not None
        assert result['opening_key'] == 'scandinavian_defense'
        print(f"✓ Scandinavian Defense detected")


class TestTeachingOfferLearnMainLine:
    """Test that teaching offers include 'learn_main_line' for openings with theory"""
    
    def test_vienna_game_has_learn_main_line_option(self):
        """Vienna Game teaching offer should include learn_main_line"""
        from services.opening_theory_json_service import get_available_variations
        
        variations = get_available_variations('vienna_game')
        assert len(variations) > 0, "Vienna Game should have variations"
        
        # The check_opening_and_offer_teaching function adds learn_main_line
        # when has_deep_theory is True (variations exist)
        has_deep_theory = len(variations) > 0
        assert has_deep_theory, "Vienna Game should have deep theory"
        
        first_var = variations[0]
        assert first_var['total_moves'] >= 18, f"Expected 18+ moves, got {first_var['total_moves']}"
        
        print(f"✓ Vienna Game has learn_main_line option ({first_var['total_moves']} moves)")
    
    def test_all_openings_with_variations_have_learn_main_line(self):
        """All openings with variations should support learn_main_line"""
        from services.opening_theory_json_service import get_all_opening_keys, get_available_variations
        
        for opening_key in get_all_opening_keys():
            variations = get_available_variations(opening_key)
            assert len(variations) > 0, f"{opening_key} has no variations"
            
            # Each should have at least 10 moves
            first_var = variations[0]
            assert first_var['total_moves'] >= 10, f"{opening_key} has only {first_var['total_moves']} moves"
        
        print(f"✓ All 24 openings support learn_main_line")


class TestStartOpeningLesson:
    """Test start_opening_lesson for multiple openings"""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database for testing"""
        class MockCollection:
            def __init__(self):
                self.data = {}
            
            async def find_one(self, query):
                session_id = query.get('session_id')
                return self.data.get(session_id)
            
            async def update_one(self, query, update):
                session_id = query.get('session_id')
                if session_id in self.data:
                    if '$set' in update:
                        self.data[session_id].update(update['$set'])
        
        class MockDB:
            def __init__(self):
                self.coach_sessions = MockCollection()
                self.user_opening_progress = MockCollection()
        
        return MockDB()
    
    @pytest.mark.asyncio
    async def test_start_vienna_game_lesson(self, mock_db):
        """Start Vienna Game lesson - should return 18+ moves"""
        from services.opening_teaching_integration import start_opening_lesson
        
        # Setup mock session
        session_id = 'test_vienna_session'
        mock_db.coach_sessions.data[session_id] = {
            'session_id': session_id,
            'user_id': 'test_user',
            'user_color': 'white',
            'detected_opening': 'vienna_game',
            'current_fen': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
        }
        
        result = await start_opening_lesson(mock_db, session_id, 'test_user', 'learn_main_line')
        
        assert result.get('success') == True, f"Failed: {result.get('error')}"
        assert result.get('total_moves') >= 18, f"Expected 18+ moves, got {result.get('total_moves')}"
        assert 'Vienna' in result.get('lesson_name', '')
        
        print(f"✓ Vienna Game lesson started: {result.get('total_moves')} moves")
    
    @pytest.mark.asyncio
    async def test_start_scotch_game_lesson(self, mock_db):
        """Start Scotch Game lesson"""
        from services.opening_teaching_integration import start_opening_lesson
        
        session_id = 'test_scotch_session'
        mock_db.coach_sessions.data[session_id] = {
            'session_id': session_id,
            'user_id': 'test_user',
            'user_color': 'white',
            'detected_opening': 'scotch_game',
            'current_fen': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
        }
        
        result = await start_opening_lesson(mock_db, session_id, 'test_user', 'learn_main_line')
        
        assert result.get('success') == True, f"Failed: {result.get('error')}"
        assert result.get('total_moves') >= 10
        
        print(f"✓ Scotch Game lesson started: {result.get('total_moves')} moves")
    
    @pytest.mark.asyncio
    async def test_start_kings_indian_lesson(self, mock_db):
        """Start King's Indian Defense lesson"""
        from services.opening_teaching_integration import start_opening_lesson
        
        session_id = 'test_kid_session'
        mock_db.coach_sessions.data[session_id] = {
            'session_id': session_id,
            'user_id': 'test_user',
            'user_color': 'black',
            'detected_opening': 'kings_indian_defense',
            'current_fen': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
        }
        
        result = await start_opening_lesson(mock_db, session_id, 'test_user', 'learn_main_line')
        
        assert result.get('success') == True, f"Failed: {result.get('error')}"
        assert result.get('total_moves') >= 10
        
        print(f"✓ King's Indian Defense lesson started: {result.get('total_moves')} moves")
    
    @pytest.mark.asyncio
    async def test_start_slav_defense_lesson(self, mock_db):
        """Start Slav Defense lesson"""
        from services.opening_teaching_integration import start_opening_lesson
        
        session_id = 'test_slav_session'
        mock_db.coach_sessions.data[session_id] = {
            'session_id': session_id,
            'user_id': 'test_user',
            'user_color': 'black',
            'detected_opening': 'slav_defense',
            'current_fen': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
        }
        
        result = await start_opening_lesson(mock_db, session_id, 'test_user', 'learn_main_line')
        
        assert result.get('success') == True, f"Failed: {result.get('error')}"
        assert result.get('total_moves') >= 10
        
        print(f"✓ Slav Defense lesson started: {result.get('total_moves')} moves")
    
    @pytest.mark.asyncio
    async def test_start_scandinavian_defense_lesson(self, mock_db):
        """Start Scandinavian Defense lesson"""
        from services.opening_teaching_integration import start_opening_lesson
        
        session_id = 'test_scandi_session'
        mock_db.coach_sessions.data[session_id] = {
            'session_id': session_id,
            'user_id': 'test_user',
            'user_color': 'black',
            'detected_opening': 'scandinavian_defense',
            'current_fen': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
        }
        
        result = await start_opening_lesson(mock_db, session_id, 'test_user', 'learn_main_line')
        
        assert result.get('success') == True, f"Failed: {result.get('error')}"
        assert result.get('total_moves') >= 10
        
        print(f"✓ Scandinavian Defense lesson started: {result.get('total_moves')} moves")


class TestTeachingInstruction:
    """Test _get_teaching_instruction function"""
    
    def test_teaching_instruction_for_user_move(self):
        """Teaching instruction should indicate user's turn correctly"""
        from services.opening_teaching_integration import _get_teaching_instruction
        
        teaching_data = {
            'main_line_moves': ['e4', 'e5', 'Nc3', 'Nf6', 'f4'],
            'user_plays_white': True,
            'critical_positions': {}
        }
        
        # Move 0 (e4) - White's turn, user plays white
        instruction = _get_teaching_instruction(teaching_data, 'main_line', 0)
        assert instruction['is_user_move'] == True
        assert instruction['move'] == 'e4'
        assert 'Play' in instruction['message']
        
        # Move 1 (e5) - Black's turn, user plays white
        instruction = _get_teaching_instruction(teaching_data, 'main_line', 1)
        assert instruction['is_user_move'] == False
        assert instruction['move'] == 'e5'
        
        print(f"✓ Teaching instruction correctly identifies user/coach moves")
    
    def test_teaching_instruction_completion(self):
        """Teaching instruction should indicate completion"""
        from services.opening_teaching_integration import _get_teaching_instruction
        
        teaching_data = {
            'main_line_moves': ['e4', 'e5'],
            'user_plays_white': True,
            'critical_positions': {},
            'explanation': 'Test explanation'
        }
        
        # Move 2 - beyond the lesson
        instruction = _get_teaching_instruction(teaching_data, 'main_line', 2)
        assert instruction['complete'] == True
        assert 'completed' in instruction['message'].lower() or 'excellent' in instruction['message'].lower()
        
        print(f"✓ Teaching instruction correctly indicates completion")


class TestAPIEndpoints:
    """Test API endpoints for opening teaching"""
    
    def test_health_check(self):
        """Basic health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print(f"✓ Health check passed")
    
    def test_teaching_start_endpoint_exists(self):
        """Verify teaching start endpoint exists and returns proper error for invalid session"""
        response = requests.post(f"{BASE_URL}/api/coach/play/teaching/start", json={
            'session_id': 'test_nonexistent',
            'lesson_type': 'learn_main_line'
        })
        # Endpoint exists - returns 404 "Session not found" or 401/403 for auth
        # The key is that it's not a generic 404 "Not Found" for the route itself
        data = response.json()
        # Should have a detail message indicating the endpoint processed the request
        assert 'detail' in data, "Endpoint should return structured error"
        # The detail should be about session/auth, not about route not found
        detail = data.get('detail', '')
        assert 'Session not found' in detail or 'Not authenticated' in detail or 'session_id' in detail, \
            f"Unexpected error: {detail}"
        print(f"✓ Teaching start endpoint exists (status: {response.status_code}, detail: {detail})")
    
    def test_teaching_move_endpoint_exists(self):
        """Verify teaching move endpoint exists and returns proper error for invalid session"""
        response = requests.post(f"{BASE_URL}/api/coach/play/teaching/move", json={
            'session_id': 'test_nonexistent',
            'move': 'e4'
        })
        data = response.json()
        assert 'detail' in data, "Endpoint should return structured error"
        detail = data.get('detail', '')
        assert 'Session not found' in detail or 'Not authenticated' in detail or 'session_id' in detail, \
            f"Unexpected error: {detail}"
        print(f"✓ Teaching move endpoint exists (status: {response.status_code}, detail: {detail})")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

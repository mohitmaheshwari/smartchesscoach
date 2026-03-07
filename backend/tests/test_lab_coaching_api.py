"""
Tests for Lab API - Coaching Data Structure
Tests that the Lab API returns proper data for coaching features
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://chess-growth-hub.preview.emergentagent.com').rstrip('/')

# Test game - a LOSS game (user played black, result is 1-0)
LOSS_GAME_ID = '42932bfa-24e8-4aff-9068-0b476cb6f4fc'


class TestLabAPIStructure:
    """Tests for Lab API data structure"""
    
    def test_lab_api_returns_valid_response(self):
        """GET /api/lab/{game_id} should return a valid response"""
        response = requests.get(
            f"{BASE_URL}/api/lab/{LOSS_GAME_ID}",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Core fields should exist
        assert 'analysis' in data or 'core_lesson' in data
    
    def test_lab_api_includes_wisdom_lessons(self):
        """Lab API should include wisdom_lessons for teaching moments"""
        response = requests.get(
            f"{BASE_URL}/api/lab/{LOSS_GAME_ID}",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # wisdom_lessons should be present
        assert 'wisdom_lessons' in data, "wisdom_lessons field missing"
        
        wisdom = data['wisdom_lessons']
        assert isinstance(wisdom, list)
        
        # If lessons exist, verify structure
        if len(wisdom) > 0:
            lesson = wisdom[0]
            assert 'move_number' in lesson
            assert 'concept' in lesson
            assert 'your_move' in lesson
            assert 'better_move' in lesson
            assert 'rule' in lesson
    
    def test_lab_api_includes_pattern_context(self):
        """Lab API should include pattern_context for recurring patterns"""
        response = requests.get(
            f"{BASE_URL}/api/lab/{LOSS_GAME_ID}",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # pattern_context should be present for coaching connection
        assert 'pattern_context' in data, "pattern_context field missing"
    
    def test_lab_api_includes_core_lesson(self):
        """Lab API should include core_lesson for main teaching point"""
        response = requests.get(
            f"{BASE_URL}/api/lab/{LOSS_GAME_ID}",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # core_lesson should be present
        assert 'core_lesson' in data, "core_lesson field missing"
        
        if data['core_lesson']:
            lesson = data['core_lesson']
            # Should have lesson text or pattern identifier
            has_lesson = 'lesson' in lesson or 'pattern' in lesson
            assert has_lesson, "core_lesson should have 'lesson' or 'pattern' field"


class TestHomeIntelligenceForLabIntegration:
    """Tests for home-intelligence API that Lab page fetches"""
    
    def test_home_intelligence_returns_specific_patterns(self):
        """home-intelligence API should return specific_patterns for coaching intro"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data'):
            assert 'specific_patterns' in data
            
            patterns = data['specific_patterns']
            if patterns.get('has_pattern'):
                # Verify pattern count exists (e.g., "27 times")
                assert 'pattern_count' in patterns
                assert isinstance(patterns['pattern_count'], int)
                assert patterns['pattern_count'] > 0
                
                # Verify pattern description exists
                assert 'pattern_description' in patterns
                assert isinstance(patterns['pattern_description'], str)
                assert len(patterns['pattern_description']) > 5
    
    def test_home_intelligence_returns_progress_trend(self):
        """home-intelligence API should return progress_trend for encouragement context"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data'):
            assert 'progress_trend' in data
            
            trend = data['progress_trend']
            # Should have message for user encouragement
            assert 'message' in trend
            assert isinstance(trend['message'], str)
            assert len(trend['message']) > 10


class TestGameDataForLabFeatures:
    """Tests for game data that affects Lab page features"""
    
    def test_game_api_returns_result_for_loss_detection(self):
        """Game API should return result field for win/loss detection"""
        response = requests.get(
            f"{BASE_URL}/api/games/{LOSS_GAME_ID}",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Result field is needed to determine if game is loss
        assert 'result' in data, "result field missing"
        assert data['result'] in ['1-0', '0-1', '1/2-1/2'], f"Invalid result: {data['result']}"
        
        # For our test game, result should be 1-0 (white won, user lost as black)
        assert data['result'] == '1-0'
    
    def test_game_api_returns_user_color(self):
        """Game API should return user_color for correct perspective"""
        response = requests.get(
            f"{BASE_URL}/api/games/{LOSS_GAME_ID}",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # user_color is needed to determine if loss
        assert 'user_color' in data, "user_color field missing"
        assert data['user_color'] in ['white', 'black']
        
        # For our test game, user played black
        assert data['user_color'] == 'black'
    
    def test_game_is_correctly_identified_as_loss(self):
        """Verify the test game is correctly identified as a LOSS"""
        response = requests.get(
            f"{BASE_URL}/api/games/{LOSS_GAME_ID}",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        result = data.get('result')
        user_color = data.get('user_color')
        
        # Loss formula: (result == "1-0" && user_color == "black") || (result == "0-1" && user_color == "white")
        is_loss = (result == "1-0" and user_color == "black") or (result == "0-1" and user_color == "white")
        
        assert is_loss, f"Game should be a LOSS but got result={result}, user_color={user_color}"


class TestAnalysisDataForMilestones:
    """Tests for analysis data used in Milestones tab"""
    
    def test_analysis_includes_move_evaluations(self):
        """Analysis API should include move_evaluations for milestones"""
        response = requests.get(
            f"{BASE_URL}/api/analysis/{LOSS_GAME_ID}",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # stockfish_analysis should have move_evaluations
        assert 'stockfish_analysis' in data
        sf = data['stockfish_analysis']
        assert 'move_evaluations' in sf
        
        evals = sf['move_evaluations']
        assert isinstance(evals, list)
        assert len(evals) > 0, "Should have move evaluations"
        
        # Each evaluation should have key fields
        first_eval = evals[0]
        assert 'move_number' in first_eval
        assert 'move' in first_eval
    
    def test_analysis_includes_blunders_and_mistakes(self):
        """Analysis should include blunder/mistake counts for display"""
        response = requests.get(
            f"{BASE_URL}/api/analysis/{LOSS_GAME_ID}",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        sf = data.get('stockfish_analysis', {})
        
        # Check for blunder/mistake counts
        has_blunders = 'blunders' in sf or 'blunders' in data
        has_mistakes = 'mistakes' in sf or 'mistakes' in data
        
        # At least one count method should be present
        assert has_blunders or has_mistakes, "Should have blunder/mistake counts"

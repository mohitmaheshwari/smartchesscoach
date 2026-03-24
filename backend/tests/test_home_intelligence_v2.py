"""
Tests for Coach Home Intelligence V2 API - specific_patterns, progress_trend, last_session
Tests the new data-driven insights for the 95/100 home page experience.
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://deep-move-analysis.preview.emergentagent.com').rstrip('/')


class TestHomeIntelligenceV2SpecificPatterns:
    """Tests for specific_patterns field in /api/coach/home-intelligence"""
    
    def test_home_intelligence_includes_specific_patterns_field(self):
        """GET /api/coach/home-intelligence should include specific_patterns field"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data'):
            assert 'specific_patterns' in data, "specific_patterns field missing from home-intelligence response"
    
    def test_specific_patterns_structure_when_has_pattern(self):
        """When specific_patterns.has_pattern is true, should have required fields"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data') and data.get('specific_patterns', {}).get('has_pattern'):
            patterns = data['specific_patterns']
            
            # Required fields when has_pattern is true
            assert 'dominant_pattern' in patterns, "dominant_pattern missing"
            assert 'pattern_count' in patterns, "pattern_count missing"
            assert 'pattern_description' in patterns, "pattern_description missing"
            assert 'total_mistakes' in patterns, "total_mistakes missing"
            
            # Type checks
            assert isinstance(patterns['dominant_pattern'], str)
            assert isinstance(patterns['pattern_count'], int)
            assert isinstance(patterns['pattern_description'], str)
            assert patterns['pattern_count'] > 0, "pattern_count should be positive"
    
    def test_specific_patterns_has_all_patterns_dict(self):
        """specific_patterns should include all_patterns breakdown"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data') and data.get('specific_patterns', {}).get('has_pattern'):
            patterns = data['specific_patterns']
            
            assert 'all_patterns' in patterns, "all_patterns missing"
            assert isinstance(patterns['all_patterns'], dict)
    
    def test_specific_patterns_valid_dominant_patterns(self):
        """dominant_pattern should be one of the expected pattern types"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data') and data.get('specific_patterns', {}).get('has_pattern'):
            valid_patterns = [
                'missed_threat',
                'walked_into_fork', 
                'walked_into_pin',
                'left_piece_hanging',
                'missed_tactic',
                'calculation_error',
                'positional_drift'
            ]
            
            dominant = data['specific_patterns']['dominant_pattern']
            assert dominant in valid_patterns, f"Invalid dominant_pattern: {dominant}"


class TestHomeIntelligenceV2ProgressTrend:
    """Tests for progress_trend field in /api/coach/home-intelligence"""
    
    def test_home_intelligence_includes_progress_trend_field(self):
        """GET /api/coach/home-intelligence should include progress_trend field"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data'):
            assert 'progress_trend' in data, "progress_trend field missing from home-intelligence response"
    
    def test_progress_trend_structure_when_has_trend(self):
        """When progress_trend.has_trend is true, should have required fields"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data') and data.get('progress_trend', {}).get('has_trend'):
            trend = data['progress_trend']
            
            # Required fields when has_trend is true
            assert 'trend' in trend, "trend field missing"
            assert 'blunder_delta' in trend, "blunder_delta missing"
            assert 'message' in trend, "message missing"
            
            # trend should be one of three values
            assert trend['trend'] in ['improving', 'stable', 'declining'], f"Invalid trend: {trend['trend']}"
            
            # blunder_delta should be a number
            assert isinstance(trend['blunder_delta'], (int, float))
    
    def test_progress_trend_message_is_human_readable(self):
        """progress_trend.message should be a non-empty string"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data') and data.get('progress_trend', {}).get('has_trend'):
            message = data['progress_trend']['message']
            assert isinstance(message, str), "message should be a string"
            assert len(message) > 10, "message should be human-readable (>10 chars)"
    
    def test_progress_trend_includes_blunder_averages(self):
        """progress_trend should include recent and previous blunder averages"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data') and data.get('progress_trend', {}).get('has_trend'):
            trend = data['progress_trend']
            
            assert 'recent_blunders_avg' in trend
            assert 'previous_blunders_avg' in trend
            assert isinstance(trend['recent_blunders_avg'], (int, float))
            assert isinstance(trend['previous_blunders_avg'], (int, float))


class TestHomeIntelligenceV2LastSession:
    """Tests for last_session field in /api/coach/home-intelligence"""
    
    def test_home_intelligence_includes_last_session_field(self):
        """GET /api/coach/home-intelligence should include last_session field"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data'):
            assert 'last_session' in data, "last_session field missing from home-intelligence response"
    
    def test_last_session_structure_when_has_session(self):
        """When last_session.has_session is true, should have required fields"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data') and data.get('last_session', {}).get('has_session'):
            session = data['last_session']
            
            # Required fields when has_session is true
            assert 'theme' in session, "theme missing"
            assert 'games_on_theme' in session, "games_on_theme missing"
            assert 'message' in session, "message missing"
            
            # Type checks
            assert isinstance(session['games_on_theme'], int)
            assert isinstance(session['message'], str)


class TestHomeIntelligenceV2GamesNeedingReflection:
    """Tests for games_needing_reflection field in /api/coach/home-intelligence"""
    
    def test_games_needing_reflection_structure(self):
        """games_needing_reflection should have expected game structure"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data') and data.get('games_needing_reflection'):
            games = data['games_needing_reflection']
            assert isinstance(games, list)
            
            for game in games:
                # Required fields for each game
                assert 'game_id' in game
                assert 'result' in game
                assert game['result'] in ['win', 'loss', 'draw']
                
                # Should have opponent info
                has_opponent = 'opponent_name' in game or 'opponent' in game
                assert has_opponent, "Game should have opponent info"
    
    def test_games_needing_reflection_includes_blunder_count(self):
        """games_needing_reflection should include blunders for each game"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data') and data.get('games_needing_reflection'):
            games = data['games_needing_reflection']
            
            for game in games:
                # blunders field should exist (can be 0)
                assert 'blunders' in game, f"Game {game.get('game_id')} missing blunders field"
                assert isinstance(game['blunders'], int)
                assert game['blunders'] >= 0
    
    def test_clean_win_detection(self):
        """Win with 0 blunders should be identifiable as clean win"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data') and data.get('games_needing_reflection'):
            games = data['games_needing_reflection']
            
            # Check if there's any clean win (win with 0 blunders)
            clean_wins = [g for g in games if g.get('result') == 'win' and g.get('blunders', 0) == 0]
            
            # Just verify structure is correct for detecting clean wins
            for game in clean_wins:
                assert game['result'] == 'win'
                assert game['blunders'] == 0
                # This is data the frontend uses to show trophy + "Clean win! Let's see what worked"


class TestHomeIntelligenceV2Integration:
    """Integration tests for all V2 fields working together"""
    
    def test_all_v2_fields_present_when_has_data(self):
        """When user has data, all V2 fields should be present"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data'):
            # All V2 fields should exist (even if empty/false)
            v2_fields = ['specific_patterns', 'progress_trend', 'last_session']
            for field in v2_fields:
                assert field in data, f"V2 field '{field}' missing from response"
    
    def test_response_structure_complete(self):
        """Complete response should have all required sections"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Base fields always required
        assert 'has_data' in data
        
        if data.get('has_data'):
            # Original fields
            required_fields = [
                'games_analyzed',
                'development_phase', 
                'focus_capacity',
                'active_advice',
                'recommended_drill',
                'stats',
                'games_needing_reflection'
            ]
            
            for field in required_fields:
                assert field in data, f"Required field '{field}' missing"
            
            # V2 fields
            v2_fields = ['specific_patterns', 'progress_trend', 'last_session']
            for field in v2_fields:
                assert field in data, f"V2 field '{field}' missing"

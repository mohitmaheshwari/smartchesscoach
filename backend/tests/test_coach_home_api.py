"""
Tests for Coach Home API endpoints - UX Overhaul
Tests /api/coach/home-intelligence, /api/coach/fresh-loss, and /api/coach/weekly-proof endpoints
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://chess-coach-debug.preview.emergentagent.com').rstrip('/')


class TestHomeIntelligenceAPI:
    """Tests for /api/coach/home-intelligence endpoint"""
    
    def test_home_intelligence_endpoint_returns_valid_response(self):
        """GET /api/coach/home-intelligence should return valid JSON"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Must have has_data field
        assert 'has_data' in data
        assert isinstance(data['has_data'], bool)
    
    def test_home_intelligence_with_data_returns_all_required_fields(self):
        """When has_data is true, should return all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data'):
            # Required fields when user has data
            assert 'games_analyzed' in data
            assert isinstance(data['games_analyzed'], int)
            assert data['games_analyzed'] >= 3
            
            # Development phase
            assert 'development_phase' in data
            phase = data['development_phase']
            assert 'phase_key' in phase
            assert 'phase_name' in phase
            assert 'description' in phase
            assert 'color' in phase
            assert 'icon' in phase
            
            # Focus capacity
            assert 'focus_capacity' in data
            capacity = data['focus_capacity']
            assert 'level' in capacity
            assert capacity['level'] in ['single', 'dual', 'multi']
            assert 'advice_count' in capacity
            assert 'message' in capacity
            
            # Active advice
            assert 'active_advice' in data
            advice = data['active_advice']
            assert 'primary' in advice
            assert isinstance(advice['primary'], str)
            
            # Recommended drill
            assert 'recommended_drill' in data
            drill = data['recommended_drill']
            assert 'title' in drill
            assert 'description' in drill
            assert 'type' in drill
    
    def test_home_intelligence_development_phase_keys_valid(self):
        """Development phase key should be one of the valid phases"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data'):
            valid_phases = [
                'tactical_discipline',
                'pattern_control',
                'calculation_depth',
                'positional_sense',
                'time_mastery',
                'advanced_refinement'
            ]
            assert data['development_phase']['phase_key'] in valid_phases
    
    def test_home_intelligence_stats_include_metrics(self):
        """Stats should include blunders_per_game and mistakes_per_game"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data'):
            assert 'stats' in data
            stats = data['stats']
            assert 'blunders_per_game' in stats
            assert 'mistakes_per_game' in stats
            assert isinstance(stats['blunders_per_game'], (int, float))
            assert isinstance(stats['mistakes_per_game'], (int, float))
    
    def test_home_intelligence_last_game_structure(self):
        """Last game should have expected structure when present"""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('has_data') and data.get('last_game'):
            last_game = data['last_game']
            assert 'game_id' in last_game
            assert 'result' in last_game
            assert 'blunders' in last_game
            assert 'mistakes' in last_game
            assert 'is_new' in last_game
            assert isinstance(last_game['is_new'], bool)


class TestCoachFreshLossAPI:
    """Tests for /api/coach/fresh-loss endpoint"""
    
    def test_fresh_loss_endpoint_returns_valid_response(self):
        """GET /api/coach/fresh-loss should return valid JSON with has_fresh_loss field"""
        response = requests.get(
            f"{BASE_URL}/api/coach/fresh-loss",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Must have has_fresh_loss field
        assert 'has_fresh_loss' in data
        assert isinstance(data['has_fresh_loss'], bool)
    
    def test_fresh_loss_when_no_loss_returns_minimal_response(self):
        """When no fresh loss, should return minimal response"""
        response = requests.get(
            f"{BASE_URL}/api/coach/fresh-loss",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # When no fresh loss
        if not data['has_fresh_loss']:
            # Should only have has_fresh_loss field
            assert data == {'has_fresh_loss': False}
    
    def test_fresh_loss_includes_expected_fields_when_present(self):
        """When fresh loss exists, should include game_id, focus_label, estimated_minutes"""
        response = requests.get(
            f"{BASE_URL}/api/coach/fresh-loss",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # If there's a fresh loss, validate structure
        if data.get('has_fresh_loss'):
            assert 'game_id' in data
            assert 'focus_label' in data
            assert 'estimated_minutes' in data
            assert isinstance(data['estimated_minutes'], (int, float))
            assert data['estimated_minutes'] > 0


class TestCoachWeeklyProofAPI:
    """Tests for /api/coach/weekly-proof endpoint"""
    
    def test_weekly_proof_endpoint_returns_valid_response(self):
        """GET /api/coach/weekly-proof should return valid JSON with expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/coach/weekly-proof",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Must have all required fields
        assert 'wins' in data
        assert 'missions_completed' in data
        assert 'leak_reduced' in data
        assert 'streak_days' in data
    
    def test_weekly_proof_wins_is_non_negative_integer(self):
        """wins field should be a non-negative integer"""
        response = requests.get(
            f"{BASE_URL}/api/coach/weekly-proof",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data['wins'], int)
        assert data['wins'] >= 0
    
    def test_weekly_proof_missions_completed_is_non_negative_integer(self):
        """missions_completed field should be a non-negative integer"""
        response = requests.get(
            f"{BASE_URL}/api/coach/weekly-proof",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data['missions_completed'], int)
        assert data['missions_completed'] >= 0
    
    def test_weekly_proof_streak_days_is_non_negative_integer(self):
        """streak_days field should be a non-negative integer"""
        response = requests.get(
            f"{BASE_URL}/api/coach/weekly-proof",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data['streak_days'], int)
        assert data['streak_days'] >= 0
    
    def test_weekly_proof_leak_reduced_is_string_or_null(self):
        """leak_reduced field should be a string (pattern name) or null"""
        response = requests.get(
            f"{BASE_URL}/api/coach/weekly-proof",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['leak_reduced'] is None or isinstance(data['leak_reduced'], str)


class TestMissionsTodayAPI:
    """Tests for /api/missions/today endpoint"""
    
    def test_missions_today_endpoint_returns_valid_response(self):
        """GET /api/missions/today should return valid JSON"""
        response = requests.get(
            f"{BASE_URL}/api/missions/today",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have mission data or null
        assert data is not None or data == {}
    
    def test_missions_today_includes_expected_fields(self):
        """Mission should include focus_label, micro_protocol, estimated_minutes, goal"""
        response = requests.get(
            f"{BASE_URL}/api/missions/today",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data and 'mission_id' in data:
            # Core mission fields
            assert 'mission_id' in data
            assert 'focus_label' in data
            assert 'micro_protocol' in data
            assert 'estimated_minutes' in data
            assert 'goal' in data
            assert 'status' in data
    
    def test_missions_today_micro_protocol_is_list(self):
        """micro_protocol should be a list of strings"""
        response = requests.get(
            f"{BASE_URL}/api/missions/today",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data and 'micro_protocol' in data:
            assert isinstance(data['micro_protocol'], list)
            for step in data['micro_protocol']:
                assert isinstance(step, str)
    
    def test_missions_today_goal_has_target(self):
        """goal should have target field"""
        response = requests.get(
            f"{BASE_URL}/api/missions/today",
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data and 'goal' in data:
            assert 'target' in data['goal']
            assert isinstance(data['goal']['target'], int)
            assert data['goal']['target'] > 0

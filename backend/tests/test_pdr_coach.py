"""
PDR (Personalized Decision Reconstruction) and Coach endpoint tests.
Tests the core interactive coaching ritual feature.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "e0M8B6ymZiR-okaGeHRE5NH5TgBo2tudtq4ynwObGq8"


class TestCoachTodayEndpoint:
    """Tests for GET /api/coach/today - the main PDR endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Authorization": f"Bearer {SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_coach_today_returns_200(self):
        """Test that /api/coach/today returns 200 with valid auth"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ /api/coach/today returns 200")
    
    def test_coach_today_has_data_flag(self):
        """Test that response contains has_data flag"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=self.headers
        )
        data = response.json()
        assert "has_data" in data, "Response should contain 'has_data' field"
        print(f"✓ has_data = {data['has_data']}")
    
    def test_pdr_structure_when_has_data(self):
        """Test PDR data structure when user has analyzed games"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=self.headers
        )
        data = response.json()
        
        if not data.get("has_data"):
            pytest.skip("User has no analyzed games - PDR section skipped")
        
        # Check PDR exists
        pdr = data.get("pdr")
        if not pdr:
            pytest.skip("No PDR data available (no mistakes in recent games)")
        
        # Verify PDR structure
        assert "fen" in pdr, "PDR should contain 'fen' field"
        assert "candidates" in pdr, "PDR should contain 'candidates' field"
        assert len(pdr["candidates"]) == 2, "PDR should have exactly 2 candidate moves"
        
        print(f"✓ PDR has valid FEN: {pdr['fen'][:30]}...")
        print(f"✓ PDR has 2 candidates: {[c['move'] for c in pdr['candidates']]}")
    
    def test_pdr_candidates_structure(self):
        """Test that each candidate has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=self.headers
        )
        data = response.json()
        
        pdr = data.get("pdr")
        if not pdr:
            pytest.skip("No PDR data available")
        
        for candidate in pdr.get("candidates", []):
            assert "move" in candidate, "Each candidate should have 'move' field"
            assert "is_best" in candidate, "Each candidate should have 'is_best' field"
            assert isinstance(candidate["is_best"], bool), "'is_best' should be boolean"
        
        # Verify one is correct and one is user's wrong move
        best_count = sum(1 for c in pdr["candidates"] if c.get("is_best"))
        assert best_count == 1, "Exactly one candidate should be marked as best"
        
        print("✓ Candidates have correct structure")
    
    def test_pdr_idea_chain_structure(self):
        """Test idea_chain has required 5 steps for wrong answer feedback"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=self.headers
        )
        data = response.json()
        
        pdr = data.get("pdr")
        if not pdr:
            pytest.skip("No PDR data available")
        
        idea_chain = pdr.get("idea_chain")
        if not idea_chain:
            pytest.skip("No idea_chain in PDR (may not have refutation)")
        
        # Check required fields
        required_fields = [
            "your_plan",
            "why_felt_right", 
            "opponent_counter",
            "why_it_works",
            "better_plan"
        ]
        
        for field in required_fields:
            assert field in idea_chain, f"idea_chain should contain '{field}'"
            assert isinstance(idea_chain[field], str), f"'{field}' should be string"
            assert len(idea_chain[field]) > 5, f"'{field}' should have meaningful content"
        
        print(f"✓ idea_chain has 5 steps:")
        for field in required_fields:
            print(f"  - {field}: {idea_chain[field][:50]}...")
    
    def test_pdr_why_options_structure(self):
        """Test why_options for Socratic method verification"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=self.headers
        )
        data = response.json()
        
        pdr = data.get("pdr")
        if not pdr:
            pytest.skip("No PDR data available")
        
        why_options = pdr.get("why_options")
        if not why_options:
            pytest.skip("No why_options in PDR")
        
        # Check options array
        options = why_options.get("options", [])
        assert len(options) >= 2, "Should have at least 2 options"
        
        for opt in options:
            assert "text" in opt, "Each option should have 'text' field"
            assert "is_correct" in opt, "Each option should have 'is_correct' field"
        
        # Verify exactly one correct answer
        correct_count = sum(1 for o in options if o.get("is_correct"))
        assert correct_count == 1, "Exactly one option should be marked as correct"
        
        print(f"✓ why_options has {len(options)} options with 1 correct")
    
    def test_coach_note_structure(self):
        """Test coach's note section (2-line text)"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=self.headers
        )
        data = response.json()
        
        if not data.get("has_data"):
            pytest.skip("User has no data")
        
        coach_note = data.get("coach_note")
        assert coach_note is not None, "Should have coach_note"
        assert "line1" in coach_note, "coach_note should have 'line1'"
        assert "line2" in coach_note, "coach_note should have 'line2'"
        
        print(f"✓ Coach's Note:")
        print(f"  Line 1: {coach_note['line1']}")
        print(f"  Line 2: {coach_note['line2']}")
    
    def test_light_stats_structure(self):
        """Test light stats section shows blunders/game with trend"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=self.headers
        )
        data = response.json()
        
        if not data.get("has_data"):
            pytest.skip("User has no data")
        
        light_stats = data.get("light_stats", [])
        assert isinstance(light_stats, list), "light_stats should be a list"
        
        if light_stats:
            stat = light_stats[0]
            assert "label" in stat, "Stat should have 'label'"
            assert "value" in stat, "Stat should have 'value'"
            assert "trend" in stat, "Stat should have 'trend'"
            assert stat["trend"] in ["up", "down", "stable"], "Trend should be up/down/stable"
            
            print(f"✓ Light Stats: {stat['label']} = {stat['value']} (trend: {stat['trend']})")
        else:
            print("✓ Light Stats: empty (new user)")
    
    def test_next_game_plan_present(self):
        """Test next game plan section is present"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=self.headers
        )
        data = response.json()
        
        if not data.get("has_data"):
            pytest.skip("User has no data")
        
        plan = data.get("next_game_plan")
        assert plan is not None, "Should have next_game_plan"
        assert isinstance(plan, str), "next_game_plan should be string"
        assert len(plan) > 10, "next_game_plan should have meaningful content"
        
        print(f"✓ Next Game Plan: {plan[:80]}...")
    
    def test_game_context_in_pdr(self):
        """Test game context shows opponent and platform info"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=self.headers
        )
        data = response.json()
        
        pdr = data.get("pdr")
        if not pdr:
            pytest.skip("No PDR data available")
        
        game_context = pdr.get("game_context")
        if not game_context:
            pytest.skip("No game_context in PDR")
        
        # Check expected fields
        assert "platform" in game_context, "game_context should have 'platform'"
        
        print(f"✓ Game Context:")
        print(f"  Platform: {game_context.get('platform', 'N/A')}")
        print(f"  Opponent: {game_context.get('opponent', 'N/A')}")
        print(f"  Time Control: {game_context.get('time_control', 'N/A')}")


class TestCoachSessionEndpoints:
    """Tests for coach session management (Go Play flow)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Authorization": f"Bearer {SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_session_status_endpoint(self):
        """Test GET /api/coach/session-status returns status"""
        response = requests.get(
            f"{BASE_URL}/api/coach/session-status",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data or "has_session" in data
        print(f"✓ Session status: {data}")


class TestLinkedAccounts:
    """Tests for chess account linking"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Authorization": f"Bearer {SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_linked_accounts_endpoint(self):
        """Test GET /api/journey/linked-accounts returns accounts"""
        response = requests.get(
            f"{BASE_URL}/api/journey/linked-accounts",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should have chess_com and lichess fields
        assert "chess_com" in data or "lichess" in data
        print(f"✓ Linked accounts: chess.com={data.get('chess_com')}, lichess={data.get('lichess')}")


class TestUnauthorizedAccess:
    """Test authentication requirements"""
    
    def test_coach_today_without_auth(self):
        """Test that /api/coach/today requires authentication"""
        response = requests.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/coach/today requires authentication")
    
    def test_coach_today_with_invalid_token(self):
        """Test with invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid token rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

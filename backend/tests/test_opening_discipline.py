"""
Tests for Opening Discipline feature in Coach /api/coach/today endpoint

Tests:
1. API returns opening_discipline object with correct structure
2. play_this_today includes best white/black openings with win rates
3. rating_leaks shows openings with <40% win rate
4. wisdom includes coaching tips for recommended openings
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "E08pn4c2DsPF4f4zL0dDvxbyULm2oHophSrl_oyKl7s"

class TestOpeningDisciplineAPI:
    """Tests for Opening Discipline feature in /api/coach/today endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session for all tests"""
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SESSION_TOKEN}"
        })
        
    def test_coach_today_returns_opening_discipline(self):
        """Test /api/coach/today returns opening_discipline object"""
        response = self.session.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify opening_discipline exists
        assert "opening_discipline" in data, "Response should contain opening_discipline"
        
        opening_discipline = data["opening_discipline"]
        assert opening_discipline is not None, "opening_discipline should not be None"
        
    def test_opening_discipline_has_data_flag(self):
        """Test opening_discipline has has_data flag"""
        response = self.session.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 200
        
        data = response.json()
        opening_discipline = data.get("opening_discipline", {})
        
        # has_data should be present
        assert "has_data" in opening_discipline, "opening_discipline should have has_data flag"
        assert isinstance(opening_discipline["has_data"], bool), "has_data should be boolean"
        
    def test_play_this_today_structure(self):
        """Test play_this_today object structure with white/black openings"""
        response = self.session.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 200
        
        data = response.json()
        opening_discipline = data.get("opening_discipline", {})
        
        if not opening_discipline.get("has_data"):
            pytest.skip("No opening data available")
        
        # play_this_today should exist
        assert "play_this_today" in opening_discipline, "Should have play_this_today"
        
        play_this_today = opening_discipline["play_this_today"]
        
        # Should have white/black keys
        assert "white" in play_this_today, "play_this_today should have white key"
        assert "black" in play_this_today, "play_this_today should have black key"
        
        # Test black opening structure (we know Scandinavian exists)
        if play_this_today.get("black"):
            black = play_this_today["black"]
            assert "name" in black, "Black opening should have name"
            assert "win_rate" in black, "Black opening should have win_rate"
            assert "games" in black, "Black opening should have games count"
            assert "wins" in black, "Black opening should have wins count"
            
            # Verify data types
            assert isinstance(black["name"], str), "Opening name should be string"
            assert isinstance(black["win_rate"], (int, float)), "Win rate should be numeric"
            assert isinstance(black["games"], int), "Games count should be integer"
            assert isinstance(black["wins"], int), "Wins count should be integer"
            
        # Should have message
        assert "message" in play_this_today, "play_this_today should have message"
        
    def test_play_this_today_black_opening_values(self):
        """Test expected values for Scandinavian Defense as best black opening"""
        response = self.session.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 200
        
        data = response.json()
        opening_discipline = data.get("opening_discipline", {})
        
        if not opening_discipline.get("has_data"):
            pytest.skip("No opening data available")
            
        play_this_today = opening_discipline.get("play_this_today", {})
        black = play_this_today.get("black")
        
        # Verify Scandinavian Defense data (per agent context)
        assert black is not None, "Should have best black opening"
        assert "Scandinavian" in black["name"], f"Expected Scandinavian, got {black['name']}"
        assert black["win_rate"] == 100, f"Expected 100% win rate, got {black['win_rate']}"
        assert black["wins"] == 3, f"Expected 3 wins, got {black['wins']}"
        assert black["games"] == 3, f"Expected 3 games, got {black['games']}"
        
    def test_rating_leaks_structure(self):
        """Test rating_leaks shows openings with <40% win rate"""
        response = self.session.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 200
        
        data = response.json()
        opening_discipline = data.get("opening_discipline", {})
        
        if not opening_discipline.get("has_data"):
            pytest.skip("No opening data available")
        
        # rating_leaks should exist
        assert "rating_leaks" in opening_discipline, "Should have rating_leaks"
        
        rating_leaks = opening_discipline["rating_leaks"]
        assert isinstance(rating_leaks, list), "rating_leaks should be a list"
        
        # If there are leaks, verify structure
        if len(rating_leaks) > 0:
            leak = rating_leaks[0]
            assert "name" in leak, "Leak should have name"
            assert "color" in leak, "Leak should have color"
            assert "win_rate" in leak, "Leak should have win_rate"
            assert "games" in leak, "Leak should have games count"
            assert "wins" in leak, "Leak should have wins count"
            
            # Verify win_rate is below 40% (threshold)
            assert leak["win_rate"] < 40, f"Rating leak should have <40% win rate, got {leak['win_rate']}"
            
    def test_rating_leaks_french_defense(self):
        """Test French Defense is in rating_leaks with 0% win rate"""
        response = self.session.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 200
        
        data = response.json()
        opening_discipline = data.get("opening_discipline", {})
        
        if not opening_discipline.get("has_data"):
            pytest.skip("No opening data available")
            
        rating_leaks = opening_discipline.get("rating_leaks", [])
        
        # Find French Defense in leaks
        french = None
        for leak in rating_leaks:
            if "French" in leak.get("name", ""):
                french = leak
                break
                
        assert french is not None, "French Defense should be in rating_leaks"
        assert french["win_rate"] == 0, f"French Defense should have 0% win rate, got {french['win_rate']}"
        assert french["color"] == "white", f"French Defense should be white, got {french['color']}"
        assert french["games"] == 3, f"Expected 3 games, got {french['games']}"
        
    def test_wisdom_structure(self):
        """Test wisdom includes coaching tips for recommended openings"""
        response = self.session.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 200
        
        data = response.json()
        opening_discipline = data.get("opening_discipline", {})
        
        if not opening_discipline.get("has_data"):
            pytest.skip("No opening data available")
        
        # wisdom should exist
        assert "wisdom" in opening_discipline, "Should have wisdom"
        
        wisdom = opening_discipline["wisdom"]
        assert isinstance(wisdom, list), "wisdom should be a list"
        
        # If there's wisdom, verify structure
        if len(wisdom) > 0:
            tip = wisdom[0]
            assert "opening" in tip, "Wisdom should have opening name"
            assert "color" in tip, "Wisdom should have color"
            assert "tip" in tip, "Wisdom should have tip text"
            assert "key_idea" in tip, "Wisdom should have key_idea"
            
            # Verify data types
            assert isinstance(tip["opening"], str), "Opening name should be string"
            assert tip["color"] in ["white", "black"], "Color should be white or black"
            assert isinstance(tip["tip"], str) and len(tip["tip"]) > 0, "Tip should be non-empty string"
            assert isinstance(tip["key_idea"], str) and len(tip["key_idea"]) > 0, "Key idea should be non-empty string"
            
    def test_wisdom_scandinavian_tip(self):
        """Test Scandinavian Defense tip content"""
        response = self.session.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 200
        
        data = response.json()
        opening_discipline = data.get("opening_discipline", {})
        
        if not opening_discipline.get("has_data"):
            pytest.skip("No opening data available")
            
        wisdom = opening_discipline.get("wisdom", [])
        
        # Find Scandinavian wisdom
        scandinavian = None
        for w in wisdom:
            if "Scandinavian" in w.get("opening", ""):
                scandinavian = w
                break
                
        assert scandinavian is not None, "Scandinavian Defense should have wisdom"
        assert scandinavian["color"] == "black", "Scandinavian should be for black"
        assert "develop" in scandinavian["tip"].lower() or "queen" in scandinavian["tip"].lower(), \
            f"Scandinavian tip should mention development/queen: {scandinavian['tip']}"
            
    def test_opening_discipline_leak_message(self):
        """Test leak_message is present when rating_leaks exist"""
        response = self.session.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 200
        
        data = response.json()
        opening_discipline = data.get("opening_discipline", {})
        
        if not opening_discipline.get("has_data"):
            pytest.skip("No opening data available")
            
        rating_leaks = opening_discipline.get("rating_leaks", [])
        
        if len(rating_leaks) > 0:
            # If leaks exist, leak_message should exist
            assert "leak_message" in opening_discipline, "Should have leak_message when leaks exist"
            assert isinstance(opening_discipline["leak_message"], str), "leak_message should be string"
            assert len(opening_discipline["leak_message"]) > 0, "leak_message should not be empty"
            
    def test_total_openings_analyzed(self):
        """Test total_openings_analyzed count"""
        response = self.session.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 200
        
        data = response.json()
        opening_discipline = data.get("opening_discipline", {})
        
        if not opening_discipline.get("has_data"):
            pytest.skip("No opening data available")
            
        assert "total_openings_analyzed" in opening_discipline, "Should have total_openings_analyzed"
        assert isinstance(opening_discipline["total_openings_analyzed"], int), "Should be integer"
        assert opening_discipline["total_openings_analyzed"] > 0, "Should have analyzed at least some openings"


class TestOpeningDisciplineEdgeCases:
    """Edge case tests for Opening Discipline"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session for all tests"""
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SESSION_TOKEN}"
        })
        
    def test_unauthenticated_request(self):
        """Test that unauthenticated requests return 401"""
        response = requests.get(f"{BASE_URL}/api/coach/today")
        assert response.status_code == 401, "Should return 401 for unauthenticated request"
        
    def test_invalid_token(self):
        """Test that invalid token returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401, "Should return 401 for invalid token"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

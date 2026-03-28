"""
Test Adaptive Performance Coach API
====================================
Tests the GM-style performance briefing system with 4 sections:
1. Coach Diagnosis - identifies user's primary weakness based on rating band
2. Next Game Plan - 5 domains with intensity levels
3. Plan Audit - last game execution review vs plan
4. Skill Signals - live performance monitoring with trends
"""
import pytest
import requests
import os

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "test_session_356539ff12b1"

class TestAdaptiveCoachAPI:
    """Test /api/adaptive-coach endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session for all tests"""
        self.session = requests.Session()
        self.session.cookies.set("session_token", SESSION_TOKEN)
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_adaptive_coach_returns_200(self):
        """Test GET /api/adaptive-coach returns 200"""
        response = self.session.get(f"{BASE_URL}/api/adaptive-coach")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/adaptive-coach returns 200")
    
    def test_adaptive_coach_has_diagnosis_section(self):
        """Test response contains diagnosis section with primary leak"""
        response = self.session.get(f"{BASE_URL}/api/adaptive-coach")
        data = response.json()
        
        # Check for needs_more_games case
        if data.get("needs_more_games"):
            pytest.skip("User needs more games for diagnosis")
        
        assert "diagnosis" in data, "Missing 'diagnosis' section"
        diagnosis = data["diagnosis"]
        
        # Check diagnosis structure
        assert "title" in diagnosis, "Missing diagnosis title"
        assert "primary_leak" in diagnosis, "Missing primary_leak in diagnosis"
        
        primary_leak = diagnosis["primary_leak"]
        assert "id" in primary_leak, "Primary leak missing 'id'"
        assert "label" in primary_leak, "Primary leak missing 'label'"
        assert "explanation" in primary_leak, "Primary leak missing 'explanation'"
        
        print(f"✓ Diagnosis section present with primary leak: {primary_leak['label']}")
    
    def test_adaptive_coach_has_next_game_plan_section(self):
        """Test response contains next_game_plan section with domains"""
        response = self.session.get(f"{BASE_URL}/api/adaptive-coach")
        data = response.json()
        
        if data.get("needs_more_games"):
            pytest.skip("User needs more games for plan")
        
        assert "next_game_plan" in data, "Missing 'next_game_plan' section"
        plan = data["next_game_plan"]
        
        # Check plan structure
        assert "plan_id" in plan, "Missing plan_id"
        assert "domains" in plan, "Missing domains array"
        assert isinstance(plan["domains"], list), "domains should be a list"
        assert len(plan["domains"]) >= 1, "Should have at least 1 domain"
        
        # Check domain structure
        for domain in plan["domains"]:
            assert "id" in domain, "Domain missing 'id'"
            assert "label" in domain, "Domain missing 'label'"
            assert "goal" in domain, "Domain missing 'goal'"
        
        print(f"✓ Next Game Plan present with {len(plan['domains'])} domains")
    
    def test_adaptive_coach_has_plan_audit_section(self):
        """Test response contains plan_audit section with audit cards"""
        response = self.session.get(f"{BASE_URL}/api/adaptive-coach")
        data = response.json()
        
        if data.get("needs_more_games"):
            pytest.skip("User needs more games for audit")
        
        assert "plan_audit" in data, "Missing 'plan_audit' section"
        audit = data["plan_audit"]
        
        # Check audit structure
        assert "has_plan" in audit, "Missing has_plan flag"
        
        if audit["has_plan"]:
            assert "audit_cards" in audit, "Missing audit_cards"
            assert isinstance(audit["audit_cards"], list), "audit_cards should be a list"
            
            # Check audit card structure
            for card in audit["audit_cards"]:
                assert "domain_id" in card, "Audit card missing domain_id"
                assert "label" in card, "Audit card missing label"
                assert "status" in card, "Audit card missing status"
                # Status should be one of: executed, partial, missed, n/a
                assert card["status"] in ["executed", "partial", "missed", "n/a"], \
                    f"Invalid status: {card['status']}"
            
            print(f"✓ Plan Audit present with {len(audit['audit_cards'])} cards")
        else:
            print("✓ Plan Audit present (no previous plan)")
    
    def test_adaptive_coach_has_skill_signals_section(self):
        """Test response contains skill_signals section with trends"""
        response = self.session.get(f"{BASE_URL}/api/adaptive-coach")
        data = response.json()
        
        if data.get("needs_more_games"):
            pytest.skip("User needs more games for signals")
        
        assert "skill_signals" in data, "Missing 'skill_signals' section"
        signals = data["skill_signals"]
        
        # Check signals structure
        assert "has_enough_data" in signals, "Missing has_enough_data flag"
        
        if signals["has_enough_data"]:
            assert "signals" in signals, "Missing signals array"
            assert isinstance(signals["signals"], list), "signals should be a list"
            
            # Check signal structure
            for signal in signals["signals"]:
                assert "id" in signal, "Signal missing id"
                assert "label" in signal, "Signal missing label"
                assert "trend" in signal, "Signal missing trend"
                # Trend should be: improving, declining, or stable
                assert signal["trend"] in ["improving", "declining", "stable"], \
                    f"Invalid trend: {signal['trend']}"
            
            print(f"✓ Skill Signals present with {len(signals['signals'])} signals")
        else:
            print("✓ Skill Signals present (not enough data for trends)")
    
    def test_adaptive_coach_diagnosis_has_example_position(self):
        """Test primary leak includes example position FEN for board visualization"""
        response = self.session.get(f"{BASE_URL}/api/adaptive-coach")
        data = response.json()
        
        if data.get("needs_more_games"):
            pytest.skip("User needs more games")
        
        diagnosis = data.get("diagnosis", {})
        primary_leak = diagnosis.get("primary_leak", {})
        
        # Check if example_position exists and has FEN
        if primary_leak.get("example_position"):
            example = primary_leak["example_position"]
            assert "fen" in example, "Example position missing FEN"
            # FEN should be a valid-looking string
            assert "/" in example["fen"], "FEN should contain '/' characters"
            print(f"✓ Primary leak has example position: {example['fen'][:30]}...")
        else:
            print("✓ Primary leak present (no example position available)")
    
    def test_adaptive_coach_audit_cards_have_board_links(self):
        """Test audit cards with 'missed' status have board_link_fen for eye icon"""
        response = self.session.get(f"{BASE_URL}/api/adaptive-coach")
        data = response.json()
        
        if data.get("needs_more_games"):
            pytest.skip("User needs more games")
        
        audit = data.get("plan_audit", {})
        if not audit.get("has_plan"):
            pytest.skip("No plan to audit")
        
        missed_cards = [c for c in audit.get("audit_cards", []) if c["status"] == "missed"]
        
        if missed_cards:
            # Missed cards should have board_link_fen
            for card in missed_cards:
                assert "board_link_fen" in card, f"Missed card '{card['label']}' missing board_link_fen"
                if card["board_link_fen"]:
                    assert "/" in card["board_link_fen"], "board_link_fen should be valid FEN"
            print(f"✓ {len(missed_cards)} missed audit cards have board_link_fen")
        else:
            print("✓ No missed cards (all executed or partial)")
    
    def test_adaptive_coach_skill_signals_have_trends(self):
        """Test skill signals show trend direction (improving/declining/stable)"""
        response = self.session.get(f"{BASE_URL}/api/adaptive-coach")
        data = response.json()
        
        if data.get("needs_more_games"):
            pytest.skip("User needs more games")
        
        signals = data.get("skill_signals", {})
        if not signals.get("has_enough_data"):
            pytest.skip("Not enough data for trends")
        
        signal_list = signals.get("signals", [])
        trends_found = {"improving": 0, "declining": 0, "stable": 0}
        
        for signal in signal_list:
            trend = signal.get("trend")
            if trend in trends_found:
                trends_found[trend] += 1
            
            # Check trend arrow is present
            assert "trend_arrow" in signal, f"Signal '{signal['label']}' missing trend_arrow"
            # Check reason is present
            assert "reason" in signal, f"Signal '{signal['label']}' missing reason"
        
        print(f"✓ Skill signals have trends: {trends_found}")
    
    def test_adaptive_coach_rating_band_detection(self):
        """Test rating band is correctly detected and returned"""
        response = self.session.get(f"{BASE_URL}/api/adaptive-coach")
        data = response.json()
        
        assert "rating_band" in data, "Missing rating_band in response"
        assert "rating" in data, "Missing rating in response"
        
        rating = data["rating"]
        band = data["rating_band"]
        
        # Verify band matches rating
        if rating < 1000:
            expected_band = "600-1000"
        elif rating < 1600:
            expected_band = "1000-1600"
        elif rating < 2000:
            expected_band = "1600-2000"
        else:
            expected_band = "2000+"
        
        assert band == expected_band, f"Rating {rating} should be in band {expected_band}, got {band}"
        print(f"✓ Rating band correctly detected: {rating} -> {band}")
    
    def test_adaptive_coach_games_analyzed_count(self):
        """Test games_analyzed count is returned"""
        response = self.session.get(f"{BASE_URL}/api/adaptive-coach")
        data = response.json()
        
        assert "games_analyzed" in data, "Missing games_analyzed count"
        games = data["games_analyzed"]
        assert isinstance(games, int), "games_analyzed should be integer"
        assert games >= 0, "games_analyzed should be non-negative"
        
        print(f"✓ Games analyzed count: {games}")


class TestAdaptiveCoachAuditGame:
    """Test /api/adaptive-coach/audit-game/{game_id} endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session for all tests"""
        self.session = requests.Session()
        self.session.cookies.set("session_token", SESSION_TOKEN)
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_audit_game_with_valid_game_id(self):
        """Test POST /api/adaptive-coach/audit-game/{game_id} with valid ID"""
        # First get a valid game_id from adaptive-coach response
        response = self.session.get(f"{BASE_URL}/api/adaptive-coach")
        data = response.json()
        
        if data.get("needs_more_games"):
            pytest.skip("User needs more games")
        
        # Get game_id from plan_audit if available
        game_id = data.get("plan_audit", {}).get("last_game", {}).get("game_id")
        if not game_id:
            pytest.skip("No game_id available in plan_audit")
        
        # Call audit endpoint
        response = self.session.post(f"{BASE_URL}/api/adaptive-coach/audit-game/{game_id}")
        # Can return 200 with data or error message
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Audit game endpoint responds correctly for game_id: {game_id}")
    
    def test_audit_game_with_invalid_game_id(self):
        """Test POST /api/adaptive-coach/audit-game/{game_id} with invalid ID"""
        response = self.session.post(f"{BASE_URL}/api/adaptive-coach/audit-game/invalid_game_123")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should return error in response body
        assert "error" in data, "Should return error for invalid game_id"
        print(f"✓ Audit game returns error for invalid game_id: {data['error']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

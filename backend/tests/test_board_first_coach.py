"""
Test Board-First Coach Feature - Phase 1
Tests the BoardFirstCoach page with 3-tab layout (Audit, Plan, Openings)
and the key_moments/drills data from backend APIs.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
SESSION_COOKIE = {"session_token": "test_session_356539ff12b1"}


class TestPlanAuditAPI:
    """Test GET /api/plan-audit endpoint for key_moments and drills"""
    
    def test_plan_audit_returns_200(self):
        """Test that plan-audit endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/plan-audit",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ /api/plan-audit returns 200")
    
    def test_plan_audit_has_key_moments(self):
        """Test that plan-audit returns key_moments array"""
        response = requests.get(
            f"{BASE_URL}/api/plan-audit",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "key_moments" in data, "key_moments field missing"
        assert isinstance(data["key_moments"], list), "key_moments should be a list"
        print(f"✓ key_moments found with {len(data['key_moments'])} moments")
    
    def test_key_moment_structure(self):
        """Test that each key moment has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/plan-audit",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        if data.get("key_moments") and len(data["key_moments"]) > 0:
            moment = data["key_moments"][0]
            
            # Required fields for KeyMomentCard
            required_fields = ["moveNumber", "fen", "evalSwing", "category", "label"]
            for field in required_fields:
                assert field in moment, f"Missing required field: {field}"
            
            # Check types
            assert isinstance(moment["moveNumber"], int), "moveNumber should be int"
            assert isinstance(moment["fen"], str), "fen should be string"
            assert isinstance(moment["evalSwing"], (int, float)), "evalSwing should be numeric"
            assert isinstance(moment["category"], str), "category should be string"
            
            print(f"✓ Key moment structure valid: Move {moment['moveNumber']} - {moment['label']}")
        else:
            pytest.skip("No key moments available to test structure")
    
    def test_key_moment_has_correct_moves(self):
        """Test that key moments have correctMoves for Try Again functionality"""
        response = requests.get(
            f"{BASE_URL}/api/plan-audit",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        if data.get("key_moments") and len(data["key_moments"]) > 0:
            moment = data["key_moments"][0]
            
            # correctMoves is needed for drill mode
            assert "correctMoves" in moment or "bestMove" in moment, \
                "Missing correctMoves or bestMove field"
            
            if "correctMoves" in moment:
                assert isinstance(moment["correctMoves"], list), "correctMoves should be a list"
            
            print("✓ Key moment has correctMoves/bestMove for drill functionality")
        else:
            pytest.skip("No key moments available")
    
    def test_plan_audit_has_drills(self):
        """Test that plan-audit returns drills array"""
        response = requests.get(
            f"{BASE_URL}/api/plan-audit",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "drills" in data, "drills field missing"
        assert isinstance(data["drills"], list), "drills should be a list"
        print(f"✓ drills found with {len(data['drills'])} drill(s)")


class TestRoundPreparationAPI:
    """Test GET /api/round-preparation endpoint for Plan tab data"""
    
    def test_round_preparation_returns_200(self):
        """Test that round-preparation endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ /api/round-preparation returns 200")
    
    def test_has_opening_recommendation(self):
        """Test that round-preparation has opening_recommendation for Openings tab"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "opening_recommendation" in data, "opening_recommendation field missing"
        opening_rec = data["opening_recommendation"]
        
        # Should have as_white and as_black
        assert "as_white" in opening_rec or "as_black" in opening_rec, \
            "opening_recommendation should have as_white or as_black"
        
        print("✓ opening_recommendation found for Openings tab")
    
    def test_has_cards_for_plan_tab(self):
        """Test that round-preparation has cards for Plan tab habits"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "cards" in data, "cards field missing"
        assert isinstance(data["cards"], list), "cards should be a list"
        assert len(data["cards"]) >= 2, "Should have at least 2 cards for Focus Habits"
        
        # Check card structure
        card = data["cards"][0]
        assert "domain" in card, "card missing domain field"
        assert "goal" in card, "card missing goal field"
        
        print(f"✓ Found {len(data['cards'])} cards for Plan tab")
    
    def test_has_drills_for_practice(self):
        """Test that round-preparation has drills for Practice Drills section"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "drills" in data, "drills field missing"
        
        if len(data["drills"]) > 0:
            drill = data["drills"][0]
            required_fields = ["id", "fen", "difficulty"]
            for field in required_fields:
                assert field in drill, f"Drill missing required field: {field}"
            
            print(f"✓ Found {len(data['drills'])} drill(s) with valid structure")
        else:
            print("✓ drills field exists (empty - no drills generated)")
    
    def test_has_training_block(self):
        """Test that round-preparation has training_block with intensity"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "training_block" in data, "training_block field missing"
        block = data["training_block"]
        
        assert "name" in block, "training_block missing name"
        assert "intensity" in block, "training_block missing intensity"
        
        print(f"✓ Training block: {block['name']} at intensity {block['intensity']}")


class TestDrillStructure:
    """Test drill data structure for CoachBoard integration"""
    
    def test_drill_has_correct_moves(self):
        """Test that drills have correctMoves for drill mode validation"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        if data.get("drills") and len(data["drills"]) > 0:
            drill = data["drills"][0]
            assert "correctMoves" in drill, "drill missing correctMoves"
            assert isinstance(drill["correctMoves"], list), "correctMoves should be a list"
            assert len(drill["correctMoves"]) > 0, "correctMoves should not be empty"
            
            print(f"✓ Drill has correctMoves: {drill['correctMoves']}")
        else:
            pytest.skip("No drills available to test")
    
    def test_drill_has_fen_position(self):
        """Test that drills have FEN for board display"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        if data.get("drills") and len(data["drills"]) > 0:
            drill = data["drills"][0]
            assert "fen" in drill, "drill missing fen"
            assert isinstance(drill["fen"], str), "fen should be string"
            # Basic FEN validation - should have pieces and side to move
            assert "/" in drill["fen"], "Invalid FEN format"
            
            print(f"✓ Drill has valid FEN position")
        else:
            pytest.skip("No drills available to test")


class TestAuditSummary:
    """Test audit summary for Last Game section in Audit tab"""
    
    def test_has_audit_summary(self):
        """Test that plan-audit has audit_summary"""
        response = requests.get(
            f"{BASE_URL}/api/plan-audit",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "audit_summary" in data, "audit_summary field missing"
        summary = data["audit_summary"]
        
        expected_fields = ["score", "game_result"]
        for field in expected_fields:
            assert field in summary, f"audit_summary missing {field}"
        
        print(f"✓ Audit summary: Score {summary['score']}, Result: {summary['game_result']}")
    
    def test_audit_summary_has_opponent(self):
        """Test that audit_summary has opponent name"""
        response = requests.get(
            f"{BASE_URL}/api/plan-audit",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        summary = data.get("audit_summary", {})
        assert "opponent_name" in summary, "Missing opponent_name in audit_summary"
        
        print(f"✓ Opponent: {summary['opponent_name']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

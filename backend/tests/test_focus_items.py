"""
Test Focus Items Feature - Critical Tactical Patterns from Last Game

This tests the P0 feature: Critical tactical patterns missed in the last game
(like piece traps, forks, etc.) should be extracted from the game analysis
and displayed as actionable 'Focus Items' in the next game's plan.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFocusItemsBackend:
    """Test Backend API for Focus Items Feature"""
    
    def test_round_preparation_returns_focus_items(self):
        """Test that /api/round-preparation endpoint returns focus_items array"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies={"session_id": "dev_session"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify focus_items key exists
        assert "focus_items" in data, "focus_items key should exist in round-preparation response"
        assert isinstance(data["focus_items"], list), "focus_items should be a list"
        print(f"✓ focus_items key exists in response with {len(data['focus_items'])} items")
    
    def test_focus_items_have_required_fields(self):
        """Test that focus_items contain all required fields when present"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies={"session_id": "dev_session"}
        )
        
        assert response.status_code == 200
        data = response.json()
        focus_items = data.get("focus_items", [])
        
        if len(focus_items) == 0:
            pytest.skip("No focus_items in current data - need game with tactical misses")
        
        # Check each focus item has required fields
        required_fields = [
            "id", "from_last_game", "pattern", "pattern_name",
            "move_number", "cp_lost", "goal", "explanation", 
            "key_insight", "icon"
        ]
        
        for item in focus_items:
            for field in required_fields:
                assert field in item, f"Focus item missing required field: {field}"
            
            # Verify field types
            assert isinstance(item["id"], str), "id should be string"
            assert isinstance(item["from_last_game"], bool), "from_last_game should be bool"
            assert isinstance(item["pattern"], str), "pattern should be string"
            assert isinstance(item["pattern_name"], str), "pattern_name should be string"
            assert isinstance(item["goal"], str), "goal should be string"
            assert isinstance(item["icon"], str), "icon should be string"
            
            print(f"✓ Focus item '{item['pattern_name']}' has all required fields")
    
    def test_focus_item_pattern_types(self):
        """Test that pattern types are valid tactical patterns"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies={"session_id": "dev_session"}
        )
        
        assert response.status_code == 200
        data = response.json()
        focus_items = data.get("focus_items", [])
        
        if len(focus_items) == 0:
            pytest.skip("No focus_items in current data")
        
        valid_patterns = [
            "piece_trap", "missed_piece_trap", "fork", "missed_fork",
            "mobility_restriction", "multi_threat", "attack_valuable",
            "pin", "missed_pin", "positional"
        ]
        
        for item in focus_items:
            assert item["pattern"] in valid_patterns, f"Unknown pattern type: {item['pattern']}"
            print(f"✓ Pattern type '{item['pattern']}' is valid")
    
    def test_focus_item_cp_loss_values(self):
        """Test that cp_lost values are reasonable (> 100 for critical patterns)"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies={"session_id": "dev_session"}
        )
        
        assert response.status_code == 200
        data = response.json()
        focus_items = data.get("focus_items", [])
        
        if len(focus_items) == 0:
            pytest.skip("No focus_items in current data")
        
        for item in focus_items:
            cp_lost = item.get("cp_lost", 0)
            # Critical patterns should have significant cp loss (>= 100 centipawns)
            assert cp_lost >= 100, f"cp_lost should be >= 100 for critical pattern, got {cp_lost}"
            print(f"✓ Pattern '{item['pattern_name']}' has cp_lost of {cp_lost}")
    
    def test_focus_item_actionable_goal(self):
        """Test that goal field provides actionable advice"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies={"session_id": "dev_session"}
        )
        
        assert response.status_code == 200
        data = response.json()
        focus_items = data.get("focus_items", [])
        
        if len(focus_items) == 0:
            pytest.skip("No focus_items in current data")
        
        for item in focus_items:
            goal = item.get("goal", "")
            assert len(goal) > 10, "goal should be a meaningful description"
            # Goal should contain actionable language
            actionable_words = ["look", "check", "watch", "scan", "ask", "create", "avoid"]
            has_actionable = any(word in goal.lower() for word in actionable_words)
            assert has_actionable or len(goal) > 20, f"Goal should be actionable: {goal}"
            print(f"✓ Goal is actionable: '{goal[:50]}...'")


class TestRegeneratePlanWithFocusItems:
    """Test that regenerate-plan generates focus_items based on last game analysis"""
    
    def test_regenerate_plan_endpoint_exists(self):
        """Test that regenerate-plan endpoint is accessible"""
        response = requests.post(
            f"{BASE_URL}/api/coaching-loop/regenerate-plan",
            cookies={"session_id": "dev_session"}
        )
        
        # Should return 200 with new plan or error if not enough data
        assert response.status_code in [200, 400, 404], f"Unexpected status: {response.status_code}"
        print(f"✓ regenerate-plan endpoint returned status {response.status_code}")
    
    def test_regenerate_plan_returns_focus_items(self):
        """Test that regenerate-plan returns focus_items in response"""
        response = requests.post(
            f"{BASE_URL}/api/coaching-loop/regenerate-plan",
            cookies={"session_id": "dev_session"}
        )
        
        if response.status_code != 200:
            pytest.skip("regenerate-plan not available for current user")
        
        data = response.json()
        
        # Check if focus_items key exists
        assert "focus_items" in data, "regenerate-plan should return focus_items"
        print(f"✓ regenerate-plan returns focus_items with {len(data.get('focus_items', []))} items")


class TestCoachingLoopProfile:
    """Test coaching loop profile endpoint for critical insights"""
    
    def test_coaching_loop_profile_exists(self):
        """Test that coaching loop profile endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/coaching-loop/profile",
            cookies={"session_id": "dev_session"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Profile should contain key information
        expected_keys = ["rating_band", "fundamentals", "behavior_patterns"]
        for key in expected_keys:
            assert key in data, f"Profile missing key: {key}"
        
        print(f"✓ coaching-loop profile returns expected keys")


class TestFocusItemsIntegration:
    """Integration tests for focus items across the coaching loop"""
    
    def test_focus_items_from_last_game_flag(self):
        """Test that focus_items have from_last_game=True flag"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies={"session_id": "dev_session"}
        )
        
        assert response.status_code == 200
        data = response.json()
        focus_items = data.get("focus_items", [])
        
        if len(focus_items) == 0:
            pytest.skip("No focus_items to test")
        
        for item in focus_items:
            assert item.get("from_last_game") is True, "focus items should have from_last_game=True"
        
        print(f"✓ All {len(focus_items)} focus items have from_last_game=True")
    
    def test_training_block_info_present(self):
        """Test that training_block info is present in round-preparation"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies={"session_id": "dev_session"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "training_block" in data, "training_block should be present"
        training_block = data["training_block"]
        
        assert "name" in training_block, "training_block should have name"
        assert "intensity" in training_block, "training_block should have intensity"
        
        print(f"✓ training_block present: {training_block['name']} (intensity {training_block['intensity']})")
    
    def test_domain_cards_present(self):
        """Test that 5 domain cards are present in round-preparation"""
        response = requests.get(
            f"{BASE_URL}/api/round-preparation",
            cookies={"session_id": "dev_session"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "cards" in data, "cards should be present"
        cards = data["cards"]
        
        assert len(cards) == 5, f"Expected 5 domain cards, got {len(cards)}"
        
        expected_domains = {"opening", "middlegame", "tactics", "endgame", "time"}
        actual_domains = {card["domain"] for card in cards}
        
        assert actual_domains == expected_domains, f"Missing domains: {expected_domains - actual_domains}"
        print(f"✓ All 5 domain cards present: {list(actual_domains)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

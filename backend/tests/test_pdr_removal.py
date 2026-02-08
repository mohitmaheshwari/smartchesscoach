"""
Test PDR Removal and New Mistake Mastery Features

Tests:
1. PDR is removed from /api/coach/today response (should not have 'pdr' key)
2. /api/training/card/{card_id}/why endpoint returns why question with options
3. Coach page structure is correct (MistakeMastery-only, no tabs)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "d8p2tHvTnbgx0hZGW7zh-dER1n77rWi6ySAxrU2nD7c"

@pytest.fixture
def auth_headers():
    """Get authenticated headers."""
    return {"Authorization": f"Bearer {SESSION_TOKEN}"}


# ==================== Test 1: PDR Removed from Coach Today ====================

class TestPDRRemoval:
    """Test that legacy PDR system has been removed from coach/today endpoint."""
    
    def test_coach_today_does_not_contain_pdr_key(self, auth_headers):
        """Verify /api/coach/today response does NOT have 'pdr' key."""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        
        # Should return 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Primary test: No 'pdr' key in response
        assert "pdr" not in data, f"Response should NOT contain 'pdr' key. Found keys: {list(data.keys())}"
        
        # Also check for any PDR-related keys
        pdr_related_keys = ["pdr_session", "decision_reconstruction", "pdr_cards", "legacy_pdr"]
        for key in pdr_related_keys:
            assert key not in data, f"Response should NOT contain '{key}' key"
        
        print(f"✓ PDR removed - Response keys: {list(data.keys())}")
    
    def test_coach_today_has_expected_structure(self, auth_headers):
        """Verify /api/coach/today returns expected Mistake Mastery structure."""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # If user has data, should have the new structure
        if data.get("has_data"):
            # Expected keys in the new structure (no PDR)
            expected_keys = ["has_data", "coach_note", "light_stats", "next_game_plan", 
                           "session_status", "last_game", "rule"]
            
            for key in expected_keys:
                assert key in data, f"Missing expected key '{key}' in response"
            
            print(f"✓ Coach today has correct structure: {list(data.keys())}")
        else:
            # User doesn't have data yet - should have message
            assert "message" in data or "has_data" in data
            print(f"✓ User has no data yet - response: {data}")
    
    def test_coach_note_structure(self, auth_headers):
        """Verify coach_note has the correct line1/line2 structure."""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get("has_data") and data.get("coach_note"):
            coach_note = data["coach_note"]
            assert "line1" in coach_note, "coach_note should have 'line1'"
            assert "line2" in coach_note, "coach_note should have 'line2'"
            print(f"✓ Coach note: {coach_note['line1']} / {coach_note['line2']}")
    
    def test_light_stats_structure(self, auth_headers):
        """Verify light_stats has correct structure."""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get("has_data") and data.get("light_stats"):
            light_stats = data["light_stats"]
            assert isinstance(light_stats, list), "light_stats should be a list"
            
            for stat in light_stats:
                assert "label" in stat, "Each stat should have 'label'"
                assert "value" in stat, "Each stat should have 'value'"
                assert "trend" in stat, "Each stat should have 'trend'"
            
            print(f"✓ Light stats: {len(light_stats)} stats found")


# ==================== Test 2: Why Question Endpoint ====================

class TestWhyQuestionEndpoint:
    """Test /api/training/card/{card_id}/why endpoint."""
    
    def get_test_card_id(self, auth_headers):
        """Get a card ID for testing."""
        # First get training session to find cards
        response = requests.get(f"{BASE_URL}/api/training/session", headers=auth_headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("cards") and len(data["cards"]) > 0:
                return data["cards"][0].get("card_id")
            if data.get("card"):
                return data["card"].get("card_id")
        return None
    
    def test_why_endpoint_returns_question(self, auth_headers):
        """Test that /why endpoint returns a question with options."""
        card_id = self.get_test_card_id(auth_headers)
        
        if not card_id:
            pytest.skip("No training cards available for testing")
        
        response = requests.get(f"{BASE_URL}/api/training/card/{card_id}/why", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Should have question
        assert "question" in data, "Response should have 'question'"
        assert isinstance(data["question"], str), "question should be a string"
        assert len(data["question"]) > 0, "question should not be empty"
        
        print(f"✓ Why question: {data['question']}")
    
    def test_why_endpoint_returns_options(self, auth_headers):
        """Test that /why endpoint returns multiple options."""
        card_id = self.get_test_card_id(auth_headers)
        
        if not card_id:
            pytest.skip("No training cards available for testing")
        
        response = requests.get(f"{BASE_URL}/api/training/card/{card_id}/why", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have options
        assert "options" in data, "Response should have 'options'"
        assert isinstance(data["options"], list), "options should be a list"
        assert len(data["options"]) >= 2, f"Should have at least 2 options, got {len(data['options'])}"
        
        # Each option should have id, text, is_correct
        for option in data["options"]:
            assert "id" in option, "Each option should have 'id'"
            assert "text" in option, "Each option should have 'text'"
            assert "is_correct" in option, "Each option should have 'is_correct'"
        
        # Exactly one option should be correct
        correct_count = sum(1 for opt in data["options"] if opt["is_correct"])
        assert correct_count == 1, f"Should have exactly 1 correct option, got {correct_count}"
        
        print(f"✓ Why options: {len(data['options'])} options, 1 correct")
    
    def test_why_endpoint_returns_explanation(self, auth_headers):
        """Test that /why endpoint returns correct_explanation."""
        card_id = self.get_test_card_id(auth_headers)
        
        if not card_id:
            pytest.skip("No training cards available for testing")
        
        response = requests.get(f"{BASE_URL}/api/training/card/{card_id}/why", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have correct_explanation
        assert "correct_explanation" in data, "Response should have 'correct_explanation'"
        assert isinstance(data["correct_explanation"], str), "correct_explanation should be a string"
        
        print(f"✓ Correct explanation: {data['correct_explanation'][:80]}...")
    
    def test_why_endpoint_invalid_card(self, auth_headers):
        """Test that /why endpoint returns 404 for invalid card."""
        response = requests.get(f"{BASE_URL}/api/training/card/invalid_card_123/why", headers=auth_headers)
        
        assert response.status_code == 404, f"Expected 404 for invalid card, got {response.status_code}"
        
        print("✓ Invalid card returns 404")
    
    def test_why_endpoint_optional_fields(self, auth_headers):
        """Test optional fields in /why response."""
        card_id = self.get_test_card_id(auth_headers)
        
        if not card_id:
            pytest.skip("No training cards available for testing")
        
        response = requests.get(f"{BASE_URL}/api/training/card/{card_id}/why", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Optional fields that may be present
        optional_fields = ["hint", "threat_line", "better_line"]
        present_fields = [f for f in optional_fields if f in data]
        
        print(f"✓ Optional fields present: {present_fields}")


# ==================== Test 3: Training Session ====================

class TestTrainingSession:
    """Test training session endpoint (used by MistakeMastery component)."""
    
    def test_training_session_endpoint_works(self, auth_headers):
        """Test /api/training/session returns valid response."""
        response = requests.get(f"{BASE_URL}/api/training/session", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Should have mode
        assert "mode" in data, "Response should have 'mode'"
        assert data["mode"] in ["post_game_debrief", "daily_training", "all_caught_up"], \
            f"Invalid mode: {data['mode']}"
        
        print(f"✓ Training session mode: {data['mode']}")
    
    def test_training_session_has_correct_structure(self, auth_headers):
        """Test training session has correct structure for each mode."""
        response = requests.get(f"{BASE_URL}/api/training/session", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        mode = data["mode"]
        
        if mode == "daily_training":
            assert "cards" in data, "daily_training should have 'cards'"
            assert "cards_due" in data, "daily_training should have 'cards_due'"
            assert isinstance(data["cards"], list), "cards should be a list"
            
            print(f"✓ Daily training: {data['cards_due']} cards due")
            
        elif mode == "post_game_debrief":
            assert "card" in data, "post_game_debrief should have 'card'"
            
            print("✓ Post-game debrief mode")
            
        elif mode == "all_caught_up":
            assert "message" in data, "all_caught_up should have 'message'"
            
            print(f"✓ All caught up: {data['message']}")


# ==================== Test 4: Card Structure ====================

class TestCardStructure:
    """Test that training cards have required fields for playback."""
    
    def test_card_has_required_fields(self, auth_headers):
        """Test cards have fields needed for MistakeMastery component."""
        response = requests.get(f"{BASE_URL}/api/training/session", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Get cards from either mode
        cards = data.get("cards", [])
        if not cards and data.get("card"):
            cards = [data["card"]]
        
        if not cards:
            pytest.skip("No cards available for structure testing")
        
        card = cards[0]
        
        # Required fields for MistakeMastery
        required_fields = [
            "card_id",
            "fen",
            "correct_move",
            "user_move",
            "move_number",
            "habit_tag"
        ]
        
        for field in required_fields:
            assert field in card, f"Card missing required field: {field}"
        
        # Fields for playback
        playback_fields = ["threat_line", "better_line"]
        present_playback = [f for f in playback_fields if f in card]
        
        print(f"✓ Card has required fields. Playback fields: {present_playback}")
    
    def test_card_fen_is_valid(self, auth_headers):
        """Test that card FEN is a valid chess position."""
        response = requests.get(f"{BASE_URL}/api/training/session", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        cards = data.get("cards", [])
        if not cards and data.get("card"):
            cards = [data["card"]]
        
        if not cards:
            pytest.skip("No cards available")
        
        card = cards[0]
        fen = card.get("fen", "")
        
        # Basic FEN validation (should have 6 parts)
        parts = fen.split(" ")
        assert len(parts) >= 4, f"FEN should have at least 4 parts, got {len(parts)}: {fen}"
        
        # First part should have 8 ranks
        ranks = parts[0].split("/")
        assert len(ranks) == 8, f"FEN should have 8 ranks, got {len(ranks)}"
        
        print(f"✓ Card FEN is valid: {fen[:50]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

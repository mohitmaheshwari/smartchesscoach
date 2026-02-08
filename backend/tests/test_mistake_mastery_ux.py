"""
Test Suite for Mistake Mastery UX Updates

Tests:
1. Cards include opponent and user_color fields from API
2. Verify card structure has personalized context
3. Training session and due cards return personalized fields
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Use the provided valid session token
VALID_SESSION_TOKEN = "D4uRg41ZbuWYH5eu2H8R_bo2TuuVxEnUL-hrO9x-2KQ"


class TestMistakeMasteryUXUpdates:
    """Test suite for the Mistake Mastery UX updates - opponent and user_color fields."""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Return headers with valid auth token."""
        return {"Authorization": f"Bearer {VALID_SESSION_TOKEN}"}
    
    # ===========================================
    # Auth Validation
    # ===========================================
    
    def test_valid_session_token(self, auth_headers):
        """Verify the provided session token is valid."""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Auth failed: {response.text}"
        data = response.json()
        assert "user_id" in data
        print(f"✓ Session valid for user: {data.get('user_id')}")

    # ===========================================
    # Training Session Tests - Personalized Context
    # ===========================================
    
    def test_training_session_endpoint_accessible(self, auth_headers):
        """Test GET /api/training/session is accessible."""
        response = requests.get(
            f"{BASE_URL}/api/training/session",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "mode" in data
        print(f"✓ Training session accessible, mode: {data['mode']}")
    
    def test_training_session_cards_have_opponent_and_user_color(self, auth_headers):
        """Test that training session cards include opponent and user_color fields."""
        response = requests.get(
            f"{BASE_URL}/api/training/session",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check based on mode
        if data["mode"] == "post_game_debrief":
            card = data.get("card")
            if card:
                # Cards from recent games should have opponent and user_color
                assert "opponent" in card, "Card should have 'opponent' field"
                assert "user_color" in card, "Card should have 'user_color' field"
                
                # user_color should be 'white' or 'black'
                if card["user_color"]:
                    assert card["user_color"] in ["white", "black"], f"Invalid user_color: {card['user_color']}"
                
                print(f"✓ Post-game debrief card has opponent: '{card.get('opponent')}', user_color: '{card.get('user_color')}'")
        
        elif data["mode"] == "daily_training":
            cards = data.get("cards", [])
            if len(cards) > 0:
                for card in cards[:3]:  # Check first 3 cards
                    assert "opponent" in card, f"Card {card.get('card_id')} should have 'opponent' field"
                    assert "user_color" in card, f"Card {card.get('card_id')} should have 'user_color' field"
                    
                    # user_color should be 'white' or 'black' if present
                    if card["user_color"]:
                        assert card["user_color"] in ["white", "black"], f"Invalid user_color: {card['user_color']}"
                
                print(f"✓ Daily training cards have opponent and user_color fields")
                print(f"  Sample card: opponent='{cards[0].get('opponent')}', user_color='{cards[0].get('user_color')}'")
        
        else:  # all_caught_up
            print(f"✓ Session mode is '{data['mode']}' - no cards to verify")

    # ===========================================
    # Due Cards Tests - Personalized Context
    # ===========================================
    
    def test_due_cards_have_opponent_field(self, auth_headers):
        """Test GET /api/training/due-cards returns cards with opponent field."""
        response = requests.get(
            f"{BASE_URL}/api/training/due-cards?limit=5",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        cards = data.get("cards", [])
        if len(cards) == 0:
            pytest.skip("No due cards available for testing")
        
        for card in cards:
            # opponent field should exist (can be empty string if not available)
            assert "opponent" in card, f"Card {card.get('card_id')} missing 'opponent' field"
            print(f"  Card {card['card_id']}: opponent='{card.get('opponent')}'")
        
        print(f"✓ All {len(cards)} due cards have opponent field")
    
    def test_due_cards_have_user_color_field(self, auth_headers):
        """Test GET /api/training/due-cards returns cards with user_color field."""
        response = requests.get(
            f"{BASE_URL}/api/training/due-cards?limit=5",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        cards = data.get("cards", [])
        if len(cards) == 0:
            pytest.skip("No due cards available for testing")
        
        for card in cards:
            # user_color field should exist
            assert "user_color" in card, f"Card {card.get('card_id')} missing 'user_color' field"
            
            # If present, should be valid value
            user_color = card.get("user_color")
            if user_color:
                assert user_color in ["white", "black"], f"Invalid user_color: {user_color}"
            
            print(f"  Card {card['card_id']}: user_color='{user_color}'")
        
        print(f"✓ All {len(cards)} due cards have user_color field")

    # ===========================================
    # Specific Card Tests
    # ===========================================
    
    def test_get_specific_card_has_personalized_fields(self, auth_headers):
        """Test GET /api/training/card/{card_id} returns personalized fields."""
        # First get a card ID from due cards
        due_response = requests.get(
            f"{BASE_URL}/api/training/due-cards?limit=1",
            headers=auth_headers
        )
        assert due_response.status_code == 200
        due_data = due_response.json()
        
        if len(due_data.get("cards", [])) == 0:
            pytest.skip("No due cards available for testing")
        
        card_id = due_data["cards"][0]["card_id"]
        
        # Get the specific card
        response = requests.get(
            f"{BASE_URL}/api/training/card/{card_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        card = response.json()
        
        # Verify personalized fields
        assert "opponent" in card, "Specific card should have 'opponent' field"
        assert "user_color" in card, "Specific card should have 'user_color' field"
        
        print(f"✓ Specific card {card_id} has personalized fields:")
        print(f"  opponent: '{card.get('opponent')}'")
        print(f"  user_color: '{card.get('user_color')}'")

    # ===========================================
    # Card Structure Completeness Tests
    # ===========================================
    
    def test_card_has_all_required_fields_for_ui(self, auth_headers):
        """Test that cards have all fields required for the MistakeMastery UI component."""
        response = requests.get(
            f"{BASE_URL}/api/training/due-cards?limit=3",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data.get("cards", [])) == 0:
            pytest.skip("No cards available for testing")
        
        # Fields required by the MistakeMastery.jsx UI component
        required_ui_fields = [
            "card_id",
            "fen",
            "correct_move",
            "user_move",
            "move_number",
            "habit_tag",
            "evaluation",
            "cp_loss",
            "explanation",
            "threat_line",
            "better_line",
            # New personalized fields
            "opponent",
            "user_color",
            # Spaced repetition fields
            "consecutive_correct",
            "is_mastered"
        ]
        
        for card in data["cards"]:
            missing_fields = []
            for field in required_ui_fields:
                if field not in card:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"⚠ Card {card.get('card_id')} missing fields: {missing_fields}")
            
            # Core fields must exist
            assert "card_id" in card
            assert "fen" in card
            assert "correct_move" in card
            assert "user_move" in card
            assert "opponent" in card
            assert "user_color" in card
        
        print(f"✓ All cards have required UI fields including opponent and user_color")

    # ===========================================
    # Why Question Tests
    # ===========================================
    
    def test_why_question_endpoint(self, auth_headers):
        """Test GET /api/training/card/{card_id}/why returns question data."""
        # First get a card ID
        due_response = requests.get(
            f"{BASE_URL}/api/training/due-cards?limit=1",
            headers=auth_headers
        )
        assert due_response.status_code == 200
        due_data = due_response.json()
        
        if len(due_data.get("cards", [])) == 0:
            pytest.skip("No due cards available for testing")
        
        card_id = due_data["cards"][0]["card_id"]
        
        # Get why question
        response = requests.get(
            f"{BASE_URL}/api/training/card/{card_id}/why",
            headers=auth_headers
        )
        assert response.status_code == 200
        why_data = response.json()
        
        # Verify why question structure
        assert "question" in why_data, "Why data should have 'question'"
        assert "options" in why_data, "Why data should have 'options'"
        assert isinstance(why_data["options"], list)
        assert len(why_data["options"]) >= 2, "Should have at least 2 options"
        
        # Verify options structure
        for option in why_data["options"]:
            assert "id" in option
            assert "text" in option
            assert "is_correct" in option
        
        # At least one option should be correct
        correct_options = [o for o in why_data["options"] if o["is_correct"]]
        assert len(correct_options) >= 1, "Should have at least one correct option"
        
        print(f"✓ Why question endpoint returns valid data:")
        print(f"  Question: {why_data['question'][:50]}...")
        print(f"  Options: {len(why_data['options'])}")

    # ===========================================
    # Progress Endpoint Tests
    # ===========================================
    
    def test_training_progress_endpoint(self, auth_headers):
        """Test GET /api/training/progress returns valid structure."""
        response = requests.get(
            f"{BASE_URL}/api/training/progress",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "habits" in data
        assert "stats" in data
        
        stats = data["stats"]
        assert "total_cards" in stats
        assert "mastered_cards" in stats
        
        print(f"✓ Training progress: {stats['mastered_cards']}/{stats['total_cards']} mastered")


class TestMistakeMasteryDataIntegrity:
    """Test data integrity of cards created from game analysis."""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        return {"Authorization": f"Bearer {VALID_SESSION_TOKEN}"}
    
    def test_cards_have_valid_fen_positions(self, auth_headers):
        """Test that card FEN positions are valid chess positions."""
        response = requests.get(
            f"{BASE_URL}/api/training/due-cards?limit=5",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data.get("cards", [])) == 0:
            pytest.skip("No cards available")
        
        for card in data["cards"]:
            fen = card.get("fen", "")
            # Basic FEN validation
            assert len(fen) > 20, f"FEN too short: {fen}"
            assert " " in fen, f"FEN should have spaces: {fen}"
            # FEN should have 6 parts
            parts = fen.split(" ")
            assert len(parts) >= 4, f"FEN should have at least 4 parts: {fen}"
            # First part should have 8 ranks
            ranks = parts[0].split("/")
            assert len(ranks) == 8, f"FEN should have 8 ranks: {fen}"
        
        print(f"✓ All {len(data['cards'])} cards have valid FEN positions")
    
    def test_cards_have_valid_evaluation_types(self, auth_headers):
        """Test that card evaluation types are valid."""
        response = requests.get(
            f"{BASE_URL}/api/training/due-cards?limit=5",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data.get("cards", [])) == 0:
            pytest.skip("No cards available")
        
        valid_evaluations = ["blunder", "mistake", "inaccuracy"]
        
        for card in data["cards"]:
            evaluation = card.get("evaluation", "")
            assert evaluation in valid_evaluations, f"Invalid evaluation: {evaluation}"
        
        print(f"✓ All cards have valid evaluation types (blunder/mistake/inaccuracy)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
Test Game Decryption V3 Features
================================

Tests for the V3 Game Decryption feature which adds:
1. Move Intent Recognition (acknowledges WHY user played a move)
2. Opening Introduction card
3. Main Line Theory explanations
4. Empathetic sideline warnings

Test game: cefa44aa-2a42-4751-85a9-8f22990339b3 (Italian Game)
User color: black
h6 move is at move index 5 (6th move: e4, e5, Nf3, Nc6, Bc4, h6)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_GAME_ID = "cefa44aa-2a42-4751-85a9-8f22990339b3"


class TestGameDecryptionV3API:
    """Test V3 Game Decryption API features"""
    
    def test_decryption_endpoint_returns_v3_fields(self):
        """GET /api/coach/decryption/{game_id} returns V3 fields"""
        response = requests.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "decryption_data" in data
        assert "summary" in data
        assert data["decryption_data"] is not None
        assert len(data["decryption_data"]) > 0
        
        # Check that V3 fields exist in move data structure
        first_move = data["decryption_data"][0]
        assert "intent_acknowledged" in first_move
        assert "main_line_theory" in first_move
        assert "main_line_moves" in first_move
        assert "is_sideline" in first_move
        assert "sideline_warning" in first_move
    
    def test_summary_includes_opening_introduction(self):
        """Summary includes opening_introduction with V3 fields"""
        response = requests.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get("summary", {})
        
        # V3: opening_introduction should be present
        assert "opening_introduction" in summary
        intro = summary["opening_introduction"]
        assert intro is not None
        
        # Check required fields
        assert "name" in intro
        assert "description" in intro
        assert "your_plan" in intro
        assert "their_plan" in intro
        assert "key_focus" in intro
        
        # Verify Italian Game content
        assert intro["name"] == "Italian Game"
        assert "f7" in intro["description"].lower() or "bishop" in intro["description"].lower()
    
    def test_h6_move_has_intent_acknowledged(self):
        """h6 move (index 5) has intent_acknowledged field populated"""
        response = requests.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        decryption_data = data["decryption_data"]
        
        # h6 is at index 5 (0-indexed: e4, e5, Nf3, Nc6, Bc4, h6)
        h6_move = decryption_data[5]
        assert h6_move["move_san"] == "h6"
        assert h6_move["is_user_move"] == True
        
        # V3: intent_acknowledged should be populated
        assert h6_move["intent_acknowledged"] is not None
        assert len(h6_move["intent_acknowledged"]) > 0
        
        # Should mention the intent (ng5 or kick the bishop)
        intent_lower = h6_move["intent_acknowledged"].lower()
        assert "ng5" in intent_lower or "bishop" in intent_lower or "awareness" in intent_lower
    
    def test_h6_move_is_sideline_with_empathetic_warning(self):
        """h6 move has is_sideline=true with empathetic sideline_warning"""
        response = requests.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        h6_move = data["decryption_data"][5]
        
        # V3: is_sideline should be true
        assert h6_move["is_sideline"] == True
        
        # V3: sideline_warning should be empathetic (mentions user's idea)
        assert h6_move["sideline_warning"] is not None
        warning_lower = h6_move["sideline_warning"].lower()
        
        # Should acknowledge the user's thinking before correcting
        assert "ng5" in warning_lower or "interesting" in warning_lower or "reasonable" in warning_lower
    
    def test_h6_move_has_main_line_moves(self):
        """h6 move has main_line_moves=['Bc5', 'Nf6']"""
        response = requests.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        h6_move = data["decryption_data"][5]
        
        # V3: main_line_moves should contain Bc5 and Nf6
        assert h6_move["main_line_moves"] is not None
        assert isinstance(h6_move["main_line_moves"], list)
        assert len(h6_move["main_line_moves"]) >= 2
        
        main_moves = h6_move["main_line_moves"]
        assert "Bc5" in main_moves
        assert "Nf6" in main_moves
    
    def test_h6_move_has_main_line_theory(self):
        """h6 move has main_line_theory with lines explaining Bc5 and Nf6"""
        response = requests.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        h6_move = data["decryption_data"][5]
        
        # V3: main_line_theory should be present
        assert h6_move["main_line_theory"] is not None
        theory = h6_move["main_line_theory"]
        
        # Should have lines explaining each main move
        assert "lines" in theory
        lines = theory["lines"]
        assert "Bc5" in lines
        assert "Nf6" in lines
        
        # Bc5 explanation should mention Giuoco Piano
        assert "giuoco" in lines["Bc5"].lower() or "piano" in lines["Bc5"].lower()
        
        # Nf6 explanation should mention Two Knights
        assert "two knights" in lines["Nf6"].lower() or "counterattack" in lines["Nf6"].lower()
        
        # Should have explanation field
        assert "explanation" in theory
    
    def test_h6_what_happened_acknowledges_intent(self):
        """h6 what_happened acknowledges intent (mentions 'ng5' or 'kick the bishop')"""
        response = requests.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        h6_move = data["decryption_data"][5]
        
        what_happened = h6_move["what_happened"].lower()
        
        # V3: what_happened should acknowledge the user's intent
        assert "ng5" in what_happened or "bishop" in what_happened or "preparing" in what_happened
    
    def test_h6_what_you_missed_is_empathetic(self):
        """h6 what_you_missed is empathetic (mentions 'your idea')"""
        response = requests.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        h6_move = data["decryption_data"][5]
        
        # h6 is a mistake, so what_you_missed should be present
        assert h6_move["is_mistake"] == True
        assert h6_move["what_you_missed"] is not None
        
        missed_lower = h6_move["what_you_missed"].lower()
        
        # V3: Should be empathetic - mention "your idea" or similar
        assert "your idea" in missed_lower or "makes sense" in missed_lower or "defensively" in missed_lower


class TestDecryptionFeedbackAPI:
    """Test feedback submission still works"""
    
    def test_feedback_endpoint_works(self):
        """POST /api/coach/decryption/feedback still works"""
        payload = {
            "game_id": TEST_GAME_ID,
            "move_number": 3,
            "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
            "coach_explanation": "Test explanation",
            "user_feedback": "not_helpful",
            "user_correction": "Test correction from V3 test",
            "is_user_move": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/coach/decryption/feedback",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True


class TestOpeningIntroductionContent:
    """Test opening introduction content quality"""
    
    def test_opening_intro_has_italian_game_content(self):
        """Opening introduction has Italian Game specific content"""
        response = requests.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        intro = data["summary"]["opening_introduction"]
        
        # Description should mention key Italian Game concepts
        desc_lower = intro["description"].lower()
        assert "italian" in desc_lower or "bishop" in desc_lower or "f7" in desc_lower
        
        # your_plan (for black) should mention Bc5 or Nf6
        your_plan_lower = intro["your_plan"].lower()
        assert "bc5" in your_plan_lower or "nf6" in your_plan_lower or "develop" in your_plan_lower
        
        # their_plan (for white) should mention f7 or attack
        their_plan_lower = intro["their_plan"].lower()
        assert "f7" in their_plan_lower or "attack" in their_plan_lower or "bishop" in their_plan_lower
    
    def test_opening_intro_key_focus_is_relevant(self):
        """Opening introduction key_focus is relevant to Italian Game"""
        response = requests.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        intro = data["summary"]["opening_introduction"]
        
        key_focus_lower = intro["key_focus"].lower()
        
        # Should mention development, castle, or main responses
        assert any(term in key_focus_lower for term in ["develop", "castle", "bc5", "nf6", "italian"])


class TestMoveDataStructure:
    """Test move data structure has all required fields"""
    
    def test_all_moves_have_v3_fields(self):
        """All moves have V3 fields (even if null)"""
        response = requests.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        
        for i, move in enumerate(data["decryption_data"]):
            # V3 fields should exist (can be null)
            assert "intent_acknowledged" in move, f"Move {i} missing intent_acknowledged"
            assert "main_line_theory" in move, f"Move {i} missing main_line_theory"
            assert "main_line_moves" in move, f"Move {i} missing main_line_moves"
            assert "is_sideline" in move, f"Move {i} missing is_sideline"
            assert "sideline_warning" in move, f"Move {i} missing sideline_warning"
            
            # Core fields should always be present
            assert "move_san" in move
            assert "is_user_move" in move
            assert "what_happened" in move
            assert "phase" in move


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Phase-Aware Coaching Feature Tests
Tests for:
1. Phase analysis endpoint - GET /api/analysis/{game_id}
2. Phase detection (Opening → Middlegame → Endgame)
3. Rating-adaptive content (beginner vs intermediate vs advanced)
4. Strategic lesson required fields
5. Phase theory required fields
6. Frontend Strategy tab data requirements
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct service testing
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://analyze-vault.preview.emergentagent.com')
ANALYZED_GAME_ID = "game_188d768edd26"
TEST_EMAIL = "testuser@demo.com"


class TestPhaseAwareCoachingBackend:
    """Backend API tests for Phase-Aware Coaching"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        # Get demo login session
        response = requests.post(
            f"{BASE_URL}/api/auth/demo-login",
            json={"email": TEST_EMAIL}
        )
        assert response.status_code == 200
        data = response.json()
        self.session_token = data.get("session_token")
        self.session = requests.Session()
        self.session.cookies.set("session_token", self.session_token)
        yield
    
    def test_analysis_endpoint_returns_phase_analysis(self):
        """GET /api/analysis/{game_id} returns phase_analysis field"""
        response = self.session.get(f"{BASE_URL}/api/analysis/{ANALYZED_GAME_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "phase_analysis" in data, "phase_analysis field missing from response"
        assert data["phase_analysis"] is not None, "phase_analysis is null"
        print(f"✓ phase_analysis present with {len(data['phase_analysis'].get('phases', []))} phases")
    
    def test_analysis_endpoint_returns_strategic_lesson(self):
        """GET /api/analysis/{game_id} returns strategic_lesson field"""
        response = self.session.get(f"{BASE_URL}/api/analysis/{ANALYZED_GAME_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "strategic_lesson" in data, "strategic_lesson field missing from response"
        assert data["strategic_lesson"] is not None, "strategic_lesson is null"
        print(f"✓ strategic_lesson present: {data['strategic_lesson'].get('lesson_title')}")
    
    def test_analysis_endpoint_returns_phase_theory(self):
        """GET /api/analysis/{game_id} returns phase_theory field"""
        response = self.session.get(f"{BASE_URL}/api/analysis/{ANALYZED_GAME_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "phase_theory" in data, "phase_theory field missing from response"
        assert data["phase_theory"] is not None, "phase_theory is null"
        print(f"✓ phase_theory present for phase: {data['phase_theory'].get('phase')}")
    
    def test_phase_transitions_detected(self):
        """Phase analysis correctly identifies Opening → Middlegame → Endgame transitions"""
        response = self.session.get(f"{BASE_URL}/api/analysis/{ANALYZED_GAME_ID}")
        assert response.status_code == 200
        data = response.json()
        
        phase_analysis = data.get("phase_analysis", {})
        phases = phase_analysis.get("phases", [])
        transitions = phase_analysis.get("phase_transitions", [])
        
        # Should have phases
        assert len(phases) >= 1, "No phases detected"
        
        # Check phase names are valid
        valid_phases = ["opening", "middlegame", "endgame"]
        for p in phases:
            assert p.get("phase") in valid_phases, f"Invalid phase: {p.get('phase')}"
        
        # For a complete game, should have transitions
        if len(phases) > 1:
            assert len(transitions) >= 1, "No phase transitions detected for multi-phase game"
            
            # Check opening → middlegame transition
            if len(transitions) >= 1 and phases[0]["phase"] == "opening":
                assert transitions[0]["from_phase"] == "opening"
                assert transitions[0]["to_phase"] == "middlegame"
                print("✓ Opening → Middlegame transition detected")
            
            # Check middlegame → endgame transition
            if len(transitions) >= 2:
                assert transitions[1]["from_phase"] == "middlegame"
                assert transitions[1]["to_phase"] == "endgame"
                print("✓ Middlegame → Endgame transition detected")
        
        print(f"✓ Phase transitions: {[p['phase'] for p in phases]}")
    
    def test_strategic_lesson_required_fields(self):
        """Strategic lesson contains required fields: lesson_title, one_sentence_takeaway, next_step, what_to_remember"""
        response = self.session.get(f"{BASE_URL}/api/analysis/{ANALYZED_GAME_ID}")
        assert response.status_code == 200
        data = response.json()
        
        strategic_lesson = data.get("strategic_lesson", {})
        
        # Required fields
        assert "lesson_title" in strategic_lesson, "Missing lesson_title"
        assert strategic_lesson["lesson_title"], "lesson_title is empty"
        
        assert "one_sentence_takeaway" in strategic_lesson, "Missing one_sentence_takeaway"
        assert strategic_lesson["one_sentence_takeaway"], "one_sentence_takeaway is empty"
        
        assert "next_step" in strategic_lesson, "Missing next_step"
        assert strategic_lesson["next_step"], "next_step is empty"
        
        assert "what_to_remember" in strategic_lesson, "Missing what_to_remember"
        assert isinstance(strategic_lesson["what_to_remember"], list), "what_to_remember should be a list"
        assert len(strategic_lesson["what_to_remember"]) > 0, "what_to_remember is empty"
        
        print(f"✓ lesson_title: {strategic_lesson['lesson_title']}")
        print(f"✓ one_sentence_takeaway: {strategic_lesson['one_sentence_takeaway'][:50]}...")
        print(f"✓ next_step: {strategic_lesson['next_step'][:50]}...")
        print(f"✓ what_to_remember: {len(strategic_lesson['what_to_remember'])} items")
    
    def test_phase_theory_required_fields(self):
        """Phase theory contains: key_principles, key_concept, one_thing_to_remember"""
        response = self.session.get(f"{BASE_URL}/api/analysis/{ANALYZED_GAME_ID}")
        assert response.status_code == 200
        data = response.json()
        
        phase_theory = data.get("phase_theory", {})
        
        # Required fields
        assert "key_principles" in phase_theory, "Missing key_principles"
        assert isinstance(phase_theory["key_principles"], list), "key_principles should be a list"
        assert len(phase_theory["key_principles"]) > 0, "key_principles is empty"
        
        assert "key_concept" in phase_theory, "Missing key_concept"
        assert phase_theory["key_concept"], "key_concept is empty"
        
        assert "one_thing_to_remember" in phase_theory, "Missing one_thing_to_remember"
        assert phase_theory["one_thing_to_remember"], "one_thing_to_remember is empty"
        
        print(f"✓ key_principles: {len(phase_theory['key_principles'])} principles")
        print(f"✓ key_concept: {phase_theory['key_concept'][:50]}...")
        print(f"✓ one_thing_to_remember: {phase_theory['one_thing_to_remember'][:50]}...")
    
    def test_rating_bracket_present(self):
        """Rating bracket is present in strategic_lesson and phase_theory"""
        response = self.session.get(f"{BASE_URL}/api/analysis/{ANALYZED_GAME_ID}")
        assert response.status_code == 200
        data = response.json()
        
        strategic_lesson = data.get("strategic_lesson", {})
        phase_theory = data.get("phase_theory", {})
        
        valid_brackets = ["beginner", "intermediate", "advanced", "expert"]
        
        assert "rating_bracket" in strategic_lesson, "Missing rating_bracket in strategic_lesson"
        assert strategic_lesson["rating_bracket"] in valid_brackets, f"Invalid rating_bracket: {strategic_lesson['rating_bracket']}"
        
        assert "rating_bracket" in phase_theory, "Missing rating_bracket in phase_theory"
        assert phase_theory["rating_bracket"] in valid_brackets, f"Invalid rating_bracket: {phase_theory['rating_bracket']}"
        
        print(f"✓ strategic_lesson rating_bracket: {strategic_lesson['rating_bracket']}")
        print(f"✓ phase_theory rating_bracket: {phase_theory['rating_bracket']}")


class TestRatingAdaptiveContent:
    """Tests for rating-adaptive content in phase_theory_service.py"""
    
    def test_rating_bracket_beginner(self):
        """Rating < 1000 returns beginner bracket"""
        from phase_theory_service import get_rating_bracket
        
        assert get_rating_bracket(800) == "beginner"
        assert get_rating_bracket(900) == "beginner"
        assert get_rating_bracket(999) == "beginner"
        print("✓ Ratings < 1000 correctly return 'beginner'")
    
    def test_rating_bracket_intermediate(self):
        """Rating 1000-1399 returns intermediate bracket"""
        from phase_theory_service import get_rating_bracket
        
        assert get_rating_bracket(1000) == "intermediate"
        assert get_rating_bracket(1200) == "intermediate"
        assert get_rating_bracket(1399) == "intermediate"
        print("✓ Ratings 1000-1399 correctly return 'intermediate'")
    
    def test_rating_bracket_advanced(self):
        """Rating 1400-1799 returns advanced bracket"""
        from phase_theory_service import get_rating_bracket
        
        assert get_rating_bracket(1400) == "advanced"
        assert get_rating_bracket(1600) == "advanced"
        assert get_rating_bracket(1799) == "advanced"
        print("✓ Ratings 1400-1799 correctly return 'advanced'")
    
    def test_rating_bracket_expert(self):
        """Rating 1800+ returns expert bracket"""
        from phase_theory_service import get_rating_bracket
        
        assert get_rating_bracket(1800) == "expert"
        assert get_rating_bracket(2000) == "expert"
        assert get_rating_bracket(2200) == "expert"
        print("✓ Ratings 1800+ correctly return 'expert'")
    
    def test_different_ratings_produce_different_content(self):
        """Different rating brackets produce different content"""
        from phase_theory_service import get_phase_theory
        
        beginner_theory = get_phase_theory("opening", None, 800)
        intermediate_theory = get_phase_theory("opening", None, 1200)
        advanced_theory = get_phase_theory("opening", None, 1600)
        expert_theory = get_phase_theory("opening", None, 2000)
        
        # Check rating brackets are set correctly
        assert beginner_theory["rating_bracket"] == "beginner"
        assert intermediate_theory["rating_bracket"] == "intermediate"
        assert advanced_theory["rating_bracket"] == "advanced"
        assert expert_theory["rating_bracket"] == "expert"
        
        # Check content differs
        # Beginner key_concept should be about "DEVELOPMENT"
        assert "DEVELOPMENT" in beginner_theory["key_concept"]
        
        # Intermediate key_concept should be about "PIECE COORDINATION"
        assert "COORDINATION" in intermediate_theory["key_concept"]
        
        # Advanced key_concept should be about "FLEXIBILITY"
        assert "FLEXIBILITY" in advanced_theory["key_concept"]
        
        # Expert key_concept should be about "UNDERSTANDING"
        assert "UNDERSTANDING" in expert_theory["key_concept"]
        
        print("✓ Different ratings produce different key_concepts:")
        print(f"  Beginner: {beginner_theory['key_concept'][:40]}...")
        print(f"  Intermediate: {intermediate_theory['key_concept'][:40]}...")
        print(f"  Advanced: {advanced_theory['key_concept'][:40]}...")
        print(f"  Expert: {expert_theory['key_concept'][:40]}...")
    
    def test_strategic_lesson_rating_adaptive(self):
        """Strategic lesson content adapts to rating level"""
        from phase_theory_service import generate_strategic_lesson
        
        endgame_info = {"is_pawn_ending": True, "pawn_structure": "2 vs 1 pawns"}
        
        beginner_lesson = generate_strategic_lesson("endgame", endgame_info, [], "white", "1-0", 800)
        intermediate_lesson = generate_strategic_lesson("endgame", endgame_info, [], "white", "1-0", 1200)
        advanced_lesson = generate_strategic_lesson("endgame", endgame_info, [], "white", "1-0", 1600)
        
        # Beginner should get simpler advice
        assert beginner_lesson["rating_bracket"] == "beginner"
        assert "king" in beginner_lesson["one_sentence_takeaway"].lower() or "pawn" in beginner_lesson["one_sentence_takeaway"].lower()
        
        # Intermediate should get principle-based advice
        assert intermediate_lesson["rating_bracket"] == "intermediate"
        assert "opposition" in intermediate_lesson["one_sentence_takeaway"].lower() or "key squares" in intermediate_lesson["one_sentence_takeaway"].lower()
        
        # Advanced should get more nuanced theory
        assert advanced_lesson["rating_bracket"] == "advanced"
        
        print("✓ Strategic lessons adapt to rating:")
        print(f"  Beginner: {beginner_lesson['one_sentence_takeaway'][:50]}...")
        print(f"  Intermediate: {intermediate_lesson['one_sentence_takeaway'][:50]}...")
        print(f"  Advanced: {advanced_lesson['one_sentence_takeaway'][:50]}...")


class TestPhaseDetection:
    """Tests for phase detection logic"""
    
    def test_detect_opening_phase(self):
        """Opening phase detected in first 10 moves with pieces on board"""
        import chess
        from phase_theory_service import detect_game_phase
        
        board = chess.Board()
        # Starting position, move 1
        phase = detect_game_phase(board, 1)
        assert phase == "opening", f"Expected 'opening', got '{phase}'"
        print("✓ Opening phase detected at move 1")
    
    def test_detect_middlegame_phase(self):
        """Middlegame phase detected after opening"""
        import chess
        from phase_theory_service import detect_game_phase
        
        # Position after some development - still has pieces but past move 10
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        phase = detect_game_phase(board, 15)  # After move 10
        assert phase == "middlegame", f"Expected 'middlegame', got '{phase}'"
        print("✓ Middlegame phase detected at move 15 with pieces")
    
    def test_detect_endgame_phase(self):
        """Endgame phase detected when queens off and few pieces"""
        import chess
        from phase_theory_service import detect_game_phase, detect_endgame_type
        
        # Rook endgame position
        board = chess.Board("8/8/8/4k3/8/4K3/4R3/4r3 w - - 0 50")
        phase = detect_game_phase(board, 50)
        assert phase == "endgame", f"Expected 'endgame', got '{phase}'"
        
        endgame_info = detect_endgame_type(board)
        assert endgame_info["is_rook_ending"] == True
        print("✓ Endgame phase detected with rook ending")
    
    def test_detect_pawn_ending(self):
        """Pure pawn ending detected correctly"""
        import chess
        from phase_theory_service import detect_endgame_type
        
        # King + Pawn vs King position
        board = chess.Board("8/8/8/4k3/8/4K3/4P3/8 w - - 0 50")
        endgame_info = detect_endgame_type(board)
        
        assert endgame_info["type"] == "pawn_ending"
        assert endgame_info["is_pawn_ending"] == True
        print("✓ Pure pawn ending detected")


class TestEndgameTypeDetection:
    """Tests for endgame type detection"""
    
    def test_rook_ending_detection(self):
        """Rook ending type detected"""
        import chess
        from phase_theory_service import detect_endgame_type
        
        board = chess.Board("8/5pk1/R7/8/8/8/5PK1/r7 w - - 0 1")
        endgame_info = detect_endgame_type(board)
        
        assert endgame_info["type"] == "rook_ending"
        assert endgame_info["is_rook_ending"] == True
        print("✓ Rook ending detected")
    
    def test_minor_piece_ending_detection(self):
        """Minor piece ending type detected"""
        import chess
        from phase_theory_service import detect_endgame_type
        
        # Bishop ending
        board = chess.Board("8/5pk1/B7/8/8/8/5PK1/b7 w - - 0 1")
        endgame_info = detect_endgame_type(board)
        
        assert endgame_info["type"] == "minor_piece_ending"
        assert endgame_info["is_minor_piece_ending"] == True
        print("✓ Minor piece ending detected")
    
    def test_material_balance_detection(self):
        """Material balance correctly identified"""
        import chess
        from phase_theory_service import detect_endgame_type
        
        # White winning position (extra rook)
        board = chess.Board("8/5pk1/R7/8/R7/8/5PK1/8 w - - 0 1")
        endgame_info = detect_endgame_type(board)
        
        assert endgame_info["material_balance"] == "white_winning"
        print("✓ Material balance correctly detected as white_winning")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

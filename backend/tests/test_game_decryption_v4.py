"""
Game Decryption V4 API Tests
============================

Tests for the V4 LLM-powered thinking simulator coaching.

V4 Key Features:
- LLM-generated fields: narrative, thinking_gap, position_breakdown, mistake_analysis, better_plan, principle, confidence
- Good moves get short rule-based narratives (no LLM fields)
- Summary uses thinking_gap in key_moments
- Opening introduction in summary
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_GAME_ID = "cefa44aa-2a42-4751-85a9-8f22990339b3"  # Italian Game, user plays black


@pytest.fixture
def api_client():
    """Shared requests session with auth cookie."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    session.cookies.set("dev_user_id", "user_62852a1b64e7")
    return session


class TestDecryptionV4Structure:
    """Tests for V4 decryption data structure."""
    
    def test_decryption_returns_v4_fields(self, api_client):
        """Verify API returns V4 structure with LLM fields."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "decryption_data" in data
        assert "summary" in data
        assert data["decryption_data"] is not None
        
        # Find h6 move (the mistake at index 5)
        h6_move = None
        for move in data["decryption_data"]:
            if move.get("move_san") == "h6" and move.get("is_user_move"):
                h6_move = move
                break
        
        assert h6_move is not None, "h6 move not found"
        
        # V4 LLM fields should be present for mistakes
        assert h6_move.get("narrative") is not None, "narrative missing"
        assert h6_move.get("thinking_gap") is not None, "thinking_gap missing"
        assert h6_move.get("position_breakdown") is not None, "position_breakdown missing"
        assert h6_move.get("mistake_analysis") is not None, "mistake_analysis missing"
        assert h6_move.get("better_plan") is not None, "better_plan missing"
        assert h6_move.get("principle") is not None, "principle missing"
        assert h6_move.get("confidence") is not None, "confidence missing"
    
    def test_h6_narrative_is_position_specific(self, api_client):
        """Verify h6 narrative is position-specific, not generic."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        data = response.json()
        
        h6_move = next((m for m in data["decryption_data"] if m.get("move_san") == "h6" and m.get("is_user_move")), None)
        assert h6_move is not None
        
        narrative = h6_move.get("narrative", "").lower()
        
        # Should NOT contain generic advice
        generic_phrases = ["control the center", "develop your pieces", "castle early"]
        for phrase in generic_phrases:
            assert phrase not in narrative, f"Narrative contains generic phrase: {phrase}"
        
        # Should be position-specific (mentions h6, development, or specific concepts)
        assert len(narrative) > 50, "Narrative too short to be meaningful"
    
    def test_h6_thinking_gap_explains_missed_question(self, api_client):
        """Verify thinking_gap explains what question user didn't ask."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        data = response.json()
        
        h6_move = next((m for m in data["decryption_data"] if m.get("move_san") == "h6" and m.get("is_user_move")), None)
        assert h6_move is not None
        
        thinking_gap = h6_move.get("thinking_gap", "")
        assert thinking_gap, "thinking_gap is empty"
        assert len(thinking_gap) > 20, "thinking_gap too short"
        
        # Should explain a thinking mistake, not just describe the move
        assert "develop" in thinking_gap.lower() or "priorit" in thinking_gap.lower() or "question" in thinking_gap.lower() or "ask" in thinking_gap.lower(), \
            "thinking_gap should explain the thinking mistake"
    
    def test_h6_position_breakdown_structure(self, api_client):
        """Verify position_breakdown has required sub-fields."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        data = response.json()
        
        h6_move = next((m for m in data["decryption_data"] if m.get("move_san") == "h6" and m.get("is_user_move")), None)
        assert h6_move is not None
        
        pb = h6_move.get("position_breakdown", {})
        assert pb.get("your_intent"), "position_breakdown.your_intent missing"
        assert pb.get("opponent_counterplay"), "position_breakdown.opponent_counterplay missing"
        assert pb.get("hidden_problem"), "position_breakdown.hidden_problem missing"
    
    def test_h6_mistake_analysis_structure(self, api_client):
        """Verify mistake_analysis has type, why_it_fails, severity."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        data = response.json()
        
        h6_move = next((m for m in data["decryption_data"] if m.get("move_san") == "h6" and m.get("is_user_move")), None)
        assert h6_move is not None
        
        ma = h6_move.get("mistake_analysis", {})
        
        # Type should be one of: strategic, tactical, calculation, impatience
        assert ma.get("type") in ["strategic", "tactical", "calculation", "impatience"], \
            f"Invalid mistake_analysis.type: {ma.get('type')}"
        
        assert ma.get("why_it_fails"), "mistake_analysis.why_it_fails missing"
        
        # Severity should be one of: inaccuracy, mistake, blunder
        assert ma.get("severity") in ["inaccuracy", "mistake", "blunder"], \
            f"Invalid mistake_analysis.severity: {ma.get('severity')}"
    
    def test_h6_better_plan_structure(self, api_client):
        """Verify better_plan has move, idea, what_happens_next."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        data = response.json()
        
        h6_move = next((m for m in data["decryption_data"] if m.get("move_san") == "h6" and m.get("is_user_move")), None)
        assert h6_move is not None
        
        bp = h6_move.get("better_plan", {})
        assert bp.get("move"), "better_plan.move missing"
        assert bp.get("idea"), "better_plan.idea missing"
        assert bp.get("what_happens_next"), "better_plan.what_happens_next missing"
    
    def test_h6_principle_is_position_specific(self, api_client):
        """Verify principle is position-specific, not generic."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        data = response.json()
        
        h6_move = next((m for m in data["decryption_data"] if m.get("move_san") == "h6" and m.get("is_user_move")), None)
        assert h6_move is not None
        
        principle = h6_move.get("principle", "").lower()
        assert principle, "principle is empty"
        
        # Should NOT be just "control the center"
        assert principle != "control the center", "Principle is too generic"
        assert len(principle) > 20, "Principle too short"
    
    def test_h6_confidence_field(self, api_client):
        """Verify confidence field is present with valid value."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        data = response.json()
        
        h6_move = next((m for m in data["decryption_data"] if m.get("move_san") == "h6" and m.get("is_user_move")), None)
        assert h6_move is not None
        
        confidence = h6_move.get("confidence")
        assert confidence in ["low", "medium", "high"], f"Invalid confidence: {confidence}"


class TestGoodMoveCoaching:
    """Tests for good move (non-mistake) coaching."""
    
    def test_good_move_has_short_narrative(self, api_client):
        """Verify good moves have short rule-based narratives."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        data = response.json()
        
        # Find e5 move (good move)
        e5_move = next((m for m in data["decryption_data"] if m.get("move_san") == "e5" and m.get("is_user_move")), None)
        assert e5_move is not None, "e5 move not found"
        
        # Good move should have narrative
        assert e5_move.get("narrative"), "Good move should have narrative"
        
        # Narrative should be short (rule-based, not LLM)
        narrative = e5_move.get("narrative", "")
        assert len(narrative) < 200, f"Good move narrative too long ({len(narrative)} chars), should be rule-based"
    
    def test_good_move_no_llm_fields(self, api_client):
        """Verify good moves don't have LLM-specific fields."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        data = response.json()
        
        # Find e5 move (good move)
        e5_move = next((m for m in data["decryption_data"] if m.get("move_san") == "e5" and m.get("is_user_move")), None)
        assert e5_move is not None
        
        # Good moves should NOT have LLM fields (or they should be None)
        assert e5_move.get("thinking_gap") is None, "Good move should not have thinking_gap"
        assert e5_move.get("position_breakdown") is None, "Good move should not have position_breakdown"


class TestSummaryV4:
    """Tests for V4 summary structure."""
    
    def test_summary_has_opening_introduction(self, api_client):
        """Verify summary includes opening_introduction."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        data = response.json()
        
        summary = data.get("summary", {})
        intro = summary.get("opening_introduction")
        
        assert intro is not None, "opening_introduction missing from summary"
        assert intro.get("name"), "opening_introduction.name missing"
        assert intro.get("description"), "opening_introduction.description missing"
        assert intro.get("your_plan"), "opening_introduction.your_plan missing"
        assert intro.get("their_plan"), "opening_introduction.their_plan missing"
    
    def test_summary_key_moments_use_thinking_gap(self, api_client):
        """Verify key_moments use thinking_gap for summary text."""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        data = response.json()
        
        summary = data.get("summary", {})
        key_moments = summary.get("key_moments", [])
        
        assert len(key_moments) > 0, "No key_moments in summary"
        
        # First key moment should have summary from thinking_gap
        km = key_moments[0]
        assert km.get("summary"), "key_moment.summary missing"
        assert km.get("type"), "key_moment.type missing"
        assert km.get("move_number"), "key_moment.move_number missing"


class TestFeedbackAPI:
    """Tests for feedback submission."""
    
    def test_feedback_submission_works(self, api_client):
        """Verify feedback can be submitted."""
        response = api_client.post(
            f"{BASE_URL}/api/coach/decryption/feedback",
            json={
                "game_id": TEST_GAME_ID,
                "move_number": 3,
                "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
                "coach_explanation": "V4 test explanation",
                "user_feedback": "not_helpful",
                "user_correction": "V4 pytest feedback test",
                "is_user_move": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True

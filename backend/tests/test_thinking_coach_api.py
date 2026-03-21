"""
Thinking Coach API Tests
========================

Tests for the Thinking Coach service endpoints that provide:
- Thought process walkthroughs
- Principle-based feedback
- Behavioral interventions
- Mindset prompts
- Pre-move checklists
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://mistake-fixer-1.preview.emergentagent.com').rstrip('/')


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def auth_session(api_client):
    """Get authenticated session via dev-login"""
    response = api_client.get(f"{BASE_URL}/api/auth/dev-login")
    if response.status_code == 200:
        return api_client
    pytest.skip("Authentication failed - skipping authenticated tests")


class TestThinkingCoachWalkthrough:
    """Tests for /api/thinking-coach/walkthrough endpoint"""
    
    def test_walkthrough_returns_valid_structure(self, api_client):
        """Test walkthrough endpoint returns proper structure"""
        response = api_client.post(
            f"{BASE_URL}/api/thinking-coach/walkthrough",
            json={
                "fen": "rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2",
                "best_move": "e5"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "phase" in data
        assert "focus" in data
        assert "walkthrough" in data
        assert "conclusion" in data
        assert "best_move" in data
        assert "key_takeaway" in data
        
        # Verify phase is valid
        assert data["phase"] in ["opening", "middlegame", "endgame"]
        
        # Verify walkthrough is a list with proper structure
        assert isinstance(data["walkthrough"], list)
        assert len(data["walkthrough"]) > 0
        
        for step in data["walkthrough"]:
            assert "phase" in step
            assert "question" in step
            assert "observation" in step
    
    def test_walkthrough_with_played_move(self, api_client):
        """Test walkthrough with both best_move and played_move"""
        response = api_client.post(
            f"{BASE_URL}/api/thinking-coach/walkthrough",
            json={
                "fen": "rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2",
                "best_move": "e5",
                "played_move": "Nc3"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["best_move"] == "e5"
        assert data["played_move"] == "Nc3"
    
    def test_walkthrough_opening_phase(self, api_client):
        """Test walkthrough identifies opening phase correctly"""
        response = api_client.post(
            f"{BASE_URL}/api/thinking-coach/walkthrough",
            json={
                "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
                "best_move": "e5"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["phase"] == "opening"
        assert "development" in data["focus"].lower() or "center" in data["focus"].lower()


class TestThinkingCoachPrincipleFeedback:
    """Tests for /api/thinking-coach/principle-feedback endpoint"""
    
    def test_principle_feedback_returns_valid_structure(self, api_client):
        """Test principle feedback endpoint returns proper structure"""
        response = api_client.post(
            f"{BASE_URL}/api/thinking-coach/principle-feedback",
            json={
                "mistake_type": "hanging_piece",
                "fen": "rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2",
                "move_played": "Qh5",
                "best_move": "e5"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "principle" in data
        assert "explanation" in data
        assert "thinking_habit" in data
        assert "applied_to_position" in data
        assert "what_to_do_instead" in data
        
        # For hanging_piece, principle should be "Safety First"
        assert data["principle"] == "Safety First"
    
    def test_principle_feedback_different_mistakes(self, api_client):
        """Test different mistake types return appropriate principles"""
        mistake_types = [
            ("hanging_piece", "Safety First"),
            ("missed_tactic", "Checks, Captures, Threats"),
            ("positional_error", "Piece Activity"),
            ("development_neglect", "Develop with Purpose"),
            ("king_safety_neglect", "King Safety is Priority")
        ]
        
        for mistake_type, expected_principle in mistake_types:
            response = api_client.post(
                f"{BASE_URL}/api/thinking-coach/principle-feedback",
                json={
                    "mistake_type": mistake_type,
                    "fen": "rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2",
                    "move_played": "a3",
                    "best_move": "Nc3"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["principle"] == expected_principle, f"Failed for {mistake_type}"


class TestThinkingCoachBehavioralIntervention:
    """Tests for /api/thinking-coach/behavioral-intervention endpoint"""
    
    def test_intervention_returns_valid_structure(self, api_client):
        """Test behavioral intervention endpoint returns proper structure"""
        response = api_client.post(
            f"{BASE_URL}/api/thinking-coach/behavioral-intervention",
            json={"behavioral_pattern": "hope_chess"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "pattern" in data
        assert "diagnosis" in data
        assert "intervention" in data
        assert "practice_rule" in data
        assert "examples" in data
        
        # For hope_chess
        assert data["pattern"] == "hope_chess"
        assert "opponent" in data["intervention"].lower()
    
    def test_intervention_different_patterns(self, api_client):
        """Test different behavioral patterns return appropriate interventions"""
        patterns = [
            "hope_chess",
            "impulsive_play",
            "tunnel_vision",
            "passive_play",
            "overextension",
            "material_obsession"
        ]
        
        for pattern in patterns:
            response = api_client.post(
                f"{BASE_URL}/api/thinking-coach/behavioral-intervention",
                json={"behavioral_pattern": pattern}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["pattern"] == pattern
            assert len(data["intervention"]) > 0


class TestThinkingCoachMindsetPrompt:
    """Tests for /api/thinking-coach/mindset-prompt endpoint"""
    
    def test_mindset_prompt_returns_valid_structure(self, api_client):
        """Test mindset prompt endpoint returns proper structure"""
        response = api_client.post(
            f"{BASE_URL}/api/thinking-coach/mindset-prompt",
            json={"fen": "rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "fen" in data
        assert "prompts" in data
        assert "recommended_thinking_time" in data
        
        # Prompts should be a list
        assert isinstance(data["prompts"], list)
        assert len(data["prompts"]) > 0
        
        # Each prompt should have required fields
        for prompt in data["prompts"]:
            assert "theme" in prompt
            assert "prompt" in prompt
            assert "what_to_look_for" in prompt
    
    def test_mindset_prompt_with_characteristics(self, api_client):
        """Test mindset prompt with position characteristics"""
        response = api_client.post(
            f"{BASE_URL}/api/thinking-coach/mindset-prompt",
            json={
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                "position_characteristics": {
                    "back_rank_weakness": True,
                    "undefended_pieces": False,
                    "king_exposed": False,
                    "pawn_break_available": False
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have prompts
        assert len(data["prompts"]) > 0


class TestThinkingCoachPreMoveChecklist:
    """Tests for /api/thinking-coach/pre-move-checklist endpoint"""
    
    def test_checklist_returns_valid_structure(self, auth_session):
        """Test pre-move checklist endpoint returns proper structure"""
        response = auth_session.get(
            f"{BASE_URL}/api/thinking-coach/pre-move-checklist",
            params={
                "move_number": 5,
                "has_castled": False,
                "developed_pieces": 2
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "checklist" in data
        assert "player_weaknesses" in data
        
        # Checklist should be a list
        assert isinstance(data["checklist"], list)
        
        # Each item should have required fields
        for item in data["checklist"]:
            assert "id" in item
            assert "question" in item
            assert "priority" in item
            assert "explanation" in item
            assert item["priority"] in ["high", "medium", "low"]
    
    def test_checklist_opening_phase(self, auth_session):
        """Test checklist returns opening-appropriate items"""
        response = auth_session.get(
            f"{BASE_URL}/api/thinking-coach/pre-move-checklist",
            params={
                "move_number": 3,
                "has_castled": False,
                "developed_pieces": 1
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # In early opening, should include center check
        checklist_ids = [item["id"] for item in data["checklist"]]
        assert "center_check" in checklist_ids or "development_check" in checklist_ids
    
    def test_checklist_castling_reminder(self, auth_session):
        """Test checklist reminds about castling when appropriate"""
        response = auth_session.get(
            f"{BASE_URL}/api/thinking-coach/pre-move-checklist",
            params={
                "move_number": 7,
                "has_castled": False,
                "developed_pieces": 3
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should include castle check when not castled by move 7
        checklist_ids = [item["id"] for item in data["checklist"]]
        assert "castle_check" in checklist_ids
    
    def test_checklist_after_castling(self, auth_session):
        """Test checklist doesn't nag about castling if already castled"""
        response = auth_session.get(
            f"{BASE_URL}/api/thinking-coach/pre-move-checklist",
            params={
                "move_number": 8,
                "has_castled": True,
                "developed_pieces": 4
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should NOT include castle check if already castled
        checklist_ids = [item["id"] for item in data["checklist"]]
        assert "castle_check" not in checklist_ids
    
    def test_checklist_threat_check_in_middlegame(self, auth_session):
        """Test checklist includes threat check in middlegame"""
        response = auth_session.get(
            f"{BASE_URL}/api/thinking-coach/pre-move-checklist",
            params={
                "move_number": 12,
                "has_castled": True,
                "developed_pieces": 4
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should include threat check
        checklist_ids = [item["id"] for item in data["checklist"]]
        assert "threat_check" in checklist_ids
    
    def test_checklist_limited_to_three_items(self, auth_session):
        """Test checklist returns at most 3 items"""
        response = auth_session.get(
            f"{BASE_URL}/api/thinking-coach/pre-move-checklist",
            params={
                "move_number": 5,
                "has_castled": False,
                "developed_pieces": 1
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have at most 3 items
        assert len(data["checklist"]) <= 3

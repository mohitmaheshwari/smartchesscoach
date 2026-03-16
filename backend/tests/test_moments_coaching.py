"""
Test Moments Tab - Interactive Training Loop

Tests:
- /api/lab/{gameId}/deep-strategy returns coaching object in each critical_moment
- Coaching object structure: thinking_lens, coach_prompt, thinking_questions, lesson_takeaway, reflection

Testing the new guided flow for the Moments tab:
INTRO -> THINKING -> REVEAL -> REFLECTION -> LESSON
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test game ID with known data (has 5 critical moments)
TEST_GAME_ID = "cb946acd-7871-4d38-a704-6c3ccbe968c5"


class TestDeepStrategyCoaching:
    """Tests for /api/lab/{gameId}/deep-strategy endpoint coaching objects"""
    
    def test_deep_strategy_returns_200(self):
        """Deep strategy endpoint should return 200 for valid game"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Deep strategy endpoint returns 200")
    
    def test_deep_strategy_returns_critical_moments(self):
        """Should return critical_moments array"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        assert "critical_moments" in data, "Response should have critical_moments field"
        assert isinstance(data["critical_moments"], list), "critical_moments should be a list"
        assert len(data["critical_moments"]) >= 1, "Should have at least 1 critical moment"
        print(f"PASS: critical_moments array has {len(data['critical_moments'])} items")
    
    def test_critical_moment_has_coaching_object(self):
        """Each critical moment should have a coaching object"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        moments = data.get("critical_moments", [])
        assert len(moments) >= 1, "Should have at least 1 moment"
        
        moment = moments[0]
        assert "coaching" in moment, "Moment should have coaching object"
        assert isinstance(moment["coaching"], dict), "coaching should be a dictionary"
        print(f"PASS: First moment has coaching object")
    
    def test_coaching_has_thinking_lens(self):
        """Coaching object should have thinking_lens with label, text, icon"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        moment = data["critical_moments"][0]
        coaching = moment.get("coaching", {})
        
        assert "thinking_lens" in coaching, "coaching should have thinking_lens"
        lens = coaching["thinking_lens"]
        
        assert "label" in lens, "thinking_lens should have label"
        assert "text" in lens, "thinking_lens should have text"
        assert "icon" in lens, "thinking_lens should have icon"
        
        assert lens["label"], "label should not be empty"
        assert lens["text"], "text should not be empty"
        assert lens["icon"], "icon should not be empty"
        
        print(f"PASS: thinking_lens = {lens['label']}")
    
    def test_coaching_has_coach_prompt(self):
        """Coaching object should have coach_prompt string"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        moment = data["critical_moments"][0]
        coaching = moment.get("coaching", {})
        
        assert "coach_prompt" in coaching, "coaching should have coach_prompt"
        assert isinstance(coaching["coach_prompt"], str), "coach_prompt should be a string"
        assert len(coaching["coach_prompt"]) > 10, "coach_prompt should have content"
        
        print(f"PASS: coach_prompt = '{coaching['coach_prompt'][:50]}...'")
    
    def test_coaching_has_thinking_questions(self):
        """Coaching object should have thinking_questions array of 3 questions"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        moment = data["critical_moments"][0]
        coaching = moment.get("coaching", {})
        
        assert "thinking_questions" in coaching, "coaching should have thinking_questions"
        questions = coaching["thinking_questions"]
        
        assert isinstance(questions, list), "thinking_questions should be a list"
        assert len(questions) == 3, f"Should have exactly 3 questions, got {len(questions)}"
        
        for i, q in enumerate(questions):
            assert isinstance(q, str), f"Question {i+1} should be a string"
            assert len(q) > 10, f"Question {i+1} should have content"
        
        print(f"PASS: thinking_questions has {len(questions)} questions")
    
    def test_coaching_has_lesson_takeaway(self):
        """Coaching object should have lesson_takeaway string"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        moment = data["critical_moments"][0]
        coaching = moment.get("coaching", {})
        
        assert "lesson_takeaway" in coaching, "coaching should have lesson_takeaway"
        assert isinstance(coaching["lesson_takeaway"], str), "lesson_takeaway should be a string"
        assert len(coaching["lesson_takeaway"]) > 10, "lesson_takeaway should have content"
        
        print(f"PASS: lesson_takeaway = '{coaching['lesson_takeaway'][:50]}...'")
    
    def test_coaching_has_reflection(self):
        """Coaching object should have reflection with prompt and options"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        moment = data["critical_moments"][0]
        coaching = moment.get("coaching", {})
        
        assert "reflection" in coaching, "coaching should have reflection"
        reflection = coaching["reflection"]
        
        assert "prompt" in reflection, "reflection should have prompt"
        assert "options" in reflection, "reflection should have options"
        
        assert isinstance(reflection["prompt"], str), "prompt should be a string"
        assert len(reflection["prompt"]) > 10, "prompt should have content"
        
        print(f"PASS: reflection.prompt = '{reflection['prompt']}'")
    
    def test_reflection_options_structure(self):
        """Reflection options should have id and label"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        moment = data["critical_moments"][0]
        reflection = moment.get("coaching", {}).get("reflection", {})
        options = reflection.get("options", [])
        
        assert len(options) == 4, f"Should have 4 options, got {len(options)}"
        
        for i, opt in enumerate(options):
            assert "id" in opt, f"Option {i+1} should have id"
            assert "label" in opt, f"Option {i+1} should have label"
            assert opt["id"], f"Option {i+1} id should not be empty"
            assert opt["label"], f"Option {i+1} label should not be empty"
        
        print(f"PASS: reflection has {len(options)} options with id and label")
    
    def test_all_moments_have_coaching(self):
        """All critical moments should have coaching objects"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        moments = data.get("critical_moments", [])
        
        for i, moment in enumerate(moments):
            assert "coaching" in moment, f"Moment {i+1} should have coaching"
            coaching = moment["coaching"]
            
            assert "thinking_lens" in coaching, f"Moment {i+1} coaching missing thinking_lens"
            assert "coach_prompt" in coaching, f"Moment {i+1} coaching missing coach_prompt"
            assert "thinking_questions" in coaching, f"Moment {i+1} coaching missing thinking_questions"
            assert "lesson_takeaway" in coaching, f"Moment {i+1} coaching missing lesson_takeaway"
            assert "reflection" in coaching, f"Moment {i+1} coaching missing reflection"
        
        print(f"PASS: All {len(moments)} moments have complete coaching objects")


class TestMomentDataStructure:
    """Tests for other required fields in critical moments"""
    
    def test_moment_has_move_info(self):
        """Each moment should have move_number, your_move, best_move"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        moment = data["critical_moments"][0]
        
        assert "move_number" in moment, "Moment should have move_number"
        assert "your_move" in moment, "Moment should have your_move"
        assert "best_move" in moment, "Moment should have best_move"
        
        print(f"PASS: Move {moment['move_number']}: played {moment['your_move']}, best {moment['best_move']}")
    
    def test_moment_has_fen(self):
        """Each moment should have fen for board position"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        moment = data["critical_moments"][0]
        
        assert "fen" in moment, "Moment should have fen"
        assert moment["fen"], "fen should not be empty"
        assert " " in moment["fen"], "fen should be valid FEN format with spaces"
        
        print(f"PASS: Moment has FEN position")
    
    def test_moment_has_insight(self):
        """Each moment should have insight object"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/deep-strategy")
        data = response.json()
        
        moment = data["critical_moments"][0]
        
        assert "insight" in moment, "Moment should have insight"
        insight = moment["insight"]
        
        # insight should have what_best_move_achieves at minimum
        assert isinstance(insight, dict), "insight should be a dictionary"
        
        print(f"PASS: Moment has insight object")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

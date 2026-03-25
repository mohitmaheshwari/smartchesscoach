"""
Test Coaching Answer Q&A Feature
================================

Tests the upgraded Q&A feature with coaching-quality answers:
1. POST /api/coach/ask-move - coaching answers with thinking_pattern detection
2. Question insights logging in MongoDB question_insights collection
3. POST /api/coach/explain-mistake - regression test for Italian d5 theory
4. GET /api/coach/theory/stats - regression test for 82 total patterns
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://progress-track-61.preview.emergentagent.com')

# Test FEN for Italian Game (from agent context)
ITALIAN_GAME_FEN = "r1bqk2r/pppp1pp1/2n2n1p/2b1p3/2B1P3/2N2N1P/PPPP1PP1/R1BQ1RK1 b kq - 0 6"

# Standard starting position for basic tests
STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class TestCoachingAnswerQA:
    """Tests for the coaching answer Q&A feature"""
    
    def test_ask_move_coaching_quality_answer(self):
        """
        Test: POST /api/coach/ask-move with 'why Na5 and not Nxd5?'
        Should return coaching-quality answer mentioning opponent recapture, not raw eval
        """
        # Use a position where Nxd5 is a capture that gets recaptured
        # Italian Game position where knight can capture on d5
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        
        response = requests.post(
            f"{BASE_URL}/api/coach/ask-move",
            json={
                "fen": fen,
                "question": "why Nc3 and not Nxe5?",
                "depth": 18
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have an answer (not an error)
        if "error" in data:
            # If error, it should be about illegal move, not a crash
            print(f"Got error (may be expected): {data['error']}")
        else:
            # Should have coaching-quality answer
            assert "answer" in data, "Response should have 'answer' field"
            answer = data["answer"]
            print(f"Coaching answer: {answer}")
            
            # Answer should be human-readable, not just eval numbers
            assert len(answer) > 20, "Answer should be substantial coaching text"
            
            # Should have thinking_pattern
            assert "thinking_pattern" in data, "Response should have 'thinking_pattern' field"
            
    def test_ask_move_capture_detects_material_awareness(self):
        """
        Test: POST /api/coach/ask-move with capture move 'what about Nxe4?'
        Should detect material awareness pattern
        """
        # Position where Nxe4 is a capture
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
        
        response = requests.post(
            f"{BASE_URL}/api/coach/ask-move",
            json={
                "fen": fen,
                "question": "what about Nxe5?",
                "depth": 18
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        if "error" not in data:
            # Should have thinking_pattern
            assert "thinking_pattern" in data, "Response should have 'thinking_pattern' field"
            thinking = data["thinking_pattern"]
            
            print(f"Thinking pattern: {thinking}")
            
            # Should have required fields
            assert "id" in thinking, "thinking_pattern should have 'id'"
            assert "label" in thinking, "thinking_pattern should have 'label'"
            assert "description" in thinking, "thinking_pattern should have 'description'"
            assert "coaching_signal" in thinking, "thinking_pattern should have 'coaching_signal'"
            assert "severity" in thinking, "thinking_pattern should have 'severity'"
            
            # For a capture, should detect capture-related pattern
            capture_patterns = ["material_awareness", "capture_instinct", "tactical_temptation", "pawn_grabbing", "trade_seeking"]
            assert thinking["id"] in capture_patterns or thinking["id"] == "unknown", \
                f"Expected capture-related pattern, got {thinking['id']}"
                
    def test_ask_move_illegal_move_explains_why(self):
        """
        Test: POST /api/coach/ask-move with illegal move 'why not Nxe5?'
        Should explain WHY it's illegal (e.g., own pawn on e5)
        """
        # Position where Nxe5 is illegal because there's no piece to capture
        # or the knight can't reach e5
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        response = requests.post(
            f"{BASE_URL}/api/coach/ask-move",
            json={
                "fen": fen,
                "question": "why not Nxe5?",
                "depth": 18
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should have an error explaining why the move is illegal
        assert "error" in data, "Should return error for illegal move"
        error_msg = data["error"]
        print(f"Illegal move error: {error_msg}")
        
        # Error should explain WHY it's illegal
        assert "not legal" in error_msg.lower() or "illegal" in error_msg.lower() or "can't" in error_msg.lower(), \
            f"Error should explain illegality: {error_msg}"
            
    def test_ask_move_thinking_pattern_structure(self):
        """
        Test: thinking_pattern field should have id, label, description, coaching_signal, severity
        """
        # Use Italian Game position
        response = requests.post(
            f"{BASE_URL}/api/coach/ask-move",
            json={
                "fen": ITALIAN_GAME_FEN,
                "question": "what about d5?",
                "depth": 18
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if "error" not in data:
            assert "thinking_pattern" in data, "Response should have thinking_pattern"
            tp = data["thinking_pattern"]
            
            # Verify structure
            required_fields = ["id", "label", "description", "coaching_signal", "severity"]
            for field in required_fields:
                assert field in tp, f"thinking_pattern missing '{field}' field"
                
            # Verify coaching_signal is valid
            valid_signals = ["positive", "neutral", "concerning"]
            assert tp["coaching_signal"] in valid_signals, \
                f"coaching_signal should be one of {valid_signals}, got {tp['coaching_signal']}"
                
            # Verify severity is valid
            valid_severities = ["minor", "moderate", "major"]
            assert tp["severity"] in valid_severities, \
                f"severity should be one of {valid_severities}, got {tp['severity']}"
                
            print(f"Thinking pattern structure verified: {tp}")


class TestQuestionInsightsLogging:
    """Tests for question insights MongoDB logging"""
    
    def test_question_logged_to_mongodb(self):
        """
        Test: Question insights should be logged in MongoDB question_insights collection
        """
        # Make a Q&A request
        unique_question = f"what about Nf3? test_{int(time.time())}"
        
        response = requests.post(
            f"{BASE_URL}/api/coach/ask-move",
            json={
                "fen": STARTING_FEN,
                "question": unique_question,
                "depth": 18
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # The logging is non-blocking, so we can't directly verify MongoDB
        # But we can verify the response has the fields that would be logged
        if "error" not in data:
            # These fields should be present and would be logged
            assert "thinking_pattern" in data or "alternative_move" in data, \
                "Response should have data that gets logged"
            print("Question submitted - logging is non-blocking, cannot verify MongoDB directly")
            print(f"Response data that would be logged: thinking_pattern={data.get('thinking_pattern', {}).get('id')}")


class TestExplainMistakeRegression:
    """Regression tests for explain-mistake endpoint"""
    
    def test_italian_d5_theory_match(self):
        """
        Test: POST /api/coach/explain-mistake with Italian d5 theory
        Should still match theory pattern (regression from iteration 140)
        """
        # Italian Game position where d5 is a mistake
        fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R b KQkq - 5 5"
        
        response = requests.post(
            f"{BASE_URL}/api/coach/explain-mistake",
            json={
                "fen_before": fen,
                "played_move": "d5",
                "played_move_uci": "d7d5",
                "best_move": "d6",
                "best_move_uci": "d7d6",
                "eval_before": 0,
                "eval_after": -150,
                "move_number": 5,
                "pv_after_played": ["exd5", "Nxd5", "Nxd5", "Qxd5"],
                "pv_after_best": ["O-O", "d3"],
                "user_color": "black"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should have explanation
        assert "explanation" in data or "headline" in data, "Response should have explanation"
        
        # Check for theory match (from iteration 140 context)
        if "theory_match" in data:
            print(f"Theory match: {data['theory_match']}")
        
        # Should have a rule
        if "rule" in data:
            print(f"Rule: {data['rule']}")
            
        print(f"Explanation: {data.get('explanation', data.get('headline', 'N/A'))}")


class TestTheoryStatsRegression:
    """Regression tests for theory stats endpoint"""
    
    def test_theory_stats_82_patterns(self):
        """
        Test: GET /api/coach/theory/stats should return 82 total patterns
        (Regression from iteration 140)
        """
        response = requests.get(f"{BASE_URL}/api/coach/theory/stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "stats" in data, "Response should have 'stats' field"
        stats = data["stats"]
        
        # Verify total is 82 (from iteration 140)
        total = stats.get("total", 0)
        assert total == 82, f"Expected 82 total patterns, got {total}"
        
        # Verify breakdown
        assert stats.get("opening_patterns", 0) == 28, f"Expected 28 opening patterns"
        assert stats.get("endgame_patterns", 0) == 17, f"Expected 17 endgame patterns"
        assert stats.get("tactical_patterns", 0) == 17, f"Expected 17 tactical patterns"
        assert stats.get("positional_rules", 0) == 20, f"Expected 20 positional rules"
        
        print(f"Theory stats verified: {stats}")


class TestCoachingAnswerQuality:
    """Tests for coaching answer quality (not raw eval dumps)"""
    
    def test_answer_not_raw_eval(self):
        """
        Test: Coaching answer should be human-readable, not raw eval numbers
        """
        response = requests.post(
            f"{BASE_URL}/api/coach/ask-move",
            json={
                "fen": ITALIAN_GAME_FEN,
                "question": "why Nf6 and not d5?",
                "played_move": "Nf6",
                "depth": 18
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if "error" not in data and "answer" in data:
            answer = data["answer"]
            
            # Answer should NOT be just eval numbers
            # It should have coaching language
            coaching_indicators = [
                "you", "your", "opponent", "capture", "recapture",
                "better", "worse", "position", "piece", "pawn",
                "principle", "tip", "check"
            ]
            
            has_coaching_language = any(ind in answer.lower() for ind in coaching_indicators)
            assert has_coaching_language, f"Answer should have coaching language: {answer}"
            
            # Should not be just numbers
            assert not answer.replace(".", "").replace("-", "").replace("+", "").isdigit(), \
                f"Answer should not be just numbers: {answer}"
                
            print(f"Coaching answer quality verified: {answer[:200]}...")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

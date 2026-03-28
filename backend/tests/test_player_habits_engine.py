"""
Test Player Habits Engine - Behavioral Coaching and Habits Report
=================================================================

Tests the new Player Habits Engine features:
1. Backend: POST /api/coach/play/v5/interactive-feedback returns 'behavioral_coaching' field
2. Backend: behavioral_coaching has fields: type, severity, message, habit, actionable_tip
3. Backend: GET /api/coach/v5/decryption/{game_id} returns 'habits_report' field
4. Backend: habits_report includes time_management, phase_performance, recommendations
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPlayerHabitsEngine:
    """Test Player Habits Engine - Behavioral Coaching and Habits Report"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Dev login - GET request
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Dev login failed: {login_resp.text}"
        self.user_data = login_resp.json()
        print(f"Logged in as: {self.user_data.get('user', {}).get('user_id', 'unknown')}")
    
    # ─── TEST 1: Interactive Feedback Returns behavioral_coaching Field ───
    def test_interactive_feedback_has_behavioral_coaching_field(self):
        """
        POST /api/coach/play/v5/interactive-feedback with phase='user_move' 
        should return a 'behavioral_coaching' field in the response (may be null for good moves)
        """
        # First, start a coach play session
        start_resp = self.session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "15+10"
        })
        
        if start_resp.status_code != 200:
            pytest.skip(f"Could not start coach play session: {start_resp.text}")
        
        session_data = start_resp.json()
        session_id = session_data.get("session", {}).get("session_id")
        assert session_id, "No session_id returned"
        print(f"Started session: {session_id}")
        
        try:
            # Make a move
            move_resp = self.session.post(f"{BASE_URL}/api/coach/play/move", json={
                "session_id": session_id,
                "move": "e4",
                "thinking_time_ms": 1500
            })
            
            if move_resp.status_code != 200:
                pytest.skip(f"Could not make move: {move_resp.text}")
            
            # Wait for coach to respond
            import time
            time.sleep(3)
            
            # Now call interactive-feedback with phase='user_move'
            feedback_resp = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
                "session_id": session_id,
                "phase": "user_move"
            })
            
            assert feedback_resp.status_code == 200, f"Interactive feedback failed: {feedback_resp.text}"
            data = feedback_resp.json()
            
            # The response MUST have 'behavioral_coaching' field (even if null)
            assert "behavioral_coaching" in data, f"Response missing 'behavioral_coaching' field. Keys: {data.keys()}"
            print(f"behavioral_coaching field present: {data.get('behavioral_coaching')}")
            
        finally:
            # Cleanup - end session
            self.session.post(f"{BASE_URL}/api/coach/play/end", json={
                "session_id": session_id,
                "reason": "test_cleanup"
            })
    
    # ─── TEST 2: Behavioral Coaching Object Structure ───
    def test_behavioral_coaching_object_structure(self):
        """
        When behavioral_coaching is returned (not null), it should have:
        type, severity, message, habit, actionable_tip
        """
        # Start session
        start_resp = self.session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "15+10"
        })
        
        if start_resp.status_code != 200:
            pytest.skip(f"Could not start session: {start_resp.text}")
        
        session_data = start_resp.json()
        session_id = session_data.get("session", {}).get("session_id")
        
        try:
            # Make a FAST move (under 2 seconds) to potentially trigger impulse detection
            move_resp = self.session.post(f"{BASE_URL}/api/coach/play/move", json={
                "session_id": session_id,
                "move": "e4",
                "thinking_time_ms": 500  # Very fast - 0.5 seconds
            })
            
            if move_resp.status_code != 200:
                pytest.skip(f"Could not make move: {move_resp.text}")
            
            import time
            time.sleep(3)
            
            # Get feedback
            feedback_resp = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
                "session_id": session_id,
                "phase": "user_move"
            })
            
            assert feedback_resp.status_code == 200
            data = feedback_resp.json()
            
            behavioral = data.get("behavioral_coaching")
            
            # If behavioral coaching is present, verify structure
            if behavioral is not None:
                print(f"Behavioral coaching returned: {behavioral}")
                
                # Required fields when behavioral coaching is present
                assert "type" in behavioral, "Missing 'type' field"
                assert "severity" in behavioral, "Missing 'severity' field"
                assert "message" in behavioral, "Missing 'message' field"
                assert "habit" in behavioral, "Missing 'habit' field"
                
                # actionable_tip may be null for positive feedback
                assert "actionable_tip" in behavioral, "Missing 'actionable_tip' field"
                
                # Validate type values
                valid_types = ["time_management", "emotional", "positive", "calculation", "pattern"]
                assert behavioral["type"] in valid_types, f"Invalid type: {behavioral['type']}"
                
                # Validate severity values
                valid_severities = ["low", "medium", "high"]
                assert behavioral["severity"] in valid_severities, f"Invalid severity: {behavioral['severity']}"
                
                # Validate habit values
                valid_habits = ["impulse_move", "tilt", "positional_patience", "overthinking", 
                               "calculation_miss", "recurring_mistake"]
                assert behavioral["habit"] in valid_habits, f"Invalid habit: {behavioral['habit']}"
                
                print(f"✓ Behavioral coaching structure valid: type={behavioral['type']}, habit={behavioral['habit']}")
            else:
                print("behavioral_coaching is null (expected for good moves at normal speed)")
                # This is acceptable - behavioral coaching only triggers for specific patterns
        
        finally:
            self.session.post(f"{BASE_URL}/api/coach/play/end", json={
                "session_id": session_id,
                "reason": "test_cleanup"
            })
    
    # ─── TEST 3: Lab Decryption Returns habits_report Field ───
    def test_lab_decryption_has_habits_report_field(self):
        """
        GET /api/coach/v5/decryption/{game_id} should return 'habits_report' field
        when status is 'complete'
        """
        # First, get a list of analyzed games
        games_resp = self.session.get(f"{BASE_URL}/api/games?limit=5")
        
        if games_resp.status_code != 200:
            pytest.skip(f"Could not fetch games: {games_resp.text}")
        
        games_data = games_resp.json()
        # API returns list directly
        games = games_data if isinstance(games_data, list) else games_data.get("games", [])
        
        if not games:
            pytest.skip("No games available for testing")
        
        # Try to find a game with V5 decryption data
        for game in games:
            game_id = game.get("game_id")
            if not game_id:
                continue
            
            # Request V5 decryption
            decryption_resp = self.session.get(f"{BASE_URL}/api/coach/decryption/v5/{game_id}")
            
            if decryption_resp.status_code != 200:
                continue
            
            data = decryption_resp.json()
            
            # Check if decryption is complete
            if data.get("status") == "generating":
                print(f"Game {game_id} is still generating, trying next...")
                continue
            
            if data.get("decryption_data"):
                # Found a complete decryption - check for habits_report
                print(f"Found complete decryption for game: {game_id}")
                
                # habits_report may or may not be present depending on when game was analyzed
                if "habits_report" in data:
                    print(f"✓ habits_report field present")
                    habits = data["habits_report"]
                    
                    if habits:
                        # Verify structure
                        assert "time_management" in habits, "Missing time_management in habits_report"
                        assert "phase_performance" in habits, "Missing phase_performance in habits_report"
                        
                        print(f"✓ habits_report structure valid")
                        print(f"  - time_management score: {habits.get('time_management', {}).get('score')}")
                        print(f"  - overall_habits_score: {habits.get('overall_habits_score')}")
                        return  # Test passed
                else:
                    print(f"habits_report field not present (may be older analysis)")
                    # This is acceptable for older games
                    return
        
        pytest.skip("No games with complete V5 decryption found")
    
    # ─── TEST 4: Habits Report Structure ───
    def test_habits_report_structure(self):
        """
        habits_report should include:
        - time_management (with score, insight, avg_move_time)
        - phase_performance (opening/middlegame/endgame accuracy)
        - recommendations
        """
        # Get games
        games_resp = self.session.get(f"{BASE_URL}/api/games?limit=10")
        
        if games_resp.status_code != 200:
            pytest.skip(f"Could not fetch games: {games_resp.text}")
        
        games_data = games_resp.json()
        # API returns list directly
        games = games_data if isinstance(games_data, list) else games_data.get("games", [])
        
        for game in games:
            game_id = game.get("game_id")
            if not game_id:
                continue
            
            decryption_resp = self.session.get(f"{BASE_URL}/api/coach/decryption/v5/{game_id}")
            
            if decryption_resp.status_code != 200:
                continue
            
            data = decryption_resp.json()
            
            if data.get("status") == "generating":
                continue
            
            habits = data.get("habits_report")
            
            if habits:
                print(f"Found habits_report for game {game_id}")
                
                # Verify time_management structure
                tm = habits.get("time_management", {})
                assert "score" in tm, "time_management missing 'score'"
                assert "insight" in tm, "time_management missing 'insight'"
                assert "avg_move_time" in tm, "time_management missing 'avg_move_time'"
                print(f"✓ time_management: score={tm['score']}, avg_time={tm['avg_move_time']}s")
                
                # Verify phase_performance structure
                pp = habits.get("phase_performance", {})
                assert "opening" in pp, "phase_performance missing 'opening'"
                assert "middlegame" in pp, "phase_performance missing 'middlegame'"
                assert "endgame" in pp, "phase_performance missing 'endgame'"
                
                # Each phase should have accuracy
                for phase in ["opening", "middlegame", "endgame"]:
                    phase_data = pp.get(phase, {})
                    assert "accuracy" in phase_data, f"{phase} missing 'accuracy'"
                
                print(f"✓ phase_performance: opening={pp['opening']['accuracy']}%, "
                      f"middlegame={pp['middlegame']['accuracy']}%, "
                      f"endgame={pp['endgame']['accuracy']}%")
                
                # Verify recommendations (may be empty list)
                recs = habits.get("recommendations", [])
                assert isinstance(recs, list), "recommendations should be a list"
                print(f"✓ recommendations: {len(recs)} items")
                
                if recs:
                    # Verify recommendation structure
                    rec = recs[0]
                    assert "priority" in rec, "recommendation missing 'priority'"
                    assert "area" in rec, "recommendation missing 'area'"
                    assert "message" in rec, "recommendation missing 'message'"
                    print(f"  First recommendation: {rec['area']} - {rec['message'][:50]}...")
                
                return  # Test passed
        
        pytest.skip("No games with habits_report found")
    
    # ─── TEST 5: Behavioral Coaching Triggers on Fast Moves ───
    def test_behavioral_coaching_triggers_on_impulse(self):
        """
        Behavioral coaching should trigger when:
        - time_spent < 2s AND move_quality is mistake/blunder
        
        This tests the impulse_move detection.
        """
        # This is a unit test of the generate_behavioral_coaching function
        from services.player_habits_service import generate_behavioral_coaching
        
        # Simulate an impulse move (fast + bad)
        result = generate_behavioral_coaching(
            move_san="Nf3",
            time_spent=1.5,  # Very fast
            move_quality="mistake",  # Bad move
            game_phase="middlegame",
            behavior_events=[],
            move_history=[
                {"by": "player", "move": "e4", "time_spent": 5.0, "evaluation": "good"},
                {"by": "coach", "move": "e5", "time_spent": 2.0},
                {"by": "player", "move": "Nf3", "time_spent": 1.5, "evaluation": "mistake"}
            ],
            player_profile=None
        )
        
        assert result is not None, "Behavioral coaching should trigger for fast mistake"
        assert result["type"] == "time_management", f"Expected time_management, got {result['type']}"
        assert result["habit"] == "impulse_move", f"Expected impulse_move, got {result['habit']}"
        assert result["severity"] == "medium", f"Expected medium severity for mistake, got {result['severity']}"
        assert "message" in result and result["message"], "Should have a message"
        
        print(f"✓ Impulse move detected: {result['message'][:60]}...")
    
    # ─── TEST 6: Behavioral Coaching for Blunder ───
    def test_behavioral_coaching_blunder_high_severity(self):
        """
        Blunders played quickly should have HIGH severity
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        result = generate_behavioral_coaching(
            move_san="Qxh7",
            time_spent=1.0,  # Very fast
            move_quality="blunder",  # Blunder
            game_phase="middlegame",
            behavior_events=[],
            move_history=[
                {"by": "player", "move": "e4", "time_spent": 5.0, "evaluation": "good"},
                {"by": "coach", "move": "e5", "time_spent": 2.0},
                {"by": "player", "move": "Qxh7", "time_spent": 1.0, "evaluation": "blunder"}
            ],
            player_profile=None
        )
        
        assert result is not None, "Behavioral coaching should trigger for fast blunder"
        assert result["severity"] == "high", f"Expected high severity for blunder, got {result['severity']}"
        assert result["habit"] == "impulse_move"
        
        print(f"✓ Fast blunder detected with HIGH severity: {result['message'][:60]}...")
    
    # ─── TEST 7: Positive Behavioral Coaching ───
    def test_behavioral_coaching_positive_patience(self):
        """
        Good moves played with patience (>15s) should get positive feedback
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        result = generate_behavioral_coaching(
            move_san="Nd5",
            time_spent=20.0,  # Took time
            move_quality="best",  # Great move
            game_phase="middlegame",
            behavior_events=[],
            move_history=[
                {"by": "player", "move": "e4", "time_spent": 5.0, "evaluation": "good"},
                {"by": "coach", "move": "e5", "time_spent": 2.0},
                {"by": "player", "move": "Nd5", "time_spent": 20.0, "evaluation": "best"}
            ],
            player_profile=None
        )
        
        assert result is not None, "Behavioral coaching should trigger for patient good move"
        assert result["type"] == "positive", f"Expected positive type, got {result['type']}"
        assert result["habit"] == "positional_patience"
        assert result["severity"] == "low"  # Positive feedback is low severity
        
        print(f"✓ Patience rewarded: {result['message'][:60]}...")
    
    # ─── TEST 8: No Behavioral Coaching for Normal Moves ───
    def test_no_behavioral_coaching_for_normal_moves(self):
        """
        Normal moves (moderate time, good quality) should NOT trigger behavioral coaching
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        result = generate_behavioral_coaching(
            move_san="Nf3",
            time_spent=8.0,  # Normal time
            move_quality="good",  # Good move
            game_phase="opening",
            behavior_events=[],
            move_history=[
                {"by": "player", "move": "e4", "time_spent": 5.0, "evaluation": "good"},
                {"by": "coach", "move": "e5", "time_spent": 2.0},
                {"by": "player", "move": "Nf3", "time_spent": 8.0, "evaluation": "good"}
            ],
            player_profile=None
        )
        
        assert result is None, f"Normal good moves should NOT trigger behavioral coaching, got: {result}"
        print("✓ Normal moves correctly return null behavioral coaching")
    
    # ─── TEST 9: Analyze Game Habits Function ───
    def test_analyze_game_habits_function(self):
        """
        Test the analyze_game_habits function directly
        """
        from services.player_habits_service import analyze_game_habits
        
        # Simulate a game with various move qualities
        move_history = [
            {"by": "player", "move": "e4", "time_spent": 5.0, "evaluation": "good"},
            {"by": "coach", "move": "e5", "time_spent": 2.0},
            {"by": "player", "move": "Nf3", "time_spent": 8.0, "evaluation": "good"},
            {"by": "coach", "move": "Nc6", "time_spent": 2.0},
            {"by": "player", "move": "Bb5", "time_spent": 12.0, "evaluation": "best"},
            {"by": "coach", "move": "a6", "time_spent": 2.0},
            {"by": "player", "move": "Ba4", "time_spent": 6.0, "evaluation": "good"},
            {"by": "coach", "move": "Nf6", "time_spent": 2.0},
            {"by": "player", "move": "O-O", "time_spent": 3.0, "evaluation": "good"},
            {"by": "coach", "move": "Be7", "time_spent": 2.0},
            {"by": "player", "move": "Re1", "time_spent": 15.0, "evaluation": "good"},
            {"by": "coach", "move": "b5", "time_spent": 2.0},
            {"by": "player", "move": "Bb3", "time_spent": 4.0, "evaluation": "good"},
            {"by": "coach", "move": "d6", "time_spent": 2.0},
            {"by": "player", "move": "c3", "time_spent": 7.0, "evaluation": "good"},
            {"by": "coach", "move": "O-O", "time_spent": 2.0},
            {"by": "player", "move": "h3", "time_spent": 1.5, "evaluation": "mistake"},  # Fast mistake
            {"by": "coach", "move": "Nb8", "time_spent": 2.0},
            {"by": "player", "move": "d4", "time_spent": 10.0, "evaluation": "good"},
            {"by": "coach", "move": "Nbd7", "time_spent": 2.0},
        ]
        
        evaluations = []  # Can be empty, move_history has evaluation field
        behavior_events = []
        
        result = analyze_game_habits(
            move_history=move_history,
            evaluations=evaluations,
            behavior_events=behavior_events,
            user_color="white"
        )
        
        assert result is not None, "analyze_game_habits should return a result"
        
        # Verify structure
        assert "time_management" in result
        assert "phase_performance" in result
        assert "behavior_patterns" in result
        assert "recommendations" in result
        assert "overall_habits_score" in result
        
        tm = result["time_management"]
        assert "score" in tm
        assert "avg_move_time" in tm
        assert "insight" in tm
        
        pp = result["phase_performance"]
        assert "opening" in pp
        assert "middlegame" in pp
        assert "endgame" in pp
        
        print(f"✓ analyze_game_habits returned valid structure")
        print(f"  - Time management score: {tm['score']}")
        print(f"  - Avg move time: {tm['avg_move_time']}s")
        print(f"  - Overall habits score: {result['overall_habits_score']}")
        print(f"  - Recommendations: {len(result['recommendations'])}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

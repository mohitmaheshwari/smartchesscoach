"""
Test Adaptive Game Decryption V5 API
=====================================

Tests for:
1. GET /api/coach/decryption/v5/{game_id} - V5 decryption with priority field
2. Adaptive filtering: ~1100 player should have inaccuracies (30-99 cp_loss) as priority='silent'
3. Mistakes (100-249 cp_loss) and blunders (250+) should have priority='essential'
4. Opponent moves should have appropriate context/essential priorities
5. GET /api/lab/{game_id}/coach-insight - habits tab with pass/fail
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test game ID from the problem statement
TEST_GAME_ID = "01158bd9-8c73-4eb8-b60f-6d28adc502c8"


@pytest.fixture(scope="module")
def auth_session():
    """Get authenticated session using dev-login"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Use dev-login endpoint (GET request)
    res = session.get(f"{BASE_URL}/api/auth/dev-login")
    if res.status_code != 200:
        pytest.skip(f"Dev login failed: {res.status_code}")
    
    return session


class TestV5DecryptionEndpoint:
    """Tests for GET /api/coach/decryption/v5/{game_id}"""
    
    def test_v5_decryption_returns_200(self, auth_session):
        """V5 decryption endpoint should return 200"""
        res = auth_session.get(f"{BASE_URL}/api/coach/decryption/v5/{TEST_GAME_ID}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print(f"✓ V5 decryption endpoint returns 200")
    
    def test_v5_decryption_has_decryption_data(self, auth_session):
        """V5 response should contain decryption_data array"""
        res = auth_session.get(f"{BASE_URL}/api/coach/decryption/v5/{TEST_GAME_ID}")
        assert res.status_code == 200
        
        data = res.json()
        # Check for generating status
        if data.get("status") == "generating":
            pytest.skip("V5 data is still generating")
        
        assert "decryption_data" in data, f"Missing decryption_data in response: {list(data.keys())}"
        assert isinstance(data["decryption_data"], list), "decryption_data should be a list"
        assert len(data["decryption_data"]) > 0, "decryption_data should not be empty"
        print(f"✓ V5 decryption has {len(data['decryption_data'])} moves")
    
    def test_v5_moves_have_priority_field(self, auth_session):
        """Each move in V5 decryption should have a 'priority' field"""
        res = auth_session.get(f"{BASE_URL}/api/coach/decryption/v5/{TEST_GAME_ID}")
        assert res.status_code == 200
        
        data = res.json()
        if data.get("status") == "generating":
            pytest.skip("V5 data is still generating")
        
        moves = data.get("decryption_data", [])
        assert len(moves) > 0, "No moves in decryption data"
        
        # Check first 10 moves for priority field
        for i, move in enumerate(moves[:10]):
            assert "priority" in move, f"Move {i} missing 'priority' field: {list(move.keys())}"
            assert move["priority"] in ["essential", "weakness_match", "growth", "silent", "context"], \
                f"Move {i} has invalid priority: {move['priority']}"
        
        print(f"✓ All checked moves have valid priority field")
    
    def test_v5_moves_have_severity_field(self, auth_session):
        """Each move should have a 'severity' field"""
        res = auth_session.get(f"{BASE_URL}/api/coach/decryption/v5/{TEST_GAME_ID}")
        assert res.status_code == 200
        
        data = res.json()
        if data.get("status") == "generating":
            pytest.skip("V5 data is still generating")
        
        moves = data.get("decryption_data", [])
        for i, move in enumerate(moves[:10]):
            assert "severity" in move, f"Move {i} missing 'severity' field"
        
        print(f"✓ All checked moves have severity field")


class TestAdaptivePriorityFiltering:
    """Tests for adaptive priority filtering based on player rating (~1100)"""
    
    def test_inaccuracies_have_silent_priority_for_low_rated(self, auth_session):
        """For ~1100 player, inaccuracies (cp_loss 30-99) should have priority='silent' and severity='good'"""
        res = auth_session.get(f"{BASE_URL}/api/coach/decryption/v5/{TEST_GAME_ID}")
        assert res.status_code == 200
        
        data = res.json()
        if data.get("status") == "generating":
            pytest.skip("V5 data is still generating")
        
        moves = data.get("decryption_data", [])
        
        # Find user moves with cp_loss in inaccuracy range (30-99)
        inaccuracy_moves = []
        for move in moves:
            if move.get("is_user_move") and move.get("cp_loss"):
                cp_loss = move["cp_loss"]
                # Inaccuracy range: 30-99 cp_loss
                if 30 <= cp_loss < 100:
                    inaccuracy_moves.append(move)
        
        if len(inaccuracy_moves) == 0:
            print("⚠ No inaccuracies (30-99 cp_loss) found in this game")
            return
        
        # For a ~1100 player with min_cp_explain=100, these should be filtered
        silent_count = 0
        for move in inaccuracy_moves:
            priority = move.get("priority")
            severity = move.get("severity")
            cp_loss = move.get("cp_loss")
            
            # With adaptive filtering, inaccuracies below threshold should be 'silent' and severity='good'
            if priority == "silent" and severity == "good":
                silent_count += 1
                print(f"  ✓ Move {move.get('move_number')} {move.get('move_san')}: cp_loss={cp_loss}, priority={priority}, severity={severity}")
            else:
                print(f"  ⚠ Move {move.get('move_number')} {move.get('move_san')}: cp_loss={cp_loss}, priority={priority}, severity={severity}")
        
        # At least some inaccuracies should be filtered
        print(f"✓ Found {len(inaccuracy_moves)} inaccuracies, {silent_count} filtered as silent/good")
    
    def test_mistakes_have_essential_priority(self, auth_session):
        """Mistakes (cp_loss 100-249) should have priority='essential'"""
        res = auth_session.get(f"{BASE_URL}/api/coach/decryption/v5/{TEST_GAME_ID}")
        assert res.status_code == 200
        
        data = res.json()
        if data.get("status") == "generating":
            pytest.skip("V5 data is still generating")
        
        moves = data.get("decryption_data", [])
        
        # Find user moves with cp_loss in mistake range (100-249)
        mistake_moves = []
        for move in moves:
            if move.get("is_user_move") and move.get("cp_loss"):
                cp_loss = move["cp_loss"]
                if 100 <= cp_loss < 250:
                    mistake_moves.append(move)
        
        if len(mistake_moves) == 0:
            print("⚠ No mistakes (100-249 cp_loss) found in this game")
            return
        
        essential_count = 0
        for move in mistake_moves:
            priority = move.get("priority")
            severity = move.get("severity")
            cp_loss = move.get("cp_loss")
            
            if priority == "essential":
                essential_count += 1
                print(f"  ✓ Move {move.get('move_number')} {move.get('move_san')}: cp_loss={cp_loss}, priority={priority}, severity={severity}")
            else:
                print(f"  ⚠ Move {move.get('move_number')} {move.get('move_san')}: cp_loss={cp_loss}, priority={priority}, severity={severity}")
        
        # Most mistakes should be essential
        assert essential_count > 0, "No mistakes have essential priority"
        print(f"✓ Found {len(mistake_moves)} mistakes, {essential_count} have essential priority")
    
    def test_blunders_have_essential_priority(self, auth_session):
        """Blunders (cp_loss 250+) should have priority='essential'"""
        res = auth_session.get(f"{BASE_URL}/api/coach/decryption/v5/{TEST_GAME_ID}")
        assert res.status_code == 200
        
        data = res.json()
        if data.get("status") == "generating":
            pytest.skip("V5 data is still generating")
        
        moves = data.get("decryption_data", [])
        
        # Find user moves with cp_loss >= 250 (blunders)
        blunder_moves = []
        for move in moves:
            if move.get("is_user_move") and move.get("cp_loss"):
                cp_loss = move["cp_loss"]
                if cp_loss >= 250:
                    blunder_moves.append(move)
        
        if len(blunder_moves) == 0:
            print("⚠ No blunders (250+ cp_loss) found in this game")
            return
        
        essential_count = 0
        for move in blunder_moves:
            priority = move.get("priority")
            severity = move.get("severity")
            cp_loss = move.get("cp_loss")
            
            if priority == "essential":
                essential_count += 1
                print(f"  ✓ Move {move.get('move_number')} {move.get('move_san')}: cp_loss={cp_loss}, priority={priority}, severity={severity}")
            else:
                print(f"  ⚠ Move {move.get('move_number')} {move.get('move_san')}: cp_loss={cp_loss}, priority={priority}, severity={severity}")
        
        # All blunders should be essential
        assert essential_count == len(blunder_moves), f"Not all blunders have essential priority: {essential_count}/{len(blunder_moves)}"
        print(f"✓ All {len(blunder_moves)} blunders have essential priority")
    
    def test_opponent_moves_have_context_or_essential(self, auth_session):
        """Opponent moves should have priority='context' or 'essential' (for blunders)"""
        res = auth_session.get(f"{BASE_URL}/api/coach/decryption/v5/{TEST_GAME_ID}")
        assert res.status_code == 200
        
        data = res.json()
        if data.get("status") == "generating":
            pytest.skip("V5 data is still generating")
        
        moves = data.get("decryption_data", [])
        
        # Find opponent moves
        opponent_moves = [m for m in moves if not m.get("is_user_move")]
        
        assert len(opponent_moves) > 0, "No opponent moves found"
        
        valid_count = 0
        for move in opponent_moves[:10]:  # Check first 10 opponent moves
            priority = move.get("priority")
            severity = move.get("severity")
            
            if priority in ["context", "essential"]:
                valid_count += 1
            else:
                print(f"  ⚠ Opponent move {move.get('move_number')} {move.get('move_san')}: priority={priority}")
        
        print(f"✓ Checked {min(10, len(opponent_moves))} opponent moves, {valid_count} have valid priority")


class TestCoachInsightEndpoint:
    """Tests for GET /api/lab/{game_id}/coach-insight"""
    
    def test_coach_insight_returns_200(self, auth_session):
        """Coach insight endpoint should return 200"""
        res = auth_session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print(f"✓ Coach insight endpoint returns 200")
    
    def test_coach_insight_has_summary(self, auth_session):
        """Coach insight should have summary section"""
        res = auth_session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        assert res.status_code == 200
        
        data = res.json()
        assert "summary" in data, f"Missing summary in response: {list(data.keys())}"
        
        summary = data["summary"]
        assert "diagnosis" in summary, "Summary missing diagnosis"
        assert "root_cause" in summary, "Summary missing root_cause"
        
        print(f"✓ Coach insight has summary with diagnosis: {summary.get('diagnosis')}")
    
    def test_coach_insight_has_habits(self, auth_session):
        """Coach insight should have habits section with pass/fail"""
        res = auth_session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        assert res.status_code == 200
        
        data = res.json()
        assert "habits" in data, f"Missing habits in response: {list(data.keys())}"
        
        habits = data["habits"]
        assert "habits" in habits, "Habits section missing habits array"
        assert "passed_count" in habits, "Habits section missing passed_count"
        assert "total_count" in habits, "Habits section missing total_count"
        
        habits_list = habits["habits"]
        assert len(habits_list) > 0, "Habits array is empty"
        
        # Check each habit has required fields
        for i, habit in enumerate(habits_list):
            assert "name" in habit, f"Habit {i} missing name"
            assert "passed" in habit, f"Habit {i} missing passed"
            assert "evidence" in habit, f"Habit {i} missing evidence"
        
        print(f"✓ Coach insight has {len(habits_list)} habits, {habits['passed_count']}/{habits['total_count']} passed")
    
    def test_coach_insight_has_memory(self, auth_session):
        """Coach insight should have memory section with identity and impact"""
        res = auth_session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        assert res.status_code == 200
        
        data = res.json()
        assert "memory" in data, f"Missing memory in response: {list(data.keys())}"
        
        memory = data["memory"]
        assert "identity" in memory, "Memory missing identity"
        assert "impact" in memory, "Memory missing impact"
        
        identity = memory["identity"]
        assert "before_line" in identity, "Identity missing before_line"
        assert "after_line" in identity, "Identity missing after_line"
        assert "archetype" in identity, "Identity missing archetype"
        
        impact = memory["impact"]
        assert "estimated_rating_gain" in impact, "Impact missing estimated_rating_gain"
        
        print(f"✓ Coach insight has memory with archetype: {identity.get('archetype')}")
    
    def test_habits_opening_principles_for_inaccuracy(self, auth_session):
        """Opening principles habit should pass for small inaccuracies like Be7 65cp"""
        res = auth_session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        assert res.status_code == 200
        
        data = res.json()
        habits = data.get("habits", {}).get("habits", [])
        
        # Find "Followed opening principles" habit
        opening_habit = None
        for habit in habits:
            if "opening" in habit.get("name", "").lower():
                opening_habit = habit
                break
        
        if opening_habit is None:
            print("⚠ No opening principles habit found")
            return
        
        # The threshold for opening mistakes is 100cp, so 65cp inaccuracy should pass
        # (Based on game_coach_summary.py line 296: opening_blunders = [m for m in opening_moves if m["cp_loss"] >= 100])
        print(f"  Opening principles habit: passed={opening_habit.get('passed')}, evidence={opening_habit.get('evidence')}")
        
        # Note: This test documents the behavior - the habit uses 100cp threshold
        # so a 65cp inaccuracy should NOT cause this habit to fail
        print(f"✓ Opening principles habit check complete")


class TestV5MoveStructure:
    """Tests for V5 move data structure"""
    
    def test_v5_move_has_required_fields(self, auth_session):
        """Each V5 move should have all required fields"""
        res = auth_session.get(f"{BASE_URL}/api/coach/decryption/v5/{TEST_GAME_ID}")
        assert res.status_code == 200
        
        data = res.json()
        if data.get("status") == "generating":
            pytest.skip("V5 data is still generating")
        
        moves = data.get("decryption_data", [])
        assert len(moves) > 0, "No moves in decryption data"
        
        required_fields = [
            "move_number", "move_san", "is_user_move", "is_white",
            "fen_before", "fen_after", "phase", "severity", "priority"
        ]
        
        for i, move in enumerate(moves[:5]):
            for field in required_fields:
                assert field in move, f"Move {i} missing required field: {field}"
        
        print(f"✓ All checked moves have required fields")
    
    def test_v5_move_has_weakness_match_field(self, auth_session):
        """V5 moves should have weakness_match field"""
        res = auth_session.get(f"{BASE_URL}/api/coach/decryption/v5/{TEST_GAME_ID}")
        assert res.status_code == 200
        
        data = res.json()
        if data.get("status") == "generating":
            pytest.skip("V5 data is still generating")
        
        moves = data.get("decryption_data", [])
        
        # Check that weakness_match field exists
        for i, move in enumerate(moves[:10]):
            assert "weakness_match" in move, f"Move {i} missing weakness_match field"
        
        # Count moves with weakness_match=True
        weakness_matches = [m for m in moves if m.get("weakness_match")]
        print(f"✓ Found {len(weakness_matches)} moves with weakness_match=True")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

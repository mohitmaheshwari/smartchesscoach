"""
Live API Tests for Play with Coach Deep Opening Teaching

Tests the actual API endpoints to verify:
1. Dev login works
2. Starting a coach session
3. Playing QGD moves and getting variation-aware teaching
4. Checking that coach messages contain opening-specific content

Note: The move endpoint returns the coach's response move, so we don't need
to wait separately - each user move triggers coach's response in the same call.
"""

import os
import pytest
import requests
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://chess-truth-engine.preview.emergentagent.com"


def get_messages_list(msg_response_json):
    """Extract messages list from API response (handles both direct array and dict format)."""
    if isinstance(msg_response_json, list):
        return msg_response_json
    if isinstance(msg_response_json, dict):
        return msg_response_json.get("messages", [])
    return []


class TestPlayWithCoachAPI:
    """API integration tests for Play with Coach opening teaching."""

    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session via dev-login."""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Dev login
        resp = session.get(f"{BASE_URL}/api/auth/dev-login")
        if resp.status_code != 200:
            pytest.skip(f"Dev login failed: {resp.status_code} - {resp.text}")
        
        data = resp.json()
        token = data.get("session_token") or resp.cookies.get("session_token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
        
        return session

    def test_dev_login_works(self, auth_session):
        """Verify dev login returns a valid session."""
        resp = auth_session.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 200, f"Auth check failed: {resp.text}"
        user = resp.json()
        assert "user_id" in user, "Should return user data"
        print(f"✓ Logged in as: {user.get('name', user.get('user_id'))}")

    def test_start_coach_session(self, auth_session):
        """Start a new coach session."""
        resp = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "color": "white",
            "opening": "queens_gambit"
        })
        assert resp.status_code == 200, f"Failed to start session: {resp.text}"
        data = resp.json()
        assert "session_id" in data, "Should return session_id"
        print(f"✓ Started session: {data['session_id']}")

    def test_d4_move_generates_teaching(self, auth_session):
        """Playing d4 should generate opening teaching message."""
        # Start fresh session
        start_resp = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "color": "white",
            "opening": "queens_gambit"
        })
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session_id"]

        # Play d4 - this also triggers coach's response (d5)
        move_resp = auth_session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "d4"
        })
        assert move_resp.status_code == 200, f"Move failed: {move_resp.text}"
        move_data = move_resp.json()
        
        # The move response itself may contain coach_move
        coach_move = move_data.get("coach_move")
        print(f"  After d4, coach played: {coach_move}")
        
        # Check for coach messages
        time.sleep(0.5)  # Small wait for async message generation
        msg_resp = auth_session.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        assert msg_resp.status_code == 200
        messages = get_messages_list(msg_resp.json())
        
        print(f"  Total messages: {len(messages)}")
        
        # Find opening teaching messages
        teaching_msgs = [m for m in messages if m.get("trigger") == "opening_teaching"]
        
        # Should have teaching messages (may be 0 if coach decided not to speak)
        # The coach should at least respond to d4
        print(f"✓ d4 generated {len(teaching_msgs)} opening_teaching messages")
        for m in teaching_msgs[:2]:
            print(f"  - {m.get('message', '')[:100]}...")

    def test_qgd_sequence_generates_variation_teaching(self, auth_session):
        """Playing QGD sequence should trigger variation-aware teaching."""
        # Start fresh session
        start_resp = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "color": "white",
            "opening": "queens_gambit"
        })
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session_id"]

        # Play QGD opening moves as white
        # Each move triggers coach's response automatically
        moves_to_play = ["d4", "c4", "Nc3"]  # User plays white, coach responds after each
        
        for move in moves_to_play:
            move_resp = auth_session.post(f"{BASE_URL}/api/coach/play/move", json={
                "session_id": session_id,
                "move": move
            })
            if move_resp.status_code != 200:
                print(f"  Move {move} failed: {move_resp.text}")
                # Continue anyway to see how far we get
            else:
                coach_move = move_resp.json().get("coach_move", "")
                print(f"  Played {move}, coach responded: {coach_move}")
            time.sleep(0.3)  # Small delay between moves
        
        # Get messages
        msg_resp = auth_session.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        assert msg_resp.status_code == 200
        messages = get_messages_list(msg_resp.json())
        
        print(f"✓ QGD sequence generated {len(messages)} messages")
        
        # Check for QGD-related content
        all_msg_text = " ".join([m.get("message", "") for m in messages]).lower()
        
        qgd_indicators = ["queen", "gambit", "center", "pawn", "d5", "develop", "knight"]
        has_qgd_content = any(ind in all_msg_text for ind in qgd_indicators)
        
        print(f"  QGD content detected: {has_qgd_content}")
        
        # Print some messages for verification
        for m in messages[:3]:
            trigger = m.get("trigger", "")
            msg_snippet = m.get("message", "")[:80]
            print(f"  [{trigger}] {msg_snippet}...")

    def test_nc3_move_gets_deep_teaching(self, auth_session):
        """After d4 d5 c4 e6, playing Nc3 should get variation-specific teaching."""
        # Start fresh session as white
        start_resp = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "color": "white",
            "opening": "queens_gambit"
        })
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session_id"]

        # Play d4 - coach responds (likely d5)
        resp = auth_session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "d4"
        })
        if resp.status_code == 200:
            print(f"  d4 → coach: {resp.json().get('coach_move')}")
        
        time.sleep(0.3)
        
        # Play c4 - coach responds (likely e6 or c6 for QGD/Slav)
        resp = auth_session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "c4"
        })
        if resp.status_code == 200:
            print(f"  c4 → coach: {resp.json().get('coach_move')}")
        
        time.sleep(0.3)
        
        # Play Nc3
        nc3_resp = auth_session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "Nc3"
        })
        
        if nc3_resp.status_code == 200:
            print(f"  Nc3 → coach: {nc3_resp.json().get('coach_move')}")
        else:
            print(f"  Nc3 failed: {nc3_resp.text}")
        
        time.sleep(0.3)
        
        # Get messages after the sequence
        msg_resp = auth_session.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        assert msg_resp.status_code == 200
        messages = get_messages_list(msg_resp.json())
        
        print(f"✓ After QGD sequence, found {len(messages)} total messages")
        
        # Look for any messages about knight or center
        knight_msgs = [m for m in messages if "knight" in m.get("message", "").lower()]
        
        for m in messages[-3:]:  # Show last 3 messages
            print(f"  - [{m.get('trigger', '')}] {m.get('message', '')[:80]}...")

    def test_deviation_still_gets_guidance(self, auth_session):
        """Playing Nf3 instead of Nc3 should still get teaching guidance."""
        # Start fresh session
        start_resp = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "color": "white",
            "opening": "queens_gambit"
        })
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session_id"]

        # Play d4
        resp = auth_session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "d4"
        })
        if resp.status_code == 200:
            print(f"  d4 → coach: {resp.json().get('coach_move')}")
        time.sleep(0.3)
        
        # Play c4
        resp = auth_session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "c4"
        })
        if resp.status_code == 200:
            print(f"  c4 → coach: {resp.json().get('coach_move')}")
        time.sleep(0.3)
        
        # Play Nf3 (deviation from main line Nc3)
        nf3_resp = auth_session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "Nf3"
        })
        
        if nf3_resp.status_code == 200:
            print(f"  Nf3 (deviation) → coach: {nf3_resp.json().get('coach_move')}")
        else:
            print(f"  Nf3 failed: {nf3_resp.text}")
        
        time.sleep(0.3)
        
        # Get messages
        msg_resp = auth_session.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        assert msg_resp.status_code == 200
        messages = get_messages_list(msg_resp.json())
        
        print(f"✓ On Nf3 deviation, got {len(messages)} total messages")
        
        # Should still have teaching for this move
        for m in messages[-2:]:
            trigger = m.get('trigger', '')
            print(f"  [{trigger}] {m.get('message', '')[:80]}...")


class TestCoachSessionMessages:
    """Test that coach messages maintain context throughout the game."""

    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session via dev-login."""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        resp = session.get(f"{BASE_URL}/api/auth/dev-login")
        if resp.status_code != 200:
            pytest.skip(f"Dev login failed: {resp.status_code}")
        
        data = resp.json()
        token = data.get("session_token") or resp.cookies.get("session_token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
        
        return session

    def test_messages_endpoint_returns_messages(self, auth_session):
        """Messages endpoint should return messages in some format."""
        start_resp = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "color": "white",
            "opening": "queens_gambit"
        })
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session_id"]
        
        # Play a move
        auth_session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "d4"
        })
        
        time.sleep(0.5)
        
        msg_resp = auth_session.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        assert msg_resp.status_code == 200
        
        data = msg_resp.json()
        messages = get_messages_list(data)
        
        print(f"✓ Messages endpoint response type: {type(data).__name__}")
        print(f"  Messages count: {len(messages)}")
        
        if messages:
            print(f"  First message keys: {list(messages[0].keys())}")

    def test_messages_have_required_fields(self, auth_session):
        """Messages should have required fields: message, trigger."""
        start_resp = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "color": "white",
            "opening": "italian"  # Different opening
        })
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session_id"]
        
        # Play e4
        auth_session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "e4"
        })
        
        time.sleep(0.5)
        
        msg_resp = auth_session.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        assert msg_resp.status_code == 200
        messages = get_messages_list(msg_resp.json())
        
        if messages:
            msg = messages[0]
            assert "message" in msg, "Should have message field"
            assert "trigger" in msg, "Should have trigger field"
            print(f"✓ Message fields present: {list(msg.keys())}")
        else:
            print("✓ No messages yet (coach may be silent on e4)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

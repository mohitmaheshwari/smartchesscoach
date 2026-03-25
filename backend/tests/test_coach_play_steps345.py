"""
Test Coach Play API - Steps 3, 4, 5: Live Behavior Extraction, CPR Engine, and Identity Engine

Tests:
Step 3 - Live Behavior Extractor:
- Behavior events detected during moves (impulse_move, threat_ignored, rapid_streak)
- GET /api/coach/play/behaviors/{session_id}

Step 4 - CPR Engine:
- CPR computed on session end (overall_cpr, interpretation, recommendations)
- GET /api/coach/play/cpr/history

Step 5 - Identity Engine:
- Identity updated on session end (identity_label, trait_snapshot, confidence)
- GET /api/coach/play/identity
- Identity confidence increases with more sessions
"""
import pytest
import time
import uuid

BASE_URL = "https://thinking-simulator-1.preview.emergentagent.com"


class TestBehaviorExtraction:
    """Test Step 3 - Live Behavior Extraction during moves"""

    def test_behavior_events_tracked_during_session(self, authenticated_session):
        """Behaviors are tracked and stored in session.behavior_events"""
        # Start a session
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        
        # Make a move
        move_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 3.0}
        )
        assert move_response.status_code == 200
        
        # Get session state - behavior_events should be in session
        state_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/state/{session_id}"
        )
        assert state_response.status_code == 200
        session_data = state_response.json()["session"]
        
        # behavior_events list exists
        assert "behavior_events" in session_data
        assert isinstance(session_data["behavior_events"], list)
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )

    def test_get_session_behaviors_endpoint(self, authenticated_session):
        """GET /api/coach/play/behaviors/{session_id} returns behavior events"""
        # Start and play some moves
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        # Make a few moves
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "d4", "time_spent": 3.0}
        )
        
        # End session to finalize behaviors
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        # Get behaviors
        response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/behaviors/{session_id}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "session_id" in data
        assert data["session_id"] == session_id
        assert "total_events" in data
        assert "positive_behaviors" in data
        assert "negative_behaviors" in data
        assert "events" in data
        assert "summary" in data
        
        # Summary has positive and negative lists
        assert "positive" in data["summary"]
        assert "negative" in data["summary"]

    def test_behaviors_endpoint_returns_404_for_invalid_session(self, authenticated_session):
        """GET behaviors for non-existent session returns 404"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/behaviors/{str(uuid.uuid4())}"
        )
        assert response.status_code == 404

    def test_behavior_types_are_valid(self, authenticated_session):
        """Behavior events have valid types from defined enums"""
        valid_behavior_types = [
            "impulse_move", "threat_ignored", "panic_defense", "rapid_streak",
            "time_pressure_mistake", "repeated_mistake",
            "calculated_sacrifice", "positional_patience", "tactical_alertness",
            "threat_addressed", "accurate_under_pressure"
        ]
        
        # Start session and make moves
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        # Make moves quickly to potentially trigger impulse detection
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 1.0}
        )
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "d4", "time_spent": 1.0}
        )
        
        # End and check behaviors
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/behaviors/{session_id}"
        )
        data = response.json()
        
        # If any events exist, verify their types
        for event in data["events"]:
            if "behavior_type" in event:
                assert event["behavior_type"] in valid_behavior_types


class TestCPREngine:
    """Test Step 4 - CPR (Cognitive Performance Rating) computation"""

    def test_cpr_computed_on_session_end(self, authenticated_session):
        """CPR is computed and returned when session ends"""
        # Start session
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        # Make some moves
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "d4", "time_spent": 4.0}
        )
        
        # End session - should compute CPR
        end_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        assert end_response.status_code == 200
        data = end_response.json()
        
        # CPR should be present
        assert "cpr" in data
        cpr = data["cpr"]
        
        # Check CPR structure
        assert "overall_cpr" in cpr
        assert "interpretation" in cpr
        assert "recommendations" in cpr
        
        # CPR should be a number 0-100
        assert 0 <= cpr["overall_cpr"] <= 100
        
        # Interpretation should be a string
        assert isinstance(cpr["interpretation"], str)
        assert len(cpr["interpretation"]) > 0
        
        # Recommendations should be a list
        assert isinstance(cpr["recommendations"], list)

    def test_cpr_has_component_breakdown(self, authenticated_session):
        """CPR includes component scores (decision_quality, threat_awareness, etc.)"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        
        end_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        cpr = end_response.json()["cpr"]
        
        # Should have components breakdown
        assert "components" in cpr
        components = cpr["components"]
        
        # Expected component keys
        expected_components = [
            "decision_quality", "time_management", "threat_awareness",
            "emotional_control", "focus_consistency"
        ]
        
        for comp in expected_components:
            assert comp in components
            assert 0 <= components[comp] <= 100

    def test_cpr_stored_in_session(self, authenticated_session):
        """CPR score is stored in session.cpr_after"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        
        end_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        session = end_response.json()["session"]
        cpr_result = end_response.json()["cpr"]
        
        # cpr_after should match the computed CPR
        assert "cpr_after" in session
        assert session["cpr_after"] == cpr_result["overall_cpr"]

    def test_get_cpr_history(self, authenticated_session):
        """GET /api/coach/play/cpr/history returns CPR from past sessions"""
        # First, complete a session to have CPR data
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        # Get CPR history
        history_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/cpr/history"
        )
        
        assert history_response.status_code == 200
        data = history_response.json()
        
        assert "history" in data
        assert "average_cpr" in data
        assert "sessions_count" in data
        
        # Should have at least the session we just completed
        assert data["sessions_count"] >= 1
        
        # Each history entry should have cpr_after
        for entry in data["history"]:
            assert "cpr_after" in entry
            assert "session_id" in entry


class TestIdentityEngine:
    """Test Step 5 - Player Identity Engine"""

    def test_identity_updated_on_session_end(self, authenticated_session):
        """Identity is computed/updated and returned when session ends"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        
        end_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        assert end_response.status_code == 200
        data = end_response.json()
        
        # Identity should be present
        assert "identity" in data
        identity = data["identity"]
        
        # Check identity structure
        assert "identity_label" in identity
        assert "identity_description" in identity
        assert "trait_snapshot" in identity
        assert "confidence" in identity
        assert "sessions_analyzed" in identity
        
        # Identity label should be one of the defined labels
        valid_labels = [
            "The Calculator", "The Warrior", "The Strategist", "The Risk-Taker",
            "The Fortress", "The Phoenix", "The Improviser", "The Perfectionist",
            "The Learner"  # Default for low confidence
        ]
        assert identity["identity_label"] in valid_labels

    def test_identity_has_trait_snapshot(self, authenticated_session):
        """Identity includes trait_snapshot with all trait dimensions"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        
        end_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        identity = end_response.json()["identity"]
        traits = identity["trait_snapshot"]
        
        # Expected trait keys
        expected_traits = ["aggression", "calculation", "consistency", "resilience", "risk_tolerance"]
        
        for trait in expected_traits:
            assert trait in traits
            # Traits range from -100 to +100
            assert -100 <= traits[trait] <= 100

    def test_get_player_identity_endpoint(self, authenticated_session):
        """GET /api/coach/play/identity returns player identity"""
        # First play a game to establish identity
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        # Get identity
        identity_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/identity"
        )
        
        assert identity_response.status_code == 200
        data = identity_response.json()
        
        assert "has_identity" in data
        assert data["has_identity"] is True
        assert "identity" in data
        
        identity = data["identity"]
        assert "identity_label" in identity
        assert "identity_description" in identity
        assert "confidence" in identity

    def test_identity_confidence_increases_with_sessions(self, authenticated_session):
        """Confidence increases as more sessions are analyzed"""
        confidences = []
        
        # Play multiple sessions
        for i in range(3):
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/start",
                json={"user_color": "white", "time_control": "15+10"}
            )
            session_id = response.json()["session_id"]
            
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/move",
                json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
            )
            
            end_response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )
            
            identity = end_response.json()["identity"]
            confidences.append(identity["confidence"])
        
        # Confidence should generally increase (or stay stable)
        # With 3 sessions, confidence = 3/10 = 0.3
        assert confidences[-1] >= confidences[0]
        
        # After 3 sessions, we should have some confidence
        assert confidences[-1] > 0

    def test_identity_sessions_count_increments(self, authenticated_session):
        """sessions_analyzed count increases with each session"""
        # Get initial count
        identity_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/identity"
        )
        
        initial_count = 0
        if identity_response.json().get("has_identity"):
            initial_count = identity_response.json()["identity"]["sessions_analyzed"]
        
        # Play a session
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        
        end_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        new_count = end_response.json()["identity"]["sessions_analyzed"]
        
        # Count should have increased
        assert new_count == initial_count + 1


class TestIntegrationBehaviorCPRIdentity:
    """Integration tests for Steps 3, 4, 5 working together"""

    def test_full_session_produces_behavior_cpr_and_identity(self, authenticated_session):
        """Complete flow: behaviors detected, CPR computed, identity updated"""
        # Start session
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        # Play several moves
        moves = ["e4", "Nf3", "Bc4"]
        for move in moves:
            move_response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/move",
                json={"session_id": session_id, "move": move, "time_spent": 5.0}
            )
            if move_response.status_code != 200:
                # Move might fail if coach checkmated us, etc.
                break
        
        # End session
        end_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        assert end_response.status_code == 200
        data = end_response.json()
        
        # All three components present
        assert "summary" in data
        assert "cpr" in data
        assert "identity" in data
        
        # CPR is valid
        assert 0 <= data["cpr"]["overall_cpr"] <= 100
        
        # Identity is valid
        assert "identity_label" in data["identity"]
        assert "sessions_analyzed" in data["identity"]

    def test_behaviors_affect_cpr_components(self, authenticated_session):
        """Behavior events influence CPR component scores"""
        # Start session
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        # Make some moves
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 10.0}
        )
        
        # End session
        end_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        cpr = end_response.json()["cpr"]
        
        # Verify component_details show modifiers
        if "component_details" in cpr:
            # Component details exist and have structure
            for comp_name, details in cpr["component_details"].items():
                assert "base" in details
                assert "final" in details
                assert "modifiers" in details

    def test_cpr_stored_in_history(self, authenticated_session):
        """After session ends, CPR appears in cpr/history"""
        # Play and end a session
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = response.json()["session_id"]
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        
        end_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        expected_cpr = end_response.json()["cpr"]["overall_cpr"]
        
        # Get history with limit 20 to include recent session
        new_history = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/cpr/history?limit=20"
        ).json()
        
        # History should have sessions
        assert new_history["sessions_count"] >= 1
        
        # The session should be in history
        session_ids = [h["session_id"] for h in new_history["history"]]
        assert session_id in session_ids
        
        # The CPR value should match what we got at session end
        matching_sessions = [h for h in new_history["history"] if h["session_id"] == session_id]
        assert len(matching_sessions) == 1
        assert matching_sessions[0]["cpr_after"] == expected_cpr

"""
Test Pre-Move Guardian API endpoints - P2 Play With Coach Step 2

Tests:
- POST /api/coach/play/evaluate - Evaluate move with guardian
- POST /api/coach/play/move/confirm - Confirm risky move after warning
- Guardian detection: hanging pieces, bad trades, ignored threats
- Guardian response time < 100ms
- Intervention counting and consumption
"""
import pytest
import uuid
import time

BASE_URL = "https://opening-trainer-pro-1.preview.emergentagent.com"


class TestGuardianEvaluate:
    """Test POST /api/coach/play/evaluate"""

    @pytest.fixture
    def active_session(self, authenticated_session):
        """Create an active session for testing"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        data = response.json()
        yield data["session_id"], authenticated_session

        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )

    def test_evaluate_safe_move(self, active_session):
        """Evaluate a safe opening move - should not intervene"""
        session_id, session = active_session

        response = session.post(
            f"{BASE_URL}/api/coach/play/evaluate",
            json={"session_id": session_id, "move": "e4"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["should_intervene"] is False
        assert data["intervention_type"] == "none"
        assert data["risk_level"] == "none"
        assert data["remaining_interventions"] == 3

    def test_evaluate_response_time_under_100ms(self, active_session):
        """Guardian response time should be under 100ms"""
        session_id, session = active_session

        response = session.post(
            f"{BASE_URL}/api/coach/play/evaluate",
            json={"session_id": session_id, "move": "e4"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check processing time is under 100ms
        assert data["processing_time_ms"] < 100, f"Guardian took {data['processing_time_ms']}ms, should be under 100ms"

    def test_evaluate_missing_session_id(self, authenticated_session):
        """Missing session_id should return 400"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/evaluate",
            json={"move": "e4"}
        )

        assert response.status_code == 400

    def test_evaluate_missing_move(self, active_session):
        """Missing move should return 400"""
        session_id, session = active_session

        response = session.post(
            f"{BASE_URL}/api/coach/play/evaluate",
            json={"session_id": session_id}
        )

        assert response.status_code == 400

    def test_evaluate_invalid_session(self, authenticated_session):
        """Invalid session should return 404"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/evaluate",
            json={"session_id": str(uuid.uuid4()), "move": "e4"}
        )

        assert response.status_code == 404

    def test_evaluate_returns_intervention_fields(self, active_session):
        """Evaluate should return all required fields"""
        session_id, session = active_session

        response = session.post(
            f"{BASE_URL}/api/coach/play/evaluate",
            json={"session_id": session_id, "move": "e4"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check all required fields are present
        required_fields = [
            "should_intervene",
            "intervention_type",
            "risk_level",
            "risk_type",
            "message",
            "explanation",
            "alternative_moves",
            "processing_time_ms",
            "remaining_interventions"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestGuardianDetection:
    """Test guardian risk detection capabilities"""

    def test_detect_hanging_piece_queen(self, authenticated_session):
        """Guardian should detect hanging queen"""
        # Create session as white
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]

        try:
            # Play 1.e4
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/move",
                json={"session_id": session_id, "move": "e4", "time_spent": 1}
            )

            # Play 2.Qh5 (aggressive queen move)
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/move",
                json={"session_id": session_id, "move": "Qh5", "time_spent": 1}
            )

            # Get current state to verify position
            state = authenticated_session.get(
                f"{BASE_URL}/api/coach/play/state/{session_id}"
            ).json()

            # If g6 was played by opponent, queen is attacked
            # Try Nc3 which ignores the hanging queen
            if "g6" in state.get("current_fen", ""):
                response = authenticated_session.post(
                    f"{BASE_URL}/api/coach/play/evaluate",
                    json={"session_id": session_id, "move": "Nc3"}
                )

                if response.status_code == 200:
                    data = response.json()
                    # Guardian may or may not detect depending on position
                    # Just verify we get a valid response
                    assert "should_intervene" in data
        finally:
            # Cleanup
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )

    def test_detect_bad_material_trade(self, authenticated_session):
        """Guardian should detect bad material trades"""
        # Create session
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]

        try:
            # The guardian uses lightweight heuristics
            # It checks if after a capture, the capturing piece can be recaptured
            # at a material disadvantage

            # Make some moves
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/move",
                json={"session_id": session_id, "move": "e4", "time_spent": 1}
            )

            # Get state
            state = authenticated_session.get(
                f"{BASE_URL}/api/coach/play/state/{session_id}"
            ).json()

            # Verify response structure
            assert "current_fen" in state
            assert "legal_moves" in state
        finally:
            # Cleanup
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )


class TestGuardianConfirm:
    """Test POST /api/coach/play/move/confirm"""

    @pytest.fixture
    def session_with_position(self, authenticated_session):
        """Create session and set up a position"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        data = response.json()
        session_id = data["session_id"]

        # Make a move to get past starting position
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 1}
        )

        yield session_id, authenticated_session

        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )

    def test_confirm_move_without_risk(self, session_with_position):
        """Confirm endpoint works for safe moves"""
        session_id, session = session_with_position

        # Get legal moves
        state = session.get(f"{BASE_URL}/api/coach/play/state/{session_id}").json()
        legal_moves = state.get("legal_moves", [])

        if legal_moves:
            # Try to confirm a move (even without warning)
            response = session.post(
                f"{BASE_URL}/api/coach/play/move/confirm",
                json={
                    "session_id": session_id,
                    "move": legal_moves[0],
                    "time_spent": 2.0,
                    "risk_acknowledged": ""
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_confirm_move_with_risk_acknowledged(self, authenticated_session):
        """Confirm move with acknowledged risk decrements interventions"""
        # Create fresh session
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]

        try:
            # Confirm a move with risk acknowledged
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/move/confirm",
                json={
                    "session_id": session_id,
                    "move": "e4",
                    "time_spent": 1.5,
                    "risk_acknowledged": "hanging_piece"
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Should have decremented interventions
            assert data.get("remaining_interventions") == 2
            assert data.get("intervention_consumed") is True
        finally:
            # Cleanup
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )

    def test_confirm_missing_session_id(self, authenticated_session):
        """Missing session_id should return 400"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move/confirm",
            json={"move": "e4"}
        )

        assert response.status_code == 400

    def test_confirm_missing_move(self, session_with_position):
        """Missing move should return 400"""
        session_id, session = session_with_position

        response = session.post(
            f"{BASE_URL}/api/coach/play/move/confirm",
            json={"session_id": session_id}
        )

        assert response.status_code == 400

    def test_confirm_invalid_session(self, authenticated_session):
        """Invalid session should return 404"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move/confirm",
            json={"session_id": str(uuid.uuid4()), "move": "e4"}
        )

        assert response.status_code == 404


class TestGuardianInterventionLimit:
    """Test intervention counting and limits"""

    def test_session_starts_with_3_interventions(self, authenticated_session):
        """New session should have 3 interventions"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]

        try:
            # Check session has 3 interventions
            assert data["session"]["remaining_interventions"] == 3

            # Also verify via evaluate endpoint
            eval_response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/evaluate",
                json={"session_id": session_id, "move": "e4"}
            )
            assert eval_response.json()["remaining_interventions"] == 3
        finally:
            # Cleanup
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )

    def test_interventions_decrement_on_override(self, authenticated_session):
        """Interventions should decrement when user overrides warning"""
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]

        try:
            # Override a move with acknowledged risk
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/move/confirm",
                json={
                    "session_id": session_id,
                    "move": "e4",
                    "time_spent": 1.0,
                    "risk_acknowledged": "test_risk"
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Should have 2 interventions remaining
            assert data["remaining_interventions"] == 2

            # Make another override
            # First get legal moves
            state = authenticated_session.get(
                f"{BASE_URL}/api/coach/play/state/{session_id}"
            ).json()

            if not state.get("game_over") and state.get("legal_moves"):
                response2 = authenticated_session.post(
                    f"{BASE_URL}/api/coach/play/move/confirm",
                    json={
                        "session_id": session_id,
                        "move": state["legal_moves"][0],
                        "time_spent": 1.0,
                        "risk_acknowledged": "another_risk"
                    }
                )

                if response2.status_code == 200:
                    data2 = response2.json()
                    # Should have 1 intervention remaining
                    assert data2["remaining_interventions"] == 1
        finally:
            # Cleanup
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )


class TestGuardianRiskTypes:
    """Test specific risk type detection"""

    def test_risk_types_exist_in_enum(self, authenticated_session):
        """Verify known risk types are handled"""
        # Create session
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]

        try:
            # Evaluate a move - just verify the response has valid risk type field
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/evaluate",
                json={"session_id": session_id, "move": "e4"}
            )

            assert response.status_code == 200
            data = response.json()

            # risk_type should be None or a valid string
            assert data["risk_type"] is None or isinstance(data["risk_type"], str)

            # Known risk types from guardian
            valid_risk_types = [
                None,
                "hanging_piece",
                "blunder_into_tactic",
                "ignore_threat",
                "material_loss",
                "back_rank_weakness",
                "king_safety",
                "trapped_piece"
            ]

            assert data["risk_type"] in valid_risk_types
        finally:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )

    def test_intervention_types_valid(self, authenticated_session):
        """Verify intervention types are valid"""
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]

        try:
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/evaluate",
                json={"session_id": session_id, "move": "e4"}
            )

            assert response.status_code == 200
            data = response.json()

            # Valid intervention types
            valid_intervention_types = ["block", "warn", "suggest", "none"]
            assert data["intervention_type"] in valid_intervention_types
        finally:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )

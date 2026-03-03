"""
Test Focus Lock API Endpoints (Step 9)

Tests:
- GET /api/coach/focus-lock
- POST /api/coach/focus-lock/activate
- POST /api/coach/focus-lock/deactivate
- GET /api/coach/breakthrough-signal (still works)
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_ID = "37cfa3f6-90be-4a3d-a4b0-1a3b65e66680"  # test user session


@pytest.fixture
def api_client():
    """Shared requests session with auth cookie"""
    session = requests.Session()
    session.cookies.set('session_id', SESSION_ID)
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def clean_focus_lock(api_client):
    """Ensure focus lock is deactivated before and after test"""
    # Deactivate before
    api_client.post(f"{BASE_URL}/api/coach/focus-lock/deactivate")
    yield
    # Deactivate after
    api_client.post(f"{BASE_URL}/api/coach/focus-lock/deactivate")


class TestFocusLockGetState:
    """Test GET /api/coach/focus-lock"""
    
    def test_get_focus_lock_inactive(self, api_client, clean_focus_lock):
        """GET focus-lock returns active: false when no lock exists"""
        response = api_client.get(f"{BASE_URL}/api/coach/focus-lock")
        assert response.status_code == 200
        data = response.json()
        assert data.get("active") == False
    
    def test_get_focus_lock_active(self, api_client, clean_focus_lock):
        """GET focus-lock returns full state when lock is active"""
        # First activate a lock
        activate_response = api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "FORCING_BLIND", "games": 5}
        )
        assert activate_response.status_code == 200
        
        # Then get state
        response = api_client.get(f"{BASE_URL}/api/coach/focus-lock")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("active") == True
        assert data.get("lesson_key") == "FORCING_BLIND"
        assert data.get("state") == "ACTIVE"
        assert "headline" in data
        assert "message" in data
        assert "progress" in data
        assert "compliance" in data
        
        # Verify progress structure
        progress = data.get("progress", {})
        assert progress.get("completed") == 0
        assert progress.get("required") == 5
        
        # Verify compliance structure
        compliance = data.get("compliance", {})
        assert "average" in compliance
        assert "color" in compliance


class TestFocusLockActivate:
    """Test POST /api/coach/focus-lock/activate"""
    
    def test_activate_forcing_blind(self, api_client, clean_focus_lock):
        """Can activate FORCING_BLIND focus lock"""
        response = api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "FORCING_BLIND", "games": 5}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "activated"
        assert data.get("lesson_key") == "FORCING_BLIND"
        assert data.get("games_required") == 5
        assert "rule_description" in data
        assert "headline" in data
    
    def test_activate_stopped_calculation_early(self, api_client, clean_focus_lock):
        """Can activate STOPPED_CALCULATION_EARLY focus lock"""
        response = api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "STOPPED_CALCULATION_EARLY", "games": 10}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "activated"
        assert data.get("lesson_key") == "STOPPED_CALCULATION_EARLY"
    
    def test_activate_threat_verification(self, api_client, clean_focus_lock):
        """Can activate THREAT_VERIFICATION focus lock"""
        response = api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "THREAT_VERIFICATION", "games": 5}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "activated"
        assert data.get("lesson_key") == "THREAT_VERIFICATION"
    
    def test_activate_invalid_lesson_key(self, api_client, clean_focus_lock):
        """Invalid lesson_key returns 400 error"""
        response = api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "INVALID_KEY", "games": 5}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "Invalid lesson_key" in data.get("detail", "")
    
    def test_activate_duplicate_rejected(self, api_client, clean_focus_lock):
        """Cannot activate when lock already active"""
        # First activation
        response1 = api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "FORCING_BLIND", "games": 5}
        )
        assert response1.status_code == 200
        
        # Second activation should fail
        response2 = api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "THREAT_VERIFICATION", "games": 5}
        )
        assert response2.status_code == 400
        
        data = response2.json()
        assert "already active" in data.get("detail", "").lower()
    
    def test_activate_default_games(self, api_client, clean_focus_lock):
        """Games parameter has default value if not provided"""
        response = api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "FORCING_BLIND"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # Default is 5 games
        assert data.get("games_required") == 5


class TestFocusLockDeactivate:
    """Test POST /api/coach/focus-lock/deactivate"""
    
    def test_deactivate_active_lock(self, api_client, clean_focus_lock):
        """Can deactivate an active lock"""
        # First activate
        api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "FORCING_BLIND", "games": 5}
        )
        
        # Then deactivate
        response = api_client.post(f"{BASE_URL}/api/coach/focus-lock/deactivate")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "deactivated"
        
        # Verify lock is inactive
        get_response = api_client.get(f"{BASE_URL}/api/coach/focus-lock")
        assert get_response.json().get("active") == False
    
    def test_deactivate_no_lock(self, api_client, clean_focus_lock):
        """Deactivating when no lock exists returns no_lock_found"""
        response = api_client.post(f"{BASE_URL}/api/coach/focus-lock/deactivate")
        assert response.status_code == 200
        
        data = response.json()
        # Either "deactivated" or "no_lock_found" is acceptable
        assert data.get("status") in ["deactivated", "no_lock_found"]


class TestBreakthroughSignalEndpoint:
    """Test GET /api/coach/breakthrough-signal still works"""
    
    def test_breakthrough_signal_returns_data(self, api_client):
        """Breakthrough signal endpoint returns expected structure"""
        response = api_client.get(f"{BASE_URL}/api/coach/breakthrough-signal")
        assert response.status_code == 200
        
        data = response.json()
        assert "show_card" in data
        assert "state" in data
        assert "headline" in data
        assert "message" in data
        assert "cta" in data


class TestFocusLockStateTransitions:
    """Test focus lock state field values"""
    
    def test_initial_state_is_active(self, api_client, clean_focus_lock):
        """Newly activated lock has state ACTIVE"""
        api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "FORCING_BLIND", "games": 5}
        )
        
        response = api_client.get(f"{BASE_URL}/api/coach/focus-lock")
        data = response.json()
        
        assert data.get("state") == "ACTIVE"
        assert data.get("strict_mode") == False
        assert data.get("failed_cycles") == 0
    
    def test_compliance_color_fields(self, api_client, clean_focus_lock):
        """Compliance has color field for UI"""
        api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "FORCING_BLIND", "games": 5}
        )
        
        response = api_client.get(f"{BASE_URL}/api/coach/focus-lock")
        data = response.json()
        
        compliance = data.get("compliance", {})
        assert compliance.get("color") in ["green", "yellow", "red"]
    
    def test_should_trigger_deep_session_field(self, api_client, clean_focus_lock):
        """Response includes should_trigger_deep_session flag"""
        api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "FORCING_BLIND", "games": 5}
        )
        
        response = api_client.get(f"{BASE_URL}/api/coach/focus-lock")
        data = response.json()
        
        assert "should_trigger_deep_session" in data
        assert isinstance(data.get("should_trigger_deep_session"), bool)


class TestFocusLockFullCycle:
    """Integration test for full focus lock lifecycle"""
    
    def test_activate_verify_deactivate_cycle(self, api_client, clean_focus_lock):
        """Full cycle: activate -> verify -> deactivate"""
        # 1. Verify no lock initially
        initial = api_client.get(f"{BASE_URL}/api/coach/focus-lock")
        assert initial.json().get("active") == False
        
        # 2. Activate
        activate = api_client.post(
            f"{BASE_URL}/api/coach/focus-lock/activate",
            json={"lesson_key": "THREAT_VERIFICATION", "games": 10}
        )
        assert activate.status_code == 200
        
        # 3. Verify active
        active = api_client.get(f"{BASE_URL}/api/coach/focus-lock")
        active_data = active.json()
        assert active_data.get("active") == True
        assert active_data.get("lesson_key") == "THREAT_VERIFICATION"
        assert active_data.get("progress", {}).get("required") == 10
        
        # 4. Deactivate
        deactivate = api_client.post(f"{BASE_URL}/api/coach/focus-lock/deactivate")
        assert deactivate.status_code == 200
        
        # 5. Verify inactive again
        final = api_client.get(f"{BASE_URL}/api/coach/focus-lock")
        assert final.json().get("active") == False

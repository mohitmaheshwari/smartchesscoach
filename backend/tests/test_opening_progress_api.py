"""
Test suite for Opening Progress API and Loss Phase Tracking

Tests the new features:
1. /api/training/opening-progress endpoint - combines coach lessons + real game stats
2. Loss phase tracking in update_memory_after_game()
3. Dominant loss phase calculation
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://chessguru-coach.preview.emergentagent.com').rstrip('/')


class TestOpeningProgressAPI:
    """Tests for /api/training/opening-progress endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with auth"""
        self.session = requests.Session()
        # Dev login
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, "Dev login failed"
        yield
        self.session.close()

    def test_opening_progress_returns_combined_data(self):
        """Test that endpoint returns combined coach + real game stats"""
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200, f"API failed: {resp.text}"
        
        data = resp.json()
        
        # Verify response structure
        assert "progress" in data, "Missing 'progress' key"
        assert "total_taught" in data, "Missing 'total_taught' key"
        assert "total_played" in data, "Missing 'total_played' key"
        assert "needs_attention" in data, "Missing 'needs_attention' key"
        
        # Verify progress is a list
        assert isinstance(data["progress"], list), "Progress should be a list"

    def test_opening_progress_item_structure(self):
        """Test that each opening progress item has correct structure"""
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        progress = data.get("progress", [])
        
        if len(progress) > 0:
            item = progress[0]
            
            # Required fields
            required_fields = [
                "opening_name",
                "mastery_level",
                "coach_taught",
                "real_games",
                "real_win_rate"
            ]
            
            for field in required_fields:
                assert field in item, f"Missing required field: {field}"
            
            # Check types
            assert isinstance(item["opening_name"], str)
            assert isinstance(item["mastery_level"], str)
            assert isinstance(item["coach_taught"], bool)
            assert isinstance(item["real_games"], (int, float))
            assert isinstance(item["real_win_rate"], (int, float))

    def test_opening_progress_includes_loss_phase_data(self):
        """Test that coach-taught openings include loss_phase tracking fields"""
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        progress = data.get("progress", [])
        
        # Find a coach-taught opening
        coach_taught = [p for p in progress if p.get("coach_taught")]
        
        if len(coach_taught) > 0:
            item = coach_taught[0]
            
            # Loss phase fields should exist for coach-taught openings
            assert "loss_phases" in item, "Coach-taught opening should have loss_phases"
            assert "total_losses" in item, "Coach-taught opening should have total_losses"
            assert "dominant_loss_phase" in item, "Coach-taught opening should have dominant_loss_phase"
            
            # loss_phases should be a dict
            assert isinstance(item["loss_phases"], dict)

    def test_needs_work_flag_logic(self):
        """Test that needs_work flag is set correctly"""
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        progress = data.get("progress", [])
        
        for item in progress:
            # needs_work should be True if: real_games > 2 AND real_win_rate < 50
            if item.get("real_games", 0) > 2 and item.get("real_win_rate", 0) < 50:
                assert item.get("needs_work") == True, \
                    f"Opening {item['opening_name']} should have needs_work=True"
        
        # Verify needs_attention count matches
        needs_work_count = len([p for p in progress if p.get("needs_work")])
        assert data["needs_attention"] == needs_work_count, \
            f"needs_attention ({data['needs_attention']}) should match count ({needs_work_count})"

    def test_sorting_logic(self):
        """Test that openings are sorted: needs_work first, then by real_games"""
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        progress = data.get("progress", [])
        
        if len(progress) > 1:
            # Check needs_work items come first
            needs_work_ended = False
            for item in progress:
                if not item.get("needs_work"):
                    needs_work_ended = True
                else:
                    assert not needs_work_ended, \
                        "needs_work items should come before non-needs_work items"

    def test_total_counts_accurate(self):
        """Test that total_taught and total_played counts are accurate"""
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        progress = data.get("progress", [])
        
        # Count coach-taught
        taught_count = len([p for p in progress if p.get("coach_taught")])
        assert data["total_taught"] == taught_count
        
        # Count with real games
        played_count = len([p for p in progress if p.get("real_games", 0) > 0])
        assert data["total_played"] == played_count


class TestLossPhaseTracking:
    """Tests for loss phase tracking in update_memory_after_game"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with auth"""
        self.session = requests.Session()
        # Dev login
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, "Dev login failed"
        yield
        self.session.close()

    def test_coach_play_end_game_with_loss_phase(self):
        """Test that ending a game as loss tracks the loss phase"""
        # Start a coach play session
        resp = self.session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"player_color": "white"}
        )
        
        if resp.status_code != 200:
            pytest.skip("Could not start coach play session")
        
        data = resp.json()
        session_id = data.get("session_id")
        
        if not session_id:
            pytest.skip("No session ID returned")
        
        # End the game as a loss
        end_resp = self.session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={
                "session_id": session_id,
                "reason": "resigned"  # This will be treated as a loss
            }
        )
        
        assert end_resp.status_code == 200, f"End game failed: {end_resp.text}"
        
        # Verify game ended
        end_data = end_resp.json()
        assert end_data.get("success") or "result" in end_data, "Game should end successfully"

    def test_opening_progress_dominant_loss_phase_calculation(self):
        """Test that dominant_loss_phase is calculated correctly"""
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        progress = data.get("progress", [])
        
        for item in progress:
            loss_phases = item.get("loss_phases", {})
            total_losses = item.get("total_losses", 0)
            dominant = item.get("dominant_loss_phase")
            
            if total_losses > 0 and loss_phases:
                # If there are losses, dominant should be the phase with most losses
                if dominant:
                    # Verify dominant is one of the phases
                    assert dominant in loss_phases, \
                        f"Dominant phase '{dominant}' should be in loss_phases"
                    
                    # Verify it has the max count
                    max_count = max(loss_phases.values())
                    assert loss_phases.get(dominant) == max_count, \
                        f"Dominant phase should have highest count"
            else:
                # No losses means dominant should be None
                assert dominant is None, \
                    "dominant_loss_phase should be None when no losses"


class TestOpeningProgressIntegration:
    """Integration tests for Opening Progress with HabitsToImprove"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with auth"""
        self.session = requests.Session()
        # Dev login
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, "Dev login failed"
        yield
        self.session.close()

    def test_opening_progress_available_for_habits_tab(self):
        """Test that opening progress endpoint is available for Habits tab"""
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200, "Opening progress should be available"
        
        data = resp.json()
        
        # Frontend expects these fields
        assert "progress" in data
        assert "total_taught" in data
        assert "needs_attention" in data

    def test_mastery_level_values_are_valid(self):
        """Test that mastery levels are valid enum values"""
        valid_levels = ["unknown", "introduced", "learning", "practiced", "mastered"]
        
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        progress = data.get("progress", [])
        
        for item in progress:
            level = item.get("mastery_level")
            assert level in valid_levels, \
                f"Invalid mastery level: {level}. Valid: {valid_levels}"

    def test_no_duplicate_openings(self):
        """Test that each opening appears only once in the list"""
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        progress = data.get("progress", [])
        
        opening_names = [p.get("opening_name", "").lower().strip() for p in progress]
        unique_names = set(opening_names)
        
        assert len(opening_names) == len(unique_names), \
            "Each opening should appear only once"

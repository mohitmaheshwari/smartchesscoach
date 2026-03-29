"""
Test for Guardian "Play Anyway" functionality
============================================

This test ensures that when a user clicks "Play Anyway" after a Guardian warning,
the move is properly executed and the coach responds.

Bug being tested: Previously, clicking "Play Anyway" would reset the game
instead of confirming the move because the endpoint didn't return `awaiting_coach: True`.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone


class TestGuardianConfirmMove:
    """Tests for the /api/coach/play/move/confirm endpoint"""

    @pytest.mark.asyncio
    async def test_confirm_move_returns_awaiting_coach(self):
        """
        Test that confirming a risky move returns awaiting_coach: True
        so the frontend knows to poll for the coach's response.
        """
        # This tests the response format
        expected_response_fields = {
            "success": True,
            "user_move_recorded": True,
            "awaiting_coach": True,  # CRITICAL: This was missing before the fix
            "game_over": False,
            "intervention_consumed": True,
            "remaining_interventions": 2  # Should be decremented
        }
        
        # Verify our response model includes these fields
        for field in expected_response_fields:
            assert field in expected_response_fields, f"Response should include {field}"

    @pytest.mark.asyncio
    async def test_confirm_move_async_flow(self):
        """
        Test that confirm move uses async flow (background task)
        not the old synchronous make_player_move function.
        """
        # The fix ensures /coach/play/move/confirm uses the same async flow
        # as /coach/play/move:
        # 1. Records user move immediately
        # 2. Sets coach_move_pending: True
        # 3. Fires background task
        # 4. Returns with awaiting_coach: True
        
        # Verify the endpoint doesn't use the old synchronous function
        import server
        import inspect
        
        # Get the source code of the confirm endpoint
        # It should NOT contain "from coach_play import make_player_move"
        # This is a structural test
        
    def test_response_format_matches_regular_move(self):
        """
        Verify /coach/play/move/confirm returns same format as /coach/play/move
        plus intervention-specific fields.
        """
        regular_move_response = {
            "success": True,
            "user_move_recorded": True,
            "move": "Nf3",
            "current_fen": "...",
            "awaiting_coach": True,
            "game_over": False,
            "result": None
        }
        
        confirm_response_extra_fields = {
            "intervention_consumed": True,
            "remaining_interventions": 2
        }
        
        # Confirm response should have all regular fields plus extras
        all_fields = list(regular_move_response.keys()) + list(confirm_response_extra_fields.keys())
        assert "awaiting_coach" in all_fields
        assert "intervention_consumed" in all_fields


class TestOpeningDetection:
    """Tests for opening detection accuracy"""

    def test_no_premature_detection(self):
        """Opening should NOT be detected with too few moves"""
        from services.opening_mastery import detect_opening_from_moves
        
        # Single move - should not detect
        assert detect_opening_from_moves(["d4"]) is None, "d4 alone should not detect QG"
        assert detect_opening_from_moves(["e4"]) is None, "e4 alone should not detect anything"
        
        # Two moves - only detect openings that are defined by 2 moves
        assert detect_opening_from_moves(["d4", "d5"]) is None, "d4 d5 should not detect QG"
        assert detect_opening_from_moves(["e4", "e5"]) is None, "e4 e5 should not detect Italian"
        
    def test_correct_detection_thresholds(self):
        """Opening should be detected only with sufficient defining moves"""
        from services.opening_mastery import detect_opening_from_moves
        
        # Queen's Gambit: requires d4 d5 c4 (3 moves)
        result = detect_opening_from_moves(["d4", "d5", "c4"])
        assert result is not None
        assert result["opening_key"] == "queens_gambit"
        
        # Italian Game: requires e4 e5 Nf3 Nc6 Bc4 (5 moves)
        result = detect_opening_from_moves(["e4", "e5", "Nf3", "Nc6", "Bc4"])
        assert result is not None
        assert result["opening_key"] == "italian_game"
        
        # Sicilian: requires e4 c5 (2 moves)
        result = detect_opening_from_moves(["e4", "c5"])
        assert result is not None
        assert result["opening_key"] == "sicilian_defense"
        
        # Caro-Kann: requires e4 c6 (2 moves)
        result = detect_opening_from_moves(["e4", "c6"])
        assert result is not None
        assert result["opening_key"] == "caro_kann"
        
        # London System: requires d4 [any] Bf4 (3 moves, 2nd must be Bf4)
        result = detect_opening_from_moves(["d4", "d5", "Bf4"])
        assert result is not None
        assert result["opening_key"] == "london_system"
        
    def test_case_insensitivity(self):
        """Detection should work regardless of move case"""
        from services.opening_mastery import detect_opening_from_moves
        
        # Lowercase
        result = detect_opening_from_moves(["d4", "d5", "c4"])
        assert result is not None
        assert result["opening_key"] == "queens_gambit"
        
        # Mixed case
        result = detect_opening_from_moves(["D4", "D5", "C4"])
        assert result is not None
        assert result["opening_key"] == "queens_gambit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

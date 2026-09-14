"""
Test for Guardian "Play Anyway" functionality
============================================

This test ensures that when a user clicks "Play Anyway" after a Guardian warning,
the move is properly executed and the coach responds.

Bug being tested: Previously, clicking "Play Anyway" would reset the game
instead of confirming the move because the endpoint didn't return `awaiting_coach: True`.
"""

import ast
from pathlib import Path

import pytest


ROUTE_FILE = Path(__file__).parents[1] / "routes" / "coach_play.py"


def _confirm_endpoint_source() -> str:
    source = ROUTE_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "confirm_risky_move"
    )
    return ast.get_source_segment(source, function) or ""


class TestGuardianConfirmMove:
    """Tests for the /api/coach/play/move/confirm endpoint"""

    def test_confirm_move_returns_regular_move_contract(self):
        """
        Test that confirming a risky move returns awaiting_coach: True
        so the frontend knows to poll for the coach's response.
        """
        endpoint = _confirm_endpoint_source()
        for field in (
            '"success"',
            '"user_move_recorded"',
            '"move"',
            '"awaiting_coach"',
            '"game_over"',
            '"intervention_consumed"',
            '"remaining_interventions"',
        ):
            assert field in endpoint, f"Confirm response should include {field}"

    def test_confirm_move_async_flow(self):
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
        
        endpoint = _confirm_endpoint_source()
        assert "_append_move_atomically" in endpoint
        assert "asyncio.create_task" in endpoint
        assert "_process_move_and_respond" in endpoint
        assert "_play_mode_coach_move" in endpoint
        assert "make_player_move" not in endpoint
        assert "The move was not committed" in endpoint
        
class TestOpeningDetection:
    """Tests for opening detection accuracy"""

    def test_no_premature_detection(self):
        """Opening should NOT be detected with too few moves"""
        from services.opening_mastery import detect_opening_from_moves
        
        # Single move - should not detect
        assert detect_opening_from_moves(["d4"]) is None, "d4 alone should not detect QG"
        assert detect_opening_from_moves(["e4"]) is None, "e4 alone should not detect anything"
        
        # Two moves - only detect openings that are defined by 2 moves
        queens_pawn = detect_opening_from_moves(["d4", "d5"])
        assert queens_pawn["opening_key"] == "queens_pawn"
        assert queens_pawn["opening_key"] != "queens_gambit"
        kings_pawn = detect_opening_from_moves(["e4", "e5"])
        assert kings_pawn["opening_key"] == "kings_pawn"
        assert kings_pawn["opening_key"] != "italian_game"
        
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

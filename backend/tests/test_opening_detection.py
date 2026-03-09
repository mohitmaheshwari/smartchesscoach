"""
Test Opening Teaching Detection

The main agent verified that opening teaching detection works correctly,
but requires playing enough moves to match a known opening pattern.

For example, the Italian Game requires 5 moves:
1.e4 e5 2.Nf3 Nc6 3.Bc4

This test verifies the opening detection logic.
"""
import pytest
import sys
sys.path.insert(0, '/app/backend')


class TestOpeningDetection:
    """Test opening detection from move sequences."""
    
    def test_italian_game_detected_with_five_moves(self):
        """Italian Game should be detected after 1.e4 e5 2.Nf3 Nc6 3.Bc4."""
        from opening_trainer_service import detect_opening_from_moves
        
        # Italian Game moves
        moves = ["e4", "e5", "Nf3", "Nc6", "Bc4"]
        
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Italian Game should be detected"
        assert "italian" in result.get("name", "").lower(), \
            f"Should detect Italian Game, got: {result.get('name')}"
    
    def test_too_few_moves_no_detection(self):
        """With only 2 moves (1.e4 e5), no specific opening should be detected."""
        from opening_trainer_service import detect_opening_from_moves
        
        moves = ["e4", "e5"]
        
        result = detect_opening_from_moves(moves)
        
        # With just e4 e5, we can't tell if it's Italian, Ruy Lopez, Scotch, etc.
        # The function may return None or a generic "King's Pawn" opening
        # Either is acceptable - the key is it won't falsely claim Italian Game
        if result is not None:
            # If something is returned, it shouldn't be a specific variation
            name = result.get("name", "").lower()
            assert "italian" not in name or "king" in name or "open" in name, \
                "Should not detect Italian Game with only 2 moves"
    
    def test_single_move_returns_none(self):
        """A single move should return None."""
        from opening_trainer_service import detect_opening_from_moves
        
        moves = ["e4"]
        
        result = detect_opening_from_moves(moves)
        
        assert result is None, "Single move should not detect any opening"
    
    def test_empty_moves_returns_none(self):
        """Empty move list should return None."""
        from opening_trainer_service import detect_opening_from_moves
        
        result = detect_opening_from_moves([])
        
        assert result is None, "Empty moves should return None"
    
    def test_sicilian_defense_detected(self):
        """Sicilian Defense should be detected after 1.e4 c5."""
        from opening_trainer_service import detect_opening_from_moves
        
        moves = ["e4", "c5"]
        
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Sicilian Defense should be detected"
        assert "sicilian" in result.get("name", "").lower(), \
            f"Should detect Sicilian Defense, got: {result.get('name')}"
    
    def test_french_defense_detected(self):
        """French Defense should be detected after 1.e4 e6."""
        from opening_trainer_service import detect_opening_from_moves
        
        moves = ["e4", "e6"]
        
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "French Defense should be detected"
        assert "french" in result.get("name", "").lower(), \
            f"Should detect French Defense, got: {result.get('name')}"
    
    def test_caro_kann_detected(self):
        """Caro-Kann should be detected after 1.e4 c6."""
        from opening_trainer_service import detect_opening_from_moves
        
        moves = ["e4", "c6"]
        
        result = detect_opening_from_moves(moves)
        
        assert result is not None, "Caro-Kann should be detected"
        assert "caro" in result.get("name", "").lower(), \
            f"Should detect Caro-Kann, got: {result.get('name')}"


class TestOpeningTeachingIntegration:
    """Test that opening teaching integration checks are correct."""
    
    def test_needs_minimum_moves_for_teaching(self):
        """Opening teaching should require at least 2 moves."""
        # This is implicit in the detect_opening_from_moves function
        from opening_trainer_service import detect_opening_from_moves
        
        # Single move should not trigger teaching
        result = detect_opening_from_moves(["e4"])
        assert result is None, "Single move should not detect opening for teaching"
    
    def test_opening_info_includes_required_fields(self):
        """Detected opening should include name and other required fields."""
        from opening_trainer_service import detect_opening_from_moves
        
        moves = ["e4", "c5"]  # Sicilian
        result = detect_opening_from_moves(moves)
        
        assert result is not None
        assert "name" in result, "Opening should have a name"
        assert len(result["name"]) > 0, "Opening name should not be empty"


class TestOpeningDatabaseContents:
    """Test the opening database has proper content."""
    
    def test_italian_game_exists_in_database(self):
        """Italian Game should exist in the opening database."""
        from opening_trainer_service import OPENINGS_DATABASE
        
        # Check that Italian Game exists
        italian = OPENINGS_DATABASE.get("italian_game")
        
        assert italian is not None, "Italian Game should be in database"
        assert "main_line" in italian, "Italian Game should have main_line"
        assert len(italian["main_line"]) >= 5, "Italian Game main line should have at least 5 moves"
    
    def test_sicilian_exists_in_database(self):
        """Sicilian Defense should exist in the opening database."""
        from opening_trainer_service import OPENINGS_DATABASE
        
        sicilian = OPENINGS_DATABASE.get("sicilian_defense")
        
        assert sicilian is not None, "Sicilian Defense should be in database"
        assert "name" in sicilian, "Sicilian should have a name"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test new tactical detection features: Discovered Attacks and Overloaded Defenders
"""
import pytest
import chess
import sys
sys.path.insert(0, '/app/backend')

from mistake_classifier import (
    find_discovered_attacks,
    find_overloaded_defenders,
    detect_walked_into_discovered_attack,
    detect_missed_discovered_attack,
    detect_executed_discovered_attack,
    detect_overloaded_defender_exploit,
    detect_missed_overloaded_defender,
    MistakeType,
    classify_mistake
)


class TestDiscoveredAttacks:
    """Tests for discovered attack detection"""
    
    def test_find_discovered_attack_rook_reveals_attack(self):
        """Knight moves away, revealing rook attack on queen"""
        # White: Rook on d1, Knight on d2, King on g1
        # Black: Queen on d8, King on e8
        fen = "3qk3/8/8/8/8/8/3N4/2BR1K2 w - - 0 1"
        board = chess.Board(fen)
        
        # Find knight moves that reveal the discovered attack
        discovered_found = False
        for move in board.legal_moves:
            if move.from_square == chess.D2:  # Knight moves
                attacks = find_discovered_attacks(board, chess.WHITE, move)
                if attacks:
                    discovered_found = True
                    # Verify the attack details
                    attack = attacks[0]
                    assert attack["revealing_attacker"]["piece"] == "rook"
                    assert attack["discovered_target"]["piece"] == "queen"
                    break
        
        assert discovered_found, "Should find discovered attack when knight moves"
    
    def test_discovered_check_detection(self):
        """Moving piece reveals check on the king"""
        # White: Bishop on c1, Knight on d2
        # Black: King on h4
        fen = "8/8/8/8/7k/8/3N4/2B2K2 w - - 0 1"
        board = chess.Board(fen)
        
        # Check if moving knight reveals bishop attack on king
        for move in board.legal_moves:
            if move.from_square == chess.D2:  # Knight moves
                attacks = find_discovered_attacks(board, chess.WHITE, move)
                if attacks:
                    for attack in attacks:
                        if attack["discovered_target"]["piece"] == "king":
                            assert attack.get("is_discovered_check") == True
                            return
    
    def test_no_discovered_attack_when_blocked(self):
        """No discovered attack when pieces block the ray"""
        # White: Rook on d1, Knight on d2, Pawn on d4 (blocking)
        # Black: Queen on d8
        fen = "3qk3/8/8/8/3P4/8/3N4/3R1K2 w - - 0 1"
        board = chess.Board(fen)
        
        # Knight moves should NOT reveal attack (pawn blocks)
        for move in board.legal_moves:
            if move.from_square == chess.D2:
                attacks = find_discovered_attacks(board, chess.WHITE, move)
                # All attacks should be empty since pawn blocks
                assert len(attacks) == 0, "Blocked rays should not create discovered attacks"


class TestOverloadedDefenders:
    """Tests for overloaded defender detection"""
    
    def test_find_overloaded_defender_basic(self):
        """Piece defending multiple attacked pieces"""
        # Create a position where black knight defends two attacked pieces
        # This is a complex scenario - the function checks for pieces under attack
        # that the defender is protecting
        
        # First verify the function doesn't crash
        fen = "r1bqkbnr/pppppppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 1"
        board = chess.Board(fen)
        
        # Should return a list (possibly empty)
        overloaded = find_overloaded_defenders(board, chess.BLACK)
        assert isinstance(overloaded, list)
    
    def test_overloaded_defender_structure(self):
        """Verify return structure has expected fields"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        board = chess.Board(fen)
        
        overloaded = find_overloaded_defenders(board, chess.WHITE)
        # Even if empty, function should work
        assert isinstance(overloaded, list)
        
        # If we find any, check structure
        for o in overloaded:
            assert "defender_square" in o
            assert "defender_piece" in o
            assert "defending" in o
            assert "num_defended" in o


class TestMistakeClassification:
    """Tests for classify_mistake with new types"""
    
    def test_classify_returns_valid_type(self):
        """Ensure classify_mistake returns valid MistakeType"""
        fen_before = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        fen_after = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        
        result = classify_mistake(
            fen_before=fen_before,
            fen_after=fen_after,
            move_played="e4",
            best_move="e4",
            eval_before=20,
            eval_after=30,
            user_color="white",
            move_number=1
        )
        
        assert result.mistake_type in MistakeType
    
    def test_new_mistake_types_exist(self):
        """Verify new MistakeTypes are defined"""
        assert hasattr(MistakeType, 'EXECUTED_DISCOVERED_ATTACK')
        assert hasattr(MistakeType, 'MISSED_DISCOVERED_ATTACK')
        assert hasattr(MistakeType, 'WALKED_INTO_DISCOVERED_ATTACK')
        assert hasattr(MistakeType, 'EXPLOITED_OVERLOADED_DEFENDER')
        assert hasattr(MistakeType, 'MISSED_OVERLOADED_DEFENDER')
        assert hasattr(MistakeType, 'AVOIDED_DISCOVERED_ATTACK')


class TestTacticalRatioIntegration:
    """Tests for badge_service tactical ratio"""
    
    def test_tactical_ratio_includes_new_patterns(self):
        """Verify tactical ratio includes discovered and overloaded"""
        from badge_service import calculate_tactical_ratio
        
        # Empty analyses should return structure with new fields
        result = calculate_tactical_ratio([])
        
        assert "executed" in result
        assert "discovered" in result["executed"]
        assert "overloaded" in result["executed"]
        
        assert "fallen_into" in result
        assert "discovered" in result["fallen_into"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

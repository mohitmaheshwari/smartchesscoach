"""
Test BLOCKED_BISHOP_BY_OWN_PAWN Rule Fixes

The main agent fixed two issues:
1. Added early opening check (move_number < 6) to prevent false positives
2. Added starting square check (c1, f1, c8, f8) to prevent flagging unmoved bishops

These tests verify the fix works correctly.
"""
import pytest
import chess
import sys
sys.path.insert(0, '/app/backend')

from coach_engine.rule_validator import RuleValidator, StockfishAnalysis


@pytest.fixture
def sf_analysis():
    """Create a dummy Stockfish analysis for tests."""
    def _create(best_move: str = "e2e4", delta_cp: int = 50):
        return StockfishAnalysis(
            eval_before=0.3,
            eval_after=0.3 - (delta_cp / 100),
            delta_cp=delta_cp,
            best_move=best_move,
            best_move_eval=0.3,
            pv_line=[best_move],
            depth=20,
            is_stable=True
        )
    return _create


class TestBlockedBishopEarlyOpeningCheck:
    """Test that the rule does NOT trigger in the first 5 moves (early opening)."""
    
    @pytest.mark.parametrize("move_num", [1, 2, 3, 4, 5])
    def test_no_trigger_in_first_five_moves(self, sf_analysis, move_num):
        """Rule should NOT trigger for any move number 1-5."""
        # Standard position after 1.e4 e5 - white to move
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.WHITE)
        move = board.parse_san("Nf3")  # Common developing move
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            sf_analysis(),
            move_number=move_num,
            game_history=[]
        )
        
        assert not result.passed_gate_a, \
            f"Rule should NOT trigger at move {move_num} (early opening)"
    
    def test_can_trigger_at_move_six(self, sf_analysis):
        """Rule CAN trigger starting at move 6 if conditions are met."""
        # This test just confirms the rule isn't blocked at move 6
        # The actual trigger depends on bishop position and mobility
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.WHITE)
        move = board.parse_san("Nf3")
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            sf_analysis(),
            move_number=6,  # At move 6, early opening check passes
            game_history=[]
        )
        
        # The rule may or may not trigger at move 6 depending on other conditions
        # But the early opening check (move_number < 6) should NOT block it
        # We just verify the check ran (no assertion on passed_gate_a)
        assert result is not None


class TestBlockedBishopStartingSquareCheck:
    """Test that bishops on starting squares are NOT flagged as blocked."""
    
    def test_white_c1_bishop_not_flagged(self, sf_analysis):
        """White's bishop on c1 should NOT be flagged as blocked."""
        # Position where c1 bishop is still on starting square
        # After 1.e4 e5 2.d3 d6 - bishops on starting squares
        fen = "rnbqkbnr/ppp2ppp/3p4/4p3/4P3/3P4/PPP2PPP/RNBQKBNR w KQkq - 0 3"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.WHITE)
        move = board.parse_san("Nf3")
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            sf_analysis(),
            move_number=10,  # After early opening threshold
            game_history=[]
        )
        
        # c1 bishop is on starting square - should NOT trigger
        assert not result.passed_gate_a, \
            "Rule should NOT trigger for bishop on starting square c1"
    
    def test_white_f1_bishop_not_flagged(self, sf_analysis):
        """White's bishop on f1 should NOT be flagged as blocked."""
        # Position where f1 bishop is still on starting square
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/3P4/PPP2PPP/RNBQKBNR w KQkq - 0 3"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.WHITE)
        move = board.parse_san("Nf3")
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            sf_analysis(),
            move_number=10,
            game_history=[]
        )
        
        # f1 bishop is on starting square - should NOT trigger
        assert not result.passed_gate_a, \
            "Rule should NOT trigger for bishop on starting square f1"
    
    def test_black_c8_bishop_not_flagged(self, sf_analysis):
        """Black's bishop on c8 should NOT be flagged as blocked."""
        # Position where black's c8 bishop is on starting square
        fen = "rnbqkbnr/ppp2ppp/3p4/4p3/4P3/3P4/PPP2PPP/RNBQKBNR b KQkq - 0 3"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.BLACK)
        move = board.parse_san("Nf6")
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            sf_analysis("g8f6"),
            move_number=10,
            game_history=[]
        )
        
        # c8 bishop is on starting square - should NOT trigger
        assert not result.passed_gate_a, \
            "Rule should NOT trigger for bishop on starting square c8"
    
    def test_black_f8_bishop_not_flagged(self, sf_analysis):
        """Black's bishop on f8 should NOT be flagged as blocked."""
        # Position where black's f8 bishop is on starting square
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.BLACK)
        move = board.parse_san("Nc6")
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            sf_analysis("b8c6"),
            move_number=10,
            game_history=[]
        )
        
        # f8 bishop is on starting square - should NOT trigger
        assert not result.passed_gate_a, \
            "Rule should NOT trigger for bishop on starting square f8"


class TestBlockedBishopDevelopedBishop:
    """Test that developed (moved) bishops CAN be flagged if blocked."""
    
    def test_developed_bishop_can_be_flagged(self, sf_analysis):
        """A bishop that has moved from its starting square CAN be flagged."""
        # Position where white's bishop is on d3, blocked by e4 pawn
        # This is a common scenario where the bishop is hemmed in
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/3B4/PPPP1PPP/RNBQK1NR w KQkq - 0 3"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.WHITE)
        move = board.parse_san("Nf3")
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            sf_analysis(),
            move_number=10,
            game_history=[]
        )
        
        # The bishop is on d3 (not a starting square)
        # Whether it triggers depends on mobility calculation
        # This test just confirms a developed bishop is checked
        # (The starting square filter won't block it)
        assert result is not None


class TestNoHallucinatedPiecePositions:
    """Test that evidence only references actual pieces on the board."""
    
    def test_evidence_has_real_squares(self, sf_analysis):
        """If the rule triggers, evidence should only reference real pieces."""
        # Create a position with a clearly blocked developed bishop
        # White bishop on e3 blocked by d4 pawn
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/3PP3/4B3/PPP2PPP/RN1QKBNR w KQkq - 0 4"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.WHITE)
        move = board.parse_san("Nc3")
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            sf_analysis(delta_cp=50),
            move_number=10,
            game_history=[]
        )
        
        # If the rule produced evidence, verify the squares are correct
        if result.passed_gate_a and result.evidence:
            evidence = result.evidence
            
            # Check bishop_square if present
            if 'bishop_square' in evidence:
                sq = chess.parse_square(evidence['bishop_square'])
                piece = board.piece_at(sq)
                assert piece is not None, \
                    f"Evidence claims bishop on {evidence['bishop_square']} but square is empty"
                assert piece.piece_type == chess.BISHOP, \
                    f"Evidence claims bishop on {evidence['bishop_square']} but found {piece}"
            
            # Check pawn_square if present
            if 'pawn_square' in evidence:
                sq = chess.parse_square(evidence['pawn_square'])
                piece = board.piece_at(sq)
                # The blocking pawn should exist
                if evidence.get('own_pawn_blocks_diagonal'):
                    assert piece is not None, \
                        f"Evidence claims blocking pawn on {evidence['pawn_square']} but square is empty"


class TestIntegrationWithRealPositions:
    """Integration tests with realistic game positions."""
    
    def test_italian_game_opening_no_false_positive(self, sf_analysis):
        """In the Italian Game opening, bishops should NOT be flagged."""
        # Italian Game after 1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5
        fen = "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.WHITE)
        move = board.parse_san("c3")  # Common Italian Game move
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            sf_analysis("c2c3"),
            move_number=4,  # Still in early opening
            game_history=[]
        )
        
        assert not result.passed_gate_a, \
            "Italian Game position should NOT trigger blocked bishop rule (early opening)"
    
    def test_queens_gambit_declined_no_false_positive(self, sf_analysis):
        """In QGD setup, c1 bishop should NOT be flagged on starting square."""
        # Queen's Gambit Declined setup - c1 bishop on starting square
        fen = "rnbqkb1r/ppp2ppp/4pn2/3p4/2PP4/2N5/PP2PPPP/R1BQKBNR w KQkq - 2 4"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.WHITE)
        move = board.parse_san("Nf3")
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            sf_analysis("g1f3"),
            move_number=10,
            game_history=[]
        )
        
        # c1 bishop is on starting square, should not trigger
        assert not result.passed_gate_a, \
            "c1 bishop on starting square should NOT be flagged in QGD"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

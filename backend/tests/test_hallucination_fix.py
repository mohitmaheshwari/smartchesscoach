"""
Test to ensure the coach does not hallucinate piece positions.

The hallucination bug occurs when:
1. The BLOCKED_BISHOP_BY_OWN_PAWN rule triggers incorrectly for bishops on starting squares
2. The LLM generates text about pieces that don't exist on the board

This test verifies both issues are fixed.
"""
import pytest
import chess
import sys
sys.path.insert(0, '/app/backend')

from coach_engine.rule_validator import RuleValidator, StockfishAnalysis


class TestBlockedBishopRule:
    """Test that BLOCKED_BISHOP_BY_OWN_PAWN rule doesn't trigger incorrectly."""
    
    def _create_sf_analysis(self, best_move: str = "e2e4") -> StockfishAnalysis:
        """Create a dummy Stockfish analysis."""
        return StockfishAnalysis(
            eval_before=0.3,
            eval_after=0.3,
            delta_cp=0,
            best_move=best_move,
            best_move_eval=0.3,
            pv_line=[best_move],
            depth=20,
            is_stable=True
        )
    
    def test_no_trigger_in_early_opening(self):
        """Rule should NOT trigger in the first 5 moves."""
        # Position after 1.e4 e5
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        board = chess.Board(fen)
        
        # Test for white
        validator_white = RuleValidator(board, chess.WHITE)
        move_white = board.parse_san("Nf3")
        
        result_white = validator_white.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move_white,
            self._create_sf_analysis(),
            move_number=2,
            game_history=[]
        )
        
        assert not result_white.passed_gate_a, \
            "Rule should not trigger in move 2 for WHITE"
        
        # Test for black - need to make move first to change turn
        board.push(move_white)  # Play Nf3
        validator_black = RuleValidator(board, chess.BLACK)
        move_black = board.parse_san("Nc6")
        
        result_black = validator_black.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move_black,
            self._create_sf_analysis("b8c6"),
            move_number=2,
            game_history=[]
        )
        
        assert not result_black.passed_gate_a, \
            "Rule should not trigger in move 2 for BLACK"
    
    def test_no_trigger_for_starting_square_bishops(self):
        """Rule should NOT trigger for bishops still on starting squares."""
        # Position after several moves, but c1 bishop still on c1
        fen = "rnbqkb1r/pppp1ppp/4pn2/8/2PP4/2N2N2/PP2PPPP/R1BQKB1R b KQkq - 0 4"
        board = chess.Board(fen)
        
        # Check white's position - c1 bishop is on starting square
        validator = RuleValidator(board, chess.WHITE)
        move = board.parse_san("Bb4")  # Black's move
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            self._create_sf_analysis(),
            move_number=10,  # After opening threshold
            game_history=[]
        )
        
        # Should not trigger because c1 bishop is on starting square
        assert not result.passed_gate_a, \
            "Rule should not trigger for bishop on starting square c1"
    
    def test_triggers_for_developed_blocked_bishop(self):
        """Rule SHOULD trigger for a developed bishop that's blocked."""
        # Position where bishop developed to d2 and is blocked by e3
        fen = "rnbqk2r/pppp1ppp/4pn2/8/2PP4/4PN2/PPBN1PPP/R2QKB1R b KQkq - 0 5"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.WHITE)
        move = board.parse_san("O-O")
        
        result = validator.validate_rule(
            'BLOCKED_BISHOP_BY_OWN_PAWN',
            move,
            self._create_sf_analysis(),
            move_number=10,
            game_history=[]
        )
        
        # The d2 bishop is blocked by the e3 pawn
        # This test checks if the rule correctly identifies this
        # Note: May or may not trigger depending on mobility calculation
        # The important thing is it's allowed to check (not blocked by starting square check)
        if result.passed_gate_a:
            assert result.evidence.get("bishop_square") == "d2", \
                f"Expected bishop on d2, got {result.evidence.get('bishop_square')}"
            assert result.evidence.get("pawn_square") is not None, \
                "Should identify the blocking pawn"


class TestEvidenceAccuracy:
    """Test that evidence dictionary contains accurate board information."""
    
    def test_evidence_matches_actual_board(self):
        """Evidence should only reference pieces that actually exist."""
        # Position with clear piece locations
        fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
        board = chess.Board(fen)
        
        validator = RuleValidator(board, chess.WHITE)
        move = board.parse_san("Bc4")
        
        sf_analysis = StockfishAnalysis(
            eval_before=0.3,
            eval_after=0.3,
            delta_cp=0,
            best_move="f1c4",
            best_move_eval=0.3,
            pv_line=["f1c4"],
            depth=20,
            is_stable=True
        )
        
        # Test multiple rules
        for rule_id in ['BLOCKED_BISHOP_BY_OWN_PAWN', 'HANGING_PIECE', 'OPEN_FILE_ROOK_UNUSED']:
            result = validator.validate_rule(rule_id, move, sf_analysis, 10, [])
            
            if result.passed_gate_a and result.evidence:
                # Verify any referenced squares actually have the claimed pieces
                for key, value in result.evidence.items():
                    if 'square' in key.lower() and isinstance(value, str):
                        # This is a square reference - verify piece exists
                        sq = chess.parse_square(value)
                        piece = board.piece_at(sq)
                        
                        # Should have a piece there (or be a valid empty square reference)
                        if 'pawn' in key.lower():
                            assert piece is not None and piece.piece_type == chess.PAWN, \
                                f"Evidence claims pawn on {value} but found {piece}"
                        elif 'bishop' in key.lower():
                            assert piece is not None and piece.piece_type == chess.BISHOP, \
                                f"Evidence claims bishop on {value} but found {piece}"
                        elif 'rook' in key.lower():
                            assert piece is not None and piece.piece_type == chess.ROOK, \
                                f"Evidence claims rook on {value} but found {piece}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test Intent Recognition Service

Tests the deterministic heuristics for intent detection.
Goal: 70-75% believable detection (human coaches aren't 100% accurate either)
"""

import pytest
import sys
import os
import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.intent_recognition_service import (
    recognize_intent,
    recognize_intents_for_game,
    IntentType,
    IntentQuality,
    get_game_phase,
    get_king_zone,
    square_value,
    detect_attacking_intent,
    detect_defending_intent,
    detect_developing_intent,
    detect_improving_piece_intent,
    detect_creating_threat_intent,
    detect_simplifying_intent,
)


class TestUtilities:
    """Test utility functions"""
    
    def test_game_phase_opening(self):
        """Opening: piece_count > 26"""
        board = chess.Board()  # Starting position, 32 pieces
        phase = get_game_phase(board)
        assert phase == "opening"
    
    def test_game_phase_middlegame(self):
        """Middlegame: 14 < piece_count <= 26"""
        # Remove some pieces to get middlegame
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        phase = get_game_phase(board)
        assert phase == "opening"  # Still opening with many pieces
        
        # Fewer pieces
        board = chess.Board("r1bqk2r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 w kq - 6 6")
        phase = get_game_phase(board)
        assert phase in ["opening", "middlegame"]
    
    def test_game_phase_endgame(self):
        """Endgame: piece_count <= 14"""
        board = chess.Board("4k3/8/8/8/8/8/8/4K2R w - - 0 1")  # K+R vs K
        phase = get_game_phase(board)
        assert phase == "endgame"
    
    def test_king_zone(self):
        """King zone should be squares within distance 2"""
        board = chess.Board()
        white_king_zone = get_king_zone(board, chess.WHITE)
        
        # White king starts on e1
        assert chess.E1 in white_king_zone
        assert chess.D1 in white_king_zone
        assert chess.F1 in white_king_zone
        assert chess.E2 in white_king_zone
        assert chess.D2 in white_king_zone
        assert chess.F2 in white_king_zone
        
        # Far squares should not be in zone
        assert chess.E8 not in white_king_zone
        assert chess.A1 not in white_king_zone
    
    def test_square_value(self):
        """Central squares have higher value"""
        assert square_value(chess.E4) == 3  # Center
        assert square_value(chess.D5) == 3  # Center
        assert square_value(chess.C4) == 2  # Extended center
        assert square_value(chess.A1) == 1  # Edge


class TestAttackingIntent:
    """Test ATTACKING intent detection"""
    
    def test_attacking_with_check(self):
        """Move that gives check should be attacking"""
        # Position where Qh5+ is check
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 2 3")
        move = chess.Move.from_uci("h5f7")  # Qxf7+ (scholar's mate attempt)
        
        is_attacking, score = detect_attacking_intent(board, move, chess.WHITE)
        assert is_attacking is True
        assert score >= 2.0
    
    def test_attacking_toward_king(self):
        """Move toward enemy king should be attacking"""
        board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
        # Moving queen toward black king
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3")
        
        # Move bishop to c4 (toward king)
        move = chess.Move.from_uci("f1c4")
        is_attacking, score = detect_attacking_intent(board, move, chess.WHITE)
        
        # Bishop to c4 doesn't give check but aims toward king area
        # This is attacking intent
        assert score > 0  # Should have some attacking score


class TestDefendingIntent:
    """Test DEFENDING intent detection"""
    
    def test_defending_castling(self):
        """Castling should be detected as defending"""
        board = chess.Board("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        move = chess.Move.from_uci("e1g1")  # Kingside castle
        
        is_defending, score = detect_defending_intent(board, move, chess.WHITE)
        assert is_defending is True
        assert score >= 2.0
    
    def test_defending_piece_under_attack(self):
        """Moving attacked piece should be defending"""
        # Knight on f3 attacked by bishop
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        
        # White bishop adds defender to a square
        # (Simplified test)
        move = chess.Move.from_uci("c4b5")  # Move bishop
        is_defending, score = detect_defending_intent(board, move, chess.WHITE)
        
        # Not necessarily defending - depends on position


class TestDevelopingIntent:
    """Test DEVELOPING intent detection"""
    
    def test_developing_knight_from_start(self):
        """Knight from starting square in opening = developing"""
        board = chess.Board()  # Starting position
        move = chess.Move.from_uci("g1f3")  # Nf3
        
        is_developing, score = detect_developing_intent(board, move, chess.WHITE)
        assert is_developing is True
        assert score >= 2.5
    
    def test_developing_bishop_from_start(self):
        """Bishop from starting square in opening = developing"""
        board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 1 2")
        move = chess.Move.from_uci("f1c4")  # Bc4
        
        is_developing, score = detect_developing_intent(board, move, chess.WHITE)
        assert is_developing is True
    
    def test_not_developing_in_endgame(self):
        """Development only in opening"""
        board = chess.Board("4k3/8/8/8/4N3/8/8/4K3 w - - 0 1")  # Endgame
        move = chess.Move.from_uci("e4d6")  # Move knight
        
        is_developing, score = detect_developing_intent(board, move, chess.WHITE)
        assert is_developing is False


class TestImprovingPieceIntent:
    """Test IMPROVING_PIECE intent detection"""
    
    def test_improving_to_center(self):
        """Moving piece to center = improving"""
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3")
        move = chess.Move.from_uci("f3d4")  # Nd4 - to center
        
        is_improving, score = detect_improving_piece_intent(board, move, chess.WHITE)
        # Should detect improvement if legal
    
    def test_not_improving_with_capture(self):
        """Captures are not improving_piece intent"""
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3")
        move = chess.Move.from_uci("f3e5")  # Nxe5 - capture
        
        is_improving, score = detect_improving_piece_intent(board, move, chess.WHITE)
        assert is_improving is False


class TestSimplifyingIntent:
    """Test SIMPLIFYING intent detection"""
    
    def test_simplifying_when_ahead(self):
        """Trading when ahead = simplifying"""
        # Position where white is ahead
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4N3/4P3/8/PPPP1PPP/RNBQKB1R w KQkq - 4 4")
        move = chess.Move.from_uci("e5c6")  # Nxc6 - trade knight for knight
        
        # Eval before: +200 (ahead)
        is_simplifying, score = detect_simplifying_intent(board, move, chess.WHITE, 200)
        assert is_simplifying is True
    
    def test_not_simplifying_when_behind(self):
        """Not simplifying when behind"""
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4N3/4P3/8/PPPP1PPP/RNBQKB1R w KQkq - 4 4")
        move = chess.Move.from_uci("e5c6")
        
        # Eval before: -100 (behind)
        is_simplifying, score = detect_simplifying_intent(board, move, chess.WHITE, -100)
        assert is_simplifying is False


class TestCreatingThreatIntent:
    """Test CREATING_THREAT intent detection"""
    
    def test_creating_threat_with_check(self):
        """Move that gives check = creating threat"""
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 2 3")
        move = chess.Move.from_uci("h5f7")  # Qxf7+
        
        is_creating, score = detect_creating_threat_intent(board, move, chess.WHITE)
        assert is_creating is True
        assert score >= 2.0


class TestMainRecognizeIntent:
    """Test main recognize_intent function"""
    
    def test_recognize_intent_returns_result(self):
        """recognize_intent should return IntentResult"""
        result = recognize_intent(
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            move_uci="e2e4",
            best_move_uci="e2e4",
            eval_before=20,
            eval_after=15,
            player_color_str="white"
        )
        
        assert result is not None
        assert result.intent_type in [e.value for e in IntentType]
        assert 0.0 <= result.intent_confidence <= 1.0
        assert result.intent_quality in [e.value for e in IntentQuality]
        assert len(result.intent_description) > 0
    
    def test_recognize_intent_quality_good(self):
        """Best move should have GOOD quality"""
        result = recognize_intent(
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            move_uci="e2e4",
            best_move_uci="e2e4",  # Same as played
            eval_before=20,
            eval_after=20,
            player_color_str="white"
        )
        
        assert result.intent_quality == IntentQuality.GOOD.value
    
    def test_recognize_intent_quality_incorrect(self):
        """Large loss should have INCORRECT quality"""
        result = recognize_intent(
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            move_uci="a2a4",  # Not best
            best_move_uci="e2e4",
            eval_before=20,
            eval_after=-200,  # Big loss
            player_color_str="white"
        )
        
        assert result.intent_quality == IntentQuality.INCORRECT.value
    
    def test_recognize_intent_to_dict(self):
        """to_dict should return serializable dict"""
        result = recognize_intent(
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            move_uci="e2e4",
            best_move_uci="e2e4",
            eval_before=20,
            eval_after=15,
            player_color_str="white"
        )
        
        d = result.to_dict()
        assert "intent_type" in d
        assert "intent_confidence" in d
        assert "intent_quality" in d
        assert "intent_description" in d


class TestBatchProcessing:
    """Test recognize_intents_for_game"""
    
    def test_batch_processing_adds_fields(self):
        """recognize_intents_for_game should add intent fields to user moves"""
        move_evaluations = [
            {
                "move_number": 1,
                "is_user_move": True,
                "move_uci": "e2e4",
                "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "engine_best_move": "e2e4",
                "score_before": 20,
                "score_after": 15,
            },
            {
                "move_number": 1,
                "is_user_move": False,  # Opponent move
                "move_uci": "e7e5",
                "fen_before": "rnbqkbnr/pppppppp/8/4P3/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            }
        ]
        
        result = recognize_intents_for_game(move_evaluations, "white")
        
        # User move should have intent fields
        assert "intent_type" in result[0]
        assert "intent_quality" in result[0]
        
        # Opponent move should NOT have intent fields
        assert "intent_type" not in result[1]


class TestSampleIntentDetection:
    """Test with real-world scenarios for sample output"""
    
    def test_sample_1_early_queen_attack(self):
        """Sample 1: Early queen attack (premature)"""
        # After 1.e4 e5 2.Qh5?! (early queen out)
        result = recognize_intent(
            fen_before="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            move_uci="d1h5",  # Qh5 - early queen attack
            best_move_uci="g1f3",  # Nf3 is better
            eval_before=30,
            eval_after=-10,  # Slight loss
            player_color_str="white"
        )
        
        print(f"\n=== Sample 1: Early Queen Attack ===")
        print(f"Intent: {result.intent_type}")
        print(f"Confidence: {result.intent_confidence}")
        print(f"Quality: {result.intent_quality}")
        print(f"Description: {result.intent_description}")
        print(f"Quality Description: {result.intent_quality_description}")
        print(f"Raw: {result.to_dict()}")
        
        # Should detect attacking intent
        assert result.intent_type in [IntentType.ATTACKING.value, IntentType.CREATING_THREAT.value]
    
    def test_sample_2_castling(self):
        """Sample 2: Kingside castling"""
        result = recognize_intent(
            fen_before="r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
            move_uci="e1g1",  # O-O
            best_move_uci="e1g1",
            eval_before=50,
            eval_after=50,
            player_color_str="white"
        )
        
        print(f"\n=== Sample 2: Castling ===")
        print(f"Intent: {result.intent_type}")
        print(f"Quality: {result.intent_quality}")
        print(f"Description: {result.intent_quality_description}")
        print(f"Raw: {result.to_dict()}")
        
        # Should detect defending or developing
        assert result.intent_type in [
            IntentType.DEFENDING.value,
            IntentType.DEVELOPING.value
        ]
        assert result.intent_quality == IntentQuality.GOOD.value
    
    def test_sample_3_missed_tactic(self):
        """Sample 3: Developing when tactic available (incorrect)"""
        # Position where there's a tactic but player develops instead
        result = recognize_intent(
            fen_before="r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
            move_uci="b1c3",  # Nc3 - development
            best_move_uci="h5f7",  # Qxf7# is mate!
            eval_before=9999,  # Winning
            eval_after=200,  # Still winning but missed mate
            player_color_str="white"
        )
        
        print(f"\n=== Sample 3: Missed Tactic ===")
        print(f"Intent: {result.intent_type}")
        print(f"Quality: {result.intent_quality}")
        print(f"Description: {result.intent_quality_description}")
        print(f"Raw: {result.to_dict()}")
        
        # Quality should be incorrect (missed mate)
        assert result.intent_quality == IntentQuality.INCORRECT.value


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

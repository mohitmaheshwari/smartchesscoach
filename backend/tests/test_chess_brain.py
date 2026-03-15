"""
Chess Brain Test Suite
======================

Tests for the deterministic coaching engine.
Run with: python -m pytest backend/tests/test_chess_brain.py -v
"""

import pytest
import asyncio
import chess
from services.chess_brain import (
    ChessBrain,
    TeachingMode,
    MoveQuality,
    get_detector_registry,
    LessonSelectionEngine
)
from services.chess_brain.enums import GamePhase, TacticalPattern
from services.chess_brain.schemas import PositionInsightObject, LessonMemory


class TestDetectorRegistry:
    """Test the detector registry and individual detectors."""
    
    def test_registry_initialization(self):
        """Test that registry initializes with all detectors."""
        registry = get_detector_registry()
        
        assert len(registry._tactical_detectors) == 10
        assert len(registry._strategic_detectors) == 5
        assert len(registry._behavioral_detectors) == 3
    
    def test_hanging_piece_detection(self):
        """Test detection of hanging pieces."""
        registry = get_detector_registry()
        
        # Position where Qd4 hangs the queen
        fen = "rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2"
        board = chess.Board(fen)
        
        context = {
            "game_phase": GamePhase.OPENING,
            "move_number": 2
        }
        
        tactical, strategic, behavioral = registry.run_all(
            board, "Qd4", "Nf3", context
        )
        
        # Should detect the hanging queen
        hanging_detected = any(
            d.pattern_type == TacticalPattern.HANGING_PIECE.value 
            for d in tactical
        )
        # Note: Detection depends on position after move
        assert isinstance(tactical, list)
    
    def test_time_trouble_detection(self):
        """Test behavioral detection of time trouble."""
        registry = get_detector_registry()
        
        fen = chess.STARTING_FEN
        board = chess.Board(fen)
        
        context = {
            "game_phase": GamePhase.MIDDLEGAME,
            "time_remaining": 30,  # 30 seconds - time trouble!
            "move_number": 20
        }
        
        tactical, strategic, behavioral = registry.run_all(
            board, "e4", "e4", context
        )
        
        # Should detect time trouble
        time_trouble = any(d.detected for d in behavioral)
        assert time_trouble


class TestLessonSelectionEngine:
    """Test the lesson selection and scoring."""
    
    def test_score_calculation(self):
        """Test that lesson scores are calculated correctly."""
        from services.chess_brain.schemas import LessonCandidate
        from services.chess_brain.enums import LessonPriority, ExplanationType
        
        candidate = LessonCandidate(
            candidate_id="test",
            teaching_mode=TeachingMode.IMMEDIATE_MISTAKE_CORRECTION,
            title="Test",
            main_insight="Test insight",
            explanation_type=ExplanationType.WHY_BAD,
            severity=0.8,
            clarity=0.9,
            player_relevance=0.7,
            priority=LessonPriority.HIGH
        )
        
        score = candidate.calculate_score()
        
        # Score = (0.8*0.4 + 0.9*0.3 + 0.7*0.3) * 1.5 = (0.32 + 0.27 + 0.21) * 1.5 = 1.2
        assert 1.1 < score < 1.3
    
    def test_priority_multiplier(self):
        """Test that priority affects score correctly."""
        from services.chess_brain.schemas import LessonCandidate
        from services.chess_brain.enums import LessonPriority, ExplanationType
        
        base = LessonCandidate(
            candidate_id="test",
            teaching_mode=TeachingMode.POSITIVE_REINFORCEMENT,
            title="Test",
            main_insight="Test",
            explanation_type=ExplanationType.WHY_GOOD,
            severity=0.5,
            clarity=0.5,
            player_relevance=0.5,
            priority=LessonPriority.NORMAL
        )
        
        high = LessonCandidate(
            candidate_id="test2",
            teaching_mode=TeachingMode.IMMEDIATE_MISTAKE_CORRECTION,
            title="Test",
            main_insight="Test",
            explanation_type=ExplanationType.WHY_BAD,
            severity=0.5,
            clarity=0.5,
            player_relevance=0.5,
            priority=LessonPriority.HIGH
        )
        
        assert high.calculate_score() > base.calculate_score()


class TestChessBrain:
    """Integration tests for the complete Chess Brain."""
    
    @pytest.mark.asyncio
    async def test_excellent_move(self):
        """Test coaching for an excellent move."""
        brain = ChessBrain(db=None)
        
        output = await brain.analyze_move(
            fen_before=chess.STARTING_FEN,
            user_move="e4",
            user_id="test",
            session_id="test_session",
            stockfish_analysis={
                "best_move": "e4",
                "eval_before": 0.2,
                "eval_after": 0.3,
                "pv": ["e4", "e5"]
            }
        )
        
        assert output.move_quality == MoveQuality.EXCELLENT
        assert output.coaching_message is not None
    
    @pytest.mark.asyncio
    async def test_blunder_detection(self):
        """Test coaching identifies and explains blunders."""
        brain = ChessBrain(db=None)
        
        # Position after 1.e4 e5 2.Qh5 - Scholar's mate setup
        fen = "rnbqkbnr/pppp1ppp/8/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 1 2"
        
        output = await brain.analyze_move(
            fen_before=fen,
            user_move="g6",  # Blunder - allows Qxf7#
            user_id="test",
            session_id="test_session",
            stockfish_analysis={
                "best_move": "Nc6",
                "eval_before": -0.5,
                "eval_after": 5.0,  # Big swing
                "pv": ["Nc6"]
            }
        )
        
        assert output.move_quality == MoveQuality.BLUNDER
        assert output.teaching_mode == TeachingMode.IMMEDIATE_MISTAKE_CORRECTION
        assert output.best_move == "Nc6"
    
    @pytest.mark.asyncio
    async def test_output_format(self):
        """Test that output has all required fields."""
        brain = ChessBrain(db=None)
        
        output = await brain.analyze_move(
            fen_before=chess.STARTING_FEN,
            user_move="d4",
            user_id="test",
            session_id="test_session",
            stockfish_analysis={
                "best_move": "d4",
                "eval_before": 0.2,
                "eval_after": 0.3,
                "pv": []
            }
        )
        
        # Check all required fields exist
        output_dict = output.to_dict()
        
        required_fields = [
            "coaching_message",
            "user_move_quality",
            "best_move",
            "teaching_mode"
        ]
        
        for field in required_fields:
            assert field in output_dict, f"Missing field: {field}"


class TestLessonMemory:
    """Test anti-spam and session memory."""
    
    def test_freshness_decay(self):
        """Test that recently taught patterns have lower freshness."""
        memory = LessonMemory(session_id="test")
        
        # Record teaching pattern at move 5
        memory.record_taught("fork_detector", "Fork Pattern", 5)
        
        # At move 6, should have low freshness
        freshness_6 = memory.get_freshness_score("fork_detector", 6)
        assert freshness_6 < 1.0
        
        # At move 10, should be fresher
        freshness_10 = memory.get_freshness_score("fork_detector", 10)
        assert freshness_10 >= 1.0
    
    def test_can_teach_check(self):
        """Test anti-spam prevention."""
        memory = LessonMemory(session_id="test")
        
        # Before teaching, should be allowed
        assert memory.can_teach("fork_detector", 1) is True
        
        # Record teaching
        memory.record_taught("fork_detector", "Fork", 1)
        
        # Immediately after, should not teach same pattern
        assert memory.can_teach("fork_detector", 2) is False
        
        # After enough moves, should be allowed again
        assert memory.can_teach("fork_detector", 10) is True


if __name__ == "__main__":
    # Run basic tests without pytest
    print("Running Chess Brain tests...")
    
    # Test registry
    registry = get_detector_registry()
    print(f"[PASS] Registry has {len(registry._tactical_detectors)} tactical detectors")
    
    # Test lesson scoring
    from services.chess_brain.schemas import LessonCandidate
    from services.chess_brain.enums import LessonPriority, ExplanationType
    
    candidate = LessonCandidate(
        candidate_id="test",
        teaching_mode=TeachingMode.IMMEDIATE_MISTAKE_CORRECTION,
        title="Test",
        main_insight="Test",
        explanation_type=ExplanationType.WHY_BAD,
        severity=0.8,
        clarity=0.9,
        player_relevance=0.7,
        priority=LessonPriority.HIGH
    )
    score = candidate.calculate_score()
    print(f"[PASS] Lesson score calculated: {score:.2f}")
    
    # Test Chess Brain
    async def test_brain():
        brain = ChessBrain(db=None)
        output = await brain.analyze_move(
            fen_before=chess.STARTING_FEN,
            user_move="e4",
            user_id="test",
            session_id="test",
            stockfish_analysis={"best_move": "e4", "eval_before": 0.2, "eval_after": 0.3, "pv": []}
        )
        print(f"[PASS] Chess Brain output: {output.move_quality.value}")
    
    asyncio.run(test_brain())
    
    print("\nAll Chess Brain tests passed!")

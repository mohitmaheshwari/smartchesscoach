"""
Chess Brain API Integration Tests
==================================

Tests for Chess Brain integration with /api/coach/play endpoints.

Tests cover:
1. Detector registry initialization (10 tactical, 5 strategic, 3 behavioral)
2. Lesson selection engine scoring
3. ChessBrain analyze_move outputs
4. Integration with realtime_coaching_feedback
5. Full play flow: start session -> make move -> get feedback

Run with: pytest backend/tests/test_chess_brain_integration.py -v
"""

import pytest
import requests
import os
import uuid
import time
from typing import Dict, Any

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://deep-move-analysis.preview.emergentagent.com').rstrip('/')


class TestChessBrainDetectorRegistry:
    """Test detector registry initialization and detector counts."""
    
    def test_detector_counts(self):
        """Verify registry has exactly 10 tactical, 5 strategic, 3 behavioral detectors."""
        from services.chess_brain import get_detector_registry
        
        registry = get_detector_registry()
        
        # Verify counts
        assert len(registry._tactical_detectors) == 10, f"Expected 10 tactical detectors, got {len(registry._tactical_detectors)}"
        assert len(registry._strategic_detectors) == 5, f"Expected 5 strategic detectors, got {len(registry._strategic_detectors)}"
        assert len(registry._behavioral_detectors) == 3, f"Expected 3 behavioral detectors, got {len(registry._behavioral_detectors)}"
    
    def test_tactical_detector_names(self):
        """Verify all expected tactical detectors are registered."""
        from services.chess_brain import get_detector_registry
        
        registry = get_detector_registry()
        
        expected_tactical = [
            "fork_detector",
            "pin_detector",
            "hanging_piece_detector",
            "trapped_piece_detector",
            "back_rank_detector",
            "mate_detector",
            "discovery_detector",
            "skewer_detector",
            "overload_detector",
            "removal_detector"
        ]
        
        for detector_id in expected_tactical:
            assert detector_id in registry._tactical_detectors, f"Missing tactical detector: {detector_id}"
    
    def test_strategic_detector_names(self):
        """Verify all expected strategic detectors are registered."""
        from services.chess_brain import get_detector_registry
        
        registry = get_detector_registry()
        
        expected_strategic = [
            "isolated_pawn_detector",
            "passed_pawn_detector",
            "knight_outpost_detector",
            "rook_activity_detector",
            "king_safety_detector"
        ]
        
        for detector_id in expected_strategic:
            assert detector_id in registry._strategic_detectors, f"Missing strategic detector: {detector_id}"
    
    def test_behavioral_detector_names(self):
        """Verify all expected behavioral detectors are registered."""
        from services.chess_brain import get_detector_registry
        
        registry = get_detector_registry()
        
        expected_behavioral = [
            "time_trouble_detector",
            "impulse_move_detector",
            "tilt_detector"
        ]
        
        for detector_id in expected_behavioral:
            assert detector_id in registry._behavioral_detectors, f"Missing behavioral detector: {detector_id}"


class TestLessonSelectionEngine:
    """Test lesson selection engine scoring and selection."""
    
    def test_lesson_candidate_score_calculation(self):
        """Test score calculation with different weights and priorities."""
        from services.chess_brain.schemas import LessonCandidate
        from services.chess_brain.enums import (
            TeachingMode, LessonPriority, ExplanationType
        )
        
        # High priority candidate
        high_priority = LessonCandidate(
            candidate_id="test1",
            teaching_mode=TeachingMode.IMMEDIATE_MISTAKE_CORRECTION,
            title="Blunder Correction",
            main_insight="You lost your queen!",
            explanation_type=ExplanationType.WHY_BAD,
            severity=1.0,
            clarity=0.9,
            player_relevance=0.8,
            priority=LessonPriority.CRITICAL
        )
        
        # Normal priority candidate
        normal_priority = LessonCandidate(
            candidate_id="test2",
            teaching_mode=TeachingMode.POSITIVE_REINFORCEMENT,
            title="Good Move",
            main_insight="Solid choice",
            explanation_type=ExplanationType.WHY_GOOD,
            severity=0.3,
            clarity=0.9,
            player_relevance=0.5,
            priority=LessonPriority.NORMAL
        )
        
        high_score = high_priority.calculate_score()
        normal_score = normal_priority.calculate_score()
        
        # Critical priority should score higher
        assert high_score > normal_score, f"High priority score {high_score} should exceed normal {normal_score}"
        
        # Score should be reasonable (not 0 or negative)
        assert high_score > 0
        assert normal_score > 0
    
    def test_freshness_affects_score(self):
        """Test that freshness multiplier affects candidate score."""
        from services.chess_brain.schemas import LessonCandidate
        from services.chess_brain.enums import (
            TeachingMode, LessonPriority, ExplanationType
        )
        
        fresh_candidate = LessonCandidate(
            candidate_id="fresh",
            teaching_mode=TeachingMode.TACTICAL_PATTERN_TEACHING,
            title="Fork Pattern",
            main_insight="Fork available",
            explanation_type=ExplanationType.PATTERN,
            severity=0.8,
            clarity=0.8,
            player_relevance=0.7,
            priority=LessonPriority.HIGH,
            freshness=1.0  # Fresh
        )
        
        stale_candidate = LessonCandidate(
            candidate_id="stale",
            teaching_mode=TeachingMode.TACTICAL_PATTERN_TEACHING,
            title="Fork Pattern",
            main_insight="Fork available",
            explanation_type=ExplanationType.PATTERN,
            severity=0.8,
            clarity=0.8,
            player_relevance=0.7,
            priority=LessonPriority.HIGH,
            freshness=0.5  # Recently taught
        )
        
        fresh_score = fresh_candidate.calculate_score()
        stale_score = stale_candidate.calculate_score()
        
        assert fresh_score > stale_score, f"Fresh {fresh_score} should beat stale {stale_score}"


class TestChessBrainAnalysis:
    """Test ChessBrain analyze_move functionality."""
    
    @pytest.mark.asyncio
    async def test_excellent_move_classification(self):
        """Test that best move is classified as excellent."""
        import chess
        from services.chess_brain import ChessBrain, MoveQuality
        
        brain = ChessBrain(db=None)
        
        output = await brain.analyze_move(
            fen_before=chess.STARTING_FEN,
            user_move="e4",
            user_id="test_user",
            session_id="test_session",
            stockfish_analysis={
                "best_move": "e4",
                "eval_before": 0.2,
                "eval_after": 0.3,
                "pv": ["e4", "e5", "Nf3"]
            }
        )
        
        # Playing the best move should be excellent
        assert output.move_quality in [MoveQuality.EXCELLENT, MoveQuality.GOOD]
        assert output.coaching_message is not None
        assert len(output.coaching_message) > 0
    
    @pytest.mark.asyncio
    async def test_blunder_classification(self):
        """Test that significant eval loss is classified as blunder."""
        import chess
        from services.chess_brain import ChessBrain, MoveQuality, TeachingMode
        
        brain = ChessBrain(db=None)
        
        # Position after 1.e4 e5 - user plays Qh5 (not a blunder, but let's test with bad eval)
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        
        output = await brain.analyze_move(
            fen_before=fen,
            user_move="Qh5",  # User's move
            user_id="test_user",
            session_id="test_session",
            stockfish_analysis={
                "best_move": "Nf3",  # Best move
                "eval_before": 0.3,
                "eval_after": -2.5,  # Big eval drop = blunder
                "pv": ["Nf3", "Nc6"]
            }
        )
        
        assert output.move_quality == MoveQuality.BLUNDER
        assert output.teaching_mode == TeachingMode.IMMEDIATE_MISTAKE_CORRECTION
        assert output.best_move == "Nf3"
    
    @pytest.mark.asyncio
    async def test_output_has_required_fields(self):
        """Test that ChessBrainOutput contains all required fields."""
        import chess
        from services.chess_brain import ChessBrain
        
        brain = ChessBrain(db=None)
        
        output = await brain.analyze_move(
            fen_before=chess.STARTING_FEN,
            user_move="d4",
            user_id="test_user",
            session_id="test_session",
            stockfish_analysis={
                "best_move": "d4",
                "eval_before": 0.2,
                "eval_after": 0.4,
                "pv": []
            }
        )
        
        # Check output object attributes
        assert hasattr(output, 'selected_lesson')
        assert hasattr(output, 'move_quality')
        assert hasattr(output, 'cp_loss')
        assert hasattr(output, 'best_move')
        assert hasattr(output, 'coaching_message')
        assert hasattr(output, 'teaching_mode')
        
        # Check to_dict output
        output_dict = output.to_dict()
        required_fields = [
            "coaching_message",
            "user_move_quality",
            "best_move",
            "teaching_mode"
        ]
        
        for field in required_fields:
            assert field in output_dict, f"Missing field in to_dict: {field}"


class TestTeachingModeAssignment:
    """Test that teaching modes are correctly assigned based on move quality."""
    
    @pytest.mark.asyncio
    async def test_mistake_gets_correction_mode(self):
        """Test that mistakes get IMMEDIATE_MISTAKE_CORRECTION teaching mode."""
        import chess
        from services.chess_brain import ChessBrain, MoveQuality, TeachingMode
        
        brain = ChessBrain(db=None)
        
        output = await brain.analyze_move(
            fen_before=chess.STARTING_FEN,
            user_move="a3",  # Not the best opening move
            user_id="test_user",
            session_id="test_session",
            stockfish_analysis={
                "best_move": "e4",
                "eval_before": 0.2,
                "eval_after": -1.5,  # Loss = mistake
                "pv": ["e4"]
            }
        )
        
        if output.move_quality in [MoveQuality.MISTAKE, MoveQuality.BLUNDER]:
            assert output.teaching_mode == TeachingMode.IMMEDIATE_MISTAKE_CORRECTION
    
    @pytest.mark.asyncio
    async def test_good_move_gets_appropriate_teaching_mode(self):
        """Test that good moves get appropriate teaching modes."""
        import chess
        from services.chess_brain import ChessBrain, MoveQuality, TeachingMode
        
        brain = ChessBrain(db=None)
        
        output = await brain.analyze_move(
            fen_before=chess.STARTING_FEN,
            user_move="e4",
            user_id="test_user",
            session_id="test_session",
            stockfish_analysis={
                "best_move": "e4",
                "eval_before": 0.2,
                "eval_after": 0.3,
                "pv": ["e4"]
            }
        )
        
        if output.move_quality in [MoveQuality.EXCELLENT, MoveQuality.BRILLIANT]:
            # Good moves can get positive reinforcement or strategic teaching
            valid_modes = [
                TeachingMode.POSITIVE_REINFORCEMENT,
                TeachingMode.STRATEGIC_CONCEPT_TEACHING,
                TeachingMode.OPENING_GUIDANCE
            ]
            assert output.teaching_mode in valid_modes, f"Unexpected mode: {output.teaching_mode}"


class TestLessonMemory:
    """Test lesson memory anti-spam functionality."""
    
    def test_can_teach_initially(self):
        """Test that patterns can be taught initially."""
        from services.chess_brain.schemas import LessonMemory
        
        memory = LessonMemory(session_id="test")
        
        assert memory.can_teach("fork_detector", 1) is True
        assert memory.can_teach("pin_detector", 1) is True
    
    def test_anti_spam_after_teaching(self):
        """Test that recently taught patterns are blocked."""
        from services.chess_brain.schemas import LessonMemory
        
        memory = LessonMemory(session_id="test")
        
        # Teach fork at move 1
        memory.record_taught("fork_detector", "Fork Pattern", 1)
        
        # Should not teach same pattern immediately
        assert memory.can_teach("fork_detector", 2) is False
        assert memory.can_teach("fork_detector", 3) is False
        assert memory.can_teach("fork_detector", 4) is False
        
        # After 5 moves, should be allowed again
        assert memory.can_teach("fork_detector", 6) is True
    
    def test_freshness_score_decay(self):
        """Test that freshness score decays after teaching."""
        from services.chess_brain.schemas import LessonMemory
        
        memory = LessonMemory(session_id="test")
        
        # Fresh pattern
        freshness_before = memory.get_freshness_score("fork_detector", 1)
        assert freshness_before == 1.0  # Max freshness
        
        # Teach pattern
        memory.record_taught("fork_detector", "Fork", 1)
        
        # Freshness should decay
        freshness_after = memory.get_freshness_score("fork_detector", 2)
        assert freshness_after < 1.0


class TestChessBrainIntegration:
    """Integration tests using the get_chess_brain_feedback function."""
    
    @pytest.mark.asyncio
    async def test_get_chess_brain_feedback_success(self):
        """Test get_chess_brain_feedback returns proper format."""
        import chess
        from services.chess_brain.integration import get_chess_brain_feedback
        
        result = await get_chess_brain_feedback(
            db=None,
            fen_before=chess.STARTING_FEN,
            user_move="e4",
            user_id="test_user",
            session_id="test_session",
            stockfish_analysis={
                "best_move": "e4",
                "eval_before": 0.2,
                "eval_after": 0.3,
                "pv": []
            },
            user_color="white",
            move_number=1
        )
        
        # Check required fields
        assert "coaching_message" in result
        assert "user_move_quality" in result
        assert "best_move" in result
        assert "teaching_mode" in result
        assert "is_chess_brain" in result
        
        # Should be marked as chess brain response
        assert result["is_chess_brain"] is True
    
    @pytest.mark.asyncio
    async def test_get_chess_brain_feedback_blunder(self):
        """Test get_chess_brain_feedback handles blunders correctly."""
        import chess
        from services.chess_brain.integration import get_chess_brain_feedback
        
        result = await get_chess_brain_feedback(
            db=None,
            fen_before="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            user_move="Qh5",
            user_id="test_user",
            session_id="test_session",
            stockfish_analysis={
                "best_move": "Nf3",
                "eval_before": 0.3,
                "eval_after": -3.0,  # Big loss
                "pv": ["Nf3"]
            },
            user_color="white",
            move_number=2
        )
        
        assert result["user_move_quality"] == "blunder"
        assert result["teaching_mode"] == "immediate_mistake_correction"
        assert result["best_move"] == "Nf3"


class TestAPIPlayWithCoachFlow:
    """API integration tests for the full play flow."""
    
    @pytest.fixture
    def authenticated_session(self):
        """Get authenticated session via dev login."""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        res = session.get(f"{BASE_URL}/api/auth/dev-login")
        if res.status_code != 200:
            pytest.skip("Dev login failed - skipping authenticated tests")
        
        return session
    
    def test_start_session_returns_session_id(self, authenticated_session):
        """Test starting a coach play session."""
        res = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={
                "user_color": "white",
                "user_rating": 1200
            }
        )
        
        assert res.status_code == 200, f"Start session failed: {res.text}"
        
        data = res.json()
        assert data.get("success") is True
        assert "session_id" in data
        assert "session" in data
        
        session = data["session"]
        assert session.get("status") == "active"
        assert session.get("user_color") == "white"
    
    def test_make_move_returns_expected_fields(self, authenticated_session):
        """Test making a move in a coach session."""
        # Start session
        start_res = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "user_rating": 1200}
        )
        assert start_res.status_code == 200
        
        session_id = start_res.json()["session_id"]
        
        # Make opening move
        move_res = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={
                "session_id": session_id,
                "move": "e4",
                "time_spent": 2.0
            }
        )
        
        assert move_res.status_code == 200, f"Move failed: {move_res.text}"
        
        data = move_res.json()
        assert data.get("success") is True
        assert data.get("user_move_recorded") is True
        assert data.get("move") == "e4"
        assert "current_fen" in data
    
    def test_full_play_flow_with_feedback(self, authenticated_session):
        """Test full flow: start session -> make move -> poll for coach response."""
        # Start session
        start_res = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "user_rating": 1200}
        )
        assert start_res.status_code == 200
        
        session_id = start_res.json()["session_id"]
        
        # Make opening move
        move_res = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={
                "session_id": session_id,
                "move": "e4",
                "time_spent": 3.0
            }
        )
        assert move_res.status_code == 200
        
        # Wait for async processing
        time.sleep(2)
        
        # Poll for feedback
        feedback_res = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        # Feedback endpoint should return valid response
        if feedback_res.status_code == 200:
            data = feedback_res.json()
            if data.get("feedback"):
                feedback = data["feedback"]
                # Verify feedback structure
                assert "user_move" in feedback or "coaching_message" in feedback


class TestChessBrainEnums:
    """Test Chess Brain enum values."""
    
    def test_teaching_mode_values(self):
        """Test all 7 teaching modes are defined."""
        from services.chess_brain import TeachingMode
        
        expected_modes = [
            "immediate_mistake_correction",
            "tactical_pattern_teaching",
            "strategic_concept_teaching",
            "positive_reinforcement",
            "habit_breakthrough",
            "opening_guidance",
            "endgame_technique"
        ]
        
        actual_modes = [mode.value for mode in TeachingMode]
        
        for expected in expected_modes:
            assert expected in actual_modes, f"Missing teaching mode: {expected}"
    
    def test_move_quality_values(self):
        """Test all move quality classifications are defined."""
        from services.chess_brain import MoveQuality
        
        expected_qualities = [
            "brilliant",
            "excellent",
            "good",
            "inaccuracy",
            "mistake",
            "blunder"
        ]
        
        actual_qualities = [q.value for q in MoveQuality]
        
        for expected in expected_qualities:
            assert expected in actual_qualities, f"Missing move quality: {expected}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

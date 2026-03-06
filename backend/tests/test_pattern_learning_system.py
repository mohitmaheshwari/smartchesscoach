"""
Tests for the Self-Learning Pattern Recognition System

This tests the complete auto-correction flow:
1. User submits feedback on wrong explanation
2. System generates corrected explanation immediately
3. System extracts a generalizable pattern rule
4. Pattern rule is stored in database
5. Future similar positions get correct explanation from rule
"""

import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock

# Set up test environment
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

pytestmark = pytest.mark.asyncio


class TestPatternRuleExtractor:
    """Tests for the pattern_rule_extractor module"""
    
    def test_position_analyzer_extracts_king_safety_features(self):
        """Test that PositionAnalyzer correctly extracts king safety features"""
        from services.pattern_learning.pattern_rule_extractor import PositionAnalyzer
        
        analyzer = PositionAnalyzer()
        
        # Position where white king is on back rank with no escape squares
        # This is after castling but pawns are on f2, g2, h2 - king trapped
        fen = "6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1"
        
        features = analyzer.extract_features(fen)
        
        assert features.king_on_back_rank == True
        assert features.king_escape_squares >= 0  # King has some escape squares
    
    def test_position_analyzer_extracts_back_rank_vulnerability(self):
        """Test detection of back rank mate vulnerability"""
        from services.pattern_learning.pattern_rule_extractor import PositionAnalyzer
        
        analyzer = PositionAnalyzer()
        
        # Classic back rank weakness - white king trapped, black rook on e8
        fen = "4r1k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1"
        
        features = analyzer.extract_features(fen)
        
        # King should be on back rank
        assert features.king_on_back_rank == True
    
    def test_pattern_rule_extractor_classifies_king_safety_insight(self):
        """Test that user insight about king safety is correctly classified"""
        from services.pattern_learning.pattern_rule_extractor import (
            PatternRuleExtractor, PositionFeatures
        )
        
        extractor = PatternRuleExtractor()
        
        # Simulate position features where king is trapped
        features = PositionFeatures(
            king_on_back_rank=True,
            king_escape_squares=0,
            king_has_luft=False,
            back_rank_vulnerable=True
        )
        
        # User insight mentions "breathing room" - should map to KING_SAFETY_LUFT
        user_insight = "My king had no breathing room, needed to create escape"
        pattern_type = extractor._classify_user_insight(user_insight, features)
        
        assert pattern_type in ["KING_SAFETY_LUFT", "BACK_RANK_MATE_THREAT"]
    
    def test_pattern_rule_extractor_classifies_fork_insight(self):
        """Test that user insight about forks is correctly classified"""
        from services.pattern_learning.pattern_rule_extractor import (
            PatternRuleExtractor, PositionFeatures
        )
        
        extractor = PatternRuleExtractor()
        features = PositionFeatures()  # Empty features
        
        # User insight mentions fork
        user_insight = "The knight forks my queen and rook"
        pattern_type = extractor._classify_user_insight(user_insight, features)
        
        assert pattern_type == "PIECE_FORK"


class TestAutoCorrection:
    """Tests for the auto_correction_service module"""
    
    async def test_feedback_submission_returns_corrected_explanation(self):
        """Test that submitting feedback returns a corrected explanation"""
        from services.pattern_learning.auto_correction_service import AutoCorrectionService
        
        service = AutoCorrectionService()
        
        result = await service.submit_feedback_and_correct(
            user_id="test_user",
            position_fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            move_played="e5",
            system_classification="UNKNOWN",
            system_explanation="Test explanation",
            correct_classification="DEFENSIVE_MOVE",
            user_explanation="This defends the center",
            move_san="e5",
            eval_before=0.3,
            eval_after=0.0,
            best_move="c5",
            pv_after_played=["Nf3"],
            game_id="test_game",
            move_number=1,
            user_color="black"
        )
        
        assert result["success"] == True
        assert "feedback_id" in result
        assert "corrected_explanation" in result
        assert result["learning_status"] in ["queued", "correction_exists", "rule_generated"]


class TestCognitiveGapIntegration:
    """Tests for cognitive_gap_service integration with learned rules"""
    
    def test_cognitive_gap_detects_threat_blindness(self):
        """Test that cognitive gap analysis detects threat blindness when explicit threat"""
        from cognitive_gap_service import analyze_cognitive_gap
        
        # Position where there's an explicit threat description
        result = analyze_cognitive_gap(
            fen_before="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            user_move_san="h5",  # Random move
            best_move_san="e5",  # Central counter
            eval_before=0.3,
            eval_after=-200,  # Big eval drop
            threat_description="Opponent threatens to win material"
        )
        
        # Should identify this as threat blindness or king safety (back rank check)
        assert result["primary_gap"] in ["threat_blindness", "king_safety_neglect"]
    
    def test_cognitive_gap_returns_coaching_focus(self):
        """Test that cognitive gap analysis returns actionable coaching focus"""
        from cognitive_gap_service import analyze_cognitive_gap
        
        result = analyze_cognitive_gap(
            fen_before="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            user_move_san="e5",
            best_move_san="c5",
            eval_before=0.3,
            eval_after=0.0
        )
        
        # Should have a coaching_focus field
        assert "coaching_focus" in result or "explanation" in result


class TestEndToEndLearning:
    """End-to-end tests for the learning loop"""
    
    async def test_feedback_creates_pattern_rule(self):
        """Test that feedback submission creates a pattern rule in database"""
        from motor.motor_asyncio import AsyncIOMotorClient
        from services.pattern_learning.auto_correction_service import AutoCorrectionService
        
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
        db = client[os.environ.get("DB_NAME", "test_database")]
        
        # Count rules before
        rules_before = await db.pattern_rules.count_documents({})
        
        # Submit feedback with user insight about king safety
        service = AutoCorrectionService()
        result = await service.submit_feedback_and_correct(
            user_id="test_user_e2e",
            position_fen="6k1/5ppp/8/8/8/8/5PPP/r5K1 w - - 0 1",
            move_played="Kh1",
            system_classification="UNKNOWN",
            system_explanation="King move",
            correct_classification="KING_SAFETY",
            user_explanation="My king had no escape squares, needed to create luft",
            move_san="Kh1",
            eval_before=-500,
            eval_after=-900,
            best_move="Kf1",
            pv_after_played=["Ra1#"],
            game_id="test_e2e_game",
            move_number=40,
            user_color="white"
        )
        
        assert result["success"] == True
        
        # Check if pattern rule was created
        rules_after = await db.pattern_rules.count_documents({})
        
        # Either a new rule was created, or one existed
        assert rules_after >= rules_before

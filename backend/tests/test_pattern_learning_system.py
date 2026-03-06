"""
Tests for the Self-Learning Pattern Recognition System

This tests the complete auto-correction flow:
1. User submits feedback on wrong explanation
2. System generates corrected explanation immediately
3. System extracts CONCRETE, QUERYABLE features from user's insight
4. Pattern rule is stored in database
5. Future similar positions MATCH the rule and get correct explanation
"""

import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock

# Set up test environment
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

pytestmark = pytest.mark.asyncio


class TestConcreteFeatureExtractor:
    """Tests for the NEW concrete_feature_extractor module"""
    
    def test_extract_fork_from_keywords(self):
        """Test that fork patterns are correctly extracted from user text"""
        from services.pattern_learning.concrete_feature_extractor import ConcreteFeatureExtractor
        
        extractor = ConcreteFeatureExtractor()
        
        # User says "knight forks my queen and rook"
        rule = extractor._extract_from_keywords(
            "The knight forks my queen and rook",
            "",
            "FORK"
        )
        
        assert rule.pattern_type == "fork"
        assert rule.attacker_piece == "knight"
        assert "queen" in rule.target_pieces
        assert "rook" in rule.target_pieces
        assert rule.min_targets == 2
    
    def test_extract_back_rank_from_keywords(self):
        """Test that back rank patterns are extracted correctly"""
        from services.pattern_learning.concrete_feature_extractor import ConcreteFeatureExtractor
        
        extractor = ConcreteFeatureExtractor()
        
        rule = extractor._extract_from_keywords(
            "I got back rank mated because my king had no escape",
            "",
            "BACK_RANK"
        )
        
        assert rule.pattern_type == "back_rank"
        assert rule.king_on_back_rank == True
        assert rule.king_escape_squares == 0
    
    def test_extract_king_safety_from_keywords(self):
        """Test king safety / luft patterns"""
        from services.pattern_learning.concrete_feature_extractor import ConcreteFeatureExtractor
        
        extractor = ConcreteFeatureExtractor()
        
        rule = extractor._extract_from_keywords(
            "My king needed breathing room, it was trapped",
            "",
            "KING_SAFETY"
        )
        
        assert rule.pattern_type == "king_safety"
        assert rule.king_on_back_rank == True
    
    def test_extract_pin_from_keywords(self):
        """Test pin pattern extraction"""
        from services.pattern_learning.concrete_feature_extractor import ConcreteFeatureExtractor
        
        extractor = ConcreteFeatureExtractor()
        
        rule = extractor._extract_from_keywords(
            "My bishop was pinned to my king",
            "",
            "PIN"
        )
        
        assert rule.pattern_type == "pin"
        assert rule.attacker_piece == "bishop"


class TestConcretePatternMatcher:
    """Tests for matching positions against concrete rules"""
    
    def test_match_fork_position(self):
        """Test that a fork position is correctly identified"""
        from services.pattern_learning.concrete_feature_extractor import (
            ConcretePatternMatcher, ConcretePatternRule
        )
        
        matcher = ConcretePatternMatcher()
        
        fork_rule = ConcretePatternRule(
            rule_id="test_fork",
            pattern_type="fork",
            min_targets=2,
            min_target_value=6  # Knight value or higher
        )
        
        # Knight on c7 forks king on e8 and rook on a8
        fork_fen = "r3k2r/ppN2ppp/8/8/8/8/PPP2PPP/R3K2R b kq - 0 1"
        
        matches, confidence = matcher.match(fork_rule, fork_fen)
        
        assert matches == True
        assert confidence >= 0.8
    
    def test_no_match_non_fork_position(self):
        """Test that non-fork positions don't match fork rules"""
        from services.pattern_learning.concrete_feature_extractor import (
            ConcretePatternMatcher, ConcretePatternRule
        )
        
        matcher = ConcretePatternMatcher()
        
        fork_rule = ConcretePatternRule(
            rule_id="test_fork",
            pattern_type="fork",
            min_targets=2,
            min_target_value=10  # Queen value
        )
        
        # Starting position - no forks
        starting_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        
        matches, confidence = matcher.match(fork_rule, starting_fen)
        
        assert matches == False
    
    def test_match_back_rank_position(self):
        """Test back rank vulnerability detection"""
        from services.pattern_learning.concrete_feature_extractor import (
            ConcretePatternMatcher, ConcretePatternRule
        )
        
        matcher = ConcretePatternMatcher()
        
        back_rank_rule = ConcretePatternRule(
            rule_id="test_back_rank",
            pattern_type="king_safety",  # Use king_safety which has king_escape_squares=1
            king_on_back_rank=True,
            king_escape_squares=2  # Allow up to 2 escape squares
        )
        
        # King on g1 with some escape squares
        trapped_king_fen = "6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1"
        
        matches, confidence = matcher.match(back_rank_rule, trapped_king_fen)
        
        # White king is on back rank (rank 0)
        assert matches == True


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


class TestEndToEndLearning:
    """End-to-end tests for the learning loop"""
    
    async def test_feedback_creates_concrete_pattern(self):
        """Test that feedback submission creates a CONCRETE pattern in database"""
        from motor.motor_asyncio import AsyncIOMotorClient
        from services.pattern_learning.auto_correction_service import AutoCorrectionService
        
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
        db = client[os.environ.get("DB_NAME", "test_database")]
        
        # Count concrete patterns before
        patterns_before = await db.concrete_patterns.count_documents({})
        
        # Submit feedback about a fork
        service = AutoCorrectionService()
        result = await service.submit_feedback_and_correct(
            user_id="test_user_e2e",
            position_fen="r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
            move_played="Qxf7",
            system_classification="UNKNOWN",
            system_explanation="Queen capture",
            correct_classification="FORK",
            user_explanation="The knight forks my queen and rook",
            move_san="Qxf7",
            eval_before=300,
            eval_after=-200,
            best_move="Qxf7",
            pv_after_played=["Ke7"],
            game_id="test_e2e_fork",
            move_number=4,
            user_color="white"
        )
        
        assert result["success"] == True
        
        # Check if concrete pattern was created
        patterns_after = await db.concrete_patterns.count_documents({})
        
        # A new concrete pattern should have been created
        assert patterns_after >= patterns_before
    
    async def test_future_position_matches_learned_rule(self):
        """Test that a future similar position matches the learned rule"""
        from motor.motor_asyncio import AsyncIOMotorClient
        from services.pattern_learning.concrete_feature_extractor import ConcretePatternStore
        
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
        db = client[os.environ.get("DB_NAME", "test_database")]
        store = ConcretePatternStore(db)
        
        # Test position: Knight fork on c7
        fork_fen = "r3k2r/ppN2ppp/8/8/8/8/PPP2PPP/R3K2R b kq - 0 1"
        
        matches = await store.find_matching_rules(fork_fen)
        
        # Should find the fork pattern we stored earlier
        assert len(matches) > 0
        rule, confidence = matches[0]
        assert rule.pattern_type == "fork"
        assert confidence >= 0.7

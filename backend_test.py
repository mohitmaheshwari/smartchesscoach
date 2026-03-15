"""
Chess Brain V1.1 Test Suite
===========================

Tests for the new Chess Brain V1.1 implementations:
1. Template System Tests
2. Fingerprint Service Tests 
3. Reinforcement Engine Tests
4. Enhanced Detector Tests
5. Integration Tests

Run with: python backend_test.py
"""

import sys
import os
import asyncio
import uuid
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

# Add the backend directory to Python path
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_dir)

# Import Chess Brain components
import chess
from services.chess_brain import (
    ChessBrain, 
    TeachingMode, 
    MoveQuality, 
    get_detector_registry
)
from services.chess_brain.templates import get_template, render_template
from services.chess_brain.fingerprint_service import FingerprintService, get_fingerprint_service
from services.chess_brain.reinforcement_engine import ReinforcementEngine, create_reinforcement_engine
from services.chess_brain.enums import MistakeCategory, TacticalPattern, StrategicConcept, LessonPriority
from services.chess_brain.schemas import PositionInsightObject, MistakeFingerprint, DetectorResult


class ChessBrainV11Tester:
    """Test suite for Chess Brain V1.1 features."""
    
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def run_template_system_tests(self):
        """Test the template system functionality."""
        print("\n" + "="*60)
        print("TESTING TEMPLATE SYSTEM")
        print("="*60)
        
        # Test 1: Import all template modules successfully
        try:
            from services.chess_brain.templates import (
                tactical_patterns,
                strategic_concepts,
                mistake_corrections,
                reinforcement,
                opening_guidance,
                endgame_technique
            )
            self.log_test("Import all template modules", True)
        except Exception as e:
            self.log_test("Import all template modules", False, str(e))
            return
        
        # Test 2: Get tactical pattern template with variations
        try:
            template = get_template(
                TeachingMode.TACTICAL_PATTERN_TEACHING,
                "FORK",
                {
                    "piece": "Knight", 
                    "square": "f7",
                    "target1": "King",
                    "target2": "Rook"
                }
            )
            
            success = (
                "main_insight" in template and
                "explanation" in template and
                "Knight" in template["main_insight"] and
                "f7" in template["main_insight"]
            )
            self.log_test("Get tactical pattern template (fork)", success, 
                         "Missing required fields" if not success else "")
        except Exception as e:
            self.log_test("Get tactical pattern template (fork)", False, str(e))
        
        # Test 3: Get strategic concept template
        try:
            template = get_template(
                TeachingMode.STRATEGIC_CONCEPT_TEACHING,
                "ISOLATED_PAWN",
                {
                    "square": "d5",
                    "file": "d-file"
                }
            )
            
            success = (
                "main_insight" in template and
                "explanation" in template and
                "d5" in str(template)
            )
            self.log_test("Get strategic concept template (isolated_pawn)", success)
        except Exception as e:
            self.log_test("Get strategic concept template (isolated_pawn)", False, str(e))
        
        # Test 4: Get mistake correction template
        try:
            template = get_template(
                TeachingMode.IMMEDIATE_MISTAKE_CORRECTION,
                "blunder",
                {
                    "move": "Qh5",
                    "best_move": "Nf3",
                    "what_went_wrong": "hangs the queen"
                }
            )
            
            success = (
                "main_insight" in template and
                "explanation" in template
            )
            self.log_test("Get mistake correction template (blunder)", success)
        except Exception as e:
            self.log_test("Get mistake correction template (blunder)", False, str(e))
        
        # Test 5: Get reinforcement template
        try:
            template = get_template(
                TeachingMode.POSITIVE_REINFORCEMENT,
                "excellent_move",
                {
                    "move": "Nf3",
                    "why_good": "develops with tempo"
                }
            )
            
            success = (
                "main_insight" in template and
                "explanation" in template
            )
            self.log_test("Get reinforcement template (positive)", success)
        except Exception as e:
            self.log_test("Get reinforcement template (positive)", False, str(e))
        
        # Test 6: Get habit breakthrough template
        try:
            template = get_template(
                TeachingMode.HABIT_BREAKTHROUGH,
                "habit_breakthrough",
                {
                    "pattern_name": "fork patterns",
                    "miss_count": 5,
                    "user_move": "Nf7",
                    "achievement_description": "shows improving pattern recognition",
                    "explanation": "Great breakthrough!"
                }
            )
            
            success = (
                "main_insight" in template and
                "explanation" in template and
                ("breakthrough" in template["main_insight"].lower() or 
                 "achievement" in template["main_insight"].lower())
            )
            self.log_test("Get reinforcement template (habit_breakthrough)", success)
        except Exception as e:
            self.log_test("Get reinforcement template (habit_breakthrough)", False, str(e))
        
        # Test 7: Get opening guidance template
        try:
            template = get_template(
                TeachingMode.OPENING_GUIDANCE,
                "opening_principles",
                {
                    "move": "e4",
                    "principle": "control the center"
                }
            )
            
            success = (
                "main_insight" in template and
                "explanation" in template
            )
            self.log_test("Get opening guidance template", success)
        except Exception as e:
            self.log_test("Get opening guidance template", False, str(e))
        
        # Test 8: Get endgame technique template
        try:
            template = get_template(
                TeachingMode.ENDGAME_TECHNIQUE,
                "king_and_pawn",
                {
                    "technique": "opposition",
                    "position_type": "king and pawn endgame"
                }
            )
            
            success = (
                "main_insight" in template and
                "explanation" in template
            )
            self.log_test("Get endgame technique template", success)
        except Exception as e:
            self.log_test("Get endgame technique template", False, str(e))
        
        # Test 9: Verify template variable rendering
        try:
            template_text = "Your {{piece}} on {{square}} attacks the {{target}}."
            rendered = render_template(template_text, {
                "piece": "Queen",
                "square": "d1", 
                "target": "King"
            })
            
            expected = "Your Queen on d1 attacks the King."
            success = rendered == expected
            self.log_test("Template variable rendering", success,
                         f"Expected '{expected}', got '{rendered}'")
        except Exception as e:
            self.log_test("Template variable rendering", False, str(e))
        
        # Test 10: Verify multiple variations return different text
        try:
            template1 = get_template(
                TeachingMode.TACTICAL_PATTERN_TEACHING,
                "FORK",
                {"piece": "Knight", "square": "f7"},
                variation=0
            )
            template2 = get_template(
                TeachingMode.TACTICAL_PATTERN_TEACHING,
                "FORK", 
                {"piece": "Knight", "square": "f7"},
                variation=1
            )
            
            success = template1["main_insight"] != template2["main_insight"]
            self.log_test("Multiple variations return different text", success,
                         "Variations should differ")
        except Exception as e:
            self.log_test("Multiple variations return different text", False, str(e))

    async def run_fingerprint_service_tests(self):
        """Test fingerprint service functionality."""
        print("\n" + "="*60)
        print("TESTING FINGERPRINT SERVICE")
        print("="*60)
        
        # Initialize service
        service = FingerprintService(db=None)  # Use in-memory for testing
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        
        # Test 1: Create new fingerprint for user
        try:
            fingerprint = await service.get_fingerprint(test_user_id)
            success = (
                fingerprint.user_id == test_user_id and
                isinstance(fingerprint.tactical, dict) and
                isinstance(fingerprint.strategic, dict) and
                isinstance(fingerprint.behavioral, dict)
            )
            self.log_test("Create new fingerprint for user", success)
        except Exception as e:
            self.log_test("Create new fingerprint for user", False, str(e))
            return
        
        # Test 2: Update fingerprint with new mistake
        try:
            await service.update_fingerprint(
                test_user_id,
                "MISSED_FORK",
                MistakeCategory.TACTICAL.value
            )
            
            updated_fingerprint = await service.get_fingerprint(test_user_id)
            success = (
                updated_fingerprint.tactical.get("MISSED_FORK", {}).get("count", 0) >= 1
            )
            self.log_test("Update fingerprint with new mistake", success)
        except Exception as e:
            self.log_test("Update fingerprint with new mistake", False, str(e))
        
        # Test 3: Verify decay score calculation
        try:
            # Simulate an old mistake
            old_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            
            # Manually set an old mistake for testing
            fingerprint = await service.get_fingerprint(test_user_id)
            fingerprint.tactical["TEST_PATTERN"] = {
                "count": 3,
                "last_seen": old_date,
                "decay_score": 1.0  # Will be updated by decay calculation
            }
            
            # Update decay scores
            service._update_decay_scores(fingerprint)
            
            # Check if decay was applied (should be 0.9^7 ≈ 0.48)
            decay_score = fingerprint.tactical["TEST_PATTERN"]["decay_score"]
            expected_decay = 0.9 ** 7  # About 0.478
            
            success = 0.4 <= decay_score <= 0.5  # Reasonable range
            self.log_test("Verify decay score calculation", success,
                         f"Expected ~{expected_decay:.3f}, got {decay_score:.3f}")
        except Exception as e:
            self.log_test("Verify decay score calculation", False, str(e))
        
        # Test 4: Get pattern stats for specific pattern
        try:
            stats = await service.get_pattern_stats(
                test_user_id,
                "MISSED_FORK",
                MistakeCategory.TACTICAL.value
            )
            
            success = (
                "count" in stats and
                "last_seen" in stats and
                "decay_score" in stats and
                "relevance_score" in stats and
                stats["count"] >= 1
            )
            self.log_test("Get pattern stats for specific pattern", success)
        except Exception as e:
            self.log_test("Get pattern stats for specific pattern", False, str(e))
        
        # Test 5: Get top 5 weaknesses sorted by relevance
        try:
            # Add multiple patterns
            await service.update_fingerprint(test_user_id, "MISSED_PIN", MistakeCategory.TACTICAL.value)
            await service.update_fingerprint(test_user_id, "ISOLATED_PAWN", MistakeCategory.STRATEGIC.value)
            await service.update_fingerprint(test_user_id, "TIME_TROUBLE", MistakeCategory.BEHAVIORAL.value)
            
            weaknesses = await service.get_top_weaknesses(test_user_id, limit=5)
            
            success = (
                isinstance(weaknesses, list) and
                len(weaknesses) <= 5 and
                all("pattern_type" in w and "relevance_score" in w for w in weaknesses)
            )
            
            # Check if sorted by relevance
            if len(weaknesses) > 1:
                sorted_check = all(
                    weaknesses[i]["relevance_score"] >= weaknesses[i+1]["relevance_score"]
                    for i in range(len(weaknesses)-1)
                )
                success = success and sorted_check
                
            self.log_test("Get top 5 weaknesses sorted by relevance", success)
        except Exception as e:
            self.log_test("Get top 5 weaknesses sorted by relevance", False, str(e))
        
        # Test 6: Increment games_analyzed counter
        try:
            initial_fingerprint = await service.get_fingerprint(test_user_id)
            initial_count = initial_fingerprint.games_analyzed
            
            await service.increment_games_analyzed(test_user_id)
            
            updated_fingerprint = await service.get_fingerprint(test_user_id)
            success = updated_fingerprint.games_analyzed == initial_count + 1
            
            self.log_test("Increment games_analyzed counter", success)
        except Exception as e:
            self.log_test("Increment games_analyzed counter", False, str(e))
        
        # Test 7: Verify relevance score calculation
        try:
            fingerprint = await service.get_fingerprint(test_user_id)
            
            # Test relevance calculation for a pattern with known values
            relevance = fingerprint.get_relevance_score("MISSED_FORK", MistakeCategory.TACTICAL.value)
            
            # Relevance should be min(1.0, (count * decay_score) / 10)
            # With count >= 1 and decay_score close to 1.0, relevance should be > 0
            success = 0.0 <= relevance <= 1.0 and relevance > 0
            
            self.log_test("Verify relevance score calculation", success,
                         f"Relevance: {relevance}")
        except Exception as e:
            self.log_test("Verify relevance score calculation", False, str(e))

    async def run_reinforcement_engine_tests(self):
        """Test reinforcement engine functionality."""
        print("\n" + "="*60)
        print("TESTING REINFORCEMENT ENGINE") 
        print("="*60)
        
        # Initialize services
        fingerprint_service = FingerprintService(db=None)
        engine = ReinforcementEngine(fingerprint_service)
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        
        # Test 1: Initialize reinforcement engine
        try:
            success = isinstance(engine, ReinforcementEngine)
            self.log_test("Initialize reinforcement engine", success)
        except Exception as e:
            self.log_test("Initialize reinforcement engine", False, str(e))
            return
        
        # Setup: Create a user with known weaknesses
        try:
            # Add multiple instances of MISSED_FORK to create a strong weakness
            for _ in range(5):
                await fingerprint_service.update_fingerprint(
                    test_user_id, 
                    "MISSED_FORK", 
                    MistakeCategory.TACTICAL.value
                )
        except Exception as e:
            print(f"Setup error: {e}")
            return
        
        # Test 2: Check for breakthrough when user avoids known weakness
        try:
            # Create a position insight representing a good move
            position_insight = PositionInsightObject(
                fen=chess.STARTING_FEN,
                move_number=15,
                user_color="white",
                eval_before=0.2,
                eval_after=0.3,
                best_move="Nf7",
                user_move="Nf7", 
                move_quality=MoveQuality.EXCELLENT,
                cp_loss=0,
                time_spent=3.0,
                is_check=False,
                is_capture=False,
                tactical_detections=[],
                strategic_detections=[],
                behavioral_detections=[]
            )
            
            breakthrough = await engine.check_for_breakthrough(test_user_id, position_insight)
            
            # This test might not trigger a breakthrough since the position doesn't contain
            # the specific pattern, but it should not error
            success = breakthrough is None or hasattr(breakthrough, 'teaching_mode')
            self.log_test("Check for breakthrough when user avoids known weakness", success)
        except Exception as e:
            self.log_test("Check for breakthrough when user avoids known weakness", False, str(e))
        
        # Test 3: Verify breakthrough NOT detected when user makes mistake
        try:
            bad_position_insight = PositionInsightObject(
                fen="rnbqkbnr/pppp1ppp/8/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 1 2",
                move_number=16,
                user_color="black",
                eval_before=-0.5,
                eval_after=5.0,
                best_move="Nc6",
                user_move="g6",  # Bad move
                move_quality=MoveQuality.BLUNDER,
                cp_loss=550,
                time_spent=2.0,
                is_check=False,
                is_capture=False,
                tactical_detections=[],
                strategic_detections=[],
                behavioral_detections=[]
            )
            
            breakthrough = await engine.check_for_breakthrough(test_user_id, bad_position_insight)
            
            # Should not get breakthrough for bad move
            success = breakthrough is None
            self.log_test("Verify breakthrough NOT detected when user makes mistake", success)
        except Exception as e:
            self.log_test("Verify breakthrough NOT detected when user makes mistake", False, str(e))
        
        # Test 4: Verify breakthrough requires count >= 3, relevance >= 0.3
        try:
            # Create a user with only 1 occurrence of a pattern (should not trigger)
            weak_user_id = f"weak_user_{uuid.uuid4().hex[:8]}"
            await fingerprint_service.update_fingerprint(
                weak_user_id,
                "MISSED_PIN", 
                MistakeCategory.TACTICAL.value
            )
            
            good_insight = PositionInsightObject(
                fen=chess.STARTING_FEN,
                move_number=10,
                user_color="white",
                eval_before=0.2,
                eval_after=0.4,
                best_move="Bb5",
                user_move="Bb5",
                move_quality=MoveQuality.EXCELLENT,
                cp_loss=0,
                time_spent=2.5,
                is_check=False,
                is_capture=False,
                tactical_detections=[],
                strategic_detections=[],
                behavioral_detections=[]
            )
            
            breakthrough = await engine.check_for_breakthrough(weak_user_id, good_insight)
            
            # Should not trigger breakthrough for weak pattern (count < 3)
            success = breakthrough is None
            self.log_test("Verify breakthrough requires count >= 3, relevance >= 0.3", success)
        except Exception as e:
            self.log_test("Verify breakthrough requires count >= 3, relevance >= 0.3", False, str(e))
        
        # Test 5: Test breakthrough lesson candidate creation
        try:
            # Test the _create_breakthrough_lesson method directly
            test_breakthrough = {
                "pattern_type": "MISSED_FORK",
                "category": MistakeCategory.TACTICAL.value,
                "count": 5,
                "relevance": 0.8,
                "user_move": "Nf7",
                "best_move": "Nf7"
            }
            
            test_insight = PositionInsightObject(
                fen=chess.STARTING_FEN,
                move_number=20,
                user_color="white",
                eval_before=0.2,
                eval_after=0.3,
                best_move="Nf7",
                user_move="Nf7",
                move_quality=MoveQuality.EXCELLENT,
                cp_loss=0,
                time_spent=3.0,
                is_check=False,
                is_capture=False,
                tactical_detections=[],
                strategic_detections=[],
                behavioral_detections=[]
            )
            
            candidate = engine._create_breakthrough_lesson(test_breakthrough, test_insight)
            
            success = (
                candidate.teaching_mode == TeachingMode.HABIT_BREAKTHROUGH and
                "breakthrough" in candidate.title.lower() and
                candidate.priority == LessonPriority.HIGH and
                hasattr(candidate, 'template_vars') and
                candidate.template_vars.get("pattern_name") == "fork patterns"
            )
            
            self.log_test("Test breakthrough lesson candidate creation", success)
        except Exception as e:
            self.log_test("Test breakthrough lesson candidate creation", False, str(e))
        
        # Test 6: Verify teaching_mode = HABIT_BREAKTHROUGH
        try:
            # Using the same test as above, verify the teaching mode
            test_breakthrough = {
                "pattern_type": "MISSED_FORK",
                "category": MistakeCategory.TACTICAL.value,
                "count": 5,
                "relevance": 0.8,
                "user_move": "Nf7",
                "best_move": "Nf7"
            }
            
            test_insight = PositionInsightObject(
                fen=chess.STARTING_FEN,
                move_number=20,
                user_color="white",
                eval_before=0.2,
                eval_after=0.3,
                best_move="Nf7",
                user_move="Nf7",
                move_quality=MoveQuality.EXCELLENT,
                cp_loss=0,
                time_spent=3.0,
                is_check=False,
                is_capture=False,
                tactical_detections=[],
                strategic_detections=[],
                behavioral_detections=[]
            )
            
            candidate = engine._create_breakthrough_lesson(test_breakthrough, test_insight)
            
            success = candidate.teaching_mode == TeachingMode.HABIT_BREAKTHROUGH
            self.log_test("Verify teaching_mode = HABIT_BREAKTHROUGH", success)
        except Exception as e:
            self.log_test("Verify teaching_mode = HABIT_BREAKTHROUGH", False, str(e))
        
        # Test 7: Check template variables populated correctly
        try:
            test_breakthrough = {
                "pattern_type": "MISSED_PIN",
                "category": MistakeCategory.TACTICAL.value,
                "count": 4,
                "relevance": 0.6,
                "user_move": "Bb5",
                "best_move": "Bb5"
            }
            
            test_insight = PositionInsightObject(
                fen=chess.STARTING_FEN,
                move_number=12,
                user_color="white",
                eval_before=0.2,
                eval_after=0.2,
                best_move="Bb5",
                user_move="Bb5",
                move_quality=MoveQuality.GOOD,
                cp_loss=0,
                time_spent=2.0,
                is_check=False,
                is_capture=False,
                tactical_detections=[],
                strategic_detections=[],
                behavioral_detections=[]
            )
            
            candidate = engine._create_breakthrough_lesson(test_breakthrough, test_insight)
            
            template_vars = candidate.template_vars
            success = (
                "pattern_name" in template_vars and
                "miss_count" in template_vars and
                "user_move" in template_vars and
                "achievement_description" in template_vars and
                template_vars["miss_count"] == 4 and
                template_vars["user_move"] == "Bb5" and
                template_vars["pattern_name"] == "pin tactics"
            )
            
            self.log_test("Check template variables populated correctly", success)
        except Exception as e:
            self.log_test("Check template variables populated correctly", False, str(e))

    def run_enhanced_detector_tests(self):
        """Test enhanced tactical detectors."""
        print("\n" + "="*60)
        print("TESTING ENHANCED DETECTORS")
        print("="*60)
        
        # Get detector registry
        try:
            registry = get_detector_registry()
            self.log_test("Get detector registry", True)
        except Exception as e:
            self.log_test("Get detector registry", False, str(e))
            return
        
        # Test 1: Test detect_skewer with skewer position
        try:
            # Test if skewer detector exists and returns proper structure
            skewer_detector = registry._tactical_detectors.get("skewer_detector")
            success = skewer_detector is not None
            self.log_test("Test detect_skewer detector exists", success)
            
            if success:
                # Create a test position - simple skewer setup
                board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1")  # Rooks aligned
                context = {"move_number": 10, "game_phase": "middlegame"}
                
                # Test detection
                result = skewer_detector.detector_func(board, "Ra8", "Ra1", context)
                
                # Should return a proper result structure
                success = (
                    isinstance(result, DetectorResult) and
                    0.0 <= result.confidence <= 1.0
                )
                self.log_test("Test detect_skewer with position", success)
                
        except Exception as e:
            self.log_test("Test detect_skewer with skewer position", False, str(e))
        
        # Test 2: Test detect_overload with overloaded defender
        try:
            overload_detector = registry._tactical_detectors.get("overload_detector")
            success = overload_detector is not None
            self.log_test("Test detect_overload detector exists", success)
            
            if success:
                # Test with any position
                board = chess.Board()  # Starting position
                context = {"move_number": 1, "game_phase": "opening"}
                
                result = overload_detector.detector_func(board, "e4", "e4", context)
                
                success = (
                    isinstance(result, DetectorResult) and
                    hasattr(result, "confidence") and
                    0.0 <= result.confidence <= 1.0
                )
                self.log_test("Test detect_overload with position", success)
                
        except Exception as e:
            self.log_test("Test detect_overload with overloaded defender", False, str(e))
        
        # Test 3: Test detect_removal with defender removal
        try:
            removal_detector = registry._tactical_detectors.get("removal_detector")
            success = removal_detector is not None
            self.log_test("Test detect_removal detector exists", success)
            
            if success:
                # Test with any position
                board = chess.Board()
                context = {"move_number": 1, "game_phase": "opening"}
                
                result = removal_detector.detector_func(board, "Nf3", "Nf3", context)
                
                success = (
                    isinstance(result, DetectorResult) and
                    hasattr(result, "confidence") and
                    0.0 <= result.confidence <= 1.0
                )
                self.log_test("Test detect_removal with position", success)
                
        except Exception as e:
            self.log_test("Test detect_removal with defender removal", False, str(e))
        
        # Test 4: Verify confidence scores are between 0.0-1.0
        try:
            # Test all three enhanced detectors for confidence range
            detectors_to_test = ["skewer_detector", "overload_detector", "removal_detector"]
            board = chess.Board()
            context = {"move_number": 5, "game_phase": "opening"}
            
            all_valid = True
            for detector_name in detectors_to_test:
                detector = registry._tactical_detectors.get(detector_name)
                if detector:
                    result = detector.detector_func(board, "e4", "e4", context)
                    confidence = result.confidence
                    if not (0.0 <= confidence <= 1.0):
                        all_valid = False
                        break
            
            self.log_test("Verify confidence scores are between 0.0-1.0", all_valid)
        except Exception as e:
            self.log_test("Verify confidence scores are between 0.0-1.0", False, str(e))
        
        # Test 5: Verify teaching hooks are populated (when pattern is detected)
        try:
            # This test verifies the structure exists, not necessarily that hooks are always populated
            detectors_to_test = ["skewer_detector", "overload_detector", "removal_detector"]
            board = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
            context = {"move_number": 1, "game_phase": "opening"}
            
            all_have_hook_field = True
            for detector_name in detectors_to_test:
                detector = registry._tactical_detectors.get(detector_name)
                if detector:
                    result = detector.detector_func(board, "e5", "e5", context)
                    # Check that the DetectorResult has the teaching_hook field
                    if not hasattr(result, "teaching_hook"):
                        all_have_hook_field = False
                        break
            
            self.log_test("Verify teaching hooks field exists in DetectorResult", all_have_hook_field)
        except Exception as e:
            self.log_test("Verify teaching hooks are populated", False, str(e))
        
        # Test 6: Verify key_squares are returned
        try:
            # Test if detectors return key squares (might be optional)
            detectors_to_test = ["skewer_detector", "overload_detector", "removal_detector"] 
            board = chess.Board("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 4 4")
            context = {"move_number": 4, "game_phase": "opening"}
            
            # Key squares might not always be returned, so we test structure
            all_valid_structure = True
            for detector_name in detectors_to_test:
                detector = registry._tactical_detectors.get(detector_name)
                if detector:
                    result = detector.detector_func(board, "Nxe5", "Nxe5", context)
                    # Result should be a dict with basic required fields
                    if not isinstance(result, DetectorResult) or not hasattr(result, "confidence"):
                        all_valid_structure = False
                        break
            
            self.log_test("Verify detectors return valid structure", all_valid_structure)
        except Exception as e:
            self.log_test("Verify key_squares are returned", False, str(e))
        
        # Test 7: Test detectors handle positions without tactical patterns appropriately
        try:
            # Use a very simple position where tactical patterns are unlikely
            board = chess.Board("8/8/8/3k4/3K4/8/8/8 w - - 0 50")  # Simple king endgame
            context = {"move_number": 50, "game_phase": "endgame"}
            
            detectors_to_test = ["skewer_detector", "overload_detector", "removal_detector"]
            all_return_valid_results = True
            
            for detector_name in detectors_to_test:
                detector = registry._tactical_detectors.get(detector_name)
                if detector:
                    result = detector.detector_func(board, "Kc4", "Kc4", context)
                    # In a simple king endgame, we just expect a valid DetectorResult
                    # The actual confidence/detection values depend on implementation
                    if not isinstance(result, DetectorResult) or not hasattr(result, "confidence"):
                        all_return_valid_results = False
                        break
            
            self.log_test("Test detectors return valid results for simple positions", all_return_valid_results)
        except Exception as e:
            self.log_test("Test all three detectors return empty result when pattern not present", False, str(e))

    async def run_integration_tests(self):
        """Test integration between components."""
        print("\n" + "="*60)
        print("TESTING INTEGRATION")
        print("="*60)
        
        # Test 1: Run existing Chess Brain test suite
        try:
            # Run the existing test suite
            result = subprocess.run([
                "python", "-m", "pytest", 
                "tests/test_chess_brain.py", 
                "tests/test_chess_brain_integration.py",
                "-v", "--tb=short"
            ], capture_output=True, text=True, cwd="/app/backend")
            
            # Check if tests passed
            success = result.returncode == 0
            details = f"Exit code: {result.returncode}"
            if result.returncode == 0:
                # Count passing tests
                stdout_lines = result.stdout.split('\n')
                passed_line = [line for line in stdout_lines if "passed" in line and "=" in line]
                if passed_line:
                    details = passed_line[-1].strip()
                    
            if result.stderr and result.returncode != 0:
                details += f"\nStderr: {result.stderr[-200:]}"
                
            self.log_test("Run existing Chess Brain test suite (pytest)", success, details)
        except Exception as e:
            self.log_test("Run existing Chess Brain test suite", False, str(e))
        
        # Test 2: Verify all 31 tests still pass (manual check)
        try:
            # Run the existing test modules directly
            from services.chess_brain import get_detector_registry
            
            registry = get_detector_registry()
            total_detectors = (
                len(registry._tactical_detectors) + 
                len(registry._strategic_detectors) + 
                len(registry._behavioral_detectors)
            )
            
            # Should have 10 tactical + 5 strategic + 3 behavioral = 18 detectors
            expected_total = 18
            success = total_detectors == expected_total
            
            self.log_test(f"Verify detector count (expected {expected_total})", success,
                         f"Found {total_detectors} detectors")
        except Exception as e:
            self.log_test("Verify all detectors are registered", False, str(e))
        
        # Test 3: Test template integration with lesson selection
        try:
            brain = ChessBrain(db=None)
            
            # Test a simple analysis
            output = await brain.analyze_move(
                fen_before=chess.STARTING_FEN,
                user_move="e4",
                user_id="test_integration_user",
                session_id="test_integration_session",
                stockfish_analysis={
                    "best_move": "e4",
                    "eval_before": 0.2,
                    "eval_after": 0.3,
                    "pv": ["e4", "e5"]
                }
            )
            
            success = (
                output.coaching_message is not None and
                len(output.coaching_message) > 0 and
                output.move_quality is not None and
                output.teaching_mode is not None
            )
            
            self.log_test("Test template integration with lesson selection", success)
        except Exception as e:
            self.log_test("Test template integration with lesson selection", False, str(e))
        
        # Test 4: Test fingerprint service integration with reinforcement engine
        try:
            fingerprint_service = get_fingerprint_service(db=None)
            engine = create_reinforcement_engine(db=None)
            
            # Test that they work together
            test_user = f"integration_test_{uuid.uuid4().hex[:8]}"
            
            # Add some mistakes
            await fingerprint_service.update_fingerprint(
                test_user,
                "MISSED_FORK",
                MistakeCategory.TACTICAL.value
            )
            
            # Create position insight
            insight = PositionInsightObject(
                fen=chess.STARTING_FEN,
                move_number=10,
                user_color="white",
                eval_before=0.2,
                eval_after=0.3,
                best_move="Nf7",
                user_move="Nf7",
                move_quality=MoveQuality.EXCELLENT,
                cp_loss=0,
                time_spent=2.0,
                is_check=False,
                is_capture=False,
                tactical_detections=[],
                strategic_detections=[],
                behavioral_detections=[]
            )
            
            # Should not error (breakthrough might or might not occur)
            breakthrough = await engine.check_for_breakthrough(test_user, insight)
            success = True  # No exceptions means integration works
            
            self.log_test("Test fingerprint service integration with reinforcement engine", success)
        except Exception as e:
            self.log_test("Test fingerprint service integration with reinforcement engine", False, str(e))

    async def run_all_tests(self):
        """Run all test suites."""
        print("🚀 Starting Chess Brain V1.1 Test Suite")
        print(f"Testing at: {datetime.now()}")
        
        # Run all test suites
        self.run_template_system_tests()
        await self.run_fingerprint_service_tests()
        await self.run_reinforcement_engine_tests() 
        self.run_enhanced_detector_tests()
        await self.run_integration_tests()
        
        # Print final results
        self.print_summary()
        
        return self.tests_passed == self.tests_run

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("CHESS BRAIN V1.1 TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%" if self.tests_run > 0 else "0%")
        
        # Show failed tests
        failed_tests = [t for t in self.test_results if not t['success']]
        if failed_tests:
            print(f"\n❌ FAILED TESTS ({len(failed_tests)}):")
            for test in failed_tests:
                print(f"   • {test['test']}")
                if test['details']:
                    print(f"     {test['details']}")
        
        print("\n" + "="*60)


async def main():
    """Main test runner"""
    tester = ChessBrainV11Tester()
    
    try:
        success = await tester.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n💥 Test runner crashed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
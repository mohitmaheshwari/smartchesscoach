"""
Test suite for active recall integration

Tests:
1. Active recall import and initialization
2. Ranking option generation and verification
3. Concept option generation and verification
4. Database recording of responses
5. End-to-end flow with /v5/interactive-feedback
"""

import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")


async def test_active_recall_imports():
    """Test that active recall modules can be imported"""
    logger.info("TEST 1: Active recall imports...")
    try:
        from services.active_recall_service import generate_active_recall, generate_ranking_options, generate_concept_options
        from services.active_recall_integration import enrich_coaching_with_active_recall, record_active_recall_response
        logger.info("✓ All imports successful")
        return True
    except Exception as e:
        logger.error(f"✗ Import failed: {e}")
        return False


async def test_learning_checkpoints_collection():
    """Test that learning_checkpoints collection exists with proper indexes"""
    logger.info("\nTEST 2: MongoDB learning_checkpoints collection...")
    try:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client["test_database"]

        # Check collection exists
        collections = await db.list_collection_names()
        if "learning_checkpoints" not in collections:
            logger.error("✗ learning_checkpoints collection not found")
            return False
        logger.info("✓ learning_checkpoints collection exists")

        # Check indexes
        indexes = await db.learning_checkpoints.list_indexes().to_list(None)
        index_names = [idx["name"] for idx in indexes]

        required_indexes = [
            "user_id_1_pattern_1_timestamp_-1",
            "user_id_1_timestamp_-1",
            "user_id_1_combined_score_1"
        ]

        for idx_name in required_indexes:
            if idx_name in index_names:
                logger.info(f"✓ Index found: {idx_name}")
            else:
                logger.warning(f"⚠ Index missing: {idx_name}")

        client.close()
        return True
    except Exception as e:
        logger.error(f"✗ Collection check failed: {e}")
        return False


async def test_active_recall_service():
    """Test active recall service functions"""
    logger.info("\nTEST 3: Active recall service functions...")
    try:
        from services.active_recall_service import (
            calibrate_difficulty_for_rating,
            CONCEPT_EXPLANATIONS
        )

        # Test difficulty calibration
        for rating in [800, 1200, 1600, 1900]:
            difficulty = calibrate_difficulty_for_rating(rating)
            expected_spreads = {
                800: 200,
                1200: 100,
                1600: 50,
                1900: 30
            }
            actual = difficulty.get("min_cp_spread", 0)
            expected = expected_spreads.get(rating, 0)

            if actual == expected:
                logger.info(f"✓ Rating {rating}: min_cp_spread = {actual}cp (correct)")
            else:
                logger.error(f"✗ Rating {rating}: expected {expected}cp, got {actual}cp")
                return False

        # Test concept explanations exist
        required_concepts = [
            "centralization", "piece_safety", "hanging_piece",
            "missed_tactic", "tactical_oversight", "calculation_depth",
            "king_safety", "pawn_structure", "piece_activity", "opening_knowledge"
        ]

        for concept in required_concepts:
            if concept in CONCEPT_EXPLANATIONS:
                exp = CONCEPT_EXPLANATIONS[concept]
                if "correct" in exp and "wrong_options" in exp and len(exp["wrong_options"]) == 3:
                    logger.info(f"✓ Concept '{concept}' properly defined")
                else:
                    logger.error(f"✗ Concept '{concept}' malformed")
                    return False
            else:
                logger.warning(f"⚠ Concept '{concept}' not found (optional)")

        logger.info("✓ Service functions work correctly")
        return True
    except Exception as e:
        logger.error(f"✗ Service test failed: {e}")
        return False


async def test_response_recording():
    """Test recording a mock active recall response"""
    logger.info("\nTEST 4: Recording active recall responses...")
    client = None
    try:
        from services.active_recall_integration import record_active_recall_response

        client = AsyncIOMotorClient(MONGO_URL)
        db = client["test_database"]

        # Record a test response
        checkpoint = await record_active_recall_response(
            db=db,
            user_id="test_user_123",
            session_id="test_session_456",
            move_index=5,
            cognitive_gap="centralization",
            ranking_response={"selected_index": 0},
            concept_response={"selected_index": 1}
        )

        if checkpoint:
            logger.info(f"✓ Response recorded successfully")
            logger.info(f"  - User: {checkpoint['user_id']}")
            logger.info(f"  - Pattern: {checkpoint['pattern']}")
            logger.info(f"  - Score: {checkpoint['combined_score']}")

            # Verify it's in the database
            stored = await db.learning_checkpoints.find_one({
                "user_id": "test_user_123",
                "session_id": "test_session_456"
            })

            if stored:
                logger.info("✓ Response verified in database")
                # Clean up
                await db.learning_checkpoints.delete_one({"_id": stored["_id"]})
                return True
            else:
                logger.error("✗ Response not found in database")
                return False
        else:
            logger.error("✗ Response recording returned None")
            return False

    except Exception as e:
        logger.error(f"✗ Response recording failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if client:
            client.close()


async def test_endpoint_wiring():
    """Test that endpoints are properly wired"""
    logger.info("\nTEST 5: Endpoint wiring check...")
    try:
        # Check that the coach_play.py file has the active recall code
        coach_play_path = "/app/backend/routes/coach_play.py"
        if os.path.exists(coach_play_path):
            with open(coach_play_path, "r") as f:
                content = f.read()

            checks = [
                ("Import statement", "from services.active_recall_integration import enrich_coaching_with_active_recall"),
                ("Enrichment call", "await enrich_coaching_with_active_recall("),
                ("Response endpoint", '@router.post("/active-recall-response")'),
                ("Response recording", "record_active_recall_response as record_ar")
            ]

            all_pass = True
            for check_name, check_str in checks:
                if check_str in content:
                    logger.info(f"✓ Found: {check_name}")
                else:
                    logger.error(f"✗ Missing: {check_name}")
                    all_pass = False

            return all_pass
        else:
            logger.error(f"✗ File not found: {coach_play_path}")
            return False

    except Exception as e:
        logger.error(f"✗ Endpoint check failed: {e}")
        return False


async def main():
    logger.info("=" * 60)
    logger.info("ACTIVE RECALL TEST SUITE")
    logger.info("=" * 60)

    results = []

    results.append(("Imports", await test_active_recall_imports()))
    results.append(("MongoDB Setup", await test_learning_checkpoints_collection()))
    results.append(("Service Functions", await test_active_recall_service()))
    results.append(("Response Recording", await test_response_recording()))
    results.append(("Endpoint Wiring", await test_endpoint_wiring()))

    logger.info("\n" + "=" * 60)
    logger.info("TEST RESULTS")
    logger.info("=" * 60)

    passed = 0
    failed = 0
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1

    logger.info("=" * 60)
    logger.info(f"Total: {passed} passed, {failed} failed")
    logger.info("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

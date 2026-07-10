"""
Coaching System Model & Database Schema
========================================

This service defines the MongoDB collections and schemas for the coaching system:

1. training_plans - 5 predefined coaching programs with full structure
2. user_coaching_prescriptions - Individual prescriptions for each user
3. coaching_prescription_history - Audit trail for all prescription changes
4. issue_to_plan_mapping - Many-to-many relationship with prerequisites
5. coaching_profile (embedded in users) - Coach-specific user profile

Collections designed for:
- Personalized coaching plan assignment
- Progress tracking and metric monitoring
- Historical audit trail for coaching decisions
- Flexible issue-to-plan mapping with prerequisites
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

# ==================== ENUMS & CONSTANTS ====================

class PrescriptionStatus(str, Enum):
    """Status of a coaching prescription."""
    PENDING = "pending"           # Prescribed, not yet started
    ACTIVE = "active"             # Currently in progress
    PAUSED = "paused"             # Temporarily paused
    COMPLETED = "completed"       # Finished successfully
    ABANDONED = "abandoned"       # User stopped before completion


class PlanDifficulty(str, Enum):
    """Difficulty level of training plans."""
    BEGINNER = "beginner"         # 600-1000 rating
    INTERMEDIATE = "intermediate" # 1000-1400 rating
    ADVANCED = "advanced"         # 1400-1800 rating
    EXPERT = "expert"             # 1800+ rating


class IssueSeverity(str, Enum):
    """Severity level of issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== PREDEFINED TRAINING PLANS ====================

PREDEFINED_TRAINING_PLANS = [
    {
        "plan_id": "plan_piece_safety_001",
        "name": "Piece Safety Fundamentals",
        "description": "Learn to protect your pieces and avoid hanging material.",
        "difficulty": PlanDifficulty.BEGINNER.value,
        "target_rating_min": 600,
        "target_rating_max": 1000,
        "duration_weeks": 4,
        "weekly_commitment_hours": 3,
        "cognitive_gap": "piece_safety",
        "related_gaps": ["missed_tactic"],
        "learning_outcomes": [
            "Identify unprotected pieces at a glance",
            "Count attacking and defending pieces systematically",
            "Develop the habit of checking piece safety before moving",
        ],
        "modules": [
            {
                "module_id": "mod_ps_001",
                "title": "Piece Counting Basics",
                "description": "Master the fundamental skill of counting attackers and defenders",
                "duration_minutes": 45,
                "content_type": "interactive_lesson",
                "puzzle_count": 10,
            },
            {
                "module_id": "mod_ps_002",
                "title": "Hanging Piece Recognition",
                "description": "Develop pattern recognition for unprotected pieces",
                "duration_minutes": 60,
                "content_type": "pattern_drill",
                "puzzle_count": 20,
            },
            {
                "module_id": "mod_ps_003",
                "title": "Position Analysis Review",
                "description": "Review your own games and spot protection weaknesses",
                "duration_minutes": 90,
                "content_type": "personalized_review",
                "puzzle_count": 0,
            },
        ],
        "success_criteria": {
            "min_puzzle_accuracy": 0.80,
            "min_modules_completed": 3,
            "metric_improvement": 0.25,  # 25% improvement
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
    },
    {
        "plan_id": "plan_calculation_001",
        "name": "Tactical Calculation Trainer",
        "description": "Improve your ability to calculate variations deeply and accurately.",
        "difficulty": PlanDifficulty.INTERMEDIATE.value,
        "target_rating_min": 1000,
        "target_rating_max": 1400,
        "duration_weeks": 6,
        "weekly_commitment_hours": 4,
        "cognitive_gap": "calculation_depth",
        "related_gaps": ["missed_tactic", "tactical_oversight"],
        "learning_outcomes": [
            "Calculate 3-4 moves ahead confidently",
            "Spot forcing moves (checks, captures, threats)",
            "Evaluate positions accurately after forced sequences",
        ],
        "modules": [
            {
                "module_id": "mod_calc_001",
                "title": "Forcing Moves Recognition",
                "description": "Learn to identify and prioritize forcing moves",
                "duration_minutes": 60,
                "content_type": "pattern_drill",
                "puzzle_count": 15,
            },
            {
                "module_id": "mod_calc_002",
                "title": "Three-Move Tactics",
                "description": "Master medium-depth tactical sequences",
                "duration_minutes": 75,
                "content_type": "interactive_lesson",
                "puzzle_count": 25,
            },
            {
                "module_id": "mod_calc_003",
                "title": "Deep Calculation Practice",
                "description": "Solve complex positions requiring 4+ move calculations",
                "duration_minutes": 90,
                "content_type": "puzzle_rush",
                "puzzle_count": 30,
            },
            {
                "module_id": "mod_calc_004",
                "title": "Your Game Analysis",
                "description": "Deep dive into calculation errors from your games",
                "duration_minutes": 120,
                "content_type": "personalized_review",
                "puzzle_count": 0,
            },
        ],
        "success_criteria": {
            "min_puzzle_accuracy": 0.75,
            "min_modules_completed": 4,
            "metric_improvement": 0.30,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
    },
    {
        "plan_id": "plan_king_safety_001",
        "name": "King Safety & Defense",
        "description": "Learn to defend your king and exploit opponent's king weaknesses.",
        "difficulty": PlanDifficulty.INTERMEDIATE.value,
        "target_rating_min": 1200,
        "target_rating_max": 1600,
        "duration_weeks": 5,
        "weekly_commitment_hours": 3,
        "cognitive_gap": "king_safety",
        "related_gaps": ["missed_tactic", "calculation_depth"],
        "learning_outcomes": [
            "Recognize vulnerable king positions quickly",
            "Develop defensive resources systematically",
            "Attack weak kings with precise tactics",
        ],
        "modules": [
            {
                "module_id": "mod_ks_001",
                "title": "King Vulnerability Assessment",
                "description": "Evaluate king safety factors in positions",
                "duration_minutes": 50,
                "content_type": "interactive_lesson",
                "puzzle_count": 12,
            },
            {
                "module_id": "mod_ks_002",
                "title": "Defensive Patterns",
                "description": "Master defensive resources and shelter positions",
                "duration_minutes": 65,
                "content_type": "pattern_drill",
                "puzzle_count": 18,
            },
            {
                "module_id": "mod_ks_003",
                "title": "King Attack Combinations",
                "description": "Exploit weak king positions with coordinated attacks",
                "duration_minutes": 75,
                "content_type": "puzzle_rush",
                "puzzle_count": 22,
            },
        ],
        "success_criteria": {
            "min_puzzle_accuracy": 0.78,
            "min_modules_completed": 3,
            "metric_improvement": 0.25,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
    },
    {
        "plan_id": "plan_opening_principles_001",
        "name": "Opening Principles Mastery",
        "description": "Master the fundamental principles of sound opening play.",
        "difficulty": PlanDifficulty.BEGINNER.value,
        "target_rating_min": 700,
        "target_rating_max": 1100,
        "duration_weeks": 3,
        "weekly_commitment_hours": 2,
        "cognitive_gap": "opening_knowledge",
        "related_gaps": [],
        "learning_outcomes": [
            "Understand key opening principles (control center, develop, castle)",
            "Recognize common opening blunders",
            "Build opening repertoires aligned with your style",
        ],
        "modules": [
            {
                "module_id": "mod_op_001",
                "title": "Core Opening Principles",
                "description": "The fundamentals every player must know",
                "duration_minutes": 40,
                "content_type": "interactive_lesson",
                "puzzle_count": 8,
            },
            {
                "module_id": "mod_op_002",
                "title": "Opening Mistake Patterns",
                "description": "Learn what NOT to do in the opening",
                "duration_minutes": 50,
                "content_type": "pattern_drill",
                "puzzle_count": 15,
            },
            {
                "module_id": "mod_op_003",
                "title": "Your Opening Errors",
                "description": "Analyze and fix opening mistakes from your games",
                "duration_minutes": 60,
                "content_type": "personalized_review",
                "puzzle_count": 0,
            },
        ],
        "success_criteria": {
            "min_puzzle_accuracy": 0.82,
            "min_modules_completed": 3,
            "metric_improvement": 0.20,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
    },
    {
        "plan_id": "plan_endgame_technique_001",
        "name": "Endgame Technique Essentials",
        "description": "Learn essential endgame patterns and techniques to convert advantages.",
        "difficulty": PlanDifficulty.ADVANCED.value,
        "target_rating_min": 1400,
        "target_rating_max": 1900,
        "duration_weeks": 7,
        "weekly_commitment_hours": 5,
        "cognitive_gap": "endgame_technique",
        "related_gaps": ["piece_activity"],
        "learning_outcomes": [
            "Master basic endgame patterns (K+P, K+R, K+Q)",
            "Understand opposition and key squares",
            "Convert technical advantages into wins",
        ],
        "modules": [
            {
                "module_id": "mod_eg_001",
                "title": "Pawn Endgame Fundamentals",
                "description": "Master king and pawn endgames",
                "duration_minutes": 80,
                "content_type": "interactive_lesson",
                "puzzle_count": 20,
            },
            {
                "module_id": "mod_eg_002",
                "title": "Rook Endgame Patterns",
                "description": "Learn essential rook ending positions",
                "duration_minutes": 90,
                "content_type": "pattern_drill",
                "puzzle_count": 25,
            },
            {
                "module_id": "mod_eg_003",
                "title": "Queen Endgame Techniques",
                "description": "Master queen versus minor piece and pawn endgames",
                "duration_minutes": 100,
                "content_type": "puzzle_rush",
                "puzzle_count": 30,
            },
            {
                "module_id": "mod_eg_004",
                "title": "Your Endgame Conversions",
                "description": "Analyze endgame mistakes and wins from your games",
                "duration_minutes": 120,
                "content_type": "personalized_review",
                "puzzle_count": 0,
            },
        ],
        "success_criteria": {
            "min_puzzle_accuracy": 0.80,
            "min_modules_completed": 4,
            "metric_improvement": 0.35,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
    },
]


# ==================== COLLECTION SCHEMAS ====================

def get_training_plan_schema() -> Dict:
    """Schema for training_plans collection."""
    return {
        "plan_id": "str (unique) - Stable identifier for the plan",
        "name": "str - Display name",
        "description": "str - What the plan teaches",
        "difficulty": "enum - 'beginner' | 'intermediate' | 'advanced' | 'expert'",
        "target_rating_min": "int - Minimum recommended rating",
        "target_rating_max": "int - Maximum recommended rating",
        "duration_weeks": "int - Expected completion time",
        "weekly_commitment_hours": "int - Recommended weekly hours",
        "cognitive_gap": "str - Primary gap this addresses (piece_safety, calculation_depth, etc)",
        "related_gaps": "list[str] - Secondary gaps",
        "learning_outcomes": "list[str] - What student will learn",
        "modules": "list[dict] - Structured modules with {module_id, title, description, duration_minutes, content_type, puzzle_count}",
        "success_criteria": "dict - {min_puzzle_accuracy, min_modules_completed, metric_improvement}",
        "created_at": "datetime - ISO format",
        "is_active": "bool - Whether plan is available for prescription",
    }


def get_user_coaching_prescriptions_schema() -> Dict:
    """Schema for user_coaching_prescriptions collection."""
    return {
        "prescription_id": "str (unique) - UUID",
        "user_id": "str - Reference to users.user_id",
        "plan_id": "str - Reference to training_plans.plan_id",
        "status": "enum - 'pending' | 'active' | 'paused' | 'completed' | 'abandoned'",
        "issue_detected": "str - The cognitive gap or weakness triggering this prescription",
        "reasoning": "str - Why this plan was recommended for this user",
        "baseline_metric": "float - Starting value (e.g., 0.45 accuracy on piece_safety)",
        "current_metric": "float - Most recent measured value",
        "improvement_pct": "float - Percentage improvement since baseline (0-100)",
        "started_at": "datetime | null - When prescription became active",
        "completed_at": "datetime | null - When prescription was marked complete",
        "expected_completion_date": "datetime - Projected end date based on plan duration",
        "priority_order": "int - Lower numbers = higher priority (1=highest)",
        "modules_completed": "list[str] - Completed module_ids",
        "current_module": "str | null - Currently active module_id",
        "puzzles_completed": "int - Total puzzles solved in this plan",
        "puzzle_accuracy": "float - Accuracy rate across all puzzles (0-1)",
        "notes": "str - Coaching notes or feedback",
        "created_at": "datetime - When prescription was issued",
        "updated_at": "datetime - Last update",
    }


def get_coaching_prescription_history_schema() -> Dict:
    """Schema for coaching_prescription_history collection (audit trail)."""
    return {
        "history_id": "str (unique) - UUID",
        "prescription_id": "str - Reference to user_coaching_prescriptions.prescription_id",
        "user_id": "str - Reference to users.user_id",
        "action": "str - 'prescribed' | 'activated' | 'paused' | 'resumed' | 'completed' | 'abandoned' | 'metric_updated'",
        "previous_status": "str - Status before this action",
        "new_status": "str - Status after this action",
        "metric_before": "float | null - Metric value before update",
        "metric_after": "float | null - Metric value after update",
        "reason": "str | null - Reason for status change or notes",
        "triggered_by": "str - 'user' | 'system' | 'coach'",
        "coach_id": "str | null - User ID of coach who made the change (if applicable)",
        "timestamp": "datetime - ISO format",
    }


def get_issue_to_plan_mapping_schema() -> Dict:
    """Schema for issue_to_plan_mapping collection (many-to-many with prerequisites)."""
    return {
        "mapping_id": "str (unique) - UUID",
        "cognitive_gap": "str - The issue type (piece_safety, calculation_depth, etc)",
        "severity_threshold": "enum - 'low' | 'medium' | 'high' | 'critical'",
        "plan_ids": "list[str] - Plans that address this issue",
        "recommended_order": "list[str] - Suggested order to complete plans",
        "prerequisite_mappings": "list[dict] - [{plan_id, requires_plan_id}] for prerequisite relationships",
        "trigger_criteria": "dict - When this mapping activates {metric_threshold, consecutive_games, etc}",
        "notes": "str - Additional guidance",
        "created_at": "datetime",
        "updated_at": "datetime",
    }


def get_coaching_profile_schema() -> Dict:
    """Schema for coaching_profile (embedded in users collection)."""
    return {
        "coaching_profile": {
            "current_prescriptions": "list[str] - Active prescription IDs",
            "completed_prescriptions": "list[str] - Completed prescription IDs",
            "total_training_hours": "int - Cumulative hours in coaching plans",
            "preferred_learning_style": "str - 'visual' | 'practice' | 'explanation'",
            "engagement_score": "float - 0-100, higher is more engaged",
            "last_prescription_date": "datetime | null",
            "coaching_level": "str - 'beginner' | 'intermediate' | 'advanced'",
            "coaching_notes": "str - Personalized coaching summary",
        }
    }


# ==================== DATABASE INITIALIZATION ====================

async def ensure_coaching_collections(db) -> None:
    """Create all coaching collections if they don't exist."""

    existing = await db.list_collection_names()

    collections = [
        "training_plans",
        "user_coaching_prescriptions",
        "coaching_prescription_history",
        "issue_to_plan_mapping",
    ]

    for coll in collections:
        if coll not in existing:
            await db.create_collection(coll)
            logger.info(f"Created collection: {coll}")
        else:
            logger.info(f"Collection exists: {coll}")


async def ensure_coaching_indexes(db) -> None:
    """Create indexes for coaching collections."""

    logger.info("Creating coaching indexes...")

    # Training Plans indexes
    await db.training_plans.create_index("plan_id", unique=True)
    await db.training_plans.create_index("difficulty")
    await db.training_plans.create_index("cognitive_gap")
    await db.training_plans.create_index([("target_rating_min", 1), ("target_rating_max", 1)])
    await db.training_plans.create_index("is_active")
    logger.info("  ✓ training_plans indexes")

    # User Coaching Prescriptions indexes
    await db.user_coaching_prescriptions.create_index("prescription_id", unique=True)
    await db.user_coaching_prescriptions.create_index("user_id")
    await db.user_coaching_prescriptions.create_index("plan_id")
    await db.user_coaching_prescriptions.create_index([("user_id", 1), ("status", 1)])
    await db.user_coaching_prescriptions.create_index([("user_id", 1), ("created_at", -1)])
    await db.user_coaching_prescriptions.create_index([("status", 1), ("priority_order", 1)])
    await db.user_coaching_prescriptions.create_index("issue_detected")
    await db.user_coaching_prescriptions.create_index("expected_completion_date")
    logger.info("  ✓ user_coaching_prescriptions indexes")

    # Coaching Prescription History indexes (audit trail)
    await db.coaching_prescription_history.create_index("history_id", unique=True)
    await db.coaching_prescription_history.create_index("prescription_id")
    await db.coaching_prescription_history.create_index("user_id")
    await db.coaching_prescription_history.create_index([("prescription_id", 1), ("timestamp", -1)])
    await db.coaching_prescription_history.create_index([("user_id", 1), ("timestamp", -1)])
    await db.coaching_prescription_history.create_index("action")
    await db.coaching_prescription_history.create_index("timestamp")
    logger.info("  ✓ coaching_prescription_history indexes")

    # Issue to Plan Mapping indexes
    await db.issue_to_plan_mapping.create_index("mapping_id", unique=True)
    await db.issue_to_plan_mapping.create_index("cognitive_gap", unique=True)
    await db.issue_to_plan_mapping.create_index("plan_ids")
    await db.issue_to_plan_mapping.create_index("severity_threshold")
    logger.info("  ✓ issue_to_plan_mapping indexes")


async def seed_training_plans(db) -> None:
    """Seed the database with predefined training plans."""

    logger.info("Seeding training plans...")

    for plan in PREDEFINED_TRAINING_PLANS:
        existing = await db.training_plans.find_one({"plan_id": plan["plan_id"]})
        if not existing:
            result = await db.training_plans.insert_one(plan)
            logger.info(f"  Inserted plan: {plan['name']} ({result.inserted_id})")
        else:
            logger.info(f"  Plan exists: {plan['name']}")


async def create_sample_issue_mappings(db) -> None:
    """Create sample issue-to-plan mappings for common cognitive gaps."""

    logger.info("Creating issue-to-plan mappings...")

    mappings = [
        {
            "mapping_id": str(uuid.uuid4()),
            "cognitive_gap": "piece_safety",
            "severity_threshold": IssueSeverity.HIGH.value,
            "plan_ids": ["plan_piece_safety_001"],
            "recommended_order": ["plan_piece_safety_001"],
            "prerequisite_mappings": [],
            "trigger_criteria": {
                "metric_threshold": 0.5,  # Accuracy below 50%
                "consecutive_games": 3,  # 3+ games with this issue
                "minimum_severity": "high"
            },
            "notes": "Fundamental skill for all ratings",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "mapping_id": str(uuid.uuid4()),
            "cognitive_gap": "calculation_depth",
            "severity_threshold": IssueSeverity.MEDIUM.value,
            "plan_ids": ["plan_calculation_001", "plan_tactical_advanced"],
            "recommended_order": ["plan_calculation_001"],
            "prerequisite_mappings": [
                {"plan_id": "plan_tactical_advanced", "requires_plan_id": "plan_calculation_001"}
            ],
            "trigger_criteria": {
                "metric_threshold": 0.55,
                "consecutive_games": 2,
                "minimum_severity": "medium"
            },
            "notes": "Prerequisite: complete Calculation Trainer first",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "mapping_id": str(uuid.uuid4()),
            "cognitive_gap": "king_safety",
            "severity_threshold": IssueSeverity.HIGH.value,
            "plan_ids": ["plan_king_safety_001"],
            "recommended_order": ["plan_king_safety_001"],
            "prerequisite_mappings": [],
            "trigger_criteria": {
                "metric_threshold": 0.50,
                "consecutive_games": 2,
                "minimum_severity": "high"
            },
            "notes": "Critical for all rating levels",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "mapping_id": str(uuid.uuid4()),
            "cognitive_gap": "opening_knowledge",
            "severity_threshold": IssueSeverity.MEDIUM.value,
            "plan_ids": ["plan_opening_principles_001"],
            "recommended_order": ["plan_opening_principles_001"],
            "prerequisite_mappings": [],
            "trigger_criteria": {
                "metric_threshold": 0.60,
                "consecutive_games": 3,
                "minimum_severity": "medium"
            },
            "notes": "Suitable for all players building opening foundation",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "mapping_id": str(uuid.uuid4()),
            "cognitive_gap": "endgame_technique",
            "severity_threshold": IssueSeverity.MEDIUM.value,
            "plan_ids": ["plan_endgame_technique_001"],
            "recommended_order": ["plan_endgame_technique_001"],
            "prerequisite_mappings": [],
            "trigger_criteria": {
                "metric_threshold": 0.55,
                "consecutive_games": 2,
                "minimum_severity": "medium"
            },
            "notes": "For advanced players (1400+ rating)",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    ]

    for mapping in mappings:
        existing = await db.issue_to_plan_mapping.find_one({"cognitive_gap": mapping["cognitive_gap"]})
        if not existing:
            result = await db.issue_to_plan_mapping.insert_one(mapping)
            logger.info(f"  Created mapping for {mapping['cognitive_gap']}")
        else:
            logger.info(f"  Mapping exists for {mapping['cognitive_gap']}")


async def add_coaching_profile_to_users(db) -> None:
    """Add coaching_profile field to users collection if not already present."""

    logger.info("Adding coaching_profile to users collection...")

    # Update all users that don't have a coaching_profile
    result = await db.users.update_many(
        {"coaching_profile": {"$exists": False}},
        {
            "$set": {
                "coaching_profile": {
                    "current_prescriptions": [],
                    "completed_prescriptions": [],
                    "total_training_hours": 0,
                    "preferred_learning_style": "practice",
                    "engagement_score": 50,
                    "last_prescription_date": None,
                    "coaching_level": "beginner",
                    "coaching_notes": "New coaching profile initialized",
                }
            }
        }
    )

    logger.info(f"  Updated {result.modified_count} users with coaching_profile")


async def initialize_coaching_system(db) -> None:
    """
    Complete initialization of the coaching system.

    This function should be called once during database setup.
    It will:
    1. Create collections
    2. Create indexes
    3. Seed predefined training plans
    4. Create sample issue-to-plan mappings
    5. Add coaching_profile to users collection
    """

    logger.info("=" * 60)
    logger.info("Initializing Coaching System")
    logger.info("=" * 60)

    try:
        await ensure_coaching_collections(db)
        await ensure_coaching_indexes(db)
        await seed_training_plans(db)
        await create_sample_issue_mappings(db)
        await add_coaching_profile_to_users(db)

        logger.info("=" * 60)
        logger.info("✅ Coaching system initialized successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error initializing coaching system: {e}", exc_info=True)
        raise


# ==================== SCHEMA DOCUMENTATION ====================

COACHING_SCHEMA_DOCS = """
COACHING SYSTEM DATABASE SCHEMA
================================

1. TRAINING PLANS Collection
   - Stores 5 predefined coaching programs
   - Each plan targets specific cognitive gaps
   - Includes modules, learning outcomes, success criteria
   - Fields: plan_id, name, description, difficulty, duration_weeks, etc.

2. USER COACHING PRESCRIPTIONS Collection
   - Individual coaching prescriptions for each user
   - Tracks progress, status, metrics
   - Linked to training_plans via plan_id
   - Fields: prescription_id, user_id, plan_id, status, baseline_metric, current_metric, etc.

3. COACHING PRESCRIPTION HISTORY Collection
   - Complete audit trail of all prescription changes
   - Tracks status changes, metric updates, actions
   - Enables historical analysis and reporting
   - Fields: history_id, prescription_id, action, timestamp, triggered_by, etc.

4. ISSUE TO PLAN MAPPING Collection
   - Many-to-many relationship between cognitive gaps and plans
   - Supports prerequisites and recommended order
   - Defines trigger criteria for automatic prescription
   - Fields: mapping_id, cognitive_gap, plan_ids, prerequisite_mappings, etc.

5. COACHING PROFILE (embedded in users)
   - User-specific coaching metadata
   - Tracks current/completed prescriptions, training hours
   - Stores learning preferences and engagement score
   - Fields: coaching_profile.current_prescriptions, total_training_hours, etc.

INDEXES:
--------
- training_plans: plan_id (unique), difficulty, cognitive_gap, rating range, is_active
- user_coaching_prescriptions: prescription_id (unique), (user_id, status), (status, priority), etc.
- coaching_prescription_history: (prescription_id, timestamp), (user_id, timestamp), action
- issue_to_plan_mapping: mapping_id (unique), cognitive_gap (unique)

PREDEFINED PLANS (5):
---------------------
1. plan_piece_safety_001 - Piece Safety Fundamentals (Beginner, 4 weeks)
2. plan_calculation_001 - Tactical Calculation Trainer (Intermediate, 6 weeks)
3. plan_king_safety_001 - King Safety & Defense (Intermediate, 5 weeks)
4. plan_opening_principles_001 - Opening Principles Mastery (Beginner, 3 weeks)
5. plan_endgame_technique_001 - Endgame Technique Essentials (Advanced, 7 weeks)
"""


if __name__ == "__main__":
    # Print schema documentation
    print(COACHING_SCHEMA_DOCS)
    print("\nTraining Plans Schema:")
    for key, desc in get_training_plan_schema().items():
        print(f"  {key}: {desc}")

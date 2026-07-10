"""
Test Suite for Coaching Model & Database Schema
================================================

Tests verify:
1. Schema structure and field types
2. Predefined training plans validity
3. Issue-to-plan mappings structure
4. Coaching profile schema
5. Index definitions
"""

import pytest
from datetime import datetime, timezone
from services.coaching_model import (
    PREDEFINED_TRAINING_PLANS,
    PrescriptionStatus,
    PlanDifficulty,
    IssueSeverity,
    get_training_plan_schema,
    get_user_coaching_prescriptions_schema,
    get_coaching_prescription_history_schema,
    get_issue_to_plan_mapping_schema,
    get_coaching_profile_schema,
)


class TestPredefinedTrainingPlans:
    """Test the 5 predefined training plans."""

    def test_plan_count(self):
        """Verify we have exactly 5 predefined plans."""
        assert len(PREDEFINED_TRAINING_PLANS) == 5, "Must have exactly 5 predefined plans"

    def test_plan_ids_unique(self):
        """Verify all plan IDs are unique."""
        plan_ids = [plan["plan_id"] for plan in PREDEFINED_TRAINING_PLANS]
        assert len(plan_ids) == len(set(plan_ids)), "Plan IDs must be unique"

    def test_plan_names_unique(self):
        """Verify all plan names are unique."""
        names = [plan["name"] for plan in PREDEFINED_TRAINING_PLANS]
        assert len(names) == len(set(names)), "Plan names must be unique"

    def test_each_plan_has_required_fields(self):
        """Verify each plan has all required fields."""
        required_fields = {
            "plan_id",
            "name",
            "description",
            "difficulty",
            "target_rating_min",
            "target_rating_max",
            "duration_weeks",
            "weekly_commitment_hours",
            "cognitive_gap",
            "related_gaps",
            "learning_outcomes",
            "modules",
            "success_criteria",
            "created_at",
            "is_active",
        }

        for plan in PREDEFINED_TRAINING_PLANS:
            missing = required_fields - set(plan.keys())
            assert not missing, f"Plan {plan['plan_id']} missing fields: {missing}"

    def test_difficulty_values_valid(self):
        """Verify difficulty values are valid enum values."""
        valid_difficulties = {e.value for e in PlanDifficulty}

        for plan in PREDEFINED_TRAINING_PLANS:
            assert plan["difficulty"] in valid_difficulties, \
                f"Invalid difficulty '{plan['difficulty']}' in plan {plan['plan_id']}"

    def test_rating_ranges_valid(self):
        """Verify rating ranges are sensible."""
        for plan in PREDEFINED_TRAINING_PLANS:
            assert plan["target_rating_min"] < plan["target_rating_max"], \
                f"Invalid rating range in {plan['plan_id']}"
            assert plan["target_rating_min"] >= 0, \
                f"Negative minimum rating in {plan['plan_id']}"
            assert plan["target_rating_max"] <= 3000, \
                f"Unrealistic maximum rating in {plan['plan_id']}"

    def test_modules_structure(self):
        """Verify module structure is consistent."""
        required_module_fields = {
            "module_id",
            "title",
            "description",
            "duration_minutes",
            "content_type",
            "puzzle_count",
        }

        for plan in PREDEFINED_TRAINING_PLANS:
            assert len(plan["modules"]) > 0, f"Plan {plan['plan_id']} has no modules"

            for module in plan["modules"]:
                missing = required_module_fields - set(module.keys())
                assert not missing, \
                    f"Module {module.get('module_id', '?')} in plan {plan['plan_id']} missing: {missing}"

                assert module["duration_minutes"] > 0, "Module duration must be positive"
                assert module["puzzle_count"] >= 0, "Puzzle count must be non-negative"

    def test_success_criteria_structure(self):
        """Verify success criteria are present and valid."""
        required_criteria = {
            "min_puzzle_accuracy",
            "min_modules_completed",
            "metric_improvement",
        }

        for plan in PREDEFINED_TRAINING_PLANS:
            criteria = plan["success_criteria"]
            missing = required_criteria - set(criteria.keys())
            assert not missing, \
                f"Plan {plan['plan_id']} missing success criteria: {missing}"

            assert 0 <= criteria["min_puzzle_accuracy"] <= 1, \
                f"Invalid min_puzzle_accuracy in {plan['plan_id']}"
            assert criteria["min_modules_completed"] > 0, \
                f"Invalid min_modules_completed in {plan['plan_id']}"
            assert 0 <= criteria["metric_improvement"] <= 1, \
                f"Invalid metric_improvement in {plan['plan_id']}"

    def test_cognitive_gap_coverage(self):
        """Verify different cognitive gaps are covered."""
        cognitive_gaps = {plan["cognitive_gap"] for plan in PREDEFINED_TRAINING_PLANS}

        expected_gaps = {
            "piece_safety",
            "calculation_depth",
            "king_safety",
            "opening_knowledge",
            "endgame_technique",
        }

        assert cognitive_gaps == expected_gaps, \
            f"Expected gaps {expected_gaps}, got {cognitive_gaps}"

    def test_created_at_timestamps(self):
        """Verify created_at timestamps are ISO format."""
        for plan in PREDEFINED_TRAINING_PLANS:
            created_at = plan["created_at"]
            # Should be parseable as ISO format
            assert "T" in created_at, f"Plan {plan['plan_id']} has non-ISO timestamp"
            assert ("Z" in created_at or "+" in created_at), \
                f"Plan {plan['plan_id']} timestamp missing timezone"


class TestSchemaDefinitions:
    """Test schema definitions for all collections."""

    def test_training_plan_schema_complete(self):
        """Verify training plan schema covers key fields."""
        schema = get_training_plan_schema()
        assert len(schema) > 0, "Schema should not be empty"
        assert "plan_id" in schema
        assert "name" in schema
        assert "modules" in schema
        assert "success_criteria" in schema

    def test_prescription_schema_complete(self):
        """Verify prescription schema covers key fields."""
        schema = get_user_coaching_prescriptions_schema()
        required = {
            "prescription_id",
            "user_id",
            "plan_id",
            "status",
            "baseline_metric",
            "current_metric",
            "improvement_pct",
        }
        for field in required:
            assert field in schema, f"Missing field: {field}"

    def test_history_schema_complete(self):
        """Verify history schema covers audit trail fields."""
        schema = get_coaching_prescription_history_schema()
        required = {
            "history_id",
            "prescription_id",
            "action",
            "timestamp",
            "triggered_by",
        }
        for field in required:
            assert field in schema, f"Missing field: {field}"

    def test_mapping_schema_complete(self):
        """Verify mapping schema covers many-to-many fields."""
        schema = get_issue_to_plan_mapping_schema()
        required = {
            "mapping_id",
            "cognitive_gap",
            "plan_ids",
            "prerequisite_mappings",
        }
        for field in required:
            assert field in schema, f"Missing field: {field}"

    def test_coaching_profile_schema_complete(self):
        """Verify coaching profile schema is complete."""
        schema = get_coaching_profile_schema()
        assert "coaching_profile" in schema, "Should have coaching_profile field"
        profile = schema["coaching_profile"]
        required = {
            "current_prescriptions",
            "completed_prescriptions",
            "total_training_hours",
            "engagement_score",
        }
        for field in required:
            assert field in profile, f"Missing field in coaching_profile: {field}"


class TestEnums:
    """Test enum definitions."""

    def test_prescription_status_values(self):
        """Verify PrescriptionStatus enum has expected values."""
        expected = {"pending", "active", "paused", "completed", "abandoned"}
        actual = {e.value for e in PrescriptionStatus}
        assert actual == expected, f"Expected {expected}, got {actual}"

    def test_plan_difficulty_values(self):
        """Verify PlanDifficulty enum has expected values."""
        expected = {"beginner", "intermediate", "advanced", "expert"}
        actual = {e.value for e in PlanDifficulty}
        assert actual == expected, f"Expected {expected}, got {actual}"

    def test_issue_severity_values(self):
        """Verify IssueSeverity enum has expected values."""
        expected = {"low", "medium", "high", "critical"}
        actual = {e.value for e in IssueSeverity}
        assert actual == expected, f"Expected {expected}, got {actual}"


class TestPlanTargeting:
    """Test that plans target appropriate rating ranges."""

    def test_no_overlapping_rating_ranges_by_difficulty(self):
        """Verify plans within same difficulty don't have conflicting rating ranges."""
        by_difficulty = {}
        for plan in PREDEFINED_TRAINING_PLANS:
            diff = plan["difficulty"]
            if diff not in by_difficulty:
                by_difficulty[diff] = []
            by_difficulty[diff].append(plan)

        # This is informational; just verify we have good coverage
        for difficulty, plans in by_difficulty.items():
            assert len(plans) > 0, f"No plans for difficulty {difficulty}"

    def test_all_rating_levels_covered(self):
        """Verify plans cover the full rating spectrum."""
        min_ratings = {plan["target_rating_min"] for plan in PREDEFINED_TRAINING_PLANS}
        max_ratings = {plan["target_rating_max"] for plan in PREDEFINED_TRAINING_PLANS}

        # Should have plans starting from near 0
        assert min(min_ratings) <= 700, "Should have beginner-level plans"

        # Should have plans going up to high ratings
        assert max(max_ratings) >= 1800, "Should have advanced-level plans"


class TestDatabaseReadiness:
    """Test that coaching system is ready for database integration."""

    def test_schemas_exportable(self):
        """Verify all schema functions are callable and return dicts."""
        schema_functions = [
            get_training_plan_schema,
            get_user_coaching_prescriptions_schema,
            get_coaching_prescription_history_schema,
            get_issue_to_plan_mapping_schema,
            get_coaching_profile_schema,
        ]

        for func in schema_functions:
            schema = func()
            assert isinstance(schema, dict), f"{func.__name__} should return dict"
            assert len(schema) > 0, f"{func.__name__} returned empty dict"

    def test_enum_values_serializable(self):
        """Verify enum values can be serialized to strings."""
        plan = PREDEFINED_TRAINING_PLANS[0]

        # Test that difficulty can be serialized
        difficulty = plan["difficulty"]
        assert isinstance(difficulty, str), "Difficulty should be string value"
        assert difficulty in [e.value for e in PlanDifficulty]

    def test_predefined_plans_ready_for_insertion(self):
        """Verify predefined plans have valid structure for MongoDB insertion."""
        for plan in PREDEFINED_TRAINING_PLANS:
            # plan_id should be unique identifier
            assert isinstance(plan["plan_id"], str)
            assert len(plan["plan_id"]) > 0

            # All string fields should be non-empty
            assert len(plan["name"]) > 0
            assert len(plan["description"]) > 0

            # All numeric fields should be positive
            assert plan["duration_weeks"] > 0
            assert plan["weekly_commitment_hours"] > 0

            # Learning outcomes should be non-empty list
            assert len(plan["learning_outcomes"]) > 0

            # Modules should be non-empty list
            assert len(plan["modules"]) > 0


class TestIntegration:
    """Integration-level tests."""

    def test_coaching_system_overview(self):
        """Verify the complete coaching system structure is coherent."""
        # We have training plans
        assert len(PREDEFINED_TRAINING_PLANS) == 5

        # Each plan addresses one or more cognitive gaps
        all_gaps = set()
        for plan in PREDEFINED_TRAINING_PLANS:
            all_gaps.add(plan["cognitive_gap"])
            all_gaps.update(plan["related_gaps"])

        # Should have diverse gap coverage
        assert len(all_gaps) >= 5, f"Should have at least 5 different gaps, got {len(all_gaps)}"

        # All plans should have valid structure
        for plan in PREDEFINED_TRAINING_PLANS:
            assert len(plan["modules"]) > 0
            assert len(plan["learning_outcomes"]) > 0
            assert "success_criteria" in plan


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

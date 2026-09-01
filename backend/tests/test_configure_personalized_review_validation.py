"""Safety properties for the Phase 6 validation-account tool."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "configure_personalized_review_validation.py"
)
SPEC = importlib.util.spec_from_file_location("phase6_enrollment", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalizes_deduplicates_and_requires_explicit_emails():
    assert MODULE.normalize_emails([
        " Coach@Example.com ",
        "coach@example.com",
    ]) == ("coach@example.com",)
    with pytest.raises(ValueError, match="explicit email"):
        MODULE.normalize_emails(["not-an-account"])


def test_feature_update_only_touches_the_namespaced_validation_flag():
    enabled = MODULE.feature_update(enabled=True)
    assert enabled == {
        "$set": {
            "feature_flags.personalized_game_review_coach.enabled": True,
            "feature_flags.personalized_game_review_coach.validation_compare": True,
            "feature_flags.personalized_game_review_coach.cohort": (
                "phase6_validation_2026_09"
            ),
        }
    }
    assert MODULE.feature_update(enabled=False)["$set"][
        "feature_flags.personalized_game_review_coach.enabled"
    ] is False


def test_script_has_no_credential_or_broad_update_literal():
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert "mongodb://" not in source
    assert "password" not in source
    assert "update_many" not in source
    assert 'os.environ.get("mongo_url")' in source
    assert 'os.environ.get("db_name")' in source

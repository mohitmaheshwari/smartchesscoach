import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "configure_home_replay_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("home_replay_enrollment", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalizes_deduplicates_and_requires_explicit_emails():
    assert MODULE.normalize_emails([
        " Coach@Example.com ", "coach@example.com"
    ]) == ("coach@example.com",)
    with pytest.raises(ValueError, match="explicit email"):
        MODULE.normalize_emails(["not-an-account"])


def test_feature_update_only_touches_namespaced_home_flag():
    assert MODULE.feature_update(enabled=True) == {
        "$set": {
            "feature_flags.home_replay_diagnostic.enabled": True,
            "feature_flags.home_replay_diagnostic.cohort": (
                "home_replay_validation_2026_09"
            ),
        }
    }


def test_script_has_no_credentials_or_broad_update():
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert "mongodb://" not in source
    assert "password" not in source
    assert "update_many" not in source
    assert 'os.environ.get("mongo_url")' in source
    assert 'os.environ.get("db_name")' in source

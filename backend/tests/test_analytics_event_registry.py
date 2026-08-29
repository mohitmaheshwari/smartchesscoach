"""Static contract tests for the single frontend analytics event registry."""

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
ANALYTICS_FILE = FRONTEND_SRC / "lib" / "analytics.js"


def _registry():
    source = ANALYTICS_FILE.read_text(encoding="utf-8")
    block = re.search(
        r"export const ANALYTICS_EVENTS = Object\.freeze\(\{(.*?)\}\);",
        source,
        re.DOTALL,
    )
    assert block, "ANALYTICS_EVENTS registry is missing"
    pairs = re.findall(r'^\s*([A-Z0-9_]+):\s*"([a-z0-9_]+)"', block.group(1), re.MULTILINE)
    return dict(pairs)


def test_registry_event_ids_are_unique():
    registry = _registry()

    assert registry
    assert len(registry.values()) == len(set(registry.values()))


def test_all_emitters_reference_a_registered_event_constant():
    registry = _registry()
    referenced = set()

    for path in FRONTEND_SRC.rglob("*.js*"):
        if path == ANALYTICS_FILE:
            continue
        source = path.read_text(encoding="utf-8")
        assert not re.search(r"\btrack(?:Curriculum)?\(\s*['\"`]", source), (
            f"raw analytics event string in {path.relative_to(REPO_ROOT)}"
        )
        referenced.update(
            re.findall(
                r"track(?:Curriculum)?\(\s*ANALYTICS_EVENTS\.([A-Z0-9_]+)",
                source,
            )
        )

    assert referenced
    assert referenced <= set(registry), f"unregistered event constants: {referenced - set(registry)}"


def test_personal_curriculum_event_contract_is_canonical_and_privacy_allowlisted():
    registry = _registry()
    required = {
        "CURRICULUM_DECISION_SHOWN": "curriculum_decision_shown",
        "CURRICULUM_PRIMARY_CLICKED": "curriculum_primary_clicked",
        "CURRICULUM_REVIEW_CLICKED": "curriculum_review_clicked",
        "LEARN_VIEWED": "learn_viewed",
        "PROGRESS_VIEWED": "progress_viewed",
        "EXPLORE_OPENED": "explore_opened",
        "LESSON_STARTED": "lesson_started",
        "EXPLANATION_COMPLETED": "explanation_completed",
        "GUIDED_ATTEMPT": "guided_attempt",
        "INDEPENDENT_ATTEMPT": "independent_attempt",
        "REVIEW_ATTEMPT": "review_attempt",
        "BACK_TO_PLAN": "back_to_plan",
    }
    assert {key: registry.get(key) for key in required} == required

    source = ANALYTICS_FILE.read_text(encoding="utf-8")
    allowlist = re.search(
        r"const CURRICULUM_ALLOWED_PROP_KEYS = new Set\(\[(.*?)\]\);",
        source,
        re.DOTALL,
    )
    assert allowlist, "Personal Curriculum analytics property allowlist is missing"
    allowed = set(re.findall(r'"([a-z0-9_]+)"', allowlist.group(1)))

    assert {"surface", "content_type", "content_id", "origin", "outcome"} <= allowed
    assert {
        "fen",
        "pgn",
        "move",
        "move_list",
        "email",
        "username",
        "coaching_text",
        "user_id",
        "game_id",
        "session_id",
    }.isdisjoint(allowed)


def test_source_map_names_the_registry_and_unknown_baseline():
    source_map = (REPO_ROOT / "docs" / "product_analytics_source_map.md").read_text(
        encoding="utf-8"
    )

    assert "ANALYTICS_EVENTS" in source_map
    assert "conversion rates are **unknown**, not zero" in source_map

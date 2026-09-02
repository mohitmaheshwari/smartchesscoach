#!/usr/bin/env python3
"""Derive the coach detector/content/drill capability matrix.

This report is deliberately a view over canonical registries. It owns no
opening line, trap sequence, endgame position, skill node, rating band or
authorization decision. Adding content or a detector updates this report
without a copied manifest edit.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.concept_detectors.registry import all_detectors
from services.concept_contract_registry import (
    content_ids_for_detector,
    exact_endgame_content_id,
    target_concept_ids_for_detector,
)
from services.curriculum_content_validator import get_publishable_content_ids
from services.detector_quality import (
    QualitySurface,
    concept_quality_id,
    get_authorization,
    is_authorized,
)
from services.endgame_theory_service import resolve_content_ref
from services.engine2_skill_builder import get_skill_node, list_skills_by_kind
from services.personalized_lesson_adapter import (
    supports_personalized_lesson_identity,
)


SCHEMA_VERSION = "coach_detector_capabilities.v1"


def _family(detector_id: str, module_name: str) -> str:
    """Group report rows without creating a chess-concept taxonomy."""
    if detector_id.startswith("endgame_curriculum__"):
        return "endgame"
    if detector_id.startswith(("endgame_", "mate_")):
        return "endgame"
    if detector_id.startswith("defend_") or detector_id == "trap_detection":
        return "trap"
    if detector_id.startswith("opening_") or detector_id == "coached_development":
        return "opening"
    if module_name.endswith("positional_patterns"):
        return "positional"
    return "concept"


def _skill_nodes(kinds: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for kind in kinds:
        for skill_id in list_skills_by_kind(kind):
            node = get_skill_node(skill_id)
            if isinstance(node, dict):
                result[skill_id] = node
    return result


def _workspace_identity(kind: str, content_id: str) -> tuple[str, str]:
    return ("endgame" if kind == "mate_pattern" else kind, content_id)


def _workspace_support(
    content_ids: list[str],
    target_skill_ids: list[str],
    skills: Dict[str, Dict[str, Any]],
    family: str,
) -> Dict[str, Any]:
    supported = set()
    for skill_id in target_skill_ids:
        node = skills[skill_id]
        kind, content_id = _workspace_identity(
            str(node.get("kind") or "concept"),
            str(node.get("content_ref") or ""),
        )
        if content_id and supports_personalized_lesson_identity(kind, content_id):
            supported.add(content_id)

    # Exact endgame adapters may point at verified Explore content before a
    # data-locked rating envelope makes the lesson curriculum-selectable.
    if family == "endgame":
        for content_id in content_ids:
            if "/" in content_id and supports_personalized_lesson_identity(
                "endgame", content_id
            ):
                supported.add(content_id)
    return {
        "available": bool(supported),
        "supported_content_ids": sorted(supported),
        "supported_content_count": len(supported),
    }


def _content_coverage(skills: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    opening_ids = get_publishable_content_ids("openings")
    trap_ids = get_publishable_content_ids("traps")
    opening_idea_ids = get_publishable_content_ids("opening_ideas")
    endgame_ids = get_publishable_content_ids("endgames")

    selectable_openings = {
        str(node.get("content_ref") or "")
        for node in skills.values()
        if node.get("kind") == "opening"
    }
    selectable_trap_families = {
        str(node.get("content_ref") or "").replace("_", "-")
        for node in skills.values()
        if node.get("kind") == "trap_set"
    }
    selectable_traps = {
        content_id
        for content_id in trap_ids
        if content_id.split("/", 1)[0].replace("_", "-")
        in selectable_trap_families
    }
    selectable_endgames = set()
    for node in skills.values():
        if node.get("kind") not in {"endgame", "mate_pattern"}:
            continue
        resolved = resolve_content_ref(str(node.get("content_ref") or ""))
        if resolved:
            selectable_endgames.add(str(resolved["lesson_id"]))

    return {
        "openings": {
            "publishable": len(opening_ids),
            "detector_covered": len(opening_ids),
            "curriculum_selectable": len(opening_ids & selectable_openings),
        },
        "traps": {
            "publishable": len(trap_ids),
            "detector_covered": len(trap_ids),
            "curriculum_selectable": len(trap_ids & selectable_traps),
        },
        "opening_ideas": {
            "publishable": len(opening_idea_ids),
            "detector_covered": (
                len(opening_idea_ids)
                if "opening_plan_play" in all_detectors()
                else 0
            ),
            "curriculum_selectable": 0,
        },
        "endgames": {
            "publishable": len(endgame_ids),
            "detector_covered": len(endgame_ids),
            "curriculum_selectable": len(endgame_ids & selectable_endgames),
        },
    }


def build_report() -> Dict[str, Any]:
    skills = _skill_nodes(
        ("opening", "trap", "trap_set", "endgame", "mate_pattern", "concept", "coached_play")
    )
    rows = []
    for detector_id, detector in sorted(all_detectors().items()):
        quality_id = concept_quality_id(detector_id)
        authorization = get_authorization(quality_id)
        family = _family(detector_id, detector.__module__)
        target_skill_ids = list(target_concept_ids_for_detector(detector_id, skills))
        content_ids = list(content_ids_for_detector(
            detector_id, target_skill_ids, skills
        ))
        workspace = _workspace_support(
            content_ids, target_skill_ids, skills, family
        )
        rows.append({
            "detector_id": detector_id,
            "detector_module": detector.__module__,
            "family": family,
            "quality_id": quality_id,
            "quality_grade": authorization.grade.value,
            "mastery_authorized": is_authorized(
                quality_id, QualitySurface.MASTERY
            ),
            "player_effect": (
                "mastery_enabled"
                if is_authorized(quality_id, QualitySurface.MASTERY)
                else "disabled"
                if authorization.grade.value == "disabled"
                else "shadow_only"
            ),
            "target_skill_ids": target_skill_ids,
            "target_skill_count": len(target_skill_ids),
            "content_ids": content_ids,
            "content_count": len(content_ids),
            "curriculum_mapped": bool(target_skill_ids) or detector_id == "opening_plan_play",
            "workspace": workspace,
            "evidence_ref": authorization.evidence_ref,
            "limitations": list(authorization.limitations),
        })

    family_counts = Counter(row["family"] for row in rows)
    effect_counts = Counter(row["player_effect"] for row in rows)
    unmapped = [
        row["detector_id"]
        for row in rows
        if not row["curriculum_mapped"]
        and exact_endgame_content_id(row["detector_id"]) is None
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": (
            "derived from canonical registries; Shadow output cannot write "
            "player mastery"
        ),
        "summary": {
            "registered_detectors": len(rows),
            "by_family": dict(sorted(family_counts.items())),
            "by_player_effect": dict(sorted(effect_counts.items())),
            "curriculum_mapped_detectors": sum(
                1 for row in rows if row["curriculum_mapped"]
            ),
            "workspace_supported_detectors": sum(
                1 for row in rows if row["workspace"]["available"]
            ),
        },
        "content_coverage": _content_coverage(skills),
        "mapping_gaps": unmapped,
        "detectors": rows,
    }


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2, sort_keys=True))

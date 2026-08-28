#!/usr/bin/env python3
"""Print one reproducible authorization inventory for every detector registry."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.caption_principles import PRINCIPLES
from services.chess_brain.detector_registry import get_detector_registry
from services.cognitive_gap_subtypes import CLASSIFIER_REGISTRY
from services.concept_detectors.registry import all_detectors
from services.detector_quality import (
    QualitySurface,
    explicit_authorizations,
    get_authorization,
    grade_for,
    is_authorized,
)
from services.endgame_detectors.principle_detector_registry import (
    DETECTORS as LEGACY_ENDGAME_DETECTORS,
)
from services.shape_patterns import PATTERNS_BY_ID


def canonical_quality_ids() -> list[str]:
    ids = set()
    ids.update(f"concept:{key}" for key in all_detectors())
    ids.update(f"shape:{key}" for key in PATTERNS_BY_ID)
    ids.update(
        f"principle:{entry['id']}"
        for entry in PRINCIPLES
        if isinstance(entry, dict) and entry.get("id")
    )

    brain = get_detector_registry()
    for registry in (
        brain._tactical_detectors,
        brain._strategic_detectors,
        brain._behavioral_detectors,
    ):
        ids.update(f"brain:{key}" for key in registry)

    # Family wildcard shows that a category classifier exists without
    # inventing a copied subtype taxonomy. Explicit promoted subtypes are
    # included from the quality authority below.
    ids.update(f"gap:{key}:*" for key in CLASSIFIER_REGISTRY)
    ids.update(
        f"legacy_endgame:{key}" for key in LEGACY_ENDGAME_DETECTORS
    )
    ids.update(explicit_authorizations())
    return sorted(ids)


def build_report() -> dict:
    rows = []
    explicit_ids = set(explicit_authorizations())
    for quality_id in canonical_quality_ids():
        grade = grade_for(quality_id)
        authorization = get_authorization(quality_id)
        rows.append({
            "quality_id": quality_id,
            "grade": grade.value,
            "explicit_authorization": quality_id in explicit_ids,
            "evidence_ref": authorization.evidence_ref,
            "rationale": authorization.rationale,
            "limitations": list(authorization.limitations),
            "caption_authorized": is_authorized(
                quality_id, QualitySurface.CAPTION
            ),
            "plan_authorized": is_authorized(
                quality_id, QualitySurface.PLAN
            ),
            "mastery_authorized": is_authorized(
                quality_id, QualitySurface.MASTERY
            ),
        })
    counts = Counter(row["grade"] for row in rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "strict authorization; independent of rollout flag",
        "summary": dict(sorted(counts.items())),
        "detectors": rows,
    }


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2, sort_keys=True))

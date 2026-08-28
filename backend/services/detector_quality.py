"""Canonical authorization for detector output.

Detector implementations and catalogs remain in their existing canonical
registries. This module stores only the right to influence a player-facing
surface. Unknown IDs deliberately fail closed to SHADOW.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


class QualityGrade(str, Enum):
    PLAN = "plan"
    CAPTION = "caption"
    SHADOW = "shadow"
    DISABLED = "disabled"


class QualitySurface(str, Enum):
    PLAN = "plan"
    CAPTION = "caption"
    MASTERY = "mastery"
    PROMPT = "prompt"
    DIAGNOSTIC = "diagnostic"


@dataclass(frozen=True)
class Authorization:
    grade: QualityGrade
    evidence_ref: str
    rationale: str
    limitations: Tuple[str, ...] = ()


_UNKNOWN = Authorization(
    grade=QualityGrade.SHADOW,
    evidence_ref="docs/detector_quality_threshold_lock_2026_08_27.md",
    rationale="No reviewed promotion packet; unknown IDs fail closed.",
    limitations=("Independent semantic precision and recall are not established.",),
)


# Promotions are intentionally sparse. Adding a detector to its canonical
# registry does not grant it product authority. Promotion is a separate,
# evidence-reviewed edit here.
_AUTHORIZATIONS: Mapping[str, Authorization] = {
    "gap:piece_safety:simple_hang": Authorization(
        grade=QualityGrade.PLAN,
        evidence_ref="docs/simple_hang_corpus_evidence.md",
        rationale=(
            "96.9% semantic precision on 260 reviewed fires with preserved "
            "opportunity evidence and 61.61% taxonomy recall."
        ),
        limitations=(
            "Authorization applies only to the current-schema simple_hang subtype.",
        ),
    ),

    # Measured candidates remain explicit Shadow entries so the quality report
    # carries their real evidence and limitations instead of making them look
    # identical to never-reviewed detectors.
    "shape:free_piece": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_exchange_truth_lock_2026_08_27.md",
        rationale=(
            "Strict post-capture recapture truth passed 200/200 rerated fires "
            "and 20/20 near-negative controls."
        ),
        limitations=(
            "No blinded independent semantic review packet.",
            "No Plan-grade opportunity/recall denominator.",
        ),
    ),
    "principle:TAC_HANGING_PIECE": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_exchange_truth_lock_2026_08_27.md",
        rationale=(
            "Board-mutating legal exchange truth removed 3,571 unsafe stored "
            "claims and passed the fresh deterministic rerating packet."
        ),
        limitations=(
            "No blinded causal-language review.",
            "Recall against independently selected hanging-piece opportunities is unknown.",
        ),
    ),
    "brain:hanging_piece_detector": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/hanging_piece_detector_implementation_2026_08_28.md",
        rationale=(
            "Chess Brain now adapts canonical board-mutating legal-exchange "
            "truth with a measured material floor, engine consequence and a "
            "strict played-versus-best issue-set counterfactual."
        ),
        limitations=(
            "The residual candidates have not received blinded semantic review.",
            "No independent Chess Brain hanging-piece opportunity denominator exists.",
        ),
    ),
    "principle:TAC_FORK_PATTERN": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_quality_threshold_lock_2026_08_27.md",
        rationale=(
            "Full-solution Lichess fork coverage reached 99.7%; a 28/28 "
            "move-attribution sample used the moving piece."
        ),
        limitations=(
            "Specificity is not established because theme absence is not negative truth.",
            "Independent semantic attribution sample is below the Caption-grade minimum.",
        ),
    ),
    "shape:pin": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_tactical_attribution_2026_08_27.md",
        rationale=(
            "Before/after causal filtering is implemented and absolute-pin "
            "king ordering is corrected."
        ),
        limitations=(
            "Fresh independent semantic precision is not yet measured.",
            "Recall and hard-negative performance are unknown.",
        ),
    ),
    "shape:skewer": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_tactical_attribution_2026_08_27.md",
        rationale=(
            "Before/after causal filtering is implemented and pin/skewer "
            "value ordering now treats the king as the highest alignment piece."
        ),
        limitations=(
            "Fresh independent semantic precision is not yet measured.",
            "The defended-front-piece adversarial packet is incomplete.",
        ),
    ),

    # Known unsafe claims do not need to execute in normal product paths.
    "concept:endgame_rule_of_square": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/rule_of_square_consolidation_implementation_2026_08_27.md",
        rationale=(
            "Canonical legal-race truth is implemented and all consumers are "
            "adapters, but the production scan found only five eligible positions "
            "and all five belong to one game."
        ),
        limitations=(
            "Needs the locked review counts across independent games and source units "
            "before reconsideration.",
        ),
    ),
    "legacy_endgame:rule_of_square": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/rule_of_square_consolidation_implementation_2026_08_27.md",
        rationale=(
            "The legacy surface is now a thin adapter over canonical legal-race "
            "truth; production evidence is still too sparse for authorization."
        ),
        limitations=(
            "Needs the locked review counts across independent games and source units "
            "before reconsideration.",
        ),
    ),
    "principle:END_RULE_OF_SQUARE": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/rule_of_square_consolidation_implementation_2026_08_27.md",
        rationale=(
            "The caption predicate now consumes canonical legal-race truth, including "
            "immediate captures; production evidence is still too sparse for authorization."
        ),
        limitations=(
            "Needs the locked review counts across independent games and source units "
            "before reconsideration.",
        ),
    ),
    "brain:trapped_piece_detector": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/trapped_piece_detector_implementation_2026_08_27.md",
        rationale=(
            "The turn-order defect is fixed and Chess Brain now adapts canonical "
            "move-causal trapped-piece truth, but independent semantic precision "
            "and recall are not established."
        ),
        limitations=(
            "No stable trapped-piece opportunity denominator.",
            "The seven post-gate production candidates still need blinded review.",
        ),
    ),
    "brain:king_safety_detector": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/king_safety_detector_implementation_2026_08_28.md",
        rationale=(
            "Broad post-move geometry was replaced with canonical board-state facts, "
            "a best-move issue-set counterfactual, a consequence floor and an endgame "
            "gate; independent semantic precision and recall are not established."
        ),
        limitations=(
            "The 90 residual production candidates still need blinded review.",
            "No independent king-safety opportunity denominator exists.",
        ),
    ),
}


def gap_quality_id(pattern: str, subtype: Optional[str]) -> str:
    return f"gap:{pattern}:{subtype or '*'}"


def shape_quality_id(pattern_id: str) -> str:
    return f"shape:{pattern_id}"


def principle_quality_id(principle_id: str) -> str:
    return f"principle:{principle_id}"


def concept_quality_id(skill_id: str) -> str:
    return f"concept:{skill_id}"


def brain_quality_id(detector_id: str) -> str:
    return f"brain:{detector_id}"


def observation_concept_quality_id(concept_id: str) -> str:
    return f"observation_concept:{concept_id}"


def get_authorization(quality_id: str) -> Authorization:
    return _AUTHORIZATIONS.get(quality_id, _UNKNOWN)


def explicit_authorizations() -> Dict[str, Authorization]:
    return dict(_AUTHORIZATIONS)


def grade_for(quality_id: str) -> QualityGrade:
    return get_authorization(quality_id).grade


def is_authorized(quality_id: str, surface: QualitySurface | str) -> bool:
    surface = QualitySurface(surface)
    grade = grade_for(quality_id)
    if surface == QualitySurface.DIAGNOSTIC:
        return grade != QualityGrade.DISABLED
    if surface == QualitySurface.CAPTION:
        return grade in (QualityGrade.CAPTION, QualityGrade.PLAN)
    # Plans, mastery claims and persistent coaching prompts need Plan-grade.
    return grade == QualityGrade.PLAN


def enforcement_enabled() -> bool:
    """Whether Shadow authorization is enforced on product output.

    Default-off prevents a registry audit from becoming an accidental blanket
    production outage. Explicitly Disabled IDs remain blocked in either mode.
    """
    return os.environ.get(
        "DETECTOR_QUALITY_GATE_ENFORCED", "false"
    ).lower() == "true"


def can_influence(quality_id: str, surface: QualitySurface | str) -> bool:
    grade = grade_for(quality_id)
    if grade == QualityGrade.DISABLED:
        return False
    if not enforcement_enabled():
        return True
    return is_authorized(quality_id, surface)


def authorized_gap_subtypes(pattern: str) -> Tuple[str, ...]:
    prefix = f"gap:{pattern}:"
    return tuple(
        quality_id[len(prefix):]
        for quality_id, auth in _AUTHORIZATIONS.items()
        if quality_id.startswith(prefix)
        and auth.grade == QualityGrade.PLAN
        and not quality_id.endswith(":*")
    )


def sanitize_plan_observation(observation: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a plan-safe observation while retaining shadow diagnostics.

    Neutral engine facts remain available. Detector-derived gap/concept fields
    are copied into detector_quality_shadow when they lack Plan authority,
    then removed from the fields consumed by focus/strength aggregation.
    """
    safe = dict(observation)
    shadow: Dict[str, Any] = dict(safe.get("detector_quality_shadow") or {})

    pattern = safe.get("missed_pattern")
    subtype = safe.get("subtype")
    if pattern:
        quality_id = gap_quality_id(str(pattern), str(subtype) if subtype else None)
        if not can_influence(quality_id, QualitySurface.PLAN):
            shadow["gap"] = {
                "quality_id": quality_id,
                "missed_pattern": pattern,
                "subtype": subtype,
                "severity": safe.get("severity"),
                "grade": grade_for(quality_id).value,
            }
            safe["missed_pattern"] = None
            safe["subtype"] = None
            safe["severity"] = None

    pattern_id = safe.get("tactical_pattern_executed")
    if pattern_id:
        quality_id = shape_quality_id(str(pattern_id))
        if not can_influence(quality_id, QualitySurface.PLAN):
            shadow["tactical_pattern_executed"] = {
                "quality_id": quality_id,
                "pattern_id": pattern_id,
                "grade": grade_for(quality_id).value,
            }
            safe["tactical_pattern_executed"] = None

    concept_id = safe.get("concept_used")
    if concept_id:
        quality_id = observation_concept_quality_id(str(concept_id))
        if not can_influence(quality_id, QualitySurface.PLAN):
            shadow["concept_used"] = {
                "quality_id": quality_id,
                "concept_id": concept_id,
                "grade": grade_for(quality_id).value,
            }
            safe["concept_used"] = None

    if shadow:
        safe["detector_quality_shadow"] = shadow
    return safe


def quality_id_for_focus_document(focus: Mapping[str, Any]) -> Optional[str]:
    explicit = focus.get("detector_quality_id")
    if explicit:
        return str(explicit)
    # Compatibility for the already-built, versioned PIC focus document.
    if (
        focus.get("focus_kind") == "piece_safety/simple_hang"
        and focus.get("diagnosis_detector_id")
        == "move_observation.simple_hang.v16_plus"
    ):
        return gap_quality_id("piece_safety", "simple_hang")
    return None


def focus_document_is_authorized(focus: Mapping[str, Any]) -> bool:
    quality_id = quality_id_for_focus_document(focus)
    if not quality_id:
        return not enforcement_enabled()
    return can_influence(quality_id, QualitySurface.PLAN)


def filter_authorized_events(
    events: Iterable[Mapping[str, Any]],
    *,
    id_field: str,
    namespace: str,
    surface: QualitySurface | str,
) -> Tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    """Split events into authorized and shadow lists without losing evidence."""
    allowed: list[Dict[str, Any]] = []
    shadow: list[Dict[str, Any]] = []
    for event in events:
        copied = dict(event)
        detector_id = copied.get(id_field)
        quality_id = f"{namespace}:{detector_id}" if detector_id else ""
        copied["detector_quality_id"] = quality_id or None
        copied["detector_quality_grade"] = grade_for(quality_id).value
        if quality_id and is_authorized(quality_id, surface):
            allowed.append(copied)
        else:
            shadow.append(copied)
    return allowed, shadow

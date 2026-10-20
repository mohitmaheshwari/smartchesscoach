"""Phase 4 adapters into the existing learning-session evidence ledger.

This module owns no chess rules and no mastery thresholds. It converts
server-owned review, guided-practice and current-schema application evidence
into ``personal_curriculum.LessonResult`` values, then appends their serialized
form to ``learning_sessions.events`` in shadow mode.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, List, Mapping, Optional, Tuple

from services.detector_quality import gap_quality_id
from services.destination_safety_detector import is_destination_safety_fact_version
from services.personal_curriculum import (
    ApplicationOutcome,
    AssistanceKind,
    AttemptKind,
    ContractViolation,
    EvidenceSourceType,
    LessonResult,
    PIC_CANONICAL_SOURCE,
    PIC_CONTENT_ID,
    PIC_CONTENT_KIND,
    PIC_CONTENT_VERSION,
    PIC_SKILL_ID,
)
from services.learning_evidence_ledger import (
    EVENT_KEY_COMPATIBILITY_VERSION as REVIEW_LEARNING_ADAPTER_VERSION,
    build_shadow_learning_event,
    store_shadow_lesson_results,
    store_shadow_lesson_results_sync,
)


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if len(raw) >= 10:
            # Chess.com imports commonly store the calendar day as
            # YYYY.MM.DD. Preserve any time suffix while normalizing the date.
            raw = raw[:10].replace(".", "-") + raw[10:]
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ContractViolation(f"{field_name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        # Existing imported games can carry naive UTC datetimes. Preserve the
        # stored instant instead of dropping otherwise valid learning evidence.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def lesson_result_from_review_reflection(
    document: Mapping[str, Any],
) -> LessonResult:
    """A completed review/reveal proves exposure, never independent skill."""
    if document.get("reflection_kind") != "game_review_event":
        raise ContractViolation("unsupported reflection kind")
    event = document.get("event")
    response = document.get("response")
    if not isinstance(event, Mapping) or not isinstance(response, Mapping):
        raise ContractViolation("reflection evidence is incomplete")
    content_id = str(event.get("content_ref") or "")
    canonical_source = str(event.get("canonical_source") or "")
    if not content_id or not canonical_source:
        raise ContractViolation("reflection lacks canonical content identity")
    if (
        content_id != PIC_CONTENT_ID
        or canonical_source != PIC_CANONICAL_SOURCE
    ):
        raise ContractViolation("reflection canonical content is unsupported")
    source_event_id = str(event.get("event_id") or "")
    if not source_event_id:
        raise ContractViolation("reflection lacks source event identity")
    return LessonResult(
        content_kind=PIC_CONTENT_KIND,
        content_id=content_id,
        canonical_source=canonical_source,
        content_version=PIC_CONTENT_VERSION,
        skill_id=PIC_SKILL_ID,
        primary_skill_id=PIC_SKILL_ID,
        attempt_kind=AttemptKind.EXPLANATION,
        occurred_at=_parse_datetime(response.get("submitted_at"), "submitted_at"),
        correct=None,
        assistance=(AssistanceKind.ANSWER_REVEALED,),
        detector_quality_id=event.get("quality_id"),
        source_event_id=source_event_id,
    )


def lesson_result_from_guided_pic_practice(
    *,
    session_id: str,
    item_id: str,
    interaction_id: str,
    occurred_at: datetime,
    correct: bool,
) -> LessonResult:
    """PIC is guided practice; correctness can prove only 'with help'."""
    if not session_id or not item_id or not interaction_id:
        raise ContractViolation("practice identity is incomplete")
    return LessonResult(
        content_kind=PIC_CONTENT_KIND,
        content_id=PIC_CONTENT_ID,
        canonical_source=PIC_CANONICAL_SOURCE,
        content_version=PIC_CONTENT_VERSION,
        skill_id=PIC_SKILL_ID,
        primary_skill_id=PIC_SKILL_ID,
        attempt_kind=AttemptKind.GUIDED,
        occurred_at=occurred_at,
        correct=bool(correct),
        assistance=(AssistanceKind.GUIDED_LINE,),
        position_id=item_id,
        board_verified=True,
        distinct_position=False,
        detector_quality_id=gap_quality_id("piece_safety", "simple_hang"),
        source_event_id=(
            f"pic_practice:{session_id}:{item_id}:{interaction_id}"
        ),
    )


@dataclass(frozen=True)
class _AdmittedShape:
    """One observation shape that may become lesson evidence."""

    pattern: str
    subtype: str
    content_id: str
    skill_id: str
    # The POSITIVE observation, and it must share the miss's denominator.
    applied_values: Tuple[str, ...] = ()


# Which observation shapes become lesson evidence, and what "applied" means
# for each.
#
# Until 2026-10-20 admission was two hardcoded conditions, both piece_safety,
# so every other concept's evidence was dropped before it could become a
# LessonResult. That is the whole reason lesson evidence existed for exactly
# two gap ids and why both were piece_safety -- not because other concepts
# were untaught. Measured then: four PLAN-grade missed_tactic detectors and a
# PLAN-grade king_safety detector, all reaching real users' plans, all with
# puzzle supply, all with zero recorded evidence.
#
# The identity needs no new mapping. A gap id is
# gap:<missed_pattern>:<subtype> and both tokens are already on the
# observation, so this table carries only the parts that are a JUDGEMENT.
#
# That judgement is `applied`. A miss is easy: the detector fired. A success
# has to be a different, positive observation -- never the absence of a
# failure, or the rate silently becomes "moves where we noticed nothing" and
# every concept trends toward mastered. gap:piece_safety:simple_hang is the
# cautionary case: it can only ever be recorded as missed, and at 0 applied
# against 607 missed it cannot show improvement in either direction.
#
# The positive observation must also share the MISS's denominator. A success
# counted from a wider population than the failure inflates the rate without
# anything improving, which is the same error as counting quiet moves, just
# harder to see.
#
# So a shape without a denominator-matched positive observation is NOT
# admitted. Three are held back:
#   missed_mate              nothing records "delivered the mate that was
#                            available"; queen_knight_mate is a shape name,
#                            not that claim
#   missed_discovered_attack `hidden_attack` is adjacent but is not the same
#                            claim, and treating it as one would manufacture
#                            successes
#   ignored_king_attack      this one was admitted and then withdrawn, and
#                            the dry run is why. `responded_to_threat` reads
#                            91% applied (3,142 against 315) because it fires
#                            for ANY threat answered, while the miss fires
#                            only for a king attack ignored. A success row
#                            carries no threat-type label at all -- no
#                            missed_pattern, no subtype, and only 528 of
#                            23,184 are even checks -- so the two sides
#                            cannot be made to count the same thing. It needs
#                            a king-specific response observation first.
#                            Admitting it would have shipped a 91% success
#                            rate on a concept nobody had got better at.
_ADMITTED_SHAPES: Tuple[_AdmittedShape, ...] = (
    # Forks are the best-balanced pair in the corpus: 902 missed against 932
    # executed across the four piece-specific fork values.
    _AdmittedShape(
        pattern="missed_tactic",
        subtype="missed_fork",
        content_id="missed_tactic.missed_fork",
        skill_id="missed_tactic_missed_fork",
        applied_values=("knight_fork", "rook_fork", "bishop_fork", "pawn_fork"),
    ),
    # Pins and skewers are two-sided but heavily one-way (1,513 missed to 39
    # executed; 1,021 to 83). Admitted anyway: that ratio is a finding about
    # 600-1500 play, and suppressing it here would be the loop report's
    # judgement to make, not this module's.
    _AdmittedShape(
        pattern="missed_tactic",
        subtype="missed_pin",
        content_id="missed_tactic.missed_pin",
        skill_id="missed_tactic_missed_pin",
        applied_values=("pin",),
    ),
    _AdmittedShape(
        pattern="missed_tactic",
        subtype="missed_skewer",
        content_id="missed_tactic.missed_skewer",
        skill_id="missed_tactic_missed_skewer",
        applied_values=("skewer",),
    ),
)

_SHAPES_BY_SUBTYPE = {shape.subtype: shape for shape in _ADMITTED_SHAPES}
_SHAPES_BY_APPLIED_VALUE = {
    value: shape
    for shape in _ADMITTED_SHAPES
    for value in shape.applied_values
}


def _widened_shape(
    observation: Mapping[str, Any],
) -> Optional[Tuple[_AdmittedShape, ApplicationOutcome]]:
    """Resolve one observation to an admitted shape and its outcome, or None.

    The miss branch requires the observation's own pattern to agree with the
    table, so a subtype arriving under an unexpected pattern is skipped rather
    than relabelled.
    """
    subtype = str(observation.get("subtype") or "")
    shape = _SHAPES_BY_SUBTYPE.get(subtype)
    if shape is not None:
        if str(observation.get("missed_pattern") or "") == shape.pattern:
            return shape, ApplicationOutcome.MISSED
        return None

    executed = str(observation.get("tactical_pattern_executed") or "")
    shape = _SHAPES_BY_APPLIED_VALUE.get(executed)
    if shape is not None:
        return shape, ApplicationOutcome.APPLIED
    return None


def application_results_from_observations(
    *,
    game_id: str,
    observations: Iterable[Mapping[str, Any]],
    occurred_at: Any,
    include_handled: bool = False,
    source_type: EvidenceSourceType = EvidenceSourceType.ORGANIC_GAME,
    assistance: tuple[AssistanceKind, ...] = (),
    assistance_measured: bool = True,
) -> List[LessonResult]:
    """Adapt explicit exact opportunities; absence is never application.

    The board fact is identical for imported and Play With Coach games. Its
    provenance is not: callers preserve whether the decision happened in an
    organic game or a coached environment, and whether help was available.
    """
    if source_type not in (
        EvidenceSourceType.ORGANIC_GAME,
        EvidenceSourceType.COACHED_APPLICATION,
    ):
        raise ContractViolation(
            "observation applications require an organic or coached source"
        )
    if any(not isinstance(item, AssistanceKind) for item in assistance):
        raise ContractViolation("assistance entries must be AssistanceKind values")
    if not isinstance(assistance_measured, bool):
        raise ContractViolation("assistance_measured must be boolean")
    results: List[LessonResult] = []
    event_time = _parse_datetime(occurred_at, "occurred_at")
    for observation in observations or []:
        if int(observation.get("schema_version") or 0) < 16:
            continue
        simple_hang = (
            observation.get("missed_pattern") == "piece_safety"
            and observation.get("subtype") == "simple_hang"
        )
        exact_fact = observation.get("destination_safety_exact") or {}
        current_exact_miss = (
            int(observation.get("schema_version") or 0) >= 18
            and is_destination_safety_fact_version(exact_fact.get("version"))
            and exact_fact.get("fires") is True
            and exact_fact.get("derivation_status") == "ok"
            and exact_fact.get("eligible") is True
            and exact_fact.get("outcome") == "miss"
        )
        legacy_exact_miss = (
            int(observation.get("schema_version") or 0) >= 18
            and is_destination_safety_fact_version(exact_fact.get("version"))
            and exact_fact.get("fires") is True
            and exact_fact.get("derivation_status") in {None, "ok"}
            and exact_fact.get("eligible") in {None, True}
            and exact_fact.get("outcome") in {None, "miss"}
            and (
                exact_fact.get("derivation_status") is None
                or exact_fact.get("eligible") is None
                or exact_fact.get("outcome") is None
            )
        )
        exact_miss = current_exact_miss or legacy_exact_miss
        exact_handled = (
            include_handled
            and int(observation.get("schema_version") or 0) >= 18
            and is_destination_safety_fact_version(exact_fact.get("version"))
            and exact_fact.get("derivation_status") == "ok"
            and exact_fact.get("eligible") is True
            and exact_fact.get("outcome") == "handled"
        )
        exact_destination = exact_miss or exact_handled
        widened = (
            None
            if (simple_hang or exact_destination)
            else _widened_shape(observation)
        )
        if not (simple_hang or exact_destination or widened):
            continue
        ply = int(observation.get("ply") or 0)
        if not game_id or ply < 1:
            continue
        exact_outcome = str(exact_fact.get("outcome") or "")
        application_outcome = (
            widened[1]
            if widened
            else (
                ApplicationOutcome.APPLIED
                if exact_destination and exact_outcome == "handled"
                else ApplicationOutcome.MISSED
            )
        )
        exact_measurement_complete = bool(
            simple_hang
            or current_exact_miss
            or exact_handled
            or widened is not None
        )
        limitations = (
            ()
            if exact_measurement_complete
            else ("legacy_exact_opportunity_fields_missing",)
        )
        shape = widened[0] if widened else None
        results.append(
            LessonResult(
                content_kind=PIC_CONTENT_KIND,
                content_id=shape.content_id if shape else PIC_CONTENT_ID,
                # These concepts are defined by their detector, not by an
                # authored curriculum entry, so the canonical source names the
                # authority that actually owns the definition. Claiming a
                # personal_curriculum source they do not have would be the
                # kind of overstatement the contract index warns about.
                canonical_source=(
                    f"detector_quality.{gap_quality_id(shape.pattern, shape.subtype)}"
                    if shape
                    else PIC_CANONICAL_SOURCE
                ),
                content_version=PIC_CONTENT_VERSION,
                skill_id=shape.skill_id if shape else PIC_SKILL_ID,
                primary_skill_id=shape.skill_id if shape else PIC_SKILL_ID,
                attempt_kind=AttemptKind.APPLICATION,
                occurred_at=event_time,
                application_outcome=application_outcome,
                source_type=source_type,
                assistance=assistance,
                assistance_measured=assistance_measured,
                detector_quality_id=(
                    gap_quality_id(shape.pattern, shape.subtype)
                    if shape
                    else (
                        "gap:piece_safety:destination_safety_exact"
                        if exact_destination
                        else gap_quality_id("piece_safety", "simple_hang")
                    )
                ),
                detector_version=(
                    str(exact_fact.get("version"))
                    if exact_destination
                    else None
                ),
                evidence_owner="move_observations",
                evidence_ref=f"{game_id}:{ply}",
                proof_contract_version=(
                    str(exact_fact.get("version"))
                    if exact_destination
                    else None
                ),
                evidence_complete=exact_measurement_complete,
                evidence_limitations=limitations,
                source_event_id=f"move_observation:{game_id}:{ply}",
            )
        )
    return results

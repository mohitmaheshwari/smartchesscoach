#!/usr/bin/env python3
"""Admit independently reviewed community-game studies, fail closed.

The source review packet is blinded and contains no runtime answer key.  The
separate sealed packet contains the anonymous studies that may eventually be
served.  This script binds those artifacts by case id and frozen fingerprints,
recomputes every locked quality gate from the reviewer's case-level answers,
validates every sealed study, and writes nothing unless the exact dry-run plan
is confirmed.

Mongo credentials are read only from the container environment.  The default
mode is read-only:

    python backend/scripts/admit_reviewed_community_game_studies.py \
      --source-review-packet <pending-v4.json> \
      --reviewed-packet <reviewed-v4.json> \
      --admission-packet <sealed-v4.json> \
      --expected-source-sha256 <sha>

Apply only the exact plan printed by that run:

    python backend/scripts/admit_reviewed_community_game_studies.py ... \
      --apply --confirm community-game-study-v4-admission \
      --confirm-plan <plan-fingerprint>
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, Mapping, Sequence


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from scripts.build_community_game_study_review_packet import (  # noqa: E402
    REVIEW_RESPONSE_SCHEMA_VERSION,
    SCHEMA_VERSION as REVIEW_PACKET_SCHEMA_VERSION,
    blank_reviewer_response,
)
from services.community_game_study_service import (  # noqa: E402
    COLLECTION,
    guided_answer_position_indices,
    validate_study,
)


ADMISSION_PACKET_SCHEMA_VERSION = "community_game_study.admission_packet.v1"
ADMISSION_RECORD_SCHEMA_VERSION = "community_game_study.independent_admission.v1"
CONFIRMATION = "community-game-study-v4-admission"
CHAPTER_VERDICTS = frozenset({
    "correct_and_teachable",
    "correct_but_not_teachable",
    "unclear_or_too_generic",
    "incorrect_or_overclaimed",
})
CORRECT_AND_TEACHABLE_FLOOR = 0.718
COHERENT_STORY_FLOOR = 0.098
ASSIGNMENT_WORTHY_FLOOR = 0.488
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TERMINAL_STATUSES = frozenset({"quarantined", "withdrawn", "stale"})


class AdmissionError(RuntimeError):
    """The frozen evidence cannot safely authorize runtime studies."""


@dataclass(frozen=True)
class ReviewDecision:
    case_id: str
    admit: bool
    response: Mapping[str, Any]


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _value_sha256(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"cannot read JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise AdmissionError(f"artifact root must be an object: {path}")
    return value


def _strict_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise AdmissionError(f"{field} must be boolean")
    return bool(value)


def _nonempty(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise AdmissionError(f"{field} must be non-empty")
    return text


def _case_index(packet: Mapping[str, Any], field: str) -> Dict[str, Mapping[str, Any]]:
    cases = packet.get("cases")
    if not isinstance(cases, list) or not cases:
        raise AdmissionError(f"{field}.cases must be a non-empty list")
    result: Dict[str, Mapping[str, Any]] = {}
    for row in cases:
        if not isinstance(row, Mapping):
            raise AdmissionError(f"{field}.cases contains a non-object")
        case_id = _nonempty(row.get("case_id"), f"{field}.case_id")
        if case_id in result:
            raise AdmissionError(f"{field} repeats case_id {case_id}")
        result[case_id] = row
    return result


def _admission_index(packet: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    rows = packet.get("records")
    if not isinstance(rows, list) or not rows:
        raise AdmissionError("admission_packet.records must be a non-empty list")
    result: Dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise AdmissionError("admission packet contains a non-object record")
        case_id = _nonempty(row.get("case_id"), "admission_record.case_id")
        if case_id in result:
            raise AdmissionError(f"admission packet repeats case_id {case_id}")
        result[case_id] = row
    return result


def _assert_review_content_unchanged(
    source: Mapping[str, Any],
    reviewed: Mapping[str, Any],
) -> None:
    comparison = deepcopy(dict(reviewed))
    comparison.pop("independent_review", None)
    cases = comparison.get("cases")
    if not isinstance(cases, list):
        raise AdmissionError("reviewed packet has no cases")
    for case in cases:
        if not isinstance(case, dict):
            raise AdmissionError("reviewed packet contains a non-object case")
        case["reviewer_response"] = blank_reviewer_response()
    if comparison != source:
        raise AdmissionError(
            "reviewed packet changed content outside reviewer_response"
        )


def _validate_case_response(
    case_id: str,
    case: Mapping[str, Any],
) -> tuple[ReviewDecision, list[str], int, int, int]:
    chapters = case.get("chapters")
    response = case.get("reviewer_response")
    if not isinstance(chapters, list) or not chapters:
        raise AdmissionError(f"{case_id}: chapters must be non-empty")
    if not isinstance(response, Mapping):
        raise AdmissionError(f"{case_id}: reviewer_response is missing")
    if response.get("schema_version") != REVIEW_RESPONSE_SCHEMA_VERSION:
        raise AdmissionError(f"{case_id}: wrong reviewer response schema")

    assign = _strict_bool(
        response.get("would_assign_to_a_player_in_this_band"),
        f"{case_id}.would_assign",
    )
    coherent = _strict_bool(
        response.get("whole_game_story_is_coherent"),
        f"{case_id}.coherent",
    )
    repeats = _strict_bool(
        response.get("repeats_primary_principle_as_separate_chapters"),
        f"{case_id}.repeats_primary_principle",
    )
    most_memorable = response.get("most_memorable_chapter_number")
    chapter_move_numbers = {chapter.get("move_number") for chapter in chapters}
    if most_memorable not in chapter_move_numbers:
        raise AdmissionError(
            f"{case_id}: most memorable chapter must name a displayed move"
        )

    verdict_rows = response.get("chapter_verdicts")
    if not isinstance(verdict_rows, list) or len(verdict_rows) != len(chapters):
        raise AdmissionError(
            f"{case_id}: one chapter verdict is required per chapter"
        )
    ordered: Dict[int, Mapping[str, Any]] = {}
    for verdict_row in verdict_rows:
        if not isinstance(verdict_row, Mapping):
            raise AdmissionError(f"{case_id}: chapter verdict is not an object")
        index = verdict_row.get("chapter_index")
        if type(index) is not int or not 0 <= index < len(chapters):
            raise AdmissionError(f"{case_id}: invalid chapter_index")
        if index in ordered:
            raise AdmissionError(f"{case_id}: duplicate chapter_index {index}")
        ordered[index] = verdict_row

    verdicts: list[str] = []
    critical_count = 0
    legal_count = 0
    headline_count = 0
    for index, chapter in enumerate(chapters):
        row = ordered.get(index)
        if row is None:
            raise AdmissionError(f"{case_id}: missing chapter_index {index}")
        if row.get("move_number") != chapter.get("move_number"):
            raise AdmissionError(f"{case_id}: chapter move_number changed")
        if row.get("move_san") != chapter.get("move_san"):
            raise AdmissionError(f"{case_id}: chapter move_san changed")
        verdict = str(row.get("verdict") or "")
        if verdict not in CHAPTER_VERDICTS:
            raise AdmissionError(f"{case_id}: invalid chapter verdict")
        _nonempty(row.get("why"), f"{case_id}.chapter[{index}].why")
        headline_ok = _strict_bool(
            row.get("headline_is_pattern_geometry_or_idea_led"),
            f"{case_id}.chapter[{index}].headline",
        )
        legal_ok = _strict_bool(
            row.get("demonstration_legally_proves_visible_claim"),
            f"{case_id}.chapter[{index}].demonstration",
        )
        critical = _strict_bool(
            row.get("critical_false_claim"),
            f"{case_id}.chapter[{index}].critical_false_claim",
        )
        verdicts.append(verdict)
        headline_count += int(headline_ok)
        legal_count += int(legal_ok)
        critical_count += int(critical)

    admit = bool(
        assign
        and coherent
        and not repeats
        and all(verdict == "correct_and_teachable" for verdict in verdicts)
        and legal_count == len(chapters)
        and headline_count == len(chapters)
        and critical_count == 0
    )
    return (
        ReviewDecision(case_id=case_id, admit=admit, response=response),
        verdicts,
        critical_count,
        legal_count,
        headline_count,
    )


def evaluate_packets(
    *,
    source: Mapping[str, Any],
    reviewed: Mapping[str, Any],
    admission_packet: Mapping[str, Any],
    source_sha256: str,
    reviewed_sha256: str,
    admission_sha256: str,
    expected_source_sha256: str,
) -> Dict[str, Any]:
    """Validate all bindings and recompute the approved v4 quality gates."""
    if not SHA256.fullmatch(expected_source_sha256):
        raise AdmissionError("expected source SHA-256 is malformed")
    if source_sha256 != expected_source_sha256:
        raise AdmissionError("source review packet SHA-256 changed")
    if source.get("schema_version") != REVIEW_PACKET_SCHEMA_VERSION:
        raise AdmissionError("unexpected source review packet schema")
    if source.get("runtime_exposure") != "none":
        raise AdmissionError("source review packet is not frozen off-runtime")
    if (
        (source.get("promotion_boundary") or {}).get(
            "player_visible_community_studies_allowed"
        )
        is not False
    ):
        raise AdmissionError("source packet does not forbid player visibility")
    independent = reviewed.get("independent_review")
    if not isinstance(independent, Mapping):
        raise AdmissionError("reviewed packet lacks independent_review")
    if independent.get("source_packet_sha256") != source_sha256:
        raise AdmissionError("independent review is bound to another packet")
    if independent.get("blinding_holds") is not True:
        raise AdmissionError("independent reviewer did not attest blinding")
    _nonempty(independent.get("reviewer"), "independent_review.reviewer")
    _nonempty(independent.get("method"), "independent_review.method")
    _nonempty(independent.get("reviewed_on"), "independent_review.reviewed_on")
    _assert_review_content_unchanged(source, reviewed)

    if admission_packet.get("schema_version") != ADMISSION_PACKET_SCHEMA_VERSION:
        raise AdmissionError("unexpected sealed admission packet schema")
    if admission_packet.get("runtime_exposure") != "none":
        raise AdmissionError("sealed admission packet is not frozen off-runtime")
    if admission_packet.get("review_packet_schema_version") != REVIEW_PACKET_SCHEMA_VERSION:
        raise AdmissionError("sealed packet targets another review schema")
    source_selection = source.get("selection") or {}
    if (
        admission_packet.get("selection_fingerprint_sha256")
        != source_selection.get("selection_fingerprint_sha256")
    ):
        raise AdmissionError("sealed packet selection fingerprint changed")
    if admission_packet.get("source") != source.get("source"):
        raise AdmissionError("sealed packet source provenance changed")

    source_cases = _case_index(source, "source")
    reviewed_cases = _case_index(reviewed, "reviewed")
    sealed_cases = _admission_index(admission_packet)
    if set(source_cases) != set(reviewed_cases) or set(source_cases) != set(sealed_cases):
        raise AdmissionError("source, reviewed and sealed case sets differ")

    counts = {verdict: 0 for verdict in sorted(CHAPTER_VERDICTS)}
    decisions: list[ReviewDecision] = []
    critical = legal = headlines = chapters_total = coherent = assigned = repeated = 0
    validated_studies: Dict[str, Dict[str, Any]] = {}
    study_ids = set()
    answer_positions: Counter[int] = Counter()
    for case_id in sorted(source_cases):
        decision, verdicts, critical_n, legal_n, headline_n = (
            _validate_case_response(case_id, reviewed_cases[case_id])
        )
        decisions.append(decision)
        response = decision.response
        for verdict in verdicts:
            counts[verdict] += 1
        chapters_total += len(verdicts)
        critical += critical_n
        legal += legal_n
        headlines += headline_n
        coherent += int(response["whole_game_story_is_coherent"])
        assigned += int(response["would_assign_to_a_player_in_this_band"])
        repeated += int(
            response["repeats_primary_principle_as_separate_chapters"]
        )

        sealed = sealed_cases[case_id]
        study = sealed.get("study")
        if not isinstance(study, Mapping):
            raise AdmissionError(f"{case_id}: sealed study is missing")
        normalized = validate_study(study)
        study_id = _nonempty(normalized.get("study_id"), f"{case_id}.study_id")
        if study_id in study_ids:
            raise AdmissionError(f"sealed packet repeats study_id {study_id}")
        study_ids.add(study_id)
        validated_studies[case_id] = normalized
        answer_positions.update(guided_answer_position_indices(normalized))

    denominator = len(decisions)
    teachable_rate = counts["correct_and_teachable"] / chapters_total
    coherent_rate = coherent / denominator
    assignment_rate = assigned / denominator
    failures = []
    if counts["incorrect_or_overclaimed"]:
        failures.append("incorrect_or_overclaimed must be zero")
    if critical:
        failures.append("critical_false_claim must be zero")
    if legal != chapters_total:
        failures.append("every demonstration must legally prove its claim")
    if teachable_rate <= CORRECT_AND_TEACHABLE_FLOOR:
        failures.append("correct_and_teachable rate did not beat 71.8%")
    if headlines != chapters_total:
        failures.append("every headline must be pattern/geometry/idea-led")
    if repeated:
        failures.append("no study may repeat its primary principle")
    if coherent_rate <= COHERENT_STORY_FLOOR:
        failures.append("coherent-story rate did not beat 9.8%")
    if assignment_rate <= ASSIGNMENT_WORTHY_FLOOR:
        failures.append("assignment-worthy rate did not beat 48.8%")
    if len(answer_positions) < 2:
        failures.append(
            "proof-supporting answer occupies one fixed option position"
        )
    if failures:
        raise AdmissionError("; ".join(failures))

    admitted_case_ids = sorted(
        decision.case_id for decision in decisions if decision.admit
    )
    return {
        "schema_version": "community_game_study.review_gate.v2",
        "source_packet_sha256": source_sha256,
        "reviewed_packet_sha256": reviewed_sha256,
        "admission_packet_sha256": admission_sha256,
        "reviewed_on": independent["reviewed_on"],
        "reviewer": independent["reviewer"],
        "cases": denominator,
        "chapters": chapters_total,
        "chapter_verdicts": counts,
        "critical_false_claims": critical,
        "legal_demonstrations": {"numerator": legal, "denominator": chapters_total},
        "pattern_led_headlines": {
            "numerator": headlines,
            "denominator": chapters_total,
        },
        "correct_and_teachable": {
            "numerator": counts["correct_and_teachable"],
            "denominator": chapters_total,
            "rate": round(teachable_rate, 6),
        },
        "coherent_stories": {
            "numerator": coherent,
            "denominator": denominator,
            "rate": round(coherent_rate, 6),
        },
        "assignment_worthy": {
            "numerator": assigned,
            "denominator": denominator,
            "rate": round(assignment_rate, 6),
        },
        "repeated_principle_studies": repeated,
        "proof_answer_positions": {
            str(index): count for index, count in sorted(answer_positions.items())
        },
        "admitted_case_ids": admitted_case_ids,
        "admitted_studies": len(admitted_case_ids),
        "validated_studies": validated_studies,
        "review_responses": {
            decision.case_id: dict(decision.response) for decision in decisions
        },
    }


def admission_documents(gate: Mapping[str, Any]) -> list[Dict[str, Any]]:
    """Build runtime documents; rejected review cases remain Shadow."""
    admitted = set(gate["admitted_case_ids"])
    documents = []
    for case_id, source_study in sorted(gate["validated_studies"].items()):
        study = deepcopy(dict(source_study))
        status = "admitted" if case_id in admitted else "shadow"
        study["status"] = status
        study["independent_admission"] = {
            "schema_version": ADMISSION_RECORD_SCHEMA_VERSION,
            "case_id": case_id,
            "status": status,
            "source_packet_sha256": gate["source_packet_sha256"],
            "reviewed_packet_sha256": gate["reviewed_packet_sha256"],
            "admission_packet_sha256": gate["admission_packet_sha256"],
            "reviewed_on": gate["reviewed_on"],
            "review_response_sha256": _value_sha256(
                gate["review_responses"][case_id]
            ),
        }
        validate_study(study)
        documents.append(study)
    return documents


def _current_state(rows: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    state = []
    for row in rows:
        admission = row.get("independent_admission") or {}
        state.append({
            "study_id": str(row.get("study_id") or ""),
            "status": str(row.get("status") or ""),
            "plan_fingerprint": str(
                (row.get("plan") or {}).get("input_fingerprint") or ""
            ),
            "reviewed_packet_sha256": str(
                admission.get("reviewed_packet_sha256") or ""
            ),
        })
    return sorted(state, key=lambda item: item["study_id"])


def build_apply_plan(
    gate: Mapping[str, Any],
    current_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    documents = admission_documents(gate)
    intended = {row["study_id"]: row for row in documents}
    current = {str(row.get("study_id") or ""): row for row in current_rows}
    for study_id, row in current.items():
        if study_id not in intended:
            continue
        status = str(row.get("status") or "")
        if status in TERMINAL_STATUSES:
            raise AdmissionError(
                f"refusing to overwrite terminal study {study_id} ({status})"
            )
        if status == "admitted" and intended[study_id]["status"] != "admitted":
            raise AdmissionError(
                f"refusing to silently demote admitted study {study_id}"
            )

    write_fingerprints = [
        {
            "study_id": document["study_id"],
            "status": document["status"],
            "document_sha256": _value_sha256(document),
        }
        for document in documents
    ]
    fingerprint_payload = {
        "source_packet_sha256": gate["source_packet_sha256"],
        "reviewed_packet_sha256": gate["reviewed_packet_sha256"],
        "admission_packet_sha256": gate["admission_packet_sha256"],
        "current_state": _current_state(current_rows),
        "writes": write_fingerprints,
    }
    return {
        "schema_version": "community_game_study.admission_apply_plan.v1",
        "mode": "dry_run",
        "plan_fingerprint": _value_sha256(fingerprint_payload),
        "scope": {
            "records": len(documents),
            "admitted": sum(
                document["status"] == "admitted" for document in documents
            ),
            "shadow": sum(
                document["status"] == "shadow" for document in documents
            ),
        },
        "quality_gate": {
            key: gate[key]
            for key in (
                "cases",
                "chapters",
                "chapter_verdicts",
                "critical_false_claims",
                "legal_demonstrations",
                "pattern_led_headlines",
                "correct_and_teachable",
                "coherent_stories",
                "assignment_worthy",
                "repeated_principle_studies",
                "proof_answer_positions",
            )
        },
        "documents": documents,
    }


async def _current_rows(db, study_ids: Sequence[str]) -> list[Dict[str, Any]]:
    if not study_ids:
        return []
    return await db[COLLECTION].find(
        {"study_id": {"$in": list(study_ids)}},
        {
            "_id": 0,
            "study_id": 1,
            "status": 1,
            "plan.input_fingerprint": 1,
            "independent_admission.reviewed_packet_sha256": 1,
        },
    ).to_list(length=None)


async def run(args: argparse.Namespace) -> Dict[str, Any]:
    source_path = args.source_review_packet.resolve()
    reviewed_path = args.reviewed_packet.resolve()
    admission_path = args.admission_packet.resolve()
    source = _read_json(source_path)
    reviewed = _read_json(reviewed_path)
    sealed = _read_json(admission_path)
    gate = evaluate_packets(
        source=source,
        reviewed=reviewed,
        admission_packet=sealed,
        source_sha256=_file_sha256(source_path),
        reviewed_sha256=_file_sha256(reviewed_path),
        admission_sha256=_file_sha256(admission_path),
        expected_source_sha256=args.expected_source_sha256,
    )

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise AdmissionError("MONGO_URL and DB_NAME must be set in the environment")
    client = AsyncIOMotorClient(mongo_url)
    try:
        db = client[db_name]
        documents = admission_documents(gate)
        rows = await _current_rows(
            db, [document["study_id"] for document in documents]
        )
        plan = build_apply_plan(gate, rows)
        public = deepcopy(plan)
        public.pop("documents", None)
        if not args.apply:
            return public
        if args.confirm != CONFIRMATION:
            raise AdmissionError(f"--confirm must equal {CONFIRMATION}")
        if args.confirm_plan != plan["plan_fingerprint"]:
            raise AdmissionError(
                "--confirm-plan does not match the current dry-run plan"
            )
        now = datetime.now(timezone.utc)
        for document in plan["documents"]:
            persisted = deepcopy(document)
            persisted["independent_admission"]["applied_at"] = now
            await db[COLLECTION].replace_one(
                {"study_id": persisted["study_id"]},
                persisted,
                upsert=True,
            )
        public["mode"] = "applied"
        public["applied_at"] = now.isoformat()
        return public
    finally:
        client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-review-packet", type=Path, required=True)
    parser.add_argument("--reviewed-packet", type=Path, required=True)
    parser.add_argument("--admission-packet", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--confirm-plan")
    return parser.parse_args()


def main() -> None:
    try:
        report = asyncio.run(run(parse_args()))
    except AdmissionError as exc:
        raise SystemExit(f"admission refused: {exc}") from exc
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

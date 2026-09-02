"""Typed, surface-neutral teaching reasons for one submitted chess move.

The contract owns shape, validation, redaction and grading. Chess facts remain
in their promoted detector/fact providers; UI surfaces consume only public
questions and post-answer summaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple


REASON_BUNDLE_SCHEMA_VERSION = "teaching_reason_bundle.v1"


class ReasonContractViolation(ValueError):
    pass


def _text(value: Any, field_name: str) -> str:
    rendered = str(value or "").strip()
    if not rendered:
        raise ReasonContractViolation(f"{field_name} must be non-empty")
    return rendered


@dataclass(frozen=True)
class ReasonChoice:
    choice_id: str
    label: str

    def __post_init__(self) -> None:
        _text(self.choice_id, "choice_id")
        _text(self.label, "choice.label")

    def public_dict(self) -> Dict[str, str]:
        return {"id": self.choice_id, "label": self.label}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReasonChoice":
        return cls(
            choice_id=str(payload.get("id") or payload.get("choice_id") or ""),
            label=str(payload.get("label") or ""),
        )


@dataclass(frozen=True)
class ReasonComponent:
    question_id: str
    kind: str
    prompt: str
    choices: Tuple[ReasonChoice, ...]
    accepted_choice_ids: Tuple[str, ...]
    facts: Mapping[str, Any] = field(default_factory=dict)
    success_text: str = ""
    correction_text: str = ""

    def __post_init__(self) -> None:
        _text(self.question_id, "question_id")
        _text(self.kind, "component.kind")
        _text(self.prompt, "component.prompt")
        _text(self.success_text, "component.success_text")
        _text(self.correction_text, "component.correction_text")
        if len(self.choices) < 2:
            raise ReasonContractViolation("a reason component needs at least two choices")
        choice_ids = [choice.choice_id for choice in self.choices]
        if len(set(choice_ids)) != len(choice_ids):
            raise ReasonContractViolation("reason choice ids must be unique")
        accepted = set(self.accepted_choice_ids)
        if not accepted or not accepted.issubset(choice_ids):
            raise ReasonContractViolation("accepted choices must reference public choices")

    def public_question(self, *, index: int, total: int) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "prompt": self.prompt,
            "choices": [choice.public_dict() for choice in self.choices],
            "progress": {"current": index + 1, "total": total},
        }

    def grade(self, selected_choice_id: str) -> Dict[str, Any]:
        selected = str(selected_choice_id or "")
        if selected not in {choice.choice_id for choice in self.choices}:
            raise ReasonContractViolation("selected choice is not in this question")
        correct = selected in set(self.accepted_choice_ids)
        return {
            "question_id": self.question_id,
            "kind": self.kind,
            "selected_choice_id": selected,
            "correct": correct,
            "feedback": self.success_text if correct else self.correction_text,
        }

    def private_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "kind": self.kind,
            "prompt": self.prompt,
            "choices": [choice.public_dict() for choice in self.choices],
            "accepted_choice_ids": list(self.accepted_choice_ids),
            "facts": dict(self.facts),
            "success_text": self.success_text,
            "correction_text": self.correction_text,
        }

    @classmethod
    def from_private_dict(cls, payload: Mapping[str, Any]) -> "ReasonComponent":
        return cls(
            question_id=str(payload.get("question_id") or ""),
            kind=str(payload.get("kind") or ""),
            prompt=str(payload.get("prompt") or ""),
            choices=tuple(
                ReasonChoice.from_dict(item) for item in (payload.get("choices") or [])
            ),
            accepted_choice_ids=tuple(payload.get("accepted_choice_ids") or ()),
            facts=dict(payload.get("facts") or {}),
            success_text=str(payload.get("success_text") or ""),
            correction_text=str(payload.get("correction_text") or ""),
        )


@dataclass(frozen=True)
class ReasonProof:
    authority: str
    quality_id: str
    detector_version: str
    verifier_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "authority",
            "quality_id",
            "detector_version",
            "verifier_version",
            "fingerprint",
        ):
            _text(getattr(self, name), f"proof.{name}")

    def private_dict(self) -> Dict[str, str]:
        return {
            "authority": self.authority,
            "quality_id": self.quality_id,
            "detector_version": self.detector_version,
            "verifier_version": self.verifier_version,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReasonProof":
        return cls(**{
            key: str(payload.get(key) or "")
            for key in (
                "authority",
                "quality_id",
                "detector_version",
                "verifier_version",
                "fingerprint",
            )
        })


@dataclass(frozen=True)
class TeachingReasonBundle:
    semantic_version: str
    position_fingerprint: str
    move_uci: str
    move_san: str
    target_result: str
    safety_kind: str
    components: Tuple[ReasonComponent, ...]
    proof: ReasonProof
    schema_version: str = REASON_BUNDLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "semantic_version",
            "position_fingerprint",
            "move_uci",
            "move_san",
            "target_result",
            "safety_kind",
        ):
            _text(getattr(self, name), name)
        if self.target_result not in {"pass", "fail", "unmeasured"}:
            raise ReasonContractViolation("unsupported target result")
        question_ids = [component.question_id for component in self.components]
        if len(question_ids) != len(set(question_ids)):
            raise ReasonContractViolation("reason question ids must be unique")

    def question(self, index: int) -> Dict[str, Any] | None:
        if index < 0 or index >= len(self.components):
            return None
        return self.components[index].public_question(
            index=index,
            total=len(self.components),
        )

    def grade_component(
        self,
        *,
        index: int,
        question_id: str,
        selected_choice_id: str,
    ) -> Dict[str, Any]:
        if index < 0 or index >= len(self.components):
            raise ReasonContractViolation("reason component is already complete")
        component = self.components[index]
        if component.question_id != str(question_id or ""):
            raise ReasonContractViolation("reason response does not match current question")
        return component.grade(selected_choice_id)

    def private_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "semantic_version": self.semantic_version,
            "position_fingerprint": self.position_fingerprint,
            "move_uci": self.move_uci,
            "move_san": self.move_san,
            "target_result": self.target_result,
            "safety_kind": self.safety_kind,
            "components": [component.private_dict() for component in self.components],
            "proof": self.proof.private_dict(),
        }

    @classmethod
    def from_private_dict(cls, payload: Mapping[str, Any]) -> "TeachingReasonBundle":
        if payload.get("schema_version") != REASON_BUNDLE_SCHEMA_VERSION:
            raise ReasonContractViolation("unsupported reason bundle schema")
        return cls(
            schema_version=str(payload.get("schema_version") or ""),
            semantic_version=str(payload.get("semantic_version") or ""),
            position_fingerprint=str(payload.get("position_fingerprint") or ""),
            move_uci=str(payload.get("move_uci") or ""),
            move_san=str(payload.get("move_san") or ""),
            target_result=str(payload.get("target_result") or ""),
            safety_kind=str(payload.get("safety_kind") or ""),
            components=tuple(
                ReasonComponent.from_private_dict(item)
                for item in (payload.get("components") or [])
            ),
            proof=ReasonProof.from_dict(payload.get("proof") or {}),
        )


__all__ = [
    "REASON_BUNDLE_SCHEMA_VERSION",
    "ReasonChoice",
    "ReasonComponent",
    "ReasonContractViolation",
    "ReasonProof",
    "TeachingReasonBundle",
]

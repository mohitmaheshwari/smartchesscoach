"""Generated, read-only concept capability contracts.

This module composes existing owners.  It does not own chess content,
detector rules, authorization decisions, lesson answers, or mastery state.
Known migration gaps remain explicit so a new mapping cannot become true merely
because a caller guessed an identifier.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from types import MappingProxyType
from typing import Dict, Iterable, Mapping, Optional, Tuple

from services.concept_detectors.registry import all_detectors
from services.curriculum_content_validator import get_publishable_content_ids
from services.detector_quality import (
    QualityGrade,
    QualitySurface,
    concept_quality_id,
    get_authorization,
    is_authorized,
)
from services.endgame_theory_service import resolve_content_ref
from services.engine2_skill_builder import (
    get_skill_tree_snapshot,
    lesson_skill_aliases,
)
from services.personalized_lesson_adapter import (
    ADAPTER_SCHEMA_VERSION,
    supports_personalized_lesson_identity,
)


SCHEMA_VERSION = "concept_contract_index.v1"
FEATURE_FLAG = "COMPLETE_COACHING_SYSTEM_V1_ENABLED"
LESSON_GRADER_REF = "services.personalized_lesson_adapter.grade_personalized_move"
TRANSFER_CONTRACT_REF = "services.personal_curriculum.LessonResult.v2"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class ConceptCapability(str, Enum):
    CURRICULUM = "curriculum"
    CAPTION = "caption"
    PLAN = "plan"
    MASTERY = "mastery"
    RESEARCH_ONLY = "research_only"
    DISABLED = "disabled"


class BindingStatus(str, Enum):
    BOUND = "bound"
    CONTENT_ONLY = "content_only"
    UNMAPPED = "unmapped"


class ContractIndexViolation(ValueError):
    """Raised when composed owners disagree or overstate authority."""


@dataclass(frozen=True)
class ContentReference:
    kind: str
    content_id: str
    source_ref: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value.strip() for value in (
            self.kind, self.content_id, self.source_ref
        )):
            raise ContractIndexViolation("content references require non-empty strings")


@dataclass(frozen=True)
class DetectorBinding:
    detector_id: str
    detector_ref: str
    quality_id: str
    quality_grade: str
    target_concept_ids: Tuple[str, ...]
    content_ids: Tuple[str, ...]
    allowed_surfaces: Tuple[str, ...]
    opportunity_contract_version: Optional[str]
    evidence_ref: str
    limitations: Tuple[str, ...]
    status: BindingStatus

    def __post_init__(self) -> None:
        if not self.detector_id or not self.detector_ref or not self.quality_id:
            raise ContractIndexViolation("detector bindings require stable identities")
        if self.quality_grade != get_authorization(self.quality_id).grade.value:
            raise ContractIndexViolation(
                f"{self.quality_id} carries a stale authorization grade"
            )
        if self.status == BindingStatus.BOUND and not self.target_concept_ids:
            raise ContractIndexViolation("bound detectors require a target concept")
        if self.status == BindingStatus.CONTENT_ONLY and not self.content_ids:
            raise ContractIndexViolation("content-only detectors require content refs")
        if self.status == BindingStatus.UNMAPPED and self.target_concept_ids:
            raise ContractIndexViolation("unmapped detectors cannot carry targets")
        for surface in self.allowed_surfaces:
            if not is_authorized(self.quality_id, QualitySurface(surface)):
                raise ContractIndexViolation(
                    f"{self.quality_id} is not authorized for {surface}"
                )


@dataclass(frozen=True)
class ConceptContract:
    concept_id: str
    aliases: Tuple[str, ...]
    domain: str
    curriculum_stage: int
    prerequisites: Tuple[str, ...]
    content: ContentReference
    detector_ids: Tuple[str, ...]
    detector_quality_ids: Tuple[str, ...]
    allowed_surfaces: Tuple[str, ...]
    capabilities: Tuple[ConceptCapability, ...]
    lesson_capabilities: Tuple[str, ...]
    grader_ref: Optional[str]
    grader_contract_version: Optional[str]
    opportunity_contract_refs: Tuple[str, ...]
    evidence_limitations: Tuple[str, ...]
    transfer_contract_ref: str = TRANSFER_CONTRACT_REF

    def __post_init__(self) -> None:
        if not self.concept_id or not self.domain or not self.transfer_contract_ref:
            raise ContractIndexViolation("concept contracts require stable identities")
        if len(self.detector_ids) != len(self.detector_quality_ids):
            raise ContractIndexViolation(
                f"{self.concept_id} has incomplete detector quality bindings"
            )
        if self.lesson_capabilities and not (
            self.grader_ref and self.grader_contract_version
        ):
            raise ContractIndexViolation(
                f"{self.concept_id} exposes a lesson without a versioned grader"
            )
        for surface in self.allowed_surfaces:
            if not any(
                is_authorized(quality_id, QualitySurface(surface))
                for quality_id in self.detector_quality_ids
            ):
                raise ContractIndexViolation(
                    f"{self.concept_id} overstates authority for {surface}"
                )
        capability_surface = {
            ConceptCapability.CAPTION: QualitySurface.CAPTION.value,
            ConceptCapability.PLAN: QualitySurface.PLAN.value,
            ConceptCapability.MASTERY: QualitySurface.MASTERY.value,
        }
        for capability, surface in capability_surface.items():
            if capability in self.capabilities and surface not in self.allowed_surfaces:
                raise ContractIndexViolation(
                    f"{self.concept_id} has {capability.value} without {surface} authority"
                )
        if (
            ConceptCapability.MASTERY in self.capabilities
            and not self.opportunity_contract_refs
        ):
            raise ContractIndexViolation(
                f"{self.concept_id} has mastery without an opportunity contract"
            )
        alias_keys = [_alias_key(value) for value in self.aliases]
        if "" in alias_keys or len(alias_keys) != len(set(alias_keys)):
            raise ContractIndexViolation(
                f"{self.concept_id} has empty or duplicate aliases"
            )


def complete_coaching_system_enabled(
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    source = os.environ if env is None else env
    return str(source.get(FEATURE_FLAG, "false")).strip().lower() in _TRUE_VALUES


def _alias_key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _workspace_kind(kind: object) -> str:
    return "endgame" if str(kind) == "mate_pattern" else str(kind)


def exact_endgame_content_id(detector_id: str) -> Optional[str]:
    prefix = "endgame_curriculum__"
    if not detector_id.startswith(prefix):
        return None
    parts = detector_id[len(prefix):].split("__", 1)
    return "/".join(parts) if len(parts) == 2 else None


def canonical_skill_nodes() -> Dict[str, Dict[str, object]]:
    """Return a detached view of the dynamically composed canonical tree."""
    return {
        str(skill_id): dict(node)
        for skill_id, node in (get_skill_tree_snapshot().get("skills") or {}).items()
        if isinstance(node, Mapping)
    }


def target_concept_ids_for_detector(
    detector_id: str,
    skills: Optional[Mapping[str, Mapping[str, object]]] = None,
) -> Tuple[str, ...]:
    """Resolve detector reach without fuzzy name matching."""
    nodes = skills or canonical_skill_nodes()
    if detector_id == "opening_play":
        return tuple(sorted(
            skill_id for skill_id, node in nodes.items()
            if node.get("kind") == "opening"
        ))
    if detector_id == "trap_detection":
        return tuple(sorted(
            skill_id for skill_id, node in nodes.items()
            if node.get("kind") == "trap_set"
        ))
    lesson_id = exact_endgame_content_id(detector_id)
    if lesson_id:
        matches = []
        for skill_id, node in nodes.items():
            if node.get("kind") not in {"endgame", "mate_pattern"}:
                continue
            resolved = resolve_content_ref(str(node.get("content_ref") or ""))
            if resolved and resolved.get("lesson_id") == lesson_id:
                matches.append(skill_id)
        return tuple(sorted(matches))
    return (detector_id,) if detector_id in nodes else ()


def content_ids_for_detector(
    detector_id: str,
    target_concept_ids: Iterable[str],
    skills: Optional[Mapping[str, Mapping[str, object]]] = None,
) -> Tuple[str, ...]:
    """Resolve canonical content references reached by one detector."""
    nodes = skills or canonical_skill_nodes()
    if detector_id in {"opening_play", "opening_sound_deviation"}:
        return tuple(sorted(get_publishable_content_ids("openings")))
    if detector_id == "opening_plan_play":
        return tuple(sorted(get_publishable_content_ids("opening_ideas")))
    if detector_id == "trap_detection":
        return tuple(sorted(get_publishable_content_ids("traps")))
    exact_endgame = exact_endgame_content_id(detector_id)
    if exact_endgame:
        return (exact_endgame,)
    return tuple(sorted({
        str(nodes[skill_id].get("content_ref") or "")
        for skill_id in target_concept_ids
        if skill_id in nodes and nodes[skill_id].get("content_ref")
    }))


def _binding_status(
    detector_id: str,
    targets: Tuple[str, ...],
    content_ids: Tuple[str, ...],
) -> BindingStatus:
    if targets:
        return BindingStatus.BOUND
    if content_ids and (
        detector_id == "opening_plan_play"
        or exact_endgame_content_id(detector_id) is not None
    ):
        return BindingStatus.CONTENT_ONLY
    return BindingStatus.UNMAPPED


def _allowed_surfaces(
    quality_id: str,
    opportunity_contract_version: Optional[str],
) -> Tuple[str, ...]:
    # DIAGNOSTIC is deliberately absent: in the v1 architecture it means
    # internal research, not permission to publish a persistent diagnosis.
    return tuple(
        surface.value
        for surface in (
            QualitySurface.CAPTION,
            QualitySurface.PLAN,
            QualitySurface.PROMPT,
        )
        if is_authorized(quality_id, surface)
    ) + (
        (QualitySurface.MASTERY.value,)
        if opportunity_contract_version
        and is_authorized(quality_id, QualitySurface.MASTERY)
        else ()
    )


def _build_detector_bindings(
    skills: Mapping[str, Mapping[str, object]],
) -> Dict[str, DetectorBinding]:
    bindings: Dict[str, DetectorBinding] = {}
    for detector_id, detector in sorted(all_detectors().items()):
        targets = target_concept_ids_for_detector(detector_id, skills)
        content_ids = content_ids_for_detector(detector_id, targets, skills)
        quality_id = concept_quality_id(detector_id)
        authorization = get_authorization(quality_id)
        opportunity_contract_version = None
        bindings[detector_id] = DetectorBinding(
            detector_id=detector_id,
            detector_ref=f"{detector.__module__}.{detector.__qualname__}",
            quality_id=quality_id,
            quality_grade=authorization.grade.value,
            target_concept_ids=targets,
            content_ids=content_ids,
            allowed_surfaces=_allowed_surfaces(
                quality_id, opportunity_contract_version
            ),
            opportunity_contract_version=opportunity_contract_version,
            evidence_ref=authorization.evidence_ref,
            limitations=tuple(authorization.limitations),
            status=_binding_status(detector_id, targets, content_ids),
        )
    return bindings


@dataclass(frozen=True)
class ConceptContractIndex:
    contracts: Mapping[str, ConceptContract]
    detector_bindings: Mapping[str, DetectorBinding]
    alias_index: Mapping[str, str]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contracts", MappingProxyType(dict(self.contracts))
        )
        object.__setattr__(
            self,
            "detector_bindings",
            MappingProxyType(dict(self.detector_bindings)),
        )
        object.__setattr__(
            self, "alias_index", MappingProxyType(dict(self.alias_index))
        )

    @property
    def unmapped_detector_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(
            detector_id
            for detector_id, binding in self.detector_bindings.items()
            if binding.status == BindingStatus.UNMAPPED
        ))

    def resolve(self, alias: str, *, domain: str) -> Optional[ConceptContract]:
        concept_id = self.alias_index.get(f"{domain}:{_alias_key(alias)}")
        return self.contracts.get(concept_id) if concept_id else None

    def to_document(self) -> Dict[str, object]:
        """Serialize references and capabilities only; never copied content."""
        return {
            "schema_version": self.schema_version,
            "contracts": {
                concept_id: {
                    "aliases": list(contract.aliases),
                    "domain": contract.domain,
                    "curriculum_stage": contract.curriculum_stage,
                    "prerequisites": list(contract.prerequisites),
                    "content_ref": {
                        "kind": contract.content.kind,
                        "content_id": contract.content.content_id,
                        "source_ref": contract.content.source_ref,
                    },
                    "detector_ids": list(contract.detector_ids),
                    "detector_quality_ids": list(contract.detector_quality_ids),
                    "allowed_surfaces": list(contract.allowed_surfaces),
                    "capabilities": [item.value for item in contract.capabilities],
                    "lesson_capabilities": list(contract.lesson_capabilities),
                    "grader_ref": contract.grader_ref,
                    "grader_contract_version": contract.grader_contract_version,
                    "opportunity_contract_refs": list(
                        contract.opportunity_contract_refs
                    ),
                    "transfer_contract_ref": contract.transfer_contract_ref,
                    "evidence_limitations": list(contract.evidence_limitations),
                }
                for concept_id, contract in self.contracts.items()
            },
            "detector_bindings": {
                detector_id: {
                    "detector_ref": binding.detector_ref,
                    "quality_id": binding.quality_id,
                    "quality_grade": binding.quality_grade,
                    "target_concept_ids": list(binding.target_concept_ids),
                    "content_ids": list(binding.content_ids),
                    "allowed_surfaces": list(binding.allowed_surfaces),
                    "opportunity_contract_version": (
                        binding.opportunity_contract_version
                    ),
                    "evidence_ref": binding.evidence_ref,
                    "limitations": list(binding.limitations),
                    "status": binding.status.value,
                }
                for detector_id, binding in self.detector_bindings.items()
            },
            "unmapped_detector_ids": list(self.unmapped_detector_ids),
        }

    def assert_valid(
        self,
        *,
        allowed_unmapped_detector_ids: Iterable[str] = (),
    ) -> None:
        known = set(allowed_unmapped_detector_ids)
        unexpected = set(self.unmapped_detector_ids) - known
        if unexpected:
            raise ContractIndexViolation(
                "unmapped detector ids: " + ", ".join(sorted(unexpected))
            )
        dangling_allowed = known - set(self.unmapped_detector_ids)
        if dangling_allowed:
            raise ContractIndexViolation(
                "stale allowed-unmapped ids: " + ", ".join(sorted(dangling_allowed))
            )
        for concept_id, contract in self.contracts.items():
            missing = set(contract.prerequisites) - set(self.contracts)
            if missing:
                raise ContractIndexViolation(
                    f"{concept_id} has dangling prerequisites: {sorted(missing)}"
                )
            for detector_id in contract.detector_ids:
                binding = self.detector_bindings.get(detector_id)
                if binding is None or concept_id not in binding.target_concept_ids:
                    raise ContractIndexViolation(
                        f"{concept_id} has dangling detector binding {detector_id}"
                    )


def _capabilities(
    bindings: Iterable[DetectorBinding],
) -> Tuple[ConceptCapability, ...]:
    rows = tuple(bindings)
    result = [ConceptCapability.CURRICULUM]
    surfaces = {
        surface for row in rows for surface in row.allowed_surfaces
    }
    if QualitySurface.CAPTION.value in surfaces:
        result.append(ConceptCapability.CAPTION)
    if QualitySurface.PLAN.value in surfaces:
        result.append(ConceptCapability.PLAN)
    if QualitySurface.MASTERY.value in surfaces:
        result.append(ConceptCapability.MASTERY)
    if rows and not surfaces:
        if all(row.quality_grade == QualityGrade.DISABLED.value for row in rows):
            result.append(ConceptCapability.DISABLED)
        else:
            result.append(ConceptCapability.RESEARCH_ONLY)
    return tuple(result)


def build_concept_contract_index() -> ConceptContractIndex:
    """Compose the current index without mutating any canonical owner."""
    tree = get_skill_tree_snapshot()
    skills = canonical_skill_nodes()
    bindings = _build_detector_bindings(skills)
    by_concept: Dict[str, list[DetectorBinding]] = {
        concept_id: [] for concept_id in skills
    }
    for binding in bindings.values():
        for concept_id in binding.target_concept_ids:
            by_concept[concept_id].append(binding)

    content_sources = (tree.get("_meta") or {}).get("content_sources") or {}
    contracts: Dict[str, ConceptContract] = {}
    aliases: Dict[str, str] = {}
    for concept_id, node in sorted(skills.items()):
        authored_kind = str(node.get("kind") or "concept")
        kind = _workspace_kind(authored_kind)
        content_id = str(node.get("content_ref") or concept_id)
        if kind == "endgame":
            resolved = resolve_content_ref(content_id)
            if resolved:
                content_id = str(resolved.get("lesson_id") or content_id)
        source_ref = str(
            content_sources.get(authored_kind)
            or content_sources.get(kind)
            or "backend/data/coaching/skill_tree.json"
        )
        lesson_available = supports_personalized_lesson_identity(kind, content_id)
        rows = tuple(sorted(by_concept[concept_id], key=lambda item: item.detector_id))
        raw_aliases = lesson_skill_aliases(
            kind, content_id, requested_skill_id=concept_id
        )
        unique_aliases = []
        for raw in raw_aliases:
            key = _alias_key(raw)
            if key and key not in {_alias_key(item) for item in unique_aliases}:
                unique_aliases.append(str(raw))
        contract = ConceptContract(
            concept_id=concept_id,
            aliases=tuple(unique_aliases),
            domain=kind,
            curriculum_stage=int(node.get("tier") or 0),
            prerequisites=tuple(node.get("prerequisites") or ()),
            content=ContentReference(kind, content_id, source_ref),
            detector_ids=tuple(row.detector_id for row in rows),
            detector_quality_ids=tuple(row.quality_id for row in rows),
            allowed_surfaces=tuple(sorted({
                surface for row in rows for surface in row.allowed_surfaces
            })),
            capabilities=_capabilities(rows),
            lesson_capabilities=("teach",) if lesson_available else (),
            grader_ref=LESSON_GRADER_REF if lesson_available else None,
            grader_contract_version=(
                ADAPTER_SCHEMA_VERSION if lesson_available else None
            ),
            opportunity_contract_refs=tuple(
                str(row.opportunity_contract_version)
                for row in rows
                if row.opportunity_contract_version
            ),
            evidence_limitations=tuple(sorted({
                limitation for row in rows for limitation in row.limitations
            })),
        )
        contracts[concept_id] = contract
        for alias in contract.aliases:
            alias_key = f"{contract.domain}:{_alias_key(alias)}"
            owner = aliases.get(alias_key)
            if owner and owner != concept_id:
                raise ContractIndexViolation(
                    f"duplicate alias {alias!r} for {owner} and {concept_id}"
                )
            aliases[alias_key] = concept_id

    return ConceptContractIndex(contracts, bindings, aliases)

"""Versioned contracts for the offline experiment; no shipping policy defaults."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Literal

VERSION = "reasoning.offline.v1"
Status = Literal["supported_consequence", "supported_mechanism", "incomplete_hypothesis", "insufficient_evidence"]


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class ReasoningConfig:
    engine_path: str
    nodes: int
    stability_nodes: int
    max_queries: int
    max_total_nodes: int
    rank_width: int
    root_cap: int
    reply_width: int
    max_plies: int
    max_hypotheses: int
    max_expanded_nodes: int
    hash_mb: int
    equivalence_cp: int

    def __post_init__(self):
        if not isinstance(self.engine_path, str) or not self.engine_path:
            raise ValueError("engine_path is required")
        for key, value in asdict(self).items():
            if key == "engine_path":
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{key} must be a positive integer")
        if self.stability_nodes < self.nodes:
            raise ValueError("stability_nodes must not be smaller than nodes")
        if self.root_cap < 2:
            raise ValueError("root_cap must allow the played move and an alternative")
        if self.max_total_nodes < self.nodes:
            raise ValueError("max_total_nodes must fund the mandatory played query")


@dataclass(frozen=True)
class Score:
    kind: Literal["cp", "mate"]
    value: int
    pov: str


@dataclass
class SearchRecord:
    id: str
    purpose: str
    fen: str
    root_moves: list[str]
    requested_nodes: int
    width: int
    status: str
    lines: list[dict] = field(default_factory=list)
    final_bounds: list[dict] = field(default_factory=list)
    actual_nodes: int = 0
    stop_reason: str = ""
    runtime: dict = field(default_factory=dict)
    requested_depth: int | None = None

    def document(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Proposition:
    id: str
    subject: str
    relation: str
    object: str
    timeline_id: str
    ply: int
    actor: str
    evidence_ids: tuple[str, ...]
    data: dict = field(default_factory=dict)
    evidence_class: str = "exact_board_fact"
    quantifier: str = "at_this_node"
    polarity: bool = True


@dataclass
class Hypothesis:
    id: str
    operation: str
    root_uci: str
    objective: dict
    proposition_ids: list[str]
    dependencies: list[dict]
    status: str = "incomplete_hypothesis"
    search_ids: list[str] = field(default_factory=list)
    counterexamples: list[dict] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    wording_strength: str = "demonstrated_continuation"


def proposal(operation: str, root_uci: str, objective: dict, propositions, dependencies=()) -> Hypothesis:
    ids = [p.id for p in propositions]
    return Hypothesis(fingerprint([operation, root_uci, objective, ids]), operation, root_uci,
                      objective, ids, list(dependencies))

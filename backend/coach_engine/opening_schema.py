"""Structured opening schema and validation helpers for the live coach."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import chess


def normalize_san(move: str) -> str:
    return (
        (move or "")
        .replace("+", "")
        .replace("#", "")
        .replace("!", "")
        .replace("?", "")
        .strip()
        .lower()
    )


@dataclass
class RatingTeachingLayer:
    message: str
    focus: str
    next_step: Optional[str] = None


@dataclass
class OpeningTrapSchema:
    move: Optional[str]
    warning: str
    question: Optional[str] = None
    name: Optional[str] = None
    after_move: Optional[int] = None


@dataclass
class DeviationRuleSchema:
    expected_move: str
    response_message: str
    new_plan_for_white: List[str] = field(default_factory=list)
    new_plan_for_black: List[str] = field(default_factory=list)


@dataclass
class OpeningNodeSchema:
    move_index: int
    move_san: str
    side_played: str
    side_to_move_next: str
    teaching: Dict[str, RatingTeachingLayer]
    plans_for_white: List[str] = field(default_factory=list)
    plans_for_black: List[str] = field(default_factory=list)
    next_expected_moves: List[str] = field(default_factory=list)
    trap_warning: Optional[str] = None
    idea: Optional[str] = None


@dataclass
class OpeningVariationSchema:
    variation_id: str
    variation_name: str
    trigger_moves: List[str]
    full_line: List[str]
    plans_for_white: List[str] = field(default_factory=list)
    plans_for_black: List[str] = field(default_factory=list)
    key_plans: List[str] = field(default_factory=list)
    nodes: List[OpeningNodeSchema] = field(default_factory=list)
    traps: List[OpeningTrapSchema] = field(default_factory=list)
    deviation_rules: List[DeviationRuleSchema] = field(default_factory=list)
    position_tags: List[str] = field(default_factory=list)


@dataclass
class OpeningCoverageSchema:
    variation_count: int
    node_count: int
    trap_count: int
    deviation_rule_count: int
    min_full_line_ply_depth: int
    max_full_line_ply_depth: int
    has_white_plans: bool
    has_black_plans: bool
    has_rating_layers: bool


@dataclass
class OpeningFamilySchema:
    family_id: str
    family_name: str
    eco_codes: List[str]
    starting_moves: List[str]
    family_concepts: Dict[str, List[str]]
    variations: List[OpeningVariationSchema] = field(default_factory=list)
    coverage: Optional[OpeningCoverageSchema] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _build_rating_layers(
    move_san: str,
    teaching: str,
    idea: str,
    next_move: Optional[str],
) -> Dict[str, RatingTeachingLayer]:
    focus = idea or f"Understand why {move_san} matters here"
    next_step = f"Compare your next decision with {next_move}." if next_move else None
    beginner_message = teaching or f"{move_san} is an important move in this opening."
    club_message = teaching or f"{move_san} fits the main plan in this variation."
    advanced_message = teaching or f"{move_san} preserves the variation's core positional idea."

    return {
        "beginner": RatingTeachingLayer(
            message=beginner_message,
            focus=focus,
            next_step=next_step,
        ),
        "club": RatingTeachingLayer(
            message=club_message,
            focus=focus,
            next_step=next_step,
        ),
        "advanced": RatingTeachingLayer(
            message=advanced_message,
            focus=focus,
            next_step=next_step,
        ),
    }


def _infer_side_played(move_index: int) -> str:
    return "white" if move_index % 2 == 0 else "black"


def _build_nodes(variation_data: Dict[str, Any]) -> List[OpeningNodeSchema]:
    full_line = variation_data.get("full_line", []) or []
    move_teaching = variation_data.get("move_teaching", {}) or {}
    explicit_nodes = variation_data.get("teaching_nodes", []) or []
    plans_for_white = variation_data.get("plans_for_white", []) or []
    plans_for_black = variation_data.get("plans_for_black", []) or []
    traps = variation_data.get("traps", []) or []
    nodes: List[OpeningNodeSchema] = []

    if explicit_nodes:
        for node_data in explicit_nodes:
            move_index = node_data.get("move_index")
            if move_index is None or move_index >= len(full_line):
                continue

            move_san = node_data.get("move_san", full_line[move_index])
            next_expected = full_line[move_index + 1] if move_index + 1 < len(full_line) else None
            matching_trap = None
            for trap in traps:
                if normalize_san(trap.get("move", "")) == normalize_san(move_san):
                    matching_trap = trap.get("warning")
                    break

            side_played = _infer_side_played(move_index)
            side_to_move_next = "black" if side_played == "white" else "white"
            nodes.append(
                OpeningNodeSchema(
                    move_index=move_index,
                    move_san=move_san,
                    side_played=side_played,
                    side_to_move_next=side_to_move_next,
                    teaching=_build_rating_layers(
                        move_san=move_san,
                        teaching=node_data.get("teach", ""),
                        idea=node_data.get("idea", ""),
                        next_move=next_expected,
                    ),
                    plans_for_white=plans_for_white,
                    plans_for_black=plans_for_black,
                    next_expected_moves=[next_expected] if next_expected else [],
                    trap_warning=matching_trap,
                    idea=node_data.get("idea"),
                )
            )

        return nodes

    for move_index, move_san in enumerate(full_line):
        normalized_move = normalize_san(move_san)
        teaching_data = None
        for key, value in move_teaching.items():
            if normalize_san(key) == normalized_move:
                teaching_data = value
                break

        if not teaching_data:
            continue

        next_expected = full_line[move_index + 1] if move_index + 1 < len(full_line) else None
        matching_trap = None
        for trap in traps:
            if normalize_san(trap.get("move", "")) == normalized_move:
                matching_trap = trap.get("warning")
                break

        side_played = _infer_side_played(move_index)
        side_to_move_next = "black" if side_played == "white" else "white"
        nodes.append(
            OpeningNodeSchema(
                move_index=move_index,
                move_san=move_san,
                side_played=side_played,
                side_to_move_next=side_to_move_next,
                teaching=_build_rating_layers(
                    move_san=move_san,
                    teaching=teaching_data.get("teach", ""),
                    idea=teaching_data.get("idea", ""),
                    next_move=next_expected,
                ),
                plans_for_white=plans_for_white,
                plans_for_black=plans_for_black,
                next_expected_moves=[next_expected] if next_expected else [],
                trap_warning=matching_trap,
                idea=teaching_data.get("idea"),
            )
        )

    return nodes


def _build_traps(variation_data: Dict[str, Any]) -> List[OpeningTrapSchema]:
    traps = []
    for trap in variation_data.get("traps", []) or []:
        traps.append(
            OpeningTrapSchema(
                move=trap.get("move"),
                warning=trap.get("warning", ""),
                question=trap.get("question"),
                name=trap.get("name"),
                after_move=trap.get("after_move"),
            )
        )
    return traps


def _build_deviation_rules(variation_data: Dict[str, Any]) -> List[DeviationRuleSchema]:
    full_line = variation_data.get("full_line", []) or []
    plans_for_white = variation_data.get("plans_for_white", []) or []
    plans_for_black = variation_data.get("plans_for_black", []) or []
    rules: List[DeviationRuleSchema] = []

    for move_index, expected_move in enumerate(full_line):
        side_played = _infer_side_played(move_index)
        rules.append(
            DeviationRuleSchema(
                expected_move=expected_move,
                response_message=(
                    f"If {side_played} deviates here, explain why {expected_move} is the reference move and shift to the new resulting plan."
                ),
                new_plan_for_white=plans_for_white,
                new_plan_for_black=plans_for_black,
            )
        )

    return rules


def build_variation_schema(variation_id: str, variation_data: Dict[str, Any]) -> OpeningVariationSchema:
    return OpeningVariationSchema(
        variation_id=variation_id,
        variation_name=variation_data.get("name", variation_id),
        trigger_moves=variation_data.get("trigger_moves", []) or [],
        full_line=variation_data.get("full_line", []) or [],
        plans_for_white=variation_data.get("plans_for_white", []) or [],
        plans_for_black=variation_data.get("plans_for_black", []) or [],
        key_plans=variation_data.get("key_plans", []) or [],
        nodes=_build_nodes(variation_data),
        traps=_build_traps(variation_data),
        deviation_rules=_build_deviation_rules(variation_data),
        position_tags=variation_data.get("position_tags", []) or [],
    )


def _build_coverage(variations: List[OpeningVariationSchema]) -> OpeningCoverageSchema:
    if not variations:
        return OpeningCoverageSchema(
            variation_count=0,
            node_count=0,
            trap_count=0,
            deviation_rule_count=0,
            min_full_line_ply_depth=0,
            max_full_line_ply_depth=0,
            has_white_plans=False,
            has_black_plans=False,
            has_rating_layers=False,
        )

    depths = [len(variation.full_line) for variation in variations]
    nodes = [node for variation in variations for node in variation.nodes]
    return OpeningCoverageSchema(
        variation_count=len(variations),
        node_count=len(nodes),
        trap_count=sum(len(variation.traps) for variation in variations),
        deviation_rule_count=sum(len(variation.deviation_rules) for variation in variations),
        min_full_line_ply_depth=min(depths),
        max_full_line_ply_depth=max(depths),
        has_white_plans=all(bool(variation.plans_for_white) for variation in variations),
        has_black_plans=all(bool(variation.plans_for_black) for variation in variations),
        has_rating_layers=all(bool(node.teaching) for node in nodes) if nodes else False,
    )


def build_family_schema(
    family_id: str,
    family_name: str,
    eco_codes: List[str],
    starting_moves: List[str],
    family_concepts: Dict[str, List[str]],
    variations: Dict[str, Dict[str, Any]],
) -> OpeningFamilySchema:
    variation_schemas = [
        build_variation_schema(variation_id, variation_data)
        for variation_id, variation_data in variations.items()
    ]
    return OpeningFamilySchema(
        family_id=family_id,
        family_name=family_name,
        eco_codes=eco_codes,
        starting_moves=starting_moves,
        family_concepts=family_concepts,
        variations=variation_schemas,
        coverage=_build_coverage(variation_schemas),
    )


def validate_family_schema(family: OpeningFamilySchema) -> List[str]:
    issues: List[str] = []

    for variation in family.variations:
        if not variation.full_line:
            issues.append(f"{family.family_id}:{variation.variation_id} has no full line")
            continue

        board = chess.Board()
        for move in variation.full_line:
            try:
                board.push_san(move)
            except ValueError:
                issues.append(f"{family.family_id}:{variation.variation_id} has illegal SAN move {move}")
                break

        if len(variation.full_line) < len(variation.trigger_moves):
            issues.append(
                f"{family.family_id}:{variation.variation_id} full line is shorter than trigger moves"
            )

        if not variation.plans_for_white:
            issues.append(f"{family.family_id}:{variation.variation_id} missing plans_for_white")
        if not variation.plans_for_black:
            issues.append(f"{family.family_id}:{variation.variation_id} missing plans_for_black")
        if not variation.nodes:
            issues.append(f"{family.family_id}:{variation.variation_id} missing teaching nodes")

    return issues
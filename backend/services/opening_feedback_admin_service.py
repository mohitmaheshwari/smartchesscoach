"""Unified opening feedback catalog for admin + runtime overrides."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from coach_engine.opening_plans import OPENING_PLANS
from services.opening_library_service import OPENING_DATABASE as LIBRARY_DATABASE
from services.opening_mastery import OPENING_DATABASE as MASTERY_DATABASE
from services.verified_opening_traps import get_verified_traps_for_opening


def normalize_opening_key(value: str) -> str:
    return (
        (value or "")
        .strip()
        .lower()
        .replace("_", "-")
        .replace(" ", "-")
        .replace("'", "")
        .replace("(", "")
        .replace(")", "")
    )


def _opening_name_to_key(name: str) -> str:
    return normalize_opening_key(name)


@lru_cache(maxsize=1)
def build_opening_source_index() -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}

    for key, data in LIBRARY_DATABASE.items():
        canonical = normalize_opening_key(key)
        entry = index.setdefault(canonical, {"aliases": set(), "sources": {}})
        entry["aliases"].update({canonical, normalize_opening_key(data.get("name", ""))})
        entry["sources"]["library"] = {"key": key, "data": data}

    for key, opening in MASTERY_DATABASE.items():
        canonical = normalize_opening_key(key)
        entry = index.setdefault(canonical, {"aliases": set(), "sources": {}})
        entry["aliases"].update({canonical, _opening_name_to_key(opening.name)})
        entry["sources"]["mastery"] = {"key": key, "data": opening}

    seen_plan_names = set()
    for key, opening in OPENING_PLANS.items():
        if opening.name in seen_plan_names:
            continue
        seen_plan_names.add(opening.name)
        canonical = normalize_opening_key(key)
        entry = index.setdefault(canonical, {"aliases": set(), "sources": {}})
        entry["aliases"].update({canonical, _opening_name_to_key(opening.name)})
        entry["sources"]["plans"] = {"key": key, "data": opening}

    # Add alias back-references
    expanded_index: Dict[str, Dict[str, Any]] = {}
    for canonical, data in index.items():
        aliases = {alias for alias in data["aliases"] if alias}
        aliases.add(canonical)
        data["aliases"] = sorted(aliases)
        for alias in aliases:
            expanded_index[alias] = data
    return expanded_index


def get_known_opening_keys() -> List[Tuple[str, Dict[str, Any]]]:
    seen = set()
    results = []
    for alias, data in build_opening_source_index().items():
        canonical = data["aliases"][0]
        if canonical in seen:
            continue
        seen.add(canonical)
        results.append((canonical, data))
    return sorted(results, key=lambda item: item[0])


def _first_variation_data(source_data: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    if not source_data:
        return [], [], []

    if isinstance(source_data, dict) and source_data.get("main_line"):
        return [step.get("move") for step in source_data.get("main_line", [])], [], []

    variations = getattr(source_data, "variations", None) or []
    if variations:
        variation = variations[0]
        return list(getattr(variation, "moves", []) or []), list(getattr(variation, "plans_for_white", []) or []), list(getattr(variation, "plans_for_black", []) or [])
    return [], [], []


def _build_verified_trap_dicts(canonical_key: str) -> List[Dict[str, Any]]:
    traps = []
    for trap in get_verified_traps_for_opening(canonical_key.replace("-", "_")):
        traps.append({
            "name": trap.name,
            "description": trap.explanation,
            "setup_moves": trap.setup_moves,
            "trap_line": [{"move": move, "explanation": trap.explanation if move == trap.trap_move else ""} for move in trap.full_line],
            "result_type": "verified_trap",
            "difficulty": trap.difficulty,
            "trap_move": trap.trap_move,
            "refutation": trap.refutation,
            "victim_color": trap.victim_color,
        })
    return traps


def build_static_opening_feedback(opening_key: str) -> Optional[Dict[str, Any]]:
    lookup = build_opening_source_index().get(normalize_opening_key(opening_key))
    if not lookup:
        return None

    library = lookup["sources"].get("library", {}).get("data")
    mastery = lookup["sources"].get("mastery", {}).get("data")
    plan = lookup["sources"].get("plans", {}).get("data")

    canonical_key = normalize_opening_key(opening_key)
    opening_name = (
        (library or {}).get("name")
        or getattr(mastery, "name", None)
        or getattr(plan, "name", None)
        or canonical_key.replace("-", " ").title()
    )
    main_line, mastery_white_plans, mastery_black_plans = _first_variation_data(mastery or library)

    core_concepts = []
    if library:
        core_concepts.extend(library.get("key_ideas", []))
    if plan:
        core_concepts.extend(getattr(plan, "main_ideas", []) or [])
    if mastery and getattr(mastery, "variations", None):
        core_concepts.extend(getattr(mastery.variations[0], "key_ideas", []) or [])
    core_concepts = list(dict.fromkeys([concept for concept in core_concepts if concept]))

    white_plans = mastery_white_plans or []
    black_plans = mastery_black_plans or []
    if plan and getattr(plan, "variations", None):
        first_variation = next(iter(getattr(plan, "variations", {}).values()), None)
        if isinstance(first_variation, dict):
            white_plans = white_plans or first_variation.get("plans_for_white", []) or first_variation.get("key_plans", [])
            black_plans = black_plans or first_variation.get("plans_for_black", []) or first_variation.get("key_plans", [])

    common_mistakes = []
    if library:
        common_mistakes.extend(library.get("common_mistakes", []))
    if plan:
        common_mistakes.extend({"mistake": mistake, "fix": "Use the opening plan instead."} for mistake in (getattr(plan, "typical_mistakes", []) or []))

    what_if = (library or {}).get("what_if", []) if library else []
    ideas_tab = what_if or [{"title": "Core concept", "body": concept} for concept in core_concepts[:5]]

    description = (library or {}).get("description") or getattr(mastery, "description", None) or getattr(plan, "simple_explanation", None) or ""
    color = (library or {}).get("color") or ("black" if "defense" in opening_name.lower() or "indian" in opening_name.lower() else "white")
    character = getattr(mastery, "character", None) or ("semi-open" if "sicilian" in opening_name.lower() else "strategic")
    introduction = getattr(mastery, "introduction_message", None) or f"Let's learn the {opening_name}."
    traps = _build_verified_trap_dicts(canonical_key)
    if not traps and library:
        traps = library.get("traps", []) or []

    feedback = {
        "opening_key": canonical_key,
        "opening_name": opening_name,
        "identity": character,
        "difficulty": "intermediate",
        "core_concepts": core_concepts[:8],
        "plans": {
            "white": white_plans or core_concepts[:3],
            "black": black_plans or core_concepts[:3],
        },
        "traps": traps,
        "common_mistakes": common_mistakes,
        "ideas_tab": ideas_tab,
        "adaptive_layers": {
            "beginner": {
                "focus": core_concepts[0] if core_concepts else "Follow the basic opening principles",
                "explanation": description,
                "next_step": "Develop pieces and castle",
            },
            "intermediate": {
                "focus": core_concepts[1] if len(core_concepts) > 1 else (core_concepts[0] if core_concepts else "Understand the key plan"),
                "explanation": description,
                "next_step": "Follow the main plan and watch the key pawn break",
            },
            "advanced": {
                "focus": core_concepts[2] if len(core_concepts) > 2 else (core_concepts[0] if core_concepts else "Study the structure"),
                "explanation": description,
                "next_step": "Compare move orders and transpositions",
            },
        },
        "coach_voice_lines": [introduction],
        "main_line": [{"move": move, "explanation": ""} for move in (library.get("main_line", []) if library else [])] if library else [{"move": move, "explanation": ""} for move in main_line],
        "what_if": what_if,
        "color": color,
        "source_metadata": {
            "canonical_key": canonical_key,
            "aliases": lookup["aliases"],
            "sources": sorted(list(lookup["sources"].keys())),
        },
    }
    return feedback


async def get_opening_feedback_override(db, opening_key: str) -> Optional[Dict[str, Any]]:
    canonical = normalize_opening_key(opening_key)
    aliases = build_opening_source_index().get(canonical, {}).get("aliases", [canonical])
    if not hasattr(db, "opening_feedback"):
        return None
    for alias in aliases:
        doc = await db.opening_feedback.find_one({"opening_key": alias}, {"_id": 0})
        if doc:
            return doc
    return None


def _merge_feedback(static_feedback: Dict[str, Any], override_feedback: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(static_feedback)
    for key, value in override_feedback.items():
        if value in (None, "", [], {}):
            continue
        merged[key] = value
    if "source_metadata" in merged:
        merged["source_metadata"] = {
            **static_feedback.get("source_metadata", {}),
            "has_admin_override": True,
        }
    return merged


async def get_effective_opening_feedback(db, opening_key: str) -> Optional[Dict[str, Any]]:
    static_feedback = build_static_opening_feedback(opening_key)
    override_doc = await get_opening_feedback_override(db, opening_key)
    if not static_feedback and not override_doc:
        return None
    if override_doc and override_doc.get("feedback"):
        override_feedback = override_doc["feedback"]
        return _merge_feedback(static_feedback or {}, override_feedback)
    return static_feedback


async def list_effective_openings(db) -> List[Dict[str, Any]]:
    rows = []
    for canonical_key, meta in get_known_opening_keys():
        effective = await get_effective_opening_feedback(db, canonical_key)
        if not effective:
            continue
        rows.append({
            "opening_key": canonical_key,
            "opening_name": effective.get("opening_name"),
            "updated_at": (await get_opening_feedback_override(db, canonical_key) or {}).get("updated_at"),
            "sources": effective.get("source_metadata", {}).get("sources", []),
        })
    return rows


def feedback_to_opening_lesson_shape(feedback: Dict[str, Any]) -> Dict[str, Any]:
    traps = []
    for trap in feedback.get("traps", []) or []:
        traps.append({
            "name": trap.get("name"),
            "description": trap.get("description") or trap.get("explanation") or "",
            "setup_moves": trap.get("setup_moves") or trap.get("moves") or [],
            "trap_line": trap.get("trap_line") or [{"move": move, "explanation": ""} for move in trap.get("moves", [])],
            "success_message": trap.get("success_message") or trap.get("description") or "",
            "difficulty": trap.get("difficulty") or feedback.get("difficulty") or "intermediate",
            "result_type": trap.get("result_type") or "training_line",
        })

    return {
        "name": feedback.get("opening_name"),
        "eco": feedback.get("eco") or "",
        "description": feedback.get("adaptive_layers", {}).get("intermediate", {}).get("explanation") or feedback.get("coach_voice_lines", [""])[0] or "",
        "color": feedback.get("color") or "white",
        "first_moves": [step.get("move") for step in feedback.get("main_line", [])[:5]],
        "main_line": feedback.get("main_line", []),
        "key_ideas": feedback.get("core_concepts", []),
        "common_mistakes": feedback.get("common_mistakes", []),
        "traps": traps,
        "what_if": feedback.get("ideas_tab", []),
        "identity": feedback.get("identity"),
    }
"""Pure whole-game composition over already-authorized review events.

This module is deliberately not a chess detector. It does not import
python-chess, inspect board geometry, read a database, call an engine, or name a
new concept. It arranges the safe GameTeachingPlan into honest stored phases.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


WHOLE_GAME_REVIEW_SCHEMA_VERSION = "whole_game_teaching_review.v1"
WHOLE_GAME_COMPOSER_VERSION = "whole_game_review_composer.v1"
PHASE_SOURCE = "stored_decryption_v5.phase"
PHASES = ("opening", "middlegame", "endgame")
PHASE_STATES = frozenset(
    {
        "verified_lesson",
        "verified_good_play",
        "no_authorized_lesson",
        "not_reached",
    }
)
_GOOD_OUTCOMES = frozenset({"demonstrated", "answered", "neutralized"})
_LESSON_OUTCOMES = frozenset({"missed", "allowed", "introduced"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _clean_text(value: Any, *, maximum: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if not text or len(text) > maximum or any(ord(char) < 32 for char in text):
        return ""
    return text


def _stored_phase_rows(
    stored_moves: Sequence[Mapping[str, Any]],
) -> Optional[Tuple[Tuple[int, str], ...]]:
    rows = []
    for index, move in enumerate(stored_moves):
        if not isinstance(move, Mapping):
            return None
        phase = _clean_text(move.get("phase"), maximum=20).lower()
        if phase not in PHASES:
            return None
        rows.append((index + 1, phase))
    return tuple(rows) if rows else None


def _opening_name(stored_moves: Sequence[Mapping[str, Any]]) -> str:
    for move in stored_moves:
        name = _clean_text(move.get("opening_name"), maximum=120)
        if name:
            return name
    return ""


def _event_headline(event: Mapping[str, Any]) -> str:
    teaching = event.get("teaching")
    practical = event.get("practical")
    if isinstance(teaching, Mapping):
        headline = _clean_text(teaching.get("headline"), maximum=160)
        if headline:
            return headline
    if isinstance(practical, Mapping):
        headline = _clean_text(practical.get("headline"), maximum=160)
        if headline:
            return headline
    outcome = _clean_text(event.get("outcome"), maximum=30)
    actor = _clean_text((event.get("move") or {}).get("actor"), maximum=20)
    if outcome in _GOOD_OUTCOMES:
        return "You handled this decision well"
    if actor == "opponent":
        return "Your opponent left a chance"
    return "One decision is worth replaying"


def _event_phase(
    event: Mapping[str, Any],
    phase_by_ply: Mapping[int, str],
) -> Optional[str]:
    move = event.get("move")
    if not isinstance(move, Mapping):
        return None
    ply = move.get("ply")
    if not isinstance(ply, int):
        return None
    return phase_by_ply.get(ply)


def _phase_summary(
    phase: str,
    state: str,
    *,
    opening_name: str,
    event_count: int,
) -> str:
    if state == "not_reached":
        if phase == "endgame":
            return "This game ended before a real endgame began."
        return f"This game did not reach a stored {phase} phase."
    if state == "no_authorized_lesson":
        if phase == "opening" and opening_name:
            return (
                f"You reached the {opening_name}. "
                "I do not yet have an opening lesson I can prove from this game."
            )
        return (
            f"This game reached the {phase}. "
            "I do not yet have a lesson I can prove there."
        )
    if state == "verified_good_play":
        return (
            "You handled a verified decision well here."
            if event_count == 1
            else f"You handled {event_count} verified decisions well here."
        )
    return (
        "I found one verified decision worth studying here."
        if event_count == 1
        else f"I found {event_count} verified decisions worth studying here."
    )


def _phase_title(phase: str, opening_name: str) -> str:
    if phase == "opening" and opening_name:
        return opening_name
    return phase.capitalize()


def _fingerprinted(payload: Dict[str, Any]) -> Dict[str, Any]:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    payload["presentation_fingerprint"] = hashlib.sha256(encoded).hexdigest()
    return payload


def compose_empty_whole_game_review(
    *,
    stored_moves: Sequence[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Describe reached phases without inventing a lesson or takeaway.

    This is a valid product result, not an error fallback. It uses only the
    phase and opening identity already stored on the move rows. No unapproved
    event, stale plan, generic principle, or inferred chess judgment can enter
    the response.
    """
    phase_rows = _stored_phase_rows(stored_moves)
    if phase_rows is None:
        return None
    opening_name = _opening_name(stored_moves)
    reached = {phase for _, phase in phase_rows}
    phases = []
    for phase in PHASES:
        state = "no_authorized_lesson" if phase in reached else "not_reached"
        phase_plies = [ply for ply, stored_phase in phase_rows if stored_phase == phase]
        phases.append(
            {
                "phase": phase,
                "title": _phase_title(phase, opening_name),
                "state": state,
                "summary": _phase_summary(
                    phase,
                    state,
                    opening_name=opening_name,
                    event_count=0,
                ),
                "first_ply": min(phase_plies) if phase_plies else None,
                "last_ply": max(phase_plies) if phase_plies else None,
                "event_ids": [],
                "lead_event_headline": None,
            }
        )

    source_input = {
        "phase_rows": list(phase_rows),
        "opening_name": opening_name or None,
    }
    source_fingerprint = hashlib.sha256(
        json.dumps(
            source_input,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    return _fingerprinted(
        {
            "schema_version": WHOLE_GAME_REVIEW_SCHEMA_VERSION,
            "composer_version": WHOLE_GAME_COMPOSER_VERSION,
            "source": {
                "kind": "stored_phase_overview",
                "input_fingerprint": source_fingerprint,
                "phase_source": PHASE_SOURCE,
            },
            "opening": {
                "name": opening_name or None,
                "claim_strength": "identity_only" if opening_name else "none",
            },
            "central_story": {
                "headline": "I don't have a verified lesson for this game yet.",
                "lead": (
                    "You can still walk through every move. I won't invent a "
                    "lesson that the stored evidence cannot prove."
                ),
                "phase": None,
                "source_event_id": None,
            },
            "phases": phases,
            "featured_event_ids": [],
            "surviving_instruction": None,
        }
    )


def _find_takeaway_source(
    plan: Mapping[str, Any],
    event_index: Mapping[str, Mapping[str, Any]],
) -> Optional[str]:
    takeaway = _clean_text(plan.get("takeaway"), maximum=500)
    if not takeaway:
        return None
    for chapter in plan.get("chapters") or []:
        if not isinstance(chapter, Mapping):
            continue
        event_id = _clean_text(chapter.get("event_id"), maximum=260)
        event = event_index.get(event_id)
        teaching = event.get("teaching") if isinstance(event, Mapping) else None
        if not isinstance(teaching, Mapping):
            continue
        if takeaway in {
            _clean_text(teaching.get("principle"), maximum=500),
            _clean_text(teaching.get("caption"), maximum=500),
        }:
            return event_id
    return None


def compose_whole_game_review(
    *,
    stored_moves: Sequence[Mapping[str, Any]],
    safe_plan: Mapping[str, Any],
    safe_events: Sequence[Mapping[str, Any]],
    stored_plan_envelope: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    """Return a deterministic public story, or None on any mismatch."""
    phase_rows = _stored_phase_rows(stored_moves)
    if phase_rows is None:
        return None
    if not isinstance(safe_plan, Mapping) or not isinstance(
        stored_plan_envelope, Mapping
    ):
        return None

    plan_id = _clean_text(safe_plan.get("plan_id"), maximum=260)
    formula_id = _clean_text(
        stored_plan_envelope.get("formula_id"), maximum=80
    )
    raw_plan = stored_plan_envelope.get("plan")
    if not plan_id or not formula_id or not isinstance(raw_plan, Mapping):
        return None
    input_fingerprint = _clean_text(
        raw_plan.get("input_fingerprint"), maximum=64
    )
    source_v5_version = stored_plan_envelope.get("source_v5_version")
    if (
        not _SHA256_RE.fullmatch(input_fingerprint)
        or not isinstance(source_v5_version, int)
        or source_v5_version < 1
    ):
        return None

    event_index: Dict[str, Mapping[str, Any]] = {}
    for event in safe_events:
        if not isinstance(event, Mapping):
            return None
        event_id = _clean_text(event.get("event_id"), maximum=260)
        display = event.get("display")
        if (
            not event_id
            or event_id in event_index
            or not isinstance(display, Mapping)
            or display.get("authorized") is not True
        ):
            return None
        event_index[event_id] = event

    chapters = safe_plan.get("chapters")
    if not isinstance(chapters, list) or not 1 <= len(chapters) <= 3:
        return None
    selected_event_ids = []
    for chapter in chapters:
        if not isinstance(chapter, Mapping):
            return None
        event_id = _clean_text(chapter.get("event_id"), maximum=260)
        if not event_id or event_id not in event_index:
            return None
        selected_event_ids.append(event_id)
    if len(selected_event_ids) != len(set(selected_event_ids)):
        return None

    phase_by_ply = dict(phase_rows)
    events_by_phase = {phase: [] for phase in PHASES}
    for event_id in selected_event_ids:
        phase = _event_phase(event_index[event_id], phase_by_ply)
        if phase not in PHASES:
            return None
        events_by_phase[phase].append(event_id)

    opening_name = _opening_name(stored_moves)
    reached = {phase for _, phase in phase_rows}
    phase_contracts = []
    for phase in PHASES:
        event_ids = events_by_phase[phase]
        if phase not in reached:
            state = "not_reached"
        elif not event_ids:
            state = "no_authorized_lesson"
        else:
            outcomes = {
                _clean_text(event_index[event_id].get("outcome"), maximum=30)
                for event_id in event_ids
            }
            state = (
                "verified_lesson"
                if outcomes & _LESSON_OUTCOMES
                else "verified_good_play"
            )
        if state not in PHASE_STATES:
            return None
        phase_plies = [ply for ply, stored_phase in phase_rows if stored_phase == phase]
        phase_contracts.append(
            {
                "phase": phase,
                "title": _phase_title(phase, opening_name),
                "state": state,
                "summary": _phase_summary(
                    phase,
                    state,
                    opening_name=opening_name,
                    event_count=len(event_ids),
                ),
                "first_ply": min(phase_plies) if phase_plies else None,
                "last_ply": max(phase_plies) if phase_plies else None,
                "event_ids": list(event_ids),
                "lead_event_headline": (
                    _event_headline(event_index[event_ids[0]])
                    if event_ids
                    else None
                ),
            }
        )

    takeaway_source_id = _find_takeaway_source(safe_plan, event_index)
    if takeaway_source_id is None:
        return None
    takeaway_event = event_index[takeaway_source_id]
    central_phase = _event_phase(takeaway_event, phase_by_ply)
    if central_phase not in PHASES:
        return None
    if opening_name and central_phase != "opening":
        central_lead = (
            f"You reached the {opening_name}. "
            f"The clearest verified lesson came in the {central_phase}."
        )
    elif central_phase == "opening":
        central_lead = "The clearest verified lesson came in the opening."
    else:
        central_lead = (
            f"The clearest verified lesson came in the {central_phase}."
        )

    payload: Dict[str, Any] = {
        "schema_version": WHOLE_GAME_REVIEW_SCHEMA_VERSION,
        "composer_version": WHOLE_GAME_COMPOSER_VERSION,
        "source": {
            "plan_id": plan_id,
            "formula_id": formula_id,
            "input_fingerprint": input_fingerprint,
            "source_v5_version": source_v5_version,
            "phase_source": PHASE_SOURCE,
        },
        "opening": {
            "name": opening_name or None,
            "claim_strength": "identity_only" if opening_name else "none",
        },
        "central_story": {
            "headline": _event_headline(takeaway_event),
            "lead": central_lead,
            "phase": central_phase,
            "source_event_id": takeaway_source_id,
        },
        "phases": phase_contracts,
        "featured_event_ids": list(selected_event_ids),
        "surviving_instruction": {
            "text": _clean_text(safe_plan.get("takeaway"), maximum=500),
            "source_event_id": takeaway_source_id,
        },
    }
    return _fingerprinted(payload)

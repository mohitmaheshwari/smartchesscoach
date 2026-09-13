"""Aggregate-only rollout evidence for the unified Play with Coach flow."""

from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Any, Dict, Iterable, Mapping


def _timestamp(value: Any) -> float | None:
    if isinstance(value, datetime):
        return value.timestamp()
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percentile)))
    return round(ordered[index], 1)


def summarize_unified_rollout(
    sessions: Iterable[Mapping[str, Any]],
    live_message_counts: Mapping[str, int] | None = None,
) -> Dict[str, Any]:
    """Return privacy-safe funnel and isolation metrics, never row content."""
    rows = list(sessions)
    message_counts = live_message_counts or {}
    modes = {"coach": 0, "play": 0}
    first_move_seconds = []
    completed = 0
    abandoned = 0
    abandoned_before_two = 0
    visible_interventions = 0
    delivered_interventions = 0
    intervention_outcomes: Dict[str, int] = {}
    interruption_durations = []
    help_requests = 0
    resumes = 0
    postgame_actions = 0
    play_live_messages = 0

    for row in rows:
        mode = str(row.get("game_mode") or "coach")
        if mode in modes:
            modes[mode] += 1
        journey = row.get("unified_journey") or {}
        started = _timestamp(journey.get("started_at") or row.get("created_at"))
        first = _timestamp(journey.get("first_move_at"))
        if started is not None and first is not None and first >= started:
            first_move_seconds.append(first - started)

        status = str(row.get("status") or "")
        if status == "completed":
            completed += 1
        if status in {"resigned", "abandoned"}:
            abandoned += 1
            player_moves = sum(
                item.get("by") == "player" for item in (row.get("move_history") or [])
            )
            if player_moves < 2:
                abandoned_before_two += 1

        decisions = [
            item for item in (row.get("coaching_decisions") or [])
            if item.get("source") == "pwc_unified_v1"
        ]
        for decision in decisions:
            if decision.get("layer") in {"advisory", "critical_interrupt"}:
                visible_interventions += 1
                if decision.get("delivered_at"):
                    delivered_interventions += 1
                outcome = str(decision.get("outcome") or "unknown")
                intervention_outcomes[outcome] = intervention_outcomes.get(outcome, 0) + 1
                duration = decision.get("interruption_duration_ms")
                if isinstance(duration, (int, float)) and duration >= 0:
                    interruption_durations.append(float(duration))

        help_requests += len(row.get("coaching_help_events") or [])
        resumes += len(journey.get("resume_events") or [])
        postgame_actions += len(journey.get("postgame_action_events") or [])
        if mode == "play":
            play_live_messages += int(message_counts.get(str(row.get("session_id")), 0))

    total = len(rows)
    return {
        "schema_version": "pwc_unified_rollout_report.v1",
        "sessions": total,
        "sessions_by_mode": modes,
        "first_move": {
            "sessions": len(first_move_seconds),
            "median_seconds": round(median(first_move_seconds), 1) if first_move_seconds else None,
            "p90_seconds": _percentile(first_move_seconds, 0.90),
        },
        "completion": {
            "completed_sessions": completed,
            "completion_rate": round(completed / total, 4) if total else None,
            "abandoned_sessions": abandoned,
            "abandoned_before_two_player_moves": abandoned_before_two,
        },
        "interventions": {
            "visible": visible_interventions,
            "delivered": delivered_interventions,
            "outcomes": intervention_outcomes,
            "median_duration_ms": (
                round(median(interruption_durations), 1)
                if interruption_durations else None
            ),
        },
        "help_requests": help_requests,
        "resume_events": resumes,
        "postgame_actions": postgame_actions,
        "play_mode_isolation": {
            "live_coach_messages": play_live_messages,
            "passes_zero_message_gate": play_live_messages == 0,
        },
    }


__all__ = ["summarize_unified_rollout"]

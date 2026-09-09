"""Read-only structural audit for the canonical opening-trap library.

All findings are derived from ``data/traps.json``. This module deliberately
does not maintain another trap registry or decide engine truth.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import chess


REQUIRED_FIELDS = (
    "name", "setup_moves", "trap_line", "trap_color", "result_type", "difficulty",
)


def normalized_san(move: str) -> str:
    return (
        (move or "").replace("+", "").replace("#", "")
        .replace("!", "").replace("?", "").strip()
    )


def position_key(board: chess.Board) -> str:
    """Legal-position FEN fields, excluding halfmove/fullmove counters."""
    return " ".join(board.fen(en_passant="legal").split()[:4])


def _line_moves(trap: Dict[str, Any]) -> List[str]:
    return [
        str(step.get("move") or "") if isinstance(step, dict) else str(step or "")
        for step in (trap.get("trap_line") or [])
    ]


def _trap_entries(data: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    for family, traps in data.items():
        if family.startswith("_") or not isinstance(traps, list):
            continue
        for trap in traps:
            if isinstance(trap, dict):
                yield family, trap


def _entry_key(family: str, trap: Dict[str, Any]) -> str:
    return f"{family}/{trap.get('name') or '?'}"


def audit_trap_library(data: Dict[str, Any]) -> Dict[str, Any]:
    """Audit parsed canonical trap data and return a JSON-safe report."""
    entries = list(_trap_entries(data))
    entry_reports: Dict[str, Dict[str, Any]] = {}
    full_line_groups: Dict[Tuple[str, ...], List[str]] = defaultdict(list)
    setup_sequence_groups: Dict[Tuple[str, ...], List[str]] = defaultdict(list)
    setup_position_groups: Dict[str, List[str]] = defaultdict(list)
    decision_position_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    role_mismatches: List[Dict[str, Any]] = []
    first_line_role_counts = {"setter": 0, "victim": 0, "unknown": 0}

    for family, trap in entries:
        key = _entry_key(family, trap)
        setup = [str(move or "") for move in (trap.get("setup_moves") or [])]
        line = _line_moves(trap)
        missing_explanation_steps = [
            index
            for index, step in enumerate(trap.get("trap_line") or [])
            if not isinstance(step, dict) or not str(step.get("explanation") or "").strip()
        ]
        full_line = setup + line
        missing = [field for field in REQUIRED_FIELDS if not trap.get(field)]
        illegal: Dict[str, Any] | None = None
        board = chess.Board()
        reached_decisions = 0

        for ply_index, san in enumerate(full_line):
            phase = "setup" if ply_index < len(setup) else "trap_line"
            step_index = None if phase == "setup" else ply_index - len(setup)
            fen_before = board.fen(en_passant="legal")
            try:
                move = board.parse_san(san)
            except Exception as exc:
                illegal = {
                    "phase": phase,
                    "ply_index": ply_index,
                    "line_step_index": step_index,
                    "move": san,
                    "fen_before": fen_before,
                    "error": str(exc),
                }
                break

            if phase == "trap_line":
                decision_position_groups[position_key(board)].append({
                    "entry": key,
                    "line_step_index": step_index,
                    "side_to_move": "white" if board.turn else "black",
                    "authored_move": san,
                })
                reached_decisions += 1
            board.push(move)
            if ply_index + 1 == len(setup):
                setup_position_groups[position_key(board)].append(key)

        setup_sequence_groups[tuple(normalized_san(m) for m in setup)].append(key)
        full_line_groups[tuple(normalized_san(m) for m in full_line)].append(key)

        parity_color = "white" if len(setup) % 2 == 0 else "black"
        trap_color = str(trap.get("trap_color") or "").lower()
        if not line or trap_color not in {"white", "black"}:
            first_line_role_counts["unknown"] += 1
        elif parity_color == trap_color:
            first_line_role_counts["setter"] += 1
        else:
            first_line_role_counts["victim"] += 1
        if trap_color and parity_color != trap_color:
            role_mismatches.append({
                "entry": key,
                "trap_color": trap_color,
                "side_to_move_after_setup": parity_color,
                "first_line_move": line[0] if line else None,
            })

        entry_reports[key] = {
            "family": family,
            "name": trap.get("name"),
            "missing_fields": missing,
            "illegal": illegal,
            "setup_plies": len(setup),
            "authored_line_steps": len(line),
            "legally_reached_decision_steps": reached_decisions,
            "missing_explanation_steps": missing_explanation_steps,
            "trap_color": trap_color or None,
            "side_to_move_after_setup": parity_color,
        }

    duplicate_full_lines = [
        {"entries": keys, "normalized_full_line": list(signature)}
        for signature, keys in full_line_groups.items() if len(keys) > 1
    ]
    ambiguous_setup_sequences = [
        {"entries": keys, "normalized_setup": list(signature)}
        for signature, keys in setup_sequence_groups.items() if len(keys) > 1
    ]
    shared_setup_positions = [
        {"entries": keys, "position_key": key}
        for key, keys in setup_position_groups.items() if len(keys) > 1
    ]
    shared_decision_positions = [
        {"matches": matches, "position_key": key}
        for key, matches in decision_position_groups.items() if len(matches) > 1
    ]

    duplicate_entries = {
        entry for group in duplicate_full_lines for entry in group["entries"]
    }
    ambiguous_entries = {
        entry for group in ambiguous_setup_sequences for entry in group["entries"]
    }
    eligible_entries: List[str] = []
    for key, report in entry_reports.items():
        reasons: List[str] = []
        if report["missing_fields"]:
            reasons.append("missing_fields")
        if report["illegal"]:
            reasons.append("illegal_line")
        if key in duplicate_entries:
            reasons.append("duplicate_full_line")
        if key in ambiguous_entries:
            reasons.append("ambiguous_exact_setup")
        report["gold_blockers"] = reasons
        if not reasons:
            eligible_entries.append(key)

    illegal_entries = [k for k, r in entry_reports.items() if r["illegal"]]
    missing_entries = [k for k, r in entry_reports.items() if r["missing_fields"]]
    authored_steps = sum(r["authored_line_steps"] for r in entry_reports.values())
    reached_steps = sum(r["legally_reached_decision_steps"] for r in entry_reports.values())
    entries_with_missing_explanations = [
        key for key, report in entry_reports.items() if report["missing_explanation_steps"]
    ]

    return {
        "summary": {
            "family_count": len({family for family, _ in entries}),
            "trap_count": len(entries),
            "fully_legal_count": len(entries) - len(illegal_entries),
            "missing_field_entry_count": len(missing_entries),
            "illegal_entry_count": len(illegal_entries),
            "duplicate_full_line_group_count": len(duplicate_full_lines),
            "ambiguous_setup_sequence_group_count": len(ambiguous_setup_sequences),
            "shared_setup_position_group_count": len(shared_setup_positions),
            "role_parity_mismatch_count": len(role_mismatches),
            "first_line_role_counts": first_line_role_counts,
            "authored_line_step_count": authored_steps,
            "legally_reached_decision_step_count": reached_steps,
            "unique_decision_position_count": len(decision_position_groups),
            "shared_decision_position_group_count": len(shared_decision_positions),
            "gold_eligible_entry_count": len(eligible_entries),
            "missing_explanation_entry_count": len(entries_with_missing_explanations),
            "has_canonical_stable_ids": all(bool(t.get("trap_id")) for _, t in entries),
        },
        "entries": entry_reports,
        "illegal_entries": illegal_entries,
        "missing_field_entries": missing_entries,
        "missing_explanation_entries": entries_with_missing_explanations,
        "role_parity_mismatches": role_mismatches,
        "duplicate_full_lines": duplicate_full_lines,
        "ambiguous_setup_sequences": ambiguous_setup_sequences,
        "shared_setup_positions": shared_setup_positions,
        "shared_decision_positions": shared_decision_positions,
        "gold_eligible_entries": eligible_entries,
    }


def audit_trap_library_file(path: Path) -> Dict[str, Any]:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("trap library root must be a JSON object")
    report = audit_trap_library(data)
    report["source"] = {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    return report


def has_gold_blockers(report: Dict[str, Any]) -> bool:
    summary = report["summary"]
    return any((
        summary["missing_field_entry_count"],
        summary["illegal_entry_count"],
        summary["duplicate_full_line_group_count"],
        summary["ambiguous_setup_sequence_group_count"],
        not summary["has_canonical_stable_ids"],
    ))

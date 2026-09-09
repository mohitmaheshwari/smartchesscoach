import copy
import json

import chess

from services.trap_library_audit import (
    audit_trap_library,
    audit_trap_library_file,
    has_gold_blockers,
    position_key,
)


BASE_TRAP = {
    "name": "Synthetic Fork Trap",
    "setup_moves": ["e4", "e5", "Nf3", "Nc6"],
    "trap_line": [
        {"move": "Bb5", "explanation": "Pin the knight."},
        {"move": "a6", "explanation": "Challenge the bishop."},
    ],
    "trap_color": "white",
    "result_type": "positional_advantage",
    "difficulty": "beginner",
    "trap_id": "synthetic-fork-trap",
}


def test_position_key_ignores_move_counters_but_keeps_legal_state():
    first = chess.Board()
    second = chess.Board()
    second.halfmove_clock = 17
    second.fullmove_number = 42
    assert position_key(first) == position_key(second)


def test_audit_accepts_one_complete_legal_trap():
    report = audit_trap_library({"synthetic-opening": [copy.deepcopy(BASE_TRAP)]})
    assert report["summary"]["trap_count"] == 1
    assert report["summary"]["fully_legal_count"] == 1
    assert report["summary"]["first_line_role_counts"] == {"setter": 1, "victim": 0, "unknown": 0}
    assert report["summary"]["gold_eligible_entry_count"] == 1
    assert report["summary"]["has_canonical_stable_ids"] is True
    assert has_gold_blockers(report) is False


def test_audit_reports_illegal_authored_move_with_reproducible_fen():
    bad = copy.deepcopy(BASE_TRAP)
    bad["trap_line"][0]["move"] = "Kxf7"
    report = audit_trap_library({"synthetic-opening": [bad]})
    issue = report["entries"]["synthetic-opening/Synthetic Fork Trap"]["illegal"]
    assert report["summary"]["illegal_entry_count"] == 1
    assert issue["phase"] == "trap_line"
    assert issue["line_step_index"] == 0
    assert issue["move"] == "Kxf7"
    assert issue["fen_before"]
    assert has_gold_blockers(report) is True


def test_audit_detects_duplicate_lines_and_first_match_setup_collision():
    first = copy.deepcopy(BASE_TRAP)
    second = copy.deepcopy(BASE_TRAP)
    second["name"] = "Same Moves, Different Name"
    second["trap_id"] = "same-moves-different-name"
    report = audit_trap_library({"synthetic-opening": [first, second]})
    assert report["summary"]["duplicate_full_line_group_count"] == 1
    assert report["summary"]["ambiguous_setup_sequence_group_count"] == 1
    assert report["summary"]["gold_eligible_entry_count"] == 0
    assert has_gold_blockers(report) is True


def test_audit_exposes_why_move_parity_cannot_define_the_setter():
    trap = copy.deepcopy(BASE_TRAP)
    trap["trap_color"] = "black"
    report = audit_trap_library({"synthetic-opening": [trap]})
    mismatch = report["role_parity_mismatches"][0]
    assert report["summary"]["role_parity_mismatch_count"] == 1
    assert mismatch["trap_color"] == "black"
    assert mismatch["side_to_move_after_setup"] == "white"
    assert report["summary"]["first_line_role_counts"] == {"setter": 0, "victim": 1, "unknown": 0}


def test_missing_stable_id_blocks_gold_without_duplicating_trap_data():
    trap = copy.deepcopy(BASE_TRAP)
    trap.pop("trap_id")
    report = audit_trap_library({"synthetic-opening": [trap]})
    assert report["summary"]["has_canonical_stable_ids"] is False
    assert has_gold_blockers(report) is True


def test_file_audit_fingerprints_the_exact_canonical_snapshot(tmp_path):
    path = tmp_path / "traps.json"
    path.write_text(json.dumps({"synthetic-opening": [BASE_TRAP]}), encoding="utf-8")
    report = audit_trap_library_file(path)
    assert report["source"]["path"] == str(path.resolve())
    assert len(report["source"]["sha256"]) == 64

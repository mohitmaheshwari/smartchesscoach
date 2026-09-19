"""Audit tests use synthetic frozen grades, never promotion/production evidence."""
from copy import deepcopy
import json
from pathlib import Path

import chess
import chess.engine
import pytest

from scripts import audit_diagnostic_teaching_readiness as audit
from services.diagnostic_service import DIAGNOSTIC_GRADE_VERSION, diagnostic_grade_fingerprint
from services.teaching_reason_contracts import TeachingReasonBundle, ReasonContractViolation


GOLD = json.loads((Path(__file__).parents[1] / "data/detector_gold/home_teaching_case_v2_v1.json")
                  .read_text(encoding="utf-8"))["cases"]


def stamp(row):
    row["grade_fingerprint"] = diagnostic_grade_fingerprint(row)
    return row


def fixture(case_index=0, *, all_legal=True):
    """Wire-contract fixture only; the test does NOT assert engine evaluations."""
    case = GOLD[case_index]
    board = chess.Board(case["fen"])
    moves = list(board.legal_moves) if all_legal else [chess.Move.from_uci(case["move_uci"])]
    return stamp({
        "puzzle_id": "test-only-not-a-production-puzzle", "concept": "piece_safety",
        "fen": case["fen"], "moves": [case["move_uci"]], "puzzle_rating": 1000,
        "grade_version": DIAGNOSTIC_GRADE_VERSION,
        "step_grades": [{"fen": case["fen"], "solution_uci": case["move_uci"],
                         "grade_by_uci": {move.uci(): {
                             "verdict": "UNDERSTOOD" if move.uci() == case["move_uci"] else "MISSING",
                             "cp_loss": 0 if move.uci() == case["move_uci"] else 400,
                             "eval_after_cp": 0,
                         } for move in moves}}],
    })


@pytest.fixture(autouse=True)
def no_engine(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("An audit must never launch an engine")
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", forbidden)


def test_inventory_does_not_invoke_reason_derivation(monkeypatch):
    monkeypatch.setattr(audit, "build_reason_bundle_for_move", lambda **_: pytest.fail("not requested"))
    report = audit.build_report([fixture()])
    assert report["counts"]["current_valid_rows"] == 1
    assert report["counts"]["missing_legal_move_grades"] == 0
    assert not report["ready_for_player_exposure"]


def test_supported_reason_is_not_a_full_move_verdict_or_mastery():
    report = audit.build_report([fixture()], derive_reasons=True)
    assert report["counts"]["rows_with_at_least_one_proposed_reason"] == 1
    assert report["move_verdict_by_destination_safety"]["UNDERSTOOD:pass"] == 1
    assert report["move_verdict_by_destination_safety"]["MISSING:pass"] > 0
    assert not report["ready_for_player_exposure"]


def test_pawn_solution_has_no_supported_piece_safety_reason():
    report = audit.build_report([fixture(4, all_legal=False)], derive_reasons=True)
    assert report["counts"]["no_supported_reason"] == 1
    assert report["move_verdict_by_destination_safety"] == {}


def test_incomplete_legal_move_map_cannot_look_complete():
    report = audit.build_report([fixture(all_legal=False)])
    assert report["counts"]["rows_missing_legal_move_grades"] == 1
    assert report["counts"]["missing_legal_move_grades"] > 0


def test_stale_fingerprint_never_derives_a_reason(monkeypatch):
    row = fixture()
    row["puzzle_rating"] += 1
    monkeypatch.setattr(audit, "build_reason_bundle_for_move", lambda **_: pytest.fail("stale"))
    report = audit.build_report([row], derive_reasons=True)
    assert report["counts"]["stale_or_missing_frozen_grades"] == 1


@pytest.mark.parametrize("corruption", ["line", "step_fen", "missing_step", "extra_step",
                                        "illegal_grade", "malformed_grade", "missing_solution"])
def test_current_fingerprint_does_not_make_bad_contract_valid(corruption):
    row = fixture()
    step = row["step_grades"][0]
    if corruption == "line":
        row["moves"] = ["d3h8"]
    elif corruption == "step_fen":
        step["fen"] = chess.STARTING_FEN
    elif corruption == "missing_step":
        row["moves"].extend(["c2d2", "d1d2"])
    elif corruption == "extra_step":
        row["step_grades"].append(deepcopy(step))
    elif corruption == "illegal_grade":
        step["grade_by_uci"]["a1a8"] = {"verdict": "UNDERSTOOD", "cp_loss": 0, "eval_after_cp": 0}
    elif corruption == "malformed_grade":
        step["grade_by_uci"]["d3d2"]["verdict"] = "email@example.test"
    elif corruption == "missing_solution":
        del step["grade_by_uci"]["d3d2"]
    report = audit.build_report([stamp(row)], derive_reasons=True)
    assert report["counts"]["invalid_stored_contract"] == 1
    assert report["move_verdict_by_destination_safety"] == {}


def test_duplicate_positions_are_counted_as_occurrences_not_independent_cases():
    first = fixture(all_legal=False)
    second = deepcopy(first)
    second["puzzle_id"] = "different-id-same-position"
    report = audit.build_report([first, stamp(second)], derive_reasons=True)
    assert report["counts"]["stored_candidate_occurrences"] == 2
    assert report["counts"]["distinct_position_move_pairs"] == 1
    assert report["counts"]["repeated_position_move_occurrences"] == 1


def test_authorization_cannot_be_bypassed(monkeypatch):
    monkeypatch.setattr(audit, "is_authorized", lambda *_: False)
    monkeypatch.setattr(audit, "build_reason_bundle_for_move", lambda **_: pytest.fail("unauthorized"))
    report = audit.build_report([fixture(all_legal=False)], derive_reasons=True)
    assert report["counts"]["reason_authorization_blocked"] == 1


def test_aggregate_output_never_includes_raw_content_or_arbitrary_labels():
    row = fixture(all_legal=False)
    row.update({"concept": "someone@example.test", "game_url": "https://private.example/id",
                "user_id": "private-user", "comment": "private text"})
    report = audit.build_report([row], derive_reasons=True)
    rendered = json.dumps(report)
    for forbidden in (row["fen"], row["puzzle_id"], "d3d2", "someone@example.test",
                      "private.example", "private-user", "private text"):
        assert forbidden not in rendered
    assert report["concept_counts"] == {"unknown": 1}


def test_reviewed_rook_example_full_question_round_trip_and_legal_demonstration():
    """Existing local gold only, not a new onboarding assignment or engine claim."""
    case = GOLD[0]
    bundle = audit.build_reason_bundle_for_move(
        fen_before=case["fen"], submitted_move=case["move_uci"], quality_id=audit.QUALITY_ID,
    )
    restored = TeachingReasonBundle.from_private_dict(bundle.private_dict())
    assert restored == bundle
    for index, component in enumerate(restored.components):
        public = restored.question(index)
        assert "accepted_choice_ids" not in json.dumps(public)
        assert "success_text" not in json.dumps(public)
        for choice in component.choices:
            result = restored.grade_component(index=index, question_id=component.question_id,
                                             selected_choice_id=choice.choice_id)
            assert result["correct"] == (choice.choice_id in component.accepted_choice_ids)
            assert result["feedback"]
        with pytest.raises(ReasonContractViolation):
            restored.grade_component(index=index, question_id="another-question",
                                     selected_choice_id=component.accepted_choice_ids[0])
    assert restored.question(len(restored.components)) is None
    calculation = next(c for c in restored.components if c.kind == "one_recapture_calculation")
    board = chess.Board(case["fen"])
    for uci in (case["move_uci"], calculation.facts["capture_uci"], calculation.facts["recapture_uci"]):
        move = chess.Move.from_uci(uci)
        assert move in board.legal_moves
        board.push(move)
    assert board.piece_at(chess.D2) == chess.Piece(chess.ROOK, chess.WHITE)
    assert not board.pieces(chess.QUEEN, chess.BLACK)
    assert board.piece_at(chess.D1) is None


def test_read_error_does_not_emit_a_fake_empty_report(monkeypatch, capsys):
    import pymongo
    def fail(*args, **kwargs):
        raise RuntimeError("private credentials must not print")
    monkeypatch.setenv("MONGO_URL", "mongodb://private")
    monkeypatch.setattr(pymongo, "MongoClient", fail)
    assert audit.main([]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "audit_failed"
    assert "counts" not in result
    assert "credentials" not in json.dumps(result)


def test_cli_only_reads_allowlisted_fields_and_labels_limited_scan(monkeypatch, capsys):
    import pymongo
    class Cursor:
        def sort(self, field, direction):
            assert (field, direction) == ("_id", 1)
            return self
        def limit(self, value):
            assert value == 1
            return self
        def __iter__(self):
            return iter([fixture(all_legal=False)])
    class Pool:
        def count_documents(self, query):
            assert query == {}
            return 10
        def find(self, query, projection):
            assert query == {}
            assert projection["_id"] == 0
            assert not {"user_id", "game_id", "game_url", "email"} & projection.keys()
            return Cursor()
    class Client:
        closed = False
        def __init__(self, *args, **kwargs):
            pass
        def __getitem__(self, key):
            assert key == "test_read_only"
            return type("Database", (), {"diagnostic_pool": Pool()})()
        def close(self):
            Client.closed = True
    monkeypatch.setattr(pymongo, "MongoClient", Client)
    monkeypatch.setenv("MONGO_URL", "mongodb://test")
    monkeypatch.setenv("DB_NAME", "test_read_only")
    assert audit.main(["--limit", "1"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["scan_scope"] == "limited"
    assert result["collection_count_at_start"] == 10
    assert result["counts"]["rows_scanned"] == 1
    assert Client.closed


def test_answer_position_is_not_fixed_across_reviewed_cases():
    reports = [audit.build_report([fixture(i, all_legal=False)], derive_reasons=True)
               for i in range(len(GOLD))]
    slots = {slot for report in reports for slot in report["accepted_answer_slot_counts_zero_based"]}
    assert slots == {"0", "1"}

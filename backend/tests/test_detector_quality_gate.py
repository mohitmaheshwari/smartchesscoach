import chess

from services import detector_quality as quality
from services.concept_detectors import _runner
from services import shape_layer
from services.shape_detectors import _DETECTORS
from services.shape_patterns import PATTERNS_BY_ID
from scripts.report_detector_quality import build_report


def test_unknown_ids_are_shadow_but_rollout_is_default_off(monkeypatch):
    monkeypatch.delenv("DETECTOR_QUALITY_GATE_ENFORCED", raising=False)
    assert quality.grade_for("shape:new_pattern") == quality.QualityGrade.SHADOW
    assert quality.can_influence(
        "shape:new_pattern", quality.QualitySurface.CAPTION
    )


def test_enforcement_fails_closed_and_plan_grade_reaches_plan(monkeypatch):
    monkeypatch.setenv("DETECTOR_QUALITY_GATE_ENFORCED", "true")
    assert not quality.can_influence(
        "shape:new_pattern", quality.QualitySurface.CAPTION
    )
    simple_hang = quality.gap_quality_id("piece_safety", "simple_hang")
    assert quality.can_influence(simple_hang, quality.QualitySurface.PLAN)
    assert quality.can_influence(simple_hang, quality.QualitySurface.CAPTION)


def test_disabled_detector_stays_blocked_when_rollout_is_off(monkeypatch):
    monkeypatch.delenv("DETECTOR_QUALITY_GATE_ENFORCED", raising=False)
    assert not quality.can_influence(
        quality.concept_quality_id("endgame_rule_of_square"),
        quality.QualitySurface.MASTERY,
    )
    assert not quality.can_influence(
        quality.principle_quality_id("END_RULE_OF_SQUARE"),
        quality.QualitySurface.CAPTION,
    )


def test_plan_sanitizer_keeps_evidence_but_hides_shadow_gap(monkeypatch):
    monkeypatch.setenv("DETECTOR_QUALITY_GATE_ENFORCED", "true")
    raw = {
        "game_id": "g1",
        "missed_pattern": "king_safety",
        "subtype": "ignored_king_attack",
        "severity": "critical",
        "cp_loss": 220,
    }
    safe = quality.sanitize_plan_observation(raw)
    assert safe["missed_pattern"] is None
    assert safe["subtype"] is None
    assert safe["cp_loss"] == 220
    assert safe["detector_quality_shadow"]["gap"]["missed_pattern"] == "king_safety"


def test_plan_sanitizer_keeps_promoted_simple_hang(monkeypatch):
    monkeypatch.setenv("DETECTOR_QUALITY_GATE_ENFORCED", "true")
    raw = {
        "missed_pattern": "piece_safety",
        "subtype": "simple_hang",
        "severity": "critical",
    }
    safe = quality.sanitize_plan_observation(raw)
    assert safe["missed_pattern"] == "piece_safety"
    assert safe["subtype"] == "simple_hang"


def test_legacy_focus_fails_closed_but_versioned_pic_focus_passes(monkeypatch):
    monkeypatch.setenv("DETECTOR_QUALITY_GATE_ENFORCED", "true")
    assert not quality.focus_document_is_authorized(
        {"topic_key": "king_safety", "status": "active"}
    )
    assert quality.focus_document_is_authorized({
        "topic_key": "piece_safety",
        "focus_kind": "piece_safety/simple_hang",
        "diagnosis_detector_id": "move_observation.simple_hang.v16_plus",
    })


def test_mastery_runner_keeps_shadow_diagnostics_out_of_product(monkeypatch):
    monkeypatch.setenv("DETECTOR_QUALITY_GATE_ENFORCED", "true")
    monkeypatch.setattr(
        _runner,
        "all_detectors",
        lambda: {"new_skill": lambda board, move, color: "applied"},
    )
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")
    assert _runner.run_detectors_for_move(board, move, chess.WHITE) == []
    assert _runner.run_detectors_for_move(
        board, move, chess.WHITE, include_shadow=True
    ) == [("new_skill", "applied")]


def test_disabled_mastery_detector_does_not_execute(monkeypatch):
    monkeypatch.delenv("DETECTOR_QUALITY_GATE_ENFORCED", raising=False)
    called = []

    def detector(board, move, color):
        called.append(True)
        return "applied"

    monkeypatch.setattr(
        _runner,
        "all_detectors",
        lambda: {"endgame_rule_of_square": detector},
    )
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")
    assert _runner.run_detectors_for_move(
        board, move, chess.WHITE, include_shadow=True
    ) == []
    assert called == []


def test_shape_selection_is_safe_when_enforced(monkeypatch):
    candidate = {
        "pattern_id": "knight_fork",
        "mover": "f3",
        "targets": ["e5", "g5"],
        "executing_move": "g1f3",
        "evidence": "test",
    }
    monkeypatch.setattr(shape_layer, "detect_all_shapes", lambda *a, **k: [candidate])
    monkeypatch.setattr(
        shape_layer, "_is_relevant_to_move", lambda *a, **k: True
    )
    monkeypatch.setattr(shape_layer, "verify_dynamics", lambda items, *a: items)
    monkeypatch.setattr(
        shape_layer, "verify_with_engine_data", lambda items, *a: items
    )
    monkeypatch.setenv("DETECTOR_QUALITY_GATE_ENFORCED", "true")
    assert shape_layer.select_shape_for_position(chess.Board()) is None
    monkeypatch.setenv("DETECTOR_QUALITY_GATE_ENFORCED", "false")
    assert (
        shape_layer.select_shape_for_position(chess.Board())["pattern_id"]
        == "knight_fork"
    )


def test_shape_catalog_dispatch_has_only_documented_special_case():
    reachable = set(_DETECTORS) | {"in_between_move"}
    assert set(PATTERNS_BY_ID) - reachable == set()
    # clearance_then_check is an internal follow-up recognizer consumed by
    # pattern_catalog; it is not a player-facing shape catalog entry.
    assert reachable - set(PATTERNS_BY_ID) == {"clearance_then_check"}


def test_authorization_report_covers_every_major_registry():
    report = build_report()
    ids = {row["quality_id"] for row in report["detectors"]}
    assert "gap:piece_safety:simple_hang" in ids
    assert "concept:endgame_rule_of_square" in ids
    assert "shape:knight_fork" in ids
    assert "principle:TAC_FORK_PATTERN" in ids
    assert "brain:fork_detector" in ids
    assert sum(report["summary"].values()) == len(ids)


def test_authorization_report_explains_measured_shadow_detectors():
    report = build_report()
    rows = {row["quality_id"]: row for row in report["detectors"]}

    free_piece = rows["shape:free_piece"]
    assert free_piece["grade"] == "shadow"
    assert free_piece["explicit_authorization"] is True
    assert free_piece["evidence_ref"].endswith(
        "detector_exchange_truth_lock_2026_08_27.md"
    )
    assert free_piece["limitations"]

    unknown = rows["shape:knight_fork"]
    assert unknown["explicit_authorization"] is False
    assert "No reviewed promotion packet" in unknown["rationale"]

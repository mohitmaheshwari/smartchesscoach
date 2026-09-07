import json
from pathlib import Path

from scripts.measure_forced_mate_caption_promotion import (
    independent_adjudication,
)
from services.detector_quality import (
    QualityGrade,
    QualitySurface,
    get_authorization,
    is_authorized,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT
    / "data"
    / "detector_gold"
    / "forced_mate_exact_caption_promotion_v1.json"
)
MATE_BOARD = "6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1"


def _row(**overrides):
    row = {
        "fen": MATE_BOARD,
        "played_move": "Ra2",
        "best_move_uci": "h1g1",
        "cp_loss": 300,
        "pv_after_best": ["Kg1", "Kh8", "Ra8#"],
    }
    row.update(overrides)
    return row


def test_independent_gold_replays_longer_line_and_names_terminal_board():
    gold = independent_adjudication(_row())
    assert gold["status"] == "exact"
    assert gold["subtype"] == "longer_line"
    assert gold["replayed_uci"] == ["h1g1", "g8h8", "a1a8"]
    assert gold["mating_move_san"] == "Ra8#"
    assert gold["mating_piece"] == "rook"
    assert gold["mating_square"] == "a8"
    assert gold["king_square"] == "h8"
    assert gold["terminal_legal_replies"] == 0


def test_independent_gold_rejects_false_missed_mate_and_incomplete_evidence():
    assert independent_adjudication(
        _row(played_move="Kg1")
    )["reason"] == "played_best_move"
    assert independent_adjudication(
        _row(cp_loss=None)
    )["reason"] == "invalid_consequence"
    assert independent_adjudication(
        _row(pv_after_best=["Kg1", "Kh8"])
    )["reason"] == "line_does_not_end_in_checkmate"
    assert independent_adjudication(
        _row(pv_after_best=["Kg1", "Kh8", "Ra8#", "a1a1"])
    )["reason"] == "moves_after_checkmate"


def test_manifest_records_passing_aggregate_gate_without_case_export():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["summary"]["caption_promotion_gate_passed"] is True
    assert payload["summary"]["true_positives"] == 50
    assert payload["summary"]["true_negatives"] == 50
    assert (
        payload["population"]["full_reproducible_matches"]
        == payload["population"]["reproducible_candidates"]
    )
    assert (
        payload["population"]["unreproducible_abstentions"]
        == payload["population"]["unreproducible_candidates"]
    )
    assert payload["population"]["fact_mismatches"] == 0
    assert payload["case_records_exported"] == 0
    serialized = json.dumps(payload).lower()
    assert '"fen"' not in serialized
    assert '"fires"' not in serialized
    assert '"negatives"' not in serialized
    assert '"source_key"' not in serialized


def test_authorization_is_caption_only():
    authorization = get_authorization("tactic:forced_mate_exact")
    assert authorization.grade == QualityGrade.CAPTION
    assert is_authorized(
        "tactic:forced_mate_exact", QualitySurface.CAPTION
    )
    assert not is_authorized(
        "tactic:forced_mate_exact", QualitySurface.PROMPT
    )
    assert not is_authorized(
        "tactic:forced_mate_exact", QualitySurface.PLAN
    )
    assert not is_authorized(
        "tactic:forced_mate_exact", QualitySurface.MASTERY
    )
    assert "missing consequence evidence" not in authorization.rationale
    assert "reproducible from its stored puzzle document" in (
        authorization.rationale
    )
    assert any(
        "source game analysis" in limitation
        and "zero-violation gate" in limitation
        for limitation in authorization.limitations
    )


def test_independent_measurement_has_no_canonical_or_runtime_dependency():
    source = (
        ROOT / "scripts" / "measure_forced_mate_caption_promotion.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "missed_mate_detector",
        "forced_mate_puzzle_proof",
        "stored_line_verifier",
        "verified_puzzle_admission",
        "StockfishEngine",
        "stockfish_service",
        "call_llm",
        "httpx",
        "requests.",
    )
    assert not any(token in source for token in forbidden)


def test_packet_builder_defaults_to_aggregate_output():
    source = (
        ROOT / "scripts" / "build_forced_mate_caption_promotion_packet.py"
    ).read_text(encoding="utf-8")
    assert 'os.environ.get("FORCED_MATE_INCLUDE_CASES") != "1"' in source
    assert '"case_records_exported": 0' in source
    assert "len(reproducible) == 261" not in source
    assert "len(unreproducible) == 3" not in source
    assert "== {1, 3, 5}" not in source

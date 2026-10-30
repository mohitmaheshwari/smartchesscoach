"""True relations need source, stability and best-reply relevance for coaching."""
from dataclasses import asdict

import chess
import pytest

from services.reasoning.contracts import SearchRecord, Hypothesis
from services.reasoning.engine import explain_fen
from services.reasoning.objectives import admit_fact, common_prefix
from services.reasoning.timeline import build_timeline, event_facts
from services.reasoning.verify import verify_dependencies
from test_reasoning_boundaries import config, score
from test_reasoning_review_regressions import QUIET, QuietSearch
from scripts.review_reasoning_policy import requests_from_review, freeze_record


def evidence():
    moves = ["g1f3", "b8c6", "f1g2", "e8g8", "e1g1"]
    line = build_timeline(chess.Board(QUIET), moves, "stable", 18)
    line["source_query"] = {"purpose": "alternative_stability", "root_moves": [moves[0]], "start_ply": 0}
    fact = asdict(next(p for p in event_facts(line) if p.ply == 3 and p.relation == "reaches"))
    base = SearchRecord("base", "alternative", QUIET, [moves[0]], 100, 1, "complete_iteration",
                        lines=[{"moves_uci": moves, "depth": 14}])
    stable = SearchRecord("stable", "alternative_stability", QUIET, [moves[0]], 200, 1, "complete_iteration",
                          lines=[{"moves_uci": moves, "depth": 16}])
    ref = SearchRecord("reference", "coaching_best_reply_depth20", line["nodes"][1]["fen"], [], 500, 1, "complete_iteration",
                       lines=[{"moves_uci": moves[1:], "depth": 20}])
    return fact, line, base, stable, ref


def test_later_fact_requires_an_unrestricted_depth20_best_reply():
    fact, line, base, stable, ref = evidence()
    assert admit_fact(fact, line, line, base, stable, ref)["admitted"]
    ref.root_moves = [chess.Move.from_uci("b8c6").uci()]
    assert not admit_fact(fact, line, line, base, stable, ref)["admitted"]


@pytest.mark.parametrize("depth", [0, 16, 19])
def test_unfinished_reference_is_not_silently_treated_as_depth20(depth):
    fact, line, base, stable, ref = evidence()
    ref.lines[0]["depth"] = depth
    assert admit_fact(fact, line, line, base, stable, ref)["reason"] == "opponent_reference_depth_not_reached"


def test_agreement_is_clipped_by_the_fresh_best_reply_not_just_the_two_root_pvs():
    fact, line, base, stable, ref = evidence()
    ref.lines[0]["moves_uci"] = ["e5e4"]
    result = admit_fact(fact, line, line, base, stable, ref)
    assert result["agreement_plies"] == 1
    assert not result["admitted"]


def test_later_fact_outside_base_stability_agreement_is_rejected():
    fact, line, base, stable, ref = evidence()
    base.lines[0]["moves_uci"] = ["g1f3", "e5e4"]
    assert not admit_fact(fact, line, line, base, stable, ref)["admitted"]


def test_forced_bishop_sacrifice_cannot_supply_a_coaching_resource():
    fact, primary, base, stable, ref = evidence()
    line = build_timeline(chess.Board(QUIET), ["g1f3", "c5f2", "e1f2", "e5e4"], "forced", 18)
    line["source_query"] = {"purpose": "forcing_counterexample", "root_moves": ["c5f2"], "start_ply": 1}
    attack = asdict(next(p for p in event_facts(line) if p.relation == "attacks_piece" and p.data["move"] == "e4"))
    decision = admit_fact(attack, line, primary, base, stable, ref)
    assert decision["reason"] == "forced_opponent_root"
    assert not decision["admitted"]


def test_immediate_root_fact_needs_no_claim_about_later_replies():
    _, line, base, stable, _ = evidence()
    fact = asdict(next(p for p in event_facts(line) if p.relation == "legal_move"))
    assert admit_fact(fact, line, line, base, stable, None)["admitted"]


def test_common_prefix_has_no_unmeasured_fixed_ply_cutoff():
    assert common_prefix(list(range(18)), list(range(18))) == 18
    assert common_prefix([1, 2, 3], [1, 4, 3]) == 1


ROOK = "2q5/4kp1p/p2pb1p1/4p3/Qp6/1P6/P1r2PPP/R1R3K1 w - - 2 25"


class CaptureSearch(QuietSearch):
    def query(self, board, purpose, *, roots=(), width=1, nodes=None):
        record = SearchRecord(str(len(self.records)), purpose, board.fen(), [m.uci() for m in roots], nodes or 100, width, "unavailable")
        if board.fen() == ROOK:
            paths = {"c1e1": ["c1e1", "c8c5", "e1f1"], "c1c2": ["c1c2", "c8c2", "a4b4"], "a4b4": ["a4b4", "c2c1", "a1c1"]}
            values = {"c1e1": -369, "c1c2": 244, "a4b4": -14}
            keys = [m.uci() for m in roots] if roots else ["c1c2", "a4b4"]
            record.lines = [{"root_uci": key, "moves_uci": paths[key], "score": score(values[key])} for key in keys]
            record.status = "complete_iteration"
        self.records.append(record)
        return record


def test_rook_capture_contrast_uses_the_root_eval_gap_and_leads_the_text(monkeypatch):
    monkeypatch.setattr("services.reasoning.engine.SearchSession", CaptureSearch)
    result = explain_fen(ROOK, "Re1", config=config())
    chosen = result["selected_teaching_point"]
    assert chosen["objective"]["root_capture_contrast"]["comparisons"][-1]["gap_cp"] == 613
    assert result["coaching"]["text"].startswith("Rxc2 takes Black's rook on c2")
    assert "Re1" in result["coaching"]["text"]
    assert "f2" not in result["coaching"]["text"]
    assert "engine score" not in result["coaching"]["text"]
    assert "6.13" not in result["coaching"]["text"]
    assert result["sentence_admission"] and all(s["admitted"] for s in result["sentence_admission"])


@pytest.mark.parametrize("field", ["gap_cp", "best_score", "played_root_uci"])
def test_root_capture_contrast_cannot_invent_a_gap_or_wrong_branch(monkeypatch, field):
    monkeypatch.setattr("services.reasoning.engine.SearchSession", CaptureSearch)
    result = explain_fen(ROOK, "Re1", config=config())
    h = Hypothesis(**result["selected_teaching_point"])
    obj = h.objective["root_capture_contrast"]
    if field == "gap_cp":
        obj["comparisons"][0][field] = 999
    elif field == "best_score":
        obj["comparisons"][0][field]["value"] = 999
    else:
        obj[field] = "a4b4"
    assert verify_dependencies(h, {p['id']: p for p in result['propositions']},
        {t['id']: t for t in result['timelines']}, {s['id']: s for s in result['searches']})


def test_review_runner_never_passes_gold_metadata_to_the_engine():
    rows = [{"id": "example", "fen": ROOK, "played_move": "Re1", "best_san": "Rxc2", "cp_loss": 481,
             "gap": "missed_tactic", "game_id": "private", "same_origin": True}]
    manifest = requests_from_review(rows)
    assert manifest["cases"] == [{"id": "example", "fen": ROOK, "played_move": "Re1"}]
    assert "disclosed" in manifest["exposure"]


def test_freeze_binds_original_inputs_engine_and_source_hashes(tmp_path):
    source, engine = tmp_path / "input.json", tmp_path / "engine"
    source.write_text("[]")
    engine.write_bytes(b"engine fixture; never executed")
    settings = config(engine_path=str(engine))
    first = freeze_record(source, settings)
    assert first == freeze_record(source, settings)
    source.write_text("[{}]")
    assert first != freeze_record(source, settings)
    assert first["source_hashes"]

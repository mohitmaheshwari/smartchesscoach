"""The why button's differential path keeps the endpoint's contract and is off by default."""
from __future__ import annotations

import importlib

import chess

from services import why_differential


def test_disabled_by_default_and_budget_is_bounded(monkeypatch):
    monkeypatch.delenv("WHY_DIFFERENTIAL_ENABLED", raising=False)
    module = importlib.reload(why_differential)
    assert module.WHY_DIFFERENTIAL_ENABLED is False
    cfg = module.button_config("unused-by-this-test")
    assert cfg.nodes == cfg.stability_nodes          # one allocation per probe on a button press
    assert cfg.max_queries == 8 and cfg.max_total_nodes == 8 * cfg.nodes
    assert cfg.engine_path == "unused-by-this-test"


def test_found_result_is_shaped_like_the_existing_answer():
    result = {
        "found": True, "direction": "received", "mechanism": "LOST_GUARD", "family": "punished", "class": "mistake",
        "gap_cp": 184, "better_move": "f3", "text": "c4 moved the pawn that was guarding d4, so c5 hits your pawn on d4 with nothing defending it.",
        "played_branch": {"reply_san": "c5", "drop_cp": 142},
        "line_san": ["c4", "c5", "cxd5"], "arrows": [{"from": "c3", "to": "c4", "san": "c4"}, {"from": "c7", "to": "c5", "san": "c5"}],
        "causes": [{"kind": "lost_guard", "text": "c4 moved the pawn that was guarding d4, so c5 hits your pawn on d4 with nothing defending it."}],
        "consequence": None, "shared_consequence": None, "facts": {"the_move_played": "c4"}, "runtime": {"wall_ms": 9400.0},
    }
    out = why_differential.to_response(result)
    for key in ("found", "direction", "mechanism", "text", "move_san", "line_san", "arrows", "candidate_rank",
                "eval_gap_cp", "payoff_cp", "punishment"):
        assert key in out                            # what GameDecryptionV5.jsx already reads
    assert out["found"] is True and out["move_san"] == "c5" and out["engine"] == "differential"
    assert out["better_move"] == "f3" and out["causes"] == [result["causes"][0]["text"]]
    assert out["differential"]["family"] == "punished" and out["differential"]["runtime_ms"] == 9400.0


def test_missed_answer_points_at_the_better_move():
    result = {"found": True, "direction": "missed", "mechanism": "FORK", "family": "missed", "class": "blunder",
              "gap_cp": 332, "better_move": "Nd5", "text": "Nd5 attacks two things at once.", "played_branch": {"reply_san": "Bxe2"},
              "line_san": ["Nd5"], "arrows": [], "causes": [], "consequence": {"payoff_cp": None}, "facts": {}}
    out = why_differential.to_response(result)
    assert out["move_san"] == "Nd5" and out["payoff_cp"] is None


def test_summary_of_a_silent_result_still_names_the_better_move():
    result = {"found": False, "reason": "no_mechanism", "family": "missed", "class": "mistake", "gap_cp": 122,
              "better_move": "Bd3", "played_branch": {"reply_san": "d5"}, "shared_consequence": None, "runtime": {"wall_ms": 5000.0}}
    s = why_differential.summary(result)
    assert s == {"engine": "differential", "found": False, "reason": "no_mechanism", "family": "missed",
                 "class": "mistake", "gap_cp": 122, "better_move": "Bd3", "reply_san": "d5",
                 "shared_consequence": None, "runtime_ms": 5000.0}


def test_the_old_paths_recapture_framing_is_recognised():
    # ho02: Nxf5 exf5 is a knight for a knight; the old path says "exf5 wins your knight".
    old = {"found": True, "direction": "received", "mechanism": "WINS_MATERIAL", "move_san": "exf5"}
    assert why_differential.old_answer_is_an_exchange(
        "1kqr1b1r/p1p1n1p1/1p3p1p/PNp2N2/2Q1P3/1P6/2P2PPP/R4RK1 b - - 0 21", "Nxf5", old) is True
    # A queen that takes a pawn and is taken back IS lost; that framing stands.
    board = chess.Board("1kqr1b1r/p1p1n1p1/1p3p1p/PNp2N2/2Q1P3/1P6/2P2PPP/R4RK1 b - - 0 21")
    assert why_differential.old_answer_is_an_exchange(board.fen(), "Nxf5", {"found": True, "direction": "missed",
                                                                            "mechanism": "WINS_MATERIAL", "move_san": "exf5"}) is False
    assert why_differential.old_answer_is_an_exchange(board.fen(), "Nxf5", None) is False
    assert "engine_choice" in why_differential.NO_FALLBACK_REASONS and "shared_consequence_only" in why_differential.NO_FALLBACK_REASONS


def test_explain_never_raises_for_a_bad_engine_path():
    out = why_differential.explain(chess.STARTING_FEN, "e4", engine_path="C:/definitely/not/an/engine.exe")
    assert out["found"] is False and out["reason"] == "engine_error"


def test_explain_reports_an_illegal_move_as_bad_input():
    out = why_differential.explain(chess.STARTING_FEN, "Ke2", engine_path="C:/definitely/not/an/engine.exe")
    assert out["found"] is False and out["reason"] == "bad_input"

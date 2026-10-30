"""Opt-in local Stockfish regressions; never use an API or production data.

CHESSGURU_TEST_STOCKFISH must explicitly name a local pinned executable.
"""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from services.reasoning.engine import explain_fen
from test_reasoning_boundaries import NA4, QF8, config
from test_reasoning_review_regressions import QUIET


ENGINE = os.environ.get("CHESSGURU_TEST_STOCKFISH")
pytestmark = pytest.mark.skipif(not ENGINE, reason="explicit local Stockfish path required")


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    assert Path(ENGINE).is_file()
    settings = config(engine_path=ENGINE, nodes=30000, stability_nodes=120000,
                      max_queries=32, max_total_nodes=2000000, rank_width=4, hash_mb=64)
    cases = [("na4", NA4, "Na4"), ("qf8", QF8, "Qf8"),
             ("nf3", QUIET, "Nf3"), ("e4", QUIET, "e4"),
             ("qa2", "7k/6pp/8/8/3b4/8/8/QK2R3 w - - 0 1", "Qa2"),
             ("na4_repeat", NA4, "Na4")]
    destination = tmp_path_factory.mktemp("reasoning_engine_regressions")
    outputs = {}
    for name, fen, played in cases:
        result = explain_fen(fen, played, config=settings)
        (destination / (name + ".json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"case": name, "text": result["coaching"]["text"],
                          "runtime": result["runtime"], "artifact": str(destination / (name + ".json"))}))
        outputs[name] = result
    return outputs


def test_real_engine_comparative_na4(results):
    result = results["na4"]
    assert result["selected_teaching_point"]["objective"]["kind"] == "comparative_sequence"
    assert "Na4 has no such checking capture" in result["coaching"]["text"]


def test_real_engine_comparative_qf8(results):
    result = results["qf8"]
    assert result["selected_teaching_point"]["objective"]["kind"] == "comparative_threat"
    assert "Qf8 adds no cover on f5" in result["coaching"]["text"]
    assert "avoids this immediate mating line" not in result["coaching"]["text"]
    # A named defence is optional; if rendered, its numerical cost is required.
    defence = result["selected_teaching_point"]["objective"]["defence_scope"]
    if defence.get("first_reply_san") in result["coaching"]["text"]:
        assert "engine score" in result["coaching"]["text"]


def test_real_engine_equivalent_move_describes_the_played_root(results):
    result = results["nf3"]
    assert result["context"]["comparison"] in ("equivalent", "played_is_best")
    assert result["selected_teaching_point"]["root_uci"] == "g1f3"
    assert "Nf3 moves the knight off g1" in result["coaching"]["text"]


def test_real_engine_later_black_e4_names_its_actor(results):
    result = results["e4"]
    for sentence in result["coaching"]["sentences"]:
        if sentence["frame"] == "attacks_piece" and "e4" in sentence["text"]:
            assert "Black" in sentence["text"] and "Later" in sentence["text"]


def test_real_engine_mate_one_is_a_lesson_over_mate_six(results):
    result = results["qa2"]
    assert result["context"]["comparison"] == "inferior"
    assert result["context"]["mate_comparison"]["best_in"] == 1
    assert result["context"]["mate_comparison"]["played_in"] > 1
    move = result["context"]["mate_comparison"]["best_san"]
    assert result["coaching"]["text"].count(move) == 1


def test_real_engine_queries_respect_budgets_and_facts_verify(results):
    for result in results.values():
        assert not result["invalid_propositions"]
        assert result["runtime"]["query_count"] <= 32
        assert result["runtime"]["requested_engine_nodes"] <= 2000000
        assert all("0000" not in line["moves_uci"] for line in result["timelines"])


def test_real_engine_na4_is_deterministic_outside_runtime(results):
    def strip_runtime(value):
        if isinstance(value, dict):
            return {k: strip_runtime(v) for k, v in value.items() if k != "runtime"}
        if isinstance(value, list):
            return [strip_runtime(v) for v in value]
        return value
    assert strip_runtime(deepcopy(results["na4"])) == strip_runtime(deepcopy(results["na4_repeat"]))

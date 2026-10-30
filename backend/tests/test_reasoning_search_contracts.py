"""Search boundaries use deterministic UCI fixtures; no engine install needed."""
from copy import deepcopy
import sys

import chess
import chess.engine

from services.reasoning.engine import explain_fen
from services.reasoning.search import SearchSession
from test_reasoning_boundaries import config
from test_reasoning_review_regressions import QUIET, QuietSearch


def session(tmp_path, **changes):
    binary = tmp_path / "engine-fixture"
    binary.write_bytes(b"not executed")
    return SearchSession(config(engine_path=str(binary), **changes), chess.BLACK, "history")


def test_budget_exhaustion_never_launches_a_process(tmp_path, monkeypatch):
    search = session(tmp_path, max_queries=1)
    search.executed_queries = 1
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda *a: (_ for _ in ()).throw(AssertionError("engine launched")))
    record = search.query(chess.Board(), "budget", roots=[chess.Move.from_uci("e2e4")])
    assert record.stop_reason == "query_or_node_budget_exhausted"
    assert not record.lines
    assert search.requested_nodes == 0


def test_total_requested_nodes_are_a_hard_gate(tmp_path):
    search = session(tmp_path, max_total_nodes=100)
    search.requested_nodes = 100
    assert not search.can_query()
    assert search.query(chess.Board(), "budget").actual_nodes == 0


def test_only_common_depth_unbounded_multipv_is_retained(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "psutil", None)
    e4, d4 = chess.Move.from_uci("e2e4"), chess.Move.from_uci("d2d4")
    score = lambda n: chess.engine.PovScore(chess.engine.Cp(n), chess.WHITE)
    rows = [dict(depth=5, multipv=1, pv=[e4], score=score(40), nodes=40),
            dict(depth=5, multipv=2, pv=[d4], score=score(35), nodes=60),
            dict(depth=6, multipv=1, pv=[e4], score=score(80), nodes=80, lowerbound=True),
            dict(depth=6, multipv=2, pv=[d4], score=score(45), nodes=100)]

    class Stream:
        multipv = [{"lowerbound": True}, {}]
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def __iter__(self): return iter(rows)

    class Engine:
        options, id = {}, {"name": "fixture"}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def configure(self, options): self.settings = options
        def analysis(self, board, limit, **kwargs):
            assert kwargs["multipv"] == 2 and limit.nodes == 100
            return Stream()

    launches = []
    def launch(path):
        launches.append(path)
        return Engine()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", launch)
    search = session(tmp_path)
    record = search.query(chess.Board(), "rank", width=2)
    assert record.status == "complete_iteration"
    assert [line["depth"] for line in record.lines] == [5, 5]
    assert [line["score"]["value"] for line in record.lines] == [-40, -35]
    assert all(line["score"]["pov"] == "black" for line in record.lines)
    assert search.query(chess.Board(), "reuse", width=2) is record
    assert len(launches) == search.executed_queries == 1
    assert search.requested_nodes == 100


def test_played_root_is_queried_before_ranking_even_outside_top_cap(monkeypatch):
    monkeypatch.setattr("services.reasoning.engine.SearchSession", QuietSearch)
    result = explain_fen(QUIET, "e4", config=config(root_cap=2))
    assert result["searches"][0]["root_moves"] == ["e2e4"]
    assert any(c["move_uci"] == "e2e4" and c["role"] == "played" for c in result["candidates"])


def test_complete_fixture_output_repeats_outside_runtime(monkeypatch):
    monkeypatch.setattr("services.reasoning.engine.SearchSession", QuietSearch)
    first = explain_fen(QUIET, "Nf3", config=config())
    second = explain_fen(QUIET, "Nf3", config=config())
    first, second = deepcopy(first), deepcopy(second)
    first.pop("runtime"), second.pop("runtime")
    assert first == second

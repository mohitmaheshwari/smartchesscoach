import ast
from pathlib import Path

from scripts.measure_whole_game_teaching_holdout_coverage import (
    DEFAULT_PACKET,
    DEFAULT_WORKSHEET,
    build_report,
)


BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = (
    BACKEND / "scripts/measure_whole_game_teaching_holdout_coverage.py"
)


def test_holdout_coverage_is_bound_and_uses_development_measure():
    report = build_report(DEFAULT_PACKET, DEFAULT_WORKSHEET)

    assert report["source"]["games"] == 42
    assert report["source"]["holdout_opened"] is True
    assert report["summary"]["gold_moments"] == 90
    assert len(report["moments"]) == 90
    assert report["execution_contract"]["engine_runs"] == 0
    assert report["execution_contract"]["model_calls"] == 0
    assert report["execution_contract"]["database_writes"] == 0

    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    locally_defined = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert "measure" not in locally_defined

from pathlib import Path
import sys

import chess

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from research.human_chess_intelligence.fathom_adapter import FathomEvidence
from scripts.audit_endgame_curriculum_with_fathom import audit_tree


def _tree(fen: str, san: str, uci: str):
    return {
        "category": {
            "lessons": {
                "lesson": {
                    "positions": [{"fen": fen, "correct_move_san": san, "correct_move_uci": uci}]
                }
            }
        }
    }


def _evidence(fen: str, *, winning=(), drawing=(), losing=(), wdl="Win"):
    return FathomEvidence(
        fen=fen,
        result="1-0",
        wdl=wdl,
        dtz=1,
        winning_moves_uci=winning,
        drawing_moves_uci=drawing,
        losing_moves_uci=losing,
    )


def test_audit_accepts_a_result_preserving_move_and_detects_alternatives():
    fen = "8/4k3/8/8/4K3/4P3/8/8 w - - 0 1"
    legal = tuple(move.uci() for move in chess.Board(fen).legal_moves)

    def probe(probe_fen):
        assert probe_fen == chess.Board(fen).fen()
        return _evidence(probe_fen, winning=("e4d5", "e4e5"), drawing=tuple(
            move for move in legal if move not in {"e4d5", "e4e5"}
        ))

    result = audit_tree(_tree(fen, "Kd5", "e4d5"), probe)
    finding = result["findings"][0]
    assert finding["status"] == "exact_preserves_result"
    assert finding["result_preserving_move_count"] == 2
    assert finding["authored_move_is_only_result_preserving"] is False


def test_audit_rejects_an_authored_move_that_changes_exact_result():
    fen = "8/4k3/8/8/4K3/4P3/8/8 w - - 0 1"
    legal = tuple(move.uci() for move in chess.Board(fen).legal_moves)

    def probe(probe_fen):
        return _evidence(
            probe_fen,
            winning=("e4d5",),
            drawing=tuple(move for move in legal if move != "e4d5"),
        )

    result = audit_tree(_tree(fen, "Kd3", "e4d3"), probe)
    assert result["findings"][0]["status"] == "exact_changes_result"


def test_audit_fails_before_probe_for_invalid_board_or_mismatched_move():
    calls = []
    invalid = audit_tree(_tree("8/8/8/8/8/8/4P3/4K3 w - - 0 1", "e4", "e2e4"), calls.append)
    assert invalid["findings"][0]["status"] == "invalid_board"
    assert not calls

    fen = "8/4k3/8/8/4K3/4P3/8/8 w - - 0 1"
    mismatch = audit_tree(_tree(fen, "Kd5", "e4f5"), calls.append)
    assert mismatch["findings"][0]["status"] == "san_uci_mismatch"
    assert not calls


def test_audit_marks_positions_above_coverage_without_probing():
    fen = "4k3/pp6/8/8/8/8/PP6/4K3 w - - 0 1"
    calls = []
    result = audit_tree(_tree(fen, "Kd2", "e1d2"), calls.append, maximum_men=5)
    assert result["findings"][0]["status"] == "outside_tablebase_coverage"
    assert not calls

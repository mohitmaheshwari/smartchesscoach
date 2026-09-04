"""Deterministic situation labels used by the Stage 4 gold audit."""
from __future__ import annotations

import os
import sys

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from scripts.audit_stage4_caption_corpus import classify  # noqa: E402


def test_delivered_mate_is_cleanly_classified():
    row = {
        "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq g3 0 2",
        "move_san": "Qh4#",
        "best_move_san": "Qh4#",
        "move_number": 2,
    }
    assert classify(row) == "delivered_mate"


def test_missed_profitable_capture_uses_legal_exchange_truth():
    row = {
        "fen_before": "7k/8/8/3p4/8/8/8/K2Q4 w - - 0 1",
        "move_san": "Ka2",
        "best_move_san": "Qxd5",
        "move_number": 1,
    }
    assert classify(row) == "missed_profitable_capture"


def test_endgame_position_is_separate_from_positional_residue():
    row = {
        "fen_before": "7k/8/8/8/8/8/4P3/4K3 w - - 0 1",
        "move_san": "Kf2",
        "best_move_san": "Kf2",
        "move_number": 40,
    }
    assert classify(row) == "endgame_position"


def test_bad_position_data_is_explicitly_deferred():
    assert classify({"fen_before": "bad", "move_san": "Qx"}) == "invalid_or_missing_position"

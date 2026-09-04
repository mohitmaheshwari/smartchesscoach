from datetime import datetime, timezone
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.audit_puzzle_stage3_data import (
    normalize_outcome,
    parse_timestamp,
    support_state,
    target_move_uci,
)


def test_outcome_normalization_rejects_conflicting_dual_schema():
    assert normalize_outcome({"correct": True}) == (True, "correct")
    assert normalize_outcome({"solved": False}) == (False, "solved")
    assert normalize_outcome({"correct": True, "solved": False}) == (None, "conflicting")
    assert normalize_outcome({}) == (None, "missing")


def test_support_state_never_calls_absence_independent():
    assert support_state({}) == "support_unknown"
    assert support_state({"support_level": "none"}) == "independent"
    assert support_state({"used_hint": True}) == "assisted"
    assert support_state({"hint_count": 2}) == "assisted"


def test_timestamp_accepts_bson_and_iso_but_not_missing():
    aware = datetime(2026, 8, 31, tzinfo=timezone.utc)
    assert parse_timestamp({"created_at": aware}) == aware
    assert parse_timestamp({"attempted_at": "2026-08-31T01:02:03Z"}) is not None
    assert parse_timestamp({}) is None


def test_target_move_accepts_legal_uci_or_san():
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    assert target_move_uci({"fen": fen, "best_move_uci": "e2e4"}) == "e2e4"
    assert target_move_uci({"fen": fen, "best_move_san": "Nf3"}) == "g1f3"
    assert target_move_uci({"fen": fen, "best_move_uci": "e7e5"}) is None

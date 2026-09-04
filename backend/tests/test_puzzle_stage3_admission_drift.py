from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.audit_puzzle_stage3_admission_drift import summarize


def _row(baseline, confirmation=None, loss=None):
    return {
        "baseline_preserves_wdl": baseline,
        "confirmation_preserves_wdl": confirmation,
        "confirmation_acceptable_loss_cp": loss,
    }


def test_summary_separates_resolved_and_confirmed_mismatches():
    result = summarize([
        _row(True),
        _row(False, True, 4),
        _row(False, False, 86),
    ])
    assert result["positions"] == 3
    assert result["baseline_mismatches"] == 2
    assert result["resolved_at_confirmation_depth"] == 1
    assert result["confirmed_wdl_mismatches"] == 1
    assert result["confirmed_mismatch_rate"] == 1 / 3
    assert result["confirmed_acceptable_move_loss_cp"]["median"] == 86


def test_summary_handles_no_mismatches():
    result = summarize([_row(True), _row(True)])
    assert result["baseline_wdl_preservation_rate"] == 1.0
    assert result["confirmation_rechecks"] == 0
    assert result["confirmed_mismatch_rate"] == 0.0
    assert result["confirmed_acceptable_move_loss_cp"]["median"] is None

"""A quarantined puzzle cannot be a version-provenance violation.

The destination-safety v2 re-grade refuses to write unless
strict_violations == 0. It counted any destination-safety row whose rebuilt
verdict lacked the v2/v2 pair -- including QUARANTINE verdicts.

community_training_positions holds one such row from 2026-04-19
(63a10df2-15d5-4a21-a55e-0fd2350bc809_m12). Its FEN does not reconstruct
("stored_fen_mismatch"), so it re-grades to quarantine every time and can
never acquire a v2 pair. With it counted, the gate was permanently
unpassable and the migration could never run.

A quarantine verdict deliberately has no playable answer and is excluded from
every pool regardless of its versions, so it cannot leak v1 provenance into
anything. It is counted separately now, not as a violation.
"""
import io
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND / "scripts" / "backfill_verified_puzzle_admission.py"


def _source() -> str:
    return io.open(SCRIPT, encoding="utf-8").read()


def test_quarantine_is_excluded_from_strict_violations():
    src = _source()
    assert (
        "strict_violations += int(not current_pair and not quarantined)" in src
    ), "a quarantined row still blocks the re-grade gate forever"


def test_quarantine_is_still_counted_and_visible():
    """Excluded from the gate, but never hidden from the operator."""
    src = _source()
    assert '"destination_v2_quarantined"' in src, (
        "quarantined rows must still appear in the reconciliation so an "
        "operator can see what was skipped and why"
    )


def test_a_genuine_mixed_pair_still_blocks_the_gate():
    """The safety property this gate exists for must survive the fix."""
    src = _source()
    start = src.index("strict_violations += int(")
    line = src[start:src.index("\n", start)]
    assert "not current_pair" in line, (
        "a non-quarantine row without the v2/v2 pair must still count as a "
        "violation -- that is the whole point of the gate"
    )


def test_the_gate_still_aborts_before_writes():
    src = _source()
    assert "if apply and not gate_passed:" in src
    assert "aborted before writes" in src, (
        "the gate must still refuse to write when it does not pass"
    )

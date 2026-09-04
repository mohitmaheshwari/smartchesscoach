"""The research Fathom adapter fails closed on incomplete exact evidence."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.human_chess_intelligence.fathom_adapter import (  # noqa: E402
    FathomAdapterError,
    parse_fathom_output,
)


FEN = "8/8/8/8/8/8/2P5/K1k5 b - - 0 1"
OUTPUT = f'''[Event ""]
[Result "1/2-1/2"]
[FEN "{FEN}"]
[WDL "Draw"]
[DTZ "0"]
[WinningMoves ""]
[DrawingMoves "Kxc2"]
[LosingMoves "Kd1, Kd2"]

1... Kxc2 2. Ka2 Kc1 1/2-1/2
'''


def test_parses_exact_result_and_complete_legal_move_partition():
    evidence = parse_fathom_output(FEN, OUTPUT)
    assert evidence.wdl == "Draw"
    assert evidence.dtz == 0
    assert evidence.drawing_moves_uci == ("c1c2",)
    assert set(evidence.losing_moves_uci) == {"c1d1", "c1d2"}
    assert set(evidence.move_partition) == {"c1c2", "c1d1", "c1d2"}


def test_rejects_output_for_a_different_position():
    with pytest.raises(FathomAdapterError, match="different FEN"):
        parse_fathom_output(FEN, OUTPUT.replace(FEN, "8/8/8/8/8/8/2P5/K2k4 b - - 0 1"))


def test_rejects_a_missing_legal_move():
    incomplete = OUTPUT.replace('LosingMoves "Kd1, Kd2"', 'LosingMoves "Kd1"')
    with pytest.raises(FathomAdapterError, match="do not partition"):
        parse_fathom_output(FEN, incomplete)


def test_rejects_overlapping_move_buckets():
    overlapping = OUTPUT.replace('WinningMoves ""', 'WinningMoves "Kxc2"')
    with pytest.raises(FathomAdapterError, match="overlap"):
        parse_fathom_output(FEN, overlapping)


def test_rejects_invalid_san_and_missing_headers():
    with pytest.raises(FathomAdapterError, match="invalid SAN"):
        parse_fathom_output(FEN, OUTPUT.replace("Kxc2", "Kc8"))
    with pytest.raises(FathomAdapterError, match="missing headers"):
        parse_fathom_output(FEN, OUTPUT.replace('[DTZ "0"]\n', ""))

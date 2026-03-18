import sys

import pytest

sys.path.insert(0, '/app/backend')

from services.opening_correction_service import parse_corrected_moves


def test_parse_corrected_moves_from_san_text():
    moves = parse_corrected_moves(None, "1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 Nf6")
    assert moves == ["e4", "c5", "Nf3", "e6", "d4", "cxd4", "Nxd4", "Nf6"]


def test_parse_corrected_moves_from_pgn():
    pgn = """[Event \"Test\"]\n\n1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 Nf6 *"""
    moves = parse_corrected_moves(pgn, None)
    assert moves == ["e4", "c5", "Nf3", "e6", "d4", "cxd4", "Nxd4", "Nf6"]


@pytest.mark.asyncio
async def test_opening_correction_endpoint_data_can_drive_siberian_override():
    corrected_moves = parse_corrected_moves(
        None,
        "e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nf6 Nc3 Bb4 e5 Qa5 exf6 Bxc3+ Bd2 Bxd2+ Qxd2 Qxd2+"
    )
    assert corrected_moves[-1] == "Qxd2+"
import ast
import json
from pathlib import Path

import pytest

from scripts.adjudicate_whole_game_teaching_holdout import (
    EXPECTED_PACKET_SHA256,
    build_holdout_worksheet,
)


BACKEND = Path(__file__).resolve().parents[1]
PACKET = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_holdout_packet_v1.json"
)
SCRIPT = BACKEND / "scripts/adjudicate_whole_game_teaching_holdout.py"


def test_holdout_wrapper_is_bound_and_uses_the_frozen_adjudicator():
    packet = json.loads(PACKET.read_text(encoding="utf-8-sig"))
    worksheet = build_holdout_worksheet(
        packet,
        packet_sha256=EXPECTED_PACKET_SHA256,
    )

    assert worksheet["evaluation_kind"] == "one_time_unseen_holdout"
    assert worksheet["source"]["games"] == 42
    assert worksheet["summary"]["games"] == 42
    assert len(worksheet["games"]) == 42

    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    locally_defined = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert "adjudicate_game" not in locally_defined


def test_holdout_wrapper_refuses_a_different_packet_hash():
    packet = json.loads(PACKET.read_text(encoding="utf-8-sig"))
    with pytest.raises(ValueError, match="packet hash mismatch"):
        build_holdout_worksheet(packet, packet_sha256="0" * 64)

"""The trap judge's packet and parsing (docs/trap_lesson_from_games_scope.md section 8).

The verdicts themselves are measured by scripts/trap_judge_calibrate.py against
docs/qa/trap_judge_calibration_2026_11_17.json; these tests pin what the judge
is shown and how its answer is read.
"""
import json
from pathlib import Path

import chess

from services import trap_judge

KE8 = {"player_color": "black",
       "before_offer_fen": "r1bqkbnr/pppp1pp1/2n4p/6N1/3pP3/8/PPP2PPP/RNBQKB1R w KQkq - 0 5",
       "offer_san": "Nxf7", "offer_moves_back": 2,
       "before_move_fen": "r1bq1bnr/pppp1kp1/2n4p/8/2BpP3/8/PPP2PPP/RNBQK2R b KQ - 1 6",
       "move_san": "Ke8", "best_san": "d5", "line_san": ["Qh5+", "g6", "Qxg6+"]}


def test_the_packet_carries_both_positions_and_no_names():
    text = trap_judge.packet(KE8)
    assert KE8["before_offer_fen"] in text and KE8["before_move_fen"] in text
    assert "Nxf7" in text and "Ke8" in text and "each side made one more move" in text
    assert "Pass position: none, the player is in check." in text


def test_a_pass_flips_the_side_to_move():
    fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    out = trap_judge.pass_fen(fen)
    assert out is not None and chess.Board(out).turn == chess.BLACK
    assert out.split()[0] == fen.split()[0]


def test_an_unknown_verdict_is_unclear_never_trap():
    assert trap_judge.parse({"verdict": "maybe"})["verdict"] == "UNCLEAR"
    assert trap_judge.parse({})["verdict"] == "UNCLEAR"
    assert trap_judge.parse({"verdict": "trap", "evidence": "x"})["verdict"] == "TRAP"


def test_the_calibration_set_has_one_row_per_position():
    path = Path(__file__).resolve().parents[2] / "docs" / "qa" / "trap_judge_calibration_2026_11_17.json"
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    keys = {(c["before_move_fen"], c["move_san"]) for c in cases}
    assert len(keys) == len(cases) == 59
    assert all(c["label"] in trap_judge.VERDICTS for c in cases)

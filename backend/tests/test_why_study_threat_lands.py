"""A threat in a study must survive the threatened side's best reply.

2026-11-11: two of the first four live studies passed the gate with an attack
that was true on the board and answered at once -- 6.e5 "d5 attacks the
bishop" (7.exd6 en passant) and 6.b3 "Qg6 hits g2" (7.g3 / 7.Bb5+ ... Qe2).
A stand-in engine returns a fixed line, so no Stockfish is needed here.
"""
import os
import sys

import chess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import why_study as ws  # noqa: E402

E5_FEN = "r1bqk1nr/pppp1pp1/2n4p/2b5/2BpP3/5N2/PPP2PPP/RNBQ1RK1 w kq - 0 6"
B3_FEN = "rn2kbnr/pbp1pppp/1p2q3/8/8/2N2P2/PPPPB1PP/R1BQK1NR w KQkq - 1 6"
RF7_FEN = "r2q1rk1/ppp1b3/4pp2/6pQ/3Pp3/2P1P1B1/PP3P1P/R4RK1 b - - 4 18"


class _Eng:
    """Plays a fixed line of SAN from whatever position it is asked about."""
    def __init__(self, line):
        self.line = line

    def analyse(self, board, limit):
        b = board.copy()
        pv = []
        for san in self.line:
            mv = b.parse_san(san)
            pv.append(mv)
            b.push(mv)
        return {"pv": pv}


def _claim(after, subject, target, kind="attacks"):
    return {"kind": kind, "after": after, "subject": subject, "target": target}


def test_en_passant_answers_the_d5_threat():
    ok, why = ws.threat_lands(_claim(["e5", "d5"], "d5", "c4"), E5_FEN,
                              eng=_Eng(["exd6", "cxd6", "c3", "d5"]))
    assert not ok and "exd6" in why


def test_a_pawn_stepping_away_is_not_a_tempo():
    ok, why = ws.threat_lands(_claim(["b3", "Qg6"], "g6", "g2"), B3_FEN,
                              eng=_Eng(["g3", "Nc6", "Bd3", "f5"]))
    assert not ok and "g3" in why


def test_a_threat_that_is_cashed_lands():
    # 18...Rf7 19.Qg6+ Kf8 20.Qxe4: the queen check hits e4 and takes it.
    ok, why = ws.threat_lands(_claim(["Rf7", "Qg6+"], "g6", "e4"), RF7_FEN,
                              eng=_Eng(["Kf8", "Qxe4"]))
    assert ok, why


def test_a_piece_forced_to_retreat_is_a_real_tempo():
    # After e5 d5, if the bishop had to retreat (no en passant in this line),
    # the attack did its job.
    ok, why = ws.threat_lands(_claim(["e5", "d5"], "d5", "c4"), E5_FEN,
                              eng=_Eng(["Bb3", "Nge7"]))
    assert ok, why


def test_descriptions_of_the_current_position_are_left_alone():
    eng = _Eng(["a3"])
    assert ws.threat_lands(_claim([], "c4", "f7"), E5_FEN, eng=eng) == (True, None)
    assert ws.threat_lands({"kind": "gives_check", "after": ["Bxf7+"]}, E5_FEN, eng=eng) == (True, None)


# --- the packet's material facts (2026-11-11) --------------------------------
# The ledger replayed engine lines with push_san, and the first token of every
# line was a numbered move ("6...d6", "7."), so it stopped at move one and
# reported "no material change" on every study. 6.c3 of 2d86e1f9 wins a pawn.

def test_numbered_moves_are_stripped_in_every_form():
    assert ws._san_only("6...d6 7. cxd4 Bb6 8.Nc3") == ["d6", "cxd4", "Bb6", "Nc3"]


def test_the_ledger_replays_the_whole_line_and_counts_the_pawn_won_back():
    after_c3 = chess.Board(E5_FEN)
    after_c3.push_san("c3")
    led = ws.material_along(after_c3, ["6...d6", "7.", "cxd4", "Bb6", "8.", "Nc3"], "white", "black")
    assert led["replayed_moves"] == led["line_moves"] == 4
    assert led["mover_material_change_cp"] == 100


def test_material_now_says_who_is_ahead():
    assert ws.material_now(chess.Board(E5_FEN), chess.WHITE) == {
        "mover_minus_opponent_cp": -100, "plain": "the mover is 1 pawn down"}
    assert ws.material_now(chess.Board(), chess.WHITE)["plain"] == "material is level"

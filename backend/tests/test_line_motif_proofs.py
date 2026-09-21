"""Locks for the three line-motif proofs, built from real Lichess puzzles.

Every position here was played out move by move on 2026-09-22 before any code
was written, and every negative case is a false positive that the first version
of the detector actually produced. They are the measurement in regression form:
if one of these flips, the cross-fire numbers in the commit message are no
longer true.
"""

from __future__ import annotations

import chess
import pytest

from services.clearance_puzzle_proof import build_clearance_proof
from services.interference_puzzle_proof import build_interference_proof
from services.xray_attack_puzzle_proof import build_xray_attack_proof


CP_LOSS = 250


def _case(fen, best, rest):
    board = chess.Board(fen)
    played = next(board.san(m) for m in board.legal_moves if m != board.parse_san(best))
    return board, played, best, rest


# --------------------------------------------------------------------------
# clearance
# --------------------------------------------------------------------------

CLEARANCE_TRUE = [
    # 00M92 Ng6+ empties h4 so the e4 rook can mate on it.
    (
        "3q1r1k/p3r1pp/1p1b1p2/2p5/3pR2N/1QPn2P1/PP1B1P1P/R5K1 w - - 0 22",
        "Ng6+", ["hxg6", "Rh4#"], "h4", "square",
    ),
    # 00Aae Rf8+ empties the promotion square.
    (
        "1R6/1P6/4pkp1/5p2/3P4/3KP2p/8/1r6 w - - 0 44",
        "Rf8+", ["Ke7", "b8=Q", "Rxb8", "Rxb8"], "b8", "square",
    ),
    # 01EUl Bxc3+ empties d4 so the d8 queen runs the whole file to d1.
    (
        "r2qk2r/ppp2pp1/2p2n2/7p/3bP1b1/2N3QP/PPP2PP1/R1B1KB1R b KQkq - 0 9",
        "Bxc3+", ["Qxc3", "Qd1#"], "d4", "line",
    ),
    # 00aCb Nf6+ empties e4 on the d3-h7 diagonal.
    (
        "r2q1rk1/pp2bpp1/2p1b2p/4P3/3PNn2/1P1Q3P/P4BP1/1BR2RK1 w - - 5 26",
        "Nf6+", ["gxf6", "Qh7#"], "e4", "line",
    ),
]


@pytest.mark.parametrize("fen,best,rest,vacated,kind", CLEARANCE_TRUE)
def test_clearance_fires_and_names_the_vacated_square(fen, best, rest, vacated, kind):
    bundle = build_clearance_proof(*_case(fen, best, rest), CP_LOSS)
    assert bundle is not None
    assert bundle.verifier.verified
    facts = bundle.detector.facts[0]
    assert facts["vacated_square"] == vacated
    assert facts["clearance_kind"] == kind


CLEARANCE_BATTERY_TRADES = [
    # 007mr, 009IO, 00EXP: doubled rooks, the front one is traded on the file
    # and the back one recaptures. Nothing got out of anything's way.
    ("5k2/p2r3p/1p4pP/3r1q2/4R3/2P5/PP3PQ1/K3R3 b - - 0 33",
     "Rd1+", ["Rxd1", "Rxd1#"]),
    ("3r4/4kp1r/p2Np1p1/3bP3/P2n4/8/1P3RPP/5RK1 w - - 5 26",
     "Rxf7+", ["Rxf7", "Rxf7#"]),
    ("2n3k1/p4ppp/2p1p3/P1NrP3/1N1r4/8/5PPP/1R1R2K1 b - - 0 29",
     "Rxd1+", ["Rxd1", "Rxd1#"]),
]


@pytest.mark.parametrize("fen,best,rest", CLEARANCE_BATTERY_TRADES)
def test_clearance_refuses_a_battery_trade(fen, best, rest):
    assert build_clearance_proof(*_case(fen, best, rest), CP_LOSS) is None


# --------------------------------------------------------------------------
# xRayAttack
# --------------------------------------------------------------------------

XRAY_TRUE = [
    # 01GBu the e5 rook only sees e1 through the white rook on e2.
    ("5r1k/3p2bp/p4pp1/qp1Pr3/8/1Q4B1/PP2RPPP/4R1K1 b - - 0 23",
     "Qxe1+", ["Rxe1", "Rxe1#"], "e5", "e1"),
    # 05Gv1 the a4 queen sees e8 through the black bishop on d7.
    ("6k1/p1pb1ppp/6r1/2p5/Q1Pq1P2/NP3P2/P6P/4R2K w - - 1 25",
     "Re8+", ["Bxe8", "Qxe8#"], "a4", "e8"),
    # 0791B the x-ray only lines up after the first ply.
    ("5k2/p4p1p/1p1Pp1pP/5b2/5P2/2R5/2rr4/2R3K1 w - - 9 37",
     "Rc8+", ["Rxc8", "Rxc8#"], "c1", "c8"),
]


@pytest.mark.parametrize("fen,best,rest,slider,target", XRAY_TRUE)
def test_xray_fires_and_names_the_slider_and_target(fen, best, rest, slider, target):
    bundle = build_xray_attack_proof(*_case(fen, best, rest), CP_LOSS)
    assert bundle is not None
    assert bundle.verifier.verified
    facts = bundle.detector.facts[0]
    assert facts["slider_square"] == slider
    assert facts["target_square"] == target
    assert facts["screening_pieces"]


XRAY_THROUGH_A_KING = [
    # 00HzH, 00JfN, 00XqB: mate nets where the only screen is the enemy king.
    ("5rk1/p2q2p1/1p2p1Np/3p3P/3Pb1P1/2P5/PP3R2/6K1 w - - 0 34",
     "Rxf8+", ["Kh7", "Rh8#"]),
    ("r6r/1bpnk3/1p1pB3/pP1P4/P3PQP1/2b2N1q/2P2P2/R3R1K1 w - - 0 25",
     "Qf7+", ["Kd8", "Qxd7#"]),
    ("8/pQ3p1k/3q1P1p/6p1/P2p2K1/1P1P3P/2P3P1/8 b - - 0 37",
     "Qf4+", ["Kh5", "Qh4#"]),
]


@pytest.mark.parametrize("fen,best,rest", XRAY_THROUGH_A_KING)
def test_xray_refuses_to_screen_through_a_king(fen, best, rest):
    assert build_xray_attack_proof(*_case(fen, best, rest), CP_LOSS) is None


# --------------------------------------------------------------------------
# interference
# --------------------------------------------------------------------------

INTERFERENCE_TRUE = [
    # 01GCT we interpose with tempo between the queen and the bishop it guards.
    ("5r2/6pk/R3bn1p/8/1P6/P2PqB2/1B2P2P/6RK w - - 1 31",
     "Be4+", ["Kh8", "Rxe6"], "own", "e3", "e6"),
    # 0EywV the quiet version of the same idea.
    ("r4rk1/pbpp1ppp/1p3n2/3Pn3/4PR2/4B1P1/PqP1N1BP/R2Q2K1 w - - 0 14",
     "Bd4", ["Qa3", "Bxe5"], "own", "b2", "e5"),
    # 0EFIo the larger half of the family: a check drives his king onto his
    # own rook's defensive line.
    ("4Rrk1/pp3ppp/2p5/2Pp4/1P1P1Qn1/P1N3Pq/1B3P1P/4R1K1 b - - 0 22",
     "Qxh2+", ["Kf1", "Qh1+", "Ke2", "Rxe8+"], "forced", "e1", "e8"),
    # 0FuFJ same shape, the blocked defender is a rook on a rank.
    ("4k3/1pr3pp/p1n5/8/2Q5/4q3/PP4PP/3R3K w - - 0 25",
     "Qg8+", ["Ke7", "Qxg7+"], "forced", "c7", "g7"),
]


@pytest.mark.parametrize(
    "fen,best,rest,kind,defender,target", INTERFERENCE_TRUE
)
def test_interference_fires_and_names_the_severed_defence(
    fen, best, rest, kind, defender, target
):
    bundle = build_interference_proof(*_case(fen, best, rest), CP_LOSS)
    assert bundle is not None
    assert bundle.verifier.verified
    facts = bundle.detector.facts[0]
    assert facts["interference_kind"] == kind
    assert facts["defender_square"] == defender
    assert facts["target_square"] == target


def test_every_proof_refuses_a_zero_cp_loss_non_mistake():
    """The shared 100cp floor: a move that lost nothing is not a puzzle."""
    case = _case(
        "3q1r1k/p3r1pp/1p1b1p2/2p5/3pR2N/1QPn2P1/PP1B1P1P/R5K1 w - - 0 22",
        "Ng6+", ["hxg6", "Rh4#"],
    )
    for builder in (
        build_clearance_proof,
        build_xray_attack_proof,
        build_interference_proof,
    ):
        assert builder(*case, 0) is None

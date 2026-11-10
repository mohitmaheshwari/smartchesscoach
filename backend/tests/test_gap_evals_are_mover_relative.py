"""Stored evals are WHITE-relative; the gap classifiers must read them from the
mover's side.

stockfish_service stores eval_before / eval_after from White's point of view
(it flips only to compute cp_loss). The king-safety "already hopeless" gate,
the severity promotion and the "overlooked immediate reply" drop compared the
raw value, so for Black they skipped the positions Black was winning and kept
the ones Black had lost (found 2026-11-10).

The king-safety position is a real Black move from production that the
classifier labels ignored_king_attack.
"""
from services import cognitive_gap_subtypes as cgs
from services.move_observation_deriver import _classify_piece_safety_severity

BLACK_KING_ATTACK = {"fen_before": "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P1P1/2PP1Q1P/PP3P2/RNB1K1NR b KQ - 0 7",
                     "move_uci": "h7h6", "move": "h6", "cp_loss": 237}


def test_mover_cp_flips_for_black_only():
    assert cgs.mover_cp({"fen_before": "8/8/8/8/8/8/8/K6k w - - 0 1"}, 250) == 250
    assert cgs.mover_cp({"fen_before": "8/8/8/8/8/8/8/K6k b - - 0 1"}, 250) == -250
    assert cgs.mover_cp({"fen_before": "8/8/8/8/8/8/8/K6k b - - 0 1"}, None) is None


def test_black_winning_is_not_gated_as_hopeless():
    winning = {**BLACK_KING_ATTACK, "eval_before": -500}     # white-relative: Black is +5
    assert cgs.classify_king_safety(winning, None, None)[0] == "ignored_king_attack"


def test_black_already_lost_is_gated():
    lost = {**BLACK_KING_ATTACK, "eval_before": 500}          # white-relative: Black is -5
    assert cgs.classify_king_safety(lost, None, None) == (None, None)


def test_severity_does_not_promote_a_hopeless_black_position():
    base = {"fen_before": BLACK_KING_ATTACK["fen_before"], "cp_loss": 450, "evaluation": "mistake"}
    hopeless = cgs._promote_severity("moderate", {**base, "eval_before": 350})   # Black -3.5
    fine = cgs._promote_severity("moderate", {**base, "eval_before": -100})      # Black +1
    assert hopeless == "moderate" and fine != "moderate"


def test_piece_safety_severity_reads_the_mover_side():
    mv = {"fen_before": BLACK_KING_ATTACK["fen_before"], "cp_loss": 450, "evaluation": "mistake"}
    assert (_classify_piece_safety_severity("small_slip", {**mv, "eval_before": 350}, None)
            != _classify_piece_safety_severity("small_slip", {**mv, "eval_before": -350}, None))

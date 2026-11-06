"""The card reads the check-first facts (fix 3 of caption_line_reasoning_scope).

Mohit 2026-11-06, 3628ebef m32: the card for Rxe7 said "Re6+ was better -- it
also hits the knight on e7. The same piece on a square that attacks more
things is the better move." Both moves take that knight. The difference is
the king: it takes back after Rxe7 and has stepped away after the check.

The facts come from services.reasoning.check_first on the two stored lines
(the same family the Why button runs); R12 reads them through two failure
clauses and two why clauses, on a mistake or worse, user cards only.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.caption_facts import extract_facts
from services.caption_templates import render_template, select_first_match

RXE7 = "8/pp2n1q1/5k2/4R3/2PP2p1/1P4P1/n4P2/4R1K1 w - - 2 32"
PV_PLAYED = ["Qxe7", "Rxe7", "Kxe7", "Kf1", "a5", "Ke1", "Nc1", "b4", "Nd3+", "Ke2", "Nxb4", "d5"]
PV_BEST = ["Kg5", "Rxe7", "Qxd4", "R1e5+", "Kf6", "R7e6+", "Kf7", "Re7+", "Kg6", "R7e6+", "Kg7", "Re7+"]

R12 = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "data", "captions", "R12_blunder.json"), encoding="utf-8"))


def rxe7_facts(**over):
    f = extract_facts(fen_before=RXE7, played_san="Rxe7", best_move_san="Re6+", cp_loss=507,
                      pv_after_played=PV_PLAYED, pv_after_best=PV_BEST,
                      mover_is_user=True, full_move_number=32)
    f.update(severity_practical="serious", mover_is_user=True)
    f.update(over)
    return f


def test_the_facts_carry_the_family():
    f = rxe7_facts()
    assert f["check_first_square"] == "e7" and f["check_first_piece"] == "knight"
    assert f["check_first_capture_san"] == "Rxe7" and f["check_first_king_to"] == "g5"
    assert f["check_first_king_last"] is True and f["check_first_sacrificed"] is None


def test_the_facts_are_absent_on_any_other_card():
    f = extract_facts(fen_before="rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2",
                      played_san="e4", best_move_san="c4", cp_loss=150,
                      pv_after_played=["dxe4"], pv_after_best=["e6"],
                      mover_is_user=True, full_move_number=2)
    for key in ("check_first_square", "check_first_piece", "check_first_capture_san",
                "check_first_king_to", "check_first_king_last", "check_first_sacrificed"):
        assert f[key] is None


def test_the_failure_clause_names_the_kings_recapture():
    f = rxe7_facts()
    match = select_first_match(R12["failure_mode_clauses_user"], f)
    assert match["variant"] == "failure_check_first_king_takes_back_last"
    assert render_template("R12_blunder", match["variant"], f) == "ends with their king taking back on e7"
    # A king that takes back at once gets the plain clause.
    plain = select_first_match(R12["failure_mode_clauses_user"], dict(f, check_first_king_last=False))
    assert plain["variant"] == "failure_check_first_king_takes_back"
    assert render_template("R12_blunder", plain["variant"], f) == "lets their king take back on e7"


def test_the_why_clause_is_check_first_take_second():
    f = rxe7_facts()
    match = select_first_match(R12["why_clauses_user"], f)
    assert match["variant"] == "why_user_missed_check_first"
    assert render_template("R12_blunder", match["variant"], f) == (
        "it makes their king step away first, and then Rxe7 wins the knight with nothing "
        "to take back. Check first, take second.")


def test_a_sacrificed_checking_piece_is_said():
    f = rxe7_facts(check_first_sacrificed="pawn")
    match = select_first_match(R12["why_clauses_user"], f)
    assert match["variant"] == "why_user_missed_check_first_sacrifice"
    assert render_template("R12_blunder", match["variant"], f) == (
        "it gives up a pawn to pull their king away, and then Rxe7 wins the knight with "
        "nothing to take back.")


def test_an_inaccuracy_does_not_get_the_clause():
    # The exchange on the square is a pawn or more; a card the rating-aware
    # tier calls an inaccuracy says less than that, so it stays with its
    # usual wording.
    f = rxe7_facts(severity_practical="inaccuracy")
    fm = select_first_match(R12["failure_mode_clauses_user"], f)
    assert fm is None or not fm["variant"].startswith("failure_check_first")
    wc = select_first_match(R12["why_clauses_user"], f)
    assert wc is None or not wc["variant"].startswith("why_user_missed_check_first")


def test_every_check_first_variant_has_its_principle_and_glossary_entry():
    for variant in ("failure_check_first_king_takes_back", "failure_check_first_king_takes_back_last"):
        assert variant in R12["variants"]
        principle = R12["teaching_principles"][variant]
        assert principle and not principle.endswith((".", "?"))
    for key in ("check_first_square", "check_first_piece", "check_first_capture_san",
                "check_first_king_to", "check_first_king_last", "check_first_sacrificed"):
        assert key in R12["fact_glossary"]

"""A relation claim about the better move is judged on the board it is made on.

Mohit 2026-11-06, Rxe7 of 3628ebef move 32 ("why did the UI caption not show
the right why?"). The prod log had the answer:

    [caption_verifier] FAIL on 'Rxe7 was a bad mistake. Re6+ was better — it
    also hits the knight on e7. ...' (rule=R12_blunder): [piece_on_square]
    'the knight on e7': square e7 has a rook, not a knight
    -> 'Rxe7 is a serious mistake. Re6+ was better.'

Re6+ does hit the knight on e7. The verifier judged the claim on the board
AFTER Rxe7, where the player's own rook stands on e7 because it has just
taken that knight. The capture hatch (test_best_move_capture_claim_board.py)
covers takes / captures / wins / removes; this is the same defect for the
relation verbs, and the proof is deliberately as narrow: the sentence must
name the better move, and the board after the better move must show the
piece on the square with the better move's piece attacking it.

Three gates share the one proof in narrator_claim_verifier, as the capture
hatch does.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import pytest

from scripts.content_correctness_audit import audit_text_against_fen
from services.caption_pipeline import (
    _clear_best_move_relation_claims,
    _verify_and_recover_caption,
)
from services.narrator_claim_verifier import (
    best_move_relation_proves,
    verify_caption,
)

# Mohit's game against ChessKingsFather, move 32, White to move.
RXE7_FEN = "8/pp2n1q1/5k2/4R3/2PP2p1/1P4P1/n4P2/4R1K1 w - - 2 32"
RXE7_CAPTION = (
    "Rxe7 was a bad mistake. Re6+ was better — it also hits the knight on e7. "
    "The same piece on a square that attacks more things is the better move."
)


def _fen_after(fen_before, played_san):
    board = chess.Board(fen_before)
    board.push(board.parse_san(played_san))
    return board.fen()


def _audit(fen_before, played_san, caption):
    return audit_text_against_fen(
        text=caption, fen=_fen_after(fen_before, played_san),
        user_color="white", engine=None)


def _facts(fen_before, played, best):
    return {"fen_before": fen_before, "move_san": played, "best_move_san": best,
            "pv_after_best": [], "pv_after_played": [], "is_user_move": True}


# ── the proof itself ─────────────────────────────────────────────────────

def test_the_better_move_hits_the_knight_on_the_board_it_is_played_on():
    at = RXE7_CAPTION.index("knight on e7")
    assert best_move_relation_proves(RXE7_CAPTION, at, "knight", "e7",
                                     _facts(RXE7_FEN, "Rxe7", "Re6+"))


def test_a_square_the_better_move_does_not_attack_is_not_proved():
    # a2 holds a black knight too, and the rook on e6 does not see it.
    caption = "Rxe7 was a bad mistake. Re6+ was better — it also hits the knight on a2."
    at = caption.index("knight on a2")
    assert not best_move_relation_proves(caption, at, "knight", "a2",
                                         _facts(RXE7_FEN, "Rxe7", "Re6+"))


def test_the_wrong_piece_name_is_not_proved():
    caption = "Rxe7 was a bad mistake. Re6+ was better — it also hits the bishop on e7."
    at = caption.index("bishop on e7")
    assert not best_move_relation_proves(caption, at, "bishop", "e7",
                                         _facts(RXE7_FEN, "Rxe7", "Re6+"))


def test_a_sentence_that_does_not_name_the_better_move_is_judged_on_the_players_board():
    # No better move in the sentence: this reads as a claim about the board
    # the player is looking at, where e7 holds the player's rook.
    caption = "Rxe7 was a bad mistake. It also hits the knight on e7."
    at = caption.index("knight on e7")
    assert not best_move_relation_proves(caption, at, "knight", "e7",
                                         _facts(RXE7_FEN, "Rxe7", "Re6+"))


def test_the_played_move_inside_a_san_is_not_the_better_move():
    # "Rxe7" contains e7 but never names Re6+; a token match is required.
    caption = "Rxe7 hits the knight on e7."
    at = caption.index("knight on e7")
    assert not best_move_relation_proves(caption, at, "knight", "e7",
                                         _facts(RXE7_FEN, "Rxe7", "Re6+"))


def test_a_current_location_claim_without_a_relation_verb_is_not_proved():
    caption = "Rxe7 was a bad mistake. Re6+ was better. Watch the knight on e7."
    at = caption.index("knight on e7")
    assert not best_move_relation_proves(caption, at, "knight", "e7",
                                         _facts(RXE7_FEN, "Rxe7", "Re6+"))


def test_an_attack_verb_on_the_movers_own_piece_is_not_proved():
    # 1.e4 e5 2.Nf3 Nc6: Nc3 defends the pawn on e4; it does not "hit" it.
    fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    hits = "d3 was a mistake. Nc3 was better — it hits the pawn on e4."
    defends = "d3 was a mistake. Nc3 was better — it defends the pawn on e4."
    assert not best_move_relation_proves(hits, hits.index("pawn on e4"), "pawn", "e4",
                                         _facts(fen, "d3", "Nc3"))
    assert best_move_relation_proves(defends, defends.index("pawn on e4"), "pawn", "e4",
                                     _facts(fen, "d3", "Nc3"))


def test_nothing_is_proved_without_a_better_move_or_a_position():
    at = RXE7_CAPTION.index("knight on e7")
    assert not best_move_relation_proves(RXE7_CAPTION, at, "knight", "e7",
                                         _facts(RXE7_FEN, "Rxe7", None))
    assert not best_move_relation_proves(RXE7_CAPTION, at, "knight", "e7",
                                         _facts("", "Rxe7", "Re6+"))
    assert not best_move_relation_proves(RXE7_CAPTION, at, "knight", "e7",
                                         _facts(RXE7_FEN, "Rxe7", "Qz9"))


# ── the reason must survive the opponent's first reply ───────────────────
#
# Hand grade of the first bulk render, 2026-11-06: a relation that is true on
# the board after the better move and gone one ply later was let through.

def _with_line(facts, line):
    return dict(facts, pv_after_best=list(line))


def test_the_rxe7_relation_survives_the_kings_step():
    at = RXE7_CAPTION.index("knight on e7")
    facts = _with_line(_facts(RXE7_FEN, "Rxe7", "Re6+"), ["Kg5", "Rxe7", "Qxd4"])
    assert best_move_relation_proves(RXE7_CAPTION, at, "knight", "e7", facts)


def test_an_attack_is_not_proved_when_the_reply_takes_the_attacker():
    # 67523b9d m39: Bxd4 does hit the b6 pawn, and exd4 takes the bishop.
    fen = "2r3k1/1p1r1p2/1P2q1p1/2bp3p/3B3n/4P2P/Q3BPP1/2R1R1K1 b - - 1 39"
    caption = "Qxb6 was a mistake. Bxd4 was better — it attacks the pawn on b6 that nothing is guarding."
    at = caption.index("pawn on b6")
    assert best_move_relation_proves(caption, at, "pawn", "b6", _facts(fen, "Qxb6", "Bxd4"))
    assert not best_move_relation_proves(
        caption, at, "pawn", "b6", _with_line(_facts(fen, "Qxb6", "Bxd4"), ["exd4", "Qxb6"]))
    # A reply that leaves bishop, pawn and diagonal alone keeps the claim.
    assert best_move_relation_proves(
        caption, at, "pawn", "b6", _with_line(_facts(fen, "Qxb6", "Bxd4"), ["Rxc8+", "Rd8"]))


def test_an_attack_is_not_proved_when_the_reply_moves_the_target_away():
    # Mohit 2026-10-03: "as knight can be moved right?"
    fen = "1k2n2r/p1p5/1p5p/8/3q4/1Q3B2/PP3PP1/4R1K1 w - - 0 1"
    caption = "Qc2 was a mistake. Qb5 was better — it attacks the knight on e8."
    at = caption.index("knight on e8")
    assert not best_move_relation_proves(
        caption, at, "knight", "e8", _with_line(_facts(fen, "Qc2", "Qb5"), ["Nd6", "Qc6"]))
    assert best_move_relation_proves(
        caption, at, "knight", "e8", _with_line(_facts(fen, "Qc2", "Qb5"), ["a5", "Qc6"]))


def test_a_defence_holds_when_the_piece_is_taken_and_the_defender_takes_back():
    # 5118ded7 m13: d3 guards the queen on e4; Qxe4+ dxe4 is the trade on its terms.
    fen = "r3k2r/ppp1qp1p/6p1/2bP4/4Q1b1/5N2/PPPP1PPP/R1B1K2R w KQkq - 1 13"
    caption = "Your opponent takes the queen. They had d3, which defends the queen on e4."
    at = caption.index("queen on e4")
    assert best_move_relation_proves(
        caption, at, "queen", "e4", _with_line(_facts(fen, "Qxe7+", "d3"), ["Qxe4+", "dxe4"]))


def test_a_defence_is_not_proved_when_the_reply_takes_the_defender():
    fen = "4k3/8/8/8/1b2P3/8/8/1N2K3 w - - 0 1"
    caption = "Kf1 was a mistake. Nc3 was better — it defends the pawn on e4."
    at = caption.index("pawn on e4")
    assert best_move_relation_proves(caption, at, "pawn", "e4", _facts(fen, "Kf1", "Nc3"))
    assert not best_move_relation_proves(
        caption, at, "pawn", "e4", _with_line(_facts(fen, "Kf1", "Nc3"), ["Bxc3+", "Kf2"]))


def test_a_line_that_does_not_replay_leaves_the_board_to_decide():
    at = RXE7_CAPTION.index("knight on e7")
    facts = _with_line(_facts(RXE7_FEN, "Rxe7", "Re6+"), ["Zz9"])
    assert best_move_relation_proves(RXE7_CAPTION, at, "knight", "e7", facts)


# ── the floor names the piece the move itself took ───────────────────────

def test_the_floor_names_what_the_move_took_not_what_the_reply_takes():
    # 9a1bc553 m21: the opponent's Nxg3 takes a bishop; the reply Nxg3 takes
    # the knight, and the pipeline re-points captured_piece_type at it.
    from services.caption_facts import extract_facts
    from services.caption_fallback_tiers import tier23_caption

    fen = "3r1r1k/1p2b1p1/pqpp3p/4p2n/P1Q1P3/1P4B1/2PRNPPP/4R1K1 b - - 6 21"
    facts = extract_facts(fen_before=fen, played_san="Nxg3", best_move_san="d5", cp_loss=0,
                          opp_cp_loss=43, pv_after_played=["Nxg3"], pv_after_best=["exd5"],
                          mover_is_user=False, full_move_number=21)
    assert facts["captured_piece_type"] == "bishop"
    facts["played_captured_piece_type"] = facts["captured_piece_type"]
    facts["captured_piece_type"] = "knight"          # what the pipeline does on this card
    text, _rule = tier23_caption(facts, flagged_mistake=True)
    assert "takes the knight" not in text
    if "takes the" in text:
        assert "takes the bishop" in text


# ── gate 1: the Phase 1 audit in caption_pipeline ────────────────────────

def test_gate_1_clears_the_rxe7_claim():
    audit = _audit(RXE7_FEN, "Rxe7", RXE7_CAPTION)
    assert audit.overall == "fail", "the old rejection: e7 holds a rook after Rxe7"
    assert _clear_best_move_relation_claims(
        audit, RXE7_CAPTION, fen_before=RXE7_FEN, best_move_san="Re6+") == 1
    assert audit.overall != "fail"


def test_gate_1_leaves_a_false_relation_claim_rejected():
    caption = "Rxe7 was a bad mistake. Re6+ was better — it also hits the knight on a2."
    audit = _audit(RXE7_FEN, "Rxe7", caption)
    # a2 does hold a knight on the player's board, so Phase 1 passes that
    # claim on its own; the point is that this function adds nothing false.
    assert _clear_best_move_relation_claims(
        audit, caption, fen_before=RXE7_FEN, best_move_san="Re6+") == 0


def test_the_rxe7_caption_is_no_longer_replaced_by_the_bare_severity_line():
    payload = {"caption": RXE7_CAPTION, "rule_name": "R12_blunder"}
    board = chess.Board(RXE7_FEN)
    telemetry = _verify_and_recover_caption(
        caption_payload=payload,
        fen_before=RXE7_FEN,
        played_move=board.parse_san("Rxe7"),
        user_color="white",
        played_san="Rxe7",
        best_move_san="Re6+",
        pv_after_best=["Kg5", "Rxe7", "Qxd4", "R1e5+"],
        severity_practical="serious",
        mover_is_user=True,
    )
    assert telemetry is not None
    assert telemetry.get("verdict") != "fail_recovered"
    assert payload["caption"] == RXE7_CAPTION
    assert "R_VERIFIER_RECOVERY" not in payload["rule_name"]


def test_a_sentence_about_the_players_board_is_still_replaced():
    caption = "Rxe7 was a bad mistake. Watch the knight on e7."
    payload = {"caption": caption, "rule_name": "R12_blunder"}
    board = chess.Board(RXE7_FEN)
    telemetry = _verify_and_recover_caption(
        caption_payload=payload,
        fen_before=RXE7_FEN,
        played_move=board.parse_san("Rxe7"),
        user_color="white",
        played_san="Rxe7",
        best_move_san="Re6+",
        pv_after_best=[],
        severity_practical="serious",
        mover_is_user=True,
    )
    assert telemetry.get("verdict") == "fail_recovered"
    assert "R_VERIFIER_RECOVERY" in payload["rule_name"]


# ── gates 2 and 3: narrator_claim_verifier.verify_caption ────────────────

@pytest.mark.parametrize("strict", [False, True])
def test_verify_caption_no_longer_flags_the_rxe7_claim(strict):
    violations = verify_caption(RXE7_CAPTION, _facts(RXE7_FEN, "Rxe7", "Re6+"),
                                strict_v2=strict)
    assert [v for v in violations if v.get("check") == "piece_on_square"] == []


@pytest.mark.parametrize("strict", [False, True])
def test_verify_caption_still_flags_a_claim_about_the_players_board(strict):
    caption = "Rxe7 was a bad mistake. Re6+ was better. Watch the knight on e7."
    violations = verify_caption(caption, _facts(RXE7_FEN, "Rxe7", "Re6+"),
                                strict_v2=strict)
    assert [v for v in violations if v.get("check") == "piece_on_square"]

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

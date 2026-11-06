"""A capture named in the played line is judged at the ply it is played.

Found 2026-11-06 while measuring why the verifier still replaces captions
after the better-move fix. Over 60 games, 58 of 99 replaced captions were one
sentence, on opponent cards:

    Your opponent played Nb6. That was a mistake -- lets you play e6, and
    Rxc4 then takes their queen on c4. ...

    [piece_on_square] 'their queen on c4': no piece on c4 -- claim is
    hallucinated

The queen reaches c4 two moves into the stored line (e6 Qc4 Rxc4), and all 58
replay true at the ply the taking move is played. The gate that failed them
already had the proof for this -- _clear_best_move_capture_claims accepts the
played line -- but _verify_and_recover_caption was never given that line to
pass on, so the proof could only ever see the better move's line.

The owner word is checked as well ("their" / "your"), because the same SAN
can capture twice in one line and the audit had failed some of these on
colour alone.

Fixtures are dumped from the trace: position, both stored lines, and the
caption the pipeline had written before the verifier replaced it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

from services.caption_pipeline import _verify_and_recover_caption

NB6 = dict(
    fen="r4rk1/2Rn1p1p/q5pQ/4Pp2/p2P1N2/8/P4PPP/5RK1 b - - 4 23", san="Nb6", best="Rfd8",
    pv_played=["e6", "Qc4", "Rxc4", "Nxc4"], pv_best=["Nd5", "Nxe5", "Ne7+", "Kh8"],
    caption=("Your opponent played Nb6. That was a mistake — lets you play e6, and Rxc4 then takes "
             "their queen on c4. Play e6 — it attacks the pawn on f7, which only their rook defends."),
)
# The audit failed this one on colour: d6 holds the player's own knight now,
# and the opponent's knight arrives there (Nxd6) before exd6 takes it.
ND4 = dict(
    fen="r4rk1/6pp/p2Np3/1p2P3/5P2/PnR3P1/3p3P/1R4K1 b - - 1 29", san="Nd4", best="Nc1",
    pv_played=["Kf2", "Nf5", "Rd1", "Nxd6", "exd6", "Rfd8", "Rxd2", "a5", "Rc6", "b4"],
    pv_best=["Rbxc1", "dxc1=B", "Rxc1", "Rfb8", "Rc5", "a5"],
    caption=("Your opponent played Nd4. That was a big mistake — lets you play Kf2, and exd6 then takes "
             "their knight on d6. Play Rd3 — it attacks their pawn on d2 that nothing is guarding."),
)
# Bxf5 occurs twice in the line: theirs takes the player's knight, the
# player's takes their bishop. Two claims fail here and both replay true.
F6 = dict(
    fen="rnbq1rk1/pp3p1p/2p3pQ/3p4/3P4/3B1N2/PPP2PPP/R3R1K1 b - - 1 14", san="f6", best="Qf6",
    pv_played=["Bxg6", "Qc7", "Nh4", "Rd8", "Nf5", "Bxf5", "Bxf5", "Qg7", "Qxg7+", "Kxg7"],
    pv_best=["h3", "Qg7", "Qh4", "Be6", "Ng5", "Re8"],
    caption=("Your opponent played f6. That was a bad mistake — lets you play Bxg6, and Bxf5 then takes "
             "their bishop on f5. Play Bxg6 — it gives up material, and Qxg7+ wins the queen on g7."),
)


def _recover(card, caption=None, with_played_line=True, severity="mistake"):
    payload = {"caption": caption or card["caption"], "rule_name": "R12_blunder"}
    board = chess.Board(card["fen"])
    telemetry = _verify_and_recover_caption(
        caption_payload=payload,
        fen_before=card["fen"],
        played_move=board.parse_san(card["san"]),
        user_color="white",
        played_san=card["san"],
        best_move_san=card["best"],
        pv_after_best=card["pv_best"],
        severity_practical=severity,
        mover_is_user=False,
        pv_after_played=card["pv_played"] if with_played_line else None,
    )
    return payload, telemetry


def test_the_nb6_sentence_survives_when_the_gate_is_given_the_played_line():
    payload, telemetry = _recover(NB6)
    assert telemetry.get("verdict") != "fail_recovered", telemetry
    assert payload["caption"] == NB6["caption"]
    assert "R_VERIFIER_RECOVERY" not in payload["rule_name"]


def test_without_the_played_line_it_is_still_replaced():
    # The behaviour before this change, kept as the control.
    payload, telemetry = _recover(NB6, with_played_line=False)
    assert telemetry.get("verdict") == "fail_recovered"
    assert "R_VERIFIER_RECOVERY" in payload["rule_name"]


def test_a_claim_the_audit_failed_on_colour_is_cleared_when_the_capture_is_of_their_piece():
    payload, telemetry = _recover(ND4)
    assert telemetry.get("verdict") != "fail_recovered", telemetry
    assert payload["caption"] == ND4["caption"]


def test_both_claims_clear_when_the_same_san_takes_twice_in_the_line():
    payload, telemetry = _recover(F6, severity="serious")
    assert telemetry.get("verdict") != "fail_recovered", telemetry
    assert payload["caption"] == F6["caption"]


def test_the_wrong_piece_is_not_cleared():
    wrong = NB6["caption"].replace("their queen on c4", "their rook on c4")
    payload, telemetry = _recover(NB6, caption=wrong)
    assert telemetry.get("verdict") == "fail_recovered"


def test_a_move_the_sentence_does_not_name_proves_nothing():
    # The square is right and the line does take a queen there, but the
    # sentence names no move that does it.
    wrong = ("Your opponent played Nb6. That was a mistake. Watch their queen on c4. "
             "Play e6 — it attacks the pawn on f7, which only their rook defends.")
    payload, telemetry = _recover(NB6, caption=wrong)
    assert telemetry.get("verdict") == "fail_recovered"


def test_a_same_san_capture_of_the_other_sides_piece_does_not_clear_the_owner():
    # In the f6 line the opponent's Bxf5 takes the PLAYER'S knight. A
    # sentence that calls that knight "their knight" names a real move, a
    # real piece and a real square, and the wrong owner.
    wrong = F6["caption"].replace("their bishop on f5", "their knight on f5")
    payload, telemetry = _recover(F6, caption=wrong, severity="serious")
    assert telemetry.get("verdict") == "fail_recovered"

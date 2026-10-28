"""A capture claim about the better move is judged on the right board.

_verify_and_recover_caption audits every rendered caption against
fen_after -- "what the player sees in the UI". That is right for a
current-location claim like "your queen on a7", and wrong the moment the
played move captured on the same square the better move would have,
because the player's own piece is standing on the target by then:

    "Ndxf2 was a small mistake. Ngxf2 was better -- it takes the pawn
     on f2."      rejected: square f2 has a knight, not a pawn

Ngxf2 does take the pawn on f2. Measured over 60 games on the stored
rows exactly as they ship: 23 rejections, 4 of them this shape, and all
four are free-capture lessons replaced by a bare severity line.

Three candidate rules recovered the same four captions on that sample:
"true on fen_before", the same plus "the caption names the best move",
and "the best move's own ply-1 capture". The narrowest shipped, because
it is the only one that binds the claim to a ply rather than asking
whether the piece sat on that square at some point.

The negative control is the reason that matters. A looser allow-set
built by unioning every capture in the stored line cleared

    "bxc6+ was better -- it takes the pawn on c6"

which is FALSE: bxc6+ is en passant, it takes the pawn on c5 and only
lands on c6, and ('pawn', 'c6') had reached the allow-set from a later
Nxc6. Every case below is a real rejection from that sweep.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import pytest

from scripts.content_correctness_audit import audit_text_against_fen
from services.caption_pipeline import (
    _best_move_capture_pair,
    _claim_piece_square,
    _clear_best_move_capture_claims,
    _verify_and_recover_caption,
)

# (label, fen_before, played_san, best_san, caption)
TRUE_CASES = [
    (
        "pawn on f2",
        "r2qkb1r/ppp2ppp/4b3/4p3/6n1/2NnP1P1/PP1PQPBP/R1B2KNR b kq - 10 11",
        "Ndxf2", "Ngxf2",
        "Ndxf2 was a small mistake. Ngxf2 was better — it takes the "
        "pawn on f2. Even after they take back, the trade leaves them "
        "worse off.",
    ),
    (
        "knight on f6",
        "r1bq1rk1/pp3pp1/4pn1p/2ppP3/2B2PnB/2NP4/PPP3PP/R2Q1RK1 w - d6 0 12",
        "Bxf6", "exf6",
        "Bxf6 was a bad mistake. exf6 was better — it takes the knight "
        "on f6. Even after they take back, the trade leaves them worse off.",
    ),
    (
        "pawn on f5",
        "6k1/pp2rrpp/q1p1p3/2PpQP2/1P6/6P1/1BN4P/4R1K1 b - - 2 29",
        "Rxf5", "exf5",
        "Rxf5 was a bad mistake. exf5 was better — it takes the pawn "
        "on f5. Before every move, look for a free piece to take.",
    ),
    (
        "knight on d4",
        "r2qr3/ppp2kpp/4bn2/4p3/1b1N4/2N5/PPQ2PPP/R1B1R1K1 b - - 0 14",
        "Qxd4", "exd4",
        "Qxd4 was a small mistake. exd4 was better — it takes the "
        "knight on d4. Before every move, look for a free piece to take.",
    ),
]

EP_FEN = "r6r/pp1knpp1/5qbp/1Pp1p3/2BbP3/P1N1B2P/5PP1/R2R2K1 w - c6 0 19"
EP_CAPTION = (
    "Ne2 was a mistake — you moved your knight away from defending e4. "
    "bxc6+ was better — it takes the pawn on c6. Even after they take "
    "back, the trade leaves them worse off."
)


def _fen_after(fen_before, played_san):
    board = chess.Board(fen_before)
    board.push(board.parse_san(played_san))
    return board.fen()


def _user_color(fen_before):
    return "white" if chess.Board(fen_before).turn == chess.WHITE else "black"


def _audit(fen_before, played_san, caption):
    return audit_text_against_fen(
        text=caption, fen=_fen_after(fen_before, played_san),
        user_color=_user_color(fen_before), engine=None)


# ── what the better move captures ────────────────────────────────────────

@pytest.mark.parametrize("label,fen,played,best,caption", TRUE_CASES)
def test_pair_is_read_off_the_board_before_the_played_move(
        label, fen, played, best, caption):
    pair = _best_move_capture_pair(fen, best)
    assert pair is not None, label
    piece, square = pair
    assert square == best[-2:].replace("+", ""), label
    assert piece in ("pawn", "knight", "bishop", "rook", "queen"), label


def test_en_passant_resolves_to_the_square_the_pawn_stands_on():
    # bxc6+ LANDS on c6 and CAPTURES on c5. The whole fix turns on this.
    assert _best_move_capture_pair(EP_FEN, "bxc6+") == ("pawn", "c5")


def test_a_quiet_better_move_proves_no_capture():
    board = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R b KQkq - 5 4"
    assert _best_move_capture_pair(board, "d6") is None


def test_an_unparseable_best_move_is_not_proof():
    assert _best_move_capture_pair(EP_FEN, "Qz9") is None
    assert _best_move_capture_pair(EP_FEN, None) is None
    assert _best_move_capture_pair("", "bxc6+") is None


def test_claim_text_is_parsed_into_piece_and_square():
    assert _claim_piece_square("the pawn on f2") == ("pawn", "f2")
    assert _claim_piece_square("your knight on e4") == ("knight", "e4")
    assert _claim_piece_square("the open file") is None


# ── clearing, and refusing to clear ──────────────────────────────────────

@pytest.mark.parametrize("label,fen,played,best,caption", TRUE_CASES)
def test_a_true_capture_claim_is_cleared(label, fen, played, best, caption):
    audit = _audit(fen, played, caption)
    assert audit.overall == "fail", "%s: expected the old rejection" % label
    assert _clear_best_move_capture_claims(
        audit, caption, fen_before=fen, best_move_san=best) == 1, label
    assert audit.overall != "fail", label


def test_the_en_passant_claim_stays_rejected():
    audit = _audit(EP_FEN, "Ne2", EP_CAPTION)
    assert audit.overall == "fail"
    assert _clear_best_move_capture_claims(
        audit, EP_CAPTION, fen_before=EP_FEN, best_move_san="bxc6+") == 0
    assert audit.overall == "fail"


def test_a_current_location_claim_is_not_cleared():
    # Same board, same proved pair -- but the sentence says the piece IS
    # there now, which is a claim about the board the player is looking at.
    label, fen, played, best, _ = TRUE_CASES[0]
    caption = "Ndxf2 was a small mistake. Watch your pawn on f2."
    audit = _audit(fen, played, caption)
    assert audit.overall == "fail"
    assert _clear_best_move_capture_claims(
        audit, caption, fen_before=fen, best_move_san=best) == 0
    assert audit.overall == "fail"


def test_a_claim_about_a_different_square_is_not_cleared():
    label, fen, played, best, _ = TRUE_CASES[0]
    caption = "Ndxf2 was a small mistake. Ngxf2 was better — it takes " \
              "the pawn on h2."
    audit = _audit(fen, played, caption)
    assert _clear_best_move_capture_claims(
        audit, caption, fen_before=fen, best_move_san=best) == 0


def test_no_best_move_clears_nothing():
    label, fen, played, best, caption = TRUE_CASES[0]
    audit = _audit(fen, played, caption)
    assert _clear_best_move_capture_claims(
        audit, caption, fen_before=fen, best_move_san=None) == 0
    assert audit.overall == "fail"


# ── the caption actually survives to the card ────────────────────────────

@pytest.mark.parametrize("label,fen,played,best,caption", TRUE_CASES)
def test_the_caption_is_no_longer_replaced_by_the_bare_severity_line(
        label, fen, played, best, caption):
    payload = {"caption": caption, "rule_name": "R12_blunder"}
    board = chess.Board(fen)
    telemetry = _verify_and_recover_caption(
        caption_payload=payload,
        fen_before=fen,
        played_move=board.parse_san(played),
        user_color=_user_color(fen),
        played_san=played,
        best_move_san=best,
        pv_after_best=[],
        severity_practical="mistake",
        mover_is_user=True,
    )
    assert telemetry is not None, label
    assert telemetry.get("verdict") != "fail_recovered", label
    assert payload["caption"] == caption, label
    assert "R_VERIFIER_RECOVERY" not in payload["rule_name"], label


def test_the_en_passant_caption_is_still_replaced():
    payload = {"caption": EP_CAPTION, "rule_name": "R12_blunder"}
    board = chess.Board(EP_FEN)
    telemetry = _verify_and_recover_caption(
        caption_payload=payload,
        fen_before=EP_FEN,
        played_move=board.parse_san("Ne2"),
        user_color="white",
        played_san="Ne2",
        best_move_san="bxc6+",
        pv_after_best=["Nxc6", "Rac1", "Ke8", "Nd5"],
        severity_practical="mistake",
        mover_is_user=True,
    )
    assert telemetry.get("verdict") == "fail_recovered"
    assert payload["caption"] != EP_CAPTION
    assert "R_VERIFIER_RECOVERY" in payload["rule_name"]


# ── gate 2: the player-facing V1 path ────────────────────────────────────
#
# game_decryption_v5_service's VERIFY_SOFTENED gate calls
# narrator_claim_verifier.verify_caption WITHOUT strict_v2, where the
# stored-capture hatch used to be switched off entirely:
#
#     stored_captures = _stored_capture_claims(facts) if strict_v2 else set()
#
# So clearing gate 1 only handed the sentence to a gate that killed it for
# the same wrong-board reason. Measured on the cards rather than on the
# audit calls: 24 collapsed to recovery at HEAD, 20 with gate 1 alone, and
# the free-capture sentence reached none of them.
#
# The strict_v2 union is deliberately left alone here. It is more
# permissive than the ply-bound proof -- it is what cleared the en-passant
# "pawn on c6" -- and narrowing it risks dropping legitimate clears about
# captures further down a line, which needs its own evidence.

def _v1_facts(fen_before, played, best, pv_after_best=()):
    return {
        "fen_before": fen_before,
        "move_san": played,
        "best_move_san": best,
        "pv_after_best": list(pv_after_best),
        "pv_after_played": [],
        "is_user_move": True,
    }


@pytest.mark.parametrize("label,fen,played,best,caption", TRUE_CASES)
def test_v1_clears_the_claim_the_better_move_proves(
        label, fen, played, best, caption):
    """The piece-on-square violation goes; other checks still apply.

    Asserting the whole caption verifies clean would be asserting more
    than this change earns. The Rxf5 caption carries a second, unrelated
    violation -- free_when_defended, because "look for a free piece to
    take" reads as a claim that f5 is free when e5 defends it -- and that
    is the real reason that card stays softened. Whether a generic
    closing principle should trip a claim check is a separate question
    with its own evidence.
    """
    from services.narrator_claim_verifier import verify_caption
    facts = _v1_facts(fen, played, best)
    violations = verify_caption(caption, facts, strict_v2=False)
    assert not [v for v in violations
                if v.get("check") == "piece_on_square"], label


def test_v1_still_refuses_the_en_passant_claim():
    from services.narrator_claim_verifier import verify_caption
    facts = _v1_facts(EP_FEN, "Ne2", "bxc6+",
                      ["Nxc6", "Rac1", "Ke8", "Nd5"])
    bad = verify_caption(EP_CAPTION, facts, strict_v2=False)
    assert bad, "the c6 claim is false and must not be cleared"
    assert any("c6" in (b.get("detail") or "") for b in bad)


def test_the_shared_helper_is_the_one_in_narrator():
    # Two copies of this proof would be the next thing to drift, and it
    # now clears the same claim at three separate gates.
    from services import caption_pipeline
    from services.narrator_claim_verifier import best_move_capture_pair
    assert best_move_capture_pair(EP_FEN, "bxc6+") == ("pawn", "c5")
    assert caption_pipeline._best_move_capture_pair(
        EP_FEN, "bxc6+") == ("pawn", "c5")


# ── the closing principle is not a claim about this capture ──────────────
#
# Every caption ends with a coaching principle, and those are generic
# imperatives. _check_free matched "a free piece" anywhere in the text and
# then tested THIS position's capture square, so
#
#     "Rxf5 was a bad mistake. exf5 was better -- it takes the pawn on f5.
#      Before every move, look for a free piece to take."
#
# was thrown away because f5 is defended by e5 -- over a sentence that
# makes no assertion about f5 at all. Found while measuring the fix above:
# clearing the piece-on-square claim handed this caption to the next gate,
# which killed it for an unrelated reason and left the card thinner than
# before the fix.
#
# The test is not phrasing. A sentence that never names this move or this
# square cannot be saying this capture is free.

RXF5_FEN = "6k1/pp2rrpp/q1p1p3/2PpQP2/1P6/6P1/1BN4P/4R1K1 b - - 2 29"


def test_a_generic_closing_principle_does_not_trip_the_free_check():
    from services.narrator_claim_verifier import verify_caption
    caption = ("Rxf5 was a bad mistake. exf5 was better — it takes the "
               "pawn on f5. Before every move, look for a free piece to "
               "take — being a piece up makes everything easier.")
    facts = _v1_facts(RXF5_FEN, "Rxf5", "exf5")
    assert [v for v in verify_caption(caption, facts, strict_v2=True)
            if v.get("check") == "free_when_defended"] == []


def test_calling_this_defended_capture_free_still_fails():
    # The negative control: the claim names f5, f5 is defended by e5, so
    # the check must still fire. Scoping the check must not disarm it.
    from services.narrator_claim_verifier import verify_caption
    caption = ("Rxf5 was a bad mistake. exf5 was better — it wins the "
               "pawn on f5 for free.")
    facts = _v1_facts(RXF5_FEN, "Rxf5", "exf5")
    assert [v for v in verify_caption(caption, facts, strict_v2=True)
            if v.get("check") == "free_when_defended"], (
        "f5 is defended by e5; calling it free is a false claim")


def test_naming_the_move_also_counts_as_claiming_it():
    from services.narrator_claim_verifier import verify_caption
    caption = "Rxf5 was a bad mistake. exf5 grabs a free piece."
    facts = _v1_facts(RXF5_FEN, "Rxf5", "exf5")
    assert [v for v in verify_caption(caption, facts, strict_v2=True)
            if v.get("check") == "free_when_defended"]

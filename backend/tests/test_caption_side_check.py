"""Stored model captions are checked on the card's board before they replace
its text (2026-11-12 reading of 56 real cards). Each case is a real caption."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.caption_side_check import stored_caption_problem  # noqa: E402
from services.caption_pipeline import reply_gap_sentence  # noqa: E402


def test_wrong_owner_is_refused():
    # da0e868e 41.Kf2 (user White): d4 is Black's pawn.
    fen = "8/2k5/8/pP6/P2p1P2/3r1N2/6P1/6K1 w - - 2 41"
    p = stored_caption_problem("This keeps coming back: Kf2 lets their rook hit your pawn on d4.",
                               fen_before=fen, played_san="Kf2", mover_is_user=True, fault_card=True)
    assert p and "belongs to the other side" in p


def test_opponent_move_did_not_leave_your_pawn_unguarded():
    # da0e868e 26...Rc8 (opponent Black): a2 was unguarded before Rc8 too.
    fen = "1k3r2/pp6/5r1p/8/2Pp4/3P1P2/PP4PN/4R1K1 b - - 0 26"
    p = stored_caption_problem("Your opponent played Rc8, leaving your a2 pawn with nothing guarding it.",
                               fen_before=fen, played_san="Rc8", mover_is_user=False, fault_card=True)
    assert p and "nothing guarded it before" in p
    # 40...Kc7: same shape.
    fen2 = "1k6/8/8/pP6/P2p1P2/3r1N2/6P1/6K1 b - - 1 40"
    assert stored_caption_problem("Your opponent's king move leaves your a4 pawn with nothing guarding it.",
                                  fen_before=fen2, played_san="Kc7", mover_is_user=False, fault_card=True)


def test_fine_under_a_fault_badge_is_refused():
    fen = "6r1/6P1/5k1K/8/8/8/p1N5/8 w - - 0 56"
    assert stored_caption_problem("Kh7 is fine, but the a-pawn is one step from queening.",
                                  fen_before=fen, played_san="Kh7", mover_is_user=True, fault_card=True)
    assert stored_caption_problem("Kh7 is fine here.", fen_before=fen, played_san="Kh7",
                                  mover_is_user=True, fault_card=False) is None


def test_true_captions_pass():
    # 7286e2f5 11...Nc6: "attack their knight and king" -- the d5 knight is theirs.
    fen = "r1bq4/pppp1kp1/7p/2bnP3/3n4/2PP4/PP3PPP/RNBQR1K1 b - - 0 11"
    assert stored_caption_problem("Your opponent's Nc6 lets Qf3+ attack their knight on d5 and king at once.",
                                  fen_before=fen, played_san="Nc6", mover_is_user=False, fault_card=True) is None
    # A move that really leaves a guarded piece: after 1.e4 d5, exd5 leaves... use a direct case:
    # White knight f3 guards e5 pawn; Ng5 leaves the e5 pawn unguarded.
    fen2 = "4k3/8/8/4P3/8/5N2/8/4K3 w - - 0 1"
    assert stored_caption_problem("Ng5 leaves your pawn on e5 with nothing guarding it.",
                                  fen_before=fen2, played_san="Ng5", mover_is_user=True, fault_card=True) is None


def test_reply_gap_names_the_played_move_when_asked():
    gap = {"their_reply": "Qxe1+", "allows": ["check"]}
    assert reply_gap_sentence(gap, mover_is_user=True) == "That lets them play Qxe1+ with check."
    assert reply_gap_sentence(gap, mover_is_user=True, subject="cxd4") == "cxd4 lets them play Qxe1+ with check."

"""What your move lets them do, derived from the board and both engine lines.

Mohit 2026-10-13: "why can't we build it deterministically, we already
have all the chess facts and stockfish there". This is that. Two facts:

CHECK -- the opponent's FIRST reply in each stored engine line, differenced,
read off the board one ply deep. Measured over 8,880 flagged cards before any
wording existed: when a check separates the two replies it favours the
engine's move 80.1% of the time (1,378 vs 343). attacks_us (64.5%) and
takes_centre (59.4%) were measured and left out as filler.

MATERIAL -- since 2026-11-06, the exchange ledger (services.reasoning.
differential) read along BOTH stored lines, square by square, with the same
claim rules the Why button uses. It replaced a one-ply capture sentence that
was measured at 69.7% as a discriminator but named the wrong thing: on
3628ebef m32 it said "That lets them take the rook on e7 with Qxe7" when the
line runs Rxe7 Qxe7 Rxe7 Kxe7 and the mover ends two pawns UP on e7. The loss
was elsewhere (the better move, Re6+, draws by perpetual check; fix 3 names
that). The ledger says nothing about Rxe7, which is the right amount.

Neither percentage is a truth rate. Whether their reply gives check is checked
on that board and is simply true or false. It is how often the fact is the
DISCRIMINATING difference, so a miss means saying something true but
secondary -- never something false.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_facts import _reply_gap  # noqa: E402
from services.caption_pipeline import reply_gap_sentence  # noqa: E402

# 1.d4 d5 2.c4 dxc4 3.Nc3 -- the QGA card that started this
QGA = "rnbqkbnr/ppp1pppp/8/8/2pP4/2N5/PP2PPPP/R1BQKBNR b KQkq - 1 3"

# Mohit v ChessKingsFather, 3628ebef move 32, White to move: Rxe7 played,
# Re6+ was the move. Both stored lines, as the card holds them.
RXE7 = "8/pp2n1q1/5k2/4R3/2PP2p1/1P4P1/n4P2/4R1K1 w - - 2 32"
RXE7_PV_PLAYED = ["Qxe7", "Rxe7", "Kxe7", "Kf1", "a5", "Ke1", "Nc1", "b4", "Nd3+", "Ke2", "Nxb4", "d5"]
RXE7_PV_BEST = ["Kg5", "Rxe7", "Qxd4", "R1e5+", "Kf6", "R7e6+", "Kf7", "Re7+", "Kg6", "R7e6+", "Kg7", "Re7+"]

# From the why-engine regression set: axb6 opens a7 and the rook is lost for
# a bishop there; Nc3 was the move.
AXB6 = "rn1q1rk1/b2b1ppp/1p1p1n2/PPp1pP2/4P3/3B1N1P/1B1P2P1/RN1QK2R w KQ - 0 14"
AXB6_PV_PLAYED = ["Qxb6", "Nc3", "c4", "Rxa7", "Rxa7", "Bxc4", "Nc6", "g4", "d5"]
AXB6_PV_BEST = ["bxa5", "Bc4", "Bc8", "d3", "Nbd7", "Bc1", "Bb7", "Bg5", "d5"]

# 1.d4 d5 2.e4?? dxe4: a pawn given for nothing, nothing takes back.
E4 = "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2"


def gap(fen, played, best, pvp, pvb, **kw):
    return _reply_gap(chess.Board(fen), played, best, pvp, pvb, **kw)


# ── it stays silent when the difference is not one of the two ────────

def test_silent_when_neither_reply_checks_and_no_material_changes_hands():
    """The QGA card: they answer e4 after Bf5 and e3 after a6. The real
    difference is the centre, which was measured at 59.4% and left out
    on purpose, so this correctly says nothing rather than reaching."""
    assert gap(QGA, "Bf5", "a6", ["e4", "Bg6"], ["e3", "b5"]) is None


def test_silent_when_the_reply_is_the_same_move():
    assert gap(QGA, "Bf5", "a6", ["e4"], ["e4"]) is None


def test_silent_on_missing_or_unplayable_input():
    assert gap(QGA, "Bf5", "a6", [], ["e3"]) is None
    assert gap(QGA, "Bf5", "a6", ["e4"], []) is None
    assert gap(QGA, None, "a6", ["e4"], ["e3"]) is None
    assert gap(QGA, "Bf5", "a6", ["Zz9"], ["e3"]) is None


# ── material: the ledger, not the first capture ──────────────────────

def test_rxe7_gets_no_capture_sentence_because_the_exchange_is_not_the_loss():
    """Rxe7 Qxe7 Rxe7 Kxe7 nets the mover two pawns on e7; the better line
    takes the same knight and gives a pawn back on d4. The two lines are
    level on material, so the ledger says nothing. The old one-ply sentence
    said "That lets them take the rook on e7 with Qxe7" here."""
    out = gap(RXE7, "Rxe7", "Re6+", RXE7_PV_PLAYED, RXE7_PV_BEST, mover_cp_loss=507)
    assert out is None


def test_a_lost_exchange_is_named_as_the_exchange():
    out = gap(AXB6, "axb6", "Nc3", AXB6_PV_PLAYED, AXB6_PV_BEST, mover_cp_loss=250)
    assert out is not None
    assert out["allows"] == ["material"]
    assert out["material"]["text"] == "After axb6, the exchange on a7 costs you a rook for a bishop."
    assert out["capture_square"] == "a7" and out["captured_piece"] == "rook"
    assert out["their_reply"] == "Qxb6"


def test_an_unanswered_capture_one_ply_in_is_still_said_plainly():
    out = gap(E4, "e4", "c4", ["dxe4"], ["e6"], mover_cp_loss=150)
    assert out is not None and "material" in out["allows"]
    assert out["material"]["text"] == "After e4, dxe4 simply takes your pawn on e4, and nothing can take back."
    assert out["capture_square"] == "e4" and out["captured_piece"] == "pawn"


def test_nothing_can_take_back_is_only_said_when_nothing_can():
    """Hand grade of the first final-code render (2026-11-06): 9 of 29
    "simply takes ... and nothing can take back" sentences sat on a board
    where a recapture was legal. The engine line does not play it, because it
    loses more, but the sentence states a board fact that is false."""
    # 157fead3 m18: Rxb7 takes the bishop and Qxb7 is legal; the line plays f5.
    out = gap("r4r1k/pbqp1p1p/3bpp2/2p4B/4N1Q1/6P1/P1P2P1P/1R3RK1 b - - 3 18",
              "Qc6", "Be7", ["Rxb7", "f5", "Qh4", "fxe4"], ["Qh4", "Bxe4", "Qxe4", "d5"], mover_cp_loss=222)
    assert out is not None and "material" in out["allows"]
    assert out["material"]["text"] == "After Qc6, Rxb7 takes your bishop on b7."
    # 17f38d52 m24: Rxg3+ takes the pawn with check and hxg3 is legal.
    out = gap("6r1/2pq1p1k/pb3p1p/3P2r1/4P3/3N1QP1/P4P1P/1R3RK1 w - - 0 24",
              "Qxf6", "Kg2", ["Rxg3+", "Kh1", "Rxd3", "Rg1"], ["Rg4", "Rfc1", "Rh4", "Nf4"], mover_cp_loss=713)
    assert "nothing can take back" not in out["material"]["text"]
    assert "simply" not in out["material"]["text"]
    # Where nothing can take back, it is still said (1.d4 d5 2.e4 dxe4).
    out = gap(E4, "e4", "c4", ["dxe4"], ["e6"], mover_cp_loss=150)
    assert out["material"]["text"].endswith("simply takes your pawn on e4, and nothing can take back.")


def test_the_opponents_card_words_the_cost_as_theirs():
    out = gap(AXB6, "axb6", "Nc3", AXB6_PV_PLAYED, AXB6_PV_BEST, mover_cp_loss=250, mover_is_user=False)
    assert out["material"]["text"] == "After axb6, the exchange on a7 costs them a rook for a bishop."


def test_a_capture_both_replies_make_is_not_the_difference():
    """Qxe6 falls on both branches, after Kc8 and after Kd8; only h6 is new.
    The same first reply cannot separate the moves by check, but the ledger
    reads on, and its shared-exchange rule keeps e6 out of the sentence."""
    fen = "8/1p1k1Q2/2p1p2p/p3P1p1/P7/2P3PK/1q6/8 b - - 3 38"
    out = gap(fen, "Kc8", "Kd8", ["Qxe6+", "Kd8", "Qxh6"], ["Qxe6", "Qe2"], mover_cp_loss=400)
    assert out is not None
    assert out["allows"] == ["material"]
    assert out["material"]["square"] == "h6"
    assert out["material"]["text"] == ("After Kc8, Qxe6+ starts a line that ends with Qxh6 "
                                       "taking your pawn on h6 for free.")


# ── the sentence ─────────────────────────────────────────────────────

def test_sentence_for_check():
    s = reply_gap_sentence({"their_reply": "Qxf2", "allows": ["check"]})
    assert s == "That lets them play Qxf2 with check."


def test_sentence_for_check_on_an_opponent_card():
    s = reply_gap_sentence({"their_reply": "Qh5", "allows": ["check"]}, mover_is_user=False)
    assert s == "That lets you play Qh5 with check."


def test_material_sentence_is_the_ledgers_and_needs_a_mistake_or_worse():
    g = {"their_reply": "Qxb6", "allows": ["material"],
         "material": {"text": "After axb6, the exchange on a7 costs you a rook for a bishop.", "square": "a7"}}
    assert reply_gap_sentence(g, severity="mistake") == "After axb6, the exchange on a7 costs you a rook for a bishop."
    assert reply_gap_sentence(g, severity="serious") == g["material"]["text"]
    assert reply_gap_sentence(g, severity="blunder") == g["material"]["text"]
    # On an inaccuracy a pawn claim contradicts the eval the card carries.
    assert reply_gap_sentence(g, severity="inaccuracy") == ""
    assert reply_gap_sentence(g) == ""


def test_check_and_material_together_say_the_check_first():
    g = {"their_reply": "Qxf2", "allows": ["check", "material"],
         "material": {"text": "After Nd5, the exchange on f2 costs you a rook for a knight.", "square": "f2"}}
    s = reply_gap_sentence(g, severity="serious")
    assert s == ("That lets them play Qxf2 with check. "
                 "After Nd5, the exchange on f2 costs you a rook for a knight.")
    # Without the tier the check still ships on its own.
    assert reply_gap_sentence(g) == "That lets them play Qxf2 with check."


def test_the_old_one_ply_capture_shape_is_gone():
    """A fact dict that only knows a first capture produces no sentence; the
    words "take the X on Y with Z" are no longer written anywhere."""
    legacy = {"their_reply": "Qxe7", "allows": ["capture"], "captured_piece": "rook", "capture_square": "e7"}
    assert reply_gap_sentence(legacy, severity="serious") == ""
    assert reply_gap_sentence({"their_reply": "Nf6", "allows": []}) == ""


def test_sentence_empty_on_empty_fact():
    assert reply_gap_sentence(None) == ""
    assert reply_gap_sentence({}) == ""
    assert reply_gap_sentence({"their_reply": "", "allows": ["check"]}) == ""


def test_the_check_sentence_is_short_enough_to_survive_the_cap():
    """The word cap cuts at the LAST sentence boundary, so an append that
    does not fit deletes itself silently. The pipeline tries the material
    sentence and the check on their own when both do not fit."""
    from services.caption_config import MAX_CAPTION_WORDS

    s = reply_gap_sentence({"their_reply": "Qxd3", "allows": ["check"]})
    assert len(s.split()) <= 8
    assert len(s.split()) < MAX_CAPTION_WORDS // 3


def test_facts_expose_it():
    """It has to reach the facts dict or no surface can use it, and the
    mover's loss has to reach the ledger's claim rules."""
    from services.caption_facts import extract_facts

    f = extract_facts(
        fen_before=E4,
        played_san="e4", best_move_san="c4", cp_loss=150,
        pv_after_played=["dxe4"], pv_after_best=["e6"],
        mover_is_user=True, full_move_number=2)
    assert "reply_gap" in f
    assert (f["reply_gap"] or {}).get("capture_square") == "e4"
    assert "material" in (f["reply_gap"] or {}).get("allows", [])

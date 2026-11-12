"""Reading a line for a caption: the situation, the deciding moment, what is
relevant, and the rule that a study explains instead of listing moves
(Mohit 2026-11-12)."""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import why_study as ws  # noqa: E402

E5_FEN = "r1bqk1nr/pppp1pp1/2n4p/2b5/2BpP3/5N2/PPP2PPP/RNBQ1RK1 w kq - 0 6"
CARD_BETTER = "c3 dxc3 Bxf7+ Kxf7 Qd5+ Kf8 Qxc5+ d6 Qxc3 Qf6 e5 dxe5 Nbd2".split()
CARD_PLAYED = "e5 Nge7 c3 dxc3 Nxc3 O-O Bf4 d6 exd6 cxd6 Rc1 Ng6 Bg3".split()


def test_better_line_wins_the_pawn_back_and_later_trades_are_not_relevant():
    r = ws.read_line(E5_FEN, CARD_BETTER, chess.BLACK, for_side=chess.WHITE)
    assert r["standing_before"] == "you are a pawn up"
    assert r["deciding_moment"].startswith("the opponent wins material: material is even")
    assert r["relevant_moves"] == ["c3", "dxc3", "Bxf7+", "Kxf7", "Qd5+", "Qxc5+", "Qxc3"]
    after = [s for s in r["steps"][r["deciding_move_index"] + 1:]]
    assert after and not any(s["relevant"] for s in after)


def test_played_line_wins_nothing_back():
    r = ws.read_line(E5_FEN, CARD_PLAYED, chess.BLACK, for_side=chess.BLACK)
    assert r["deciding_move_index"] is None and r["relevant_moves"] == []


def test_mid_trade_counts_are_never_the_deciding_moment():
    # exd6 is followed by cxd6: the moment after exd6 is not quiet.
    r = ws.read_line(E5_FEN, CARD_PLAYED, chess.BLACK, for_side=chess.WHITE)
    assert r["deciding_move_index"] is None


def test_mate_is_the_deciding_moment():
    fen = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"
    r = ws.read_line(fen, ["Rd8#"], chess.WHITE, for_side=chess.WHITE)
    assert r["deciding_moment"] == "mate by you" and r["relevant_moves"] == ["Rd8#"]


def test_situation_words():
    assert ws.standing_words(0) == "material is even"
    assert ws.standing_words(1) == "you are a pawn up" and ws.standing_words(-3) == "you are a piece down"
    assert ws.eval_words(600) == "you are clearly winning" and ws.eval_words(-20) == "about equal"
    assert ws.eval_words(None, -1) == "you get mated by force"


def test_moves_named_allows_played_better_and_squares_only():
    assert ws.moves_named("If you take with dxc3, Bxf7+ and Qd5+ check your king.", "e5", "c3") == \
        ["Bxf7+", "Qd5+", "dxc3"]
    assert ws.moves_named("Their e5 lets you keep your pawn. The better plan was c3, attacking your pawn on d4.",
                          "e5", "c3") == []


def test_the_gate_holds_a_study_that_lists_moves():
    out = ws.gate_text("c3 attacks your pawn on d4. If you take, Bxf7+ and Qd5+ win it back.", [],
                       fen_before=E5_FEN, played_san="e5", better_san="c3", mover_is_user=False)
    assert any("names moves instead of explaining" in f for f in out)

"""Lost guard, two steps: the trade on the square decides the piece it held.

Scope: docs/why_lost_guard_threat_scope.md. Position from chesstribe64's game
4ec5dfca (26.Qc2, stored cp_loss 158), checked on the board and against
Stockfish 2026-11-16: after 26...f6, fxe5 fxe5 Bxe5+ wins e5 and leaves the
knight on d6 with no guard; after 26.Rbc1 the same trade ends Qxe5.
"""
import chess

from services.reasoning.lost_guard import lost_guard_threat, trade

QC2_FEN = "r2q1rk1/1p3pbp/p1bNp1p1/2RpP3/1P3P2/P5K1/4Q1PP/1R6 w - - 3 26"


def _run(fen, played, alt, reply, mover_is_user=True):
    root = chess.Board(fen)
    p, a = root.parse_san(played), root.parse_san(alt)
    after = root.copy()
    after.push(p)
    return lost_guard_threat(root, p, a, after.parse_san(reply).uci(), mover_is_user=mover_is_user)


def test_the_trade_is_played_out_with_xrays():
    # After Qc2 f6 and a pass: the g7 bishop sees e5 only once f6 has captured.
    board = chess.Board(QC2_FEN)
    board.push_san("Qc2")
    board.push_san("f6")
    board.push(chess.Move.null())
    out = trade(chess.Board(board.fen()), chess.E5)
    assert [s["san"] for s in out["steps"]] == ["fxe5", "fxe5", "Bxe5+"]
    assert out["net"] == 100


def test_the_better_move_keeps_the_trade_from_starting():
    # After Rbc1 f6 the trade would end Qxe5, so Black does not begin it.
    board = chess.Board(QC2_FEN)
    board.push_san("Rbc1")
    board.push_san("f6")
    board.push(chess.Move.null())
    out = trade(chess.Board(board.fen()), chess.E5)
    assert out["steps"] == [] and out["net"] == 0


def test_qc2_is_explained_by_the_guard_it_gave_up():
    out = _run(QC2_FEN, "Qc2", "Rbc1", "f6")
    assert out["fires"] is True
    cause = out["cause"]
    assert cause["kind"] == "lost_guard" and cause["variant"] == "threat"
    assert (cause["guard_piece"], cause["guard_square"]) == ("queen", "e2")
    assert (cause["square"], cause["target_piece"], cause["target_square"]) == ("e5", "knight", "d6")
    assert cause["trade_san"] == ["fxe5", "fxe5", "Bxe5+"]
    assert cause["text"] == ("Qc2 stops your queen guarding e5. After f6, they win the trade on e5: their bishop "
                             "takes last with check. Then nothing guards your knight on d6. "
                             "Rbc1 keeps your queen guarding e5.")
    assert not any(ch.isdigit() for ch in cause["text"].replace("e5", "").replace("d6", "")
                   .replace("Qc2", "").replace("f6", "").replace("Rbc1", ""))


def test_the_opponents_move_is_worded_from_the_readers_side():
    cause = _run(QC2_FEN, "Qc2", "Rbc1", "f6", mover_is_user=False)["cause"]
    assert cause["text"].startswith("Qc2 stops their queen guarding e5. After f6, you win the trade on e5: your bishop")


def test_a_move_that_does_not_move_the_guard_is_silent():
    # Negative control: Rbc1 leaves the queen on e2; nothing it guarded is lost.
    out = _run(QC2_FEN, "Rbc1", "Qc2", "f6")
    assert out["fires"] is False


def test_a_better_move_that_also_drops_the_guard_is_not_the_difference():
    # Qd2 also takes the queen off e5 (d2 does not see e5), so the guard is
    # not what separates Qc2 from Qd2.
    out = _run(QC2_FEN, "Qc2", "Qd2", "f6")
    assert out["fires"] is False


def test_a_capturing_reply_is_left_to_the_one_step_rules():
    board = chess.Board(QC2_FEN)
    board.push_san("Qc2")
    capture = next(m for m in board.legal_moves if board.is_capture(m))
    root = chess.Board(QC2_FEN)
    out = lost_guard_threat(root, root.parse_san("Qc2"), root.parse_san("Rbc1"), capture.uci(), mover_is_user=True)
    assert out["fires"] is False and out["why_not"] in ("reply_not_quiet", "reply_not_on_both_branches")

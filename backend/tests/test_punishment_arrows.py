"""Blunder arrows must draw the engine's refutation, never a SEE guess.

Mohit 2026-09-28, on move 30 of game 26d74ad6, where the caption said
"Qf7 lets Nd6 attack the queen on f7" and the board drew a red arrow d4->f2:
"wrong arrow here, look at stockfish what is this suggesting and what are you
doing there?"

Stockfish's answer in that position is Nd6. d4->f2 is Qxf2+, which loses the
queen to Kxf2 -- it was drawn because static_exchange_eval does not count the
king as a defender, so an f2 pawn guarded by Kg1 alone scored "free".

Every assertion below is computed from squares and legality, never from the
text of a caption.
"""
import chess
import pytest

from services.caption_pipeline import _punishment_arrows

# The position Mohit reported, before 30.Qf7.
REPORTED = "1k2n2r/p1p5/1p5p/8/3q4/1Q3B2/PP3PP1/4R1K1 w - - 0 30"
REPORTED_PV = ["Nd6", "Qd7", "Qc4", "Rd1"]   # as stored by the committed analysis


def _draw(fen, san, pv, *, cp_loss=523, mover_is_user=True):
    board = chess.Board(fen)
    return _punishment_arrows(
        board,
        board.parse_san(san),
        mover_is_user=mover_is_user,
        cp_loss=cp_loss,
        pv_after_played=pv,
    )


class TestTheReportedCard:
    def test_never_draws_the_queen_sacrifice(self):
        assert {"d4", "f2"} not in [
            {a["from"], a["to"]} for a in _draw(REPORTED, "Qf7", REPORTED_PV)
        ]

    def test_draws_the_move_stockfish_actually_plays(self):
        arrows = _draw(REPORTED, "Qf7", REPORTED_PV)
        assert arrows, "a 523cp blunder with a stored refutation must show something"
        board = chess.Board(REPORTED)
        board.push(board.parse_san("Qf7"))
        nd6 = board.parse_san("Nd6")
        assert arrows[0]["from"] == chess.square_name(nd6.from_square)
        assert arrows[0]["to"] == chess.square_name(nd6.to_square)

    def test_the_threat_arrow_points_at_the_queen_the_caption_names(self):
        arrows = _draw(REPORTED, "Qf7", REPORTED_PV)
        assert len(arrows) == 2, "a quiet refutation must show what it threatens"
        assert arrows[1]["from"] == "d6" and arrows[1]["to"] == "f7"
        assert arrows[1]["color"] != arrows[0]["color"], "replies get their own colour"

    def test_f2_really_is_defended_so_the_old_arrow_really_was_wrong(self):
        # The negative control for the bug itself, proved on the board.
        board = chess.Board(REPORTED)
        board.push(board.parse_san("Qf7"))
        assert chess.square_name(next(iter(board.attackers(chess.WHITE, chess.F2)))) == "g1"
        board.push(board.parse_san("Qxf2+"))
        assert board.is_capture(board.parse_san("Kxf2")), "the king simply takes the queen"


class TestEveryArrowIsALegalMove:
    """board.attackers() is pseudo-legal; that drew arrows for illegal captures."""

    @pytest.mark.parametrize(
        "fen,san,pv",
        [
            (REPORTED, "Qf7", REPORTED_PV),
            ("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
             "Ng5", ["d5"]),
        ],
    )
    def test_arrow_endpoints_are_reachable(self, fen, san, pv):
        board = chess.Board(fen)
        played = board.parse_san(san)
        after = board.copy()
        after.push(played)
        for arrow in _punishment_arrows(
            board, played, mover_is_user=True, cp_loss=300, pv_after_played=pv
        ):
            frm = chess.parse_square(arrow["from"])
            to = chess.parse_square(arrow["to"])
            if arrow["color"] == "red":
                assert any(
                    m.from_square == frm and m.to_square == to for m in after.legal_moves
                ), f"{arrow} is not a legal move for the opponent"


class TestSilence:
    def test_no_stored_line_draws_nothing(self):
        assert _draw(REPORTED, "Qf7", []) == []

    def test_opponent_cards_draw_nothing(self):
        assert _draw(REPORTED, "Qf7", REPORTED_PV, mover_is_user=False) == []

    def test_small_losses_draw_nothing(self):
        assert _draw(REPORTED, "Qf7", REPORTED_PV, cp_loss=40) == []

    def test_a_quiet_reply_that_threatens_nothing_is_silent(self):
        # 30...Kb7 attacks no piece; v180 drew king shuffles in red.
        assert _draw(REPORTED, "Qf7", ["Kb7"]) == []

    def test_an_unparseable_line_is_silent_not_a_crash(self):
        assert _draw(REPORTED, "Qf7", ["Zz9"]) == []


class TestCaptureRefutations:
    def test_a_capture_refutation_draws_exactly_the_capture(self):
        # Black hangs the queen on d4; White's refutation is the capture itself.
        fen = "4k3/8/8/8/3q4/8/8/3QK3 b - - 0 1"
        board = chess.Board(fen)
        arrows = _punishment_arrows(
            board, board.parse_san("Qd5"), mover_is_user=True, cp_loss=900,
            pv_after_played=["Qxd5"],
        )
        assert arrows == [{"from": "d1", "to": "d5", "color": "red", "teach": True}]

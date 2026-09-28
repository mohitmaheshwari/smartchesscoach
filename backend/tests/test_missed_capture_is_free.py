"""An opponent's missed capture is only "free" if taking it actually keeps it.

Mohit 2026-09-28, on move 4 of game 26d74ad6, an Opponent card reading
"Opponent's d6 is a mistake -- they had Nxe4, grabbing your pawn on e4 for
free."  On

    r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R b KQkq - 4 4

the e4 pawn is defended by the knight on c3, and the line the engine plays --
Nxe4 Nxe4 d5 Bd3 dxe4 Bxe4 -- ends dead level. Nothing was free, nothing was
won; the flag was set by `is_capture` alone.

Every assertion computes material from the board. None reads caption text.
"""
import chess

from services.caption_facts import PIECE_VALUE_CP, legal_exchange_gain

# The position Mohit reported, Black to move, before 4...d6.
REPORTED = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R b KQkq - 4 4"


def _gain(fen: str, san: str) -> int:
    board = chess.Board(fen)
    move = board.parse_san(san)
    return legal_exchange_gain(board, move.to_square, board.turn, first_move=move)


class TestTheReportedPosition:
    def test_e4_is_defended_so_the_capture_is_not_free(self):
        board = chess.Board(REPORTED)
        defenders = {chess.square_name(s) for s in board.attackers(chess.WHITE, chess.E4)}
        assert defenders == {"c3"}, "the c3 knight is exactly why 'free' was wrong"

    def test_nxe4_wins_nothing(self):
        # Below a pawn's value, so the "for free" wording must not fire.
        assert _gain(REPORTED, "Nxe4") < PIECE_VALUE_CP[chess.PAWN]

    def test_the_whole_line_is_level(self):
        board = chess.Board(REPORTED)
        material_before = _material(board)
        for san in ("Nxe4", "Nxe4", "d5", "Bd3", "dxe4", "Bxe4"):
            board.push(board.parse_san(san))
        assert _material(board) == material_before, "nobody ends up a pawn richer"


class TestGenuinelyFreeCapturesStillCount:
    """The positive control: the gate must not silence real free material."""

    def test_an_undefended_pawn_is_free(self):
        # Black rook takes an undefended white pawn on a2 and keeps it.
        fen = "4k3/8/8/8/8/8/P6r/4K3 b - - 0 1"
        assert _gain(fen, "Rxa2") >= PIECE_VALUE_CP[chess.PAWN]

    def test_an_undefended_queen_is_free(self):
        # Open a-file, and e1 is nowhere near a1, so the queen is simply lost.
        fen = "q3k3/8/8/8/8/8/8/Q3K3 b - - 0 1"
        assert _gain(fen, "Qxa1+") >= PIECE_VALUE_CP[chess.QUEEN]


class TestKingDefendersCount:
    """static_exchange_eval skips king recaptures; this must not."""

    def test_a_pawn_guarded_only_by_the_king_is_not_free(self):
        # Black queen can take f2, but Kg1 simply takes back.
        fen = "1k6/8/8/8/3q4/8/5P2/6K1 b - - 0 1"
        board = chess.Board(fen)
        assert {chess.square_name(s) for s in board.attackers(chess.WHITE, chess.F2)} == {"g1"}
        assert _gain(fen, "Qxf2+") < PIECE_VALUE_CP[chess.PAWN]


def _material(board: chess.Board) -> int:
    total = 0
    for _sq, piece in board.piece_map().items():
        value = PIECE_VALUE_CP.get(piece.piece_type, 0)
        total += value if piece.color == chess.WHITE else -value
    return total

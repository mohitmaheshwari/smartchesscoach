"""A caption may not call a defended piece "lost".

distilled_caption_service decided "was the piece really lost?" from cp_loss:

    # only a CLEAN loss: opp captures our >=minor piece AND cp_loss is
    # consistent with actually losing it (>= ~half its value)
    if (... and cpl >= VAL[c.piece_type] * 0.5 ...)

cp_loss measures the whole move, so a move that loses 200cp by MISSING
something elsewhere reads as proof that an unrelated piece was captured. The
module has its own VAL table and never consulted legally_hanging_pieces, the
exchange-truth authority the rest of the system uses.

Flagged live 2026-09-09, game 46edaf7e move 7:

    "h4 runs into Nxb3, losing your bishop on b3; instead Nxe5 was stronger
     because it captures the pawn on e5, whereas h4 hands material away."

The stored row falsifies it three times over:
  * b3 is defended twice, by a2 and c2 -- Nxb3 axb3 is a knight-for-bishop
    trade, not a loss
  * pv_after_played is ["d6","Bg5","Nxb3","axb3"] -- Nxb3 is three plies deep
    and the recapture is in the same list the builder walks
  * pv_after_best is ["Nxb3","axb3",...] -- the same trade happens in the
    engine's own best line
  * cp_loss 200 came from missing Nxe5, a free pawn, and the row's own
    cognitive_gap says "missed_tactic", not a hung piece

Corpus measurement (400 games): 672 moves produce a specific "losing your X on
Y" claim; 146 of them (21.7%) are refuted by exchange truth -- ordinary trades
and recaptures narrated as blunders.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import distilled_caption_service as dcs

FLAGGED_FEN = "r1bqk1nr/2ppbppp/p7/np2p3/4P3/1BNP1N2/PPP2PPP/R1BQK2R w KQkq - 2 7"


class _Inp:
    """Shape the service expects, filled from the real stored row."""

    fen_before = FLAGGED_FEN
    played_san = "h4"
    best_move_san = "Nxe5"
    mover_is_white = True
    cp_loss = 200
    pv_after_played = ["d6", "Bg5", "Nxb3", "axb3"]
    pv_after_best = ["Nxb3", "axb3", "Bb7", "Qg4"]
    eval_before_cp = 159
    eval_after_cp = -41
    user_color = "white"


def test_the_bishop_on_b3_is_defended_twice():
    board = chess.Board(FLAGGED_FEN)
    board.push_san("h4")
    defenders = {chess.square_name(s) for s in board.attackers(chess.WHITE, chess.B3)}
    assert defenders == {"a2", "c2"}


def test_a_defended_piece_is_not_reported_as_lost():
    board = chess.Board(FLAGGED_FEN)
    board.push_san("h4")
    for san in ("d6", "Bg5"):
        board.push_san(san)
    capture = board.parse_san("Nxb3")
    assert dcs._capture_really_wins_the_piece(board, capture, chess.WHITE) is False


def test_walked_into_tactic_abstains_when_no_material_is_lost():
    # The template ends "whereas {played_san} hands material away", so it may
    # only render when the line actually costs material. Here it does not:
    # Nxb3 is answered by axb3.
    assert dcs._mistake_caption(_Inp(), "walked_into_tactic") is None


def test_line_costs_material_rejects_an_even_trade():
    board = chess.Board(FLAGGED_FEN)
    board.push_san("h4")
    assert dcs._line_costs_material(board, _Inp.pv_after_played, chess.WHITE) is False


def test_line_costs_material_accepts_a_real_loss():
    # Positive control: same position, but the opponent wins the bishop and
    # nothing comes back.
    board = chess.Board(FLAGGED_FEN)
    board.push_san("h4")
    assert dcs._line_costs_material(board, ["Nxb3"], chess.WHITE) is True


def test_the_true_lesson_is_still_available():
    # The real mistake was missing a free pawn, and that template is truthful:
    # e5 is undefended, so Nxe5 wins it outright.
    board = chess.Board(FLAGGED_FEN)
    assert not board.attackers(chess.BLACK, chess.E5)
    caption = dcs._mistake_caption(_Inp(), "missed_free_material")
    assert caption is not None
    assert "e5" in caption

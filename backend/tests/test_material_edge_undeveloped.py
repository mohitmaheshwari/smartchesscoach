"""OP_MATERIAL_EDGE_UNDEVELOPED - the four conditions, locked.

The lesson is Mohit's, 2026-10-12, on 26.Nb3 in

    rnbqkb1r/pp3ppp/8/2pp4/3Np3/2N5/PPPP1PPP/R1BQKB1R w

    "White is a whole knight up for a pawn ... the extra piece is worth
     nothing while five of your pieces are still at home. So the lesson
     here isn't 'don't get chased'. It's: When you're a piece up but
     undeveloped, the extra piece does nothing until your pieces are
     out. Use checks and threats to develop with tempo."

I had first given him the surface reading of that move -- the knight
gets chased, tempo -- and he corrected it to the material one.

Every test below is a board fact computed from squares and material,
never a string match on the caption
([[feedback_verify_by_maths_never_strings]]).

The negative controls exist because the first version of this detector
fired on exactly two cards in a 2,227-move corpus and BOTH were wrong,
in the same way: the engine's move "developed" the queen off her home
square (Qh5 off d1, Qd7 off d8), which OP_QUEEN_OUT_EARLY in the same
catalog teaches against. Reading the two cards caught it; the count
could not ([[feedback_verify_with_own_perspective]]).
"""
import sys
from pathlib import Path

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_facts import (  # noqa: E402
    _MATERIAL_EDGE_CP,
    _MIN_PIECES_AT_HOME,
    _material_edge_cp,
    _p_op_material_edge_undeveloped,
    _pieces_at_home,
)

MOHIT_FEN = "rnbqkb1r/pp3ppp/8/2pp4/3Np3/2N5/PPPP1PPP/R1BQKB1R w - - 0 13"
PRINCIPLE = "OP_MATERIAL_EDGE_UNDEVELOPED"


def _facts(played, best, cp_loss=150, colour="white", phase="middlegame"):
    return {
        "phase": phase,
        "cp_loss": cp_loss,
        "moving_piece_color": colour,
        "played_san": played,
        "best_move_san": best,
    }


def _fire(fen, played, best, **kw):
    return _p_op_material_edge_undeveloped(
        _facts(played, best, **kw), chess.Board(fen))


# ── the position itself, before any detector runs ────────────────────

def test_mohit_position_is_a_piece_up_for_a_pawn():
    """The premise of the lesson, from material rather than from the
    word 'knight': +300 for the extra piece, -100 for the pawn."""
    board = chess.Board(MOHIT_FEN)
    assert _material_edge_cp(board, chess.WHITE) == 200
    assert _material_edge_cp(board, chess.BLACK) == -200


def test_mohit_position_has_five_pieces_at_home():
    """His count. The queen is one of the five and stays in this count."""
    board = chess.Board(MOHIT_FEN)
    assert _pieces_at_home(board, chess.WHITE) == [
        "a1", "c1", "d1", "f1", "h1"]


def test_queen_is_excluded_from_the_development_count_only():
    board = chess.Board(MOHIT_FEN)
    assert "d1" in _pieces_at_home(board, chess.WHITE)
    assert "d1" not in _pieces_at_home(board, chess.WHITE, exclude_queen=True)


# ── the positive control ─────────────────────────────────────────────

def test_fires_on_mohits_card():
    """Nb3 moves an already-developed knight; Bb5+ brings f1 into the
    game with check, which is the 'checks and threats' half of his
    sentence."""
    ev = _fire(MOHIT_FEN, "Nb3", "Bb5+")
    assert ev is not None
    assert ev["principle_id"] == PRINCIPLE
    assert ev["evidence"]["material_edge_cp"] == 200
    assert ev["evidence"]["developed_by_best"] == ["f1"]
    assert ev["evidence"]["best_move_gives_check"] is True
    # condition 4 makes the engine's move the aligned move by definition
    assert ev["engine_endorsement"] == "best"
    # _normalize_san strips check/mate suffixes, which is the existing
    # convention everywhere else in caption_facts.py -- the aligned move
    # is still Bb5, the check is carried in best_move_gives_check above.
    assert ev["aligned_moves_offered"] == ["Bb5"]


# ── the four conditions, each denied in turn ─────────────────────────

def test_silent_when_not_a_piece_up():
    """Equal material. A pawn up is not 'the extra piece does nothing',
    so the threshold stays at a piece."""
    fen = "rnbqkb1r/pp3ppp/8/2pp4/3np3/2N5/PPPP1PPP/R1BQKB1R w - - 0 13"
    board = chess.Board(fen)
    assert _material_edge_cp(board, chess.WHITE) < _MATERIAL_EDGE_CP
    assert _fire(fen, "Nb5", "Bb5+") is None


def test_silent_when_already_developed():
    """Same material edge, pieces out. Castled, both bishops and both
    rooks active -- nothing left to finish."""
    fen = "rnbqkb1r/pp3ppp/8/2pp4/3NpB2/2N1B3/PPPP1PPP/R2Q1RK1 w - - 0 13"
    board = chess.Board(fen)
    assert _material_edge_cp(board, chess.WHITE) >= _MATERIAL_EDGE_CP
    assert len(_pieces_at_home(board, chess.WHITE)) < _MIN_PIECES_AT_HOME
    assert _fire(fen, "Nb3", "Qd2") is None


def test_silent_when_the_played_move_already_develops():
    """Bb5+ IS the developing move. A card cannot teach 'develop' about
    a move that developed -- condition 3."""
    assert _fire(MOHIT_FEN, "Bb5+", "Nb5") is None


def test_silent_when_the_engine_move_develops_nothing():
    """Condition 4. Without it the principle fires on every move of
    every won game, which is a base rate and not a lesson."""
    assert _fire(MOHIT_FEN, "Nb3", "Nb5") is None


# ── the two defects the first corpus run exposed ─────────────────────

def test_a_queen_sortie_is_not_development():
    """Both of the detector's first two corpus fires had the engine
    'developing' the queen off her home square. OP_QUEEN_OUT_EARLY
    teaches against exactly that, so praising it would put two shipped
    principles in contradiction on one board."""
    board = chess.Board(MOHIT_FEN)
    before = _pieces_at_home(board, chess.WHITE, exclude_queen=True)
    board.push_san("Qh5")
    after = _pieces_at_home(board, chess.WHITE, exclude_queen=True)
    assert after == before, "the queen must not count as developed"
    assert _fire(MOHIT_FEN, "Nb3", "Qh5") is None


def test_silent_on_terminal_cp_loss():
    """cp_loss is 6000+ on delivered checkmates. Nxf7+ at 9330cp was the
    other bad first fire; whatever that move is, 'finish developing' is
    not its lesson."""
    assert _fire(MOHIT_FEN, "Nb3", "Bb5+", cp_loss=9330) is None
    assert _fire(MOHIT_FEN, "Nb3", "Bb5+", cp_loss=150) is not None


# ── gates inherited from the catalog entry ───────────────────────────

def test_silent_in_the_endgame():
    """phase_in_scope is opening + middlegame."""
    assert _fire(MOHIT_FEN, "Nb3", "Bb5+", phase="endgame") is None


def test_silent_on_an_engine_approved_move():
    """gate_policy includes cp_loss_strict."""
    assert _fire(MOHIT_FEN, "Nb3", "Bb5+", cp_loss=0) is None


def test_silent_when_played_is_the_best_move():
    assert _fire(MOHIT_FEN, "Bb5+", "Bb5+") is None


def test_works_for_both_sides():
    """The home-square table is written out per colour, so the Black
    half is a separate code path that nothing else here exercises.
    board.mirror() swaps colour and flips vertically, so the mirror is
    exact by construction instead of by my FEN typing -- the first
    version of this test hand-wrote a position where Black was only a
    pawn up, and would have passed for the wrong reason."""
    board = chess.Board(MOHIT_FEN)
    mirrored = board.mirror()
    assert mirrored.turn == chess.BLACK
    assert (_material_edge_cp(mirrored, chess.BLACK)
            == _material_edge_cp(board, chess.WHITE) == 200)
    assert _pieces_at_home(mirrored, chess.BLACK) == [
        "a8", "c8", "d8", "f8", "h8"]

    ev = _p_op_material_edge_undeveloped(
        _facts("Nb6", "Bb4+", colour="black"), mirrored)
    assert ev is not None, "the Black path must reach the same lesson"
    assert ev["evidence"]["material_edge_cp"] == 200
    assert ev["evidence"]["developed_by_best"] == ["f8"]
    assert ev["evidence"]["best_move_gives_check"] is True


# ── the collision this detector caused, locked shut ──────────────────

def test_pieces_still_at_home_is_not_shadowed():
    """caption_facts already had _HOME_SQUARES and pieces_still_at_home
    before this detector was added. The first version of the detector
    defined a SECOND _HOME_SQUARES, later in the same module and in a
    different shape, so at import time it won and pieces_still_at_home
    began raising TypeError -- which OP_SAME_PIECE_TWICE depends on.

    Nothing failed. Every detector call is wrapped in
    `except Exception: ev = None`, so the principle went silent while
    2,227 corpus moves and 14 tests in this file all passed.

    This is the positive control for that absence
    ([[feedback_a_zero_needs_a_positive_control]]): the start position
    has all seven pieces at home, so a working helper must return 7.
    """
    from services.caption_facts import _HOME_SQUARES, pieces_still_at_home

    assert pieces_still_at_home(chess.Board(), chess.WHITE) == 7
    assert pieces_still_at_home(chess.Board(), chess.BLACK) == 7
    # the shape the existing helper unpacks: pairs, not dict keys
    for colour in (chess.WHITE, chess.BLACK):
        for entry in _HOME_SQUARES[colour]:
            sq, piece_type = entry
            assert isinstance(sq, int) and isinstance(piece_type, int)


def test_the_detector_and_the_existing_helper_agree():
    """Two readers of one table must not drift. Both count the same
    seven squares; _pieces_at_home just returns the names."""
    from services.caption_facts import pieces_still_at_home

    board = chess.Board(MOHIT_FEN)
    assert len(_pieces_at_home(board, chess.WHITE)) == pieces_still_at_home(
        board, chess.WHITE)


def test_no_second_piece_value_table():
    """PIECE_VALUE_CP is the module's material table. The detector reuses
    it rather than adding a 39th material count to the repo."""
    import services.caption_facts as cf

    assert not hasattr(cf, "_PIECE_CP")
    assert cf.PIECE_VALUE_CP[chess.KNIGHT] - cf.PIECE_VALUE_CP[chess.PAWN] == 200

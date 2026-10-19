"""Two of your own units on one line, and the opponent about to exploit it.

The mirror of `_aligned_pieces_evidence`, which only ever walked OUR sliders
looking for two of THEIR pieces — the motif we create. This is the motif we
allow, and the pipeline could not see it: run on the gold position the real
extractor returned 124 facts with `aligned_pieces_evidence = []`.

Gold case: game 66090078, move 30, FEN
`8/6pp/6k1/3p4/P2Pn1b1/B7/5rPP/3R1BK1 w - - 0 30`. White played `Rc1`
(cp_loss 284, +2.92 -> +0.08) when `Ra1` was the only move that kept anything
— Stockfish depth 26: Ra1 +2.79, Rb1 +0.05, Re1 +0.01, Rc1 -0.03. The black
rook on f2 steps to a2, hits the undefended bishop on a3, and when it moves
the passed pawn on a4 goes with it.

The gate matters more than the geometry. Measured over 500 games (2,285 user
mistakes vs a control of 9,815 good moves,
docs/own_side_alignment_scope.md §0b/§0c):

    geometry alone                      52.3% bad / 40.8% good     1.3x
    + opponent's real reply enters       6.1% / 0.1%                85x
    + that reply ATTACKS the front unit  4.4% / 0.04%              107x
    + no king in the pair, not mate      5.5% / 0.03%              180x

So the tests that matter here are the ones asserting it stays SILENT.
"""
import sys
from pathlib import Path

import chess
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.caption_facts import (  # noqa: E402
    _confirm_own_alignment,
    _own_alignment_exposure,
)

GOLD = "8/6pp/6k1/3p4/P2Pn1b1/B7/5rPP/3R1BK1 w - - 0 30"
GOLD_PV = ["Ra2", "Bf8", "Kf7", "Bc5"]


def _gold():
    return chess.Board(GOLD)


# ------------------------------------------------------------- geometry

def test_the_shape_is_found_at_all():
    shapes = _own_alignment_exposure(_gold(), chess.WHITE)
    keys = {(s["entry_square"], s["front_piece_square"], s["rear_piece_square"])
            for s in shapes}
    assert ("a2", "a3", "a4") in keys


def test_the_shape_names_the_right_units_and_reuses_the_existing_taxonomy():
    shape = next(s for s in _own_alignment_exposure(_gold(), chess.WHITE)
                 if s["front_piece_square"] == "a3")
    assert shape["front_piece"] == "bishop"
    assert shape["rear_piece"] == "pawn"
    assert shape["front_undefended"] is True
    assert shape["rear_is_passed_pawn"] is True
    # Same vocabulary `_aligned_pieces_evidence` emits, not a second taxonomy.
    assert shape["front_value_vs_rear"] == "higher"


def test_geometry_alone_is_not_a_claim():
    """It sits on 41% of GOOD moves. If this ever becomes a fact a caption can
    read directly, the feature starts explaining correct play."""
    from services import caption_facts

    board = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6", "Bb5"):
        board.push_san(san)
    # The opening position has these shapes all over it; that is the point.
    assert _own_alignment_exposure(board, chess.BLACK) != []


# ------------------------------------------------------------ the gate

def test_the_gold_case_is_confirmed():
    hit = _confirm_own_alignment(_gold(), chess.WHITE, "Rc1", "Ra1", GOLD_PV)
    assert hit is not None
    assert hit["entry_square"] == "a2"
    assert hit["front_piece_square"] == "a3"
    assert hit["rear_piece_square"] == "a4"
    assert hit["opponent_reply_san"] == "Ra2"
    assert hit["best_move_guards_entry"] is True


def test_nothing_fires_without_the_engine():
    """No best move or no punishment line means no claim. The board cannot
    decide on its own that a move was bad."""
    assert _confirm_own_alignment(_gold(), chess.WHITE, "Rc1", None, GOLD_PV) is None
    assert _confirm_own_alignment(_gold(), chess.WHITE, "Rc1", "Ra1", []) is None
    assert _confirm_own_alignment(_gold(), chess.WHITE, "Rc1", "Ra1", None) is None


def test_silent_when_the_opponent_goes_somewhere_else():
    """The shape still exists; the opponent simply is not taking it. This is
    the condition that separates 6.1% from 52.3%."""
    assert _confirm_own_alignment(
        _gold(), chess.WHITE, "Rc1", "Ra1", ["h5", "Bf8", "Kf7"]) is None


def test_silent_when_the_move_played_already_fixed_it():
    """Ra1 guards a2, so after it there is nothing to warn about — and the
    opponent cannot play Ra2 anyway."""
    assert _confirm_own_alignment(
        _gold(), chess.WHITE, "Ra1", "Ra1", ["Rd2", "a5", "Bd7"]) is None


def test_a_check_is_not_a_skewer():
    """At the 107x gate this was still catching Re2+ and Qd2#, where the two
    aligned units are incidental to a check or a mate. Excluding the king on
    either end is what took it to 180x. Here the black rook enters on e2
    giving check to the king on f2, with a pawn on g2 behind it."""
    # Black rook on e8 can run to e2, checking the king on f2 with the pawn
    # on g2 directly behind it. (An earlier fixture put the rook on h2, where
    # it was blocked by the very pieces it was meant to skewer — a hand-built
    # position that could not happen.)
    board = chess.Board("4r1k1/8/8/8/8/8/5KP1/8 w - - 0 1")

    shapes = _own_alignment_exposure(board, chess.WHITE)
    # The geometry IS present — king on f2 in front, pawn on g2 behind ...
    assert any(s["front_piece_square"] == "f2" and s["rear_piece_square"] == "g2"
               for s in shapes), "expected the king/pawn pair to be visible as geometry"

    # ... and the gate must refuse it anyway, because a check is not a skewer.
    hit = _confirm_own_alignment(board, chess.WHITE, "Kf1", "Kf3", ["Re2"])
    assert hit is None


def test_the_existing_offensive_fact_is_untouched():
    """`aligned_pieces_evidence` is read by six other services
    (caption_rules, board_geometry_service, motif_profile_service,
    aligned_tactic_puzzle_proof, …). This feature adds a key; it must never
    widen that one."""
    from services.caption_facts import _aligned_pieces_evidence

    board = _gold()
    before = _aligned_pieces_evidence(board, chess.WHITE)
    _own_alignment_exposure(board, chess.WHITE)
    assert _aligned_pieces_evidence(board, chess.WHITE) == before


def test_the_fact_reaches_extract_facts():
    from services.caption_facts import extract_facts

    facts = extract_facts(
        fen_before=GOLD, played_san="Rc1", best_move_san="Ra1",
        eval_before_cp=292, eval_after_cp=8, cp_loss=284,
        pv_after_played=GOLD_PV, pv_after_best=["Rd2", "a5", "Bd7", "Bc5"],
        move_history_san=["e4"], full_move_number=30, mover_is_user=True,
    )
    assert "own_alignment_confirmed" in facts
    hit = facts["own_alignment_confirmed"]
    assert hit is not None, "the gold case must survive the real extractor"
    assert hit["front_piece_square"] == "a3"
    # and the offensive fact is still empty here, as measured
    assert facts.get("aligned_pieces_evidence") == []

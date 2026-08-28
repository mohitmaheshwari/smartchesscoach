"""Regression tests for causal Chess Brain hanging-piece truth."""

import inspect

import chess
import pytest

from services.caption_facts import legally_hanging_pieces
from services.chess_brain.detector_registry import (
    CAUSAL_MISTAKE_MIN_CP_LOSS,
    HANGING_PIECE_MIN_GAIN_CP,
    DetectorRegistry,
    detect_hanging_piece,
)


MOVED_HANG_FEN = "r1b1kbnr/pp3ppp/8/q1pPp3/2BnP3/2N1B3/PP3PPP/R2QK1NR w KQkq - 2 8"
OTHER_HANG_FEN = "rnbqk2r/1p2bppp/p2ppn2/2p1P3/2B5/P1NP1N2/1PP2PPP/R1BQK2R b KQkq - 0 7"
PREEXISTING_HANG_FEN = "3r3k/8/8/8/8/8/P6P/3Q3K w - - 0 1"
PAWN_ONLY_FEN = "7k/7b/8/8/8/8/3P4/7K w - - 0 1"
XRAY_RECAPTURE_FEN = "7k/8/8/8/8/2n5/1B6/b6K w - - 0 1"


def _detect(fen, played, best, cp_loss):
    return detect_hanging_piece(
        chess.Board(fen),
        played,
        best,
        {"cp_loss": cp_loss},
    )


def test_moved_piece_hang_is_detected_with_winning_reply():
    result = _detect(MOVED_HANG_FEN, "Bxd4", "f4", 470)

    assert result.detected
    assert result.details["subtype"] == "moved_piece"
    assert result.details["hanging_piece"] == "bishop"
    assert result.details["hanging_square"] == "d4"
    assert result.details["material_loss_cp"] == 300
    assert result.details["winning_reply"] == "exd4"


def test_other_piece_left_exposed_is_detected():
    result = _detect(OTHER_HANG_FEN, "O-O", "dxe5", 494)

    assert result.detected
    assert result.details["subtype"] == "other_piece"
    assert result.details["hanging_piece"] == "knight"
    assert result.details["hanging_square"] == "f6"
    assert result.details["material_loss_cp"] == 200
    assert result.details["winning_reply"] == "exf6"


def test_sound_defended_exchange_is_not_hanging():
    board = chess.Board("7k/8/8/2n5/4N3/5P2/8/7K b - - 0 1")

    assert legally_hanging_pieces(board, chess.WHITE, 1) == []


def test_xray_recapture_is_seen_after_the_capture_opens_the_line():
    board = chess.Board(XRAY_RECAPTURE_FEN)
    board.push_san("Bxc3")

    facts = legally_hanging_pieces(board, chess.WHITE, 150)

    assert len(facts) == 1
    assert facts[0]["piece_type"] == "bishop"
    assert facts[0]["square"] == "c3"
    assert facts[0]["winning_capture_san"] == "Bxc3"


def test_pawn_only_loss_is_below_the_coaching_floor():
    assert not _detect(PAWN_ONLY_FEN, "Kg1", "d4", 200).detected


def test_preexisting_hang_left_by_both_moves_is_not_attributed():
    assert not _detect(PREEXISTING_HANG_FEN, "a3", "h3", 200).detected


@pytest.mark.parametrize(
    "best, cp_loss",
    [
        ("f4", 99),
        ("f4", None),
        ("Bxd4", 470),
        ("", 470),
    ],
)
def test_detector_abstains_without_causal_engine_evidence(best, cp_loss):
    assert not _detect(MOVED_HANG_FEN, "Bxd4", best, cp_loss).detected


def test_registry_requires_best_move_and_uses_locked_floors():
    detector = DetectorRegistry().get_detector("hanging_piece_detector")

    assert detector is not None
    assert detector.requires_best_move
    assert CAUSAL_MISTAKE_MIN_CP_LOSS == 100
    assert HANGING_PIECE_MIN_GAIN_CP == 150


def test_chess_brain_is_only_an_adapter_to_canonical_exchange_truth():
    source = inspect.getsource(detect_hanging_piece)

    assert "legally_hanging_pieces" in source
    assert "is_attacked_by" not in source
    assert "is_defended" not in source


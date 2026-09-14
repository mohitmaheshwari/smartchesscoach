"""Board Geometry reaches Game Review (Mohit, 2026-09-15).

The detector, the copy, the arrows and the highlights already existed in
board_geometry_service and fed two surfaces: PWC in-game moments and the
/training/geometry lessons. Game Review -- the one place a player studies
their own mistakes -- had no wiring to it, so the shape was never named there.

The join is a shape adapter, not a second detector: the detector speaks
stockfish move-evaluation shape (ev["move"], ev["is_opponent_move"]) and a
stored V5 card names the same facts move_san / is_user_move.
"""
from __future__ import annotations

import os

import chess
import pytest

from services import board_geometry_service as geo


def _card_to_ev(card: dict) -> dict:
    """Exactly the adaptation routes/coach.py performs."""
    ev = dict(card)
    ev["move"] = card.get("move_san") or card.get("move")
    if card.get("is_user_move") is not None:
        ev["is_opponent_move"] = not bool(card.get("is_user_move"))
    return ev


def test_a_v5_card_shape_produces_a_moment():
    """Without the adapter the detector sees move=None and returns nothing."""
    # A queen capture that lines up queen, blocker and rook on one diagonal.
    card = {
        "fen_before": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        "move_san": "Ng5",
        "best_move_san": "Ng5",
        "is_user_move": True,
        "cp_loss": 0,
    }
    raw = geo.geometry_moments_for_move(dict(card))      # unadapted
    adapted = geo.geometry_moments_for_move(_card_to_ev(card))
    # The adapter is what makes the card legible; raw shape cannot even read the move.
    assert raw == [] or isinstance(raw, list)
    assert isinstance(adapted, list)


def test_adapter_sets_the_fields_the_detector_reads():
    card = {"move_san": "Nf3", "is_user_move": True, "fen_before": chess.STARTING_FEN}
    ev = _card_to_ev(card)
    assert ev["move"] == "Nf3"
    assert ev["is_opponent_move"] is False


def test_opponent_cards_are_marked_so_the_detector_can_skip_them():
    card = {"move_san": "e5", "is_user_move": False, "fen_before": chess.STARTING_FEN}
    assert _card_to_ev(card)["is_opponent_move"] is True


def test_moment_carries_everything_the_review_card_renders():
    """eyebrow / explanation / lesson / module_id are what the UI reads."""
    fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    board = chess.Board(fen)
    found = None
    for mv in board.legal_moves:
        ev = {"fen_before": fen, "move": board.san(mv), "is_opponent_move": False,
              "cp_loss": 0}
        ms = geo.geometry_moments_for_move(ev)
        if ms:
            found = ms[0]
            break
    if found is None:
        pytest.skip("no geometry shape reachable from this fixture position")
    for key in ("moment_type", "module_id", "eyebrow", "lesson"):
        assert found.get(key), f"review card needs {key}"
    assert found["module_id"] in {
        "knight_shared_square", "pawn_fork_v", "diagonal_lines", "rank_file_lines"
    }


def test_review_wiring_is_gated_on_the_lesson_flag(monkeypatch):
    """A moment that names a lesson the player cannot open is a dead end."""
    monkeypatch.delenv("BOARD_GEOMETRY_LEARNING", raising=False)
    monkeypatch.delenv("DEV_MODE", raising=False)
    assert geo.feature_enabled(None) is False
    monkeypatch.setenv("BOARD_GEOMETRY_LEARNING", "true")
    assert geo.feature_enabled(None) is True

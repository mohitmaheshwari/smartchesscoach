"""Opening names come from Lichess's own list, by position, with no network.

The explorer refuses anonymous requests (401, checked 2026-11-09), so the
coach commentary's opening names were silently empty.
"""
import chess

from services import lichess_openings_local as lo


def _fen(*sans):
    b = chess.Board()
    for s in sans:
        b.push_san(s)
    return b.fen()


def test_a_named_position_gets_its_lichess_name():
    name, eco = lo.name_for_fen(_fen("e4", "c5"))
    assert name == "Sicilian Defense" and eco == "B20"


def test_a_transposed_move_order_finds_the_same_name():
    a = lo.name_for_fen(_fen("Nf3", "d5", "d4"))
    b = lo.name_for_fen(_fen("d4", "d5", "Nf3"))
    assert a and a == b


def test_an_unnamed_position_returns_none():
    assert lo.name_for_fen("8/8/8/8/8/6k1/6P1/6K1 w - - 0 1") is None


def test_the_explorer_token_is_sent_only_when_set(monkeypatch):
    monkeypatch.delenv("LICHESS_API_TOKEN", raising=False)
    assert "Authorization" not in lo.explorer_headers()
    monkeypatch.setenv("LICHESS_API_TOKEN", "abc")
    assert lo.explorer_headers()["Authorization"] == "Bearer abc"

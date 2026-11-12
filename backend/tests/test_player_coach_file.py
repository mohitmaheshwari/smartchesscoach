"""The player file: opening habits, the personal sitting rule, and the payload.

docs/coach_pages_scope.md. Pure functions, no database.
"""
import re
from datetime import datetime, timedelta, timezone

import chess
import pytest

from services import player_coach_file as pcf

MODERN_BC4 = "rnbqk1nr/ppp1ppbp/3p2p1/8/2BPP3/5N2/PPP2PPP/RNBQK2R b KQkq - 1 4"
MODERN_NC3 = "rnbqk1nr/ppp1ppbp/3p2p1/8/3PP3/2N2N2/PPP2PPP/R1BQKB1R b KQkq - 2 4"
MODERN_C3 = "rnbqk1nr/ppp1ppbp/3p2p1/8/3PP3/2P2N2/PP3PPP/RNBQKB1R b KQkq - 0 4"


def _game(gid, rows):
    return {"game_id": gid, "rows": rows}


def _row(fen, move, cp, best="Nf6"):
    return {"fen_before": fen, "move": move, "cp_loss": cp, "is_opponent_move": False, "best_move": best}


def _bg4_games(costs, fens=(MODERN_BC4, MODERN_NC3, MODERN_C3)):
    games = []
    for i, cp in enumerate(costs):
        fen = fens[i % len(fens)]
        games.append(_game(f"g{i}", [_row("x w - - 0 1", "g6", 0), _row("x w - - 0 2", "Bg7", 0), _row(fen, "Bg4", cp)]))
    return games


def test_a_repeated_costly_idea_is_a_habit():
    habits = pcf.opening_habits(_bg4_games([238, 60, 50, 70]), "1800+")
    assert len(habits) == 1
    h = habits[0]
    assert h["idea"] == "Bg4" and h["side"] == "black" and h["line"] == "g6 Bg7"
    # The example is the costliest instance, and both moves are legal there.
    assert h["fen"] == MODERN_BC4 and h["better_san"] == "Nf6"
    board = chess.Board(h["fen"])
    board.parse_san(h["san"])
    board.parse_san(h["better_san"])
    assert (h["played_from"], h["played_to"]) == ("c8", "g4")
    assert h["measured"]["games"] == 4 and h["measured"]["positions"] == 3


def test_below_the_band_cut_is_not_shown():
    # Average 69 clears the 1800+ cut (64) and not the under-1000 cut (140).
    games = _bg4_games([238, 60, 50, 70])
    assert pcf.opening_habits(games, "1800+")
    assert not pcf.opening_habits(games, "<1000")


def test_two_games_are_not_a_habit_and_one_position_is_not_an_idea():
    assert not pcf.opening_habits(_bg4_games([300, 300]), "1800+")
    same_square = _bg4_games([300, 300, 300], fens=(MODERN_BC4,))
    assert not pcf.opening_habits(same_square, "1800+")


def test_castling_is_never_the_opening_habit():
    fen = "rnbqk2r/ppppppbp/5np1/8/2PP4/2N2N2/PP2PPPP/R1BQKB1R b KQkq - 0 4"
    fen2 = "rnbqk2r/ppppppbp/5np1/8/3P4/2N2N2/PPP1PPPP/R1BQKB1R b KQkq - 0 4"
    games = [_game(f"c{i}", [_row("x w - - 0 1", "Nf6", 0), _row("x w - - 0 2", "g6", 0),
                             _row(fen if i % 2 else fen2, "O-O", 400, best="d6")]) for i in range(4)]
    assert not pcf.opening_habits(games, "1800+")


def test_one_instance_per_game():
    rows = [_row("x w - - 0 1", "g6", 0), _row("x w - - 0 2", "Bg7", 0),
            _row(MODERN_BC4, "Bg4", 300), _row(MODERN_NC3, "Bg4", 300)]
    # Two Bg4 rows in one game plus one more game is two games, not three.
    games = [_game("a", rows), _game("b", [rows[0], rows[1], _row(MODERN_C3, "Bg4", 300)])]
    assert not pcf.opening_habits(games, "1800+")


def test_no_digit_reaches_the_player_in_opening_sentences():
    for h in pcf.opening_habits(_bg4_games([238, 60, 50, 70]), "1800+"):
        for text in (h["headline"], h["detail"]):
            assert not re.search(r"\d", text), text


def _sittings(pattern, start=datetime(2026, 11, 1, tzinfo=timezone.utc)):
    """pattern: list of sittings, each a list of scores (1, 0.5, 0)."""
    games, t = [], start
    for sitting in pattern:
        for s in sitting:
            result = "1-0" if s == 1 else "0-1" if s == 0 else "1/2-1/2"
            games.append({"played_at_utc": t, "result": result, "user_color": "white"})
            t += timedelta(minutes=12)
        t += timedelta(hours=5)
    return games


def test_a_clear_late_sitting_drop_is_proven():
    pattern = [[1, 1, 1, 1, 1, 1, 0, 0, 0, 0]] * 8
    finding = pcf.sitting_finding(_sittings(pattern), seed="u")
    assert finding["proven"] is True
    assert finding["measured"]["late_score"] == 0.0


def test_no_drop_is_never_said():
    pattern = [[1, 0, 1, 0, 1, 0, 1, 0, 1, 0]] * 8
    assert pcf.sitting_finding(_sittings(pattern), seed="u")["proven"] is False


def test_too_few_late_games_is_not_enough():
    pattern = [[1, 1, 1, 1, 1, 1, 0]] * 5
    finding = pcf.sitting_finding(_sittings(pattern), seed="u")
    assert finding["proven"] is False and "why_not" in finding["measured"]


def test_sitting_now_live_only_mid_sitting():
    proven = {"proven": True}
    now = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)
    six_in_a_row = [{"played_at_utc": now - timedelta(minutes=5 + 12 * i)} for i in range(6)]
    live = pcf.sitting_now(proven, six_in_a_row, now=now)
    assert live["show"] and live["live"]
    resting = pcf.sitting_now(proven, six_in_a_row, now=now + timedelta(hours=3))
    assert resting["show"] and not resting["live"]
    assert pcf.sitting_now({"proven": False}, six_in_a_row, now=now) == {"show": False}
    for text in (live["headline"], live["detail"], resting["headline"], resting["detail"]):
        assert not re.search(r"\d", text), text


def test_duplicate_imports_count_once():
    pgn = '[Site "https://lichess.org/abcd1234"]\n1. e4 *'
    chesscom = '[Site "Chess.com"]\n[Link "https://www.chess.com/game/live/1"]\n1. e4 *'
    chesscom2 = '[Site "Chess.com"]\n[Link "https://www.chess.com/game/live/2"]\n1. e4 *'
    games = [{"game_id": "a", "pgn": pgn}, {"game_id": "b", "pgn": pgn},
             {"game_id": "c", "pgn": chesscom}, {"game_id": "d", "pgn": chesscom2}]
    # Chess.com's constant Site must not merge different games.
    assert [g["game_id"] for g in pcf.dedupe_games(games)] == ["a", "c", "d"]


def test_flag(monkeypatch):
    monkeypatch.setenv(pcf.FLAG_ENV, "user_a, user_b")
    assert pcf.is_enabled_for("user_a") and not pcf.is_enabled_for("user_c")
    monkeypatch.setenv(pcf.FLAG_ENV, "*")
    assert pcf.is_enabled_for("anyone")
    monkeypatch.delenv(pcf.FLAG_ENV)
    assert not pcf.is_enabled_for("user_a")


def test_payload_without_a_file_is_building():
    assert pcf.payload(None, []) == {"enabled": True, "state": "building"}

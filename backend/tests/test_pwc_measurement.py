"""Play with Coach measurement (docs/coaching_intelligence_scope.md, 1b)."""
import chess

from coach_play.coach_opponent import opponent_strength_record
from routes.coach_play import apply_game_over_to_update
from scripts.pwc_strength_report import report


def test_the_strength_record_shows_the_floor_and_the_engine_path():
    beginner = opponent_strength_record(731, "coach")
    assert beginner["floor_applied"] and beginner["strength_rating"] == 1500
    assert beginner["engine_path"] == "teaching_selector"
    strong = opponent_strength_record(1900, "play")
    assert not strong["floor_applied"] and strong["engine_path"] == "weakened_engine"


def test_a_checkmate_records_how_it_ended_and_its_length():
    board = chess.Board()
    for san in ["f3", "e5", "g4", "Qh4#"]:
        board.push_san(san)
    update = apply_game_over_to_update(board, {"_user_is_mated": True})
    assert update["termination_reason"] == "checkmate" and update["result"] == "loss"
    assert update["plies_at_end"] == 4


def test_an_unfinished_board_gets_no_ending():
    assert apply_game_over_to_update(chess.Board(), {}) == {}


def test_the_report_leaves_out_staff_short_games_and_counts_players():
    sessions = [
        {"user_id": "u1", "result": "loss", "plies_at_end": 60, "game_mode": "coach"},
        {"user_id": "u1", "result": "win", "plies_at_end": 80, "game_mode": "coach"},
        {"user_id": "u2", "result": "loss", "plies_at_end": 12, "game_mode": "coach"},
        {"user_id": "boss", "result": "loss", "plies_at_end": 90, "game_mode": "coach"},
        {"user_id": "dev_user_local", "result": "loss", "plies_at_end": 90},
    ]
    out = report(sessions, {"boss": "super_admin"}, {"u1": 900, "u2": 1200})
    row = out["rows"]["<1000 / teaching_selector"]
    assert row["games"] == 2 and row["players"] == 1 and row["score"] == 0.5
    assert out["left_out"] == {"under 15 moves": 1, "staff or development account": 2}

"""The refresh after every analysed game: right answers, in bounded memory.

It used to start on game_analyses, join every row to games, then filter by
user, and it held the player's whole history in one list. That read 6.9 GB
three times per game and killed the 2 GB workers on large accounts.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

import mongomock
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import data_freshness as df  # noqa: E402


def _game(i, user="u1", result="1-0", color="white"):
    return {"game_id": f"g{i}", "user_id": user, "result": result, "user_color": color,
            "white_player": "me", "black_player": f"opp{i}"}


def _analysis(i, user="u1", analyzed_at=None, moves=None, **sf):
    return {"game_id": f"g{i}", "user_id": user,
            "analyzed_at": analyzed_at or f"2026-01-{(i % 28) + 1:02d}T00:00:{i % 60:02d}",
            "stockfish_analysis": {"accuracy": 80.0, "mistakes": 1, "blunders": 1, "inaccuracies": 0,
                                   "move_evaluations": moves if moves is not None else [], **sf},
            "decryption_v5_data": [], "enormous_unused_field": "x" * 100}


def _blunder(n=20, gap="piece_safety", fen="fen-a", **extra):
    return {"cp_loss": 300, "move_number": n, "cognitive_gap": gap, "move": "Qh5",
            "best_move": "Nf3", "fen_before": fen, **extra}


@pytest.fixture
def db():
    return mongomock.MongoClient().db


def test_only_this_players_games_are_counted(db):
    db.games.insert_many([_game(1), _game(2, result="0-1"), _game(3, user="other")])
    db.game_analyses.insert_many([_analysis(1), _analysis(2), _analysis(3, user="other")])
    out = df.refresh_player_identity(db, "u1")
    stored = db.player_identities.find_one({"user_id": "u1"})
    assert out["games_processed"] == 2
    assert (stored["total_wins"], stored["total_losses"]) == (1, 1)


def test_an_analysis_with_no_game_row_is_left_out(db):
    db.games.insert_one(_game(1))
    db.game_analyses.insert_many([_analysis(1), _analysis(9)])
    assert df.refresh_player_identity(db, "u1")["games_processed"] == 1


def test_a_player_with_no_analyses_is_reported_as_such(db):
    db.games.insert_one(_game(1))
    assert df.refresh_player_identity(db, "u1") == {"status": "no_games", "games_processed": 0}


def test_games_replay_oldest_first_across_string_and_date_times(db):
    """The current streak is whatever the last replayed game left behind."""
    db.games.insert_many([_game(1, result="0-1"), _game(2), _game(3, result="0-1")])
    db.game_analyses.insert_many([
        _analysis(1, analyzed_at=datetime(2026, 3, 1, tzinfo=timezone.utc)),
        _analysis(2, analyzed_at=datetime(2026, 5, 1)),
        _analysis(3, analyzed_at="2026-01-01T00:00:00"),
    ])
    df.refresh_player_identity(db, "u1")
    stored = db.player_identities.find_one({"user_id": "u1"})
    assert stored["consecutive_wins"] == 1  # the May win came last
    assert [p["result"] for p in stored["recent_performance"]] == ["loss", "loss", "win"]


def test_the_caption_still_reaches_the_pattern_history(db):
    db.games.insert_one(_game(1))
    doc = _analysis(1, moves=[_blunder(fen="fen-a")])
    doc["decryption_v5_data"] = [{"fen_before": "fen-a", "caption": "Your queen came out too early."}]
    db.game_analyses.insert_one(doc)
    df.refresh_player_identity(db, "u1")
    entry = db.player_identities.find_one({"user_id": "u1"})["pattern_history"][0]
    assert entry["description"] == "Your queen came out too early."
    assert entry["opponent"] == "opp1"


def test_pattern_history_keeps_the_last_hundred(db):
    db.games.insert_many([_game(i) for i in range(30)])
    db.game_analyses.insert_many([
        _analysis(i, analyzed_at=f"2026-01-01T00:{i:02d}:00",
                  moves=[_blunder(n=m) for m in range(1, 6)]) for i in range(30)])
    df.refresh_player_identity(db, "u1")
    history = db.player_identities.find_one({"user_id": "u1"})["pattern_history"]
    assert len(history) == 100
    assert history[-1]["game_id"] == "g29"
    assert history[0]["game_id"] == "g10"


def test_style_is_the_same_whether_tallied_or_computed_in_one_go(db):
    games = [_analysis(i, moves=[_blunder(gap="piece_safety"), _blunder(gap="pawn_structure"),
                                 _blunder(gap="piece_activity", is_opponent_move=True)],
                       brilliant_moves=1, sacrifices=1) for i in range(6)]
    db.games.insert_many([_game(i) for i in range(6)])
    db.game_analyses.insert_many([dict(g) for g in games])
    df.refresh_player_identity(db, "u1")
    style = db.player_identities.find_one({"user_id": "u1"})["style_profile"]
    want = df._compute_style_tendencies(games)
    assert {k: style[k] for k in want} == want
    assert want["tactical_tendency"] == 0.5


def test_never_reads_more_than_one_batch_of_analysis_bodies(db, monkeypatch):
    """The fault itself: a long history must not be held in memory at once."""
    total = df._ANALYSIS_BATCH * 3 + 7
    db.games.insert_many([_game(i) for i in range(total)])
    db.game_analyses.insert_many([_analysis(i) for i in range(total)])

    real_iter = df._iter_analyses
    largest = {"n": 0}

    def spy(database, rows, fields, batch=df._ANALYSIS_BATCH):
        largest["n"] = max(largest["n"], batch)
        return real_iter(database, rows, fields, batch)

    monkeypatch.setattr(df, "_iter_analyses", spy)
    out = df.refresh_player_identity(db, "u1")
    assert out["games_processed"] == total
    assert largest["n"] == df._ANALYSIS_BATCH


def test_identity_reads_only_the_fields_it_uses(db):
    db.games.insert_one(_game(1))
    db.game_analyses.insert_one(_analysis(1))
    rows = df._user_analysis_rows(db, "u1")
    doc = next(df._iter_analyses(db, rows, df._IDENTITY_FIELDS))
    assert "enormous_unused_field" not in doc


def test_profile_reads_the_twenty_newest(db):
    db.games.insert_many([_game(i) for i in range(25)])
    db.game_analyses.insert_many([
        {**_analysis(i, analyzed_at=f"2026-01-01T00:{i:02d}:00"),
         "stockfish_analysis": {"accuracy": 100.0 if i >= 5 else 0.0, "mistakes": 0, "blunders": 0,
                                "inaccuracies": 0, "move_evaluations": []}}
        for i in range(25)])
    out = df.refresh_player_profile(db, "u1")
    assert out["games_analyzed"] == 20
    assert out["avg_accuracy"] == 100.0


def test_only_missing_thinking_scores_are_calculated(db, monkeypatch):
    db.games.insert_many([_game(1), _game(2)])
    db.game_analyses.insert_many([_analysis(1), _analysis(2)])
    db.thinking_scores.insert_one({"user_id": "u1", "game_id": "g1"})
    import services.thinking_score as ts
    seen = []
    monkeypatch.setattr(ts, "calculate_game_thinking_scores",
                        lambda analysis, color: seen.append(analysis["game_id"]) or {"overall_score": 1})
    out = df.ensure_thinking_scores(db, "u1")
    assert seen == ["g2"]
    assert (out["total_games"], out["scores_calculated"], out["already_had_scores"]) == (2, 1, 1)


def test_the_whole_refresh_runs_and_shares_one_list_of_games(db, monkeypatch):
    db.games.insert_one(_game(1))
    db.game_analyses.insert_one(_analysis(1))
    db.thinking_scores.insert_one({"user_id": "u1", "game_id": "g1"})
    calls = []
    real = df._user_analysis_rows
    monkeypatch.setattr(df, "_user_analysis_rows", lambda *a: calls.append(1) or real(*a))
    out = df.refresh_all_user_data(db, "u1")
    assert out["success"] is True
    assert len(calls) == 1


class _Queue:
    def __init__(self):
        self.calls = []

    def update_one(self, selector, update):
        self.calls.append(selector)


class _Db:
    def __init__(self):
        self.analysis_queue = _Queue()


def test_a_running_job_keeps_beating_and_stops_when_it_ends():
    aw = pytest.importorskip("analysis_worker")
    db = _Db()
    aw.HEARTBEAT_INTERVAL = 0.02
    with aw.job_heartbeat(db, "g1"):
        time.sleep(0.15)
    beats = len(db.analysis_queue.calls)
    assert beats >= 3
    assert db.analysis_queue.calls[0]["worker_id"] == aw.WORKER_ID
    time.sleep(0.1)
    assert len(db.analysis_queue.calls) == beats


def test_a_wedged_job_stops_beating_so_it_can_be_taken_back():
    aw = pytest.importorskip("analysis_worker")
    db = _Db()
    aw.HEARTBEAT_INTERVAL = 0.01
    aw.JOB_HARD_LIMIT_MINUTES = 0.05 / 60
    with aw.job_heartbeat(db, "g1"):
        time.sleep(0.2)
        settled = len(db.analysis_queue.calls)
        time.sleep(0.1)
        assert len(db.analysis_queue.calls) == settled

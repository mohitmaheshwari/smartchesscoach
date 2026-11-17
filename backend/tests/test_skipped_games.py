"""Result records for skipped games (services/skipped_games.py).

2026-11-17: the import dropped bullet games outright, so the coach could not
see that a player's 2+1 games go badly on the clock. Records keep the clock,
result and ending, in their own collection.
"""
import asyncio

from journey_service import should_analyze_game
from services.skipped_games import COLLECTION, skipped_game_record, store_skipped_games

LICHESS_BULLET = {
    "id": "abcd1234", "rated": True, "speed": "bullet", "status": "outoftime", "winner": "white",
    "createdAt": 1758000000000, "clock": {"initial": 120, "increment": 1},
    "players": {"white": {"user": {"id": "opp"}, "rating": 830}, "black": {"user": {"id": "me"}, "rating": 816}},
    "moves": "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d4 exd4 cxd4 Bb4+ Bd2 Bxd2+ Nbxd2 d5 exd5 Nxd5 Qb3 Na5 Qa4+ c6",
}
CHESSCOM_BULLET = {
    "url": "https://www.chess.com/game/live/99887766", "time_class": "bullet", "time_control": "60",
    "rated": True, "end_time": 1758000000,
    "white": {"username": "Me", "rating": 700, "result": "timeout"},
    "black": {"username": "opp", "rating": 720, "result": "win"},
    "pgn": "1. e4 {[%clk 0:00:59]} 1... e5 2. Nf3 2... Nc6 3. Bb5 3... a6",
}
LICHESS_RAPID = {**LICHESS_BULLET, "id": "r1", "speed": "rapid", "clock": {"initial": 600, "increment": 0},
                 "moves": " ".join(["e4", "e5"] * 12)}


def test_a_lichess_bullet_loss_on_time_is_recorded_from_the_players_side():
    r = skipped_game_record(LICHESS_BULLET, "lichess", "Me", "u1")
    assert r["reason"] == "bullet" and r["color"] == "black" and r["result"] == "loss"
    assert r["ending"] == "time" and (r["base_seconds"], r["increment_seconds"]) == (120, 1)
    assert (r["user_rating"], r["opponent_rating"]) == (816, 830) and r["full_moves"] == 11
    assert r["platform_game_id"] == "abcd1234" and r["user_id"] == "u1"


def test_a_chesscom_bullet_game_reads_the_clock_result_and_ending():
    r = skipped_game_record(CHESSCOM_BULLET, "chess.com", "me", "u1")
    assert r["reason"] == "bullet" and r["color"] == "white" and r["result"] == "loss"
    assert r["ending"] == "time" and (r["base_seconds"], r["increment_seconds"]) == (60, 0)
    assert r["platform_game_id"] == "99887766" and r["full_moves"] == 3


def test_a_game_the_player_is_not_in_is_not_recorded():
    assert skipped_game_record(LICHESS_BULLET, "lichess", "someone_else", "u1") is None


class _Coll:
    def __init__(self):
        self.rows = {}

    async def update_one(self, flt, upd, upsert=False):
        self.rows[tuple(sorted(flt.items()))] = upd["$set"]


class _DB(dict):
    def __getitem__(self, k):
        return self.setdefault(k, _Coll()) if k not in self else dict.__getitem__(self, k)


def test_only_skipped_games_are_stored_and_a_rerun_does_not_duplicate():
    db = _DB()
    games = [LICHESS_BULLET, LICHESS_RAPID]
    n = asyncio.run(store_skipped_games(db, "u1", games, "lichess", "me", should_analyze_game))
    asyncio.run(store_skipped_games(db, "u1", games, "lichess", "me", should_analyze_game))
    assert n == 1 and len(db[COLLECTION].rows) == 1
    assert list(db[COLLECTION].rows.values())[0]["speed"] == "bullet"

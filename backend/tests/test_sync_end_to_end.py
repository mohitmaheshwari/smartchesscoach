"""sync_user_games end to end, on a fake database.

2026-11-17: the per-game import was moved into journey_service.import_one_game.
A leftover name in the sync loop's log line would have raised inside the loop's
try, so every imported game would have skipped analysis queueing, and none of
the existing import tests noticed. This one runs the whole sync.
"""
import asyncio

import journey_service as js

PGN = """[Event "Rated blitz game"]
[Site "https://lichess.org/blitz001"]
[UTCDate "2026.11.10"]
[UTCTime "10:00:00"]
[White "me"]
[Black "opp"]
[Result "1-0"]
[WhiteElo "1350"]
[BlackElo "1340"]
[TimeControl "300+3"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Bd2 Bxd2+ 8. Nbxd2 d5 9. exd5 Nxd5 10. Qb3 Na5 11. Qa4+ c6 12. Bxd5 Qxd5 1-0
"""
BLITZ = {"id": "blitz001", "rated": True, "speed": "blitz", "status": "resign", "winner": "white",
         "createdAt": 1762768800000, "lastMoveAt": 1762769400000, "clock": {"initial": 300, "increment": 3},
         "players": {"white": {"user": {"id": "me", "name": "me"}, "rating": 1350},
                     "black": {"user": {"id": "opp", "name": "opp"}, "rating": 1340}},
         "moves": " ".join(["e4"] * 24), "pgn": PGN}
BULLET = {**BLITZ, "id": "bullet01", "speed": "bullet", "status": "outoftime", "winner": "black",
          "clock": {"initial": 120, "increment": 1}, "pgn": PGN.replace("blitz001", "bullet01")}


class Coll:
    def __init__(self):
        self.docs = []

    async def find_one(self, q, *a, **k):
        for d in self.docs:
            clauses = q.get("$or", [q])
            if any(all(d.get(f) == v for f, v in c.items()) for c in clauses):
                return d
        return None

    async def insert_one(self, d):
        self.docs.append(dict(d))

    async def update_one(self, q, u, upsert=False):
        self.docs.append({**q, **u.get("$set", {})})


class DB:
    def __init__(self):
        self.c = {}

    def __getattr__(self, name):
        return self.c.setdefault(name, Coll())

    def __getitem__(self, name):
        return self.c.setdefault(name, Coll())


def test_a_synced_game_is_imported_and_queued_and_a_bullet_game_only_gets_a_record(monkeypatch):
    async def fake_lichess(username, since):
        return [BLITZ, BULLET]
    monkeypatch.setattr(js, "fetch_recent_lichess_games", fake_lichess)
    db = DB()
    user = {"user_id": "u1", "lichess_username": "me", "last_game_sync": "2026-11-01T00:00:00+00:00"}
    asyncio.run(js.sync_user_games(db, "u1", user))

    games = db.games.docs
    assert [g["platform_game_id"] for g in games] == ["blitz001"]
    assert games[0]["user_color"] == "white" and games[0]["result"] == "1-0"
    queued = db.analysis_queue.docs
    assert [q["game_id"] for q in queued] == [games[0]["game_id"]] and queued[0]["status"] == "pending"
    records = db["skipped_game_records"].docs
    assert len(records) == 1 and records[0]["reason"] == "bullet" and records[0]["ending"] == "time"

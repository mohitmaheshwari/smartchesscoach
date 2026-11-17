"""Similar moments (services/similar_moments.py), on Mohit's move-22 position.

FEN: he played Be7 and the queen on c7 took it. docs/similar_moments_scope.md.
"""
from services import similar_moments as sm

FEN = "5r1k/2q3pp/pb4b1/1pn1pp2/7B/1BP2P2/PP2Q1PP/3R1R1K w - - 0 22"


class Coll:
    def __init__(self):
        self.rows = {}

    def update_one(self, q, u, upsert=False):
        key = q.get("_id") or tuple(sorted(q.items()))
        self.rows[key] = {**self.rows.get(key, {}), **u.get("$set", {}), "_id": key}

    def find(self, *a, **k):
        return list(self.rows.values())

    def find_one(self, q, sort=None):
        def ok(r):
            for f, v in q.items():
                val = r.get(f)
                if isinstance(v, dict):
                    if "$ne" in v and val == v["$ne"]: return False
                    if "$gte" in v and (val is None or val < v["$gte"]): return False
                elif val != v:
                    return False
            return True
        hits = [r for r in self.rows.values() if ok(r)]
        if sort:
            f, d = sort[0]
            hits.sort(key=lambda r: r.get(f) or 0, reverse=d < 0)
        return hits[0] if hits else None


class DB:
    def __init__(self, children=()):
        self.c = {"academy_students": Coll(), sm.COLLECTION: Coll(), "games": Coll()}
        for i, ch in enumerate(children):
            self.c["academy_students"].rows[i] = {"child_user_id": ch}

    def __getattr__(self, n):
        return self.c.setdefault(n, Coll())

    def __getitem__(self, n):
        return self.c.setdefault(n, Coll())


def test_the_signature_names_the_kind_of_landing_mistake():
    s = sm.landing_signature(FEN, "h4e7")
    assert (s["piece"], s["kind"], s["capture"], s["check"]) == ("bishop", "far_line", False, False)
    assert s["taker"] == {"piece": "queen", "sq": "c7"}
    assert sm.landing_signature(FEN, "b3c2") is None


def test_candidates_list_every_dangerous_landing_but_not_the_played_move():
    ucis = {c["uci"] for c in sm.landing_candidates(FEN, exclude_uci="b3c2")}
    assert {"h4e7", "h4f6"} <= ucis and "b3c2" not in ucis


def _game(uid="strong", platform="lichess", rating=1600):
    return {"user_id": uid, "game_id": "g1", "platform": platform, "user_rating": rating}


def _obs(played="b3c2", cp_loss=0):
    return [{"fen_before": FEN, "move_uci": played, "cp_loss": cp_loss, "phase": "middlegame", "move_number": 22}]


def test_a_stronger_players_sound_move_beside_a_tempting_danger_is_stored_and_found():
    db = DB()
    n = sm.tag_game_moments_sync(db, _game(), _obs(), maia=lambda fen, r: {"h4e7": 0.12, "h4f6": 0.01})
    assert n == 1
    found = sm.find_similar_sync(db, user_id="weak", fen=FEN, played_uci="h4e7", rating=1325, phase="middlegame")
    assert found["words"] == "Their bishop could go to e7, where the queen on c7 could win it along a long straight line. They played Bc2 instead."
    assert found["dangerous_uci"] == "h4e7" and found["played_uci"] == "b3c2" and found["taker_uci"] == "c7e7"


def test_the_pool_keeps_out_coach_games_children_unsound_moves_and_weak_temptations():
    tempt = lambda fen, r: {"h4e7": 0.12}
    assert sm.tag_game_moments_sync(DB(), _game(platform="coach"), _obs(), maia=tempt) == 0
    assert sm.tag_game_moments_sync(DB(children=["strong"]), _game(), _obs(), maia=tempt) == 0
    assert sm.tag_game_moments_sync(DB(), _game(), _obs(cp_loss=200), maia=tempt) == 0
    assert sm.tag_game_moments_sync(DB(), _game(), _obs(), maia=lambda f, r: {"h4e7": 0.001}) == 0


def test_no_match_from_a_player_who_is_not_stronger_or_from_yourself():
    db = DB()
    sm.tag_game_moments_sync(db, _game(rating=1400), _obs(), maia=lambda f, r: {"h4e7": 0.12})
    assert sm.find_similar_sync(db, user_id="weak", fen=FEN, played_uci="h4e7", rating=1325, phase="middlegame") is None
    db2 = DB()
    sm.tag_game_moments_sync(db2, _game(uid="me", rating=1700), _obs(), maia=lambda f, r: {"h4e7": 0.12})
    assert sm.find_similar_sync(db2, user_id="me", fen=FEN, played_uci="h4e7", rating=1325, phase="middlegame") is None


def test_the_coach_thinking_walks_the_three_looks_from_the_players_square():
    t = sm.thinking_words(FEN, "h4e7")
    assert t["lead"] == "Before your bishop lands on e7, look from e7:"
    assert [line["found"] for line in t["looks"]] == ["nothing", "nothing", "the queen on c7"]
    assert t["end"].startswith("One of them can take it")

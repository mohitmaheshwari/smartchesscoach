"""Academy routes: who can see a child, and what the three family links do.

docs/academy_pilot_scope.md. An in-memory stand-in for Mongo; the engine
opponent is replaced so no Stockfish runs.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from routes import academy as routes  # noqa: E402
from services import academy_service as svc  # noqa: E402


# ---------------------------------------------------------------------------
# a small Mongo
# ---------------------------------------------------------------------------
def _get(doc, key):
    for part in key.split("."):
        if not isinstance(doc, dict):
            return None
        doc = doc.get(part)
    return doc


def _matches(doc, query):
    for key, cond in (query or {}).items():
        value = _get(doc, key)
        if isinstance(cond, dict) and any(k.startswith("$") for k in cond):
            for op, arg in cond.items():
                if op == "$in" and value not in arg:
                    return False
                if op == "$ne" and value == arg:
                    return False
                if op == "$gte" and not (value is not None and value >= arg):
                    return False
                if op == "$lt" and not (value is not None and value < arg):
                    return False
        elif value != cond:
            return False
    return True


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, key, direction=1):
        self.rows.sort(key=lambda r: (_get(r, key) is None, _get(r, key)), reverse=direction < 0)
        return self

    async def to_list(self, length=None):
        return [dict(r) for r in self.rows]

    def __aiter__(self):
        self._it = iter(list(self.rows))
        return self

    async def __anext__(self):
        try:
            return dict(next(self._it))
        except StopIteration:
            raise StopAsyncIteration


class _Coll:
    def __init__(self):
        self.rows = []

    def find(self, query=None, projection=None):
        return _Cursor([r for r in self.rows if _matches(r, query)])

    async def find_one(self, query=None, projection=None, sort=None):
        rows = [r for r in self.rows if _matches(r, query)]
        if sort:
            key, direction = sort[0]
            rows.sort(key=lambda r: (_get(r, key) is None, _get(r, key)), reverse=direction < 0)
        return dict(rows[0]) if rows else None

    async def insert_one(self, doc):
        self.rows.append(dict(doc))

    async def update_one(self, query, update, upsert=False):
        hits = [r for r in self.rows if _matches(r, query)]
        if not hits and upsert:
            row = {k: v for k, v in query.items() if not isinstance(v, dict)}
            row.update(update.get("$setOnInsert") or {})
            self.rows.append(row)
            hits = [row]
        elif hits:
            pass
        for row in hits[:1]:
            for key, value in (update.get("$set") or {}).items():
                target = row
                parts = key.split(".")
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = value
            for key in (update.get("$unset") or {}):
                row.pop(key, None)
            for key, value in (update.get("$inc") or {}).items():
                row[key] = row.get(key, 0) + value
            for key, value in (update.get("$min") or {}).items():
                row[key] = min(row[key], value) if key in row else value

    async def delete_many(self, query):
        self.rows = [r for r in self.rows if not _matches(r, query)]

    async def count_documents(self, query):
        return len([r for r in self.rows if _matches(r, query)])

    async def create_index(self, *a, **k):
        return None


class _DB:
    def __init__(self):
        self._c = {}

    def __getitem__(self, name):
        return self._c.setdefault(name, _Coll())

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]


class _User:
    def __init__(self, uid, role="user", email=None):
        self.user_id, self.role, self.name = uid, role, uid.title()
        self.email = email or f"{uid}@example.com"


OWNER, COACH, STRANGER, ADMIN = _User("owner"), _User("coach"), _User("stranger"), _User("boss", "admin")


class _Req:
    headers = {"user-agent": "test"}


@pytest.fixture
def db(monkeypatch):
    database = _DB()
    routes.set_db(database)
    monkeypatch.setattr(routes, "_first_sync", lambda uid: asyncio.sleep(0))
    yield database
    routes.set_db(None)


def run(coro):
    return asyncio.run(coro)


def _setup(db):
    academy = run(routes.create_academy({"name": "Sunrise Chess", "city": "Pune"}, user=OWNER))
    db.users.rows.append({"user_id": "coach", "email": "coach@example.com", "name": "Coach Priya"})
    run(routes.add_coach(academy["academy_id"], {"email": "Coach@Example.com"}, user=OWNER))
    batch = run(routes.create_batch(academy["academy_id"], {"name": "Saturday batch",
                                                            "coach_name": "Coach Priya"}, user=COACH))
    added = run(routes.add_student(batch["batch_id"], {
        "display_name": "Rohan", "lichess_username": "rohan_plays", "parent_name": "Meena",
        "parent_phone": "98765 43210"}, user=COACH))
    student = db[svc.STUDENTS].rows[0]
    return academy, batch, added, student


# ---------------------------------------------------------------------------
# consent
# ---------------------------------------------------------------------------
def test_nothing_is_imported_before_the_parent_agrees(db):
    _, _, added, student = _setup(db)
    child = next(u for u in db.users.rows if u["user_id"] == student["child_user_id"])
    assert "lichess_username" not in child and "email" not in child
    assert added["whatsapp"].startswith("https://wa.me/919876543210?text=")
    assert student["consent"]["status"] == "pending"


def test_consent_needs_a_ticked_box_a_name_and_a_parent(db):
    _, _, _, student = _setup(db)
    token = student["consent_token"]
    for payload in ({"agree": False, "parent_name": "Meena", "is_parent": True},
                    {"agree": True, "parent_name": "", "is_parent": True},
                    {"agree": True, "parent_name": "Meena", "is_parent": False}):
        with pytest.raises(HTTPException) as e:
            run(routes.give_consent(token, _Req(), payload))
        assert e.value.status_code == 400


def test_agreeing_starts_the_import(db):
    _, _, _, student = _setup(db)
    page = run(routes.consent_page(student["consent_token"]))
    assert page["child_name"] == "Rohan" and page["accounts"] == ["Lichess: rohan_plays"]
    run(routes.give_consent(student["consent_token"], _Req(),
                            {"agree": True, "parent_name": "Meena", "is_parent": True}))
    child = next(u for u in db.users.rows if u["user_id"] == student["child_user_id"])
    assert child["lichess_username"] == "rohan_plays"
    assert db[svc.STUDENTS].rows[0]["consent"]["given_by_name"] == "Meena"


def test_stop_and_delete_removes_the_child_games(db):
    _, _, _, student = _setup(db)
    run(routes.give_consent(student["consent_token"], _Req(),
                            {"agree": True, "parent_name": "Meena", "is_parent": True}))
    uid = student["child_user_id"]
    db.games.rows.append({"user_id": uid, "game_id": "g1"})
    db.game_analyses.rows.append({"game_id": "g1"})
    db.move_observations.rows.append({"user_id": uid, "game_id": "g1"})
    db.games.rows.append({"user_id": "someone_else", "game_id": "g2"})
    run(routes.withdraw_consent(student["consent_token"]))
    assert [g["game_id"] for g in db.games.rows] == ["g2"]
    assert db.game_analyses.rows == [] and db.move_observations.rows == []
    child = next(u for u in db.users.rows if u["user_id"] == uid)
    assert "lichess_username" not in child
    assert run(routes.report_page(student["report_token"])) == {"status": "deleted"}
    assert db[svc.STUDENTS].rows[0]["parent_phone"] is None


# ---------------------------------------------------------------------------
# access
# ---------------------------------------------------------------------------
def test_another_academy_cannot_see_the_child(db):
    _, batch, _, student = _setup(db)
    for call in (lambda: routes.batch_view(batch["batch_id"], user=STRANGER),
                 lambda: routes.student_view(student["student_id"], user=STRANGER),
                 lambda: routes.approve_report(student["student_id"], {}, user=STRANGER)):
        with pytest.raises(HTTPException) as e:
            run(call())
        assert e.value.status_code == 403


def test_only_the_owner_adds_coaches(db):
    academy, _, _, _ = _setup(db)
    db.users.rows.append({"user_id": "c2", "email": "c2@example.com"})
    with pytest.raises(HTTPException) as e:
        run(routes.add_coach(academy["academy_id"], {"email": "c2@example.com"}, user=COACH))
    assert e.value.status_code == 403


def test_an_admin_can_open_any_academy(db):
    _, batch, _, _ = _setup(db)
    assert run(routes.batch_view(batch["batch_id"], user=ADMIN))["rows"][0]["name"] == "Rohan"


@pytest.mark.parametrize("token", ["", "short", "x" * 24])
def test_a_wrong_link_opens_nothing(db, token):
    _setup(db)
    with pytest.raises(HTTPException) as e:
        run(routes.report_page(token))
    assert e.value.status_code == 404


def test_each_token_opens_only_its_own_page(db):
    _, _, _, student = _setup(db)
    with pytest.raises(HTTPException):
        run(routes.report_page(student["consent_token"]))
    with pytest.raises(HTTPException):
        run(routes.consent_page(student["report_token"]))


# ---------------------------------------------------------------------------
# the week, the report, the class
# ---------------------------------------------------------------------------
KNIGHT_HANG = "2n3k1/5r1p/4ppN1/3p4/3r2P1/pP6/P4PP1/1K5R w - - 0 31"
QUEEN_HANG = "r1bq1rk1/pp3p1p/2nb4/3p2p1/5N2/1B4Q1/PPP2PPP/R1B2RK1 w - - 0 15"


def _played_this_week(days_ago):
    begin, _ = svc.week_bounds_utc(svc.week_start())
    return begin + timedelta(hours=1 + days_ago)


def _consented_with_games(db):
    academy, batch, added, student = _setup(db)
    run(routes.give_consent(student["consent_token"], _Req(),
                            {"agree": True, "parent_name": "Meena", "is_parent": True}))
    uid = student["child_user_id"]
    for gid, fen, uci in (("g1", KNIGHT_HANG, "g6f4"), ("g2", QUEEN_HANG, "g3g4")):
        db.games.rows.append({"user_id": uid, "game_id": gid, "result": "0-1", "user_color": "white",
                              "played_at_utc": _played_this_week(0), "opponent_rating": 1100})
        db.move_observations.rows.append({"user_id": uid, "game_id": gid, "ply": 20, "fen_before": fen,
                                          "move_uci": uci, "color": "white", "execution_quality": "blunder",
                                          "eval_before": 450, "eval_after": -300})
    db.game_analyses.rows.append({"game_id": "g1", "stockfish_analysis": {"move_evaluations": [
        {"fen_before": KNIGHT_HANG, "best_move_uci": "g6h4"}]}})
    return academy, batch, db[svc.STUDENTS].rows[0]


def test_a_week_is_built_and_the_class_view_reads_it(db):
    _, batch, student = _consented_with_games(db)
    run(routes.refresh_student(student["student_id"], user=COACH))
    view = run(routes.batch_view(batch["batch_id"], user=COACH))
    row = view["rows"][0]
    assert row["habit"] == "Moves a piece where it can be taken"
    assert row["homework"] == "not_started" and row["needs_you"] == "Homework not started"
    assert view["summary"] == "One child needs you this week."
    week = db[svc.WEEKS].rows[0]
    assert week["better_moves"] == {"g1:20": "g6h4"}


def test_a_refresh_before_consent_is_refused(db):
    _, _, _, student = _setup(db)
    with pytest.raises(HTTPException) as e:
        run(routes.refresh_student(student["student_id"], user=COACH))
    assert e.value.status_code == 409


def test_the_parent_sees_only_what_the_coach_approved(db):
    _, _, student = _consented_with_games(db)
    assert run(routes.report_page(student["report_token"]))["status"] == "none"
    with pytest.raises(HTTPException):
        run(routes.approve_report(student["student_id"], {}, user=COACH))  # week not built yet
    run(routes.refresh_student(student["student_id"], user=COACH))
    out = run(routes.approve_report(student["student_id"], {"coach_note": "Slow down a little."},
                                    user=COACH))
    assert out["whatsapp"].startswith("https://wa.me/919876543210?text=")
    page = run(routes.report_page(student["report_token"]))
    assert page["status"] == "ready"
    kinds = [s["kind"] for s in page["report"]["sections"]]
    assert kinds == ["week", "habit", "homework", "question", "note"]
    assert page["report"]["sections"][-1]["lines"] == ["Slow down a little."]
    assert db[svc.REPORTS].rows[0]["opens"] == 1


# ---------------------------------------------------------------------------
# homework
# ---------------------------------------------------------------------------
class _FakeOpponent:
    def __init__(self, replies):
        self.replies = replies

    async def get_move(self, fen, history=()):
        import chess
        board = chess.Board(fen)
        return board.san(next(iter(board.legal_moves)))

    async def get_evaluation(self, fen):
        return (3.5, None)


def test_homework_plays_against_the_engine_and_is_judged(db, monkeypatch):
    _, _, student = _consented_with_games(db)
    run(routes.refresh_student(student["student_id"], user=COACH))
    page = run(routes.homework_page(student["homework_token"]))
    assert page["status"] == "ready" and page["color"] == "white"
    opponent = _FakeOpponent([])
    monkeypatch.setattr(routes, "homework_opponent", lambda rating: opponent)
    attempt = run(routes.homework_start(student["homework_token"]))
    with pytest.raises(HTTPException) as e:
        run(routes.homework_move(student["homework_token"], {"attempt_id": attempt["attempt_id"], "uci": "a1a8"}))
    assert e.value.status_code == 400
    fen = page["fen"]
    import chess
    legal = next(iter(chess.Board(fen).legal_moves)).uci()
    moved = run(routes.homework_move(student["homework_token"], {"attempt_id": attempt["attempt_id"], "uci": legal}))
    assert moved["status"] == "playing"
    stopped = run(routes.homework_stop(student["homework_token"], {"attempt_id": attempt["attempt_id"]}))
    assert stopped["status"] == "kept"
    view = run(routes.batch_view(db[svc.STUDENTS].rows[0]["batch_id"], user=COACH))
    assert view["rows"][0]["homework_words"] == "Won it back"


def test_the_homework_opponent_plays_at_the_real_rating():
    """Play with Coach floors the engine at its coaching minimum; homework must not."""
    from coach_play.coach_opponent import COACH_MIN_RATING, rating_to_skill_level
    opponent = routes.homework_opponent(900)
    assert opponent.skill_level == rating_to_skill_level(900)
    assert rating_to_skill_level(900) < rating_to_skill_level(COACH_MIN_RATING)


# ---------------------------------------------------------------------------
# a child's games are read even though the child never opens the app
# ---------------------------------------------------------------------------
def test_consent_starts_the_import_at_the_start_of_last_week(db):
    _, _, _, student = _setup(db)
    run(routes.give_consent(student["consent_token"], _Req(),
                            {"agree": True, "parent_name": "Meena", "is_parent": True}))
    child = next(u for u in db.users.rows if u["user_id"] == student["child_user_id"])
    start = datetime.fromisoformat(child["last_game_sync"])
    begin, _ = svc.week_bounds_utc(svc.week_start() - timedelta(days=7))
    assert start.replace(tzinfo=None) == begin


def test_unread_games_are_queued_below_every_ordinary_job(db):
    uid = "user_kid"
    recent = datetime.utcnow() - timedelta(days=2)
    db.games.rows += [
        {"user_id": uid, "game_id": "rapid", "pgn": "1. e4", "played_at_utc": recent, "time_control_category": "rapid"},
        {"user_id": uid, "game_id": "bullet", "pgn": "1. e4", "played_at_utc": recent, "time_control_category": "bullet"},
        {"user_id": uid, "game_id": "done", "pgn": "1. e4", "played_at_utc": recent, "is_analyzed": True},
        {"user_id": uid, "game_id": "old", "pgn": "1. e4", "played_at_utc": recent - timedelta(days=30)},
    ]
    db.analysis_queue.rows.append({"game_id": "rapid", "user_id": uid, "status": "failed", "priority": 7})
    db.games.rows.append({"user_id": uid, "game_id": "blitz", "pgn": "1. d4", "played_at_utc": recent,
                          "time_control_category": "blitz"})
    assert run(routes.queue_unanalysed(uid)) == 2
    by_id = {r["game_id"]: r for r in db.analysis_queue.rows}
    assert set(by_id) == {"rapid", "blitz"}
    assert by_id["blitz"]["priority"] == routes.ACADEMY_QUEUE_PRIORITY < 5
    assert by_id["rapid"]["status"] == "failed"  # an existing job is never rewritten


# ---------------------------------------------------------------------------
# class games
# ---------------------------------------------------------------------------
def _two_children(db):
    academy, batch, _, rohan = _setup(db)
    run(routes.add_student(batch["batch_id"], {"display_name": "Ananya", "parent_phone": "9876500000",
                                               "lichess_username": "ananya_x"}, user=COACH))
    ananya = db[svc.STUDENTS].rows[1]
    for s in (rohan, ananya):
        run(routes.give_consent(s["consent_token"], _Req(),
                                {"agree": True, "parent_name": "Parent", "is_parent": True}))
    return batch, db[svc.STUDENTS].rows[0], db[svc.STUDENTS].rows[1]


def test_a_class_game_needs_two_consented_children_of_the_batch(db):
    academy, batch, _, rohan = _setup(db)
    run(routes.add_student(batch["batch_id"], {"display_name": "Ananya", "parent_phone": "9876500000"},
                           user=COACH))
    ananya = db[svc.STUDENTS].rows[1]
    with pytest.raises(HTTPException) as e:
        run(routes.create_class_game(batch["batch_id"], {"white_student_id": rohan["student_id"],
                                                         "black_student_id": rohan["student_id"]}, user=COACH))
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        run(routes.create_class_game(batch["batch_id"], {"white_student_id": rohan["student_id"],
                                                         "black_student_id": ananya["student_id"]}, user=COACH))
    assert e.value.status_code == 409
    with pytest.raises(HTTPException) as e:
        run(routes.create_class_game(batch["batch_id"], {"white_student_id": rohan["student_id"],
                                                         "black_student_id": ananya["student_id"]}, user=STRANGER))
    assert e.value.status_code == 403


def test_a_class_game_is_played_to_mate_and_reaches_both_children(db):
    batch, rohan, ananya = _two_children(db)
    out = run(routes.create_class_game(batch["batch_id"], {"white_student_id": rohan["student_id"],
                                                           "black_student_id": ananya["student_id"]}, user=COACH))
    w = out["links"]["white"].rsplit("/", 1)[1]
    b = out["links"]["black"].rsplit("/", 1)[1]
    assert run(routes.class_game_page(b))["my_color"] == "black"
    with pytest.raises(HTTPException) as e:
        run(routes.class_game_move(b, {"uci": "e7e5"}))
    assert e.value.status_code == 409  # not black's turn
    for token, uci in ((w, "f2f3"), (b, "e7e5"), (w, "g2g4")):
        run(routes.class_game_move(token, {"uci": uci}))
    with pytest.raises(HTTPException) as e:
        run(routes.class_game_move(b, {"uci": "d8h4", "ply": 2}))
    assert e.value.status_code == 409  # stale board
    end = run(routes.class_game_move(b, {"uci": "d8h4", "ply": 3}))
    assert end["status"] == "black_won" and end["result_words"] == "Checkmate. You won."
    assert run(routes.class_game_page(w))["result_words"] == "Checkmate. You lost this one."
    stored = {g["user_id"]: g for g in db.games.rows if g.get("platform") == "chessguru"}
    assert set(stored) == {rohan["child_user_id"], ananya["child_user_id"]}
    assert stored[rohan["child_user_id"]]["user_color"] == "white"
    assert stored[rohan["child_user_id"]]["result"] == "0-1"
    assert "1. f3 e5 2. g4 Qh4# 0-1" in stored[rohan["child_user_id"]]["pgn"]
    queued = [q for q in db.analysis_queue.rows if q.get("source") == "academy_class_game"]
    assert len(queued) == 2
    with pytest.raises(HTTPException):
        run(routes.class_game_move(w, {"uci": "a2a3"}))


def test_resigning_ends_the_game_and_removing_a_child_removes_their_games(db):
    batch, rohan, ananya = _two_children(db)
    out = run(routes.create_class_game(batch["batch_id"], {"white_student_id": rohan["student_id"],
                                                           "black_student_id": ananya["student_id"]}, user=COACH))
    w = out["links"]["white"].rsplit("/", 1)[1]
    b = out["links"]["black"].rsplit("/", 1)[1]
    run(routes.class_game_move(w, {"uci": "e2e4"}))
    run(routes.class_game_move(b, {"uci": "e7e5"}))
    end = run(routes.class_game_resign(w))
    assert end["status"] == "black_won" and end["result_words"] == "You resigned."
    listed = run(routes.list_class_games(batch["batch_id"], user=COACH))["games"]
    assert listed[0]["status_words"] == "Black won"
    run(routes.remove_student(rohan["student_id"], user=COACH))
    assert db[svc.CLASS_GAMES].rows == []
    assert [g["user_id"] for g in db.games.rows if g.get("platform") == "chessguru"] == [ananya["child_user_id"]]


# ---------------------------------------------------------------------------
# the coach confirms a good moment; a parent without an academy
# ---------------------------------------------------------------------------
SAVE = "6k1/8/8/8/4p3/5N2/8/6K1 w - - 0 1"


def test_a_confirmed_good_moment_is_said_in_the_coach_name_and_survives_a_rebuild(db):
    _, _, student = _consented_with_games(db)
    uid = student["child_user_id"]
    db.games.rows.append({"user_id": uid, "game_id": "g3", "result": "1-0", "user_color": "white",
                          "played_at_utc": _played_this_week(0), "opponent_rating": 1100})
    db.move_observations.rows.append({"user_id": uid, "game_id": "g3", "ply": 9, "fen_before": SAVE,
                                      "move_uci": "f3d4", "color": "white", "execution_quality": "best"})
    with pytest.raises(HTTPException):
        run(routes.confirm_good_moment(student["student_id"], {}, user=COACH))  # week not built
    run(routes.refresh_student(student["student_id"], user=COACH))
    out = run(routes.confirm_good_moment(student["student_id"], {}, user=COACH))
    assert out["confirmed_by_name"] == "Coach Priya"
    run(routes.refresh_student(student["student_id"], user=COACH))
    view = run(routes.student_view(student["student_id"], user=COACH))
    good = next(s for s in view["preview"]["sections"] if s["kind"] == "good")
    assert good["confirmed"] is True
    assert "Coach Priya checked this move. It shows Rohan understands the idea." in good["lines"]
    assert db["academy_coach_evidence"].rows[0]["move_uci"] == "f3d4"
    with pytest.raises(HTTPException):
        run(routes.confirm_good_moment(student["student_id"], {}, user=STRANGER))


def test_a_parent_sets_up_a_family_with_a_home_batch(db):
    parent = _User("parent")
    out = run(routes.create_academy({"kind": "family"}, user=parent))
    assert out["kind"] == "family" and out["name"] == "Parent's family"
    view = run(routes.batch_view(out["batch_id"], user=parent))
    assert view["batch"]["name"] == "Home" and view["academy"]["kind"] == "family"

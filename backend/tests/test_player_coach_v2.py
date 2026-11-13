"""The player file, schema 2: opening choices only, verified traps, the last
game's deciding move and its repeat, the habit, progress, play positions,
and who may read it. docs/coach_pages_scope.md. Pure functions, no database.
"""
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import chess
import pytest

from services import player_coach_file as pcf
from services import player_coach_habit as pch

MODERN_BC4 = "rnbqk1nr/ppp1ppbp/3p2p1/8/2BPP3/5N2/PPP2PPP/RNBQK2R b KQkq - 1 4"
MODERN_NC3 = "rnbqk1nr/ppp1ppbp/3p2p1/8/3PP3/2N2N2/PPP2PPP/R1BQKB1R b KQkq - 2 4"
MODERN_C3 = "rnbqk1nr/ppp1ppbp/3p2p1/8/3PP3/2P2N2/PP3PPP/RNBQKB1R b KQkq - 0 4"


def _row(fen, move, cp, best="Nf6"):
    return {"fen_before": fen, "move": move, "cp_loss": cp, "is_opponent_move": False, "best_move": best}


def _rows(fen, move, cp, best="Nf6"):
    return [_row("x w - - 0 1", "g6", 0), _row("x w - - 0 2", "Bg7", 0), _row(fen, move, cp, best)]


# --------------------------------------------------------------------------
# opening choices only
# --------------------------------------------------------------------------
def test_instance_kind_separates_shots_slips_and_choices():
    # A better move that captures is a missed shot, not opening knowledge.
    fen = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    assert pcf.instance_kind(fen, "Nf3", "exd5") == "shot"
    # Bc4 walks into ...dxc4: the bishop is left hanging on its new square.
    assert pcf.instance_kind(fen, "Bc4", "Nc3") == "safety"
    # A quiet move for a quiet better move is a choice.
    assert pcf.instance_kind(MODERN_BC4, "Bg4", "Nf6") == "choice"
    assert pcf.instance_kind(MODERN_BC4, "Zz9", "Nf6") is None


def test_a_habit_made_of_missed_shots_is_not_an_opening_habit():
    fen_a = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    fen_b = "rnbqkbnr/ppp1pppp/8/3p4/4P3/2N5/PPPP1PPP/R1BQKBNR w KQkq - 0 2"
    games = [{"game_id": f"g{i}", "rows": [_row("x w - - 0 1", "e4", 0), _row("x w - - 0 2", "Nc3", 0),
                                          _row(fen_a if i % 2 else fen_b, "Nf3", 300, best="exd5")]}
             for i in range(4)]
    assert not pcf.opening_habits(games, "1800+")


def test_a_real_opening_habit_links_to_its_game_moment():
    games = [{"game_id": f"g{i}", "rows": _rows(f, "Bg4", cp)}
             for i, (f, cp) in enumerate([(MODERN_BC4, 238), (MODERN_NC3, 60), (MODERN_C3, 70)])]
    h = pcf.opening_habits(games, "1800+")[0]
    assert h["review_url"] == "/game/g0?move=4"


# --------------------------------------------------------------------------
# traps (roles from the engine, not from a field)
# --------------------------------------------------------------------------
@pytest.fixture
def scholars(monkeypatch):
    roles = {"italian-game#0": {"name": "Scholar's Mate Danger", "setter": "white", "lesson_kind": None,
                                "setup_san": ["e4", "e5", "Bc4", "Nc6", "Qh5"],
                                "trap_line_san": ["Nf6", "Qxf7#"], "setup_fen": "x"}}
    monkeypatch.setattr(pcf, "_TRAP_ROLES", roles)
    return roles


def _fire(gid, colour, full, setter_field="black"):
    # setter_field is the scanner's own (parity) guess; the engine's side wins.
    return {"game_id": gid, "user_color": colour,
            "fire": {"trap_name": "Scholar's Mate Danger", "full_sprung": full, "setter_color": setter_field}}


def test_trap_cases_use_the_engine_side_and_the_whole_line(scholars):
    out = pcf.trap_record([_fire("a", "black", True), _fire("b", "black", False),
                           _fire("c", "white", False), _fire("d", "white", True)], {})
    assert [t["headline"] for t in out["caught"]] == ["This trap has caught you."]
    assert out["caught"][0]["side"] == "black" and out["caught"][0]["game_id"] == "a"
    assert out["waiting"][0]["game_id"] == "b" and out["waiting"][0]["side"] == "black"
    assert out["could_set"][0]["side"] == "white" and out["sprang"][0]["game_id"] == "d"
    for rows in out.values():
        for t in rows:
            assert not re.search(r"\d", t["headline"] + t["detail"])


def test_a_trap_the_engine_did_not_decide_is_not_shown(scholars):
    unknown = {"game_id": "a", "user_color": "black", "fire": {"trap_name": "Fried Liver Attack", "full_sprung": True}}
    assert all(rows == [] for rows in pcf.trap_record([unknown], {}).values())


def test_an_unknown_practice_key_links_nowhere(scholars):
    out = pcf.trap_record([_fire("a", "white", False)], {"italian-game#0": "not_a_real_key"})
    assert out["could_set"][0]["practice_url"] is None


def test_the_trap_school_file_holds_only_verified_lines():
    import json
    school = json.loads(pcf.TRAP_SCHOOL_PATH.read_text(encoding="utf-8"))["traps"]
    assert school, "data/trap_school.json is missing or empty"
    for t in school:
        board = chess.Board()
        for san in t["setup_san"]:
            board.push_san(san)
        assert board.fen() == t["setup_fen"]
        for step in t["steps"]:
            board.push_san(step["san"])
            assert board.fen() == step["fen_after"]
        assert t["examples"], t["name"]
        assert not re.search(r"\d", t["how_common"]), t["how_common"]
        for ex in t["examples"]:
            # Every example game really plays the setup and the whole trap line.
            g = chess.Board()
            seen = set()
            for san in ex["moves"][: ex["line_plies"] + 10]:
                g.push_san(san)
                seen.add(g.board_fen())
            assert board.board_fen() in seen, (t["name"], ex["id"])


def test_a_change_needs_games_behind_it():
    # Seen in no earlier game and two recent ones: not "showing up more".
    assert pch.change_state(2, 20, 0.0, hits_then=0) == "same"
    assert pch.change_state(3, 20, 0.0, hits_then=0) == "worse"
    # A baseline of one game is not one to be "kept" against.
    assert pch.change_state(0, 20, 0.2, hits_then=1) == "same"
    assert pch.change_state(0, 20, 0.2, hits_then=8) == "kept"


def test_verified_trap_roles_file_is_well_formed():
    roles = pcf.trap_roles()
    assert roles, "data/trap_roles_verified.json is missing or empty"
    for key, t in roles.items():
        board = chess.Board()
        for san in t["setup_san"] + t["trap_line_san"]:
            board.push_san(san)  # raises on an illegal line
        assert t["setter"] in ("white", "black")


# --------------------------------------------------------------------------
# the last game
# --------------------------------------------------------------------------
def test_last_game_deciding_move_and_its_repeat():
    habit = {"side": "black", "line": "g6 Bg7", "idea": "Bg4"}
    game = {"game_id": "new", "user_color": "black", "result": "1-0"}
    read = pcf.last_game_read(game, _rows(MODERN_BC4, "Bg4", 238), [habit])
    assert read["clean"] is False and read["san"] == "Bg4" and read["better_san"] == "Nf6"
    assert read["review_url"] == "/game/new?move=4"
    assert read["repeat"] and not re.search(r"\d", read["repeat"]["words"])
    # A different opening is not "the same as before".
    other = pcf.last_game_read(game, _rows(MODERN_BC4, "Bg4", 238), [{**habit, "line": "e5 Nc6"}])
    assert other["repeat"] is None


def test_a_game_without_a_deciding_move_is_clean():
    read = pcf.last_game_read({"game_id": "g", "user_color": "black", "result": "0-1"},
                              _rows(MODERN_BC4, "Bg4", 90), [])
    assert read["clean"] is True and not re.search(r"\d", read["headline"] + read["detail"])


# --------------------------------------------------------------------------
# play positions
# --------------------------------------------------------------------------
def test_play_positions_are_his_side_to_move_and_unique():
    last = {"clean": False, "fen": MODERN_BC4, "user_color": "black", "game_id": "g"}
    habit_same = {"side": "black", "fen": MODERN_BC4, "game_id": "h"}
    wrong_side = {"side": "white", "fen": MODERN_NC3, "game_id": "w"}
    out = pcf.play_positions([habit_same, wrong_side], last, None)
    assert [p["source_game_id"] for p in out] == ["g"]


# --------------------------------------------------------------------------
# habit and progress
# --------------------------------------------------------------------------
def test_change_state_needs_evidence_beyond_chance():
    assert pch.change_state(0, 20, 0.5) == "kept"
    assert pch.change_state(2, 20, 0.5) == "better"
    assert pch.change_state(9, 20, 0.5) == "same"
    assert pch.change_state(17, 20, 0.5) == "worse"
    assert pch.change_state(0, 4, 0.5) == "waiting"
    assert pch.change_state(3, 20, None) == "waiting"


def _games(n, start=datetime(2026, 10, 1, tzinfo=timezone.utc)):
    gs = [{"game_id": f"g{i}", "result": "0-1", "user_color": "white",
           "played_at_utc": start + timedelta(days=i)} for i in range(n)]
    return list(reversed(gs))  # newest first


def _fork_obs(game_ids):
    # missed_fork is a PLAN-trusted problem in coach_plan_service.PROBLEMS.
    return [{"game_id": g, "missed_pattern": "missed_tactic", "subtype": "missed_fork", "eval_before": 0,
             "fen_before": MODERN_BC4, "move_uci": "c8g4", "ply": 8, "move_number": 4} for g in game_ids]


def test_progress_reads_each_trusted_problem_against_his_own_past():
    from services import coach_plan_service as cp

    games = _games(60)
    ids = [g["game_id"] for g in games]
    obs = _fork_obs(ids[20:60:2])  # half his older games, none of his newest twenty
    if not any(cp.quality_id(o) for o in obs):
        pytest.skip("missed fork is not PLAN-trusted in this detector registry")
    out = pch.progress(ids, pch.games_map(games), obs)
    states = {r["quality_id"]: r["state"] for r in out["habits"] + out["kept"]}
    assert set(states.values()) == {"kept"}
    for r in out["kept"]:
        assert not re.search(r"\d", r["title"] + r["words"])


def test_the_habit_is_kept_while_young_and_still_in_his_top_three():
    from services import coach_plan_service as cp

    games = _games(30)
    ids = [g["game_id"] for g in games]
    obs = _fork_obs(ids[:10])
    if not any(cp.quality_id(o) for o in obs):
        pytest.skip("missed fork is not PLAN-trusted in this detector registry")
    gmap = pch.games_map(games)
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    first = pch.choose_habit(ids, gmap, obs, None, now=now)
    assert first and first["rule"] and first["warning_sign"]["text"]
    again = pch.choose_habit(ids, gmap, obs, first, now=now + timedelta(days=3))
    assert again["started_at"] == first["started_at"]
    later = pch.choose_habit(ids, gmap, obs, first, now=now + timedelta(days=30))
    assert later["started_at"] == now + timedelta(days=30)


# --------------------------------------------------------------------------
# who may read it, and what reaches the page
# --------------------------------------------------------------------------
def test_view_as_opens_the_pages_for_the_viewed_player_only(monkeypatch):
    monkeypatch.delenv(pcf.FLAG_ENV, raising=False)
    plain = SimpleNamespace(state=SimpleNamespace())
    viewing = SimpleNamespace(state=SimpleNamespace(view_as={"target_user_id": "u1", "admin_user_id": "a"}))
    assert not pcf.is_enabled_for_request(plain, "u1")
    assert pcf.is_enabled_for_request(viewing, "u1")
    assert not pcf.is_enabled_for_request(viewing, "u2")
    monkeypatch.setenv(pcf.FLAG_ENV, "u2")
    assert pcf.is_enabled_for_request(plain, "u2")


def test_build_file_and_payload_carry_no_digits_in_player_text(scholars):
    games = []
    t0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
    for i, (fen, cp) in enumerate([(MODERN_BC4, 238), (MODERN_NC3, 90), (MODERN_C3, 120)]):
        games.append({"game_id": f"g{i}", "is_analyzed": True, "user_color": "black", "result": "1-0",
                      "played_at_utc": t0 - timedelta(days=i), "pgn": "", "black_rating": 1850})
    analyses = [{"game_id": g["game_id"], "rows": _rows(f, "Bg4", cp)}
                for g, (f, cp) in zip(games, [(MODERN_BC4, 238), (MODERN_NC3, 90), (MODERN_C3, 120)])]
    doc = pcf.build_file("u", games, analyses, [], _rows(MODERN_BC4, "Bg4", 238), None, None, now=t0)
    out = pcf.payload(doc, [])
    assert out["state"] == "ready" and out["openings"] and out["last_game"]["repeat"]

    def walk(node, key=None):
        if isinstance(node, dict):
            for k, v in node.items():
                if k != "measured":
                    walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, str) and key in ("headline", "detail", "words", "title", "text", "rule"):
            assert not re.search(r"\d", node), (key, node)

    walk(out)


# --------------------------------------------------------------------------
# Home never says the coach is unprepared (Mohit, 2026-11-12)
# --------------------------------------------------------------------------
def test_prepared_focus_order_habit_then_opening_and_never_the_last_game_twice():
    from routes.home import prepared_focus

    read = {"source": {"analysed_games_read": 30}}
    habit = {"label": "Leaving a piece where it can be taken", "rule": "Look first.",
             "warning_sign": {"title": "The three looks", "text": "Look from the square."},
             "moments": [{"game_id": "g1", "move_number": 14}]}
    opening = {"headline": "As Black, you keep playing this move early, and it keeps costing you.",
               "detail": "Here is the clearest time.", "review_url": "/game/g2?move=4"}
    last = {"clean": False, "headline": "One move decided your last game.", "review_url": "/game/g3?move=20"}

    a = prepared_focus({**read, "habit": habit, "openings": [opening], "last_game": last})
    assert a["kind"] == "habit" and a["see_url"] == "/game/g1?move=14" and a["rule"] == "Look first."
    b = prepared_focus({**read, "habit": None, "openings": [opening], "last_game": last})
    assert b["kind"] == "opening" and b["see_url"] == "/game/g2?move=4"
    # The last game is LastGameCard's: Home's coach card never repeats it.
    c = prepared_focus({**read, "habit": None, "openings": [], "last_game": last})
    assert c == {"state": "ready", "kind": "none"}
    e = prepared_focus({"source": {"analysed_games_read": 0}})
    assert e["kind"] == "reading"
    for x in (a, b, c, e):
        text = " ".join(str(x.get(k) or "") for k in ("title", "detail", "rule"))
        assert "not settled" not in text and not re.search(r"\d", text), text


# --------------------------------------------------------------------------
# trap school
# --------------------------------------------------------------------------
def test_trap_school_puts_his_own_traps_first_and_shows_no_figures():
    from services import trap_school as ts

    first = ts.traps()[0]
    page = ts.school({"caught": [{"key": first["key"], "game_id": "g1"}], "waiting": [{"key": "nope#0"}]})
    assert page["mine"][0]["case"] == "caught" and page["mine"][0]["traps"][0]["game_id"] == "g1"
    assert len(page["mine"]) == 1  # an unknown key is dropped, not shown empty
    assert len(page["all"]) == len(ts.traps())
    one = ts.by_slug(ts.slug(first["key"]))
    assert one["steps"] and one["examples"] and "measured" not in one
    assert ts.by_slug("no-such-trap") is None

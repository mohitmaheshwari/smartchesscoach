"""The knowledge record and teaching games (docs/daily_coach_plan_scope.md, section 9)."""
import chess

from services import idea_knowledge as ik
from services import teaching_games as tg

# The Blackburne Shilling trap: 5.Nxf7? lets Black mate.
PGN = """[Event "Rated blitz game"]
[Site "https://lichess.org/abcdefgh"]
[Result "0-1"]
[WhiteElo "1210"]
[BlackElo "1250"]
[Opening "Italian Game: Blackburne Shilling Gambit"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3# 0-1
"""


def _puzzle():
    b = chess.Board()
    for san in ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4", "Nxe5", "Qg5"]:
        b.push_san(san)
    return {"puzzle_id": "p1", "fen": b.fen(), "moves": "e5f7 g5g2 h1f1 g2e4 c4e2 d4f3"}


def test_the_walk_through_stops_after_the_move_that_allowed_it():
    s = tg.study(PGN, _puzzle())
    assert s["moves_before"][-1] == "Nxf7" and len(s["moves_before"]) == 9
    assert s["solver"] == "black"
    assert s["solution"] == ["Qxg2", "Rf1", "Qxe4+", "Be2", "Nf3#"]
    assert s["found_in_game"] is True and s["result"] == "0-1"


def test_a_game_that_never_reaches_the_puzzle_is_refused():
    p = _puzzle()
    p["fen"] = chess.Board("8/8/8/8/8/8/8/K6k w - - 0 1").fen()
    assert tg.study(PGN, p) is None


def test_openings_match_lichess_tags_most_specific_first():
    tags = {tg.norm(t): t for t in ["Caro-Kann_Defense", "Caro-Kann_Defense_Exchange_Variation", "Italian_Game"]}
    assert tg.tags_for("Caro Kann Defense Exchange Variation 3...cxd5", tags) == [
        "Caro-Kann_Defense_Exchange_Variation", "Caro-Kann_Defense"]
    assert tg.his_openings([{"opening": "Italian Game", "user_color": "black"}] * 2
                           + [{"opening": "Caro Kann Defense", "user_color": "black"}])[0] == ("Italian Game", "black")
    assert tg.game_id_of("https://lichess.org/TiwHxq8n#25") == "TiwHxq8n"


def test_openings_are_named_from_the_moves_and_variants_are_skipped():
    italian = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 *"
    name = tg.opening_name(italian)
    assert name and name.startswith("Italian Game")
    games = [{"pgn": italian, "user_color": "white", "opening": None},
             {"pgn": "1. Be3 Be4 *", "user_color": "white", "opening": "From Position - None"},
             {"pgn": '[FEN "8/8/8/8/8/8/8/K6k w - - 0 1"]\n\n1. Kb2 *', "user_color": "black", "opening": None}]
    assert tg.his_openings(games) == [(name, "white")]


def test_knowledge_states_from_games_and_puzzles():
    obs = [{"tactic_tags": [{"motif": "fork", "kind": "missed"}, {"motif": "fork", "kind": "missed"},
                            {"motif": "pin", "kind": "found"}, {"motif": "pin", "kind": "found"},
                            {"motif": "skewer", "kind": "missed"}, {"motif": "forced_mate", "concept_id": "tactic.mate_in_one",
                                                                     "kind": "allowed"}]}]
    attempts = [{"topic": "theme-skewer", "correct": True}] * 3
    rec = ik.record(obs, attempts)
    assert rec["fork"]["state"] == "misses" and rec["pin"]["state"] == "knows"
    assert rec["skewer"]["state"] == "puzzles_only" and rec["mate_in_one"]["allowed"] == 1
    assert ik.to_teach(rec) == ["fork", "skewer"]

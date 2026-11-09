"""Coach plan: ranking by results lost, board facts, cause, check.

docs/coach_assistant_plan_scope.md, signed 2026-11-09. A fake engine scores
moves so the tests do not depend on a Stockfish binary; every board fact is
real python-chess on real positions.
"""
import chess
import chess.engine

from services import coach_plan_service as cp
from routes.academy_coach_plan import found_when_asked, _clean_answers

LANDING = "gap:piece_safety:destination_safety_exact"
FORK = "gap:missed_tactic:missed_fork"
KING = "gap:king_safety:ignored_king_attack"


class FakeEngine:
    """Scores every legal move 0 except `best`, which gets `best_cp` (white POV
    from the mover's side)."""

    def __init__(self, best_uci, best_cp=300):
        self.best, self.best_cp = best_uci, best_cp

    def analyse(self, board, limit, multipv=1):
        me = board.turn
        out = []
        for mv in board.legal_moves:
            v = self.best_cp if mv.uci() == self.best else 0
            out.append({"score": chess.engine.PovScore(chess.engine.Cp(v), me), "pv": [mv]})
        return out


def obs(gid, qid, ev, ply=10, fen=None, uci=None, t=None):
    pattern, subtype = qid.split(":")[1], qid.split(":")[2]
    return {"game_id": gid, "ply": ply, "missed_pattern": pattern, "subtype": subtype,
            "eval_before": ev, "fen_before": fen or chess.STARTING_FEN, "move_uci": uci or "e2e4",
            "time_spent_seconds": t}


def games(**outcomes):
    return {gid: {"outcome": o, "user_color": "white", "played_at": f"2026-11-0{i + 1}"}
            for i, (gid, o) in enumerate(outcomes.items())}


# ---------------------------------------------------------------- ranking
def test_results_lost_outranks_frequency():
    g = games(w1="win", w2="win", w3="win", l1="loss", l2="draw")
    rows = [obs("w1", LANDING, 0), obs("w2", LANDING, 0), obs("w3", LANDING, 0), obs("w1", LANDING, 0),
            obs("l1", FORK, 50), obs("l2", FORK, -80)]
    ranked = cp.rank_problems(g, rows)
    assert ranked[0]["quality_id"] == FORK and ranked[0]["games_lost"] == 2
    assert ranked[1]["quality_id"] == LANDING and ranked[1]["moments"] == 4


def test_the_floor_is_a_pawn_below_level_and_black_is_flipped():
    lost_white = {"outcome": "loss", "user_color": "white"}
    assert cp.costs_result({"eval_before": -100}, lost_white)
    assert not cp.costs_result({"eval_before": -101}, lost_white)
    lost_black = {"outcome": "loss", "user_color": "black"}
    assert cp.costs_result({"eval_before": 100}, lost_black)       # white +1 = black -1
    assert not cp.costs_result({"eval_before": 300}, lost_black)
    assert not cp.costs_result({"eval_before": 500}, {"outcome": "win", "user_color": "white"})


def test_only_plan_grade_detectors_take_part():
    assert cp.quality_id({"missed_pattern": "missed_tactic", "subtype": "missed_fork"}) == FORK
    assert cp.quality_id({"missed_pattern": "missed_tactic", "subtype": "generic_tactic"}) is None
    assert cp.quality_id({"missed_pattern": None}) is None


def test_moments_cost_a_result_first_one_per_game():
    g = games(a="loss", b="win", c="loss")
    rows = [obs("b", LANDING, 0, ply=4), obs("a", LANDING, 0, ply=6), obs("a", LANDING, 0, ply=8),
            obs("c", LANDING, 0, ply=2)]
    chosen = cp.choose_moments(cp.rank_problems(g, rows)[0], 3)
    assert [o["game_id"] for o in chosen][:2] == ["c", "a"]       # result-losing, newest first
    assert len({o["game_id"] for o in chosen}) == len(chosen)


# ---------------------------------------------------------------- moments
QG4_PGN = '[Event "t"]\n[Result "0-1"]\n\n1. e4 d5 2. Qg4 Bxg4 0-1'
QG4_FEN = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"


def test_landing_moment_facts():
    o = {**obs("g", LANDING, 0, fen=QG4_FEN, uci="d1g4"), "_costs_result": True}
    m = cp.build_moment(o, {"pgn": QG4_PGN, "played_at": "2026-11-05T10:00:00"}, FakeEngine("e4d5"))
    assert m["kind"] == "landing" and m["san"] == "Qg4" and m["develops"] is True
    assert m["test"]["answer"] == [{"sq": "c8", "piece": "bishop", "kind": "far_diagonal",
                                    "path": ["d7", "e6", "f5"]}]
    assert m["reply_san"] == "Bxg4"
    assert m["cost"] == {"lost": "queen", "won": "bishop", "can_recapture": False}
    assert set(u[:2] for u in m["practice"]["moves"]) == {"d1"}
    assert m["practice"]["moves"]["d1g4"]["safe"] is False
    assert m["best"]["san"] == "exd5"
    # d7 is empty after 1...d5, so the queen's diagonal reaches the bishop that
    # takes it: the "a line works both ways" case.
    assert any(i["kind"] == "attack" and i["sq"] == "c8" for i in m["intents"])


def test_pinned_guard_makes_the_guard_needed():
    fen = "r1bqk2r/pp1p1ppp/4pn2/4n3/1b2P3/1BN5/PPP2PPP/R1BQK1NR w KQkq - 7 8"
    o = {**obs("g", LANDING, 0, fen=fen, uci="d1f3"), "_costs_result": True}
    m = cp.build_moment(o, {"pgn": "", "played_at": ""}, FakeEngine("c1d2"))
    e4 = next(i for i in m["intents"] if i["sq"] == "e4")
    assert e4["verdict"] == "needed"
    assert e4["guards"][0]["pinned_by"] == {"sq": "b4", "piece": "bishop"}
    assert m["best"]["frees"] == [{"sq": "c3", "piece": "knight", "now_guards": ["e4"]}]


def test_missed_fork_moment_is_a_find_the_move_test():
    fen = "r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1"
    o = {**obs("g", FORK, 0, fen=fen, uci="e1e2"), "_costs_result": False}
    m = cp.build_moment(o, {"pgn": "", "played_at": ""}, FakeEngine("b5c7", 500))
    assert m["test"]["kind"] == "find_move"
    assert m["test"]["accept"] == ["b5c7"]
    assert {t["sq"] for t in m["test"]["explain"]["targets"]} == {"a8", "e8"}


def test_a_moment_that_does_not_replay_is_dropped():
    o = {**obs("g", LANDING, 0, fen=chess.STARTING_FEN, uci="e2e5"), "_costs_result": True}
    assert cp.build_moment(o, {"pgn": ""}, FakeEngine("e2e4")) is None


# ---------------------------------------------------------------- grading the child
def test_found_when_asked_is_graded_from_the_board():
    landing = {"kind": "landing", "test": {"kind": "tap_pieces", "answer": [{"sq": "c8"}, {"sq": "f6"}]}}
    assert found_when_asked(landing, ["c8", "f6", "a7"])
    assert not found_when_asked(landing, ["c8"])
    king = {"kind": "king_attack", "test": {"kind": "tap_pieces", "answer": [{"sq": s} for s in "a1 b2 c3".split()]}}
    assert found_when_asked(king, ["a1", "b2", "h8"])
    assert not found_when_asked(king, ["a1", "h8", "h7"])
    fork = {"kind": "missed_tactic", "test": {"kind": "find_move", "accept": ["b5c7"]}}
    assert found_when_asked(fork, ["e1e2", "b5c7"])
    assert not found_when_asked(fork, ["e1e2", "e1d1", "e1f1", "b5c7"])


def test_answers_from_the_page_are_cleaned():
    m = {"kind": "landing", "test": {"kind": "tap_pieces", "answer": [{"sq": "c8"}]}}
    a = _clean_answers(m, {"picks": [{"kind": "develop"}, {"kind": "hack", "sq": "x"}],
                           "tapped": ["c8"], "seen_in_game": "maybe", "found_when_asked": False})
    assert a["picks"] == [{"kind": "develop", "sq": None}]
    assert a["seen_in_game"] == "unsure"
    assert a["found_when_asked"] is True          # the page's claim is ignored


def test_cause_from_answers():
    assert cp.cause_from([])["kind"] == "not_yet"
    looking = {"found_when_asked": True, "seen_in_game": "no"}
    pattern = {"found_when_asked": False, "seen_in_game": "no"}
    judged = {"found_when_asked": True, "seen_in_game": "ok"}
    assert cp.cause_from([looking, looking, pattern])["kind"] == "not_looking"
    assert cp.cause_from([judged])["kind"] == "misjudged"
    assert cp.cause_from([looking, pattern])["kind"] == "mixed"


def test_every_problem_has_a_sign_and_rules():
    for qid, (kind, pattern, _label) in cp.PROBLEMS.items():
        assert cp.sign_for(kind, pattern)["text"]
        assert len(cp.rule_options(kind, pattern)) >= 2


def test_week_check_compares_with_the_baseline():
    g = games(a="loss", b="win", c="win", d="win")
    rows = [obs("a", LANDING, 0, t=12)]
    check = cp.week_check(LANDING, g, rows, {"games": 10, "hit_games": 6, "rate": 0.6, "median_think_s": 5})
    assert check["hit_games"] == 1 and check["fewer"] is True and check["slower"] is True
    assert "1 of 4 games" in check["words"]

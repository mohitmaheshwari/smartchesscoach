"""Coach plan, amendment A: the development habit as a knowledge problem.

The position is a real production move (2026-11-10): White has played the
queen three times with the b1 knight and c1 bishop still home; the engine
wants Nc3, the player played Qg3.
"""
import chess
import chess.engine

from services import coach_plan_service as cp
from routes.academy_coach_plan import found_when_asked

FEN = "rnb1kb1r/ppp2ppp/8/3qp3/8/4Q3/PP1P1PPP/RNB1KBNR w KQkq - 0 7"


class FakeEngine:
    def __init__(self, best_uci, best_cp=300):
        self.best, self.best_cp = best_uci, best_cp

    def analyse(self, board, limit, multipv=1):
        me = board.turn
        return [{"score": chess.engine.PovScore(chess.engine.Cp(self.best_cp if mv.uci() == self.best else 0), me),
                 "pv": [mv]} for mv in board.legal_moves]


def dev_obs(gid="g1", eligible=True, pattern=None, decision="missed"):
    return {"game_id": gid, "ply": 13, "move_number": 7, "fen_before": FEN, "move_uci": "e3g3",
            "missed_pattern": pattern, "subtype": None, "eval_before": 0,
            "development_decision": decision, "_development_eligible": eligible}


def test_rate_gate_is_the_locked_cut_off():
    def rows(applied, missed, owned=0):
        return ([{"development_decision": "applied"}] * applied + [{"development_decision": "missed"}] * missed
                + [{"development_decision": "missed", "missed_pattern": "piece_safety"}] * owned)
    assert cp.development_rate(rows(14, 6))["eligible"]               # 0.70, 20 chances
    assert not cp.development_rate(rows(15, 5))["eligible"]           # 0.75 is not below
    assert not cp.development_rate(rows(7, 3))["eligible"]            # too few chances
    # a miss owned by piece safety is not a development chance at all
    r = cp.development_rate(rows(15, 4, owned=10))
    assert r["chances"] == 19 and not r["eligible"]


def test_only_an_eligible_child_and_an_unowned_miss_make_the_problem():
    assert cp.quality_id(dev_obs()) == cp.DEVELOPMENT_QID
    assert cp.quality_id(dev_obs(eligible=False)) is None
    assert cp.quality_id(dev_obs(decision="applied")) is None
    # a tactic label on the same row owns the cause
    assert cp.quality_id(dev_obs(pattern="missed_tactic")) is None
    # a label outside the plan does not block it
    assert cp.quality_id(dev_obs(pattern="opening_knowledge")) == cp.DEVELOPMENT_QID


def test_development_moment_is_find_a_developing_move():
    m = cp.build_moment(dev_obs(), {"played_at": "2026-11-01", "pgn": ""}, FakeEngine("b1c3"))
    assert m and m["kind"] == "development"
    assert m["test"]["kind"] == "find_move"
    assert m["test"]["best"]["san"] == "Nc3"
    assert m["test"]["accept"] == ["b1c3"]
    assert {h["sq"] for h in m["test"]["explain"]["home"]} == {"b1", "c1", "f1", "g1"}
    # graded from the board: a developing answer is found, a queen move is not
    assert found_when_asked(m, ["b1c3"]) and not found_when_asked(m, ["g3g7"])


def test_moment_is_dropped_when_the_board_does_not_back_the_claim():
    # The engine prefers a queen move: developing was not better, so no question.
    assert cp.build_moment(dev_obs(), {"played_at": "", "pgn": ""}, FakeEngine("e3e5")) is None


def test_no_answers_yet_shows_the_game_data_reading():
    c = cp.cause_from([], cp.DEVELOPMENT_QID)
    assert c["prior"] == "unknown_pattern" and "not learned yet" in c["words"]
    assert cp.cause_from([], "gap:missed_tactic:missed_fork")["kind"] == "not_yet"
    assert "prior" not in cp.cause_from([], "gap:missed_tactic:missed_fork")


def test_sign_and_rules_exist():
    assert cp.sign_for("development", None)["title"]
    assert len(cp.rule_options("development", None)) == 2


def test_parent_report_names_the_idea_once_approved_and_never_a_digit():
    import re
    from services.academy_service import render_report
    week = {"games": {"count": 5, "days": 3, "analysed": 5},
            "coach_plan": {"status": "approved", "problem": {"kind": "development"}}}
    rep = render_report(week, child_name="Asha")
    plan = [s for s in rep["sections"] if s["kind"] == "plan"]
    assert plan and "bring all the pieces into the game" in plan[0]["headline"]
    assert not re.search(r"\d", " ".join([plan[0]["headline"], *plan[0]["lines"]]))
    draft = render_report({**week, "coach_plan": {"status": "draft", "problem": {"kind": "development"}}},
                          child_name="Asha")
    assert not [s for s in draft["sections"] if s["kind"] == "plan"]

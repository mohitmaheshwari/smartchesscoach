"""The human-move opponent (coach_play/human_opponent.py, docs/coaching_intelligence_scope.md 1c)."""
import asyncio
import random

import chess

from coach_play import human_opponent as ho
from coach_play.coach_opponent import PedagogicalOpponent, opponent_strength_record


class _Dist:
    def __init__(self, probs):
        self.probs = probs

    def probability_of(self, uci):
        return self.probs.get(uci)


class _Maia:
    def __init__(self, probs):
        self.probs = probs
        self.calls = []

    def predict(self, ctx, top_k=10):
        self.calls.append((ctx.player_elo, ctx.opponent_elo))
        return _Dist(self.probs)


def test_the_tail_is_never_sampled_and_the_rest_follows_maia():
    rng = random.Random(1)
    dist = {"e2e4": 0.6, "d2d4": 0.399, "h2h4": 0.001}
    picks = [ho.sample(dist, rng) for _ in range(2000)]
    assert "h2h4" not in picks
    assert 0.55 < picks.count("e2e4") / len(picks) < 0.65


def test_choose_move_samples_at_the_players_rating_and_reports_it(monkeypatch):
    maia = _Maia({"e2e4": 0.7, "g1f3": 0.3})
    monkeypatch.setattr(ho, "_maia", lambda: maia)
    choice = ho.choose_move(chess.STARTING_FEN, 731, 731, rng=random.Random(3))
    assert choice["san"] in ("e4", "Nf3") and choice["target_rating"] == 731 and choice["legal_moves"] == 20
    assert maia.calls == [(731, 731)]


def test_no_maia_means_no_move_so_the_caller_falls_back(monkeypatch):
    monkeypatch.setattr(ho, "_maia", lambda: None)
    assert ho.choose_move(chess.STARTING_FEN, 900, 900) is None


def test_the_flag_is_per_player(monkeypatch):
    monkeypatch.setenv(ho.FLAG_ENV, "u1,u2")
    assert ho.enabled_for("u1") and not ho.enabled_for("u3") and not ho.enabled_for(None)
    monkeypatch.setenv(ho.FLAG_ENV, "*")
    assert ho.enabled_for("anyone")


def test_the_coach_opponent_uses_it_only_when_on(monkeypatch):
    monkeypatch.setattr(ho, "choose_move", lambda fen, t, p, rng=None: {"san": "Nf3", "probability": 0.3, "rank": 2,
                                                                         "target_rating": t})
    opp = PedagogicalOpponent(user_rating=731)
    opp.human_user_id = "u1"
    monkeypatch.setenv(ho.FLAG_ENV, "u1")
    assert asyncio.run(opp.get_move(chess.STARTING_FEN)) == "Nf3"
    ctx = opp.get_teaching_context()
    assert ctx["human_policy"]["used"] and ctx["teaching_goal"] == "natural_play"
    monkeypatch.setenv(ho.FLAG_ENV, "someone_else")
    other = PedagogicalOpponent(user_rating=731)
    other.human_user_id = "u1"
    called = []
    monkeypatch.setattr(ho, "choose_move", lambda *a, **k: called.append(1))
    monkeypatch.setattr(other, "_get_opening_guided_move", lambda fen: "e4")
    assert asyncio.run(other.get_move(chess.STARTING_FEN)) == "e4" and not called


def test_the_session_record_shows_the_human_opponent_without_a_floor():
    rec = opponent_strength_record(731, "coach", human=True)
    assert rec["engine_path"] == "human_policy" and rec["strength_rating"] == 731 and not rec["floor_applied"]
    assert opponent_strength_record(731, "play", human=True)["engine_path"] == "weakened_engine"


def test_warm_up_runs_one_prediction_and_never_raises(monkeypatch):
    monkeypatch.setattr(ho, "_maia", lambda: _Maia({"e2e4": 1.0}))
    assert ho.warm() is True
    monkeypatch.setattr(ho, "_maia", lambda: None)
    assert ho.warm() is False

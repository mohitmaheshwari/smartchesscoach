"""The provider abstraction must never invent a probability or crash analysis.

These run without either model installed: the point is the contract, not the
weights. Provider output shapes are pinned to REAL observed returns --
Maia-2's inference_each gives (move_probs, win_probability), which an earlier
normaliser silently dropped.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.human_behavior_engine import (  # noqa: E402
    MoveContext,
    MoveDistribution,
    Maia2Provider,
    OtterProvider,
    _normalise_provider_output,
    get_providers,
)

FEN = "r2q1rk1/ppp1bppp/2n2n2/4p3/6b1/2NP1N2/PPP1BPPP/R1BQ1RK1 b - - 0 8"


def _ctx(**kw):
    base = dict(fen=FEN, player_elo=1265, opponent_elo=1344)
    base.update(kw)
    return MoveContext(**base)


# --- output normalisation, pinned to shapes actually returned -------------

def test_maia2_tuple_shape_is_understood():
    """inference_each returns (move_probs, win_prob) -- the win_prob is NOT a move."""
    raw = ({"e5e4": 0.21, "g4f3": 0.20}, 0.6068)
    out = _normalise_provider_output(raw)
    assert out == {"e5e4": 0.21, "g4f3": 0.20}
    assert 0.6068 not in out.values() or len(out) == 2


def test_plain_mapping_shape():
    assert _normalise_provider_output({"e2e4": 0.5}) == {"e2e4": 0.5}


def test_wrapped_mapping_shapes():
    for key in ("move_probs", "probabilities", "top_moves"):
        assert _normalise_provider_output({key: {"e2e4": 0.4}}) == {"e2e4": 0.4}


def test_list_of_dicts_shape():
    raw = [{"uci": "e2e4", "probability": 0.4}, {"move": "d2d4", "prob": 0.2}]
    assert _normalise_provider_output(raw) == {"e2e4": 0.4, "d2d4": 0.2}


def test_unknown_shapes_yield_nothing_rather_than_garbage():
    for raw in (None, 42, "e2e4", object(), [1, 2, 3]):
        assert _normalise_provider_output(raw) == {}


# --- distribution semantics ---------------------------------------------

def test_surprise_is_negative_log_probability():
    d = MoveDistribution("t", "1", {"e2e4": 0.25})
    assert math.isclose(d.human_surprise("e2e4"), -math.log(0.25), rel_tol=1e-9)


def test_unlisted_move_gives_no_surprise_rather_than_infinity():
    """A truncated top-k list is not evidence a move is never played."""
    d = MoveDistribution("t", "1", {"e2e4": 0.9})
    assert d.human_surprise("h2h4") is None
    assert d.probability_of("h2h4") is None


def test_zero_probability_does_not_raise():
    d = MoveDistribution("t", "1", {"e2e4": 0.0})
    assert d.human_surprise("e2e4") is None


def test_top_is_ordered_by_probability():
    d = MoveDistribution("t", "1", {"a": 0.1, "b": 0.5, "c": 0.3})
    assert [u for u, _ in d.top(2)] == ["b", "c"]


# --- graceful degradation -----------------------------------------------

def test_unavailable_provider_returns_none_not_an_exception():
    class Missing(OtterProvider):
        def available(self):
            return False

    assert Missing().predict(_ctx()) is None


def test_provider_failure_degrades_to_none():
    class Broken(OtterProvider):
        def available(self):
            return True

        def _load(self):
            raise RuntimeError("weights missing")

    assert Broken().predict(_ctx()) is None


def test_get_providers_never_returns_an_unavailable_one():
    for p in get_providers():
        assert p.available()


# --- context contract ----------------------------------------------------

def test_context_carries_more_than_maia_needs():
    """Otter needs history and clock; the shape must not be Maia-specific."""
    ctx = _ctx(history_uci=["e2e4", "e7e5"], clock_seconds=894,
               clock_fraction=0.99, time_control="900+10")
    assert ctx.history_uci and ctx.clock_seconds and ctx.clock_fraction
    assert ctx.time_control == "900+10"


def test_context_is_immutable():
    import dataclasses
    ctx = _ctx()
    try:
        ctx.player_elo = 2000
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("MoveContext must be frozen")


def test_predict_across_elos_probes_each_rating_without_mutating_context():
    seen = []

    class Fake(Maia2Provider):
        def available(self):
            return True

        def predict(self, ctx, top_k=10):
            seen.append(ctx.player_elo)
            return MoveDistribution("fake", "1", {"e2e4": 0.1})

    ctx = _ctx()
    out = Fake().predict_across_elos(ctx, [1100, 1300, 1500], "e2e4")
    assert seen == [1100, 1300, 1500]
    assert set(out) == {1100, 1300, 1500}
    assert ctx.player_elo == 1265          # original untouched

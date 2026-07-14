"""Tests for the prescription-tracking metric + auto-close (rewritten 2026-07-14, W2).

The 2026-07-14 rewrite replaced the lifetime-SUM-vs-7-day-SUM metric (window-size
biased: guaranteed ">50% improvement" once 3 games existed) with per-game rates over
symmetric windows. These tests lock that math with a deterministic in-memory fake DB —
no Mongo, no network, CI-runnable. Replaces the old file's documentation-style stubs
(most were `pass`) with executable assertions, including the edge cases the old
TestMetricEdgeCases class listed but never implemented.

Run: python backend/tests/test_prescription_tracking.py   (or pytest)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.prescription_tracking_service import (
    BASELINE_MAX_GAMES,
    MIN_GAMES_AFTER_TRAINING,
    _normalize_game_date,
    _started_date,
    calculate_gap_rate,
    calculate_improvement_percentage,
    compute_prescription_progress,
)


# ── Fake async Mongo (just enough for calculate_gap_rate) ─────────────────
class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, _n):
        return self._docs


class _FakeColl:
    def __init__(self, docs):
        self._docs = docs

    def find(self, query, _proj=None):
        out = []
        for d in self._docs:
            ok = True
            for k, v in query.items():
                if isinstance(v, dict) and "$in" in v:
                    if d.get(k) not in v["$in"]:
                        ok = False
                elif d.get(k) != v:
                    ok = False
            if ok:
                out.append(dict(d))
        return _FakeCursor(out)


class _FakeDB:
    def __init__(self, games, analyses):
        self.games = _FakeColl(games)
        self.game_analyses = _FakeColl(analyses)


def _mk_game(gid, date):
    return {"user_id": "u1", "game_id": gid, "date_played": date, "is_analyzed": True}


def _mk_analysis(gid, moves):
    """moves: list of (cognitive_gap, cp_loss) user moves, or dicts for full control."""
    evals = []
    for m in moves:
        if isinstance(m, dict):
            evals.append(m)
        else:
            evals.append({"cognitive_gap": m[0], "cp_loss": m[1], "is_opponent_move": False})
    return {"game_id": gid, "stockfish_analysis": {"move_evaluations": evals}}


# ── date normalization ─────────────────────────────────────────────────────
def test_normalize_game_date():
    assert _normalize_game_date("2026.03.01") == "2026-03-01"      # chess.com PGN form
    assert _normalize_game_date("2026-07-10T13:38:44") == "2026-07-10"
    assert _normalize_game_date(None) is None
    assert _normalize_game_date("") is None
    assert _normalize_game_date("junk") is None


def test_started_date():
    from datetime import datetime, timezone
    assert _started_date("2026-07-10T13:38:44.119603") == "2026-07-10"
    assert _started_date(datetime(2026, 7, 10, tzinfo=timezone.utc)) == "2026-07-10"
    assert _started_date(None) is None


# ── improvement formula ────────────────────────────────────────────────────
def test_improvement_percentage():
    assert calculate_improvement_percentage(100.0, 50.0) == 0.5
    assert calculate_improvement_percentage(100.0, 0.0) == 1.0
    assert calculate_improvement_percentage(0.0, 50.0) == 0.0     # no baseline -> unmeasurable
    assert calculate_improvement_percentage(100.0, 150.0) == 0.0  # regression floors at 0


# ── per-game rate: the window-bias regression test ────────────────────────
def test_gap_rate_is_per_game_not_sum():
    """The exact failure the rewrite fixes: 20 old games with the gap vs 3 new
    ones. Old SUM metric: baseline 2000 vs current 300 -> '85% improvement'
    with IDENTICAL per-game behavior. New rate metric must say 0%."""
    games, analyses = [], []
    for i in range(20):  # before training: 100cp of piece_safety per game
        gid = f"old{i}"
        games.append(_mk_game(gid, f"2026-06-{i+1:02d}"))
        analyses.append(_mk_analysis(gid, [("piece_safety", 100)]))
    for i in range(3):   # after training: SAME 100cp per game
        gid = f"new{i}"
        games.append(_mk_game(gid, f"2026-07-{i+10:02d}"))
        analyses.append(_mk_analysis(gid, [("piece_safety", 100)]))
    db = _FakeDB(games, analyses)

    b_avg, b_n = asyncio.run(calculate_gap_rate(
        db, "u1", "piece_safety", before_date="2026-07-01", max_games=BASELINE_MAX_GAMES))
    c_avg, c_n = asyncio.run(calculate_gap_rate(
        db, "u1", "piece_safety", after_date="2026-07-01"))

    assert (b_avg, b_n) == (100.0, 20)
    assert (c_avg, c_n) == (100.0, 3)
    assert calculate_improvement_percentage(b_avg, c_avg) == 0.0  # no false improvement


def test_gap_rate_denominator_is_all_analyzed_games():
    """Incidence dropping must lower the rate: gap in 2 of 4 games -> rate
    counts all 4 analyzed games, not just the 2 with the gap. (The old file's
    'games_with_no_moves_in_gap' edge case, now executable.)"""
    games = [_mk_game(f"g{i}", f"2026-06-0{i+1}") for i in range(4)]
    analyses = [
        _mk_analysis("g0", [("piece_safety", 200)]),
        _mk_analysis("g1", []),
        _mk_analysis("g2", [("piece_safety", 200)]),
        _mk_analysis("g3", []),
    ]
    avg, n = asyncio.run(calculate_gap_rate(_FakeDB(games, analyses), "u1", "piece_safety"))
    assert n == 4
    assert avg == 100.0  # 400cp / 4 games — NOT 200


def test_gap_rate_excludes_opponent_zero_and_other_gaps():
    """Old TestMetricEdgeCases stubs, executable: opponent moves excluded,
    cp_loss=0 ignored, other gaps isolated."""
    games = [_mk_game("g0", "2026-06-01")]
    analyses = [_mk_analysis("g0", [
        {"cognitive_gap": "piece_safety", "cp_loss": 100, "is_opponent_move": False},
        {"cognitive_gap": "piece_safety", "cp_loss": 500, "is_opponent_move": True},   # opponent
        {"cognitive_gap": "piece_safety", "cp_loss": 0, "is_opponent_move": False},    # zero loss
        {"cognitive_gap": "king_safety", "cp_loss": 300, "is_opponent_move": False},   # other gap
    ])]
    avg, n = asyncio.run(calculate_gap_rate(_FakeDB(games, analyses), "u1", "piece_safety"))
    assert (avg, n) == (100.0, 1)


def test_gap_rate_dot_dates_window():
    """chess.com '2026.03.01' dates must window correctly against ISO cutoffs
    (the old code compared them lexicographically against ISO strings — always
    true, so 'games after start' silently included the entire history)."""
    games = [_mk_game("a", "2026.03.01"), _mk_game("b", "2026.07.12")]
    analyses = [_mk_analysis("a", [("king_safety", 300)]),
                _mk_analysis("b", [("king_safety", 100)])]
    db = _FakeDB(games, analyses)
    avg, n = asyncio.run(calculate_gap_rate(db, "u1", "king_safety", after_date="2026-07-01"))
    assert n == 1 and avg == 100.0     # only the July game
    avg, n = asyncio.run(calculate_gap_rate(db, "u1", "king_safety", before_date="2026-07-01"))
    assert n == 1 and avg == 300.0     # only the March game


# ── eligibility gates ──────────────────────────────────────────────────────
def _progress(db, started="2026-07-01T00:00:00"):
    return asyncio.run(compute_prescription_progress(db, {
        "user_id": "u1", "issue_detected": "piece_safety", "started_at": started,
    }))


def test_progress_real_improvement_is_eligible():
    games, analyses = [], []
    for i in range(6):   # baseline: 200cp/game
        games.append(_mk_game(f"o{i}", f"2026-06-{i+1:02d}"))
        analyses.append(_mk_analysis(f"o{i}", [("piece_safety", 200)]))
    for i in range(3):   # after: 50cp/game = 75% improvement
        games.append(_mk_game(f"n{i}", f"2026-07-{i+2:02d}"))
        analyses.append(_mk_analysis(f"n{i}", [("piece_safety", 50)]))
    p = _progress(_FakeDB(games, analyses))
    assert p["eligible"] is True
    assert abs(p["improvement"] - 0.75) < 0.01


def test_progress_gates():
    # not started
    p = asyncio.run(compute_prescription_progress(_FakeDB([], []), {
        "user_id": "u1", "issue_detected": "piece_safety", "started_at": None}))
    assert p["reason"] == "not_started"
    # no gap
    p = asyncio.run(compute_prescription_progress(_FakeDB([], []), {
        "user_id": "u1", "issue_detected": "", "started_at": "2026-07-01"}))
    assert p["reason"] == "no_cognitive_gap"
    # invalid baseline (behavioral issue like 'rushing' never appears on moves)
    games = [_mk_game(f"g{i}", f"2026-06-0{i+1}") for i in range(5)]
    analyses = [_mk_analysis(f"g{i}", [("piece_safety", 100)]) for i in range(5)]
    p = asyncio.run(compute_prescription_progress(_FakeDB(games, analyses), {
        "user_id": "u1", "issue_detected": "rushing", "started_at": "2026-07-01"}))
    assert p["reason"] == "invalid_baseline" and p["eligible"] is False
    # insufficient games after start
    games2 = games + [_mk_game("n0", "2026-07-02")]
    analyses2 = analyses + [_mk_analysis("n0", [("piece_safety", 10)])]
    p = _progress(_FakeDB(games2, analyses2))
    assert p["reason"] == "insufficient_games_after_start"
    assert p["current_games"] == 1 < MIN_GAMES_AFTER_TRAINING
    # insufficient improvement
    games3 = games + [_mk_game(f"n{i}", f"2026-07-0{i+2}") for i in range(3)]
    analyses3 = analyses + [_mk_analysis(f"n{i}", [("piece_safety", 80)]) for i in range(3)]
    p = _progress(_FakeDB(games3, analyses3))
    assert p["reason"] == "insufficient_improvement"   # 20% < 50%
    assert p["eligible"] is False


# ── calibration math (W4 consumer, same buckets the endpoint uses) ─────────
def test_calibration_buckets():
    from services.rate_your_move import quality_bucket
    rows = [
        ("good", "best", True), ("good", "good", True), ("inaccuracy", "inaccuracy", True),
        ("mistake_blunder", "blunder", True), ("mistake_blunder", "mistake", True),
        ("good", "best", True), ("inaccuracy", "inaccuracy", True),
        ("good", "blunder", False), ("good", "mistake", False), ("good", "blunder", False),
        ("mistake_blunder", "good", False), ("inaccuracy", "best", False),
    ]
    total = len(rows)
    accurate = sum(1 for _, _, c in rows if c)
    real_mistakes = [(g, a) for g, a, _ in rows if quality_bucket(a) == "mistake_blunder"]
    blind = sum(1 for g, _ in real_mistakes if g == "good")
    assert round(100 * accurate / total) == 58
    assert len(real_mistakes) == 5 and blind == 3
    assert round(100 * blind / len(real_mistakes)) == 60


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

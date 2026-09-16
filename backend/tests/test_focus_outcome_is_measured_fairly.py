"""The focus outcome check has to measure the player, not our own detectors.

`user_active_focus` carried a `baseline_metric` from the day each focus was
locked and a `current_metric` that was never once written -- 53 baselines, 0
currents on production. Three separate things kept it that way, and all three
are asserted below:

  1. every `cycle_version: 1` focus returned `measurement_pending` before
     looking at anything (43 of the 53);
  2. the window was built from `analyzed_at`, which is when WE got round to
     analysing a game, not when it was played (the other 10 returned
     `no_data`);
  3. the daily loop matched `type: "weakness"` exactly, so the 8 legacy rows
     written before that field existed were never even selected.

The fourth problem was the one that mattered most, because it would have
produced a *wrong answer* rather than no answer. Differencing today's count
against a baseline that older detectors produced scores our own detector
changes as if the player had changed. Measured on production it turned
"13 improved, 0 regressed" into 4 improved, 6 regressed, 3 stuck -- the entire
apparent effect was ours. `test_a_detector_change_alone_is_not_improvement`
is the lock on that.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from datetime import datetime, timezone

from services import primary_weakness_picker as pwp


def _as_dt(value):
    """Accept a datetime, or a 'YYYY-MM-DD'/ISO string, return aware UTC."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --- a database that answers with the games and observations we specify ------

class _Games:
    """Games keyed by the canonical `played_at_utc`.

    The split moved off the legacy `date_played` string because that field
    holds three incompatible shapes and ASCII "." sorts above "-", so a
    chess.com `2026.04.15` compared as later than any ISO timestamp. This
    fake therefore stores real datetimes and refuses a `date_played` bound,
    so a regression back to string ordering fails loudly here rather than
    silently misordering a real user's window.

    `unmigrated` models rows the backfill has not reached yet, which the
    production code still splits the old way during the transition.
    """

    def __init__(self, played, unmigrated=None):
        # played: {game_id: datetime}. Plain "YYYY-MM-DD" strings are
        # accepted and coerced so the cases below stay readable.
        self.played = {g: _as_dt(v) for g, v in played.items()}
        # unmigrated: {game_id: legacy date_played string}
        self.unmigrated = unmigrated or {}

    @staticmethod
    def _select(items, bound):
        out = []
        for game_id, when in items.items():
            if "$lt" in bound and when < bound["$lt"]:
                out.append(game_id)
            elif "$gte" in bound and when >= bound["$gte"]:
                out.append(game_id)
        return out

    async def distinct(self, field, query):
        # The legacy branch carries BOTH keys: it is scoped to un-migrated
        # rows and bounded by the old string. Check it first.
        if "date_played" in query:
            assert query.get("played_at_utc") == {"$exists": False}, (
                "a date_played bound is only legal for un-migrated rows; "
                "the canonical split must use played_at_utc"
            )
            return self._select(self.unmigrated, query["date_played"])

        if "played_at_utc" in query:
            bound = query["played_at_utc"]
            if bound == {"$exists": False}:
                return list(self.unmigrated)
            return self._select(self.played, bound)

        raise AssertionError(f"unexpected games query: {query}")

    async def count_documents(self, query):
        if query.get("played_at_utc") == {"$exists": False}:
            return len(self.unmigrated)
        return len(self.played)


class _Observations:
    def __init__(self, by_game):
        self.by_game = by_game

    async def count_documents(self, query):
        ids = query.get("game_id", {}).get("$in", [])
        return sum(self.by_game.get(g, 0) for g in ids)


class _DB:
    def __init__(self, played, observations):
        self.games = _Games(played)
        self.move_observations = _Observations(observations)


def _focus(**over):
    focus = {
        "user_id": "u1",
        "topic_key": "piece_safety",
        "started_at": "2026-06-01T00:00:00+00:00",
        "baseline_metric": {"name": "piece_safety_per_game", "value": 1.0},
    }
    focus.update(over)
    return focus


def _run(db, focus):
    return asyncio.run(pwp.check_focus_outcome(db, focus))


def _no_subtype_gate(monkeypatch):
    """The authorized-subtype gate is prod config, not what these test."""
    import services.detector_quality as dq
    monkeypatch.setattr(dq, "enforcement_enabled", lambda: False)


# --- the three wedges -------------------------------------------------------

def test_a_pic_focus_is_measured_rather_than_waved_through(monkeypatch):
    """cycle_version 1 used to short-circuit before reading anything.

    It is measured with its OWN proof detector -- a rate per piece-safety
    decision faced, which is what the focus document declares -- not with the
    generic per-game counter, which would be the wrong instrument.
    """
    async def fake_summary(db, user_id, game_ids=None):
        # before: 100 misses in 1000 decisions. after: 5 in 200.
        if game_ids and "new1" in game_ids:
            return {"decisions": 200, "misses": 5, "handled": 195}
        return {"decisions": 1000, "misses": 100, "handled": 900}

    import services.focus_bridge as fb
    monkeypatch.setattr(fb, "get_d_live_evidence_summary", fake_summary)

    db = _DB({"old1": "2026-01-01", "old2": "2026-02-01",
              "new1": "2026-07-01", "new2": "2026-07-02", "new3": "2026-07-03"},
             {})
    outcome = _run(db, _focus(cycle_version=1))

    assert outcome["resolution"] != "measurement_pending"
    assert outcome["current_metric"] is not None
    assert outcome["current_metric"]["name"] == "piece_safety_misses_per_decision"
    # 10% -> 2.5% is a 75% fall.
    assert outcome["resolution"] == "improved"
    assert outcome["delta_pct"] == -75.0


def test_the_window_is_when_games_were_played_not_when_we_analysed_them(
    monkeypatch
):
    """`analyzed_at` is not the same axis as `date_played`.

    On production the median game is analysed 19 days after it was played and
    42% more than 30 days after, so an `analyzed_at` window sweeps in games
    played long BEFORE the coaching started and calls them evidence of it.
    This asserts the split is made on play date: the two pre-focus games must
    land in the baseline half, where they lower the measured improvement.
    """
    _no_subtype_gate(monkeypatch)
    db = _DB(
        {"old1": "2026-01-01", "old2": "2026-02-01",
         "new1": "2026-07-01", "new2": "2026-07-02", "new3": "2026-07-03"},
        {"old1": 10, "old2": 10, "new1": 1, "new2": 1, "new3": 1},
    )
    outcome = _run(db, _focus())
    metric = outcome["current_metric"]
    assert metric["n_games_since_start"] == 3, "only post-focus games count"
    assert metric["measured_baseline"]["n_games"] == 2
    assert metric["measured_baseline"]["value"] == 10.0
    assert metric["value"] == 1.0


def test_a_focus_with_no_type_field_is_still_a_weakness_focus():
    """The daily loop's selector must not drop rows written before `type`."""
    import re
    server = (BACKEND / "server.py").read_text(encoding="utf-8")
    loop = server[server.index("async def focus_outcome_loop"):]
    loop = loop[:loop.index("async def", 10)] if "async def" in loop[10:] else loop
    assert '"type": "weakness", "status": "active"' not in loop, (
        "an equality match on `type` silently skips every legacy focus"
    )
    assert re.search(r'\{"type": \{"\$exists": False\}\}', loop), (
        "the loop must select focuses that predate the `type` field"
    )


# --- the one that would have produced a WRONG answer ------------------------

def test_a_detector_change_alone_is_not_improvement(monkeypatch):
    """The player is identical before and after; only our counting changed.

    The stored baseline says 5.0 per game because that is what the detector
    reported when the focus was locked. Today's detector reports 1.0 per game
    on the very same pre-focus games. If the check differenced against the
    stored number it would announce an 80% improvement for a player whose
    behaviour is identical on both sides of the split. Re-deriving the before
    half with today's counter is what makes it say "stuck" instead.
    """
    _no_subtype_gate(monkeypatch)
    db = _DB(
        {"old1": "2026-01-01", "old2": "2026-02-01",
         "new1": "2026-07-01", "new2": "2026-07-02", "new3": "2026-07-03"},
        # Exactly one event per game, on both sides of the split. Nothing
        # about this player changed.
        {"old1": 1, "old2": 1, "new1": 1, "new2": 1, "new3": 1},
    )
    outcome = _run(db, _focus(baseline_metric={
        "name": "piece_safety_per_game", "value": 5.0,
    }))
    assert outcome["resolution"] == "stuck", outcome
    assert outcome["delta_pct"] == 0.0, outcome
    # The stored number is kept, but only as provenance.
    assert outcome["current_metric"]["stored_baseline"]["value"] == 5.0
    assert outcome["current_metric"]["measured_baseline"]["value"] == 1.0
    assert outcome["current_metric"]["value"] == 1.0


# --- silence, where silence is the true answer ------------------------------

def test_too_few_games_is_no_data_not_a_verdict(monkeypatch):
    _no_subtype_gate(monkeypatch)
    db = _DB({"old1": "2026-01-01", "new1": "2026-07-01"}, {"old1": 5})
    outcome = _run(db, _focus())
    assert outcome["resolution"] == "no_data"
    assert outcome["current_metric"] is None
    assert outcome["action"] == "extend", "the focus stays open"


def test_too_few_decisions_is_pending_not_stuck(monkeypatch):
    """A PIC focus with a handful of decisions has not been measured.

    Returning "stuck" there would be a statement about the player made from
    an absence of evidence.
    """
    async def thin(db, user_id, game_ids=None):
        return {"decisions": 4, "misses": 1, "handled": 3}

    import services.focus_bridge as fb
    monkeypatch.setattr(fb, "get_d_live_evidence_summary", thin)
    db = _DB({"old1": "2026-01-01",
              "new1": "2026-07-01", "new2": "2026-07-02", "new3": "2026-07-03"},
             {})
    outcome = _run(db, _focus(cycle_version=1))
    assert outcome["resolution"] == "measurement_pending"
    assert outcome["current_metric"] is None


def test_a_focus_with_no_start_date_is_never_guessed_at():
    db = _DB({"g1": "2026-07-01"}, {"g1": 1})
    outcome = _run(db, _focus(started_at=None))
    assert outcome["resolution"] == "measurement_pending"
    assert outcome["current_metric"] is None


def test_a_real_regression_is_reported_as_one(monkeypatch):
    """Improvement and regression run through the same arithmetic.

    Measured on production this fires for 6 of the 13 measurable focuses. A
    check that can only ever say "improved" is not a measurement.
    """
    _no_subtype_gate(monkeypatch)
    db = _DB(
        {"old1": "2026-01-01", "old2": "2026-02-01",
         "new1": "2026-07-01", "new2": "2026-07-02", "new3": "2026-07-03"},
        {"old1": 1, "old2": 1, "new1": 3, "new2": 3, "new3": 3},
    )
    outcome = _run(db, _focus())
    assert outcome["resolution"] == "regressed"
    assert outcome["delta_pct"] == 200.0


# --- the ordering defect that made every window untrustworthy ---------------

def test_a_dotted_chesscom_date_does_not_land_in_the_after_window(monkeypatch):
    """The production defect, pinned.

    `date_played` held ISO timestamps for most games and chess.com's dotted
    `2026.04.15` for 477 of them. Compared as strings, "." (0x2E) sorts above
    "-" (0x2D), so every dotted value landed after every ISO timestamp no
    matter what date it named. On 2026-09-16 that put 407 games into 15
    focuses' "after" windows; for six users *every* "after" game predated the
    focus by months, so the loop would have reported a change measured
    against games played before the coaching started.

    Splitting on a real datetime cannot reproduce it.
    """
    _no_subtype_gate(monkeypatch)
    april = datetime(2026, 4, 15, 5, 45, 33, tzinfo=timezone.utc)   # was "2026.04.15"
    db = _DB(
        {"april_game": april,
         "new1": "2026-07-01", "new2": "2026-07-02", "new3": "2026-07-03"},
        {"april_game": 40, "new1": 40, "new2": 40, "new3": 40},
    )
    before, after = asyncio.run(
        pwp._games_split_by_play_date(db, "u1", "2026-06-01T00:00:00+00:00")
    )
    assert "april_game" in before, "an April game belongs before a June focus"
    assert "april_game" not in after
    assert sorted(after) == ["new1", "new2", "new3"]


def test_string_ordering_would_have_got_this_wrong():
    """Guards the claim above rather than trusting the prose."""
    assert "2026.04.15" > "2026-06-01T00:00:00+00:00"


def test_unmigrated_rows_are_still_counted_during_the_transition(monkeypatch):
    """Deploying the canonical reader before the backfill runs must not make
    a user's games vanish from both halves of the window."""
    _no_subtype_gate(monkeypatch)
    db = _DB({"new1": "2026-07-01", "new2": "2026-07-02"},
             {"new1": 40, "new2": 40, "legacy_old": 40})
    db.games.unmigrated = {"legacy_old": "2026-01-01"}
    before, after = asyncio.run(
        pwp._games_split_by_play_date(db, "u1", "2026-06-01T00:00:00+00:00")
    )
    assert "legacy_old" in before
    assert sorted(after) == ["new1", "new2"]

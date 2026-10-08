"""The milestone chain. docs/progress_then_and_now_scope.md

Every test here is a thing the production data actually did, not a shape I
imagined:

  * 2026-09-21 wrote 32 observations with `metric_name: None` and deltas of
    +97%, +236%, +382%, +473%
  * `piece_safety_misses_per_decision` is a per-decision rate while
    `king_safety_per_game` is per-game, so two valid readings can be on
    different scales
  * one player was shown 9 rows, 7 of them our own migrations repeating the
    same sentence on the same day
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import progress_chain as chain  # noqa: E402


def obs(day, resolution, metric="piece_safety_misses_per_decision", delta=-20.0):
    # `user_id` is included because build_chain filters the shadow query on it;
    # leaving it out made four tests fail against correct code.
    return {"observed_on": day, "resolution": resolution, "user_id": "u",
            "metric_name": metric, "delta_pct": delta}


# ----------------------------------------------------------- the verdict rule

def test_one_observation_is_never_a_verdict():
    """A coach does not revise his assessment because of one session."""
    assert chain.settled_verdict([obs("2026-10-01", "improved")]) is None


def test_two_agreeing_observations_settle_it():
    out = chain.settled_verdict([obs("2026-10-01", "improved"),
                                 obs("2026-10-02", "improved")])
    assert out["verdict"] == "improved"
    assert out["words"] == "this got better"
    assert out["observations"] == 2


def test_a_disagreement_in_the_recent_readings_settles_nothing():
    """The honest answer is "still watching", not whichever came last."""
    assert chain.settled_verdict([obs("2026-10-01", "improved"),
                                  obs("2026-10-02", "regressed")]) is None


def test_the_single_bad_day_cannot_flip_a_settled_verdict():
    """The real series from user_c90a2ac2ad02: steady -29%, one +97.4 spike on
    2026-09-21, then steady again. Seventeen of the eighteen outlier readings
    in the whole dataset fall on that one day."""
    series = ([obs("2026-09-%02d" % d, "improved", delta=-29.0)
               for d in range(17, 21)]
              + [obs("2026-09-21", "regressed", delta=97.4)]
              + [obs("2026-09-%02d" % d, "improved", delta=-29.0)
                 for d in range(22, 28)])
    out = chain.settled_verdict(series)
    assert out["verdict"] == "improved", "a one-day artefact must not win"


def test_readings_on_a_different_metric_are_not_mixed_in():
    """`..._misses_per_decision` is a per-DECISION rate and `..._per_game` is
    per-GAME. Chaining across them compares different scales, which is how a
    +473% delta gets written down as if it meant something."""
    series = [obs("2026-10-01", "improved"),
              obs("2026-10-02", "improved"),
              obs("2026-10-03", "regressed", metric="king_safety_per_game")]
    out = chain.settled_verdict(series)
    assert out["verdict"] == "improved"
    assert out["metric_name"] == "piece_safety_misses_per_decision"


def test_an_observation_with_no_metric_name_is_discarded():
    """Every one of the 32 observations on 2026-09-21 had metric_name None.
    A reading with no metric identity cannot be compared to anything."""
    series = [obs("2026-09-21", "regressed", metric=None, delta=473.2),
              obs("2026-09-22", "regressed", metric=None, delta=382.3)]
    assert chain.settled_verdict(series) is None


def test_a_verdict_without_a_delta_is_not_usable():
    assert chain.settled_verdict([obs("2026-10-01", "improved", delta=None),
                                  obs("2026-10-02", "improved", delta=None)]) is None


def test_measurement_pending_and_no_data_are_not_verdicts():
    for non_verdict in ("no_data", "measurement_pending", "metric_gap", None):
        series = [obs("2026-10-01", non_verdict), obs("2026-10-02", non_verdict)]
        assert chain.settled_verdict(series) is None, non_verdict


# ------------------------------------------------------------------ the words

def test_no_verdict_or_topic_phrase_contains_a_number():
    """The deltas are real -- median 39% -- and still never rendered. "You are
    29% better at piece safety" is not usable by a 1200 player."""
    import re
    digit = re.compile(r"\d")
    for text in list(chain.VERDICT_WORDS.values()) + list(chain.TOPIC_WORDS.values()):
        assert not digit.search(text), text


def test_stuck_is_not_said_as_stuck():
    """A label for us, not a thing to tell someone."""
    assert "stuck" not in chain.VERDICT_WORDS["stuck"].lower()
    assert chain.VERDICT_WORDS["stuck"] == "this did not move"


def test_an_unauthored_topic_gets_no_row_rather_than_a_raw_key():
    """Printing `tactical_oversight` is how a reader learns they are reading a
    dashboard."""
    assert chain.topic_words("some_new_topic") is None
    assert chain.topic_words(None) is None
    assert chain.topic_words("piece_safety")


# ------------------------------------------------- the chain, on a fake db

class _Cursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def __aiter__(self):
        async def gen():
            for r in self._rows:
                yield r
        return gen()

    async def to_list(self, _n=None):
        return list(self._rows)


class _Coll:
    def __init__(self, rows):
        self._rows = rows

    def find(self, query, projection=None):
        def ok(row):
            for k, v in query.items():
                if isinstance(v, dict) and "$ne" in v:
                    if row.get(k) == v["$ne"]:
                        return False
                elif row.get(k) != v:
                    return False
            return True
        return _Cursor([r for r in self._rows if ok(r)])


class _DB:
    def __init__(self, focuses, observations):
        self._c = {chain.FOCUSES: _Coll(focuses), chain.SHADOW: _Coll(observations)}

    def __getitem__(self, name):
        return self._c[name]


@pytest.mark.asyncio
async def test_a_focus_nothing_was_ever_measured_against_is_not_a_cycle():
    """One player was shown NINE rows, seven of them dated 2026-07-01/02 and
    all repeating the same sentence -- `superseded_v6` through `v9`, our own
    migrations rewriting a single focus.

    The filter is evidence rather than a status whitelist: measured 2026-10-08,
    those four statuses hold 163 rows with ZERO observations between them,
    while active (53/53), completed (2/2) and escalated (1/1) are fully
    observed. A status list would also rot at the next migration.
    """
    focuses = [
        {"_id": "ghost", "user_id": "u", "topic_key": "piece_safety", "status": "superseded_v7",
         "started_at": "2026-07-02"},
        {"_id": "real", "user_id": "u", "topic_key": "piece_safety", "status": "active",
         "started_at": "2026-09-11"},
    ]
    observations = [dict(obs("2026-10-0%d" % d, "improved"), focus_id="real")
                    for d in (1, 2)]
    out = await chain.build_chain(_DB(focuses, observations), "u")
    assert [c["topic"] for c in out["cycles"]] == ["piece_safety"]
    assert out["cycles"][0]["settled"]["verdict"] == "improved"


@pytest.mark.asyncio
async def test_cycles_read_oldest_first_and_the_current_one_is_marked():
    focuses = [
        {"_id": "b", "user_id": "u", "topic_key": "king_safety", "status": "active",
         "started_at": "2026-09-26"},
        {"_id": "a", "user_id": "u", "topic_key": "piece_safety", "status": "completed",
         "started_at": "2026-09-11", "closed_at": "2026-09-25"},
    ]
    observations = (
        [dict(obs("2026-09-%02d" % d, "improved"), focus_id="a") for d in (20, 21)]
        + [dict(obs("2026-09-%02d" % d, "regressed",
                    metric="king_safety_per_game", delta=57.1), focus_id="b")
           for d in (27, 28)])
    out = await chain.build_chain(_DB(focuses, observations), "u")
    assert [c["topic"] for c in out["cycles"]] == ["piece_safety", "king_safety"]
    assert out["cycles"][0]["is_current"] is False
    assert out["cycles"][1]["is_current"] is True
    assert out["cycles"][1]["settled"]["words"] == (
        "this got worse while we worked on it")


@pytest.mark.asyncio
async def test_an_unsettled_current_cycle_still_appears():
    """"We are on this now" is part of the story. Dropping it would turn the
    chain into a trophy cabinet."""
    focuses = [{"_id": "a", "user_id": "u", "topic_key": "piece_safety", "status": "active",
                "started_at": "2026-10-07"}]
    observations = [dict(obs("2026-10-07", "no_data"), focus_id="a")]
    out = await chain.build_chain(_DB(focuses, observations), "u")
    assert len(out["cycles"]) == 1
    assert out["cycles"][0]["settled"] is None
    assert out["measured"] is False


@pytest.mark.asyncio
async def test_the_stored_resolution_is_carried_but_never_used_as_the_verdict():
    """It was written by whatever the detector looked like at the time.
    Differencing against stored values turned 13 improved / 0 regressed into
    4 / 3 / 6 when the before half was re-derived with current code."""
    focuses = [{"_id": "a", "user_id": "u", "topic_key": "piece_safety", "status": "active",
                "started_at": "2026-09-11", "resolution": "improved"}]
    observations = [dict(obs("2026-10-0%d" % d, "stuck"), focus_id="a")
                    for d in (1, 2)]
    out = await chain.build_chain(_DB(focuses, observations), "u")
    cycle = out["cycles"][0]
    assert cycle["stored_resolution"] == "improved"
    assert cycle["settled"]["verdict"] == "stuck", "the measurement wins"

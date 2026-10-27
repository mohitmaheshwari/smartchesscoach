"""Connecting the games: "we looked at this in an earlier game".

Mohit 2026-10-27: "have we coached him on this and asked to correct, you
know like he reviewed this game, we taught him that this was an issue,
so games should be connected, are you getting me, like a real coach
does."

WHY THIS READS user_pattern_events AND NOT THE OBVIOUS COLLECTION.
Measured 2026-10-27 on production:

    user_pattern_events            142,392 rows, every one with game_id,
                                   move_number, pattern_id and outcome
                                   (5,372 of them Mohit's)
    user_concept_understanding     5,355 rows, but shown_games holds 39
                                   entries across Mohit's 916 games and
                                   shown_count is a RENDER counter --
                                   32,807 on a concept whose shown_games
                                   names 10 games

So the ledger that looks built is empty, and the one that can answer the
question is full. pattern_id is also the vocabulary
data/pattern_catalog.json bridges to concept ids, so nothing new is
mapped. The move row's own `cognitive_gap` cannot do this job: it has six
values for this user against dozens of pattern ids.

THE TWO RULES THIS FILE HOLDS

  NO SCOREBOARD. The facts are booleans. "We looked at this in an earlier
  game" is a coach's sentence; "your 7th time" is a tally, and this
  product does not show one.

  NEVER ITS OWN GAME. The history query excludes the game being analysed.
  Without that every card would report having seen itself before, which
  is the failure this test exists to catch.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import reader_context as rc  # noqa: E402


class _Cursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def sort(self, key, direction=1):
        self._rows.sort(key=lambda r: r.get(key) or "",
                        reverse=(direction == -1))
        return self

    def __iter__(self):
        return iter(self._rows)


class _Events:
    """Just enough of a collection to answer the two queries gather makes."""

    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def find(self, query, projection=None):
        self.queries.append(query)
        out = []
        for r in self.rows:
            if r.get("user_id") != query.get("user_id"):
                continue
            gq = query.get("game_id")
            if isinstance(gq, dict):
                if "$ne" in gq and r.get("game_id") == gq["$ne"]:
                    continue
            elif gq is not None and r.get("game_id") != gq:
                continue
            pq = query.get("pattern_id")
            if isinstance(pq, dict) and "$in" in pq:
                if r.get("pattern_id") not in pq["$in"]:
                    continue
            out.append(dict(r))
        return _Cursor(out)

    def distinct(self, field, query=None):
        return []


class _DB:
    def __init__(self, events):
        self.user_pattern_events = events
        self.user_pattern_decay = _Missing()
        self.puzzle_attempts = _Missing()

    def __getitem__(self, name):
        raise KeyError(name)


class _Missing:
    def find_one(self, *a, **k):
        return {}

    def distinct(self, *a, **k):
        return []


U = "user_x"
NOW, PAST, OLDER = "2026-10-20", "2026-09-01", "2026-08-01"

ROWS = [
    # the game being analysed
    {"user_id": U, "game_id": "g_now", "move_number": 11,
     "pattern_id": "knight_on_rim", "outcome": "miss", "created_at": NOW},
    {"user_id": U, "game_id": "g_now", "move_number": 19,
     "pattern_id": "back_rank_weakness", "outcome": "miss", "created_at": NOW},
    # earlier games
    {"user_id": U, "game_id": "g_old", "move_number": 7,
     "pattern_id": "knight_on_rim", "outcome": "miss", "created_at": PAST},
    {"user_id": U, "game_id": "g_older", "move_number": 5,
     "pattern_id": "knight_on_rim", "outcome": "hit", "created_at": OLDER},
    # another player's history must never leak in
    {"user_id": "someone_else", "game_id": "g_other", "move_number": 3,
     "pattern_id": "back_rank_weakness", "outcome": "miss", "created_at": PAST},
]


def _ctx(rows=ROWS, game_id="g_now"):
    return rc.gather(_DB(_Events(rows)), U, [], game_id=game_id)


class TestTheHistoryExcludesTheGameBeingAnalysed:
    def test_a_pattern_seen_in_an_earlier_game_is_reported(self):
        got = rc.for_move(_ctx(), {"move_number": 11})
        assert got["we_flagged_this_in_an_earlier_game"] is True

    def test_a_pattern_seen_only_in_this_game_is_not(self):
        """back_rank_weakness appears once, in g_now. Claiming history for
        it would be the card reporting that it had seen itself."""
        got = rc.for_move(_ctx(), {"move_number": 19})
        assert "we_flagged_this_in_an_earlier_game" not in got

    def test_without_a_game_id_nothing_is_guessed(self):
        ctx = rc.gather(_DB(_Events(ROWS)), U, [])
        assert ctx["pattern_here"] == {}
        assert rc.for_move(ctx, {"move_number": 11}) == {}

    def test_another_players_history_never_leaks(self):
        rows = [r for r in ROWS if r["pattern_id"] == "back_rank_weakness"]
        got = rc.for_move(_ctx(rows), {"move_number": 19})
        assert "we_flagged_this_in_an_earlier_game" not in got


class TestWhatHappenedLastTime:
    def test_the_latest_earlier_outcome_wins_not_the_oldest(self):
        """g_old (September, a miss) is later than g_older (August, a hit).
        A coach refers to the last time, so the sort must be by date and
        the newest earlier row is the one that speaks."""
        got = rc.for_move(_ctx(), {"move_number": 11})
        assert got["they_missed_it_last_time_too"] is True
        assert "they_got_it_right_last_time" not in got

    def test_a_past_success_is_carried_because_it_is_good_news(self):
        rows = [r for r in ROWS if r["game_id"] != "g_old"]
        got = rc.for_move(_ctx(rows), {"move_number": 11})
        assert got["they_got_it_right_last_time"] is True
        assert "they_missed_it_last_time_too" not in got


class TestNoScoreboard:
    def test_no_field_carries_a_tally(self):
        """One user's missed_tactic is 157 occurrences. No field may say so."""
        got = rc.for_move(_ctx(), {"move_number": 11})
        for key, value in got.items():
            assert "count" not in key, key
            assert "times" not in key, key
            assert not isinstance(value, int) or isinstance(value, bool), key

    def test_the_facts_are_booleans(self):
        got = rc.for_move(_ctx(), {"move_number": 11})
        assert got["we_flagged_this_in_an_earlier_game"] is True
        assert got["they_missed_it_last_time_too"] is True


class TestItNeverRaises:
    def test_a_broken_collection_degrades_to_no_facts(self):
        class _Boom:
            def find(self, *a, **k):
                raise RuntimeError("no index")

            def distinct(self, *a, **k):
                return []

        ctx = rc.gather(_DB(_Boom()), U, [], game_id="g_now")
        assert ctx["pattern_here"] == {}
        assert rc.for_move(ctx, {"move_number": 11}) == {}

    def test_a_move_with_no_number_is_silent(self):
        assert rc.for_move(_ctx(), {}) == {}

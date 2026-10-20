"""The stuck-job reaper must reset the row it found, not another one.

`cleanup_stuck_jobs` reads stuck rows with a cursor and then wrote them back
with `update_one({"game_id": ...})`. `analysis_queue` is not unique on
game_id, so when a game had two rows the reaper reset whichever matched first
-- usually the wrong one.

Measured on production 2026-10-20, game 56b6c294 held:

    _id=eebe8f  status=pending     heartbeat None   retry_count 7623
    _id=1652a5  status=processing   heartbeat 02:45  retry_count None

The reaper logged "Found stuck job" and "Reset stuck job" on every worker
start, incremented the pending row's counter past seven thousand, and never
touched the row that was actually stuck. Deploy check 6 failed on a stale
heartbeat that no restart could clear, which is how this surfaced at all.

A fake collection is used rather than mongomock so the test states exactly
which selector reached the driver -- that selector IS the bug.
"""
from datetime import datetime, timedelta, timezone

import analysis_worker


class FakeCursor:
    """Just enough cursor: the function chains .limit() and .sort()."""

    def __init__(self, rows):
        self._rows = list(rows)

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def sort(self, *_args, **_kwargs):
        return self

    def __iter__(self):
        return iter(self._rows)


class FakeCollection:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def find(self, query=None, *_a, **_kw):
        # Only the stale-processing read matters here. The later auto-retry
        # pass looks for status="failed" and must find nothing, or it would
        # write rows this test has no opinion about.
        wanted = (query or {}).get("status")
        if wanted == "processing" or wanted is None:
            return FakeCursor(
                r for r in self.rows if r.get("status") == "processing")
        return FakeCursor([])

    def update_one(self, selector, update, **_kw):
        self.updates.append((selector, update))

    def count_documents(self, _query=None, **_kw):
        return len(self.rows)


class FakeDB:
    def __init__(self, queue_rows):
        self.analysis_queue = FakeCollection(queue_rows)
        self.games = FakeCollection([])

    def __getitem__(self, name):
        return getattr(self, name)


def two_rows_for_one_game():
    stale = datetime.now(timezone.utc) - timedelta(hours=11)
    return [
        {"_id": "eebe8f", "game_id": "g1", "status": "pending",
         "last_heartbeat": None, "retry_count": 7623},
        {"_id": "1652a5", "game_id": "g1", "status": "processing",
         "last_heartbeat": stale, "started_at": stale, "worker_id": "worker-1"},
    ]


class TestReaperTargetsTheStuckRow:
    def test_the_reset_names_the_stuck_row_by_id(self):
        db = FakeDB(two_rows_for_one_game())
        analysis_worker.cleanup_stuck_jobs(db)

        queue_writes = [s for s, _ in db.analysis_queue.updates]
        assert queue_writes, "the reaper wrote nothing for a stale row"
        assert {"_id": "1652a5"} in queue_writes, (
            f"reset did not target the stuck row; selectors were {queue_writes}"
        )

    def test_it_never_selects_by_game_id_alone(self):
        """The precise defect. A game_id selector is ambiguous by construction.

        This fails against the original code, which is the point: a test that
        only checked "something was reset" passed throughout the 7,623
        mis-resets.
        """
        db = FakeDB(two_rows_for_one_game())
        analysis_worker.cleanup_stuck_jobs(db)

        for selector, _update in db.analysis_queue.updates:
            assert "_id" in selector, (
                f"queue write selected by {sorted(selector)} -- with two rows "
                "per game that can reset the wrong one"
            )

    def test_the_other_row_is_left_alone(self):
        db = FakeDB(two_rows_for_one_game())
        analysis_worker.cleanup_stuck_jobs(db)

        touched = {s.get("_id") for s, _ in db.analysis_queue.updates}
        assert "eebe8f" not in touched, (
            "the pending row was updated; that is what inflated retry_count "
            "to 7623 while the stuck row stayed stuck"
        )

    def test_the_games_row_may_still_be_keyed_by_game_id(self):
        """Deliberate asymmetry, so a future reader does not 'fix' it.

        `games` is one document per game, so game_id is the right key there.
        Only `analysis_queue` carries more than one row per game.
        """
        db = FakeDB(two_rows_for_one_game())
        analysis_worker.cleanup_stuck_jobs(db)
        assert all("game_id" in s for s, _ in db.games.updates)

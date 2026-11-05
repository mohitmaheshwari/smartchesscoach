"""A short game is not a failed analysis.

On 2026-11-04/05 all six "failed" analysis jobs were real games of 0-7 plies:
abandoned daily games, a resignation, a mate in four. The analysis had covered
every move the user made in each one; the worker failed them on a fixed
"fewer than 5 moves" floor, and the deploy gate read them as a failure spike.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import analysis_worker as worker  # noqa: E402

MATE_IN_FOUR = '[Event "x"]\n[Result "1-0"]\n\n1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0'


def test_counts_only_the_users_moves():
    assert worker.user_move_count(MATE_IN_FOUR, "black") == 3
    assert worker.user_move_count(MATE_IN_FOUR, "white") == 4


def test_a_game_with_no_moves_has_none():
    assert worker.user_move_count('[Result "0-1"]\n\n0-1', "white") == 0
    assert worker.user_move_count('[Result "1-0"]\n\n1. e4 1-0', "black") == 0
    assert worker.user_move_count("", "white") == 0


def test_a_set_up_position_starts_from_its_own_side_to_move():
    pgn = ('[SetUp "1"]\n[FEN "4k3/8/8/8/8/8/8/4K2R b K - 0 1"]\n[Result "*"]\n\n'
           '1... Kd7 2. Rh7+ Kc6 *')
    assert worker.user_move_count(pgn, "black") == 2
    assert worker.user_move_count(pgn, "white") == 1


class _Coll:
    def __init__(self):
        self.updates = []

    def update_one(self, query, update, upsert=False):
        self.updates.append((query, update))


class _DB:
    def __init__(self):
        self.analysis_queue = _Coll()
        self.games = _Coll()


def test_skipped_is_terminal_and_never_called_failed():
    db = _DB()
    worker.mark_job_skipped(db, "g1", "no_user_moves")
    (q, u), = db.analysis_queue.updates
    assert q == {"game_id": "g1"}
    assert u["$set"]["status"] == "skipped"
    assert u["$set"]["skip_reason"] == "no_user_moves"
    assert "$inc" not in u  # no retry count: there is nothing to retry
    (_, g), = db.games.updates
    assert g["$set"]["analysis_status"] == "skipped"

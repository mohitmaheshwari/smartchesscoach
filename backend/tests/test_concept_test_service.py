"""Concept test — proof, not impressions.

docs/teaching_loop_scope.md

The load-bearing test here is `test_clean_streak_alone_never_promotes`:
that is the bug this whole feature exists to close.
"""

import os
import sys

import chess
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.concept_test_service import (  # noqa: E402
    STATE_MASTERED,
    STATE_MONITORING,
    STATE_SHOWN,
    STATE_TESTED_FAILED,
    STATE_UNDERSTOOD,
    _apply_state_transition,
    _lichess_positions,
    build_concept_test,
    canonical_concept,
    grade_concept_test,
    may_promote_to_mastered,
    should_offer_test,
    pick_concept_for_game,
)


# ── the ordering bug ──────────────────────────────────────────────────────

class TestPromotionRequiresProof:
    """A clean streak is monitoring evidence, never a route to understood."""

    @pytest.mark.parametrize("state", [None, STATE_SHOWN, STATE_TESTED_FAILED])
    def test_clean_streak_alone_never_promotes(self, state):
        # THE regression. Before 2026-09-21 a 3-game clean streak set
        # acknowledged=True and stamped mastered_at, so a concept could be
        # "mastered" because it stopped coming up, not because it was learnt.
        assert may_promote_to_mastered(state, streak_clean=3, streak_required=3) is False
        # Even an absurd streak must not rescue an unproven concept.
        assert may_promote_to_mastered(state, streak_clean=999, streak_required=3) is False

    @pytest.mark.parametrize("state", [STATE_UNDERSTOOD, STATE_MONITORING])
    def test_proven_concept_promotes_at_threshold(self, state):
        assert may_promote_to_mastered(state, 3, 3, tests_passed=1) is True
        assert may_promote_to_mastered(state, 4, 3, tests_passed=1) is True

    @pytest.mark.parametrize("state", [STATE_UNDERSTOOD, STATE_MONITORING])
    def test_proven_but_short_streak_does_not_promote(self, state):
        assert may_promote_to_mastered(state, 2, 3, tests_passed=1) is False

    @pytest.mark.parametrize("state", [STATE_UNDERSTOOD, STATE_MONITORING])
    def test_proven_state_without_a_passed_test_never_promotes(self, state):
        # Caught in production on 2026-09-21, minutes after the backfill.
        # The migration put 1,078 legacy rows into `monitoring` to keep
        # their streak history, and `monitoring` is a proven state — so on
        # a state check alone, 532 of them would have promoted straight to
        # mastered on their next clean game, having never taken a test.
        # The proof must be read explicitly, never inferred from the state.
        assert may_promote_to_mastered(state, 999, 3, tests_passed=0) is False
        assert may_promote_to_mastered(state, 999, 3) is False  # default is 0

    def test_a_passed_test_plus_a_streak_does_promote(self):
        assert may_promote_to_mastered(STATE_MONITORING, 3, 3, tests_passed=1) is True

    def test_already_mastered_does_not_re_promote(self):
        assert may_promote_to_mastered(STATE_MASTERED, 99, 3, tests_passed=1) is False


# ── the Lichess convention that would silently break every puzzle ─────────

class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield d
        return gen()


class _Collection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.written = []

    def find(self, query=None, projection=None):
        return _Cursor(self.docs)

    async def find_one(self, query, projection=None):
        return self.docs[0] if self.docs else None

    async def insert_one(self, doc):
        self.written.append(doc)
        self.docs.append(doc)
        return type("R", (), {"inserted_id": "x"})()

    async def update_one(self, query, update, upsert=False):
        self.written.append({"query": query, "update": update})
        return type("R", (), {"modified_count": 1})()


class _DB:
    def __init__(self, **collections):
        for name, coll in collections.items():
            setattr(self, name, coll)

    def __getattr__(self, name):
        coll = _Collection()
        setattr(self, name, coll)
        return coll


#: A REAL row, pulled from the production corpus (puzzle 00AdI) rather than
#: hand-written — an invented FEN silently encoded an illegal move on the
#: first attempt. The stored FEN is WHITE to move; moves[0] is white's Kh3,
#: so the solver is BLACK and sees the position after it. Answer is Rd3+.
LICHESS_ROW = {
    "puzzle_id": "00AdI",
    "fen": "3r4/4kp1p/1PQ1p1p1/p3b3/1p2P2P/1P6/6PK/8 w - - 1 36",
    "moves": ["h2h3", "d8d3"],
    "rating": 1264,
    "themes": ["crushing", "discoveredAttack", "discoveredCheck",
               "endgame", "long", "master"],
    "popularity": 97,
}


class TestLichessConvention:
    @pytest.mark.asyncio
    async def test_served_position_is_after_the_opponent_move(self):
        # Serving the stored FEN as-is shows the wrong position with the
        # user on the wrong colour — and fails silently, because that
        # position is perfectly legal.
        db = _DB(lichess_puzzles=_Collection([LICHESS_ROW]))
        out = await _lichess_positions(db, "TAC_DISCOVERED_PATTERN", 1264, 5, set())
        assert len(out) == 1
        served = out[0]

        assert served["fen"] != LICHESS_ROW["fen"], "stored fen served raw"

        expected = chess.Board(LICHESS_ROW["fen"])
        expected.push(chess.Move.from_uci(LICHESS_ROW["moves"][0]))
        assert served["fen"] == expected.fen()

        # The side to move flipped: the opponent moved, now it is the user.
        assert served["side_to_move"] == "black"
        assert chess.Board(LICHESS_ROW["fen"]).turn is chess.WHITE

    @pytest.mark.asyncio
    async def test_answer_is_moves_index_one_and_is_legal(self):
        db = _DB(lichess_puzzles=_Collection([LICHESS_ROW]))
        served = (await _lichess_positions(db, "TAC_DISCOVERED_PATTERN", 1264, 5, set()))[0]
        assert served["solution_uci"] == LICHESS_ROW["moves"][1]
        board = chess.Board(served["fen"])
        assert chess.Move.from_uci(served["solution_uci"]) in board.legal_moves
        assert served["solution_san"] == "Rd3+"

    @pytest.mark.asyncio
    async def test_unmapped_positional_concept_gets_no_lichess_positions(self):
        # There is no Lichess theme for "you moved a piece that was already
        # doing a job". Returning something here would serve a confident,
        # irrelevant puzzle — worse than returning nothing.
        db = _DB(lichess_puzzles=_Collection([LICHESS_ROW]))
        assert await _lichess_positions(db, "same_piece_better_square", 1264, 5, set()) == []


# ── state transitions ─────────────────────────────────────────────────────

class TestStateTransitions:
    @pytest.mark.asyncio
    async def test_failing_lands_in_tested_failed_and_clears_acknowledged(self):
        db = _DB()
        state = await _apply_state_transition(
            db, "u1", "queen_fork", passed=False, promotes=False,
        )
        assert state == STATE_TESTED_FAILED
        written = db.user_concept_understanding.written[-1]["update"]["$set"]
        assert written["acknowledged"] is False

    @pytest.mark.asyncio
    async def test_calibrated_pass_enters_monitoring(self):
        db = _DB()
        state = await _apply_state_transition(
            db, "u1", "queen_fork", passed=True, promotes=True,
        )
        assert state == STATE_MONITORING
        written = db.user_concept_understanding.written[-1]["update"]["$set"]
        assert written["acknowledged"] is True
        # The monitoring streak starts fresh at the moment of proof.
        assert written["streak_clean"] == 0

    @pytest.mark.asyncio
    async def test_uncalibrated_pass_is_recorded_but_does_not_promote(self):
        # He passed, and we tell him so. But we do not yet know what a
        # passing score means on uncalibrated positions, so the state
        # machine holds until the first cohort is reviewed.
        db = _DB()
        state = await _apply_state_transition(
            db, "u1", "same_piece_better_square", passed=True, promotes=False,
        )
        assert state == STATE_SHOWN
        written = db.user_concept_understanding.written[-1]["update"]["$set"]
        assert "acknowledged" not in written
        assert "last_test_passed_unpromoted_at" in written


# ── offering ──────────────────────────────────────────────────────────────

class TestOffering:
    @pytest.mark.asyncio
    async def test_offered_when_never_seen(self):
        db = _DB(user_concept_understanding=_Collection([]))
        assert await should_offer_test(db, "u1", "queen_fork") is True

    @pytest.mark.asyncio
    async def test_not_offered_once_proven(self):
        db = _DB(user_concept_understanding=_Collection([{"state": STATE_MONITORING}]))
        assert await should_offer_test(db, "u1", "queen_fork") is False

    @pytest.mark.asyncio
    async def test_stops_asking_after_two_declines(self):
        # "Not now" is a first-class answer, not a failure — but we do not
        # nag. Two declines and we stop offering.
        db = _DB(user_concept_understanding=_Collection(
            [{"state": STATE_SHOWN, "tests_declined": 2}]))
        assert await should_offer_test(db, "u1", "queen_fork") is False


# ── aliases ───────────────────────────────────────────────────────────────

def test_opening_prefixed_duplicates_fold_into_their_siblings():
    # 2 and 4 in-band positions respectively — too thin to test on their
    # own, and they mean the same thing as the concepts they mirror.
    assert canonical_concept("OP_KNIGHT_ON_RIM") == "knight_on_rim"
    assert canonical_concept("OP_SAME_PIECE_TWICE") == "same_piece_better_square"
    assert canonical_concept("queen_fork") == "queen_fork"


# ── the mapping ───────────────────────────────────────────────────────────

class TestThemeMapping:
    def test_tactical_detector_concepts_reach_lichess(self):
        from services.coaching_puzzle_service import WEAKNESS_TO_PUZZLE_THEMES
        for concept, expected in [
            ("queen_fork", "fork"),
            ("TAC_FORK_PATTERN", "fork"),
            ("TAC_DISCOVERED_PATTERN", "discoveredAttack"),
            ("clearance_then_check", "clearance"),
            ("trap_punishment", "trappedPiece"),
            ("stop_opp_pawn", "advancedPawn"),
            ("king_pawn_lifted", "exposedKing"),
        ]:
            assert expected in WEAKNESS_TO_PUZZLE_THEMES.get(concept, []), concept

    def test_positional_concepts_are_deliberately_absent(self):
        # Lichess puzzles are tactical. Mapping these to a near-enough
        # theme would serve a confident, irrelevant puzzle.
        from services.coaching_puzzle_service import WEAKNESS_TO_PUZZLE_THEMES
        for concept in [
            "same_piece_better_square", "knight_outpost", "pawn_kicks_piece",
            "attack_with_tempo", "knight_on_rim", "un_developing",
            "blocked_own_pawn",
        ]:
            assert concept not in WEAKNESS_TO_PUZZLE_THEMES, concept


# ── the answer must not ship to the browser ───────────────────────────────

class TestSolutionsStaySeverSide:
    @pytest.mark.asyncio
    async def test_payload_carries_no_solution(self):
        db = _DB(
            lichess_puzzles=_Collection([LICHESS_ROW]),
            concept_test_results=_Collection([]),
        )
        out = await build_concept_test(db, "u1", "TAC_DISCOVERED_PATTERN", rating=1264)
        assert out["available"] is True
        for pos in out["positions"]:
            assert "solution_uci" not in pos
            assert "solution_san" not in pos
        # ...but it is stored, so grading has something to check against.
        stored = db.concept_tests.written[-1]
        assert stored["positions"][0]["solution_uci"] == LICHESS_ROW["moves"][1]


# ── which concept did this game teach? ────────────────────────────────────

class _SortRecordingCursor(_Cursor):
    """Records the sort it was asked for.

    The shared _Cursor accepts .sort() and ignores it, so a test that fed
    unsorted docs and checked the winner would pass whatever the service
    asked the database for. Ordering is the DB's job; what this code is
    responsible for is ASKING for it, so that is what gets asserted.
    """

    def __init__(self, docs, log):
        super().__init__(docs)
        self.log = log

    def sort(self, *args, **kwargs):
        self.log.append(args)
        return self


class _EventsCollection(_Collection):
    def __init__(self, docs=None):
        super().__init__(docs)
        self.sorts = []

    def find(self, query=None, projection=None):
        self.queries = getattr(self, "queries", [])
        self.queries.append(query)
        return _SortRecordingCursor(self.docs, self.sorts)


def _events(*rows):
    return _EventsCollection(list(rows))


def _row(concept, cp, move=10):
    return {"concept_id": concept, "cp_loss": cp, "move_number": move}


class TestTestableConceptForGame:
    """The proof step never appeared because it read a retired field.

    concept_id on a stored review card was hardcoded to None on 2026-05-11
    and ConceptTestCard was built against it in September — measured null on
    all 16,292 cards. The concept comes from the detector event log instead.
    """

    @pytest.mark.asyncio
    async def test_returns_the_concept_the_game_taught(self):
        db = _DB(
            user_pattern_events=_events(_row("knight_outpost", 240)),
            user_concept_understanding=_Collection(),
        )
        got = await pick_concept_for_game(db, "u1", "g1")
        assert got["concept_id"] == "knight_outpost"
        assert got["cp_loss"] == 240

    @pytest.mark.asyncio
    async def test_asks_the_database_for_the_biggest_mistake_first(self):
        # If a game taught several things, the one that cost the most is the
        # one worth proving he understood.
        events = _events(_row("a", 400), _row("b", 90))
        db = _DB(user_pattern_events=events,
                 user_concept_understanding=_Collection())
        await pick_concept_for_game(db, "u1", "g1")
        assert ("cp_loss", -1) in events.sorts

    @pytest.mark.asyncio
    async def test_scopes_the_query_to_this_user_and_this_game(self):
        # Without both, a user would be offered a test for someone else's
        # mistake, or for a game he is not looking at.
        events = _events(_row("x", 100))
        db = _DB(user_pattern_events=events,
                 user_concept_understanding=_Collection())
        await pick_concept_for_game(db, "u1", "g1")
        q = events.queries[0]
        assert q["user_id"] == "u1"
        assert q["game_id"] == "g1"
        assert q["outcome"] == "miss"

    @pytest.mark.asyncio
    async def test_skips_a_concept_he_has_already_proven(self):
        # should_offer_test reads user_concept_understanding; a row in a
        # proven state means do not offer. Skipping here rather than offering
        # and being refused one call later.
        db = _DB(
            user_pattern_events=_events(_row("already_known", 300)),
            user_concept_understanding=_Collection(
                [{"state": STATE_UNDERSTOOD, "tests_declined": 0}]
            ),
        )
        assert await pick_concept_for_game(db, "u1", "g1") is None

    @pytest.mark.asyncio
    async def test_a_game_that_taught_nothing_returns_none(self):
        # The ordinary case on about half of reviews, not an error.
        db = _DB(user_pattern_events=_events(),
                 user_concept_understanding=_Collection())
        assert await pick_concept_for_game(db, "u1", "g1") is None

    @pytest.mark.asyncio
    async def test_blank_rows_are_not_offered_as_a_concept(self):
        # The field being present is not the same as it having a value —
        # which is the exact shape of the bug this replaces.
        db = _DB(
            user_pattern_events=_events(
                {"concept_id": "", "cp_loss": 500},
                {"concept_id": None, "cp_loss": 400},
                _row("real_one", 120),
            ),
            user_concept_understanding=_Collection(),
        )
        got = await pick_concept_for_game(db, "u1", "g1")
        assert got["concept_id"] == "real_one"

    @pytest.mark.asyncio
    async def test_missing_ids_never_hit_the_database(self):
        db = _DB(user_pattern_events=_events(_row("x", 100)),
                 user_concept_understanding=_Collection())
        assert await pick_concept_for_game(db, "", "g1") is None
        assert await pick_concept_for_game(db, "u1", "") is None
        assert not getattr(db.user_pattern_events, "queries", [])

import pytest

from services.coaching_puzzle_service import CoachingPuzzleService


FEN = "3rk3/8/8/8/8/8/8/3QK3 w - - 0 1"
PGN = f'''[Event "Exact focus"]
[SetUp "1"]
[FEN "{FEN}"]
[Result "*"]

1. Qd5 Rxd5 *
'''


class _Cursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def sort(self, *_args):
        return self

    def limit(self, size):
        self.rows = self.rows[:size]
        return self

    async def to_list(self, length=None):
        return list(self.rows if length is None else self.rows[:length])

    def __aiter__(self):
        self._it = iter(self.rows)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _Analyses:
    def find(self, *_args, **_kwargs):
        return _Cursor([{
            "game_id": "g1",
            "stockfish_analysis": {"move_evaluations": [{
                "move_number": 1,
                "fen_before": FEN,
                "move": "Qd5",
                "move_uci": "d1d5",
                "best_move": "d1a4",
                "cp_loss": 500,
                "cognitive_gap": "piece_safety",
                "pv_after_played": ["Rxd5"],
            }]},
        }])


class _Games:
    async def find_one(self, *_args, **_kwargs):
        return {
            "game_id": "g1",
            "user_id": "u1",
            "user_color": "white",
            "pgn": PGN,
        }


class _Attempts:
    def find(self, *_args, **_kwargs):
        return _Cursor([])


class _DB:
    game_analyses = _Analyses()
    games = _Games()
    puzzle_attempts = _Attempts()


@pytest.mark.asyncio
async def test_exact_focus_serves_only_matching_own_game_proof():
    service = CoachingPuzzleService(_DB())
    puzzles = await service._get_puzzles_from_user_games(
        "u1",
        "piece_safety",
        limit=10,
        solved_ids=set(),
        required_quality_id="gap:piece_safety:destination_safety_exact",
    )

    assert len(puzzles) == 1
    verdict = puzzles[0]["verified_admission"]
    assert verdict["status"] == "specific"
    assert verdict["quality_id"] == (
        "gap:piece_safety:destination_safety_exact"
    )


@pytest.mark.asyncio
async def test_different_exact_focus_cannot_reuse_the_position():
    service = CoachingPuzzleService(_DB())
    puzzles = await service._get_puzzles_from_user_games(
        "u1",
        "piece_safety",
        limit=10,
        solved_ids=set(),
        required_quality_id="gap:piece_safety:some_other_claim",
    )
    assert puzzles == []

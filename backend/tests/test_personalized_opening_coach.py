import asyncio
from types import SimpleNamespace

import chess

from services.opening_mastery_tracker import (
    FREE_PLAY,
    MASTERED,
    _compute_phase,
    compute_engine_aware_opening_accuracy,
    record_opening_practice_completion,
)


class _UpdateResult:
    def __init__(self, modified_count):
        self.modified_count = modified_count


class _MemoryCollection:
    def __init__(self):
        self.document = None

    async def update_one(self, query, update, upsert=False):
        created = False
        if self.document is None:
            if not upsert:
                return _UpdateResult(0)
            self.document = {
                key: value
                for key, value in query.items()
                if not isinstance(value, dict)
            }
            created = True

        for key, condition in query.items():
            if isinstance(condition, dict) and "$ne" in condition:
                if condition["$ne"] in (self.document.get(key) or []):
                    return _UpdateResult(0)
            elif self.document.get(key) != condition:
                return _UpdateResult(0)

        if created:
            self.document.update(update.get("$setOnInsert") or {})
        self.document.update(update.get("$set") or {})
        for key, amount in (update.get("$inc") or {}).items():
            self.document[key] = int(self.document.get(key) or 0) + amount
        for key, value in (update.get("$addToSet") or {}).items():
            values = list(self.document.get(key) or [])
            if value not in values:
                values.append(value)
            self.document[key] = values
        return _UpdateResult(1)


class _ListCursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, *_args, **_kwargs):
        return list(self.documents)


class _FindCollection:
    def __init__(self, documents):
        self.documents = documents

    def find(self, *_args, **_kwargs):
        return _ListCursor(self.documents)


def test_black_authored_moves_are_compared_with_black_plies():
    setup_order = ["e4", "e5", "Nf3", "Nc6"]
    black_moves = [
        {
            "is_user_move": True,
            "phase": "opening",
            "move_san": "e5",
            "cp_loss": 100,
        },
        {
            "is_user_move": True,
            "phase": "opening",
            "move_san": "Nc6",
            "cp_loss": 100,
        },
    ]

    accuracy, count = compute_engine_aware_opening_accuracy(
        black_moves,
        setup_order,
        player_color="black",
    )

    assert count == 2
    assert accuracy == 1.0


def test_unknown_engine_loss_does_not_become_full_credit():
    accuracy, count = compute_engine_aware_opening_accuracy(
        [{
            "is_user_move": True,
            "phase": "opening",
            "move_san": "a3",
            "cp_loss": None,
        }],
        ["e4", "e5"],
        player_color="white",
    )

    assert accuracy is None
    assert count == 0


def test_personalized_opening_coach_rollout_is_default_off():
    from services.personalized_opening_coach import (
        FEATURE_FLAG,
        personalized_opening_coach_enabled,
    )

    assert personalized_opening_coach_enabled({}) is False
    assert personalized_opening_coach_enabled({FEATURE_FLAG: "true"}) is True


def test_recommendation_headline_uses_concise_authored_words(monkeypatch):
    from services import opening_library_service

    monkeypatch.setattr(
        "services.opening_theory_json_service.get_all_lesson_move_paths",
        lambda _key: [[{
            "move": "d5",
            "explanation": (
                "d5. You challenge the middle on move one, before White has "
                "any pieces out. Either they take or leave the pawn."
            ),
        }]],
    )

    title = opening_library_service._authored_idea_for_move(
        "scandinavian-defense",
        "d5",
    )

    assert title == "You challenge the middle on move one"
    assert len(title) <= 96


def test_opening_stats_keep_chosen_and_opponent_roles_separate():
    from opening_trainer_service import get_user_opening_stats

    fake_db = SimpleNamespace(
        games=_FindCollection([
            {
                "game_id": "white-game",
                "opening_name": "Italian Game",
                "user_color": "white",
                "result": "1-0",
            },
            {
                "game_id": "black-game",
                "opening_name": "Italian Game",
                "user_color": "black",
                "result": "1-0",
            },
            {
                "game_id": "dict-opening-game",
                "opening": {"name": "Italian Game"},
                "user_color": "black",
                "result": "draw",
            },
        ]),
        game_analyses=_FindCollection([
            {"game_id": "white-game", "accuracy": 90},
            {"game_id": "black-game", "accuracy": 40},
            {"game_id": "dict-opening-game", "accuracy": 70},
        ]),
    )

    split = asyncio.run(
        get_user_opening_stats(fake_db, "user-1", split_by_color=True)
    )
    combined = asyncio.run(get_user_opening_stats(fake_db, "user-1"))

    assert len(split) == 2
    assert {(row["player_color"], row["games_played"]) for row in split} == {
        ("white", 1),
        ("black", 2),
    }
    assert len(combined) == 1
    assert combined[0]["games_played"] == 3


def test_experience_mastery_path_is_reachable_with_ten_results():
    history = [0.55] * 10

    assert _compute_phase(FREE_PLAY, 10, history) == MASTERED


def test_practice_evidence_is_idempotent_and_never_awards_mastery():
    collection = _MemoryCollection()
    fake_db = SimpleNamespace(user_opening_mastery=collection)

    first = asyncio.run(
        record_opening_practice_completion(
            fake_db,
            "user-1",
            "italian_game",
            "session-1",
            "white",
            player_role="chosen_opening",
        )
    )
    duplicate = asyncio.run(
        record_opening_practice_completion(
            fake_db,
            "user-1",
            "italian_game",
            "session-1",
            "white",
            player_role="chosen_opening",
        )
    )
    assisted = asyncio.run(
        record_opening_practice_completion(
            fake_db,
            "user-1",
            "italian_game",
            "session-2",
            "black",
            player_role="answering_opponent",
            mistakes_count=1,
            hints_used=1,
        )
    )

    assert first["recorded"] is True
    assert first["mastery_awarded"] is False
    assert duplicate["recorded"] is False
    assert assisted["evidence_status"] == "assisted_practice"
    assert assisted["evidence"]["role"] == "answering_opponent"
    assert collection.document["phase"] == "introduction"
    assert collection.document["games_played"] == 0
    assert collection.document["practice_attempts"] == 2
    assert collection.document["independent_practice_completions"] == 1
    assert collection.document["assisted_practice_completions"] == 1
    assert collection.document["white_practice_attempts"] == 1
    assert collection.document["black_practice_attempts"] == 1
    assert collection.document["white_independent_practice_completions"] == 1
    assert collection.document["black_assisted_practice_completions"] == 1


def test_non_authored_move_uses_server_engine_soundness(monkeypatch):
    import stockfish_service
    from services import opening_practice_evidence
    from services.opening_practice_evidence import evaluate_practice_alternative

    class _FakeEngine:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def analyse_full(self, board, depth=18, pv_length=6):
            if not board.move_stack:
                return 35, chess.Move.from_uci("e2e4"), ["e4", "e5"]
            return 25, chess.Move.from_uci("e7e5"), ["e5", "Nf3"]

    monkeypatch.setattr(stockfish_service, "StockfishEngine", _FakeEngine)
    monkeypatch.setattr(opening_practice_evidence, "StockfishEngine", _FakeEngine)
    board = chess.Board()
    result = asyncio.run(
        evaluate_practice_alternative(board, chess.Move.from_uci("d2d4"))
    )

    assert result["cp_loss"] == 10
    assert result["best_move_san"] == "e4"
    assert result["reply_line"][0] == "e5"


def test_branch_identity_is_transposition_safe_and_keeps_player_role(monkeypatch):
    from services import opening_branch_evidence

    monkeypatch.setattr(
        opening_branch_evidence,
        "resolve_opening_key",
        lambda _key: "sample_opening",
    )
    monkeypatch.setattr(
        opening_branch_evidence,
        "get_opening_theory",
        lambda _key: {"color": "white"},
    )
    monkeypatch.setattr(
        opening_branch_evidence,
        "get_all_lesson_move_paths",
        lambda _key: [[
            {"move": "e4", "side": "white"},
            {"move": "e5", "side": "black"},
        ]],
    )

    after_e4 = chess.Board()
    after_e4.push_san("e4")
    events = opening_branch_evidence.build_opening_branch_events(
        "sample_opening",
        "black",
        "1. e4 c5 *",
        [{
            "fen_before": after_e4.fen(),
            "move": "c5",
            "cp_loss": 10,
        }],
        "game-1",
    )

    assert len(events) == 1
    assert events[0]["outcome"] == "sound_alternative"
    assert events[0]["role"] == "answering_opponent"
    assert events[0]["player_color"] == "black"

    same_position_different_clocks = " ".join(
        after_e4.fen().split()[:4] + ["17", "42"]
    )
    key_a = opening_branch_evidence.normalized_position_key(after_e4)
    key_b = opening_branch_evidence.normalized_position_key(
        same_position_different_clocks
    )
    assert key_a == key_b
    assert opening_branch_evidence.decision_id(
        "sample_opening", "black", key_a
    ) == opening_branch_evidence.decision_id(
        "sample_opening", "black", key_b
    )

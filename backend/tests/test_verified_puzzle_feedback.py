import inspect

from services import verified_puzzle_feedback as feedback


START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _puzzle(concept, facts, *, fen=START, best="g1f3", source="community"):
    return {
        "fen": fen,
        "best_move_uci": best,
        "source": source,
        "verified_admission": {
            "status": "specific",
            "concept_id": concept,
            "detector_facts": [{"candidate": True}],
            "verifier_facts": [facts],
        },
    }


def test_fork_feedback_names_piece_square_and_both_targets():
    puzzle = _puzzle(
        "tactic.knight_fork",
        {
            "forking_piece": "knight",
            "fork_square": "f3",
            "targets": ["e5", "h4"],
        },
    )

    result = feedback.build_verified_puzzle_feedback(
        puzzle, "g1f3", correct=True, primary_uci="g1f3"
    )

    assert "knight on f3" in result["why"]
    assert "e5, h4" in result["why"]
    assert "verified answer set" not in result["feedback"].lower()


def test_piece_safety_feedback_identifies_the_source_game_and_hanging_piece():
    puzzle = _puzzle(
        "piece_safety.simple_hang",
        {"piece": "bishop", "square": "d4", "winning_reply_uci": "e5d4"},
        source="your_game",
    )

    result = feedback.build_verified_puzzle_feedback(
        puzzle, "d2d4", correct=False, primary_uci="g1f3"
    )

    assert result["feedback"].startswith("This came from your own game.")
    assert "bishop on d4" in result["why"]
    assert "scan every piece you own" in result["remember"]


def test_canonical_endgame_feedback_reuses_the_owned_lesson_content():
    fen = "8/4k3/8/8/4K3/4P3/8/8 w - - 0 1"
    puzzle = _puzzle(
        "endgame:king_and_pawn/opposition",
        {"content_id": "king_and_pawn/opposition", "position_index": 0},
        fen=fen,
        best="e4d5",
    )

    result = feedback.build_verified_puzzle_feedback(
        puzzle, "e4d5", correct=True, primary_uci="e4d5"
    )

    assert "Kd5" in result["feedback"]
    assert "King" in result["why"]
    assert "pawn" in result["remember"].lower()


def test_generic_feedback_describes_only_a_visible_move_effect():
    puzzle = {
        "fen": START,
        "best_move_uci": "e2e4",
        "verified_admission": {"status": "generic"},
    }

    result = feedback.build_verified_puzzle_feedback(
        puzzle, "d2d4", correct=False, primary_uci="e2e4"
    )

    assert "pawn from e2 to e4" in result["why"]
    assert "verified" not in result["feedback"].lower()


def test_feedback_renderer_has_no_engine_model_or_network_dependency():
    source = inspect.getsource(feedback).lower()
    forbidden = (
        "stockfish",
        "chess.engine",
        "openai",
        "anthropic",
        "requests.",
        "httpx.",
    )
    assert not [token for token in forbidden if token in source]

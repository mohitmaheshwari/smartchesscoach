from copy import deepcopy

import chess

from services.curriculum_content_validator import (
    get_publishable_content_ids,
    is_content_publishable,
    trap_content_id,
    validate_all_content,
    validate_endgame_lesson,
    validate_opening_record,
    validate_trap_record,
)


def _codes(record):
    return {issue.code for issue in record.issues}


def test_real_canonical_sources_are_reported_together():
    report = validate_all_content()

    assert set(report["subjects"]) == {"openings", "traps", "endgames"}
    assert report["subjects"]["openings"]["total"] == 79
    assert report["subjects"]["traps"]["total"] == 55
    assert report["subjects"]["endgames"]["total"] == 18
    assert report["canonical_sources"]["openings"].endswith(
        "backend/data/opening_curriculum.json"
    )


def test_repaired_opening_trees_are_publishable():
    report = validate_all_content()
    records = report["subjects"]["openings"]["records"]

    for opening_key in ("london_system", "italian_game_black", "modern_defense"):
        assert records[opening_key]["publishable"] is True
        assert not any(
            issue["code"] == "move.illegal_or_ambiguous"
            for issue in records[opening_key]["issues"]
        )


def test_repaired_french_critical_position_is_publishable():
    report = validate_all_content()
    french = report["subjects"]["openings"]["records"]["french_defense"]

    assert french["publishable"] is True
    assert not any(
        issue["code"] == "move.illegal_or_ambiguous"
        for issue in french["issues"]
    )


def test_opening_without_a_teaching_line_is_not_a_visible_lesson():
    record = validate_opening_record(
        "recognition_only",
        {"name": "Recognition only", "color": "white", "summary": "A label."},
    )

    assert "opening.no_teaching_line" in _codes(record)
    assert record.publishable is False


def test_legal_opening_line_with_teaching_copy_passes():
    record = validate_opening_record(
        "open_game",
        {
            "name": "Open Game",
            "color": "white",
            "summary": "Develop a knight while attacking the center pawn.",
            "main_line": ["e4", "e5", "Nf3"],
            "move_ideas": {
                "e4": {"idea": "Put a pawn in the center."},
                "e5": {"idea": "Black takes a share of the center."},
                "Nf3": {"idea": "Bring out a knight and attack e5."},
            },
        },
    )

    assert record.publishable is True


def test_flat_opening_line_without_move_teaching_stays_recognition_only():
    record = validate_opening_record(
        "label_with_moves",
        {
            "name": "Label with moves",
            "color": "white",
            "summary": "This can recognize a line but cannot teach it yet.",
            "main_line": ["e4", "e5", "Nf3"],
        },
    )

    assert "opening.move_teaching_missing" in _codes(record)
    assert record.publishable is False


def test_unexplained_specialist_term_fails_player_voice_gate():
    record = validate_opening_record(
        "jargon",
        {
            "name": "Jargon",
            "color": "white",
            "summary": "Gain a tempo.",
            "main_line": ["e4"],
            "move_ideas": {"e4": {"idea": "Put a pawn in the center."}},
        },
    )

    assert "voice.unexplained_term" in _codes(record)
    assert record.publishable is False


def test_trap_line_must_demonstrate_claimed_mate():
    trap = {
        "name": "Empty mate claim",
        "description": "A test line.",
        "success_message": "Mate.",
        "result_type": "checkmate",
        "trap_color": "white",
        "setup_moves": ["e4", "e5"],
        "trap_line": [
            {"move": "Nf3", "explanation": "Develop with a threat."},
        ],
    }

    record = validate_trap_record("open-game", trap)

    assert "trap.outcome_not_demonstrated" in _codes(record)
    assert record.publishable is False


def test_real_legal_mate_line_passes():
    trap = {
        "name": "Scholar finish",
        "description": "Black ignores the shared attack on f7.",
        "success_message": "The queen reaches f7 with mate.",
        "result_type": "checkmate",
        "trap_color": "white",
        "setup_moves": ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6"],
        "trap_line": [
            {"move": "Qxf7#", "explanation": "Queen and bishop protect f7 together."},
        ],
    }

    record = validate_trap_record("open-game", trap)

    assert record.publishable is True


def test_endgame_fen_and_answer_must_agree():
    lesson = {
        "name": "King step",
        "rule": "Bring the king closer.",
        "description": "Use the king.",
        "positions": [
            {
                "fen": "8/8/8/8/8/8/4K3/6k1 w - - 0 1",
                "side_to_move": "white",
                "prompt": "Move closer.",
                "correct_move_san": "Ke3",
                "correct_move_uci": "e2e3",
                "idea": "The king approaches.",
                "on_correct": "Good.",
                "on_wrong": "Try a king step.",
            }
        ],
    }
    evidence = {
        ("kings/king_step", 0): {
            "content_id": "kings/king_step",
            "position_index": 0,
            "fen": chess.Board(lesson["positions"][0]["fen"]).fen(),
            "stored_move_uci": "e2e3",
            "root_category": "draw",
            "move_category_from_opponent_turn": "draw",
            "preserves_wdl": True,
        }
    }
    record = validate_endgame_lesson("kings", "king_step", lesson, evidence)

    assert record.publishable is True

    broken = deepcopy(lesson)
    broken["positions"][0]["correct_move_uci"] = "e2e4"
    broken_record = validate_endgame_lesson("kings", "broken", broken, evidence)
    assert "endgame.move_illegal" in _codes(broken_record)


def test_real_tablebase_regressions_are_quarantined():
    report = validate_all_content()
    philidor = report["subjects"]["endgames"]["records"][
        "rook_endgames/philidor"
    ]
    opposite_bishops = report["subjects"]["endgames"]["records"][
        "bishop_endgames/opposite_color_bishops"
    ]

    assert any(
        issue["code"] == "endgame.tablebase_regression"
        for issue in philidor["issues"]
    )
    assert sum(
        issue["code"] == "endgame.tablebase_regression"
        for issue in opposite_bishops["issues"]
    ) == 3


def test_publication_helpers_use_record_identity():
    report = validate_all_content()
    publishable = get_publishable_content_ids("traps")

    for content_id in publishable:
        assert is_content_publishable("traps", content_id)
    assert trap_content_id("open-game", "Scholar's Mate") == (
        "open-game/scholar-s-mate"
    )
    assert report["subjects"]["traps"]["publishable"] == len(publishable)

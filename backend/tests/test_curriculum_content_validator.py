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

    assert set(report["subjects"]) == {
        "openings",
        "traps",
        "opening_ideas",
        "endgames",
    }
    assert report["subjects"]["openings"]["total"] == 79
    assert report["subjects"]["traps"]["total"] == 36
    assert report["subjects"]["opening_ideas"]["total"] == 19
    assert report["subjects"]["endgames"]["total"] == 20
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


def test_completed_flat_opening_lessons_are_publishable():
    records = validate_all_content()["subjects"]["openings"]["records"]

    completed = {
        "albin_counter_gambit",
        "benoni_defense",
        "budapest_gambit",
        "dutch_defense",
        "englund_gambit",
        "grunfeld_defense",
        "nimzo_indian",
        "nimzowitsch_defense",
        "qgd",
        "queens_indian",
        "sicilian_dragon",
        "sicilian_najdorf",
        "kings_pawn_opening",
        "van_t_kruijs_opening",
        "queens_pawn_opening_chigorin_v",
        "center_game",
    }

    assert all(records[key]["publishable"] for key in completed)


def test_repaired_french_critical_position_is_publishable():
    report = validate_all_content()
    french = report["subjects"]["openings"]["records"]["french_defense"]

    assert french["publishable"] is True
    assert not any(
        issue["code"] == "move.illegal_or_ambiguous"
        for issue in french["issues"]
    )


def test_complete_endgame_catalog_is_publishable():
    subject = validate_all_content()["subjects"]["endgames"]

    assert subject["total"] == 20
    assert subject["publishable"] == 20
    assert subject["quarantined"] == 0


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


def test_player_voice_gate_ignores_internal_reference_ids():
    record = validate_opening_record(
        "reference_ids_are_not_copy",
        {
            "name": "Reference ID example",
            "color": "white",
            "main_line": ["d4"],
            "move_ideas": {"d4": {"idea": "Put a pawn in the center."}},
            "critical_positions": {
                "choice": {
                    "fen_pattern": chess.STARTING_FEN,
                    "best_moves_white": {
                        "d4": {
                            "idea": "Put a pawn in the center.",
                            "leads_to": "qi_fianchetto",
                        }
                    },
                }
            },
        },
    )

    assert "voice.unexplained_term" not in _codes(record)


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


def test_opening_plan_requires_an_honest_goal_not_a_forced_result():
    lesson = {
        "name": "Center plan",
        "lesson_kind": "opening_plan",
        "learning_goal": "Use d4 to build a two-pawn center.",
        "description": "A model line for gaining central space.",
        "success_message": "The center gives both bishops room to develop.",
        "result_type": "opening_plan",
        "trap_color": "white",
        "setup_moves": ["e4", "e5"],
        "trap_line": [
            {"move": "d4", "explanation": "Challenge e5 and open the c1 bishop."},
        ],
    }

    record = validate_trap_record("open-game", lesson)
    assert record.subject == "opening_ideas"
    assert record.publishable is True

    broken = deepcopy(lesson)
    broken["success_message"] = "This is a forced winning plan."
    broken_record = validate_trap_record("open-game", broken)
    assert "opening_idea.forced_claim" in _codes(broken_record)


def test_opening_plan_cannot_call_an_advanced_pawn_passed():
    lesson = {
        "name": "False passer",
        "lesson_kind": "opening_plan",
        "learning_goal": "Develop while supporting the center.",
        "description": "White has a strong passed pawn on d5.",
        "success_message": "The d5-pawn gives White more room.",
        "result_type": "opening_plan",
        "trap_color": "white",
        "setup_moves": ["d4", "Nf6", "d5", "e6"],
        "trap_line": [
            {"move": "Nc3", "explanation": "Develop and support the center."},
        ],
    }

    record = validate_trap_record("queen-pawn", lesson)

    assert "opening_idea.passed_pawn_claim_false" in _codes(record)
    assert record.publishable is False

    corrected = deepcopy(lesson)
    corrected["description"] = (
        "The d5-pawn is not a passed pawn because Black's e6-pawn can capture it."
    )
    corrected_record = validate_trap_record("queen-pawn", corrected)
    assert "opening_idea.passed_pawn_claim_false" not in _codes(corrected_record)


def test_opening_plan_cannot_call_one_of_many_legal_replies_forced():
    lesson = {
        "name": "False forced reply",
        "lesson_kind": "opening_plan",
        "learning_goal": "Develop a knight.",
        "description": "A model development line.",
        "success_message": "Both sides have developed a piece.",
        "result_type": "opening_plan",
        "trap_color": "white",
        "setup_moves": ["e4", "e5"],
        "trap_line": [
            {"move": "Nf3", "explanation": "Forced — this is the only legal move."},
        ],
    }

    record = validate_trap_record("open-game", lesson)

    assert "opening_idea.reply_not_forced" in _codes(record)
    assert record.publishable is False

    corrected = deepcopy(lesson)
    corrected["trap_line"][0]["explanation"] = (
        "White chooses Nf3 to develop and attack e5."
    )
    corrected_record = validate_trap_record("open-game", corrected)
    assert "opening_idea.reply_not_forced" not in _codes(corrected_record)


def test_exposed_king_claim_requires_the_line_to_remove_castling_and_move_king():
    trap = {
        "name": "King chase",
        "description": "A sacrifice pulls the king away from home.",
        "success_message": "The king is exposed on e6.",
        "result_type": "king_exposed",
        "trap_color": "white",
        "setup_moves": [
            "e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5",
            "d5", "exd5", "Nxd5", "Nxf7", "Kxf7", "Qf3+", "Ke6",
        ],
        "trap_line": [
            {"move": "Nc3", "explanation": "Develop with pressure on d5."},
        ],
    }

    assert validate_trap_record("italian", trap).publishable is True

    broken = deepcopy(trap)
    broken["setup_moves"] = ["e4", "e5"]
    broken["trap_line"] = [
        {"move": "Nf3", "explanation": "Develop a knight."},
    ]
    record = validate_trap_record("italian", broken)
    assert "trap.outcome_not_demonstrated" in _codes(record)


def test_endgame_fen_and_answer_must_agree():
    lesson = {
        "name": "King step",
        "rule": "Bring the king closer.",
        "description": "Use the king.",
        "positions": [
            {
                "fen": "8/8/8/8/8/8/4K3/6k1 w - - 0 1",
                "side_to_move": "white",
                "expected_result": "draw",
                "prompt": "Move closer.",
                "correct_move_san": "Ke3",
                "correct_move_uci": "e2e3",
                "wrong_example_san": "Kd2",
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

    false_claim = deepcopy(lesson)
    false_claim["positions"][0]["expected_result"] = "win"
    false_claim_record = validate_endgame_lesson(
        "kings", "king_step", false_claim, evidence
    )
    assert "endgame.claimed_result_mismatch" in _codes(false_claim_record)

    missing_claim = deepcopy(lesson)
    del missing_claim["positions"][0]["expected_result"]
    missing_claim_record = validate_endgame_lesson(
        "kings", "king_step", missing_claim, evidence
    )
    assert "endgame.expected_result_missing" in _codes(missing_claim_record)

    broken = deepcopy(lesson)
    broken["positions"][0]["correct_move_uci"] = "e2e4"
    broken_record = validate_endgame_lesson("kings", "broken", broken, evidence)
    assert "endgame.move_illegal" in _codes(broken_record)

    illegal_wrong = deepcopy(lesson)
    illegal_wrong["positions"][0]["wrong_example_san"] = "Ke4"
    illegal_wrong_record = validate_endgame_lesson(
        "kings", "king_step", illegal_wrong, evidence
    )
    assert "endgame.wrong_example_illegal" in _codes(illegal_wrong_record)


def test_repaired_tablebase_lessons_preserve_the_exact_result():
    report = validate_all_content()
    philidor = report["subjects"]["endgames"]["records"][
        "rook_endgames/philidor"
    ]
    opposite_bishops = report["subjects"]["endgames"]["records"][
        "bishop_endgames/opposite_color_bishops"
    ]

    assert philidor["publishable"] is True
    assert opposite_bishops["publishable"] is True
    assert not any(
        issue["code"] == "endgame.tablebase_regression"
        for issue in philidor["issues"] + opposite_bishops["issues"]
    )


def test_publication_helpers_use_record_identity():
    report = validate_all_content()
    publishable = get_publishable_content_ids("traps")

    for content_id in publishable:
        assert is_content_publishable("traps", content_id)
    assert trap_content_id("open-game", "Scholar's Mate") == (
        "open-game/scholar-s-mate"
    )
    assert report["subjects"]["traps"]["publishable"] == len(publishable)

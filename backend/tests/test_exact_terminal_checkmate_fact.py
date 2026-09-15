from __future__ import annotations

from copy import deepcopy

import chess
import pytest

from services.caption_facts import (
    EXACT_TERMINAL_QUALITY_ID,
    ExactTerminalFact,
    build_exact_terminal_fact,
)
from services.caption_pipeline import build_exact_terminal_teaching
from services.caption_pipeline import render_exact_terminal_teaching_claim
from services.detector_quality import QualityGrade, get_authorization, grade_for
from services.game_review_shadow_runtime import adapt_exact_terminal_event
from services.community_game_study_service import (
    CommunityGameStudyError,
    _project_stored_chapter,
    project_neutral_chapter,
)


def _fools_mate_position() -> chess.Board:
    board = chess.Board()
    for san in ("f3", "e5", "g4"):
        board.push_san(san)
    return board


def test_exact_terminal_fact_proves_the_played_checkmate_from_the_board():
    board = _fools_mate_position()
    fact = build_exact_terminal_fact(
        fen_before=board.fen(),
        played_move="Qh4#",
    )
    assert fact is not None
    assert fact.move_uci == "d8h4"
    assert fact.move_san == "Qh4#"
    assert fact.mover_color == "black"
    assert fact.origin == "d8"
    assert fact.destination == "h4"
    assert fact.checked_king_square == "e1"
    assert fact.terminal_legal_replies == 0
    assert {(item.piece, item.square) for item in fact.checking_pieces} == {
        ("queen", "h4")
    }
    assert ExactTerminalFact.from_document(fact.contract_dict()) == fact


@pytest.mark.parametrize("move", ["Qh6", "Qh4"])
def test_exact_terminal_fact_abstains_when_the_move_is_not_legal_checkmate(move):
    board = _fools_mate_position()
    if move == "Qh4":
        board = chess.Board()
    assert build_exact_terminal_fact(
        fen_before=board.fen(),
        played_move=move,
    ) is None


def test_exact_terminal_fact_rejects_stale_serialized_evidence():
    fact = build_exact_terminal_fact(
        fen_before=_fools_mate_position().fen(),
        played_move="Qh4#",
    )
    assert fact is not None
    stale = deepcopy(fact.contract_dict())
    stale["checked_king_square"] = "d1"
    with pytest.raises(ValueError, match="fingerprint"):
        ExactTerminalFact.from_document(stale)


def test_terminal_teaching_is_narrow_board_fact_with_a_transferable_check():
    fact = build_exact_terminal_fact(
        fen_before=_fools_mate_position().fen(),
        played_move="Qh4#",
    )
    assert fact is not None
    teaching = build_exact_terminal_teaching(fact)
    assert teaching["headline"] == "The king has no legal reply"
    assert "king on e1" in teaching["explanation"]
    assert "no legal move" in teaching["explanation"]
    assert teaching["demonstration"]["moves_san"] == ["Qh4#"]
    assert teaching["interaction"]["correct_option_id"] == "no_legal_reply"
    assert teaching["principle"].endswith("block the check.")


def test_review_renderer_matches_verified_player_copy_without_granting_truth():
    fact = build_exact_terminal_fact(
        fen_before=_fools_mate_position().fen(),
        played_move="Qh4#",
    )
    assert fact is not None
    preview = render_exact_terminal_teaching_claim(
        move_san=fact.move_san,
        checked_king_square=fact.checked_king_square,
    )
    assert preview == build_exact_terminal_teaching(fact)
    assert preview["explanation"].startswith("Qh4 ends the game.")


def test_terminal_event_is_bound_to_caption_promotion_evidence():
    board = _fools_mate_position()
    pair = adapt_exact_terminal_event(
        fen_before=board.fen(),
        played_move="Qh4#",
        game_id="anonymous-game",
        ply=4,
        move_number=2,
        phase="opening",
    )
    assert grade_for(EXACT_TERMINAL_QUALITY_ID) == QualityGrade.CAPTION
    assert get_authorization(EXACT_TERMINAL_QUALITY_ID).evidence_ref.endswith(
        "exact_terminal_checkmate_caption_promotion_v1.json"
    )
    assert pair is not None


def test_promoted_terminal_event_reaches_finish_planner_without_mistake_frame():
    pair = adapt_exact_terminal_event(
        fen_before=_fools_mate_position().fen(),
        played_move="Qh4#",
        game_id="anonymous-game",
        ply=4,
        move_number=2,
        phase="",
    )
    assert pair is not None
    event, features = pair
    assert event.player_authorized is True
    assert event.practical is None
    assert event.contract_dict()["cause"]["kind"] == "exact_terminal_checkmate"
    assert features.terminal is True
    assert features.phase == "opening"
    assert features.primary_principle_id == (
        "king_safety.confirm_all_mate_defenses"
    )
    projected = project_neutral_chapter(
        event.contract_dict(),
        {
            "event_id": event.event_id,
            "concept_id": event.concept.concept_id,
            "quality_id": EXACT_TERMINAL_QUALITY_ID,
            "phase": "opening",
            "ply": 4,
            "move_number": 2,
            "role": "finish",
            "primary_principle_id": (
                "king_safety.confirm_all_mate_defenses"
            ),
        },
    )
    assert projected["headline"] == "The king has no legal reply"
    assert projected["demonstration"]["moves_san"] == ["Qh4#"]
    assert projected["interaction"]["correct_option_id"] == "no_legal_reply"
    verified_projection = _project_stored_chapter(
        event.contract_dict(),
        {
            "event_id": event.event_id,
            "concept_id": event.concept.concept_id,
            "quality_id": EXACT_TERMINAL_QUALITY_ID,
            "phase": "opening",
            "ply": 4,
            "move_number": 2,
            "role": "finish",
            "primary_principle_id": (
                "king_safety.confirm_all_mate_defenses"
            ),
        },
        fen_before=_fools_mate_position().fen(),
    )
    assert verified_projection["role"] == "finish"


def test_terminal_projection_rederives_board_truth_instead_of_trusting_document():
    pair = adapt_exact_terminal_event(
        fen_before=_fools_mate_position().fen(),
        played_move="Qh4#",
        game_id="anonymous-game",
        ply=4,
        move_number=2,
        phase="opening",
    )
    assert pair is not None
    event, _ = pair
    with pytest.raises(
        CommunityGameStudyError,
        match="does not match the exact chapter position",
    ):
        _project_stored_chapter(
            event.contract_dict(),
            {
                "event_id": event.event_id,
                "concept_id": event.concept.concept_id,
                "quality_id": EXACT_TERMINAL_QUALITY_ID,
                "phase": "opening",
                "ply": 4,
                "move_number": 2,
                "role": "finish",
                "primary_principle_id": (
                    "king_safety.confirm_all_mate_defenses"
                ),
            },
            fen_before=chess.STARTING_FEN,
        )

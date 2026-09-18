"""A move the grader declines to judge must not count against the player.

`grade_destination_safety_candidate` answers exactly one question: does the
piece you MOVED survive the full exchange on the square it LANDED on? It
returns `piece_not_eligible` for every pawn and every king move, so a large
share of the board is simply outside its competence:

    Italian middlegame   14 of 38 legal moves  (37%)  -- includes O-O
    open Sicilian        13 of 43 legal moves  (30%)
    pawn-heavy endgame    6 of 10 legal moves  (60%)

Every one of those satisfies the printed question ("Play a move that leaves
nothing of yours hanging"), and the card tells the player the truth -- it
renders no verdict and says "I cannot measure h3 fairly here, so I will not
judge it."

The record did not match the card. `teaching_engine` decides whether an
attempt becomes learning evidence by reading a TOP-LEVEL `unmeasured` flag on
the grade, and this grader never set one -- only `target_result:
"unmeasured"`, which nothing reads. So `evidence_complete` stayed True and the
attempt was banked as a genuine wrong answer against the player's piece_safety
skill, feeding the picker and mastery from a move the product had just said it
would not judge.

Measured on prod 2026-09-18: two destination-safety attempts exist in total
and neither was ungraded, so there is nothing to repair. This closes it before
the lesson carries traffic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.destination_safety_detector import (  # noqa: E402
    QUALITY_ID,
    grade_destination_safety_candidate,
)
from services.personalized_lesson_adapter import (  # noqa: E402
    grade_personalized_move,
)

ITALIAN = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 0 1"


def _item(fen: str = ITALIAN):
    from services.lesson_question_spec import ANY_SAFE

    return {"fen": fen, "_accepts": ANY_SAFE, "item_id": "t1"}


async def _grade(move: str, fen: str = ITALIAN):
    return await grade_personalized_move(
        {"kind": "concept", "id": "x", "canonical_source": "s",
         "content_version": "1", "skill_id": "piece_safety"},
        _item(fen), move,
    )


def test_the_detector_really_does_decline_pawn_and_king_moves():
    """The premise, asserted rather than assumed."""
    board = chess.Board(ITALIAN)
    declined = [
        board.san(mv) for mv in board.legal_moves
        if grade_destination_safety_candidate(ITALIAN, mv.uci())["reason"]
        == "piece_not_eligible"
    ]
    assert "O-O" in declined, "castling is outside the grader's competence"
    assert "h3" in declined
    assert len(declined) > board.legal_moves.count() // 4, (
        f"expected a large share of the board to be unjudgeable, got {declined}"
    )


@pytest.mark.asyncio
async def test_an_unjudgeable_move_is_flagged_so_it_earns_no_evidence():
    for move in ("h2h3", "e1g1"):  # a quiet pawn move, and castling
        grade = await _grade(move)
        assert grade["target_result"] == "unmeasured", move
        assert grade["unmeasured"] is True, (
            f"{move}: teaching_engine reads the top-level flag, not "
            "target_result -- without it this is banked as a wrong answer"
        )


@pytest.mark.asyncio
async def test_a_judged_move_still_carries_full_evidence():
    """The flag must not swallow real results in either direction."""
    safe = await _grade("c4b3")        # Bb3, a quiet retreat: passes
    assert safe["target_result"] == "pass"
    assert safe["correct"] is True
    assert safe["unmeasured"] is False

    unsafe = await _grade("c4e6")      # Be6, walks into a pawn: fails
    assert unsafe["target_result"] == "fail"
    assert unsafe["correct"] is False
    assert unsafe["unmeasured"] is False, (
        "a genuinely wrong answer must still count against the player"
    )


@pytest.mark.asyncio
async def test_an_illegal_move_teaches_us_nothing_about_piece_safety():
    grade = await _grade("a1a8")
    assert grade["unmeasured"] is True


@pytest.mark.asyncio
async def test_a_position_proved_by_another_family_is_not_graded_here():
    item = _item()
    item["_diagnostic_quality_id"] = "gap:something:else"
    grade = await grade_personalized_move(
        {"kind": "concept", "id": "x", "canonical_source": "s",
         "content_version": "1", "skill_id": "piece_safety"},
        item, "c4b3",
    )
    assert grade["unmeasured"] is True
    assert QUALITY_ID not in str(grade.get("target_reason") or "")


def test_the_engine_gates_evidence_on_the_flag_this_grader_now_sets():
    """If that read ever moves, these tests stop meaning anything."""
    src = (BACKEND / "services" / "teaching_engine.py").read_text(encoding="utf-8")
    assert 'unmeasured = bool(grade.get("unmeasured"))' in src
    assert 'evidence_complete = not bool(grade.get("unmeasured"))' in src

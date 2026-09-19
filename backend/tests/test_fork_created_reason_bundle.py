"""The fork family answers with the fork, not with piece safety.

Before 2026-09-19 every diagnostic question was a piece-safety question,
including on fork, pin, skewer and mate puzzles, because
`build_reason_bundle_for_move` dispatched on a single quality id and returned
None for the other seventeen authorized detectors. A fork puzzle whose
solution was Bxc3+ asked "Before Bxc3+, what attacked your bishop on b4?".

The fork geometry was already proven and already CAPTION-graded. These tests
pin the two things that make it usable as a question: it must describe the
fork, and it must never claim material it has not proven.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_pipeline import build_reason_bundle_for_move
from services.destination_safety_detector import QUALITY_ID as SAFETY_QUALITY_ID
from services.fork_puzzle_proof import (
    FORK_QUALITY_ID,
    build_fork_created_reason_bundle,
)
from services.teaching_reason_contracts import build_reason_choices


# A knight landing on e7 forking the king on g8 and the rook on c8.
FORK_FEN = "2r3k1/pp3ppp/8/3N4/8/8/PP3PPP/6K1 w - - 0 1"
FORK_MOVE = "d5e7"


def _bundle():
    return build_fork_created_reason_bundle(FORK_FEN, FORK_MOVE)


def test_the_fork_is_actually_a_fork():
    """Guard the fixture itself, so a later edit cannot quietly de-fang it."""
    board = chess.Board(FORK_FEN)
    move = chess.Move.from_uci(FORK_MOVE)
    assert move in board.legal_moves
    board.push(move)
    attacked = {
        chess.square_name(square)
        for square in board.attacks(move.to_square)
        if board.piece_at(square) and board.piece_at(square).color == chess.BLACK
    }
    assert {"g8", "c8"} <= attacked


def test_question_names_the_forked_piece():
    """Ne7+ is a ROYAL fork, so the question asks what the check *also* hits.

    Naming the king as one of two "attacked pieces" would be the wrong
    lesson: the mechanism is that check forces a reply, which is what strands
    the rook. See test_royal_fork_teaches_the_check_mechanism.
    """
    bundle = _bundle()
    assert bundle.target_result == "pass"
    assert len(bundle.components) == 1
    component = bundle.components[0]
    assert component.kind == "fork_targets"
    assert "knight on e7" in component.prompt
    assert "besides the king" in component.prompt
    correct = next(
        c for c in component.choices if c.choice_id in component.accepted_choice_ids
    )
    assert "c8" in correct.label
    assert "g8" not in correct.label, "the king is the check, not the prize"


def test_royal_fork_teaches_the_check_mechanism():
    component = _bundle().components[0]
    joined = f"{component.success_text} {component.correction_text}".lower()
    assert "check" in joined
    assert "answered" in joined


def test_a_plain_fork_asks_which_pieces_and_claims_no_rule():
    """Without a king there is no forcing reply, so the text must not assert
    that one of them has to fall -- that is not proven here."""
    fen = "8/2r3r1/8/8/3N4/8/8/K6k w - - 0 1"  # Ne6 forks the rooks, no check
    bundle = build_fork_created_reason_bundle(fen, "d4e6")
    assert bundle.components, "fixture must produce a plain fork, not skip"
    component = bundle.components[0]
    assert "which ones?" in component.prompt.lower()
    assert "besides the king" not in component.prompt
    joined = f"{component.success_text} {component.correction_text}".lower()
    for rule in ("only one", "cannot both", "must fall", "has to fall"):
        assert rule not in joined


def test_it_does_not_ask_about_the_moved_piece_safety():
    """The defect this closes: a fork puzzle asking a piece-safety question."""
    prompt = _bundle().components[0].prompt.lower()
    assert "what attacked your" not in prompt
    assert "can black win your" not in prompt
    assert "destination square" not in prompt


def test_it_never_claims_material_it_has_not_proven():
    """`verify_created_fork` proves geometry only, by its own docstring. A
    "wins a piece" claim needs the payoff proof, a different entry point."""
    component = _bundle().components[0]
    text = " ".join(
        [component.prompt, component.success_text, component.correction_text]
        + [c.label for c in component.choices]
    ).lower()
    for claim in ("wins a piece", "win material", "wins material", "up material"):
        assert claim not in text
    assert component.facts["proves_material_gain"] is False


def test_the_false_choice_is_provably_false():
    """A distractor that happens to be true would mark a right answer wrong."""
    bundle = _bundle()
    component = bundle.components[0]
    board = chess.Board(FORK_FEN)
    move = chess.Move.from_uci(FORK_MOVE)
    board.push(move)
    attacked = {chess.square_name(s) for s in board.attacks(move.to_square)}
    wrong = [
        c for c in component.choices
        if c.choice_id not in component.accepted_choice_ids
    ]
    assert wrong, "there must be something to get wrong"
    for choice in wrong:
        squares = {
            f"{f}{r}"
            for f in "abcdefgh"
            for r in "12345678"
            if f"{f}{r}" in choice.label
        }
        assert squares, f"distractor names no square: {choice.label}"
        assert not squares <= attacked, (
            f"distractor {choice.label!r} is actually true"
        )


def test_no_attention_self_report_option():
    """The other branch removed the generic attitude quiz; this family must
    not reintroduce it. Every option is an answer about the board."""
    component = _bundle().components[0]
    ids = {c.choice_id for c in component.choices}
    assert "unsure" not in ids
    assert len(component.choices) == 2
    for choice in component.choices:
        assert "did not" not in choice.label.lower()
        assert "notice" not in choice.label.lower()


def test_exactly_one_choice_is_accepted():
    component = _bundle().components[0]
    assert len(component.accepted_choice_ids) == 1


def test_grading_matches_the_printed_question():
    """Selecting the option the prompt describes must grade correct."""
    component = _bundle().components[0]
    accepted = component.accepted_choice_ids[0]
    assert component.grade(accepted)["correct"] is True
    other = next(
        c.choice_id for c in component.choices if c.choice_id != accepted
    )
    assert component.grade(other)["correct"] is False


# --- abstention -----------------------------------------------------------

def test_a_non_fork_move_abstains_rather_than_inventing_one():
    bundle = build_fork_created_reason_bundle(FORK_FEN, "g1h1")
    assert bundle.components == ()
    assert bundle.target_result == "unmeasured"
    assert bundle.safety_kind == "no_fork_created"


def test_an_illegal_move_raises_rather_than_returning_a_wrong_bundle():
    with pytest.raises(ValueError):
        build_fork_created_reason_bundle(FORK_FEN, "d5d8")


def test_abstains_when_no_provably_false_distractor_exists():
    """Every enemy piece is forked, so any pair we could offer is true."""
    fen = "6k1/8/5N2/8/8/8/8/6K1 w - - 0 1"
    board = chess.Board(fen)
    assert board.piece_at(chess.G8) is not None
    bundle = build_fork_created_reason_bundle(fen, "f6h7")
    assert bundle.components == ()


# --- dispatcher -----------------------------------------------------------

def test_dispatcher_routes_the_fork_quality_id():
    bundle = build_reason_bundle_for_move(
        fen_before=FORK_FEN, submitted_move=FORK_MOVE, quality_id=FORK_QUALITY_ID
    )
    assert bundle is not None
    assert bundle.components[0].kind == "fork_targets"


def test_dispatcher_still_returns_none_for_unregistered_ids():
    """Registration is opt-in; an unpromoted id must not leak a reason."""
    assert build_reason_bundle_for_move(
        fen_before=FORK_FEN, submitted_move=FORK_MOVE, quality_id="tactic:not_real"
    ) is None


def test_fork_quality_id_is_caption_authorized():
    """This dispatcher must never expose an unpromoted detector."""
    from services.detector_quality import QualitySurface, is_authorized
    assert is_authorized(FORK_QUALITY_ID, QualitySurface.CAPTION)


# --- no regression in the piece-safety family ------------------------------

def test_reason_choice_ordering_is_unchanged():
    """The ordering helper moved into the contract module. Same seed, same
    order, same accepted id, and the unsure option still lands last."""
    choices, accepted = build_reason_choices("seed-1", "TRUE", "FALSE", "UNSURE")
    assert [c.choice_id for c in choices] == ["a", "b", "unsure"]
    assert choices[-1].label == "UNSURE"
    assert accepted[0] in {"a", "b"}
    labels = {c.choice_id: c.label for c in choices}
    assert labels[accepted[0]] == "TRUE"


def test_ordering_is_stable_for_a_given_seed():
    first = build_reason_choices("seed-2", "TRUE", "FALSE", "UNSURE")
    second = build_reason_choices("seed-2", "TRUE", "FALSE", "UNSURE")
    assert [c.label for c in first[0]] == [c.label for c in second[0]]
    assert first[1] == second[1]


def test_omitting_unsure_gives_two_choices():
    choices, accepted = build_reason_choices("seed-3", "TRUE", "FALSE")
    assert len(choices) == 2
    assert "unsure" not in {c.choice_id for c in choices}
    assert len(accepted) == 1


def test_piece_safety_bundle_still_builds_three_choices():
    """The existing family is untouched by the shared helper."""
    bundle = build_reason_bundle_for_move(
        fen_before=FORK_FEN, submitted_move=FORK_MOVE, quality_id=SAFETY_QUALITY_ID
    )
    assert bundle is not None
    for component in bundle.components:
        assert "unsure" in {c.choice_id for c in component.choices}

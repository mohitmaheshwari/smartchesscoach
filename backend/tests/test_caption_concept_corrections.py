"""The correction verifier: what it must refuse to say.

A compliment is settled by the board. A correction says a move the player did
NOT play was better, which only an engine can settle, and only at the depth
the claim is made at. Measured over 400 games the raw claim held 84-88%, so
one correction in eight would have told a player to develop a piece when the
strongest move was a queen move developing nothing.

These tests are about the refusals, because a correction that reaches a player
wrongly costs more than ten that never get said.
"""
import sys
from pathlib import Path

import chess

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_concept_corrections import (  # noqa: E402
    CLEARLY_BETTER_CP,
    MAX_CHECKS_PER_GAME,
    VERIFY_DEPTH,
    verdict_lookup,
    verify_corrections,
)
from services.caption_concept_sentences import (  # noqa: E402
    CONCEPT_PREDICATES,
    WRONG,
    concept_sentence_for_move,
)

START_FEN = chess.Board().fen()


def _dev(board, move, colour):
    return CONCEPT_PREDICATES["coached_development"](board, move, colour)


# ------------------------------------------------------- the lookup refuses

def test_a_position_never_checked_is_not_a_yes():
    """The table holds only what was settled. Absent must read as "do not
    say it", never as "assume it was fine"."""
    verify = verdict_lookup({})
    board = chess.Board()
    assert verify(board, board.parse_san("a3"), chess.WHITE) is False


def test_a_position_checked_and_refused_stays_refused():
    board = chess.Board()
    verify = verdict_lookup({(board.fen(), "a3"): False})
    assert verify(board, board.parse_san("a3"), chess.WHITE) is False


def test_a_position_checked_and_confirmed_passes():
    board = chess.Board()
    verify = verdict_lookup({(board.fen(), "a3"): True})
    assert verify(board, board.parse_san("a3"), chess.WHITE) is True


def test_the_lookup_is_keyed_to_the_position_not_just_the_move():
    """Two different positions can both be answered with the same SAN. A
    verdict earned in one must not travel to the other."""
    board = chess.Board()
    other = chess.Board()
    other.push_san("e4")
    other.push_san("e5")
    verify = verdict_lookup({(board.fen(), "a3"): True})
    assert verify(board, board.parse_san("a3"), chess.WHITE) is True
    assert verify(other, other.parse_san("a3"), chess.WHITE) is False


def test_a_lookup_that_is_handed_rubbish_says_no():
    verify = verdict_lookup({("not a fen", "a3"): True})
    board = chess.Board()
    assert verify(board, board.parse_san("a3"), chess.WHITE) is False


# ------------------------------------------------- the engine path refuses

def test_no_candidates_means_no_engine_is_started():
    assert verify_corrections([]) == {}


def test_a_missing_engine_does_not_raise_and_says_nothing():
    """On a box with no Stockfish the review must still render; corrections
    simply do not appear."""
    import services.caption_concept_corrections as mod

    original = mod.ENGINE_PATH
    try:
        mod.ENGINE_PATH = "/nonexistent/stockfish-does-not-exist"
        out = verify_corrections([(START_FEN, "a3", True, _dev)])
        assert out == {}
    finally:
        mod.ENGINE_PATH = original


def test_one_review_can_never_become_an_unbounded_engine_job():
    """The box that runs this also serves the app."""
    assert MAX_CHECKS_PER_GAME <= 5
    import services.caption_concept_corrections as mod

    original = mod.ENGINE_PATH
    try:
        mod.ENGINE_PATH = "/nonexistent/stockfish-does-not-exist"
        many = [(START_FEN, "a3", True, _dev)] * 50
        assert verify_corrections(many) == {}
    finally:
        mod.ENGINE_PATH = original


def test_the_depth_is_the_one_the_evidence_was_measured_at():
    """Changing it changes the basis of docs/detectors_speak_scope.md, so it
    is not a tuning knob."""
    assert VERIFY_DEPTH == 18
    assert CLEARLY_BETTER_CP == 100


# ------------------------------------------- end to end through the sentence

def test_the_sentence_layer_honours_a_refusal():
    board = chess.Board()
    said = concept_sentence_for_move(
        skill_id="coached_development",
        outcome=WRONG,
        board_before=board,
        move=board.parse_san("a3"),
        user_color=chess.WHITE,
        verify_correction=verdict_lookup({}),
    )
    assert said is None


def test_the_sentence_layer_speaks_on_a_confirmation():
    board = chess.Board()
    said = concept_sentence_for_move(
        skill_id="coached_development",
        outcome=WRONG,
        board_before=board,
        move=board.parse_san("a3"),
        user_color=chess.WHITE,
        verify_correction=verdict_lookup({(board.fen(), "a3"): True}),
    )
    assert said is not None
    assert said["outcome"] == WRONG
    assert said["principle"] in said["text"]

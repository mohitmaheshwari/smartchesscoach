"""The adversarial packet for the six detectors promoted on 2026-10-17.

Caption grade requires zero critical false claims under adversarial probing,
so these are not happy-path tests. Each one is a way the sentence could reach
a player when it is not true, and the measured reason it matters:

  * a king walking to the middle with a full board -- 42 of 122 fires, and
    the advice there is how a player gets mated
  * a central pawn move with no enemy pawn anywhere near it -- 122 of 177
    fires, where the word "break" is a lie
  * a correction with nobody to check it -- 1 in 8 of them names an
    improvement a depth-18 look does not back
  * a detector with sentences written but no permission -- the words existing
    must never be what lets a detector speak
"""
import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_concept_sentences import (  # noqa: E402
    APPLIED,
    CONCEPT_SENTENCES,
    ENDGAME_PIECE_LIMIT,
    PRIORITY,
    WRONG,
    concept_sentence_for_move,
    may_speak,
    pick_concept_sentence,
)

START = chess.Board()
# Two kings and nothing else: unambiguously an endgame. (An earlier fixture
# here put the kings on adjacent squares and was not a legal position at all.)
ENDGAME = chess.Board("8/8/8/4k3/8/8/5K2/8 w - - 0 40")
# Both kings, both queens, both rooks, a full set of pawns: not an endgame.
MIDDLEGAME = chess.Board("r2q1rk1/pppb1ppp/2np1n2/4p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 9")


def _yes(board, move, colour):
    return True


def _no(board, move, colour):
    return False


# ---------------------------------------------------------------- permission

def test_permission_comes_from_the_quality_table_not_from_this_file():
    """Sentences exist for seven detectors; six have earned caption grade.
    opening_development_with_tempo is correct on all 20 of its fires and is
    short of the 50-fire floor, so having words must not let it speak."""
    assert "opening_development_with_tempo" in CONCEPT_SENTENCES
    assert may_speak("opening_development_with_tempo") is False

    board = chess.Board()
    said = concept_sentence_for_move(
        skill_id="opening_development_with_tempo",
        outcome=APPLIED,
        board_before=board,
        move=board.parse_san("Nf3"),
        user_color=chess.WHITE,
    )
    assert said is None


def test_the_six_that_earned_it_may_speak():
    for skill_id in (
        "coached_development",
        "opening_center",
        "opening_castling",
        "concept_rook_open_file",
        "endgame_king_centralization",
        "concept_central_pawn_break",
    ):
        assert may_speak(skill_id) is True, skill_id


def test_an_unknown_detector_says_nothing():
    board = chess.Board()
    assert concept_sentence_for_move(
        skill_id="concept_invented_just_now",
        outcome=APPLIED,
        board_before=board,
        move=board.parse_san("e4"),
        user_color=chess.WHITE,
    ) is None


# ---------------------------------------------------------- the king's gate

def test_the_king_stays_silent_with_a_full_board():
    """The measured failure: 42 of 122 fires happen with 13 to 21 pieces on
    the board. Praising a king walk to the middle there is how a player gets
    mated, and no rewording fixes it."""
    assert len(MIDDLEGAME.piece_map()) > ENDGAME_PIECE_LIMIT
    board = MIDDLEGAME.copy()
    move = board.parse_san("Kh1")
    assert concept_sentence_for_move(
        skill_id="endgame_king_centralization",
        outcome=APPLIED,
        board_before=board,
        move=move,
        user_color=chess.WHITE,
    ) is None


def test_the_king_speaks_once_the_board_has_emptied():
    board = ENDGAME.copy()
    assert len(board.piece_map()) <= ENDGAME_PIECE_LIMIT
    said = concept_sentence_for_move(
        skill_id="endgame_king_centralization",
        outcome=APPLIED,
        board_before=board,
        move=board.parse_san("Ke3"),
        user_color=chess.WHITE,
    )
    assert said is not None
    assert "middle" in said["sentence"]


# ------------------------------------------------------- the pawn-break gate

def test_a_central_pawn_move_with_no_enemy_pawn_near_it_is_not_a_break():
    """122 of 177 fires have no enemy pawn in contact. Calling those a break
    tells the player something that did not happen."""
    board = chess.Board("4k3/8/8/8/8/8/3P4/4K3 w - - 0 40")
    said = concept_sentence_for_move(
        skill_id="concept_central_pawn_break",
        outcome=APPLIED,
        board_before=board,
        move=board.parse_san("d4"),
        user_color=chess.WHITE,
    )
    assert said is None


def test_a_pawn_that_really_does_meet_theirs_may_speak():
    board = chess.Board("4k3/8/8/4p3/8/8/3P4/4K3 w - - 0 40")
    said = concept_sentence_for_move(
        skill_id="concept_central_pawn_break",
        outcome=APPLIED,
        board_before=board,
        move=board.parse_san("d4"),   # black's e5 pawn now meets it
        user_color=chess.WHITE,
    )
    assert said is not None


def test_a_pawn_CAPTURE_stays_silent_today_and_that_is_a_known_gap():
    """The gate asks whether enemy pawns meet the pawn AFTER the move, and a
    capture removes the pawn it met -- so dxe4, exd4 and friends never pass,
    even though a capture in the centre is the clearest break there is.

    This is the behaviour that was MEASURED (55 of 177 fires), so it is the
    behaviour that ships. Widening the gate to count captures changes the
    population and therefore needs its own measurement before it is allowed
    to speak; until then the detector stays quiet rather than guessing."""
    board = chess.Board("4k3/2p5/8/8/8/8/3P4/4K3 w - - 0 40")
    board.push_san("d4")
    board.push_san("c5")
    assert concept_sentence_for_move(
        skill_id="concept_central_pawn_break",
        outcome=APPLIED,
        board_before=board,
        move=board.parse_san("dxc5"),
        user_color=chess.WHITE,
    ) is None


# ------------------------------------------------------------- corrections

def test_a_correction_with_nobody_to_check_it_stays_silent():
    """Measured: 1 correction in 8 names an improvement a depth-18 look does
    not back. Absent a verifier the honest output is nothing, not a guess."""
    board = chess.Board()
    assert concept_sentence_for_move(
        skill_id="coached_development",
        outcome=WRONG,
        board_before=board,
        move=board.parse_san("a3"),
        user_color=chess.WHITE,
        verify_correction=None,
    ) is None


def test_a_correction_the_verifier_refuses_stays_silent():
    board = chess.Board()
    assert concept_sentence_for_move(
        skill_id="coached_development",
        outcome=WRONG,
        board_before=board,
        move=board.parse_san("a3"),
        user_color=chess.WHITE,
        verify_correction=_no,
    ) is None


def test_a_verified_correction_speaks_and_explains_itself():
    board = chess.Board()
    said = concept_sentence_for_move(
        skill_id="coached_development",
        outcome=WRONG,
        board_before=board,
        move=board.parse_san("a3"),
        user_color=chess.WHITE,
        verify_correction=_yes,
    )
    assert said is not None
    assert said["outcome"] == WRONG
    # A correction without a why is a verdict, not coaching.
    assert said["principle"]
    assert said["principle"] in said["text"]


def test_a_verifier_that_raises_does_not_leak_a_correction():
    def boom(board, move, colour):
        raise RuntimeError("engine died")

    board = chess.Board()
    assert concept_sentence_for_move(
        skill_id="coached_development",
        outcome=WRONG,
        board_before=board,
        move=board.parse_san("a3"),
        user_color=chess.WHITE,
        verify_correction=boom,
    ) is None


# ---------------------------------------------------------------- collisions

def test_one_sentence_per_move_even_when_several_fire():
    """About one firing move in nine draws two detectors, and the pairs are
    near-synonyms, so two sentences would read as repetition."""
    board = chess.Board()
    said = pick_concept_sentence(
        outcomes=[("coached_development", APPLIED), ("opening_center", APPLIED)],
        board_before=board,
        move=board.parse_san("Nf3"),
        user_color=chess.WHITE,
    )
    assert said is not None
    assert said["skill_id"] == "coached_development"  # more specific wins


def test_a_correction_outranks_a_compliment_on_the_same_move():
    board = chess.Board()
    said = pick_concept_sentence(
        outcomes=[("opening_center", APPLIED), ("coached_development", WRONG)],
        board_before=board,
        move=board.parse_san("e4"),
        user_color=chess.WHITE,
        verify_correction=_yes,
    )
    assert said is not None
    assert said["outcome"] == WRONG


def test_permission_beats_priority():
    """opening_development_with_tempo sits above coached_development in the
    priority order and has no permission, so the promoted one must speak."""
    assert PRIORITY.index("opening_development_with_tempo") < PRIORITY.index(
        "coached_development")
    board = chess.Board()
    said = pick_concept_sentence(
        outcomes=[
            ("opening_development_with_tempo", APPLIED),
            ("coached_development", APPLIED),
        ],
        board_before=board,
        move=board.parse_san("Nf3"),
        user_color=chess.WHITE,
    )
    assert said is not None
    assert said["skill_id"] == "coached_development"


def test_nothing_fired_means_nothing_said():
    board = chess.Board()
    assert pick_concept_sentence(
        outcomes=[],
        board_before=board,
        move=board.parse_san("e4"),
        user_color=chess.WHITE,
    ) is None


# --------------------------------------------------------------- the voice

@pytest.mark.parametrize("skill_id", sorted(CONCEPT_SENTENCES))
def test_every_sentence_keeps_the_voice(skill_id):
    for outcome, (said, principle) in CONCEPT_SENTENCES[skill_id].items():
        both = said + " " + principle
        # No figures in player-facing text.
        assert not any(ch.isdigit() for ch in both), (skill_id, outcome)
        # Every sentence ends on something usable in a game we never see.
        assert principle.endswith("."), (skill_id, outcome)
        assert said.endswith("."), (skill_id, outcome)
        # No tally of past failures.
        for banned in ("again", "as usual", "every time", "always do this"):
            assert banned not in both.lower(), (skill_id, outcome, banned)


# ------------------------------------------------- not the same idea twice

def test_the_sentence_is_dropped_when_the_caption_already_said_it():
    """Measured over 12 rendered reviews: 6 of 35 sentences landed under a
    caption making the same point, every one of them "you took the middle"
    under an opening-intro caption that had just said "White takes a share of
    the center". A second voice saying the same thing is not a second idea."""
    from services.caption_concept_sentences import already_said

    assert already_said("R_TIER2_center→R_PROMOTED_opening_intro", "opening_center") is True
    assert already_said("distilled:good_rook_open_file", "concept_rook_open_file") is True


def test_an_unrelated_caption_leaves_the_sentence_alone():
    from services.caption_concept_sentences import already_said

    # The most common rule over those sentences, and it says nothing about
    # what the move achieved -- only that it was the engine's pick.
    assert already_said("distilled:good_was_best", "opening_center") is False
    assert already_said("R12_blunder→OPENING", "coached_development") is False
    assert already_said(None, "opening_center") is False
    assert already_said("", "opening_center") is False


def test_a_detector_with_no_measured_clash_is_not_silenced_on_a_guess():
    """Only detectors with an observed overlap are listed. Guessing at the
    rest would drop sentences for no reason."""
    from services.caption_concept_sentences import already_said

    assert already_said("distilled:anything_at_all", "opening_castling") is False


def test_the_five_drafted_on_2026_10_18_are_inert_until_evidence_clears():
    """Words exist for them so they can be measured against the sentence they
    would actually say. Words must never be what lets a detector speak."""
    board = chess.Board()
    for skill_id in ("concept_rook_seventh", "endgame_create_passed_pawn",
                     "concept_knight_outpost", "endgame_opposition",
                     "opening_development_with_tempo"):
        assert skill_id in CONCEPT_SENTENCES, skill_id
        assert may_speak(skill_id) is False, skill_id
        assert concept_sentence_for_move(
            skill_id=skill_id,
            outcome=APPLIED,
            board_before=board,
            move=board.parse_san("Nf3"),
            user_color=chess.WHITE,
        ) is None, skill_id

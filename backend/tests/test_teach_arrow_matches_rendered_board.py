"""The arrows must describe the board the card is showing.

Reported 2026-09-22 on an opponent card: "Opponent's b4 is a major blunder.
Play Qe7 -- it attacks the queen on h7", drawn with an arrow at White's queen
on h7. "Qe7" was legal for both sides, so the picture and the words named
different moves while looking like one.

The review board renders fen_after = board_before + the PLAYED move. Any
picture computed on a different position is describing something the player
cannot see.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_pipeline import (  # noqa: E402
    _check_attack_arrows,
    _reply_attack_arrows,
)


def _arrow_pairs(arrows):
    return {(a["from"], a["to"]) for a in arrows}


# --- the helper draws on the board it was handed ---------------------------

# Both sides can play "Qe7" here. White's is Qh7-e7; Black's is Qd8-e7+, which
# checks down the e-file and attacks the white queen still on h7. Only Black's
# exists on the board the card renders.
AMBIGUOUS = "k2q4/7Q/1p6/2N5/8/8/PP4PP/4K3 w - - 0 1"


def test_the_reply_picture_is_built_on_the_board_after_their_move():
    before = chess.Board(AMBIGUOUS)
    played = before.parse_san("b4")
    arrows = _reply_attack_arrows(before, played, "Qe7+")
    pairs = _arrow_pairs(arrows)

    # Move the queen d8-e7; from e7 it hits the queen on h7 AND the knight on
    # c5, and checks the king on e1. Both targets are drawn -- the move forks
    # them, and showing one of the two would hide what makes it strong.
    assert pairs == {
        ("d8", "e7"), ("e7", "h7"), ("e7", "c5"), ("e7", "e1"),
    }, pairs


def test_no_arrow_starts_at_the_opponents_queen():
    """The reported symptom, stated as an assertion.

    The opponent's queen sits on h7. Every arrow on this card belongs to our
    reply, so none of them may start there.
    """
    before = chess.Board(AMBIGUOUS)
    played = before.parse_san("b4")
    assert before.piece_at(chess.H7).symbol() == "Q"
    for a in _reply_attack_arrows(before, played, "Qe7+"):
        assert a["from"] != "h7", f"arrow drawn from the opponent's queen: {a}"


def test_the_opponents_own_best_move_is_not_what_gets_drawn():
    """Feeding the mover's best move to the old path describes another board."""
    before = chess.Board(AMBIGUOUS)
    white_qe7 = before.parse_san("Qe7")
    assert white_qe7.from_square == chess.H7
    reply_pairs = _arrow_pairs(
        _reply_attack_arrows(before, before.parse_san("b4"), "Qe7+")
    )
    old_pairs = _arrow_pairs(_check_attack_arrows(before, white_qe7.uci()))
    assert reply_pairs != old_pairs


def test_a_reply_that_is_illegal_after_their_move_draws_nothing():
    before = chess.Board(AMBIGUOUS)
    played = before.parse_san("b4")
    assert _reply_attack_arrows(before, played, "Nf6") == []
    assert _reply_attack_arrows(before, played, "totally not san") == []
    assert _reply_attack_arrows(before, played, None) == []
    assert _reply_attack_arrows(before, None, "Qe7") == []
    assert _reply_attack_arrows(None, played, "Qe7") == []


def test_the_same_san_means_two_different_moves_by_side():
    """The exact ambiguity behind the report."""
    before = chess.Board(AMBIGUOUS)
    white_qe7 = before.parse_san("Qe7")
    assert white_qe7.from_square == chess.H7

    after = before.copy()
    after.push(before.parse_san("b4"))
    black_qe7 = after.parse_san("Qe7+")
    assert black_qe7.from_square == chess.D8
    assert black_qe7.from_square != white_qe7.from_square


# --- the picture only fires where it is true -------------------------------

def test_the_check_picture_needs_a_check():
    """Right-or-silent: a quiet best move draws nothing."""
    board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert _check_attack_arrows(board, "e2e4") == []


def test_the_check_picture_needs_a_winnable_target():
    """A bare check with nothing hanging is not the lesson."""
    board = chess.Board("4k3/8/8/8/8/8/8/4K1R1 w - - 0 1")
    assert _check_attack_arrows(board, "g1g8") == []


def test_an_illegal_uci_is_silent_not_an_exception():
    board = chess.Board("4k3/8/8/8/8/8/8/4K1R1 w - - 0 1")
    assert _check_attack_arrows(board, "a1a8") == []
    assert _check_attack_arrows(board, "nonsense") == []
    assert _check_attack_arrows(board, "") == []
    assert _check_attack_arrows(None, "g1g8") == []


def test_every_arrow_names_real_squares():
    """A malformed square string renders as a stray line on the board."""
    before = chess.Board(AMBIGUOUS)
    played = before.parse_san("b4")
    for a in _reply_attack_arrows(before, played, "Qe7+"):
        assert len(a["from"]) == 2 and len(a["to"]) == 2
        assert a["from"][0] in "abcdefgh" and a["from"][1] in "12345678"
        assert a["to"][0] in "abcdefgh" and a["to"][1] in "12345678"
        assert a.get("teach") is True


# --- the regression, stated as a board fact --------------------------------

# White's best is Qd1-d5+, forking the king on g8 and the loose rook on a8.
# White instead plays b4. The card renders the position after b4, where d5 is
# an empty square.
MISSED_FORK = "r5k1/7p/8/8/8/8/1P4PP/3Q2K1 w - - 0 1"


def test_arrows_for_a_move_that_was_not_played_start_on_an_empty_square():
    """Why feeding best_move_uci to this helper was wrong.

    The picture is computed on board_before + BEST move. The card renders
    board_before + PLAYED move. When those differ, the arrows are anchored to
    a square that holds nothing on the board the player is looking at.
    """
    before = chess.Board(MISSED_FORK)
    best = before.parse_san("Qd5+")
    arrows = _check_attack_arrows(before, best.uci())
    assert _arrow_pairs(arrows) == {("d5", "a8"), ("d5", "g8")}

    rendered = before.copy()
    rendered.push(before.parse_san("b4"))
    for a in arrows:
        assert rendered.piece_at(chess.parse_square(a["from"])) is None, (
            f"arrow starts at {a['from']}, which is empty on the rendered board"
        )


def test_the_same_picture_is_honest_when_the_move_was_actually_played():
    """The 238 of 514 cards that were fine, and stay fine."""
    before = chess.Board(MISSED_FORK)
    best = before.parse_san("Qd5+")
    arrows = _check_attack_arrows(before, best.uci())

    rendered = before.copy()
    rendered.push(best)
    for a in arrows:
        assert rendered.piece_at(chess.parse_square(a["from"])) is not None


# --- the tag has to survive the dedupe -------------------------------------

def test_a_picture_another_rule_already_drew_still_renders():
    """The fork board came out empty.

    The fork rule emits d5->a8 and d5->g8 with no "teach" tag. The check
    picture emits the same two pairs WITH the tag. The dedupe dropped the
    tagged copies as already-present, and the suppression filter then removed
    the untagged originals for having no tag -- so the arrows Mohit asked for
    were deleted by their own duplicate.
    """
    from services.caption_pipeline import (
        CrossMoveState,
        MoveInputs,
        build_move_teaching_decision,
    )

    before = chess.Board(MISSED_FORK)
    best_uci = before.parse_san("Qd5+").uci()
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=MISSED_FORK, played_san="Qd5+",
            mover_is_user=True, mover_is_white=True, user_color="white",
            full_move_number=1, move_history_san=[],
            best_move_san="Qd5+", best_move_uci=best_uci,
            eval_before_cp=100, eval_after_cp=120, cp_loss=0, opp_cp_loss=0,
            pv_after_played=[], pv_after_best=[],
        ),
        CrossMoveState(),
    )
    pairs = _arrow_pairs(decision.visual.arrows or [])
    assert pairs == {("d5", "a8"), ("d5", "g8")}, pairs
    assert all(a.get("teach") is True for a in decision.visual.arrows)


def test_a_mistake_card_draws_no_picture_of_the_move_not_played():
    from services.caption_pipeline import (
        CrossMoveState,
        MoveInputs,
        build_move_teaching_decision,
    )

    before = chess.Board(MISSED_FORK)
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=MISSED_FORK, played_san="b4",
            mover_is_user=True, mover_is_white=True, user_color="white",
            full_move_number=1, move_history_san=[],
            best_move_san="Qd5+", best_move_uci=before.parse_san("Qd5+").uci(),
            eval_before_cp=100, eval_after_cp=-200, cp_loss=300, opp_cp_loss=0,
            pv_after_played=[], pv_after_best=[],
        ),
        CrossMoveState(),
    )
    rendered = before.copy()
    rendered.push(before.parse_san("b4"))
    for a in decision.visual.arrows or []:
        assert rendered.piece_at(chess.parse_square(a["from"])) is not None, a


# --- the missed win keeps its picture, on its own board --------------------

def test_the_recommended_move_picture_ships_with_the_fen_it_is_true_of():
    """v166 is not deleted, it is relocated.

    Mohit asked for this picture (fb_1c52480b2e9b): the recommended move's
    lines onto what it wins and into the king. It was real teaching drawn over
    the wrong position. It now travels with the board it belongs to, which the
    review page already shows under "What if I played X?".
    """
    from services.caption_pipeline import (
        CrossMoveState,
        MoveInputs,
        build_move_teaching_decision,
    )

    before = chess.Board(MISSED_FORK)
    best_uci = before.parse_san("Qd5+").uci()
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=MISSED_FORK, played_san="b4",
            mover_is_user=True, mover_is_white=True, user_color="white",
            full_move_number=1, move_history_san=[],
            best_move_san="Qd5+", best_move_uci=best_uci,
            eval_before_cp=100, eval_after_cp=-200, cp_loss=300, opp_cp_loss=0,
            pv_after_played=[], pv_after_best=[],
        ),
        CrossMoveState(),
    )
    assert _arrow_pairs(decision.visual.best_move_arrows) == {
        ("d5", "a8"), ("d5", "g8"),
    }
    # And it names the board it is true of -- which is NOT the rendered one.
    expected = before.copy()
    expected.push(before.parse_san("Qd5+"))
    assert decision.visual.best_move_arrows_fen == expected.fen()

    rendered = before.copy()
    rendered.push(before.parse_san("b4"))
    assert decision.visual.best_move_arrows_fen != rendered.fen()

    # Every arrow stands on a real piece of the board it was shipped with.
    proof = chess.Board(decision.visual.best_move_arrows_fen)
    for a in decision.visual.best_move_arrows:
        assert proof.piece_at(chess.parse_square(a["from"])) is not None


def test_the_two_arrow_channels_never_carry_the_same_thing():
    """If the relocated picture leaked back into `arrows`, the bug returns."""
    from services.caption_pipeline import (
        CrossMoveState,
        MoveInputs,
        build_move_teaching_decision,
    )

    before = chess.Board(MISSED_FORK)
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=MISSED_FORK, played_san="b4",
            mover_is_user=True, mover_is_white=True, user_color="white",
            full_move_number=1, move_history_san=[],
            best_move_san="Qd5+", best_move_uci=before.parse_san("Qd5+").uci(),
            eval_before_cp=100, eval_after_cp=-200, cp_loss=300, opp_cp_loss=0,
            pv_after_played=[], pv_after_best=[],
        ),
        CrossMoveState(),
    )
    on_card = _arrow_pairs(decision.visual.arrows or [])
    relocated = _arrow_pairs(decision.visual.best_move_arrows or [])
    assert not (on_card & relocated), on_card & relocated


def test_a_move_that_was_played_needs_no_relocated_copy():
    """It is already on the rendered board, so shipping it twice would
    double-draw it."""
    from services.caption_pipeline import (
        CrossMoveState,
        MoveInputs,
        build_move_teaching_decision,
    )

    before = chess.Board(MISSED_FORK)
    best_uci = before.parse_san("Qd5+").uci()
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=MISSED_FORK, played_san="Qd5+",
            mover_is_user=True, mover_is_white=True, user_color="white",
            full_move_number=1, move_history_san=[],
            best_move_san="Qd5+", best_move_uci=best_uci,
            eval_before_cp=100, eval_after_cp=120, cp_loss=0, opp_cp_loss=0,
            pv_after_played=[], pv_after_best=[],
        ),
        CrossMoveState(),
    )
    assert decision.visual.best_move_arrows == []
    assert decision.visual.best_move_arrows_fen == ""
    assert _arrow_pairs(decision.visual.arrows) == {("d5", "a8"), ("d5", "g8")}


# --- the reply picture has to start on a piece the player can see ----------

def test_the_reply_picture_leads_with_the_move_itself():
    """Otherwise it is a line starting in mid-air.

    _check_attack_arrows draws from the square the piece LANDS on. On our own
    cards that square holds the piece that just moved. On an opponent card the
    reply has not been played, so e7 is empty and the only thing the arrow
    visibly touches is the opponent's queen on h7 -- the complaint all over
    again, with the arrow pointing the other way.
    """
    before = chess.Board(AMBIGUOUS)
    played = before.parse_san("b4")
    arrows = _reply_attack_arrows(before, played, "Qe7+")
    assert arrows

    shown = before.copy()
    shown.push(played)
    first = arrows[0]
    assert (first["from"], first["to"]) == ("d8", "e7"), arrows
    assert shown.piece_at(chess.parse_square(first["from"])) is not None
    # and the attack line still lands on the queen the caption names
    assert ("e7", "h7") in _arrow_pairs(arrows)


def test_the_move_arrow_is_not_drawn_twice():
    """If the attack picture already contains it, adding it again double-draws."""
    before = chess.Board(AMBIGUOUS)
    played = before.parse_san("b4")
    arrows = _reply_attack_arrows(before, played, "Qe7+")
    pairs = [(a["from"], a["to"]) for a in arrows]
    assert len(pairs) == len(set(pairs)), pairs


def test_a_reply_with_no_attack_picture_draws_nothing_at_all():
    """The move arrow alone is not a lesson -- it would put a blue line on
    every opponent card in the game."""
    before = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
    played = before.parse_san("e4")
    assert _reply_attack_arrows(before, played, "Ke7") == []


# --- a threat does not have to be a check to be worth drawing --------------

def test_a_recommended_move_that_only_threatens_still_draws():
    """Mohit 2026-09-23, on an inaccuracy card with an empty board: "did we not
    talk about inaccuracies too? Why is missing there?"

    The card said "Play d5 -- your pawn kicks their knight on c6" and drew
    nothing, because the picture used to require a CHECK. d5 really does attack
    that knight -- SEE 200 -- it just is not a check. A check is what makes a
    threat unanswerable; it is not what makes it worth showing.
    """
    before = chess.Board(
        "r3k2r/pbpp1pp1/1pnbqn1p/4p3/P1BPP3/2P1BN2/1P1N1PPP/R2QK2R b KQkq - 0 1"
    )
    played = before.parse_san("Qe7")
    arrows = _reply_attack_arrows(before, played, "d5")
    assert _arrow_pairs(arrows) == {("d4", "d5"), ("d5", "c6")}

    shown = before.copy()
    shown.push(played)
    # the picture starts on the pawn the player can see
    assert shown.piece_at(chess.D4) is not None
    # and c6 really is a black knight the pawn will attack
    after = shown.copy()
    after.push(shown.parse_san("d5"))
    assert after.piece_at(chess.C6).symbol() == "n"
    assert chess.C6 in after.attacks(chess.D5)


def test_a_quiet_reply_that_threatens_nothing_still_draws_nothing():
    """Coverage is not the goal on its own -- a move arrow with no threat
    behind it would put a line on every opponent card in the game."""
    before = chess.Board("4k3/8/8/8/8/8/4P3/4K3 b - - 0 1")
    played = before.parse_san("Kd8")
    assert _reply_attack_arrows(before, played, "e4") == []


def test_at_most_two_targets_plus_the_check():
    before = chess.Board(AMBIGUOUS)
    arrows = _reply_attack_arrows(before, before.parse_san("b4"), "Qe7+")
    greens = [a for a in arrows if a["color"] == "green"]
    reds = [a for a in arrows if a["color"] == "red"]
    blues = [a for a in arrows if a["color"] == "blue"]
    assert len(blues) == 1 and len(greens) <= 2 and len(reds) <= 1
    assert len(arrows) <= 4

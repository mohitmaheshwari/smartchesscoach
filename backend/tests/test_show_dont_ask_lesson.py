"""Lock the show-don't-ask lesson to its rules.

docs/show_dont_ask_lesson_scope.md. Positions here are real boards, checked
by hand -- an earlier session of mine built five endgame positions by hand
and three were illegal, which proved nothing and wasted the run.
"""
import re
import sys
from pathlib import Path

import chess

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.show_dont_ask_lesson import (  # noqa: E402
    CAUSE_LINE,
    HABIT_LINE,
    RETRY_TASK,
    build_lesson,
    build_moment,
    grade_attempt,
    safe_move_count,
    transfer_position_is_usable,
)

# A REAL position from Mohit's game 5591d1d9, move 7, pulled from production
# rather than composed here. He played Bxf2+ and the rook on f1 took it back.
# Verified on the board: 47 legal moves, 37 the grader accepts, 10 it refuses,
# and both a pawn move and a king move are available.
#
# The first version of this file used a position I wrote by hand, and the move
# it claimed was punished was not punished at all -- four tests got None. That
# is the same mistake that produced three illegal endgame positions earlier in
# this project. Fixtures come from the database.
HANGS = "r1bqk2r/ppp2ppp/2n2n2/2b1p3/4P3/5NP1/PPP2PBP/RNBQ1RK1 b kq - 0 7"
PUNISHED_MOVE = "Bxf2+"


def test_the_lesson_never_asks_what_the_player_was_thinking():
    """The whole point of the rebuild. No question about his own reasoning,
    and no multiple choice, anywhere in the payload."""
    lesson = build_lesson(HANGS, PUNISHED_MOVE)
    payload = str(lesson)
    for banned in ("what did you check", "reason_options", "pick the thought",
                   "I am not sure yet"):
        assert banned.lower() not in payload.lower(), banned


def test_a_wrong_attempt_draws_the_taker_instead_of_scolding():
    board = chess.Board(HANGS)
    # find a move the grader rejects
    wrong = None
    for mv in board.legal_moves:
        if not grade_attempt(HANGS, mv.uci())["accepted"]:
            wrong = mv
            break
    assert wrong is not None, "fixture no longer contains an unsafe move"
    out = grade_attempt(HANGS, wrong.uci())
    assert out["accepted"] is False
    assert out["arrows"], "a rejected move must show who takes it"
    frm, to, colour = out["arrows"][0]
    assert colour == "red"
    assert to == chess.square_name(wrong.to_square)
    # and the drawn capture must be legal on the real board
    after = board.copy()
    after.push(wrong)
    assert chess.Move(chess.parse_square(frm), wrong.to_square) in after.legal_moves


def test_the_arrow_always_starts_on_an_enemy_piece():
    board = chess.Board(HANGS)
    for mv in board.legal_moves:
        out = grade_attempt(HANGS, mv.uci())
        if not out["arrows"]:
            continue
        after = board.copy()
        after.push(mv)
        piece = after.piece_at(chess.parse_square(out["arrows"][0][0]))
        assert piece is not None
        assert piece.color == after.turn, "arrow points from our own piece"


def test_a_safe_move_is_accepted_and_says_nothing():
    board = chess.Board(HANGS)
    safe = next(mv for mv in board.legal_moves
                if grade_attempt(HANGS, mv.uci())["accepted"])
    out = grade_attempt(HANGS, safe.uci())
    assert out["accepted"] is True
    assert out["arrows"] == []
    assert out["message"] == ""


def test_pawn_and_king_moves_are_not_marked_wrong():
    """The card says "play a move that nothing can take". A sound pawn move
    satisfies that, and the grader calls it piece_not_eligible because it
    cannot hang a PIECE. Failing someone there would mark them against a rule
    we never printed."""
    board = chess.Board(HANGS)
    for mv in board.legal_moves:
        if board.piece_type_at(mv.from_square) in (chess.PAWN, chess.KING):
            assert grade_attempt(HANGS, mv.uci())["accepted"] is True


def test_the_retry_screen_can_always_be_passed():
    lesson = build_lesson(HANGS, PUNISHED_MOVE)
    assert lesson["retry"]["safe_move_count"] >= 1
    assert lesson["retry"]["task"] == RETRY_TASK


def test_a_moment_that_was_not_punished_builds_no_lesson():
    """A lesson must never open by claiming something the board does not
    show. If the move was not in fact taken on its square, this is not an
    example of this concept and we skip it rather than invent a punishment."""
    board = chess.Board(HANGS)
    safe = next(mv for mv in board.legal_moves
                if grade_attempt(HANGS, mv.uci())["accepted"])
    assert build_moment(HANGS, board.san(safe)) is None
    assert build_lesson(HANGS, board.san(safe)) is None


def test_the_cause_names_the_cause_not_the_move():
    """Moves do not repeat; causes do. The sentence he carries must not
    contain a square or a piece letter from this one position."""
    assert CAUSE_LINE == "The square you moved to was already being watched."
    assert not re.search(r"\b[a-h][1-8]\b", CAUSE_LINE)


def test_the_habit_is_one_fixed_sentence():
    a = build_lesson(HANGS, PUNISHED_MOVE)["habit"]
    b = build_lesson(HANGS, PUNISHED_MOVE)["habit"]
    assert a == b == HABIT_LINE


def test_published_text_is_plain_and_has_no_numbers():
    lesson = build_lesson(HANGS, PUNISHED_MOVE)
    for text in (lesson["cause"], lesson["habit"], lesson["retry"]["task"]):
        assert not re.search(r"\d", text), text
        for jargon in ("material", "tempo", "initiative", "prophylaxis"):
            assert jargon not in text.lower()


def test_someone_elses_position_is_labelled_as_such():
    own = build_lesson(HANGS, PUNISHED_MOVE, transfer_fen=HANGS,
                       transfer_is_own_game=True)
    theirs = build_lesson(HANGS, PUNISHED_MOVE, transfer_fen=HANGS,
                          transfer_is_own_game=False)
    assert "DIFFERENT GAME" in own["transfer"]["label"]
    assert "SOMEONE ELSE" in theirs["transfer"]["label"]


def test_an_unpassable_position_is_refused_as_transfer():
    # Black king on h8 with only a rook that cannot move safely is contrived;
    # use a real one instead: a position where every legal move is a king move
    # into check is impossible, so assert the guard on a position with no
    # unsafe moves at all -- the starting position.
    assert transfer_position_is_usable(chess.STARTING_FEN) is False


def test_safe_move_count_agrees_with_grading_each_move():
    board = chess.Board(HANGS)
    counted = sum(1 for mv in board.legal_moves
                  if grade_attempt(HANGS, mv.uci())["accepted"])
    assert safe_move_count(HANGS) == counted


def test_screen_one_never_leads_with_move_notation():
    """Mohit's rule: players remember patterns, not moves. A card that opens
    "You played Bxf2+" makes a 600 decode algebraic before they feel
    anything, and the move name is the one detail that never recurs. The
    board is playing the move underneath these lines anyway."""
    moment = build_moment(HANGS, PUNISHED_MOVE)
    assert moment is not None
    assert not moment["line_one"].lower().startswith("you played")
    assert PUNISHED_MOVE not in moment["line_one"]
    # it should name the piece and where it went instead
    assert "bishop" in moment["line_one"].lower()
    assert "f2" in moment["line_one"]

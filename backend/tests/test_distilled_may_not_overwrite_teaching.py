"""The distilled coverage net may not overwrite teaching.

Measured 2026-10-14 over 60 games / 3,303 cards with
DISTILLED_CAPTIONS_ENABLED forced both ways (prod runs it ON): of 2,164
caption overrides, ZERO filled a card the rules had left silent, 6
replaced a caption with an empty string, and 246 dropped a named motif,
an opening name, a better-move why-clause or a mate verdict.

The templates have no slot for any of those four, so losing one is
information loss rather than a rewording. These cases are real pairs
from that run.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.caption_pipeline import _distilled_may_replace


def test_fills_a_silent_card():
    """The one thing a coverage net is for."""
    assert _distilled_may_replace("", "Nf3 develops a piece.") is True
    assert _distilled_may_replace("   ", "Nf3 develops a piece.") is True


def test_never_trades_a_REAL_caption_for_silence():
    """A card about this board is not thrown away for an empty one."""
    assert _distilled_may_replace(
        "Rb6. Pins the pawn on b2 to the king.", "", "Rb6") is False


def test_generic_filler_may_be_silenced():
    """156 of the cards this rule kept were verbatim repeats, one of them
    "Your opponent tidys up the king, keeping it safe." 25 times in a
    single game. That is what the decided-position gate exists to
    silence, and Mohit's ruling is that silence beats fake explanation."""
    assert _distilled_may_replace(
        "Your opponent tidys up the king, keeping it safe.", "",
        "Kg2") is True
    assert _distilled_may_replace(
        "You push the h-pawn, claiming a little space.", "", "h4") is True


def test_keeps_the_named_motif():
    """game 03d3e3cb ply14: the rule named the fork, the template said
    only 'leaves your bishop undefended'."""
    assert _distilled_may_replace(
        "Bb2 allows Qxb2 forking your rook on a1 and knight on c3. "
        "Rb1 was better.",
        "Bb2 leaves your bishop on b2 undefended, and after Qxb2 you "
        "simply lose it for nothing; better was Rb1.") is False


def test_a_mate_verdict_alone_is_not_teaching():
    """Measured over 120 re-rendered games: of the 78 cards the mate
    clause saved, 76 were this sentence, repeated down a lost game while
    naming nothing about the position. It does not earn protection, and
    the replacement is often the more useful card. This corrects the case
    the rule was first built on."""
    assert _distilled_may_replace(
        "Raxe3+. Opp is winning by force. Before moving, calculate every "
        "enemy check to the end.",
        "Raxe3+ takes your knight, but your king can take back — an "
        "even trade. Recapture to keep material level.",
        "Raxe3+") is True


def test_keeps_a_mate_claim_about_this_board():
    """A mate claim that names a square is real teaching and still wins."""
    assert _distilled_may_replace(
        "Bxf5 misses a forced win — mate on h7 was there.",
        "Bxf5 takes your knight and nothing takes back.",
        "Bxf5") is False


def test_keeps_the_better_move_why():
    """game 03d3e3cb ply36: 'Qd5 was better — it wins the knight on
    c6' became 'better was Qd5' with no why."""
    assert _distilled_may_replace(
        "Qf8+ lets Bxf8 win your queen on f8. Qd5 was better — it "
        "wins the knight on c6.",
        "Qf8+ leaves your queen on f8 undefended; better was Qd5. Before "
        "you commit a move, check what your opponent can capture.") is False


def test_keeps_the_opening_name():
    """game 2c3367d6 ply0: the authored opening intro became 'e4 is the
    best move in this position'."""
    assert _distilled_may_replace(
        "e4. King's Pawn Opening. White takes a share of the center.",
        "e4 is the best move in this position.") is False


def test_allows_a_plain_reword():
    """88% of the overrides carry none of the four markers; the layer
    still owns those, and several read better for a 600-1500 player."""
    assert _distilled_may_replace(
        "Your opponent posts the knight on a strong central square the "
        "opponent can't easily challenge.",
        "Your opponent brought their knight out into the game with Nc6. "
        "Lesson: bring your pieces out early so they can help you.") is True


def test_allows_replacement_that_keeps_the_marker():
    """Abstention is about LOSS, not about the marker being present."""
    assert _distilled_may_replace(
        "Bb2 allows Qxb2 forking your rook and knight.",
        "Bb2 allows Qxb2, forking the rook on a1 and the knight on c3. "
        "Rb1 held both.") is True


def test_marker_gained_is_fine():
    assert _distilled_may_replace(
        "Nf3 is the best move here.",
        "Nf3 stops the fork on e5.") is True


def test_keeps_the_square_reference():
    """318 of 1,857 overwrites dropped every square. The largest stored
    rule in the corpus, distilled:good_was_best (4,422 cards), says only
    'X is the best move in this position'."""
    assert _distilled_may_replace(
        "Qh5+ — check, and attacks the pawn on h7 too. You attack h7 "
        "more often than they defend it. That is how a weak pawn falls.",
        "Qh5+ is the best move in this position.") is False
    assert _distilled_may_replace(
        "Bg5 threatens the queen on f6.",
        "Bg5 is the best move in this position.") is False
    assert _distilled_may_replace(
        "Nc3 — supports your central pawn on e4.",
        "Nc3 is the best move in this position.") is False


def test_square_may_be_traded_for_an_opening_name():
    """A replacement that pays for the square by naming the opening is an
    upgrade; blocking it to save a square would cost teaching."""
    assert _distilled_may_replace(
        "Nf6 — controls d5, e4, keeping enemy pieces off those squares.",
        "Indian Defense setup. Black delays committing pawns to the centre "
        "and develops pieces first.") is True


def test_neither_side_names_a_square_is_untouched():
    """1,174 of the overwrites name no square either way; the layer still
    owns those."""
    assert _distilled_may_replace(
        "Your opponent tidys up the king.",
        "Your opponent moved their king. Lesson: keep your king safe.") is True


def test_played_move_square_does_not_count_as_board_detail():
    """A pawn move's SAN *is* a square, so "b6. Opp is winning by force."
    would pass a naive square test while naming nothing."""
    assert _distilled_may_replace(
        "b6. Opp is winning by force. Before moving, calculate every "
        "enemy check to the end.",
        "Your opponent played b6, taking more room.", "b6") is True
    # the same sentence about a DIFFERENT square is board detail
    assert _distilled_may_replace(
        "b6. Opp is winning by force — mate lands on g7.",
        "Your opponent played b6, taking more room.", "b6") is False

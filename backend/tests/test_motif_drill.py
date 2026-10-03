"""Tests for the pin and skewer drill. docs/pin_skewer_drill_scope.md

Three things are locked here, and each one is locked because it already went
wrong once or would have gone wrong silently.

THE ALIAS TRAP. `canonical_category` applies the alias map BEFORE looking in
BY_CATEGORY, so while `pin` was aliased onto `missed_tactic` the new pin spec
was unreachable while appearing to exist. Nothing failed. A test now asserts the
category resolves to itself.

THE PRINTED SENTENCE. The pin card claims the front piece is worth less and the
skewer card claims it is worth more. Those are claims about the board. They are
checked by geometry, with a negative control, because a card that lies about the
position is worse than no card.

NO NUMBERS. Every string a player can see is checked for digits and percent
signs. An authored string that drifts never errors by itself.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.lesson_question_spec import (  # noqa: E402
    BY_CATEGORY, canonical_category, get_spec, spec_or_fallback,
)
from services.motif_alignment import alignment_after  # noqa: E402
from services.motif_drill_service import (  # noqa: E402
    MATERIAL_FLOOR_CP, MOTIFS, _hands_over_material,
)

MOTIF_LIST = ("pin", "skewer")


# ── the alias trap ──────────────────────────────────────────────────────

@pytest.mark.parametrize("motif", MOTIF_LIST)
def test_motif_resolves_to_its_own_spec(motif):
    """Not to `missed_tactic`, which is what the removed alias did."""
    assert canonical_category(motif) == motif
    spec = get_spec(motif)
    assert spec is not None, "%s has no spec" % motif
    assert spec.category == motif


@pytest.mark.parametrize("motif", MOTIF_LIST)
def test_motif_question_is_not_the_generic_one(motif):
    generic = spec_or_fallback("missed_tactic").question
    assert get_spec(motif).question != generic


def test_no_spec_category_is_shadowed_by_an_alias():
    """The general form of the bug, so the next category cannot repeat it."""
    for category in BY_CATEGORY:
        assert canonical_category(category) == category, (
            "%r is aliased away and its spec can never be reached" % category)


# ── the printed sentence is true about the board ────────────────────────

def test_pin_is_front_worth_less():
    """Rook attacks a knight with the queen behind it: a pin."""
    # White rook a1 -> e1. Black knight e5, black queen e8.
    board = "4q2k/8/8/4n3/8/8/8/R6K w - - 0 1"
    assert alignment_after(board, "a1e1") == "pin"


def test_skewer_is_bigger_in_front():
    """Rook attacks the queen with the knight behind it: a skewer."""
    board = "4n2k/8/8/4q3/8/8/8/R6K w - - 0 1"
    assert alignment_after(board, "a1e1") == "skewer"


def test_king_in_front_reads_as_skewer():
    """A king is valued above the queen so that this is not a pin."""
    board = "4q3/8/8/4k3/8/8/8/R6K w - - 0 1"
    assert alignment_after(board, "a1e1") == "skewer"


def test_equal_values_are_neither_card():
    """Two rooks on the line: neither sentence would be honest, so None."""
    board = "4r2k/8/8/4r3/8/8/8/R6K w - - 0 1"
    assert alignment_after(board, "a1e1") is None


def test_own_piece_blocks_the_line():
    """A white pawn between the rook and the pair makes no alignment."""
    board = "4q2k/8/8/4n3/8/4P3/8/R6K w - - 0 1"
    assert alignment_after(board, "a1e1") is None


def test_knight_move_makes_no_alignment_card():
    """Knights create no line, so neither sentence can describe what they did."""
    board = "4q2k/8/8/4n3/8/8/8/N6K w - - 0 1"
    assert alignment_after(board, "a1b3") is None


def test_malformed_input_refuses():
    board = "4q2k/8/8/4n3/8/8/8/R6K w - - 0 1"
    assert alignment_after(board, "zzzz") is None
    assert alignment_after(board, "") is None
    assert alignment_after("not a fen", "a1e1") is None


def test_an_illegal_move_refuses():
    """Rb1 is not available to a rook on a1 with the a-file open elsewhere;
    pick a move that is genuinely not legal here and assert the refusal."""
    board = "4q2k/8/8/4n3/8/8/8/R6K w - - 0 1"
    # a rook cannot move diagonally
    assert chess.Move.from_uci("a1b2") not in chess.Board(board).legal_moves
    assert alignment_after(board, "a1b2") is None


def test_negative_control_most_moves_make_no_alignment():
    """If the check passed everything it would be worthless.

    Across every legal move of a position with one real alignment, only a
    minority may produce a card.
    """
    board = "4q2k/8/8/4n3/8/8/8/R6K w - - 0 1"
    legal = [m.uci() for m in chess.Board(board).legal_moves]
    carded = [m for m in legal if alignment_after(board, m) is not None]
    assert carded, "positive control: at least one move must make a card"
    assert len(carded) < len(legal) / 2, (
        "the geometry check fires on %d of %d legal moves; it is not "
        "discriminating" % (len(carded), len(legal)))


# ── the material floor ──────────────────────────────────────────────────

def test_material_floor_rejects_giving_the_piece_away():
    """Rb1 makes a real pin AND loses the rook to cxb1. Not an answer.

    Black knight b4 stands in front of the black queen b8, so the geometry is a
    pin; the black pawn on c2 then takes the rook on b1 for nothing. Both halves
    are asserted, because a case that only failed the floor would not show that
    the floor is what rejected it.
    """
    board = "1q5k/8/8/8/1n6/8/2p5/R6K w - - 0 1"
    assert alignment_after(board, "a1b1") == "pin"
    assert _hands_over_material(board, "a1b1") is True


def test_material_floor_allows_a_safe_move():
    board = "4q2k/8/8/4n3/8/8/8/R6K w - - 0 1"
    assert _hands_over_material(board, "a1e1") is False


def test_material_floor_is_a_pawn():
    """Stated as a constant so a reader does not have to infer the policy."""
    assert MATERIAL_FLOOR_CP == 100


def test_motifs_tuple_matches_what_has_specs():
    assert set(MOTIFS) == set(MOTIF_LIST)
    for motif in MOTIFS:
        assert get_spec(motif) is not None


# ── no numbers in anything a player reads ───────────────────────────────

_DIGIT = re.compile(r"[0-9%]")


@pytest.mark.parametrize("motif", MOTIF_LIST)
def test_no_numbers_in_player_facing_strings(motif):
    spec = get_spec(motif)
    strings = [spec.question, spec.task_line, spec.reason_prompt,
               spec.best_move_question]
    for option in spec.reason_options:
        strings += [option.label, option.belief_lead, option.correction]
    for text in strings:
        if not text:
            continue
        assert not _DIGIT.search(text), (
            "%s shows a number or a percent sign to the player: %r"
            % (motif, text))


@pytest.mark.parametrize("motif", MOTIF_LIST)
def test_reason_options_name_the_line_first(motif):
    """The expected option is the one about seeing the line.

    `expected_reason` is whichever option is listed first, and the route
    shuffles the order before it reaches the player. If a future edit reorders
    the tuple, the drill would start marking the wrong belief as correct
    without failing anything.
    """
    assert get_spec(motif).expected_reason == "saw_the_line"


@pytest.mark.parametrize("motif", MOTIF_LIST)
def test_every_wrong_option_carries_a_correction(motif):
    """A named misconception with no correction is a dead end for the player."""
    for option in get_spec(motif).reason_options[1:]:
        assert option.misconception_id, (
            "%s option %r has no misconception id" % (motif, option.id))
        assert option.correction, (
            "%s option %r names a misconception and does not correct it"
            % (motif, option.id))

"""Regressions for the three findings in Codex's review of 116fbd90.

Each test reproduces a counterexample the reviewer supplied, so the specific
case that the first repair got wrong fails here if it comes back.

    P1  mate transitions must carry direction and outcome
    P1  evaluation loss must not be presented as material given away
    P2  mate involvement must be detected below the 9000cp delta cutoff

Run:
    python -m pytest backend/tests/test_mate_state_and_cost_wording.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import mate_state  # noqa: E402
from services.game_coach_review import _format_cp, compose_story  # noqa: E402
from services.game_coach_summary import (  # noqa: E402
    _blunder_cost_line,
    _cp_to_pieces,
    compute_game_summary,
)

START_FEN_W = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
START_FEN_B = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1"


def _row(mn, san, cp, white_to_move=True, **kw):
    row = {
        "move_number": mn,
        "move": san,
        "cp_loss": cp,
        "best_move": "d4",
        "fen_before": START_FEN_W if white_to_move else START_FEN_B,
        "eval_before": 20,
        "eval_after": 20 - cp,
        "evaluation": "best" if cp == 0 else "blunder",
        "cognitive_gap": None if cp == 0 else "piece_safety",
    }
    row.update(kw)
    return row


def _game(extra=None, white_to_move=True):
    evs = [
        _row(6, "Nf3", 0, white_to_move),
        _row(7, "Bc4", 0, white_to_move),
        _row(8, "b4", 300, white_to_move),
    ]
    if extra:
        evs.extend(extra)
    return evs


# ══════════════════════════════════════════════════════════════════════════
# P1  Mate transitions must preserve direction and outcome
# ══════════════════════════════════════════════════════════════════════════

# mate_info is WHITE-relative and signed: + mates for White, - for Black,
# 0 means the move delivered mate. Verified over 300 production games that
# ended in checkmate -- see services/mate_state for the figures.

@pytest.mark.parametrize("user_color,before,after,expected", [
    # The reviewer's first counterexample: the player ALLOWED a mate. He
    # never had one, so "lost a forced mate" was simply false.
    ("white", None, -3, mate_state.ALLOWED_MATE),
    ("black", None, 3, mate_state.ALLOWED_MATE),
    # The reviewer's second counterexample: the player STILL has a forced
    # mate, just a slower one. Not a loss at all.
    ("white", 3, 13, mate_state.KEPT_MATE),
    ("black", -3, -13, mate_state.KEPT_MATE),
    # Giving up a mate you did hold.
    ("white", 3, None, mate_state.GAVE_UP_MATE),
    ("black", -3, None, mate_state.GAVE_UP_MATE),
    # Delivering it.
    ("white", 1, 0, mate_state.DELIVERED_MATE),
    ("black", -1, 0, mate_state.DELIVERED_MATE),
    # Escaping one that was against you.
    ("white", -2, None, mate_state.ESCAPED_MATE),
    ("black", 2, None, mate_state.ESCAPED_MATE),
    # Turning your own mate into theirs.
    ("white", 4, -2, mate_state.SWAPPED_MATE),
    ("black", -4, 2, mate_state.SWAPPED_MATE),
    # Still being mated: this move did not cause it.
    ("white", -2, -1, mate_state.MATE_INVOLVED),
])
def test_p1_transition_direction_both_colours(user_color, before, after, expected):
    ev = {"cp_loss": 500, "mate_info": {"before": before, "after": after}}
    assert mate_state.mate_transition(ev, user_color) == expected


def test_p1_reviewer_case_one_allowed_not_lost():
    """before 20, after -9970, mate_info before null / after -3, cp_loss 9990.
    White allowed the mate; he did not surrender one of his own."""
    ev = {"cp_loss": 9990, "eval_before": 20, "eval_after": -9970,
          "mate_info": {"before": None, "after": -3}}
    label = mate_state.mate_transition(ev, "white")
    assert label == mate_state.ALLOWED_MATE
    assert _format_cp(9990, mate_transition=label) == mate_state.ALLOWED_MATE
    assert "lost a forced mate" not in label


def test_p1_reviewer_case_two_still_has_mate():
    """before 9970, after 9870, mate_info before 3 / after 13, cp_loss 100.
    The player still has a forced mate, so nothing was lost."""
    ev = {"cp_loss": 100, "eval_before": 9970, "eval_after": 9870,
          "mate_info": {"before": 3, "after": 13}}
    label = mate_state.mate_transition(ev, "white")
    assert label == mate_state.KEPT_MATE
    assert mate_state.costs_the_player(label) is False


@pytest.mark.parametrize("label,costs", [
    (mate_state.GAVE_UP_MATE, True),
    (mate_state.ALLOWED_MATE, True),
    (mate_state.SWAPPED_MATE, True),
    (mate_state.KEPT_MATE, False),
    (mate_state.ESCAPED_MATE, False),
    (mate_state.DELIVERED_MATE, False),
    (mate_state.MATE_INVOLVED, False),
    (None, False),
])
def test_p1_only_adverse_transitions_count_as_a_cost(label, costs):
    assert mate_state.costs_the_player(label) is costs


def test_p1_unknown_direction_is_neutral_not_guessed():
    """8.1% of rows carry mate_info. Without it the direction is unknown, and
    the wording must not invent one."""
    ev = {"cp_loss": 9500, "eval_before": 9970}
    label = mate_state.mate_transition(ev, "white")
    assert label == mate_state.MATE_INVOLVED
    assert "lost" not in label and "allowed" not in label


def test_p1_card_exposes_direction_and_whether_it_cost_him():
    out = compose_story(
        _game([_row(20, "Qxh3+", 9990, eval_after=-9970,
                    mate_info={"before": None, "after": -3})]),
        "0-1", "white", "Italian Game")
    card = next(p for p in out["principles"] if p["move_number"] == 20)
    assert card["mate_transition"] == mate_state.ALLOWED_MATE
    assert card["mate_cost_the_player"] is True
    assert card["cp_loss_label"] == mate_state.ALLOWED_MATE


def test_p1_kept_mate_card_is_not_described_as_a_loss():
    out = compose_story(
        _game([_row(20, "Qh4", 100, eval_before=9970, eval_after=9870,
                    mate_info={"before": 3, "after": 13})]),
        "1-0", "white", "Italian Game")
    card = next((p for p in out["principles"] if p["move_number"] == 20), None)
    if card is not None:          # 100cp is at the principle floor
        assert card["mate_cost_the_player"] is False
        assert "lost" not in card["cp_loss_label"]


# ══════════════════════════════════════════════════════════════════════════
# P1  Evaluation loss is not material given away
# ══════════════════════════════════════════════════════════════════════════

def test_p1_no_material_claim_from_cp_loss():
    """The reviewer's case: _material_leaked_line([{cp_loss: 352}]) returned
    "Material given away: about 3.5 pawns worth" with no board evidence."""
    line = _blunder_cost_line([{"cp_loss": 352}])
    assert "material" not in line.lower()
    # "centipawns" legitimately contains "pawns" -- it is the honest engine
    # unit. What must be absent is the material framing.
    assert " pawns" not in line.lower()
    assert "pawns worth" not in line.lower()
    assert "3.5" not in line
    assert "352 centipawns" in line


@pytest.mark.parametrize("phrase", [
    "material given away", "material leaked", "pawns worth",
    "gives up about", "drops about", "loses about", "costs about",
])
def test_p1_forbidden_misframings_absent(phrase):
    line = _blunder_cost_line([{"cp_loss": 352}, {"cp_loss": 500}])
    assert phrase not in line.lower()


def test_p1_centipawns_is_the_unit_and_the_total_is_right():
    line = _blunder_cost_line([{"cp_loss": 300}, {"cp_loss": 52}])
    assert "352 centipawns" in line


def test_p1_summary_output_makes_no_material_claim():
    out = compute_game_summary(
        _game([_row(9, "Nd5", 400), _row(10, "Ke2", 350),
               _row(11, "Qh5", 300), _row(12, "Bg5", 250)]),
        "0-1", "white", "Italian Game", "timeout")
    joined = " ".join(out.get("context") or [])
    assert "pawns worth" not in joined.lower()
    assert "material given away" not in joined.lower()


# ══════════════════════════════════════════════════════════════════════════
# P2  Mate involvement below the 9000cp cutoff
# ══════════════════════════════════════════════════════════════════════════

def test_p2_reviewer_case_mate_row_under_the_cutoff():
    """before 9970, after 8585, cp_loss 1385, no mate remaining. Partitioning
    on cp_loss >= 9000 counted this as 13.8 pawns of material."""
    row = {"cp_loss": 1385, "eval_before": 9970, "eval_after": 8585}
    assert mate_state.is_mate_related(row) is True
    line = _blunder_cost_line([row])
    assert "13.8" not in line
    assert "1385" not in line, "the mate row must not be summed as a cost"
    assert "forced mate" in line


def test_p2_both_consumers_agree_on_the_same_row():
    """The two repaired consumers disagreed about this row. One shared test
    now decides it for both."""
    row = _row(20, "Qxh3+", 1385, eval_before=9970, eval_after=8585)
    assert mate_state.is_mate_related(row) is True
    out = compose_story(_game([row]), "0-1", "white", "Italian")
    card = next(p for p in out["principles"] if p["move_number"] == 20)
    assert card["cost_is_mate"] is True
    assert "cp" not in card["cp_loss_label"]
    assert "1385" not in _blunder_cost_line([row])


@pytest.mark.parametrize("row,expected", [
    ({"cp_loss": 300}, False),
    ({"cp_loss": 1385, "eval_before": 9970}, True),
    ({"cp_loss": 100, "eval_after": -9840}, True),
    ({"cp_loss": 50, "mate_info": {"before": 3, "after": None}}, True),
    ({"cp_loss": 50, "mate_info": {"before": None, "after": None}}, False),
    ({"cp_loss": 9108}, True),
    ({"cp_loss": 0}, False),
])
def test_p2_detection_is_not_a_delta_cutoff(row, expected):
    assert mate_state.is_mate_related(row) is expected


def test_p2_mixed_blunder_list_splits_correctly():
    rows = [
        {"cp_loss": 300},                                      # material
        {"cp_loss": 1385, "eval_before": 9970},                # mate, small delta
        {"cp_loss": 9108},                                     # mate, big delta
    ]
    line = _blunder_cost_line(rows)
    assert "300 centipawns" in line
    assert "2 of these involved a forced mate" in line


def test_p2_public_summary_excludes_mate_rows_from_the_total():
    """A public-summary regression, not just the helper."""
    out = compute_game_summary(
        _game([_row(9, "Nd5", 400), _row(10, "Ke2", 350), _row(11, "Qh5", 300),
               _row(12, "Qxh3+", 1385, eval_before=9970, eval_after=8585)]),
        "0-1", "white", "Italian Game", "timeout")
    joined = " ".join(out.get("context") or [])
    if "centipawns" in joined:
        assert "2435" not in joined, "mate row must not be summed in"
    assert "13.8" not in joined


def test_p2_cp_to_pieces_still_guards_the_sentinel():
    assert _cp_to_pieces(950) == "a queen"
    assert _cp_to_pieces(9108) == "a forced mate"

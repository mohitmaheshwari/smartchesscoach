"""missed_pin must only fire where the prover backs the caption's claim.

The caption names the pinning piece. A pin that appears because the moved piece
stepped ASIDE is a real pin and a false sentence, so the gate is about what the
words claim, not about whether a pin exists.
"""
from __future__ import annotations

import chess
import pytest

from services.cognitive_gap_subtypes import _pin_is_provable, classify_missed_tactic
from services.detector_quality import QualityGrade, grade_for


def mv(fen, best, cp_loss=250):
    return {"fen_before": fen, "best_move_uci": best, "cp_loss": cp_loss,
            "move": "a3", "evaluation": "mistake"}


# ── the gate itself ───────────────────────────────────────────────────

def test_a_pin_made_by_the_moved_piece_is_provable():
    """Ra1-e1: the knight on e5 is then pinned to the king on e8.

    Verified against the prover and the detector before being written down.
    The first fixture here was the Ruy Lopez Bb5 "pin", which is not a pin at
    all -- d7 blocks the diagonal, so the ray ends on a pawn and the shape is a
    skewer. Chess intuition is not a fixture.
    """
    board = chess.Board("4k3/8/8/4n3/8/8/8/R5K1 w - - 0 1")
    assert _pin_is_provable(board, "a1e1") is True


def test_a_move_that_makes_no_pin_is_not_provable():
    board = chess.Board("4k3/8/8/4n3/8/8/8/R5K1 w - - 0 1")
    assert _pin_is_provable(board, "g1f1") is False


def test_an_illegal_or_unparseable_move_fails_closed():
    board = chess.Board()
    assert _pin_is_provable(board, "e4e5") is False
    assert _pin_is_provable(board, "not-a-move") is False
    assert _pin_is_provable(board, None) is False


# ── what the classifier does with it ──────────────────────────────────

def test_the_label_is_given_when_the_prover_backs_it():
    subtype, severity = classify_missed_tactic(
        mv("4k3/8/8/4n3/8/8/8/R5K1 w - - 0 1", "a1e1"), None, None)
    assert subtype == "missed_pin"
    assert severity in ("minor", "moderate", "critical")


def test_coverage_is_not_lost_when_the_gate_refuses(monkeypatch):
    """The 7% the gate drops must still reach the player as a generic tactic.

    Silence would be a worse outcome than a less specific name.
    """
    import services.cognitive_gap_subtypes as mod
    monkeypatch.setattr(mod, "_detect_tactic_on_move", lambda b, m: "pin")
    monkeypatch.setattr(mod, "_pin_is_provable", lambda b, m: False)
    subtype, _ = classify_missed_tactic(
        mv("4k3/8/8/4n3/8/8/8/R5K1 w - - 0 1", "g1f1", cp_loss=250), None, None)
    assert subtype == "missed_generic_tactic", \
        "a refused pin fell silent instead of falling through"


def test_a_refused_pin_below_the_generic_bar_says_nothing_rather_than_guessing(monkeypatch):
    import services.cognitive_gap_subtypes as mod
    monkeypatch.setattr(mod, "_detect_tactic_on_move", lambda b, m: "pin")
    monkeypatch.setattr(mod, "_pin_is_provable", lambda b, m: False)
    subtype, _ = classify_missed_tactic(
        mv("4k3/8/8/4n3/8/8/8/R5K1 w - - 0 1", "g1f1", cp_loss=50), None, None)
    assert subtype is None


def test_the_gate_does_not_swallow_the_other_motifs(monkeypatch):
    """Pin returns early through a different path now; the siblings must be
    untouched by that."""
    import services.cognitive_gap_subtypes as mod
    for tactic, expected in (("fork", "missed_fork"),
                             ("skewer", "missed_skewer"),
                             ("discovered_attack", "missed_discovered_attack")):
        monkeypatch.setattr(mod, "_detect_tactic_on_move",
                            lambda b, m, t=tactic: t)
        subtype, _ = classify_missed_tactic(
            mv("4k3/8/8/4n3/8/8/8/R5K1 w - - 0 1", "a1e1"), None, None)
        assert subtype == expected


# ── the promotion ─────────────────────────────────────────────────────

def test_missed_pin_is_plan_grade_like_its_siblings():
    assert grade_for("gap:missed_tactic:missed_pin") == QualityGrade.PLAN


def test_the_three_aligned_motifs_all_sit_at_the_same_grade():
    """fork, skewer and pin are produced by one function and proved by one
    prover. A grade split between them was an accident, not a decision."""
    grades = {name: grade_for("gap:missed_tactic:missed_%s" % name)
              for name in ("fork", "skewer", "pin")}
    assert len(set(grades.values())) == 1, grades

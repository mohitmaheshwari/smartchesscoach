"""A mate swing is about the king or the tactic, never "oversight".

`docs/move_classification_from_gold_scope.md` §1, amendment 2, signed off
2026-09-18. One line in `analysis_interpreter` assigned TACTICAL_OVERSIGHT to
every missed mate, and it is the single largest source of mislabelling in the
product.

Measured on production, 1,339 stored `tactical_oversight` moves:

    49.4%  had mate and lost it      -> belongs to missed_tactic
     4.0%  allowed a NEW mate        -> belongs to king_safety
    46.4%  no mate involved          -> genuinely not a mate swing
     0.3%  already lost before the move

It is also why that bucket's average cp_loss reads 7,524 — those are mate
scores, not oversights — and why 81% of its `generic_oversight` subtype is a
mate swing when sampled independently.

The allowed-mate half never had a rule at all: the missed-mate trigger only
fires when a mate existed BEFORE the move, so a player walking into one fell
through to whatever the generic gap analysis guessed.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import analysis_interpreter as ai  # noqa: E402

SOURCE = (BACKEND / "analysis_interpreter.py").read_text(encoding="utf-8")


def test_a_missed_mate_is_a_missed_tactic_not_an_oversight():
    trigger = SOURCE[SOURCE.index("# TRIGGER 2: the mate gate."):]
    trigger = trigger[: trigger.index("# TRIGGER 3")]
    assert "cognitive_gap = GAP_MISSED_TACTIC" in trigger
    assert "TACTICAL_OVERSIGHT" not in trigger.replace(
        "This line used to assign TACTICAL_OVERSIGHT", ""), (
        "the missed-mate branch must no longer assign tactical_oversight"
    )


def test_allowing_a_mate_is_king_safety():
    """The half that had no rule at all."""
    trigger = SOURCE[SOURCE.index("# TRIGGER 2: the mate gate."):]
    trigger = trigger[: trigger.index("# TRIGGER 3")]
    assert "cognitive_gap = GAP_KING_SAFETY" in trigger
    assert 'mate_info.get("after") is not None' in trigger, (
        "an allowed mate has no mate BEFORE the move, so the missed-mate "
        "trigger can never see it"
    )


def test_it_uses_the_string_constants_not_the_enum():
    """`CognitiveGap` has no MISSED_TACTIC and no KING_SAFETY.

    Its members are HANGING_PIECE_BLINDNESS, KING_SAFETY_NEGLECT and so on --
    a different vocabulary, noted at the top of analysis_interpreter. Writing
    `CognitiveGap.MISSED_TACTIC.value` raises AttributeError at runtime, which
    a source-only test would never catch, so this asserts on the enum itself.
    """
    from cognitive_gap_service import CognitiveGap

    assert not hasattr(CognitiveGap, "MISSED_TACTIC")
    assert not hasattr(CognitiveGap, "KING_SAFETY")
    assert ai.GAP_MISSED_TACTIC == "missed_tactic"
    assert ai.GAP_KING_SAFETY == "king_safety"


def test_the_gate_runs_before_the_turning_point_trigger():
    """Trigger 3 re-runs the generic gap analysis and would overwrite us."""
    gate = SOURCE.index("# TRIGGER 2: the mate gate.")
    turning = SOURCE.index("# TRIGGER 3: Turning Point")
    assert gate < turning


def test_a_position_with_no_mate_is_left_alone():
    """46.4% of the bucket. The gate must not widen into ordinary mistakes."""
    trigger = SOURCE[SOURCE.index("# TRIGGER 2: the mate gate."):]
    trigger = trigger[: trigger.index("# TRIGGER 3")]
    # both halves are guarded on mate_info being present
    assert trigger.count("if mate_info and") == 2


def test_the_scope_records_this_decision():
    scope = (BACKEND.parent / "docs" /
             "move_classification_from_gold_scope.md").read_text(encoding="utf-8")
    assert "SIGNED OFF 2026-09-18" in scope
    assert "Mate gate" in scope

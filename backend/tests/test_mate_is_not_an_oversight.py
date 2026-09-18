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
    """The half that had no rule at all.

    Asserted on behaviour rather than on source text since the rule moved into
    `mate_gate_label` -- shared so the backfill of 7,797 stored labels cannot
    drift from the live path.
    """
    trigger = SOURCE[SOURCE.index("# TRIGGER 2: the mate gate."):]
    trigger = trigger[: trigger.index("# TRIGGER 3")]
    assert "cognitive_gap = GAP_KING_SAFETY" in trigger

    # An allowed mate has NO mate before the move, so the missed-mate half can
    # never see it. This is the case that used to fall through to a guess.
    assert ai.mate_gate_label({"before": None, "after": -3}) == "king_safety"
    # Already being mated before the move is not something this move caused.
    assert ai.mate_gate_label({"before": -2, "after": -3}) is None


def test_the_missed_mate_half_tolerates_a_slower_mate():
    """Mate in 3 becoming mate in 4 is still winning; it is not the error."""
    assert ai.mate_gate_label({"before": 3, "after": 4}) is None
    assert ai.mate_gate_label({"before": 3, "after": 8}) == "missed_tactic"
    assert ai.mate_gate_label({"before": 3, "after": None}) == "missed_tactic"


def test_the_backfill_and_the_live_path_share_one_predicate():
    """The whole reason the rule is a module-level function.

    A second copy inside the backfill script would be correct the day it was
    written and wrong the first time this rule changed.
    """
    script = (BACKEND / "scripts" / "backfill_mate_gate_labels.py").read_text(
        encoding="utf-8")
    assert "from analysis_interpreter import mate_gate_label" in script
    assert "GAP_MISSED_TACTIC" not in script.replace(
        "# no local copy of GAP_MISSED_TACTIC", ""), (
        "the script must not restate the gate's own constants"
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
    for mate_info in (None, {}, {"before": None, "after": None}):
        assert ai.mate_gate_label(mate_info) is None, mate_info


def test_a_malformed_mate_info_does_not_take_down_an_analysis_run():
    assert ai.mate_gate_label({"before": "3", "after": None}) is None


def test_the_scope_records_this_decision():
    scope = (BACKEND.parent / "docs" /
             "move_classification_from_gold_scope.md").read_text(encoding="utf-8")
    assert "SIGNED OFF 2026-09-18" in scope
    assert "Mate gate" in scope

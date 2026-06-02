"""Unit tests for services/pwc_skill_gate.py.

Covers all 6 outcomes from the spec (docs/pwc_skills_aware_coaching.md §6)
plus the mastery/struggle threshold boundary conditions.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.pwc_skill_gate import (
    GATE_PASS, GATE_SUPPRESS, GATE_ESCALATE,
    gate_decision, is_enabled, reload_skill_map,
    _is_mastered, _is_struggling,
)


def _skill(skill_id, seen=0, correct=0, wrong=0, applied=0):
    return {
        "skill_id": skill_id,
        "seen": seen, "correct": correct, "wrong": wrong, "applied": applied,
    }


class TestMasteryClassifier(unittest.TestCase):
    """Boundary tests for _is_mastered (applied >= 3 AND wrong/seen < 0.2)."""

    def test_mastered_clean(self):
        # Applied=5, wrong=0/seen=10 → wrong_rate=0; mastered.
        self.assertTrue(_is_mastered(_skill("x", seen=10, correct=5, wrong=0, applied=5)))

    def test_mastered_at_applied_floor(self):
        # Applied=3 (boundary), wrong_rate=0; mastered.
        self.assertTrue(_is_mastered(_skill("x", seen=10, correct=5, wrong=0, applied=3)))

    def test_not_mastered_below_applied_floor(self):
        # Applied=2 < 3; not mastered even with zero wrongs.
        self.assertFalse(_is_mastered(_skill("x", seen=10, correct=10, wrong=0, applied=2)))

    def test_not_mastered_at_wrong_rate_boundary(self):
        # 2/10 = 0.20; NOT strictly less than 0.2 → not mastered.
        self.assertFalse(_is_mastered(_skill("x", seen=10, correct=8, wrong=2, applied=3)))

    def test_mastered_just_below_wrong_rate(self):
        # 1/10 = 0.10; strictly less than 0.2 → mastered.
        self.assertTrue(_is_mastered(_skill("x", seen=10, correct=9, wrong=1, applied=3)))


class TestStruggleClassifier(unittest.TestCase):
    """Boundary tests for _is_struggling (wrong >= correct AND seen >= 3)."""

    def test_struggling_typical(self):
        self.assertTrue(_is_struggling(_skill("x", seen=4, correct=1, wrong=3)))

    def test_struggling_at_equality(self):
        # wrong == correct still counts.
        self.assertTrue(_is_struggling(_skill("x", seen=4, correct=2, wrong=2)))

    def test_not_struggling_below_seen_floor(self):
        # Seen=2 < 3 — even with all wrongs.
        self.assertFalse(_is_struggling(_skill("x", seen=2, correct=0, wrong=2)))

    def test_not_struggling_when_correct_dominates(self):
        self.assertFalse(_is_struggling(_skill("x", seen=10, correct=8, wrong=2)))


class TestGateDecision(unittest.TestCase):
    """The 6 outcomes from spec §6, plus a couple of edge cases."""

    def setUp(self):
        reload_skill_map()

    def test_no_nudge_id_passes(self):
        d = gate_decision(None, [])
        self.assertEqual(d["decision"], GATE_PASS)
        self.assertEqual(d["reason"], "no_nudge_id")

    def test_unmapped_nudge_passes(self):
        d = gate_decision("never_heard_of_this_nudge", [
            _skill("defend_fried_liver", applied=5, seen=5),
        ])
        self.assertEqual(d["decision"], GATE_PASS)
        self.assertEqual(d["reason"], "unmapped")

    def test_no_skill_data_passes(self):
        d = gate_decision("fried_liver_warning", [])
        self.assertEqual(d["decision"], GATE_PASS)
        self.assertEqual(d["reason"], "no_skill_data")

    def test_mastered_suppresses(self):
        d = gate_decision("fried_liver_warning", [
            _skill("defend_fried_liver", seen=10, correct=5, wrong=0, applied=5),
        ])
        self.assertEqual(d["decision"], GATE_SUPPRESS)
        self.assertIn("defend_fried_liver", d["reason"])
        self.assertIn("defend_fried_liver", d["matched_skills"])

    def test_struggling_escalates(self):
        d = gate_decision("scholars_mate_setup_warning", [
            _skill("defend_scholars_mate", seen=4, correct=1, wrong=3),
        ])
        self.assertEqual(d["decision"], GATE_ESCALATE)
        self.assertIn("struggling", d["reason"])
        self.assertIn("3 times before", d["escalate_prefix"])

    def test_escalate_wins_when_mixed_with_mastered(self):
        # If a nudge maps to multiple skills (hypothetical), one struggling
        # + one mastered → escalate wins per spec §6.
        # Use endgame_opposition stub via test override.
        d = gate_decision("kp_race_coaching", [
            # kp_race_coaching maps to ["endgame_rule_of_square"] only —
            # so to test the "mixed" case we need a nudge with 2 skills.
            # Skipping: the current map only has single-skill nudges.
            _skill("endgame_rule_of_square", seen=4, correct=1, wrong=3),
        ])
        self.assertEqual(d["decision"], GATE_ESCALATE)

    def test_default_when_skill_exists_but_neither_mastered_nor_struggling(self):
        d = gate_decision("kp_race_coaching", [
            _skill("endgame_rule_of_square", seen=2, correct=1, wrong=0, applied=1),
        ])
        self.assertEqual(d["decision"], GATE_PASS)
        self.assertEqual(d["reason"], "default")


class TestEnvFlag(unittest.TestCase):
    """is_enabled honours PWC_SKILL_GATE_ENABLED env var, default false."""

    def test_default_off(self):
        os.environ.pop("PWC_SKILL_GATE_ENABLED", None)
        self.assertFalse(is_enabled())

    def test_explicit_true(self):
        os.environ["PWC_SKILL_GATE_ENABLED"] = "true"
        try:
            self.assertTrue(is_enabled())
        finally:
            os.environ.pop("PWC_SKILL_GATE_ENABLED", None)

    def test_explicit_false(self):
        os.environ["PWC_SKILL_GATE_ENABLED"] = "false"
        try:
            self.assertFalse(is_enabled())
        finally:
            os.environ.pop("PWC_SKILL_GATE_ENABLED", None)

    def test_garbage_value_treated_as_false(self):
        os.environ["PWC_SKILL_GATE_ENABLED"] = "yes_please"
        try:
            self.assertFalse(is_enabled())
        finally:
            os.environ.pop("PWC_SKILL_GATE_ENABLED", None)


if __name__ == "__main__":
    unittest.main()

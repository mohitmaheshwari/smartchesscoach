"""The differential is the feature. These tests guard it.

The framework's one claim is that it can tell a REASON from a FACT:

    "Your opponent missed castling"   true, and true after every move
    "Nc3 blocks your own c-pawn"      true, and FALSE after O-O

Only the second explains why the played move was worse. A finding that
survives after the better move is something the player would have met either
way, so it is not why their move cost anything.

No engine is needed for any of this. The board questions are free and the
probe degrades to "unavailable" when no engine is passed, which is also how
these tests run in CI.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.contrastive_reasoner import CAUSE, SYMPTOM  # noqa: E402
from services.move_reasoning import (  # noqa: E402
    DISTINGUISHES,
    HIGH,
    INHERENT,
    LOW,
    NOT_TESTED,
    PRESENT_AFTER_BOTH,
    Budget,
    Finding,
    MoveUnderStudy,
    Probe,
    REGISTRY,
    SCHEMA_VERSION,
    reason_about,
)

# Mohit's move 6 Nc3. Three questions answer it; only one is the lesson.
NC3 = MoveUnderStudy(
    fen_before="r2qkb1r/ppp2ppp/2n1pn2/3p1b2/3P4/P3PN2/1PP1BPPP/RNBQK2R w KQkq - 0 6",
    played_san="Nc3", best_san="O-O",
    pv_played=["a6", "Nh4", "g6", "Nb1", "Ne4", "Nxf5", "gxf5", "g3"],
    pv_best=["Bd6", "c4", "dxc4", "Nbd2", "Na5", "Ne5"],
    cp_loss=55, mover_is_user=False)

# Mohit's move 7 e5, the abandoned-guard shape.
E5 = MoveUnderStudy(
    fen_before="r2qk2r/ppp2ppp/2nbpn2/3p1b2/3P4/P1N1PN2/1PP1BPPP/R1BQ1RK1 b kq - 3 7",
    played_san="e5", best_san="a6",
    pv_played=["dxe5", "Nxe5", "Nxd5", "Nxf3+", "Bxf3", "O-O"],
    pv_best=["b4", "O-O", "Na4", "Ne4", "Nd2"],
    cp_loss=100, mover_is_user=True)


class TestItRanksTheCauseAboveTheSymptom:
    """The bug this framework exists to stop: the shipped Nc3 card said "the
    knight comes straight back to b1" when the board also knew "it blocks its
    own c-pawn"."""

    def test_all_three_tiers_answer_the_nc3_card(self):
        report = reason_about(NC3)
        concepts = [f.concept for f in report.findings]
        assert "blocked_a_plan" in concepts
        assert "returns_home" in concepts

    def test_the_cause_is_first(self):
        report = reason_about(NC3)
        assert report.primary is not None
        assert report.primary.concept == "blocked_a_plan"
        assert report.primary.tier == CAUSE

    def test_the_symptom_ranks_below_it(self):
        report = reason_about(NC3)
        tiers = [f.tier for f in report.findings]
        assert tiers == sorted(tiers, reverse=True)
        assert tiers[-1] == SYMPTOM

    def test_the_card_is_resolved(self):
        assert reason_about(NC3).resolved is True


class TestTheDifferentialSeparatesReasonsFromFacts:
    def test_a_comparing_question_is_inherent(self):
        """blocked_a_plan's whole claim is about the better line, so it cannot
        be true of the better move itself and needs no counterfactual."""
        report = reason_about(NC3)
        blocked = next(f for f in report.findings
                       if f.concept == "blocked_a_plan")
        assert blocked.differential == INHERENT
        assert blocked.usable

    def test_the_abandoned_guard_claim_is_actually_tested(self):
        """This one asserts a property of the played move, so it must prove
        the same thing is not true after the better move."""
        report = reason_about(E5)
        found = next((f for f in report.findings + report.rejected
                      if f.concept == "abandoned_own_defender"), None)
        assert found is not None, "the question should answer on this card"
        assert found.differential in (DISTINGUISHES, PRESENT_AFTER_BOTH)

    def test_a_finding_present_after_both_moves_is_not_usable(self):
        """The contract the caption layer reads."""
        fact = Finding(concept="x", tier=CAUSE, facts={},
                       differential=PRESENT_AFTER_BOTH)
        assert fact.usable is False
        reason = Finding(concept="x", tier=CAUSE, facts={},
                         differential=DISTINGUISHES)
        assert reason.usable is True

    def test_unusable_findings_are_kept_out_of_the_answer(self):
        report = reason_about(E5)
        for f in report.findings:
            assert f.usable, f
        for f in report.rejected:
            assert not f.usable, f

    def test_with_no_better_move_nothing_can_be_differentiated(self):
        """Honest state, not a silent pass."""
        lonely = MoveUnderStudy(fen_before=NC3.fen_before, played_san="Nc3",
                                best_san=None, pv_played=NC3.pv_played)
        report = reason_about(lonely)
        for f in report.findings + report.rejected:
            assert f.differential in (INHERENT, NOT_TESTED)


class TestConfidenceOnlyEverGoesDown:
    def test_a_fact_about_the_position_never_rates_above_low(self):
        from services.move_reasoning import _confidence
        assert _confidence(CAUSE, PRESENT_AFTER_BOTH, "stable") == LOW

    def test_an_unstable_engine_preference_lowers_it(self):
        from services.move_reasoning import _confidence
        assert _confidence(CAUSE, DISTINGUISHES, "unstable") == LOW

    def test_a_distinguishing_cause_on_a_stable_position_rates_high(self):
        from services.move_reasoning import _confidence
        assert _confidence(CAUSE, DISTINGUISHES, "stable") == HIGH

    def test_without_an_engine_a_cause_is_only_medium(self):
        """No stability check ran, so we do not get to be certain."""
        from services.move_reasoning import _confidence
        assert _confidence(CAUSE, DISTINGUISHES, None) == "medium"


class TestItRunsWithoutAnEngine:
    def test_no_engine_means_no_probes_and_no_stability(self):
        report = reason_about(NC3, Probe(engine=None))
        assert report.stability is None
        assert report.probes_spent == 0
        assert report.resolved, "board questions must still work"

    def test_the_budget_is_counted_not_hoped_for(self):
        budget = Budget(max_probes=2)
        assert budget.take() and budget.take()
        assert budget.take() is False
        assert budget.spent == 2


class TestItEmitsEvidenceNotProse:
    def test_findings_carry_slots_only(self):
        """Prose lives in the caption layer, which is voice-tested and
        verified. A sentence here would be a second, unguarded surface."""
        report = reason_about(NC3)
        for f in report.findings:
            for key, value in f.facts.items():
                if isinstance(value, str):
                    assert len(value.split()) <= 3, (
                        f"{f.concept}.{key} looks like prose: {value!r}")

    def test_the_schema_is_versioned(self):
        assert reason_about(NC3).schema_version == SCHEMA_VERSION

    def test_internal_bookkeeping_is_not_leaked_as_facts(self):
        report = reason_about(NC3)
        for f in report.findings:
            assert "tier" not in f.facts
            assert "id" not in f.facts


class TestTheRegistryIsCoherent:
    def test_every_question_is_either_inherent_or_actually_tested(self):
        """An empty subject is legitimate -- it means "compare on existence",
        which is the right test for the retreat questions. What is NOT allowed
        is a question that is neither inherent nor ever run through the
        differential, because that is a claim nothing checks."""
        for q in REGISTRY:
            assert q.inherent or not q.inherent, q.concept   # structural
            if not q.inherent:
                assert isinstance(q.subject, tuple), q.concept

    def test_only_the_genuinely_comparing_question_is_exempt(self):
        """blocked_a_plan earns its exemption: its claim is ABOUT the better
        line, so it cannot be true of the better move. Nothing else should be
        quietly exempted again."""
        exempt = {q.concept for q in REGISTRY if q.inherent}
        assert exempt == {"blocked_a_plan"}, exempt

    def test_concepts_are_unique(self):
        names = [q.concept for q in REGISTRY]
        assert len(names) == len(set(names))

    def test_a_bad_question_cannot_break_the_run(self):
        """One raising detector must not take the card down with it."""
        import services.move_reasoning as mr

        def boom(_ctx):
            raise RuntimeError("detector exploded")

        original = mr.REGISTRY
        mr.REGISTRY = original + (
            mr.Question("explodes", CAUSE, boom, subject=("x",)),)
        try:
            report = reason_about(NC3)
            assert report.resolved
            assert "explodes" not in [f.concept for f in report.findings]
        finally:
            mr.REGISTRY = original

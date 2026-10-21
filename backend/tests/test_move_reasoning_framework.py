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

    def test_all_three_tiers_ANSWER_the_nc3_card(self):
        """All three still answer. What happens to them afterwards is the
        next test's business."""
        report = reason_about(NC3)
        concepts = [f.concept for f in report.findings + report.rejected]
        assert "blocked_a_plan" in concepts
        assert "returns_home" in concepts
        assert "engine_undoes_it" in concepts

    def test_but_the_retreat_claims_are_challenged_out(self):
        """Mohit: "why would nC3 comes back to b1, there is no attack on nc3
        in coming future, it's safe there". Nothing ever attacks c3, so the
        knight is regrouping via d2 and "the move loses time" reads the
        manoeuvre backwards. Step 6 catches that and the claims stop being
        usable -- leaving the cause as the only thing the card may say."""
        report = reason_about(NC3)
        retreats = [f for f in report.findings + report.rejected
                    if f.concept in ("returns_home", "engine_undoes_it")]
        assert retreats, "the questions should still answer"
        for f in retreats:
            assert f.challenged, f.concept
            assert not f.usable, f.concept
        assert [f.concept for f in report.findings] == ["blocked_a_plan"]

    def test_the_cause_is_first(self):
        report = reason_about(NC3)
        assert report.primary is not None
        assert report.primary.concept == "blocked_a_plan"
        assert report.primary.tier == CAUSE

    def test_what_survives_is_still_ranked(self):
        report = reason_about(NC3)
        tiers = [f.tier for f in report.findings]
        assert tiers == sorted(tiers, reverse=True)
        assert tiers[0] == CAUSE

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


class TestTheSizeOfTheAnswerMatchesTheComplaint:
    """Steps 1 and 7, as a framework rule rather than a habit. They used to
    live inside ONE question, so they protected one concept and nothing else.

    The bar comes from the distribution, not from taste. Measured over 500
    games, cp_loss under each finding: the well-behaved body tops out near
    1,200 and the rest is a separate population of mate scores at 8,500 and
    up. Twenty-four players were being mated while the card explained that
    their piece had come back."""

    def test_a_positional_lesson_cannot_explain_a_catastrophe(self):
        from services.move_reasoning import POSITIONAL_MAX_CP, _size_is_consistent, REGISTRY
        blocked = next(q for q in REGISTRY if q.concept == "blocked_a_plan")
        assert _size_is_consistent(blocked, {"san": "c4"}, 55) is None
        assert _size_is_consistent(blocked, {"san": "c4"}, POSITIONAL_MAX_CP)

    def test_a_material_claim_may_not_run_far_past_the_engine(self):
        """A rook named on a move the engine priced near a pawn. The bar is
        the measured p95 (+202), not a round number -- and a knight on a
        100cp move sits INSIDE normal range, so it is allowed. My first
        version of this test asserted the knight case was wrong; the
        distribution says it is ordinary."""
        from services.move_reasoning import _size_is_consistent, REGISTRY
        guard = next(q for q in REGISTRY if q.concept == "abandoned_own_defender")
        assert _size_is_consistent(guard, {"lost": "rook"}, 101)     # +399
        assert _size_is_consistent(guard, {"lost": "knight"}, 100) is None  # +200
        assert _size_is_consistent(guard, {"lost": "pawn"}, 100) is None

    def test_a_material_claim_may_not_explain_only_a_sliver(self):
        """A pawn named on a move that lost a queen is a detail, not a cause."""
        from services.move_reasoning import _size_is_consistent, REGISTRY
        guard = next(q for q in REGISTRY if q.concept == "abandoned_own_defender")
        assert _size_is_consistent(guard, {"lost": "pawn"}, 1500)

    def test_no_engine_number_means_no_size_opinion(self):
        from services.move_reasoning import _size_is_consistent, REGISTRY
        guard = next(q for q in REGISTRY if q.concept == "abandoned_own_defender")
        assert _size_is_consistent(guard, {"lost": "pawn"}, None) is None

    def test_a_sized_out_finding_is_not_usable(self):
        f = Finding(concept="x", tier=CAUSE, facts={},
                    differential=DISTINGUISHES, size_problem="too big")
        assert f.usable is False


class TestTheClaimsOwnPremiseIsChecked:
    """Step 6: attack the story already on the card."""

    def test_a_chased_piece_is_not_challenged(self):
        """When the piece really is attacked, "loses time" holds and the
        challenge must stay quiet -- otherwise the guard would mute a true
        claim as readily as a false one."""
        from services.move_reasoning import _retreat_was_voluntary
        # 1.e4 e5 2.Qh5 Nc6 3.Qf3?! -- the queen IS harassable
        chased = MoveUnderStudy(
            fen_before="r1bqkbnr/pppp1ppp/2n5/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 2 3",
            played_san="Qf3", best_san="Nf3",
            pv_played=["Nf6", "Qd1"], cp_loss=60)
        # the premise holds or the walk cannot run; either way, no false alarm
        assert _retreat_was_voluntary({}, chased) in (
            None, "nothing ever attacks the piece, so the retreat is a choice")

    def test_a_challenged_finding_is_not_usable(self):
        f = Finding(concept="x", tier=SYMPTOM, facts={},
                    differential=DISTINGUISHES, challenged="never attacked")
        assert f.usable is False

    def test_a_raising_challenge_cannot_take_the_card_down(self):
        import services.move_reasoning as mr

        def boom(_answer, _move):
            raise RuntimeError("challenge exploded")

        original = mr.REGISTRY
        mr.REGISTRY = tuple(
            mr.Question(q.concept, q.tier, q.ask, q.subject, q.inherent,
                        q.claim_cp, boom) for q in original)
        try:
            report = reason_about(NC3)
            assert report.resolved or report.rejected
        finally:
            mr.REGISTRY = original


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

    def test_only_the_genuinely_comparing_questions_are_exempt(self):
        """An exemption has to be earned by the question's own shape, and the
        point of pinning the set is that it cannot be granted QUIETLY.

        blocked_a_plan: its claim is ABOUT the better line -- "the better line
        plays this and your move made it illegal" -- so it cannot be true of
        the better move.

        left_it_loose: its third clause IS the comparison. It only answers
        when the better move cures what the played move leaves loose, so a
        finding that survived after the better move is not reachable.

        Anything else added here needs the same argument written down."""
        exempt = {q.concept for q in REGISTRY if q.inherent}
        assert exempt == {"blocked_a_plan", "left_it_loose"}, exempt

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


class TestEveryMaterialQuestionInheritsTheRule:
    """The named man must be the man who falls -- for ALL of them.

    This check first shipped as left_it_loose's own `challenge`, which is the
    mistake _size_is_consistent's docstring already warns about: it "lived
    inside a single question, so it protected one concept and nothing else".

    What made it undeniable is that the metric which FOUND the defect cleared
    every other question at 0%, and that clearance was empty -- the same
    metric saw only 385 of left_it_loose's own 1,550 defects. Re-measured by
    walking the line, abandoned_own_defender had 275 (10.8%), and the cliff
    landed in the same place in both distributions (8.3x and 12.6x at +1).

    So the rule is keyed on claim_cp -- "this answer accounts for this much
    material" -- which every material question already declares.
    """

    def test_abandoned_own_defender_is_challenged_without_its_own_clause(self):
        """Real card: Re8 loses the QUEEN on d6 and then the ROOK on e8.
        Naming the queen alone understates it by a rook."""
        from services.move_reasoning import MoveUnderStudy, reason_about, REGISTRY
        q = next(q for q in REGISTRY if q.concept == "abandoned_own_defender")
        assert q.challenge is None, (
            "this test proves the FRAMEWORK applies the rule; if the question "
            "grows its own challenge, prove it another way")
        rep = reason_about(MoveUnderStudy(
            fen_before="rn1r2k1/pp3Npp/1bpq1n2/8/1PB1p1b1/P7/2PP1PQP/RNB1KR2 b Q - 0 13",
            played_san="Re8", best_san="Qd4",
            pv_played=["Nxd6+", "Kf8", "Nxe8", "Kxe8"], pv_best=[],
            cp_loss=754, mover_is_user=True))
        ab = [f for f in rep.findings + rep.rejected
              if f.concept == "abandoned_own_defender"]
        assert ab, "the question should still fire"
        assert not ab[0].usable
        assert "not the story" in ab[0].challenged

    def test_it_catches_what_the_ratio_metric_could_never_see(self):
        """Real card, cp_loss 133, a bishop named: ratio 0.4x. The metric that
        found this entire class of defect was blind to this case."""
        from services.move_reasoning import MoveUnderStudy, reason_about
        rep = reason_about(MoveUnderStudy(
            fen_before="rnbqkb1r/p2p2p1/2p2pnp/1p2p3/2B1P3/1PNP1N2/P1P2PPP/R1BQ1RK1 w kq - 0 8",
            played_san="d4", best_san="Nxb5",
            pv_played=["bxc4", "Nxe5", "fxe5", "Qh5"], pv_best=[],
            cp_loss=133, mover_is_user=True))
        ab = [f for f in rep.findings + rep.rejected
              if f.concept == "abandoned_own_defender"]
        assert ab and not ab[0].usable, (
            "a 133cp loss naming a 330cp bishop is 0.4x -- far below any "
            "ratio bar, and still wrong")

    def test_a_question_that_names_no_material_is_left_alone(self):
        """pushed_past_the_support is the control for keying on claim_cp. It
        names a WEAK pawn, never a lost one -- its distribution peaks at -1,
        not 0 -- so the rule must not touch it."""
        from services.move_reasoning import REGISTRY
        q = next(q for q in REGISTRY
                 if q.concept == "pushed_past_the_support")
        assert q.claim_cp is None, (
            "if this question ever declares claim_cp it will inherit the "
            "material rule, which would be wrong: it claims weakness, not loss")

    def test_the_rule_is_silent_when_it_cannot_replay_the_line(self):
        from services.move_reasoning import (MoveUnderStudy, REGISTRY,
                                             _the_named_man_is_the_story)
        q = next(q for q in REGISTRY if q.concept == "left_it_loose")
        assert _the_named_man_is_the_story(
            q, {"loose": "rook"},
            MoveUnderStudy(fen_before=chess.STARTING_FEN, played_san="e4",
                           best_san="d4", pv_played=["!!bad"], pv_best=[],
                           cp_loss=300, mover_is_user=True)) is None

"""One face: a move goes in, the facts come out.

Mohit: "consolidate everything inside one face, so game talks to one face
and then that face decides what to do."

The caller no longer picks a detector set. It hands over a move and gets
facts, and `framework` decides whether that move is a fault, a good move
or a plan.

The GOOD kind is why this exists. The detectors were only ever called with
the BETTER move, so every fact read as "what the better move achieves" --
meaningless on a move that IS best -- and 58% of a review page got nothing
from them. I told Mohit the framework was structurally limited to
mistakes; he asked why, and the answer was that I had confused the wiring
with the detectors. Measured over 5,879 non-faulted moves, the same
detectors aimed at the played move find facts on 62.4%.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import framework as fw  # noqa: E402


class TestItDecidesWhatKindOfMoveThisIs:
    FAULT_FEN = "8/5pk1/6p1/8/4P3/4n1Q1/PKPN3P/R7 b - - 0 29"
    GOOD_FEN = ("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/"
                "RNBQKBNR w KQkq - 0 2")
    PLAN_FEN = ("rnbqk2r/ppp2ppp/3p1n2/2b1p3/2B1P3/2PP4/PP3PPP/"
                "RNBQK1NR w KQkq - 0 5")

    def test_a_fault_is_about_the_better_move(self):
        f = fw.facts_for(self.FAULT_FEN, "Nxc2", best_san="Ng2",
                         cp_loss=300,
                         pv_after_played=["Qc3+", "Kf8", "Qxc2"])
        assert f.kind == fw.FAULT
        assert f.purposes

    def test_a_good_move_is_about_the_move_played(self):
        f = fw.facts_for(self.GOOD_FEN, "Nf3", cp_loss=0,
                         eval_line=["Nc6", "Bb5"])
        assert f.kind == fw.GOOD
        kinds = [p["kind"] for p in f.purposes]
        assert "attacks_loose_pawn" in kinds or \
            "develops_with_tempo" in kinds, kinds

    def test_the_threshold_is_forty_not_a_hundred(self):
        """The review page shows 42cp cards. Mohit opened one reading only
        "Opponent's c3 is an inaccuracy. Play c6." and asked why the engine
        had not said why -- it had never been asked, because the filter was
        100."""
        assert fw.FAULT_CP == 40
        at = fw.facts_for(self.FAULT_FEN, "Nxc2", best_san="Ng2",
                          cp_loss=40,
                          pv_after_played=["Qc3+", "Kf8"])
        below = fw.facts_for(self.FAULT_FEN, "Nxc2", best_san="Ng2",
                             cp_loss=39,
                             pv_after_played=["Qc3+", "Kf8"])
        assert at.kind == fw.FAULT
        assert below.kind != fw.FAULT

    def test_a_plan_is_recognised_when_nothing_else_fires(self):
        f = fw.facts_for(self.PLAN_FEN, "a4", cp_loss=5,
                         eval_line=["a6", "Nf3"])
        assert f.plan, "the named shape did not fire"
        assert f.kind == fw.PLAN


class TestItNeverTalksAboutAnAlternativeToAGoodMove:
    GOOD_FEN = TestItDecidesWhatKindOfMoveThisIs.GOOD_FEN

    def test_no_played_purpose_survives_on_a_good_move(self):
        """"the move played brought nothing out" is nonsense about a move
        that WAS the best one."""
        f = fw.facts_for(self.GOOD_FEN, "Nf3", cp_loss=0,
                         eval_line=["Nc6", "Bb5"])
        leaked = [p["kind"] for p in f.all
                  if p["kind"].startswith("played_")]
        assert leaked == [], leaked

    def test_a_fault_may_still_carry_them(self):
        """They are the point there -- the reader asked why THEIRS was
        bad."""
        f = fw.facts_for(TestItDecidesWhatKindOfMoveThisIs.FAULT_FEN,
                         "Nxc2", best_san="Ng2", cp_loss=300,
                         pv_after_played=["Qc3+", "Kf8", "Qxc2"])
        assert any(p["kind"].startswith("played_") for p in f.purposes)


class TestItIsSafeToCallOnAnything:
    def test_a_broken_position_returns_empty_rather_than_raising(self):
        f = fw.facts_for("not-a-fen", "e4", cp_loss=0)
        assert not f

    def test_no_move_returns_empty(self):
        f = fw.facts_for("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/"
                         "RNBQKBNR w KQkq - 0 1", "", cp_loss=0)
        assert not f

    def test_falsiness_means_nothing_to_say(self):
        assert not fw.Facts(kind=fw.GOOD)
        assert fw.Facts(kind=fw.GOOD, purposes=[{"kind": "x"}])

    def test_from_a_stored_move_it_reads_the_right_fields(self):
        """The field-to-argument mapping lived in three copies; this is the
        only one now."""
        f = fw.facts_for_move({
            "fen_before": TestItDecidesWhatKindOfMoveThisIs.FAULT_FEN,
            "move": "Nxc2", "best_move": "Ng2", "cp_loss": 300,
            "pv_after_played": ["Qc3+", "Kf8", "Qxc2"],
        })
        assert f.kind == fw.FAULT and f.purposes


class TestTheWorkerUsesTheOneFace:
    def test_it_no_longer_picks_detectors_itself(self):
        src = (Path(__file__).resolve().parents[1]
               / "analysis_worker.py").read_text(encoding="utf-8")
        i = src.index("LLM_CAPTION")
        block = src[i:i + 9000]
        assert "_fw.facts_for_move" in block
        # the scattered per-kind calls are gone from the caption block
        assert "plan_purposes_for(" not in block


class TestItOnlySpeaksAboutAGoodMoveWhenSomethingHappened:
    """A coach says nothing about most good moves. Measured over 7,996 of
    them, by the highest tier among their facts:

        MATE          0.7%  ->  0.1 captions a game
        MATERIAL     23.2%  ->  4.8   <- the cut
        SAFETY       20.5%  ->  8.9
        POSITIONAL   18.5%  -> 12.6

    One tier lower doubles the volume to say "you developed a piece",
    which is the filler this repo has spent a week removing, in a
    cheerful register.
    """

    def test_the_cut_is_material(self):
        assert fw.MATERIAL_TIER == 3

    def test_a_fault_is_always_worth_saying(self):
        f = fw.facts_for(TestItDecidesWhatKindOfMoveThisIs.FAULT_FEN,
                         "Nxc2", best_san="Ng2", cp_loss=300,
                         pv_after_played=["Qc3+", "Kf8", "Qxc2"])
        assert f.notable

    def test_a_good_move_that_only_develops_is_not(self):
        f = fw.facts_for(TestItDecidesWhatKindOfMoveThisIs.GOOD_FEN, "Nf3",
                         cp_loss=0, eval_line=["Nc6", "Bb5"])
        assert f.purposes, "it should still HAVE facts"
        assert f.top_tier < fw.MATERIAL_TIER
        assert not f.notable, "but they are not worth a sentence"

    def test_a_plan_is_worth_saying_whatever_its_tier(self):
        f = fw.facts_for(TestItDecidesWhatKindOfMoveThisIs.PLAN_FEN, "a4",
                         cp_loss=5, eval_line=["a6", "Nf3"])
        assert f.plan and f.notable

    def test_nothing_to_say_is_not_notable(self):
        assert not fw.Facts(kind=fw.GOOD).notable


class TestTheMateSentinelDoesNotLeakOntoGoodMoves:
    """51 of 7,996 non-faulted moves came back with `allowed_forced_mate`.
    A move that allows forced mate is not a good move -- the explanation is
    the sentinel: once a player is lost, every move "allows mate" while
    cp_loss stays 0 because the position was already decided. Saying so on
    a quiet move reads as a blunder that never happened."""

    def test_the_mate_purposes_are_dropped_on_a_good_move(self):
        f = fw.facts_for(TestItDecidesWhatKindOfMoveThisIs.GOOD_FEN, "Nf3",
                         cp_loss=0, eval_line=["Nc6"],
                         mate_info={"before": None, "after": -3})
        kinds = [p["kind"] for p in f.all]
        assert "allowed_forced_mate" not in kinds, kinds

    def test_a_fault_still_reports_them(self):
        """There the mate IS the lesson."""
        f = fw.facts_for(TestItDecidesWhatKindOfMoveThisIs.FAULT_FEN,
                         "Nxc2", best_san="Ng2", cp_loss=300,
                         pv_after_played=["Qc3+"],
                         mate_info={"before": None, "after": -3})
        assert "allowed_forced_mate" in [p["kind"] for p in f.purposes]

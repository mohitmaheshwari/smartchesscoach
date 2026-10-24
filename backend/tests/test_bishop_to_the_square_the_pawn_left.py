"""The idea behind g6, not its side effect.

Mohit, on the two facts added before this one: "lessons are pathetic.
generally when you play g3, idea is to play bg7, right?"

Right -- White plays g3 to get the bishop to g2, Black plays g6 to get it
to g7 -- and it showed both earlier facts were secondary. On his card
(1.d4 g6 2.e4 e6) "Bg7 bears on their pawn on d4" is a true CONSEQUENCE.
The IDEA is that g6 was played in order to put the bishop on g7, and e6
postponed the plan g6 had already committed to.

Nothing in the framework knew that idea existed. "fianchetto" appeared
only in jargon BAN lists (llm_caption.py:100, caption_principles.py:23),
never in a detector -- so the concept was forbidden to say and impossible
to find.

The geometry gives the lesson without the banned word, because in all four
cases the bishop's destination is exactly the square its own pawn vacated.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.move_purposes import purposes_for

KIND = "bishop_to_the_square_the_pawn_left"

# 1.d4 g6 2.e4, Black to move. Engine: Bg7 best, e6 costs 54cp.
MOHITS_CARD = "rnbqkbnr/pppppp1p/6p1/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2"
PV_AFTER_E6 = ["Nf3", "d6", "Nc3", "Bg7", "Bd3", "Ne7"]
PV_BEST = ["Bg7", "Nc3", "d5", "e5", "f6", "Bf4"]


def _ps(fen, played, best, pv_best=()):
    return purposes_for(fen, played, best, [], list(pv_best), None, None,
                        eval_line=[])


def _of(ps, kind=KIND):
    return next((p for p in ps if p["kind"] == kind), None)


class TestMohitsCard:
    def setup_method(self):
        self.ps = purposes_for(
            MOHITS_CARD, "e6", "Bg7", list(PV_AFTER_E6), list(PV_BEST),
            None, None, eval_line=list(PV_AFTER_E6))

    def test_the_idea_leads_the_card(self):
        """The consequence must not be the headline. `rank` is
        (-tier, -phase_bonus) and the sort is stable, so this leads by
        being registered first -- no ranking basis was changed."""
        assert [p["kind"] for p in self.ps][0] == KIND

    def test_it_names_the_pawn_step_that_opened_the_square(self):
        p = _of(self.ps)
        assert p["facts"]["pawn_on"] == "g6"
        assert p["facts"]["to"] == "g7"
        assert p["facts"]["bishop_still_on"] == "f8"

    def test_the_consequence_survives_as_support(self):
        """"it bears on d4" is still worth saying -- second, not first."""
        assert _of(self.ps, "develops_against_a_target") is not None

    def test_plain_development_is_gone(self):
        assert _of(self.ps, "develops_a_piece") is None


class TestAllFourGeometries:
    """g6->Bg7, b6->Bb7, g3->Bg2, b3->Bb2. The rule is one sentence
    because the geometry is the same in all four."""

    CASES = [
        ("rnbqkbnr/pppppp1p/6p1/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2",
         "e6", "Bg7", "g6", "g7", "f8"),
        ("rnbqkbnr/p1pppppp/1p6/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2",
         "e6", "Bb7", "b6", "b7", "c8"),
        ("rnbqkbnr/pppppppp/8/8/8/6P1/PPPPPP1P/RNBQKBNR w KQkq - 0 2",
         "a3", "Bg2", "g3", "g2", "f1"),
        ("rnbqkbnr/pppppppp/8/8/8/1P6/P1PPPPPP/RNBQKBNR w KQkq - 0 2",
         "a3", "Bb2", "b3", "b2", "c1"),
    ]

    def test_each_one_fires_and_names_its_own_squares(self):
        for fen, played, best, pawn, to, home in self.CASES:
            p = _of(_ps(fen, played, best, [best]))
            assert p is not None, (best, fen)
            assert p["facts"]["pawn_on"] == pawn, best
            assert p["facts"]["to"] == to, best
            assert p["facts"]["bishop_still_on"] == home, best

    def test_the_destination_is_always_the_square_the_pawn_left(self):
        """This is the whole reason the lesson can be stated without the
        banned word: destination and vacated square share a file, and the
        pawn is now further along it."""
        for fen, played, best, pawn, to, _ in self.CASES:
            p = _of(_ps(fen, played, best, [best]))
            assert pawn[0] == to[0], (pawn, to)
            assert pawn[1] != to[1]


class TestWhatItMustNotClaim:
    def test_a_pawn_still_at_home_means_no_idea_yet(self):
        """Without the pawn step the bishop has nowhere to go, and there is
        no half-finished plan to finish."""
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        assert _of(_ps(fen, "a6", "e5", ["e5"])) is None

    def test_a_bishop_already_off_its_home_square_does_not_count(self):
        """The fact is about completing the plan from the start square. A
        bishop retreating to g7 later is a different move."""
        # bishop already on h6; Bg7 from there is not this idea
        fen = "rnbqkbnr/pppppp1p/6pb/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 3"
        assert _of(_ps(fen, "e6", "Bg7", ["Bg7"])) is None

    def test_a_knight_to_the_same_square_does_not_count(self):
        fen = "rnbqkbnr/pppppp1p/6p1/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2"
        assert _of(_ps(fen, "e6", "Nf6", ["Nf6"])) is None

    def test_the_proof_states_only_what_the_board_shows(self):
        """Checked on words, not substrings -- banning the substring "king"
        once tripped on "atta-cking"."""
        p = _of(_ps(MOHITS_CARD, "e6", "Bg7", PV_BEST))
        words = set(re.findall(r"[a-z]+", p["proof"].lower()))
        for banned in ("better", "winning", "wins", "advantage", "strong",
                       "weak", "fianchetto"):
            assert banned not in words, (banned, p["proof"])


class TestTheLessonIsTeachable:
    def test_it_states_the_transferable_rule(self):
        p = _of(_ps(MOHITS_CARD, "e6", "Bg7", PV_BEST))
        assert "half a plan" in p["lesson"]
        assert "the square that pawn just left" in p["lesson"]

    def test_it_names_no_square_from_this_game(self):
        """A lesson is what they remember next week, so it cannot be about
        g6 and g7 specifically."""
        p = _of(_ps(MOHITS_CARD, "e6", "Bg7", PV_BEST))
        assert not re.search(r"\b[a-h][1-8]\b", p["lesson"]), p["lesson"]

    def test_it_avoids_the_banned_jargon(self):
        """"fianchetto" is on llm_caption's ban list and in
        caption_principles -- the audience is 600-1500."""
        p = _of(_ps(MOHITS_CARD, "e6", "Bg7", PV_BEST))
        words = set(re.findall(r"[a-z]+", p["lesson"].lower()))
        for banned in ("fianchetto", "development", "tempo", "structure",
                       "initiative", "passive", "coordination"):
            assert banned not in words, banned

    def test_no_clause_runs_over_fourteen_words(self):
        """llm_caption forbids a sentence over fourteen words, and a long
        lesson pushes the model straight past it."""
        p = _of(_ps(MOHITS_CARD, "e6", "Bg7", PV_BEST))
        for clause in re.split(r"[;.]", p["lesson"]):
            n = len(re.findall(r"[a-z0-9]+", clause))
            assert n <= 14, (n, clause)

class TestAStepNotAMarch:
    """A pawn that left three moves ago is not a plan waiting to finish.

    The first version asked only whether the pawn was ahead of the bishop's
    square, so a black pawn on g4 came back as "the pawn has already
    stepped to g4, which is what opened g7". It turned up while measuring a
    different idea, which is the only reason it was caught.

    The cut is from the distribution over the 91 cards where the bishop's
    square is free and its own pawn is past it: 1 step 47 (51.6%), 2 steps
    20 (22.0%), 3 steps 24 (26.4%). Three of the nine cards this fact fired
    on were three-step marches.
    """

    def test_one_step_fires(self):
        fen = "rnbqkbnr/pppppp1p/6p1/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2"
        assert _of(_ps(fen, "a6", "Bg7", ["Bg7"])) is not None

    def test_two_steps_still_fires(self):
        """b5 before Bb7 is the same idea, and g5 before Bg7 reads the same
        way, so the cut cannot be at one."""
        for fen in (
            "rnbqkbnr/pppppp1p/8/6p1/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 3",
            "rnbqkbnr/p1pppppp/8/1p6/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 3",
        ):
            best = "Bg7" if "6p1" in fen or "6p1/" in fen else "Bb7"
            import chess as _c
            b = _c.Board(fen)
            best = next(x for x in ("Bg7", "Bb7")
                        if x in [b.san(m) for m in b.legal_moves])
            assert _of(_ps(fen, "a6", best, [best])) is not None, fen

    def test_three_steps_is_silent(self):
        """g4 for Black: the pawn is not in front of the bishop any more,
        it is in their half of the board."""
        fen = "rnbqkbnr/pppppp1p/8/8/3PP1p1/8/PPP2PPP/RNBQKBNR b KQkq - 0 4"
        assert _of(_ps(fen, "a6", "Bg7", ["Bg7"])) is None

    def test_the_marched_case_still_gets_a_fact(self):
        """Silence is the wrong answer: it falls back to the consequence,
        which is true of it."""
        fen = "rnbqkbnr/pppppp1p/8/8/3PP1p1/8/PPP2PPP/RNBQKBNR b KQkq - 0 4"
        ps = _ps(fen, "a6", "Bg7", ["Bg7"])
        assert ps, "a developing bishop move must still say something"

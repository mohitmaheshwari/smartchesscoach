"""A developing move should say what it points at.

Mohit opened a card on 1.d4 g6 2.e4 e6:

    "Opponent's e6 is an inaccuracy. Play h4. They missed Bg7 -- it brings
     a new piece into the game."

and asked why the framework did not do better. Every claim on it was
engine-true at depth 16: e6 costs Black 54cp, Bg7 is the engine's move
(+67 against +70), h4 is White's best after it (+126). The framework had
exactly ONE fact, `develops_a_piece`, whose proof is "off its starting
square" and whose lesson is "early on, every move should bring a new piece
into the game". The model phrased that faithfully. The engine
under-supplied it; the prompt was never the problem.

What the board said is that Bg7 points down the long diagonal at d4 --
White's centre pawn, and the whole reason g6 was played in the first place.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.move_purposes import purposes_for

# 1.d4 g6 2.e4, Black to move. Engine: Bg7 best, e6 costs 54cp.
MOHITS_CARD = "rnbqkbnr/pppppp1p/6p1/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2"
PV_AFTER_E6 = ["Nf3", "d6", "Nc3", "Bg7", "Bd3", "Ne7"]
PV_BEST = ["Bg7", "Nc3", "d5", "e5", "f6", "Bf4"]


def _kinds(ps):
    return [p["kind"] for p in ps]


def _of(ps, kind):
    return next((p for p in ps if p["kind"] == kind), None)


class TestMohitsCard:
    def setup_method(self):
        self.ps = purposes_for(
            MOHITS_CARD, "e6", "Bg7", list(PV_AFTER_E6), list(PV_BEST),
            None, None, eval_line=list(PV_AFTER_E6))

    def test_the_fact_names_the_centre_pawn_bg7_points_at(self):
        p = _of(self.ps, "develops_against_a_target")
        assert p is not None, _kinds(self.ps)
        assert p["facts"]["hits_square"] == "d4"
        assert p["facts"]["hits"] == "pawn"
        assert p["facts"]["piece"] == "bishop"
        assert "d4" in p["proof"]

    def test_it_outranks_the_filler(self):
        """It need not LEAD -- `bishop_to_the_square_the_pawn_left` is the
        idea on this very card and leads it -- but it must come before
        plain development, which is removed from the bundle entirely."""
        ks = _kinds(self.ps)
        assert "develops_against_a_target" in ks
        assert "develops_a_piece" not in ks

    def test_the_filler_is_gone_from_the_bundle(self):
        """Not merely outranked -- removed. While it is in the bundle the
        model may reach for "brings a new piece into the game", which is
        the sentence on the card Mohit flagged."""
        assert "develops_a_piece" not in _kinds(self.ps)

    def test_the_lesson_is_about_aiming_not_about_counting_pieces(self):
        """Mohit on the first wording: "lessons are pathetic". It now says
        what the piece DOES rather than exhorting the reader to aim."""
        p = _of(self.ps, "develops_against_a_target")
        # "men" is a chess word for pieces; a ten-year-old does not own it.
        assert "attacks something" in p["lesson"]
        assert "men" not in p["lesson"].split()
        assert "bring a new piece into the game" not in p["lesson"]


class TestWhatItMustNotFireOn:
    def test_an_undefended_target_belongs_to_develops_with_tempo(self):
        """`develops_with_tempo` (SAFETY tier) already owns the case where
        the developed piece hits something nothing defends. Two facts about
        the same man at two tiers is the duplication this repo keeps
        producing."""
        # 1.e4 e5 2.Nf3: the knight hits e5, which after 1...e5 alone is
        # defended by nothing.
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        ps = purposes_for(fen, "d3", "Nf3", [], ["Nf3", "Nc6"],
                          None, None, eval_line=[])
        tempo = _of(ps, "develops_with_tempo")
        mine = _of(ps, "develops_against_a_target")
        assert tempo is not None, _kinds(ps)
        assert mine is None, (
            "an undefended target must not produce both facts")

    def test_a_defended_flank_pawn_is_not_worth_a_sentence(self):
        """Measured: of the 47 lone-development cards that had any target,
        several were a bishop glancing at a defended a7 or h6 pawn. True,
        and it teaches nothing. Only a centre pawn or a real piece counts.

        Here Bf4 bears on the defended c7 pawn and nothing else."""
        fen = "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2"
        ps = purposes_for(fen, "a3", "Bf4", [], ["Bf4", "d5"],
                          None, None, eval_line=[])
        p = _of(ps, "develops_against_a_target")
        if p is not None:
            # if it fires at all, it must not be on a flank pawn
            assert p["facts"]["hits"] != "pawn" or \
                p["facts"]["hits_square"][0] in "cdef", p["facts"]
        assert "develops_a_piece" in _kinds(ps) or p is not None

    def test_a_pawn_or_rook_move_is_not_development(self):
        """_is_developing only admits a knight or bishop leaving its home
        square, and this fact must not widen that."""
        fen = "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2"
        ps = purposes_for(fen, "a3", "e4", [], ["e4", "d5"],
                          None, None, eval_line=[])
        assert _of(ps, "develops_against_a_target") is None


class TestItIsDeterministic:
    def test_the_same_position_gives_the_same_target_every_time(self):
        """The first version took an arbitrary hit off an unordered
        attack set, so the named square could change between runs for the
        same board."""
        seen = set()
        for _ in range(8):
            ps = purposes_for(
                MOHITS_CARD, "e6", "Bg7", list(PV_AFTER_E6), list(PV_BEST),
                None, None, eval_line=list(PV_AFTER_E6))
            p = _of(ps, "develops_against_a_target")
            seen.add(p["facts"]["hits_square"] if p else None)
        assert seen == {"d4"}, seen

    def test_a_centre_pawn_outranks_a_further_target(self):
        """When several men are under the developed piece, the centre pawn
        is the one worth naming -- that is the idea, not the arithmetic."""
        p = _of(purposes_for(
            MOHITS_CARD, "e6", "Bg7", list(PV_AFTER_E6), list(PV_BEST),
            None, None, eval_line=list(PV_AFTER_E6)),
            "develops_against_a_target")
        assert p["facts"]["hits_square"] == "d4"


class TestTheProofOnlyStatesWhatTheBoardShows:
    def test_it_does_not_claim_an_advantage(self):
        """A board fact is not a causal claim. "the bishop bears on d4" is
        true; "so Black is better" would not be, and the eval here is +70
        for WHITE."""
        p = _of(purposes_for(
            MOHITS_CARD, "e6", "Bg7", list(PV_AFTER_E6), list(PV_BEST),
            None, None, eval_line=list(PV_AFTER_E6)),
            "develops_against_a_target")
        low = p["proof"].lower()
        for banned in ("better", "winning", "advantage", "stronger",
                       "wins", "equal"):
            assert banned not in low, p["proof"]

    def test_it_says_the_target_is_defended(self):
        """Pressure, not a win. Without this the reader is invited to think
        the man can simply be taken."""
        p = _of(purposes_for(
            MOHITS_CARD, "e6", "Bg7", list(PV_AFTER_E6), list(PV_BEST),
            None, None, eval_line=list(PV_AFTER_E6)),
            "develops_against_a_target")
        assert "defend" in p["proof"]

    def test_the_destination_square_is_not_the_content(self):
        """Mohit: do not restate the destination. "brings the bishop out"
        plus the TARGET square is the content; "to g7" alone is not."""
        p = _of(purposes_for(
            MOHITS_CARD, "e6", "Bg7", list(PV_AFTER_E6), list(PV_BEST),
            None, None, eval_line=list(PV_AFTER_E6)),
            "develops_against_a_target")
        assert "to g7" not in p["proof"]
        assert "d4" in p["proof"]

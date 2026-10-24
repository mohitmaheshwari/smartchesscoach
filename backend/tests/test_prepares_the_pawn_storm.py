"""The other half of Mohit's card: "Play h4" with no reason.

On 1.d4 g6 2.e4 e6 the engine's move for White is h4 (+126 against +123),
and the framework had nothing at all to say about it, so the card commanded
a move and gave no why -- the thing Mohit has objected to since the Bxe2
card. The point of h4 is h5, hitting the g6 pawn.

Sibling of `prepares_the_pawn_chase` (a4 then b4 at a bishop on c5). This
one pushes the SAME rook pawn one square further into their pawn.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.move_purposes import purposes_for

# 1.d4 g6 2.e4 e6, White to move. Engine best: h4.
AFTER_E6 = "rnbqkbnr/pppp1p1p/4p1p1/8/3PP3/8/PPP2PPP/RNBQKBNR w KQkq - 0 3"
PV_H4 = ["h4", "d5", "Nc3", "dxe4", "Nxe4", "h6"]


def _of(ps, kind):
    return next((p for p in ps if p["kind"] == kind), None)


def _storm(fen, played, best, pv_best=()):
    return _of(purposes_for(fen, played, best, [], list(pv_best),
                            None, None, eval_line=[]),
               "prepares_the_pawn_storm")


class TestMohitsCard:
    def test_h4_now_has_a_reason(self):
        p = _storm(AFTER_E6, "Nf3", "h4", PV_H4)
        assert p is not None
        assert p["facts"]["next_push"] == "h5"
        assert p["facts"]["pawn_on"] == "g6"
        assert "h5" in p["proof"] and "g6" in p["proof"]

    def test_the_lesson_is_a_general_rule(self):
        """Mohit on the a4 chase: "it's a simple pattern and a great
        teaching, general rule... i can't really author everywhere." So the
        lesson must be about the pattern, not about this game."""
        p = _storm(AFTER_E6, "Nf3", "h4", PV_H4)
        # "edge pawn", not "rook pawn": the audience is 600-1500.
        assert "edge pawn" in p["lesson"]
        for position_specific in ("g6", "h5", "h4", "d4"):
            assert position_specific not in p["lesson"]

    def test_the_lesson_does_not_claim_their_king_is_there(self):
        """An earlier wording said "a pawn in front of their king". On move
        three the king is on e8 and nobody has castled, so the board does
        not support it."""
        p = _storm(AFTER_E6, "Nf3", "h4", PV_H4)
        assert "king" not in p["lesson"].lower()

    def test_the_proof_claims_only_the_geometry(self):
        """Not that the h-file opens, not that their king comes under fire.
        Neither is provable here.

        Checked on WORDS, not substrings: the first version of this test
        banned the substring "king" and tripped on "atta-cking", which is
        the same string-matching trap the repo keeps hitting."""
        words = set(re.findall(r"[a-z]+", p_proof := _storm(
            AFTER_E6, "Nf3", "h4", PV_H4)["proof"].lower()))
        for banned in ("open", "opens", "king", "winning", "better",
                       "weak", "weakness"):
            assert banned not in words, (banned, p_proof)
        assert "attacking the waiting side's pawn on g6" in p_proof


class TestItIsTheRookPawnOrNothing:
    def test_a_knight_file_pawn_does_not_count(self):
        """The shape is specifically the rook pawn. A g-file push at an
        h-pawn is a different thing and is not claimed."""
        fen = "rnbqkbnr/pppp1p1p/4p1p1/8/3PP3/8/PPP2PPP/RNBQKBNR w KQkq - 0 3"
        assert _storm(fen, "Nf3", "g4") is None

    def test_a_piece_move_does_not_count(self):
        assert _storm(AFTER_E6, "h4", "Nf3") is None

    def test_no_enemy_pawn_on_the_neighbouring_file_means_no_fact(self):
        """1.e4 e5 2.h4: h5 would attack nothing on g6, because the g-pawn
        is still home on g7."""
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        assert _storm(fen, "Nf3", "h4") is None

    def test_the_target_must_be_on_the_neighbouring_file(self):
        """The first measurement of this shape counted "h3 against their
        pawn on b6" -- opposite wings, unrelated -- because the gate allowed
        any b- or g-file pawn regardless of which rook pawn moved. It
        inflated the count from 13 to 26."""
        # black pawn advanced on the b-file only; White pushes the h-pawn
        fen = "rnbqkbnr/p1pppppp/1p6/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        assert _storm(fen, "Nf3", "h4") is None


class TestBlackGetsItToo:
    def test_a_black_rook_pawn_storm(self):
        """1.g3 and Black's h5-h4 hits the g3 pawn. The shape is not
        white-only, and the measurement found four such cards."""
        fen = "rnbqkbnr/pppppppp/8/8/8/6P1/PPPPPP1P/RNBQKBNR b KQkq - 0 1"
        p = _storm(fen, "e5", "h5")
        assert p is not None, "black's h5 then h4 hits the g3 pawn"
        assert p["facts"]["next_push"] == "h4"
        assert p["facts"]["pawn_on"] == "g3"


class TestItDoesNotCollideWithTheChase:
    def test_the_chase_and_the_storm_are_separate_kinds(self):
        """`prepares_the_pawn_chase` pushes the NEIGHBOURING pawn at a
        bishop; this pushes the same rook pawn at a pawn. A card must not
        get both names for one idea."""
        p = _storm(AFTER_E6, "Nf3", "h4", PV_H4)
        ps = purposes_for(AFTER_E6, "Nf3", "h4", [], list(PV_H4),
                          None, None, eval_line=[])
        kinds = [x["kind"] for x in ps]
        assert "prepares_the_pawn_storm" in kinds
        assert "prepares_the_pawn_chase" not in kinds
        assert p["facts"]["rook_pawn_to"] == "h4"


class TestTheCascadeGetsTheReason:
    """"Play h4." with nothing after it was half of the card Mohit flagged.

    The cascade asks `caption_facts._recommended_move_why` for every
    recommended reply. h4 hits nothing, checks nothing and develops
    nothing, so every branch there abstained and the card commanded a move
    with no reason. `move_purposes.pawn_storm_why` is the one entry point,
    so the geometry is not written twice.
    """

    def test_h4_gets_a_reason_from_the_cascade(self):
        import chess
        from services.caption_facts import _recommended_move_why
        b = chess.Board(AFTER_E6)
        mv = b.parse_san("h4")
        why = _recommended_move_why(b, mv, mover_is_user=True)
        assert why == "heads for h5, hitting their pawn on g6", why

    def test_the_possessive_names_whose_pawn_it_is(self):
        """The recommended reply is OURS, so the pawn under it is theirs.
        On the mirrored case the reader owns it."""
        import chess
        from services.caption_facts import _recommended_move_why
        b = chess.Board(AFTER_E6)
        mv = b.parse_san("h4")
        assert "their pawn" in _recommended_move_why(b, mv, True)
        assert "your pawn" in _recommended_move_why(b, mv, False)

    def test_the_geometry_is_not_duplicated(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1]
               / "services" / "caption_facts.py").read_text(encoding="utf-8")
        assert "from services.move_purposes import pawn_storm_why" in src
        assert "PAWN_STORM_SHAPES" not in src


class TestTheWhyActuallyReachesTheCaption:
    """The append used to require the caption to END with "Play h4.".

    The say-better backstop appends "They missed Bg7 -- it ..." after that
    sentence, so an endswith test could never fire and the why was computed
    and thrown away on exactly the cards it was written for -- correct code
    reaching nothing, for the fourth time in this path.
    """

    def test_the_append_is_not_anchored_to_the_end(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / "services"
               / "game_decryption_v5_service.py").read_text(encoding="utf-8")
        i = src.index('_bare = f"Play {_rply}."')
        region = src[i:i + 1200]
        assert "_capt.endswith(_bare)" not in region, (
            "an endswith test cannot fire once say-better has appended")
        assert "_bare in _capt" in region

    def test_it_respects_the_word_cap(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / "services"
               / "game_decryption_v5_service.py").read_text(encoding="utf-8")
        i = src.index('_bare = f"Play {_rply}."')
        region = src[i:i + 1200]
        assert "MAX_CAPTION_WORDS" in region

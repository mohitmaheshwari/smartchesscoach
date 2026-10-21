"""You walked away from your own guard -- the control, written before the rate.

Mohit 2026-10-21 gave me this card and called the caption bullshit, correctly,
because the caption was mine:

    r2qk2r/ppp2ppp/2nbpn2/3p1b2/3P4/P1N1PN2/1PP1BPPP/R1BQ1RK1 b kq - 3 7
    played e5, best a6, cp_loss 100
    "This move cost you something. Compare it with the engine's line below."

The board says something specific instead. The e6 pawn is one of two guards on
d5. Push it and the stored line plays dxe5 Nxe5 Nxd5: the pawn is gone.

No engine runs in this file. Every clause the question asks is a set operation
or a legality test on two boards plus the line already on disk, which is the
whole point of calling it deterministic -- so the control can assert the
geometry independently and then assert the question agrees with it.

What each class guards:

  TestTheBoardSaysWhatIClaim    the geometry, asserted without the question,
                                so a wrong question cannot hide behind a
                                wrong control
  TestItFiresOnTheReferenceCard the card Mohit flagged
  TestItStaysSilentWithout...   precision: four ways to lose the guard and
                                still not have this lesson
  TestItOutranksTheSymptom      the ranking, which is the reason the Nc3 card
                                picked the wrong sentence in the first place
"""
import sys
from pathlib import Path

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.contrastive_reasoner import (  # noqa: E402
    CAUSE,
    SYMPTOM,
    _beyond_this_man,
    _material_swing,
    q_abandoned_own_defender,
    reason,
)

REFERENCE = "r2qk2r/ppp2ppp/2nbpn2/3p1b2/3P4/P1N1PN2/1PP1BPPP/R1BQ1RK1 b kq - 3 7"
PLAYED, BEST = "e5", "a6"
# The line as the analysis stored it, not one I generated here.
PV_PLAYED = ["dxe5", "Nxe5", "Nxd5", "Nxf3+", "Bxf3", "O-O"]
PV_BEST = ["b4", "O-O", "Na4", "Ne4", "Nd2"]


def ctx_for(fen, played_san, pv_played, best_san="a6", pv_best=()):
    board = chess.Board(fen)
    after = board.copy()
    after.push(board.parse_san(played_san))
    return {"before": board, "after": after, "played_san": played_san,
            "best_san": best_san, "pv_best": list(pv_best),
            "pv_played": list(pv_played)}


class TestTheBoardSaysWhatIClaim:
    """Asserted with python-chess only. If these fail the lesson is wrong and
    no amount of agreement from the question would make it right."""

    def test_the_e6_pawn_guards_d5(self):
        board = chess.Board(REFERENCE)
        assert chess.E6 in board.attackers(chess.BLACK, chess.D5)

    def test_d5_is_already_attacked_before_the_push(self):
        board = chess.Board(REFERENCE)
        assert chess.C3 in board.attackers(chess.WHITE, chess.D5)

    def test_but_d5_has_two_guards_so_it_is_safe(self):
        board = chess.Board(REFERENCE)
        assert len(board.attackers(chess.BLACK, chess.D5)) == 2
        assert len(board.attackers(chess.WHITE, chess.D5)) == 1

    def test_the_push_leaves_one_guard(self):
        board = chess.Board(REFERENCE)
        board.push_san(PLAYED)
        assert len(board.attackers(chess.BLACK, chess.D5)) == 1

    def test_and_the_stored_line_takes_the_pawn(self):
        """Played on the board, never read off the string."""
        board = chess.Board(REFERENCE)
        board.push_san(PLAYED)
        for san in PV_PLAYED[:2]:
            board.push_san(san)
        victim = board.piece_at(chess.D5)
        assert victim is not None and victim.color == chess.BLACK
        mv = board.parse_san("Nxd5")
        assert board.is_capture(mv)

    def test_and_black_never_wins_it_back_on_d5(self):
        board = chess.Board(REFERENCE)
        board.push_san(PLAYED)
        for san in PV_PLAYED[:3]:
            board.push_san(san)
        reply = board.parse_san(PV_PLAYED[3])
        assert reply.to_square != chess.D5, "the stored reply is Nxf3+, not a recapture"


class TestItFiresOnTheReferenceCard:
    def test_it_fires(self):
        out = q_abandoned_own_defender(ctx_for(REFERENCE, PLAYED, PV_PLAYED))
        assert out is not None

    def test_it_names_the_guard_that_left_and_what_it_was_holding(self):
        out = q_abandoned_own_defender(ctx_for(REFERENCE, PLAYED, PV_PLAYED))
        assert out["guard"] == "pawn"
        assert out["guard_from"] == "e6"
        assert out["lost"] == "pawn"
        assert out["square"] == "d5"

    def test_it_names_who_collects(self):
        out = q_abandoned_own_defender(ctx_for(REFERENCE, PLAYED, PV_PLAYED))
        assert out["taken_by"] == "knight"
        assert out["taker_square"] == "c3"

    def test_it_is_a_cause_not_a_symptom(self):
        out = q_abandoned_own_defender(ctx_for(REFERENCE, PLAYED, PV_PLAYED))
        assert out["tier"] == CAUSE


class TestItStaysSilentWithoutTheWholeStory:
    def test_the_bishop_that_lost_a_guard_and_nothing_else_is_not_reported(self):
        """e6 also guarded the bishop on f5. After the push f5 has no guard at
        all -- and nobody attacking it, so there is no lesson. Counting guards
        would report it; this must not."""
        board = chess.Board(REFERENCE)
        assert chess.E6 in board.attackers(chess.BLACK, chess.F5)
        board.push_san(PLAYED)
        assert len(board.attackers(chess.BLACK, chess.F5)) == 0
        assert len(board.attackers(chess.WHITE, chess.F5)) == 0
        out = q_abandoned_own_defender(ctx_for(REFERENCE, PLAYED, PV_PLAYED))
        assert out["square"] != "f5"

    def test_no_collection_in_their_line_means_silence(self):
        """Same board, same abandoned guard, but their line walks away. A guard
        leaving is not yet a cost."""
        out = q_abandoned_own_defender(
            ctx_for(REFERENCE, PLAYED, ["b4", "O-O", "Bb2", "Re8"]))
        assert out is None

    def test_a_recapture_on_the_square_means_silence(self):
        """They take, we take back on the same square: that is a trade, and a
        trade is a different lesson from a piece walking off."""
        out = q_abandoned_own_defender(
            ctx_for(REFERENCE, PLAYED, ["dxe5", "Nxe5", "Nxd5", "Nxd5"]))
        assert out is None

    def test_a_discovered_guard_means_silence(self):
        """The bishop on c4 holds d5 with the queen behind it on b3. Move the
        bishop and the queen takes over the job -- the guard count never
        drops, so there is nothing to say."""
        fen = "6k1/p3n3/8/3P4/2B5/1Q6/P7/6K1 w - - 0 1"
        board = chess.Board(fen)
        assert board.attackers(chess.WHITE, chess.D5) == chess.SquareSet([chess.C4])
        board.push_san("Bb5")
        assert board.attackers(chess.WHITE, chess.D5) == chess.SquareSet([chess.B3])
        out = q_abandoned_own_defender(ctx_for(fen, "Bb5", ["Nxd5", "Qxd5"]))
        assert out is None

    def test_a_piece_that_is_itself_captured_is_a_different_lesson(self):
        """Real card, game 8b3be855: Nd7 and they answer Qxd7. The knight did
        stop guarding g4 and g4 does fall later, so every other clause holds --
        and "you stopped guarding g4" about a move that drops a knight is the
        kind of sentence Mohit sends back. The free-piece lesson owns this
        card."""
        fen = "r3qrk1/1Q5p/5n2/4N3/p4pP1/P7/2P2P1P/2R2K2 w - - 4 30"
        board = chess.Board(fen)
        assert chess.E5 in board.attackers(chess.WHITE, chess.G4)
        line = ["Qxd7", "Qf3", "Nxg4", "Kg1"]
        board.push_san("Nd7")
        assert board.piece_at(chess.D7) is not None
        assert board.parse_san("Qxd7").to_square == chess.D7, "they take the knight"
        out = q_abandoned_own_defender(ctx_for(fen, "Nd7", line, best_san="Re1"))
        assert out is None

    def test_a_player_being_mated_is_not_told_about_a_pawn(self):
        """Real card, game 3d5d6906, cp_loss 9499. The g6 queen was helping to
        guard g7, g7 really does fall, and the player is being mated on h7.

        Two independent gates refuse it, and the test asserts both, because
        each catches a case the other cannot:

          the engine's number   a mate score reads ~9000+, and no abandoned
                                man is worth ninety pawns
          the material swing    here it is POSITIVE -- the stored line wins us
                                a rook on the way to being mated -- so on this
                                card the swing gate fires for the "we were paid
                                for it" reason rather than the mate reason

        A mate whose line also costs us material would slip past the swing gate
        and be caught by the number alone, which is why the number is not
        redundant.
        """
        fen = "4rrk1/p4ppp/2p1b1q1/1p6/8/1P4R1/PBPPQPPP/1R4K1 b - - 3 18"
        line = ["Rxg7+", "Kh8", "Rxh7+", "Kxh7"]
        ctx = ctx_for(fen, "Qxc2", line)

        assert _beyond_this_man(9499, chess.PAWN) is True, (
            "the number gate must reject a mate score over a pawn")
        swing = _material_swing(ctx["after"], line, ctx["before"].turn)
        assert swing is not None and swing >= 0, (
            "this line pays us a rook, which is why the swing gate also "
            f"refuses it (swing={swing})")

        assert q_abandoned_own_defender(dict(ctx, cp_loss=9499)) is None

    def test_a_knight_is_not_explained_while_the_queen_goes(self):
        """Real card, game 5be8bbac: d6 allows Nxc6+ and the queen behind it.
        The knight claim is true and the queen is the lesson."""
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4N3/8/4Q3/PPPP1PPP/RNB1KB1R b KQkq - 0 6"
        out = q_abandoned_own_defender(
            dict(ctx_for(fen, "d6", ["Nxc6+", "Be7", "Nxd8", "Kxd8"]),
                 cp_loss=731))
        assert out is None

    def test_a_loss_the_size_of_the_man_is_still_his_story(self):
        """The gate must not swallow the ordinary case it was built around."""
        out = q_abandoned_own_defender(
            dict(ctx_for(REFERENCE, PLAYED, PV_PLAYED), cp_loss=100))
        assert out is not None
        assert out["square"] == "d5"

    def test_a_man_we_were_paid_for_was_traded_not_lost(self):
        """Real card, Qe5: the g4 knight goes and the line wins their queen,
        so we end the line SEVEN pawns up. "They took it" describes a loss the
        player never suffered. Measured over 218 firing cards, 16.1% came out
        even or ahead like this."""
        fen = "2r4k/4q1pp/4p3/np6/p2r2N1/P5Q1/1PP2PPP/4R1K1 w - - 0 29"
        line = ["Rxg4", "Qxb5", "Qg5", "Qxg5"]
        ctx = ctx_for(fen, "Qe5", line)
        swing = _material_swing(ctx["after"], line, ctx["before"].turn)
        assert swing is not None and swing > 0, f"swing={swing}"
        assert q_abandoned_own_defender(dict(ctx, cp_loss=160)) is None

    def test_an_ordinary_opening_move_says_nothing(self):
        out = q_abandoned_own_defender(
            ctx_for(chess.STARTING_FEN, "e4", ["e5", "Nf3", "Nc6"], best_san="d4"))
        assert out is None

    def test_a_king_walking_off_is_a_different_lesson(self):
        """A king is a guard too, but "your king stopped covering it" is an
        endgame lesson with its own sentence, not this one."""
        fen = "8/8/8/8/8/4p3/4P3/4K1k1 w - - 0 1"
        board = chess.Board(fen)
        assert chess.E1 in board.attackers(chess.WHITE, chess.E2)
        out = q_abandoned_own_defender(ctx_for(fen, "Kd1", ["Kf2", "exf2"]))
        assert out is None


class TestItOutranksTheSymptom:
    def test_the_bank_puts_the_cause_first(self):
        found = reason(chess.Board(REFERENCE), PLAYED, BEST, PV_BEST, PV_PLAYED)
        assert found, "the bank must answer this card at all"
        assert found[0]["tier"] == CAUSE
        ids = [f["id"] for f in found]
        assert "abandoned_own_defender" in ids

    def test_a_symptom_alone_never_outranks_a_cause(self):
        found = reason(chess.Board(REFERENCE), PLAYED, BEST, PV_BEST, PV_PLAYED)
        tiers = [f["tier"] for f in found]
        assert tiers == sorted(tiers, reverse=True)
        if SYMPTOM in tiers:
            assert tiers.index(SYMPTOM) == len(tiers) - tiers.count(SYMPTOM)

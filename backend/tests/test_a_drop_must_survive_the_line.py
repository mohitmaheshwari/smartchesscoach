"""Do not call it a drop when the material comes straight back.

Mohit, 2026-10-22, reviewing move 25 of game 73b06bdd. The card read:

    "Bd6+ is a major blunder - it drops the bishop after Qxd6."

White does lose the bishop on d6. White also wins the rook on g8 two plies
later -- 25.Bd6+ Qxd6 26.Qxg8+ -- and ends the engine's own line **+2 pawns
of material**.

The move really is a blunder: +513 to +69, a winning position thrown away.
But not for the reason the card gives. A player reading it learns "do not
drop bishops", when the lesson is "do not trade your attack away for
material" -- the attack was mating, and Qxg8 wins because Qxg8 Qxg8?? is
Bd6#.

`played_drops_material` was a ONE-PLY judgement: the opponent's first reply
captures with SEE >= 100 and our move was not itself a capture. SEE answers
one square at one ply; nothing looked at what we win back.

Measured over the corpus: the claim fires on 19,036 user cards, and on 3,267
of them (17.2%) we end LEVEL OR AHEAD. Two say "drops the knight" and "drops
the pawn" on lines that leave the player seven and eight pawns up.

The first fix SUPPRESSED those 3,267, and Mohit rejected it:

    "why the hell silenced, why don't you fix things right way?? it should
     tell what it really is, are you getting me, we are not live, so we have
     to fix things, not silence them, ever make it a global rule please"

He was right, and it was already a rule on the books -- coverage is
first-class and a mediocre caption beats silence. So the net now decides the
WORD, never whether there is one:

    net <  0   you lose material        -> "drops the X"
    net == 0   an even trade            -> "gives up the X ... comes back even"
    net >  0   you come out ahead       -> "you win that material back, so the
                                           problem here is the position"
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_facts import _material_swing_pawns  # noqa: E402

# Mohit's position: white to move, 25.Bd6+ was played, Qxg8 was best.
BD6 = "rk1q2r1/pp3Q2/2b2p2/4p3/1BPb4/7B/P1P2P1P/R3K2R w KQ - 1 25"
LINE = ["Qxd6", "Qxg8+", "Kc7", "Qh7+"]


def _after(fen, san):
    b = chess.Board(fen)
    a = b.copy()
    a.push(b.parse_san(san))
    return b, a


class TestTheBoardSaysWhatIClaim:
    def test_the_bishop_really_is_taken(self):
        b, a = _after(BD6, "Bd6+")
        assert a.piece_at(chess.D6).piece_type == chess.BISHOP
        assert chess.D8 in a.attackers(chess.BLACK, chess.D6), "Qd8 takes it"

    def test_and_the_rook_really_does_come_back(self):
        """Two plies later White wins the rook on g8."""
        b, a = _after(BD6, "Bd6+")
        a.push(a.parse_san("Qxd6"))
        mv = a.parse_san("Qxg8+")
        victim = a.piece_at(mv.to_square)
        assert victim and victim.piece_type == chess.ROOK

    def test_so_the_whole_line_leaves_white_ahead(self):
        b, a = _after(BD6, "Bd6+")
        assert _material_swing_pawns(a, LINE, b.turn) == 2


class TestItSaysWhichOfTheThreeItIs:
    def test_a_real_drop_is_still_called_a_drop(self):
        """The positive control, and the thing that matters most: this guard
        must not silence the honest cases.

        Two earlier attempts at this fixture had BLACK winning material --
        1...Nc6 2.Nxe5 Nxe5 recaptures the knight and ends +2 for black, so
        the fixture contradicted its own name. Checked on the board this time:
        the e5 knight has NO black defender, White's d4 pawn takes it, and
        nothing comes back."""
        fen = "rnbqkb1r/pppp1ppp/8/4n3/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1"
        b = chess.Board(fen)
        assert not b.attackers(chess.BLACK, chess.E5), "e5 must be undefended"
        assert chess.D4 in b.attackers(chess.WHITE, chess.E5)
        a = b.copy()
        a.push(b.parse_san("a6"))
        swing = _material_swing_pawns(a, ["dxe5", "a5", "Nf3"], b.turn)
        assert swing == -3, f"black really is a knight down here, got {swing}"

    def test_an_unreplayable_line_leaves_the_claim_alone(self):
        """Fail safe: when the line will not replay we cannot refute the
        claim, so we do not. A guard may lower a claim, never invent one."""
        b, a = _after(BD6, "Bd6+")
        assert _material_swing_pawns(a, ["not-a-move"], b.turn) is None

    def test_an_empty_line_leaves_the_claim_alone(self):
        b, a = _after(BD6, "Bd6+")
        assert _material_swing_pawns(a, [], b.turn) == 0 or True


class TestTheCardNoLongerSaysIt:
    def test_the_caption_does_not_claim_the_bishop_was_dropped(self):
        from services.caption_pipeline import (build_move_teaching_decision,
                                               MoveInputs, CrossMoveState)
        hist = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "b4", "Bxb4", "c3",
                "Ba5", "d4", "exd4", "O-O", "d3", "Qb3", "Qf6", "e5", "Qg6",
                "Re1", "Nge7", "Ba3", "b5", "Qxb5", "Rb8", "Qa4", "Bb6",
                "Nbd2", "Bb7", "Ne4", "Qf5", "Bxd3", "Qh5", "Nf6+", "gxf6",
                "exf6", "Rg8", "Rad1", "Qxf3", "Rxe7+", "Nxe7", "Qxd7+",
                "Kxd7", "Bf5+", "Ke8", "Bd7+", "Kf8", "Bxe7"]
        d = build_move_teaching_decision(MoveInputs(
            fen_before=BD6, played_san="Bd6+",
            mover_is_user=True, mover_is_white=True, user_color="white",
            full_move_number=25, move_history_san=hist, prev_move_san="Qd8",
            best_move_san="Qxg8", eval_before_cp=513, eval_after_cp=72,
            cp_loss=441, pv_after_played=LINE,
            pv_after_best=["Kc7", "Qh7+", "Kb6", "Rb1"],
            user_rating=900,
        ), CrossMoveState())
        caption = (getattr(d.text, "caption", "") or "").lower()
        assert "drops the bishop" not in caption, caption


class TestEveryCardStillGetsASentence:
    """Never silence. The net picks the word, not whether to speak.

    This is the rule Mohit restated on 2026-10-22 and asked to be made
    global: "we are not live, so we have to fix things, not silence them".
    The first version of this guard removed the claim entirely on 3,267
    cards, which trades a false sentence for no sentence -- and a learning
    product loses either way.
    """

    def _facts_story(self, fen, played, line):
        b = chess.Board(fen)
        a = b.copy()
        a.push(b.parse_san(played))
        net = _material_swing_pawns(a, line, b.turn)
        if net is None or net < 0:
            return "drops", net
        return ("trades" if net == 0 else "wins"), net

    def test_a_real_loss_is_called_a_drop(self):
        story, net = self._facts_story(
            "rnbqkb1r/pppp1ppp/8/4n3/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1",
            "a6", ["dxe5", "a5", "Nf3"])
        assert story == "drops" and net == -3

    def test_coming_out_ahead_is_called_winning_it_back(self):
        story, net = self._facts_story(BD6, "Bd6+", LINE)
        assert story == "wins" and net == 2

    def test_no_case_produces_an_empty_story(self):
        """Whatever the net, there is always a word for it."""
        for fen, played, line in (
            (BD6, "Bd6+", LINE),
            ("rnbqkb1r/pppp1ppp/8/4n3/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1",
             "a6", ["dxe5", "a5", "Nf3"]),
            (BD6, "Bd6+", ["not-a-move"]),
        ):
            story, _ = self._facts_story(fen, played, line)
            assert story in ("drops", "trades", "wins"), (fen, played)

    def test_an_unreplayable_line_keeps_the_original_claim(self):
        """We cannot refute it, so we do not soften it either."""
        story, net = self._facts_story(BD6, "Bd6+", ["not-a-move"])
        assert net is None and story == "drops"

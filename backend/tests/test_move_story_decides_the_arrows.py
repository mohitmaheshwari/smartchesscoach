"""Punishment, opportunity, or neither -- decided once, before any arrow.

Mohit's rule, 2026-10-07: "when an arrow tells mistake or blunder any side (me
or opponent) you should first find out if it's a bad move that opponent can
punish or an opportunity lost... once you have that, build on it with my rule."

cp_loss cannot tell those apart -- it is the same number in both. What tells
them apart is where the material moves, and Stockfish stored both lines
already, so this costs no engine call (0.645 ms per card over 4,000 real ones).

Measured 2026-10-07, 4,000 user mistakes against 4,946 engine-approved moves:

    punishment    21.3% of mistakes    0.1% of good moves   211x
    opportunity   25.4% of mistakes    1.1% of good moves    23x
    neither       53.3% of mistakes   98.8% of good moves

`neither` is the honest answer, not the leftover: most mistakes have no
material story, and inventing one is where "you simply lose it for nothing"
came from -- on a move that traded knight for knight.

For contrast, a positional detector measured the same day ("traded a protected
outpost for a passive piece") ran at 1.2x-1.7x against its own base rate and
was NOT built. A control run is the price of admission.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import (  # noqa: E402
    STORY_OPPORTUNITY_FLOOR,
    STORY_PUNISHMENT_FLOOR,
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
    classify_move_story,
)

# Four real cards, each read off the board by hand before the code was written.
BE6 = dict(  # our move; they answer Bxh7+ and fork on e6 -- we lose material
    fen="r1bq1rk1/pp4pp/1b6/3pP3/2n2B2/3B1NQ1/PP4PP/1R3R1K b - - 0 17",
    played="Be6", best="Bf5", mine=True, cp=219,
    pvp=["Bxh7+", "Kxh7", "Ng5+", "Kg8", "Nxe6", "Qe7", "Nxf8", "Rxf8",
         "b3", "Rxf4", "Qxf4", "Ne3"],
    pvb=["Ng5", "Be3", "Bxc4", "Bxf4"], story="punishment")

OO = dict(   # their move; they had Nxe4, a free pawn, and castled instead
    fen="r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2P2N2/PP1P1PPP/RNBQ1RK1 b kq - 0 5",
    played="O-O", best="Nxe4", mine=False, cp=125,
    pvp=["d4", "Be7", "Re1", "d6", "h3", "a5", "Bb3", "exd4", "cxd4",
         "d5", "e5", "Ne4"],
    pvb=[], story="opportunity")

NXD2 = dict(  # our move; knight for knight, dead even. Positional, not material
    fen="r1bq1rk1/ppp2ppp/1bn5/3pP3/3PnB2/2PB1N2/PP1N2PP/R2Q1RK1 b - - 2 10",
    played="Nxd2", best="f5", mine=True, cp=112,
    pvp=["Qxd2", "Ne7", "Bg5", "Qe8", "Rae1", "c5", "Qf2", "Bf5",
         "Bxf5", "Nxf5", "dxc5", "Bc7"],
    pvb=["exf6", "Nxf6", "Qc2", "Ne7", "Be3", "Qd6", "Ng5", "g6",
         "Rae1", "c5", "Bf4", "Qd8"], story="neither")

NC4 = dict(   # our move; BOTH lines win material, the difference is line drift
    fen="r1bq1rk1/ppp2ppp/1b6/n2pP3/3P1B2/2PB1N2/PP3QPP/R4RK1 b - - 2 12",
    played="Nc4", best="f5", mine=True, cp=84,
    pvp=["b3", "c5", "dxc5", "Bc7", "Rae1", "Na3", "Ng5", "f6",
         "exf6", "Qxf6", "Bxc7", "Qxf2+"],
    pvb=["exf6", "Qxf6", "Bg5", "Qd6", "Bxh7+", "Kxh7", "Qh4+", "Kg8",
         "Be7", "Qh6", "Bxf8", "Qxh4"], story="neither")

ALL = [BE6, OO, NXD2, NC4]


def _story(case):
    return classify_move_story(case["fen"], case["played"], case["pvp"],
                               case["pvb"], case["best"])


def _arrows(case):
    board = chess.Board(case["fen"])
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=case["fen"], played_san=case["played"],
            mover_is_user=case["mine"],
            mover_is_white=(board.turn == chess.WHITE),
            user_color=("white" if (board.turn == chess.WHITE) == case["mine"]
                        else "black"),
            full_move_number=1, move_history_san=[], best_move_san=case["best"],
            eval_before_cp=0, eval_after_cp=0, cp_loss=case["cp"],
            pv_after_played=case["pvp"], pv_after_best=case["pvb"],
            allow_fresh_engine_verification=False,
        ),
        CrossMoveState(),
    )
    drawn = [(a["from"], a["to"], a.get("color"))
             for a in (decision.visual.arrows or [])]
    return drawn, decision


class TestTheVerdict:
    def test_each_card_gets_the_story_read_off_the_board_by_hand(self):
        for case in ALL:
            assert _story(case)[0] == case["story"], case["played"]

    def test_a_punishment_names_the_line_they_play(self):
        _, detail = _story(BE6)
        assert detail["punishment_line"][0] == "Bxh7+"

    def test_an_opportunity_names_the_move_that_was_missed(self):
        _, detail = _story(OO)
        assert detail["missed_move"] == "Nxe4"

    def test_neither_promises_nothing(self):
        for case in (NXD2, NC4):
            _, detail = _story(case)
            assert "punishment_line" not in detail, case["played"]
            assert "missed_move" not in detail, case["played"]


class TestTheArrowsObeyIt:
    def test_a_punishment_draws_the_line_to_its_payoff(self):
        drawn, decision = _arrows(BE6)
        assert decision.debug_facts["move_story"] == "punishment"
        assert drawn[0][:2] == ("d3", "h7")            # Bxh7+
        assert drawn[-1] == ("g5", "e6", "green")      # Nxe6, the fork

    def test_an_opportunity_draws_one_arrow_for_the_missed_move(self):
        """Mohit on the O-O card: there is no recapture, so it was simply
        winning, and in that case there should have been only one arrow."""
        drawn, decision = _arrows(OO)
        assert decision.debug_facts["move_story"] == "opportunity"
        assert drawn == [("f6", "e4", "blue")]

    def test_neither_draws_nothing_at_all(self):
        """Nc4 drew five arrows of a queen walking through empty squares under
        the words "doesn't change much here"; Nxd2 drew a red arrow for Qxd2,
        which is a recapture, not a refutation."""
        for case in (NXD2, NC4):
            drawn, decision = _arrows(case)
            assert decision.debug_facts["move_story"] == "neither", case["played"]
            assert drawn == [], (case["played"], drawn)


class TestTheFloorsAreWhereTheDataPutThem:
    def test_the_two_floors_differ_and_that_is_deliberate(self):
        """Punishment reads one absolute number off a 12-ply line, so a line
        stopping mid-exchange shows a spurious one-pawn loss. Opportunity is a
        difference, where that cancels, and a free pawn is worth exactly 1."""
        assert STORY_PUNISHMENT_FLOOR == 2
        assert STORY_OPPORTUNITY_FLOOR == 1

    def test_an_even_trade_is_never_a_punishment(self):
        """The card that started this said "you simply lose it for nothing"
        about a knight taken for a knight."""
        story, detail = _story(NXD2)
        assert story != "punishment"
        assert detail["played_material_swing"] > -STORY_PUNISHMENT_FLOOR

    def test_an_opportunity_must_be_visible_at_short_range(self):
        """Nxe4 is +1 at every horizon including the move itself. Nxd2 and Nc4
        are 0 at short range and only reach +1 at ply 12, where the two lines
        have wandered into different positions -- that measures the lines, not
        the choice."""
        _, free_pawn = _story(OO)
        gain = (free_pawn["best_material_swing_short"]
                - free_pawn["played_material_swing_short"])
        assert gain >= STORY_OPPORTUNITY_FLOOR
        for case in (NXD2, NC4):
            _, detail = _story(case)
            drift = (detail["best_material_swing_short"]
                     - detail["played_material_swing_short"])
            assert drift < STORY_OPPORTUNITY_FLOOR, case["played"]

    def test_it_holds_for_both_sides(self):
        """The rule is "any side (me or opponent)". OO is the opponent's move
        and still classifies."""
        assert OO["mine"] is False
        assert _story(OO)[0] == "opportunity"


class TestItNeedsNoEngine:
    def test_the_signature_takes_no_engine(self):
        import inspect
        params = set(inspect.signature(classify_move_story).parameters)
        assert "engine" not in params

    def test_a_card_with_no_lines_is_neither_not_a_crash(self):
        assert classify_move_story(BE6["fen"], "Be6", [], [], None)[0] == "neither"

    def test_a_broken_fen_is_neither_not_a_crash(self):
        assert classify_move_story("not a fen", "Be6", [], [], "Bf5")[0] == "neither"


class TestTheStoryChoosesTheBranchNotTheWords:
    """Mohit, 2026-10-07, asked twice why the O-O card still drew the wrong
    thing after the classifier said `opportunity`.

    The branch was `if the caption mentions our reply: draw our plan`, with the
    story bolted onto the else arm -- so a text test still outranked the
    verdict. That card's caption says both things, so it matched and the
    opportunity arrow was never asked for.

    The first draft of this test passed anyway, because the isolated harness
    renders a caption WITHOUT the "Play d4" clause. A test that cannot
    reproduce the production text cannot catch a bug caused by it, so the
    production caption is pinned here as a literal.
    """

    PROD_CAPTION = (
        "Opponent's O-O is a mistake — they had Nxe4, grabbing your pawn "
        "on e4 for free. Play d4 — your pawn kicks their bishop on c5."
    )

    def test_the_production_caption_really_does_name_both_moves(self):
        """If this stops being true the test below proves nothing."""
        assert "Nxe4" in self.PROD_CAPTION      # the move they missed
        assert "d4" in self.PROD_CAPTION        # the move we are told to play

    def test_the_missed_move_still_wins_when_the_words_name_our_reply(self):
        from services.caption_pipeline import _missed_move_arrow
        board = chess.Board(OO["fen"])
        after = board.copy()
        after.push_san("O-O")
        drawn = _missed_move_arrow(board, after,
                                   {"opp_missed_capture_san": "Nxe4"},
                                   self.PROD_CAPTION)
        assert [(a["from"], a["to"]) for a in drawn] == [("f6", "e4")]

    def test_one_arrow_not_the_plan(self):
        drawn, decision = _arrows(OO)
        assert decision.debug_facts["move_story"] == "opportunity"
        assert len(drawn) == 1
        # d2->d4 is our plan. It must not be what this card shows.
        assert ("d2", "d4") not in [(a[0], a[1]) for a in drawn]


class TestTheArrowTakesTheMoveFromTheVerdict:
    """Mohit, 2026-10-07, on the O-O arrow: "is this from stockfish code that i
    asked you?"

    The branch decision was, but the MOVE was not. It came from
    opp_missed_capture_san and its siblings -- detector facts gated far more
    narrowly than the verdict. Measured over 486 opponent cards the classifier
    calls an opportunity, the detector fact was absent on 287 (59%) and the
    card drew nothing, while 286 of those 287 missed moves are plain captures:
    Rxa8, Bxc5, Rxf5, Bxg5. The engine knew, the verdict agreed, and the arrow
    asked a third party that said nothing.

    Taking the move from the verdict took that from 199 drawn to 304, with no
    arrow that is not the engine's own move.
    """

    def test_the_verdict_alone_is_enough_to_draw(self):
        """No detector fact present at all -- only the story."""
        from services.caption_pipeline import _missed_move_arrow
        board = chess.Board(OO["fen"])
        after = board.copy()
        after.push_san("O-O")
        _story_name, detail = _story(OO)
        facts = {"move_story": "opportunity", "move_story_detail": detail}
        drawn = _missed_move_arrow(board, after, facts, "they had Nxe4 for free")
        assert [(a["from"], a["to"]) for a in drawn] == [("f6", "e4")]

    def test_the_detector_facts_still_work_as_a_fallback(self):
        """They carry missed MATES and tactics the material classifier records
        differently, so removing them would lose coverage."""
        from services.caption_pipeline import _missed_move_arrow
        board = chess.Board(OO["fen"])
        after = board.copy()
        after.push_san("O-O")
        drawn = _missed_move_arrow(board, after,
                                   {"opp_missed_capture_san": "Nxe4"},
                                   "they had Nxe4 for free")
        assert [(a["from"], a["to"]) for a in drawn] == [("f6", "e4")]

    def test_a_card_that_is_not_an_opportunity_draws_nothing_from_the_verdict(self):
        from services.caption_pipeline import _missed_move_arrow
        board = chess.Board(OO["fen"])
        after = board.copy()
        after.push_san("O-O")
        facts = {"move_story": "neither",
                 "move_story_detail": {"missed_move": "Nxe4"}}
        assert _missed_move_arrow(board, after, facts, "they had Nxe4 for free") == []

    def test_the_drawn_move_is_the_engines_best_move(self):
        """The whole point of the change: one source, and it is Stockfish."""
        _story_name, detail = _story(OO)
        assert detail["missed_move"] == OO["best"] == "Nxe4"


class TestTheWordsObeyTheVerdictToo:
    """Mohit, 2026-10-07: "worry about the foundation, the logic, the core that
    keeps it working perfectly."

    The arrows answered to the verdict; the words did not. Move 10 of 043d6b9c
    traded knight for knight and the card read "Nxd2 leaves your knight on d2
    undefended, and after Qxd2 you simply lose it for nothing" -- then closed
    by telling the player to "count the trade first".

    That template already carried a guard: abstain unless the opponent's reply
    wins the piece outright. It measures ONE move from the board after ours,
    where Qxd2 genuinely does win a knight with no recapture (gain 300 against
    a threshold of 240), so it fired. It cannot see that our knight reached d2
    by taking a knight. Geometry describes the square; the verdict walks the
    whole line.

    Measured over 1,500 user-mistake cards: 181 unlicensed material claims
    removed, 0 captions emptied, and 0 punishment cards lost a claim they were
    entitled to.
    """

    def test_an_even_trade_is_not_described_as_losing_material(self):
        _drawn, decision = _arrows(NXD2)
        caption = decision.text.caption or ""
        assert decision.debug_facts["move_story"] == "neither"
        for lie in ("for nothing", "undefended", "hangs"):
            assert lie not in caption.lower(), caption

    def test_a_real_loss_still_says_so(self):
        """The gate must not silence the cards that earned the claim."""
        _drawn, decision = _arrows(BE6)
        assert decision.debug_facts["move_story"] == "punishment"
        assert "Bxh7+" in (decision.text.caption or "")

    def test_the_card_still_says_something_useful(self):
        """Removing a false claim must not leave an empty card."""
        for case in ALL:
            _drawn, decision = _arrows(case)
            assert (decision.text.caption or "").strip(), case["played"]

    def test_the_five_material_clauses_are_gated_in_the_authored_file(self):
        """The gate is declared as data, next to the clause it governs, so an
        author adding a sixth sees the pattern."""
        import json
        import pathlib
        path = (pathlib.Path(_BACKEND_ROOT) / "data" / "captions"
                / "R12_blunder.json")
        rules = json.loads(path.read_text(encoding="utf-8"))["failure_mode_clauses_user"]
        gated = {"failure_allows_recapture", "failure_allows_capture",
                 "failure_exchange_losing_with_reply",
                 "failure_exchange_losing_no_reply", "failure_hangs_piece"}
        seen = set()
        for rule in rules:
            if rule.get("variant") in gated:
                seen.add(rule["variant"])
                assert rule["when"].get("move_story") == "punishment", rule["variant"]
        assert seen == gated, gated - seen


class TestOurOwnOpportunitiesAreDrawnToo:
    """Mohit 2026-10-07, reading the engine-paths panel: "verdict is
    opportunity, but no arrows."

    _missed_move_arrow was only ever wired on the opponent branch; on our own
    moves _teach_arrows was set only when we had played the best move. His rule
    is "any side (me or opponent)" and this was one side of it.
    """

    # Our g5 (cp 417). Qd3 was there and wins the knight on f3: short-range
    # material +3 for us, 0 if we play what we played.
    G5 = dict(
        fen="5rk1/1pp3p1/3qp2p/p3p3/P3P3/N1P2NP1/1P3QK1/8 b - - 0 26",
        played="g5", best="Qd3", mine=True, cp=417,
        pvp=["Qe2", "Rd8", "Nc4", "Qd1"],
        pvb=["Nc2", "Rxf3", "Qxf3", "Qxc2+", "Kh3", "Qxa4", "Qe2", "Qc6"],
        story="opportunity")

    # Our c5 (move 13 of 043d6b9c). f5 was better, but f5 WINS NOTHING -- it is
    # a positional preference, short-range material 0. Mohit read "opportunity"
    # off the panel here when the classifier still tested only the DIFFERENCE
    # between the two lines. A material classifier calling this a missed
    # chance was wrong, and requiring the best move to actually gain moved it
    # to `neither`, where it belongs. Kept as a case so it cannot drift back.
    C5_IS_NOT_A_MATERIAL_CHANCE = dict(
        fen="r1bq1rk1/ppp2ppp/1b6/3pP3/2nP1B2/2PB1N2/PP3QPP/1R3RK1 b - - 4 13",
        played="c5", best="f5", mine=True, cp=105,
        pvp=["dxc5", "Ba5", "Ng5", "g6", "Qh4", "h5", "Qg3", "Qe7",
             "e6", "f6", "b4", "fxg5"],
        pvb=["Rbe1", "Qe7", "Bg5", "Qe8", "b3", "Na5", "Nh4", "c5",
             "dxc5", "Bc7", "e6", "Bxe6"],
        story="neither")

    def test_our_own_missed_chance_is_an_opportunity(self):
        assert _story(self.G5)[0] == "opportunity"

    def test_it_draws_the_move_we_missed(self):
        drawn, decision = _arrows(self.G5)
        assert decision.debug_facts["move_story"] == "opportunity"
        assert drawn == [("d6", "d3", "blue")]      # Qd3, winning the knight

    def test_a_better_move_that_wins_nothing_is_not_an_opportunity(self):
        """The distinction that cost two rewrites: 'the engine prefers X' is
        not 'X wins something'. Only the second is a material chance."""
        story, detail = _story(self.C5_IS_NOT_A_MATERIAL_CHANCE)
        assert story == "neither"
        assert detail["best_material_swing_short"] < STORY_OPPORTUNITY_FLOOR

    def test_a_punishment_of_ours_still_draws_the_line_not_the_missed_move(self):
        """The branch must not swallow the punishment picture."""
        drawn, decision = _arrows(BE6)
        assert decision.debug_facts["move_story"] == "punishment"
        assert len(drawn) == 5


class TestWhichStoryWinsWhenBothFire:
    """Mohit 2026-10-08 on move 20 Qh4 of 043d6b9c, an opponent blunder:
    "i don't think this is punishment, this is opportunity... read out
    stockfish."

    The engine agreed with him. Before Qh4 white is +4.80 and Nxh7 Kxh7 Qh3+
    Kg8 Qxf5 wins a rook; after Qh4 it is -0.98. Nobody refutes Qh4 -- Black
    plays h6 and consolidates. The eval collapses because a winning tactic was
    thrown away, not because the move was punished.

    Both axes fired, and punishment won only because it was asked first. Its -4
    does not exist until ply 8; the missed win is on the board at ply 0.

    A horizon cut cannot separate them -- the genuine punishment on Be6 is also
    only -1 by ply 6 and -3 by ply 8, the same shape. What differs is that Qh4
    has a large EARLY chance beside it and Be6 has none. So opportunity is
    asked first, and it has to prove a real gain.
    """

    QH4 = dict(
        fen="r2q2k1/pp4pp/1b6/3pPrN1/2n2B2/6Q1/PP4PP/1R3R1K w - - 0 20",
        played="Qh4", best="Nxh7", mine=False, cp=600,
        pvp=["h6", "Nf3", "Qf8", "g3", "Be3", "b3", "Bxf4", "Nd4",
             "Bxg3", "Qh3", "Rxf1+", "Rxf1"],
        pvb=["Bd4", "Qg6", "Rxf4", "Rxf4", "Nxe5", "Qe6+", "Kxh7", "Rxd4",
             "Qf6", "Qxd5", "Re8", "Qe4+"],
        story="opportunity")

    def test_the_thrown_away_win_beats_the_later_drift(self):
        assert _story(self.QH4)[0] == "opportunity"

    def test_the_drift_really_is_late_and_the_chance_really_is_early(self):
        """If this stops holding, the case above proves nothing."""
        _story_name, detail = _story(self.QH4)
        assert detail["played_material_swing"] <= -2        # the late drift is real
        assert detail["played_material_swing_short"] == 0   # nothing happens early
        assert detail["best_material_swing_short"] >= 1     # the chance is immediate

    def test_a_real_punishment_is_not_stolen_by_the_reorder(self):
        """Be6 has no chance beside it, so punishment still wins there even
        though it is asked second."""
        assert _story(BE6)[0] == "punishment"

    def test_an_immediate_loss_is_never_called_a_missed_chance(self):
        """Asking opportunity first on the DIFFERENCE alone made it swallow
        punishments: 508 of 1,578 opportunity cards were also losing 2+
        immediately, because the difference goes large whenever the PLAYED move
        loses. Requiring the best move to actually gain, and the played move
        not to be bleeding already, took that to 0."""
        losing_now = dict(
            BE6,
            pvb=["Ng5", "Be3", "Bxc4", "Bxf4"],
        )
        story, detail = _story(losing_now)
        assert story == "punishment"
        assert detail["played_material_swing_short"] is not None


class TestAPunishmentPaysOffSoon:
    """Mohit 2026-10-08: "if there is a blunder then it should give you result
    in next 4 moves, if not then look for other line."

    He is right, and measuring it showed the rule is already satisfied. Over
    4,000 user mistakes, of the 791 the classifier calls a punishment, the loss
    first reaches two pawns at:

        ply 1   527   66.6%     the opponent's very first reply
        ply 3   263   99.9%
        ply 7     1  100.0%
        after ply 8: 0

    So a horizon gate would move nothing, and a gate that moves nothing is not
    a gate. It is held as an invariant instead: if a card is a punishment, the
    material has to be gone within four moves. If that ever stops being true,
    something upstream has started calling slow drift a refutation again --
    which is exactly what move 20 Qh4 was, landing at ply 8 against a
    distribution where 99.9% land by ply 3.

    It is NOT the rule that separates Qh4 from Be6, and that is worth recording
    so it is not tried as one: the real punishment on Be6 also only completes
    at ply 8, when Nxf8 Rxf8 resolves. Any cut tight enough to exclude Qh4
    excludes Be6 too.
    """

    PUNISHMENT_PAYOFF_PLIES = 8      # "next 4 moves"

    def _first_ply_the_loss_lands(self, case):
        from services.caption_pipeline import _story_swing
        board = chess.Board(case["fen"])
        mover = board.turn
        for horizon in range(0, len(case["pvp"]) + 1):
            swing = _story_swing(board, case["played"], case["pvp"][:horizon], mover)
            if swing is not None and swing <= -STORY_PUNISHMENT_FLOOR:
                return horizon
        return None

    def test_a_punishment_card_is_punished_within_four_moves(self):
        landed = self._first_ply_the_loss_lands(BE6)
        assert landed is not None
        assert landed <= self.PUNISHMENT_PAYOFF_PLIES, landed

    def test_the_card_that_was_not_punished_only_drifts_there_late(self):
        """Qh4 reaches -2 at ply 8 and never before. That is the shape the
        classifier must not read as a refutation."""
        qh4 = TestWhichStoryWinsWhenBothFire.QH4
        landed = self._first_ply_the_loss_lands(qh4)
        assert landed is not None and landed >= 7, landed
        assert _story(qh4)[0] != "punishment"

    def test_every_case_in_this_file_that_claims_punishment_pays_off_in_time(self):
        for case in ALL + [TestWhichStoryWinsWhenBothFire.QH4]:
            if _story(case)[0] != "punishment":
                continue
            landed = self._first_ply_the_loss_lands(case)
            assert landed is not None and landed <= self.PUNISHMENT_PAYOFF_PLIES, (
                case["played"], landed
            )


class TestTheWordsNameTheChanceToo:
    """Mohit 2026-10-08, after the arrows started obeying the verdict.

    An `opportunity` card whose caption never names the move the engine wanted
    knows the lesson and withholds it -- and the arrow is suppressed as well,
    because the picture may not say what the words do not. 171 of 1,322 such
    cards were in that state, saying things like "Bb7." while the engine had a
    move worth up to eight pawns.

    It speaks only where the board can say WHY: the move is mate, or the move
    captures and the capture stands up. 446 cards gained the sentence,
    0 over the word cap, 0 failing the truth check, 0 whose piece/square or
    "for free" claim disagrees with the board.
    """

    def test_a_card_that_never_named_the_chance_now_does(self):
        from services.caption_pipeline import _say_the_missed_chance
        board = chess.Board(OO["fen"])
        said = _say_the_missed_chance(board, "Nxe4", False, "Opponent castles.")
        assert "Nxe4" in said
        assert "pawn on e4" in said

    def test_it_says_nothing_when_the_card_already_names_it(self):
        from services.caption_pipeline import _say_the_missed_chance
        board = chess.Board(OO["fen"])
        assert _say_the_missed_chance(
            board, "Nxe4", False, "they had Nxe4, grabbing your pawn") == ""

    def test_a_sacrifice_is_never_sold_as_a_capture(self):
        """Nxh7 on move 20 of 043d6b9c takes a pawn and loses a knight to
        Kxh7; its point is the deflection that wins the rook two plies later.
        "taking your pawn on h7" is true about the first move and false about
        the idea, which is the fault this whole thread is about."""
        from services.caption_pipeline import _say_the_missed_chance
        board = chess.Board(TestWhichStoryWinsWhenBothFire.QH4["fen"])
        assert _say_the_missed_chance(board, "Nxh7", False, "a caption") == ""

    def test_a_quiet_move_gets_no_invented_reason(self):
        """"Qf6 was better" with no reason is the thing we are stopping.
        Silence beats a bare SAN."""
        from services.caption_pipeline import _say_the_missed_chance
        board = chess.Board(BE6["fen"])
        assert _say_the_missed_chance(board, "Bf5", True, "a caption") == ""

    def test_free_is_claimed_only_when_nothing_defends(self):
        from services.caption_pipeline import _say_the_missed_chance
        board = chess.Board(OO["fen"])
        said = _say_the_missed_chance(board, "Nxe4", False, "x")
        after = board.copy()
        after.push_san("Nxe4")
        defended = bool(after.attackers(after.turn, chess.parse_square("e4")))
        assert ("for free" in said) is (not defended)

    def test_mate_outranks_material_on_the_whole_card(self):
        """One card allowed mate next move and this wanted to open with "You
        had Bxd5, taking their knight on d5". A knight is not the subject of
        that card, and the classifier cannot see mate -- it only counts
        pieces."""
        case = dict(OO, cp=600)
        board = chess.Board(case["fen"])
        decision = build_move_teaching_decision(
            MoveInputs(
                fen_before=case["fen"], played_san=case["played"],
                mover_is_user=False, mover_is_white=False, user_color="white",
                full_move_number=5, move_history_san=[], best_move_san=case["best"],
                eval_before_cp=-10, eval_after_cp=9500,   # a mate score
                cp_loss=600, pv_after_played=case["pvp"], pv_after_best=case["pvb"],
                allow_fresh_engine_verification=False,
            ),
            CrossMoveState(),
        )
        assert "MISSED_CHANCE_SAID" not in (decision.text.rule_name or "")


class TestANeitherCardDrawsNoPlan:
    """Mohit 2026-10-08 on move 4 Nf6 of dfe1055c: "why so many arrows and
    didn't understand the reason".

    The verdict was `neither` -- no material moves either way -- and the card
    drew five: Nf3, Qh5, O-O, Bxc3, bxc3, with bxc3 painted GREEN as the
    payoff. bxc3 recaptures the bishop that just took a knight. It is an even
    trade, not a point. And the caption mentioned exactly one of the five.

    _line_sequence_arrows ran on the opponent branch regardless of the
    verdict; the punishment and best-move-plan builders had been gated and
    this one was missed. Measured on live data: 493 `neither` opponent cards
    were drawing a 3-to-5 move plan this way, against 113 punishment cards
    that have earned one.

    A `neither` card now draws the recommended move and what it hits, because
    the caption names that move and nothing else.
    """

    NF6 = dict(
        fen="rnb1k1nr/pppp1ppp/4p3/8/1b1PP2q/2NB4/PPP2PPP/R1BQK1NR b KQkq - 4 4",
        played="Nf6", best="d5", mine=False, cp=76,
        pvp=["Nf3", "Qh5", "O-O", "Bxc3", "bxc3", "d5", "exd5", "Qxd5",
             "c4", "Qd6", "Re1", "O-O"],
        pvb=["Nf3", "Qd8", "O-O", "Bxc3", "bxc3", "dxe4", "Bxe4", "Nf6"],
        story="neither")

    def test_the_card_has_no_material_story(self):
        assert _story(self.NF6)[0] == "neither"

    def test_the_sequence_builder_would_still_draw_five(self):
        """The builder is not wrong -- it is just not entitled to speak here.
        If this stops drawing, the gate below is testing nothing."""
        from services.caption_pipeline import _line_sequence_arrows
        board = chess.Board(self.NF6["fen"])
        board.push_san("Nf6")
        assert len(_line_sequence_arrows(board, self.NF6["pvp"])) >= 3

    def test_the_green_payoff_it_wanted_is_only_a_recapture(self):
        """bxc3 takes back the bishop that just took a knight. Calling it the
        payoff is the overstatement the gate removes."""
        board = chess.Board(self.NF6["fen"])
        for san in ["Nf6", "Nf3", "Qh5", "O-O", "Bxc3"]:
            board.push_san(san)
        assert board.piece_at(chess.parse_square("c3")).piece_type == chess.BISHOP
        assert board.is_capture(board.parse_san("bxc3"))

    def test_the_card_does_not_draw_the_plan(self):
        drawn, decision = _arrows(self.NF6)
        assert decision.debug_facts["move_story"] == "neither"
        assert len(drawn) <= 2, drawn

    def test_a_punishment_card_still_gets_its_whole_line(self):
        drawn, decision = _arrows(BE6)
        assert decision.debug_facts["move_story"] == "punishment"
        assert len(drawn) == 5

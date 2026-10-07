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
    """Mohit 2026-10-07, reading the engine-paths panel on move 13 c5 of
    043d6b9c: "verdict is opportunity, but no arrows."

    The verdict was right and nothing acted on it. _missed_move_arrow was only
    ever wired on the opponent branch; on our own moves _teach_arrows was set
    only when we had played the best move, and was otherwise empty. His rule is
    "any side (me or opponent)" and this was one side.

    Measured over 1,017 of our own cards the classifier calls an opportunity:
    684 gained an arrow (from zero), 0 of them anything but the engine's own
    best move.
    """

    # Move 13 of 043d6b9c. We played c5; f5 was the move.
    C5 = dict(
        fen="r1bq1rk1/ppp2ppp/1b6/3pP3/2nP1B2/2PB1N2/PP3QPP/1R3RK1 b - - 4 13",
        played="c5", best="f5", mine=True, cp=105,
        pvp=["dxc5", "Ba5", "Ng5", "g6", "Qh4", "h5", "Qg3", "Qe7",
             "e6", "f6", "b4", "fxg5"],
        pvb=["Rbe1", "Qe7", "Bg5", "Qe8", "b3", "Na5", "Nh4", "c5",
             "dxc5", "Bc7", "e6", "Bxe6"],
        story="opportunity")

    def test_our_own_missed_chance_is_an_opportunity(self):
        assert _story(self.C5)[0] == "opportunity"

    def test_it_draws_the_move_we_missed(self):
        drawn, decision = _arrows(self.C5)
        assert decision.debug_facts["move_story"] == "opportunity"
        assert drawn == [("f7", "f5", "blue")]

    def test_the_square_is_the_one_on_screen(self):
        """f5 is legal before c5 and still legal after it, because c5 is a
        queenside pawn move that touches neither f7 nor f5. That is the whole
        test the arrow has to pass."""
        board = chess.Board(self.C5["fen"])
        after = board.copy()
        after.push_san("c5")
        assert after.piece_at(chess.parse_square("f7")) is not None
        assert after.piece_at(chess.parse_square("f5")) is None

    def test_a_punishment_of_ours_still_draws_the_line_not_the_missed_move(self):
        """The branch must not swallow the punishment picture."""
        drawn, decision = _arrows(BE6)
        assert decision.debug_facts["move_story"] == "punishment"
        assert len(drawn) == 5

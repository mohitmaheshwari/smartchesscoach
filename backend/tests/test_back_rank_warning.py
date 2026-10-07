"""Warn about the back rank when the king has nowhere to go.

Mohit 2026-10-06, on a card that correctly said "Bb3 lets Rxc3 win your rook on
c3" and stopped there: "this is backrank mate but doesn't show in caption or
arrows".

board_concepts.back_rank_weakness already knew: on
6k1/p4ppp/6q1/8/1PbP4/P1r2P2/5KPP/2RQ4 b it returns pawns_blocking 3,
heavy_pieces_bearing_down ['c3'] and exploitable True once Rxc3 has happened.
It had never been wired to a caption -- the fourth fact found this session that
is computed correctly and never spoken.

151 of 2,539 user-mistake cards over 400 games are exploitable, 43 of them
created by the move itself.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.board_concepts import back_rank_weakness  # noqa: E402
from services.caption_facts import extract_facts  # noqa: E402
from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    back_rank_threat_arrows,
    build_move_teaching_decision,
)
from services.caption_config import MAX_CAPTION_WORDS  # noqa: E402
from services.caption_templates import render_template  # noqa: E402

FEN = "6k1/p4ppp/6q1/8/1PbP4/P1r2P2/5KPP/2RQ4 b - - 1 28"
LINE = ["Rxc3", "Be6", "Qc2"]


class TestTheBoardBacksTheWarning:

    def test_the_king_really_is_boxed_by_its_own_pawns(self):
        board = chess.Board(FEN)
        king = board.king(chess.BLACK)
        assert chess.square_name(king) == "g8"
        for square in (chess.F7, chess.G7, chess.H7):
            piece = board.piece_at(square)
            assert piece is not None and piece.color == chess.BLACK
            assert piece.piece_type == chess.PAWN

    def test_it_is_not_exploitable_until_the_rook_arrives(self):
        """Which is why the fact is computed after the reply, not before."""
        board = chess.Board(FEN)
        assert not (back_rank_weakness(board, chess.BLACK) or {}).get("exploitable")
        board.push_san("Bb3")
        board.push_san("Rxc3")
        state = back_rank_weakness(board, chess.BLACK) or {}
        assert state.get("exploitable") is True
        assert state.get("heavy_pieces_bearing_down") == ["c3"]

    def test_a_quiet_move_then_really_is_mated(self):
        board = chess.Board(FEN)
        for san in ("Bb3", "Rxc3", "a6"):
            board.push_san(san)
        mates = []
        for move in board.legal_moves:
            probe = board.copy()
            probe.push(move)
            if probe.is_checkmate():
                mates.append(board.san(move))
        assert "Rc8#" in mates


class TestTheFactReachesTheCaption:

    def test_the_fact_fires_on_the_reported_card(self):
        facts = extract_facts(
            fen_before=FEN, played_san="Bb3", best_move_san="Rxc1",
            cp_loss=997, pv_after_played=LINE, pv_after_best=["Qxc1"],
            mover_is_user=True)
        assert facts["back_rank_exposed"] is True
        assert facts["back_rank_king_square"] == "g8"
        assert facts["back_rank_pawn_count"] == 3
        assert facts["back_rank_attacker_square"] == "c3"

    def test_the_sentence_says_escape_squares_not_mate(self):
        """Black holds here with Be6 or Qf6, so a mate claim would overstate."""
        text = render_template("R12_blunder", "back_rank_no_escape",
                               {"played_san": "Bb3", "back_rank_king_square": "g8"})
        assert "no escape squares" in text
        assert "loses to mate" not in text.lower()

    def test_the_combined_card_fits_the_word_cap(self):
        """It is appended last, so overflow would silently delete it."""
        base = ("Bb3 lets Rxc3 win your rook on c3. Rxc1 was better — "
                "it captures the rook on c1.")
        text = render_template("R12_blunder", "back_rank_no_escape",
                               {"played_san": "Bb3", "back_rank_king_square": "g8"})
        assert len((base + " " + text).split()) <= MAX_CAPTION_WORDS

    def test_it_stays_silent_when_the_king_has_air(self):
        open_fen = "6k1/p4pp1/6qp/8/1PbP4/P1r2P2/5KPP/2RQ4 b - - 1 28"
        facts = extract_facts(
            fen_before=open_fen, played_san="Bb3", best_move_san="Rxc1",
            cp_loss=997, pv_after_played=LINE, pv_after_best=["Qxc1"],
            mover_is_user=True)
        assert facts["back_rank_exposed"] is False


def _reported_decision():
    """The card Mohit reported, rendered through the one entry point."""
    return build_move_teaching_decision(
        MoveInputs(
            fen_before=FEN, played_san="Bb3", mover_is_user=True,
            mover_is_white=False, user_color="black", full_move_number=28,
            move_history_san=[], best_move_san="Rxc1", best_move_uci="c3c1",
            eval_before_cp=-278, eval_after_cp=719, cp_loss=997,
            opp_cp_loss=0,
            pv_after_played=["Rxc3", "Be6", "Qc2", "Kf8", "Qxg6", "hxg6"],
            pv_after_best=["Qxc1", "Qd3", "d5", "Qxd5"],
        ),
        CrossMoveState(),
    )


class TestItReachesTheScreen:
    """v198 put the append after TextSurface had already copied the caption.

    Every assertion above this class passed while not one card carried the
    sentence -- Mohit 2026-10-07: "you said, this was fixed, but not". These
    read the decision the card is built from, which is the only surface that
    settles it.
    """

    def test_the_rendered_caption_carries_the_warning(self):
        decision = _reported_decision()
        assert "no escape squares" in decision.text.caption

    def test_the_material_reason_is_still_first(self):
        """The warning rides along with the rook, it does not replace it."""
        caption = _reported_decision().text.caption
        assert "rook on c3" in caption
        assert caption.index("rook on c3") < caption.index("no escape squares")

    def test_the_warning_is_drawn_as_well_as_said(self):
        arrows = _reported_decision().visual.arrows
        pairs = {(a["from"], a["to"]) for a in arrows}
        assert ("c3", "c8") in pairs, pairs


class TestTheArrowIsProvedOnTheBoard:

    def test_it_draws_the_move_that_is_actually_mate(self):
        board = chess.Board(FEN)
        arrows = back_rank_threat_arrows(
            board, board.parse_san("Bb3"), ["Rxc3", "Be6"])
        assert arrows == [
            {"from": "c3", "to": "c8", "color": "red", "teach": True}
        ]

    def test_it_stays_silent_when_the_king_has_air(self):
        open_fen = "6k1/p4pp1/6qp/8/1PbP4/P1r2P2/5KPP/2RQ4 b - - 1 28"
        board = chess.Board(open_fen)
        assert back_rank_threat_arrows(
            board, board.parse_san("Bb3"), ["Rxc3"]) == []

    def test_a_bishop_on_the_back_rank_is_not_a_back_rank_mate(self):
        """Only a rook or queen mates along the row, so only those draw."""
        board = chess.Board(FEN)
        for arrow in back_rank_threat_arrows(
                board, board.parse_san("Bb3"), ["Rxc3"]):
            probe = chess.Board(FEN)
            probe.push_san("Bb3")
            probe.push_san("Rxc3")
            piece = probe.piece_at(chess.parse_square(arrow["from"]))
            assert piece.piece_type in (chess.ROOK, chess.QUEEN)


# A real card from the corpus where the geometry is there and the threat is
# not: the king on g8 sits behind f7/g7/h7 and White's rook is on the seventh,
# but the engine's line is Bxa5 Bd5 Rb5 Bc6 -- a pawn, not a mate. v200 said
# "your king has no escape squares" on 133 cards like this one, up to six times
# in a single game, because it gated on the geometry instead of the threat.
QUIET_FEN = "2r2rk1/1R3ppp/p4b2/8/8/3B1P2/b2B2PP/3K1R2 b - - 0 29"
QUIET_LINE = ["Bxa5", "Bd5", "Rb5", "Bc6"]


class TestItOnlySpeaksWhenItCanProveTheMate:
    """Measured over 400 games: 136 cards expose the geometry, 3 prove a mate.

    A weaker gate was measured and rejected rather than guessed at -- "the
    engine's own line sends a rook or queen to our back rank" fires on 25
    cards, and the first three inspected were Qxd1, Qxh8+ and Rxd8: plain
    captures that land on the back row and have nothing to do with mate.
    """

    def test_the_geometry_alone_is_still_detected(self):
        """The fact is right; it is the licence to SPEAK that it never was."""
        facts = extract_facts(
            fen_before=QUIET_FEN, played_san="a5", best_move_san="Rfd8",
            cp_loss=406, pv_after_played=QUIET_LINE, pv_after_best=["Bf5"],
            mover_is_user=True)
        assert facts["back_rank_exposed"] is True

    def test_no_mate_means_no_arrow(self):
        board = chess.Board(QUIET_FEN)
        assert back_rank_threat_arrows(
            board, board.parse_san("a5"), QUIET_LINE) == []

    def test_no_mate_means_no_sentence(self):
        decision = build_move_teaching_decision(
            MoveInputs(
                fen_before=QUIET_FEN, played_san="a5", mover_is_user=True,
                mover_is_white=False, user_color="black", full_move_number=29,
                move_history_san=[], best_move_san="Rfd8",
                best_move_uci="f8d8", eval_before_cp=-470, eval_after_cp=-64,
                cp_loss=406, opp_cp_loss=0,
                pv_after_played=list(QUIET_LINE), pv_after_best=["Bf5", "Rc5"],
            ),
            CrossMoveState(),
        )
        assert "no escape squares" not in (decision.text.caption or "")

    def test_the_sentence_and_the_arrow_are_never_apart(self):
        """One proof licenses both, so a card cannot say it without showing it."""
        for fen, played, line in ((FEN, "Bb3", ["Rxc3", "Be6"]),
                                  (QUIET_FEN, "a5", QUIET_LINE)):
            board = chess.Board(fen)
            decision = build_move_teaching_decision(
                MoveInputs(
                    fen_before=fen, played_san=played, mover_is_user=True,
                    mover_is_white=board.turn, user_color="black",
                    full_move_number=29, move_history_san=[],
                    best_move_san=None, best_move_uci=None,
                    eval_before_cp=-300, eval_after_cp=400, cp_loss=700,
                    opp_cp_loss=0, pv_after_played=list(line), pv_after_best=[],
                ),
                CrossMoveState(),
            )
            said = "no escape squares" in (decision.text.caption or "")
            drew = bool(back_rank_threat_arrows(
                chess.Board(fen), chess.Board(fen).parse_san(played), list(line)))
            assert said <= drew, (fen, said, drew)


class TestItSaysItOnceAGame:
    """On 7b966897 the king sat on e1 behind its own pawns for five straight
    moves, so the mate stayed provable and five consecutive cards carried the
    identical sentence. The mate proof stops the filler; it does not stop a
    nag. feedback_never_show_a_failure_scoreboard
    """

    def test_the_second_card_stays_quiet(self):
        state = CrossMoveState()
        first = build_move_teaching_decision(_reported_inputs(), state)
        assert "no escape squares" in first.text.caption
        assert first.state_mutations.fired_state_keys_added

        state = CrossMoveState(
            fired_state_keys=set(first.state_mutations.fired_state_keys_added))
        second = build_move_teaching_decision(_reported_inputs(), state)
        assert "no escape squares" not in (second.text.caption or "")

    def test_the_second_card_also_drops_the_arrow(self):
        """One proof, both surfaces -- the restraint cannot split them."""
        state = CrossMoveState()
        first = build_move_teaching_decision(_reported_inputs(), state)
        state = CrossMoveState(
            fired_state_keys=set(first.state_mutations.fired_state_keys_added))
        second = build_move_teaching_decision(_reported_inputs(), state)
        assert ("c3", "c8") not in {
            (a["from"], a["to"]) for a in second.visual.arrows}


def _reported_inputs():
    return MoveInputs(
        fen_before=FEN, played_san="Bb3", mover_is_user=True,
        mover_is_white=False, user_color="black", full_move_number=28,
        move_history_san=[], best_move_san="Rxc1", best_move_uci="c3c1",
        eval_before_cp=-278, eval_after_cp=719, cp_loss=997, opp_cp_loss=0,
        pv_after_played=["Rxc3", "Be6", "Qc2", "Kf8", "Qxg6", "hxg6"],
        pv_after_best=["Qxc1", "Qd3", "d5", "Qxd5"],
    )

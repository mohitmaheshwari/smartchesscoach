"""A line played AGAINST you must not be painted in your own colours.

smartchesscoach-f8 reported a green arrow -- the colour that means YOUR
payoff -- drawn for Black winning White's pawn on a card where Mohit plays
White:

    c6->e7  blue      moved by black
    f3->e5  palegrey  moved by white
    d7->d6  blue      moved by black
    e5->f3  palegrey  moved by white
    f6->e4  green     moved by black

Its example card, 413fcce2 move 8, turned out not to be a case: that stored
record holds move_story "neither", caption_arrows [], and a single correct blue
best_move_arrow d4->e5, so the story gate had already refused to draw a
sequence there. The colours it quoted are what the builder DOES return for
that line -- reproducible by calling it directly -- but no card rendered them.
The defect below is real regardless, and rests on the fresh-render measurement,
never on that card.

`_line_sequence_arrows` documents blue as YOUR move, paleGrey as THEIR forced
reply and green as YOUR payoff, and it reads the side off the board handed to
it. The opponent-card callers hand in a board where WE are to move, so they
were right. The user-side caller builds its board by pushing our own move
first, so the side to move in it is the OPPONENT -- and every arrow came out
inverted, with their winning capture painted as our payoff.

Measured by re-rendering 2,336 real user mistake cards (cp_loss >= 100, a 3+
ply stored line) from 400 games through the deployed pipeline: 113 drew a
sequence this way, every one of them inverted, and every one of them put green
on a capture made by the opponent. Nothing else in the population moved --
same captions, same arrow squares, only the colour tokens -- and green still
reaches 88 cards via the winning-plan and sacrifice paths, which is the
positive control for this fix not simply having deleted green.

The worst of the 113 is the mate case below: a card where the player is being
mated drew the mating move in the colour that means "this is your payoff".
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    _line_sequence_arrows,
    build_move_teaching_decision,
)

# What each colour token is allowed to mean. Checked as sets, never as strings
# found in a caption: the arrow's side comes from pushing the line on a board.
OURS = {"blue", "green"}
THEIRS = {"red", "darkred"}
FORCED_REPLY = {"palegrey", "palegray"}

# Game 043d6b9c move 17: Black played Be6, and White has Bxh7+ Kxh7 Ng5+ Kg8
# Nxe6 -- the sacrifice, the forced king walk, and the fork on e6. This is the
# position Mohit asked about by name ("i am trying to undresatnd what happens
# after bishop hitting h7"), so it is the one the colours must be right on.
BE6_FEN = "r1bq1rk1/pp4pp/1b6/3pP3/2n2B2/3B1NQ1/PP4PP/1R3R1K b - - 0 17"
BE6_PV = ["Bxh7+", "Kxh7", "Ng5+", "Kg8", "Nxe6", "Qe7", "Nxf8", "Rxf8"]

# Game with the player a move from being mated: Nxf7 allows Bxe3+ Qf2 Nf3#.
MATE_FEN = "r4rk1/bp3ppp/3N4/p2Pp3/P1B4n/2P1P2q/1P2Q3/R3R1K1 w - - 2 20"
MATE_PV = ["Bxe3+", "Qf2", "Nf3#"]


def _card(fen, played, best, pv, cp, *, mover_is_user=True):
    board = chess.Board(fen)
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=fen, played_san=played, mover_is_user=mover_is_user,
            mover_is_white=(board.turn == chess.WHITE),
            user_color=("white" if (board.turn == chess.WHITE) == mover_is_user
                        else "black"),
            full_move_number=board.fullmove_number, move_history_san=[],
            best_move_san=best, eval_before_cp=0, eval_after_cp=0, cp_loss=cp,
            pv_after_played=list(pv), pv_after_best=[],
            allow_fresh_engine_verification=False,
        ),
        CrossMoveState(),
    )
    arrows = [a for a in (decision.visual.arrows or []) if a.get("teach")]
    return arrows, decision


def _who_moves_each_step(fen, played, pv):
    """The ground truth: push the moves and record whose turn it was."""
    board = chess.Board(fen)
    user_is_white = board.turn == chess.WHITE   # a user card: we move first
    board.push_san(played)
    out = {}
    for san in pv:
        move = board.parse_san(str(san))
        out[(chess.square_name(move.from_square),
             chess.square_name(move.to_square))] = (board.turn == user_is_white)
        board.push(move)
    return out


class TestTheOpponentsPlanIsNotOurs:
    def test_the_premise_the_line_belongs_to_the_opponent(self):
        """If this stops holding, everything below proves nothing."""
        sides = _who_moves_each_step(BE6_FEN, "Be6", BE6_PV)
        assert sides[("d3", "h7")] is False      # Bxh7+ is theirs
        assert sides[("g8", "h7")] is True       # Kxh7 is ours, and forced
        assert sides[("g5", "e6")] is False      # Nxe6, the fork, is theirs

    def test_no_arrow_for_their_move_carries_our_colour(self):
        arrows, decision = _card(BE6_FEN, "Be6", "Bf5", BE6_PV, 219)
        assert decision.debug_facts["move_story"] == "punishment"
        assert arrows, "the card draws nothing, so this proves nothing"
        sides = _who_moves_each_step(BE6_FEN, "Be6", BE6_PV)
        for a in arrows:
            mover_is_user = sides.get((a["from"], a["to"]))
            if mover_is_user is None:
                continue
            token = (a.get("color") or "").lower()
            if mover_is_user:
                assert token in FORCED_REPLY, (a, "our forced reply")
            else:
                assert token in THEIRS, (a, "their move in our colour")
                assert token not in OURS

    def test_their_fork_is_not_drawn_as_our_payoff(self):
        arrows, _ = _card(BE6_FEN, "Be6", "Bf5", BE6_PV, 219)
        payoff = [a for a in arrows if a["from"] == "g5" and a["to"] == "e6"]
        assert payoff, "the fork is not drawn at all"
        assert payoff[0]["color"] == "darkred"
        assert not [a for a in arrows if a.get("color") == "green"]

    def test_being_mated_is_never_green(self):
        """The 9404cp card. Nxf7 allows Bxe3+ Qf2 Nf3#, and the mating move
        was painted in the colour that means 'this is what you were playing
        for'."""
        arrows, decision = _card(MATE_FEN, "Nxf7", "Qf1", MATE_PV, 9404)
        assert decision.debug_facts["move_story"] == "punishment"
        assert arrows
        assert arrows[-1]["color"] == "darkred"
        assert not [a for a in arrows if a.get("color") in OURS]


class TestOurOwnPlanStillReadsAsOurs:
    """The positive control. A fix that simply stopped drawing green would
    pass every test above."""

    def test_the_default_is_still_our_plan(self):
        board = chess.Board(BE6_FEN)
        board.push_san("Be6")
        ours = _line_sequence_arrows(board, BE6_PV)
        assert ours, "nothing drawn, so the control proves nothing"
        assert ours[0]["color"] == "blue"
        assert ours[-1]["color"] == "green"

    def test_the_two_callers_disagree_on_purpose(self):
        board = chess.Board(BE6_FEN)
        board.push_san("Be6")
        mine = _line_sequence_arrows(board, BE6_PV, line_is_ours=True)
        theirs = _line_sequence_arrows(board, BE6_PV, line_is_ours=False)
        assert [(a["from"], a["to"]) for a in mine] == \
               [(a["from"], a["to"]) for a in theirs], "geometry must not move"
        assert [a["color"] for a in mine] != [a["color"] for a in theirs]
        # the forced replies are the same either way: they are forced
        assert [a["color"] for a in mine if a["color"] in FORCED_REPLY] == \
               [a["color"] for a in theirs if a["color"] in FORCED_REPLY]

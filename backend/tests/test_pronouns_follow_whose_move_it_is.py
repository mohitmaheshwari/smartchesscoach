"""The why button must not call the opponent's piece "yours".

`_phrase()` chose "your" / "their" from `direction` alone. That is correct for
the player's own moves and inverted for every one of the opponent's, and the
endpoint has answered the opponent's moves since 2026-10-28 (routes/coach.py,
the `opponent` flag).

Audited over 320 positions, checked against the BOARD -- the victim's square
from the resolver, the colour of the man standing there from python-chess:

    checkable answers (victim square present)   44
      the player's own moves    24 right,  0 wrong
      the opponent's moves       0 right, 20 wrong

A perfect split, which is the signature of a pronoun that does not depend on
the thing it should depend on. One sample, verbatim:

    "After Bxh1, your queen on d7 has no safe square left."   <- their queen

The tests below assert the RELATIONSHIP rather than the strings, because the
sentences are rewritten often and a string test would pass while the pronoun
drifted back.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.punishment_resolver import (  # noqa: E402
    Punishment,
    agent_owner,
    victim_owner,
)
from services.why_on_demand import _phrase  # noqa: E402


def _p(mechanism, direction="received", **kw):
    return Punishment(direction=direction, mechanism=mechanism,
                      agent_move=kw.pop("agent_move", "Nc3"),
                      payoff_cp=kw.pop("payoff_cp", 300),
                      line=kw.pop("line", ["Nc3"]), **kw)


class TestTheOwnershipRule:
    """Four cases, and all four have to be stated, because two of them were
    right before and two were wrong -- a rule that only fixes the broken half
    breaks the half that worked."""

    def test_our_move_punished_takes_our_piece(self):
        assert victim_owner("received", mover_is_user=True) == "your"

    def test_our_missed_chance_takes_theirs(self):
        assert victim_owner("missed", mover_is_user=True) == "their"

    def test_their_move_punished_takes_theirs(self):
        assert victim_owner("received", mover_is_user=False) == "their"

    def test_their_missed_chance_takes_ours(self):
        assert victim_owner("missed", mover_is_user=False) == "your"

    def test_the_agent_is_always_the_other_side(self):
        for d in ("received", "missed"):
            for who in (True, False):
                assert agent_owner(d, who) != victim_owner(d, who), (d, who)


class TestTheSentencesFollowIt:
    MECHANISMS = ("WINS_MATERIAL", "TRAPPED", "FORCES_RETREAT")

    def test_our_own_move_still_says_your(self):
        """The half that was already right. A fix that inverts this is not a
        fix."""
        for m in self.MECHANISMS:
            said = _phrase(_p(m, victim_piece="queen", victim_square="d7"),
                           "Bxh1", True)
            assert "your queen" in said, (m, said)
            assert "their queen" not in said, (m, said)

    def test_the_opponents_move_says_their(self):
        """The measured bug: "After Bxh1, your queen on d7 has no safe square
        left" about the opponent's own queen."""
        for m in self.MECHANISMS:
            said = _phrase(_p(m, victim_piece="queen", victim_square="d7"),
                           "Bxh1", False)
            assert "their queen" in said, (m, said)
            assert "your queen" not in said, (m, said)

    def test_a_missed_chance_inverts_both_ways(self):
        ours = _phrase(_p("WINS_MATERIAL", "missed", victim_piece="rook"),
                       "Nxa7", True)
        theirs = _phrase(_p("WINS_MATERIAL", "missed", victim_piece="rook"),
                         "Nxa7", False)
        assert "their rook" in ours and "your rook" not in ours
        assert "your rook" in theirs and "their rook" not in theirs

    def test_a_counted_victim_keeps_its_shape(self):
        said = _phrase(_p("WINS_MATERIAL", victim_piece="two pawns"),
                       "a4", False)
        assert "two of their pawns" in said, said


class TestThePawnThatPromotesBelongsToTheOtherSide:
    """PROMOTES names the AGENT's pawn, not the victim's -- the one mechanism
    a single owner would have inverted, which is why agent_owner exists."""

    def test_our_move_lets_their_pawn_through(self):
        said = _phrase(_p("PROMOTES"), "h6", True)
        assert "their pawn" in said, said

    def test_their_move_lets_our_pawn_through(self):
        said = _phrase(_p("PROMOTES"), "h6", False)
        assert "your pawn" in said, said

    def test_the_missed_direction_flips_it_again(self):
        """We missed a promotion: the pawn was OURS."""
        assert "your pawn" in _phrase(_p("PROMOTES", "missed"), "h6", True)
        assert "their pawn" in _phrase(_p("PROMOTES", "missed"), "h6", False)


class TestTheForkSaysWhoCannotSaveBoth:
    def test_it_is_the_victims_side(self):
        assert "You cannot save both" in _phrase(_p("FORK"), "e5", True)
        assert "They cannot save both" in _phrase(_p("FORK"), "e5", False)

    def test_and_it_follows_the_direction_too(self):
        assert "They cannot save both" in _phrase(_p("FORK", "missed"), "e5", True)
        assert "You cannot save both" in _phrase(_p("FORK", "missed"), "e5", False)


class TestTheDefaultIsTheSafeOne:
    def test_omitting_it_behaves_as_the_players_own_move(self):
        """Every existing caller passes nothing, and the player's own moves
        were the half that was already correct -- so the default must keep
        them correct rather than quietly flip 123 answers."""
        assert _phrase(_p("WINS_MATERIAL", victim_piece="rook"), "a4") == \
            _phrase(_p("WINS_MATERIAL", victim_piece="rook"), "a4", True)

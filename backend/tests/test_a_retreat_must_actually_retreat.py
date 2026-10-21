"""Do not call it a retreat when the piece captures, and do not say "back"
when it goes forward.

Found on Mohit's position 2026-10-21. The Why button said:

    "d4 drives their knight back."

After d4 the knight goes c3 -> e4: forward, to a central square. Measured over
400 games, 423 of these claims:

    the piece really returns home     0    0.0%
    it does NOT return home         423  100.0%
       of which it moves FORWARD    194   45.9%

Not one was true about going back. And a good share are not retreats at all --
the "chased" piece captures something:

    "drives their bishop back"  ->  they play Bxh4
    "drives their queen back"   ->  they play Qxa8
    "drives their knight back"  ->  they play Nxf3+   (with check)

A piece that answers an attack by taking something is counter-attacking. The
resolver asked "does this piece move?" and called any answer a retreat.

Two fixes, and the second is the one that matters: the resolver refuses the
claim when the move is a capture, and the sentence says "chases", adding
"back" only when the piece really returns to where it came from -- which is
what the `received` direction already did correctly.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.punishment_resolver import resolve_missed  # noqa: E402


class TestACaptureIsNotARetreat:
    def test_a_piece_that_takes_something_is_not_retreating(self):
        """Real card: best was Rxa8 and the "retreating" queen plays Qxa8."""
        fen = "r1q2rk1/2p2pp1/8/2N4p/1pP3n1/R5B1/3PRPPP/3Q2K1 w - - 0 24"
        p = resolve_missed(fen, "Rxa8", ["Qxa8", "Qd1"])
        assert p is None or p.mechanism != "FORCES_RETREAT", (
            f"a capture was called a retreat: {p}")

    def test_a_capture_with_check_is_certainly_not_a_retreat(self):
        fen = "r2q1bnr/ppp2kp1/3p3p/4p3/3nP1b1/P1NP1N2/1PP2PPP/R1BQK2R w KQ - 0 8"
        p = resolve_missed(fen, "Be3", ["Nxf3+", "gxf3"])
        assert p is None or p.mechanism != "FORCES_RETREAT", (
            f"a capture with check was called a retreat: {p}")


class TestTheSentenceDoesNotAssertADirection:
    def test_it_never_says_back_unless_the_piece_goes_back(self):
        from services.why_on_demand import _phrase
        from services.punishment_resolver import Punishment

        forward = Punishment(
            mechanism="FORCES_RETREAT", payoff_cp=30, direction="missed",
            agent_move="d4", victim_piece="knight", retreat_san="Ne4",
            returns_home=False, line=["d4", "Ne4"])
        text = _phrase(forward, "c5") or ""
        assert "back" not in text.lower(), text
        assert "knight" in text, text

    def test_it_may_say_back_when_the_piece_really_returns(self):
        from services.why_on_demand import _phrase
        from services.punishment_resolver import Punishment

        home = Punishment(
            mechanism="FORCES_RETREAT", payoff_cp=30, direction="missed",
            agent_move="d4", victim_piece="knight", retreat_san="Nb1",
            returns_home=True, line=["d4", "Nb1"])
        text = _phrase(home, "c5") or ""
        assert "back" in text.lower(), text

    def test_the_received_direction_was_already_honest_and_stays(self):
        """It said "chases your knight" and added "straight back" only when
        earned. The fix is to make the other direction match it, not to
        change this one."""
        from services.why_on_demand import _phrase
        from services.punishment_resolver import Punishment

        p = Punishment(
            mechanism="FORCES_RETREAT", payoff_cp=30, direction="received",
            agent_move="d4", victim_piece="knight", retreat_san="Ne4",
            returns_home=False, line=["d4", "Ne4"])
        text = _phrase(p, "c5") or ""
        assert "chases" in text.lower(), text
        assert "back" not in text.lower(), text

"""Why a recommended reply is good, when the reason is a clearance.

Mohit 2026-09-28, on "Opponent's Rae8 is a mistake - their bishop on d6 has
nothing defending it... Play Nf6+ - it forces a reply": "the caption becomes
wrong then, because we are moving knight to check the king, so undefended
bishop gets attacked by rook, right?"

He had the mechanism exactly right. The DIAGNOSIS was fine and verifiable --
Rad8 defends d6, Rae8 does not, which is why it is a mistake. The
recommended-move WHY was broken: "it forces a reply" fits any check ever
played, and the generic builder offered "attacks the rook on e8", which is
true and is not why the move is played.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_facts import clearance_reply_why  # noqa: E402

# After Black's Rae8. White's knight on d5 blocks White's OWN rook on d1,
# and Black's bishop on d6 has nothing defending it.
POSITION = "4rrk1/pp3ppp/3bb3/3N4/4P3/5N2/PPP2PPP/2KR3R w - - 7 18"
LINE = ["gxf6", "Rxd6", "Bc8", "Rd4"]


def _why(san, pv=LINE, fen=POSITION):
    board = chess.Board(fen)
    return clearance_reply_why(board, board.parse_san(san), pv)


class TestItNamesTheRealReason:
    def test_says_what_the_move_clears_and_what_that_wins(self):
        assert _why("Nf6+") == (
            "clears the way for your rook to take the bishop on d6"
        )

    def test_it_does_not_name_the_incidental_attack(self):
        # The generic builder returns "attacks the rook on e8" here: true,
        # and the wrong motive. Naming a wrong motive is worse than vague.
        assert "e8" not in (_why("Nf6+") or "")

    def test_it_names_the_piece_that_does_the_taking(self):
        why = _why("Nf6+")
        assert "your rook" in why
        assert "bishop" in why


class TestWhenItStaysQuiet:
    def test_a_move_that_clears_nothing(self):
        assert _why("Rhe1", ["Rfe8", "Rd3"]) is None

    def test_a_follow_up_that_wins_nothing_is_not_a_clearance_lesson(self):
        # The prover's own note: 44.1% of follow-ups over 400 games are quiet
        # moves achieving nothing visible -- the "Rxf2 ... Kf1" shape, where
        # the lesson is "take the free knight", not a clearance. Naming one
        # there would be a true statement about a move nobody plays for that
        # reason.
        assert _why("Nf6+", ["gxf6", "Rd2", "Bc8"]) is None

    def test_an_empty_line(self):
        assert _why("Nf6+", []) is None

    def test_missing_inputs_do_not_raise(self):
        board = chess.Board(POSITION)
        assert clearance_reply_why(None, None, LINE) is None
        assert clearance_reply_why(board, None, LINE) is None


class TestTheDiagnosisWasNeverWrong:
    """Guards the half Mohit thought was broken and was not."""

    def test_their_best_move_would_have_defended_the_bishop(self):
        before = chess.Board(
            "r4rk1/pp3ppp/3bb3/3N4/4P3/5N2/PPP2PPP/2KR3R b - - 6 17"
        )
        assert not before.attackers(chess.BLACK, chess.D6)

        best = before.copy()
        best.push_san("Rad8")
        assert best.attackers(chess.BLACK, chess.D6)   # Rad8 defends it

        played = before.copy()
        played.push_san("Rae8")
        assert not played.attackers(chess.BLACK, chess.D6)   # Rae8 does not

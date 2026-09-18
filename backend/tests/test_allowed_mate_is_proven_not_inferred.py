""""You allowed mate" is a claim that has to be shown, not read off a score.

Measured on production 2026-09-18, across 3,727 moves whose stored evaluation
was a mate score against the player:

    66.5%  already lost BEFORE the move -- already in the net, so the claim
           "you allowed mate" is simply false
    24.3%  stored line too short to reach mate (PVs run 4-6 moves)
     9.2%  mate proven by replaying the stored line to board.is_checkmate()

A detector keyed on the evaluation alone would have told two thirds of those
players they walked into a mate they were already inside. That is the failure
this file exists to prevent, and it is the same shape as `king_safety` sitting
in shadow at 75.4% precision: the detector was right that something was wrong
and wrong about what.

The 24.3% are left unknown, never denied. Silence about a real mate costs
recall; denying one costs trust.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.allowed_mate_detector import (  # noqa: E402
    MATE_SENTINEL_CP,
    QUALITY_ID,
    detect_allowed_mate,
    render_claim,
)

# Scholar's mate. Black plays Nf6??; White has Qxf7#.
# After 1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6??
FEN_BEFORE = "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3"
FEN_AFTER = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"


def _move(**over):
    # Stored evaluations are WHITE-relative. Black is the player here, so
    # white mating reads as a large POSITIVE score and the point-of-view flip
    # is what turns it into "mate against you".
    base = {
        "eval_before": 60,
        "eval_after": 9999,
        "fen_before": FEN_BEFORE,
        "fen_after": FEN_AFTER,
        "move": "Nf6",
        "move_uci": "g8f6",
        "move_number": 3,
        "pv_after_played": ["Qxf7#"],
    }
    base.update(over)
    return base


def test_a_real_walk_into_mate_is_detected():
    found = detect_allowed_mate(_move(), "black")
    assert found is not None
    assert found["plies_to_mate"] == 1
    assert found["moves_to_mate"] == 1
    assert found["mating_line"] == ["Qxf7#"]
    assert found["verified"] == "replayed_to_checkmate"
    assert found["quality_id"] == QUALITY_ID


def test_a_player_already_in_the_net_is_not_blamed():
    """Two thirds of candidates. They did not allow it; they were already in it."""
    assert detect_allowed_mate(
        _move(eval_before=MATE_SENTINEL_CP + 500), "black") is None


def test_a_truncated_line_is_unknown_not_denied():
    """24.3% of genuine cases. Silence costs recall; denial costs trust.

    `Nc3` is legal here and is not mate, standing in for a stored line that
    runs out before the mate arrives — which is what a 4-6 move PV does.
    (Note `Qxf7` without the `#` would NOT work as a truncated case: SAN
    parsing does not need the suffix, so it still reaches checkmate.)
    """
    assert detect_allowed_mate(_move(pv_after_played=["Nc3"]), "black") is None
    assert detect_allowed_mate(_move(pv_after_played=[]), "black") is None
    assert detect_allowed_mate(_move(pv_after_played=None), "black") is None


def test_a_line_that_does_not_mate_is_never_claimed():
    """The whole point: the board decides, not the score."""
    assert detect_allowed_mate(
        _move(pv_after_played=["Qxe5+", "Be7", "Qxg7"]), "black") is None


def test_an_ordinary_bad_move_is_not_a_mate():
    for after in (299, 1200, 2999, 0, -300):
        assert detect_allowed_mate(_move(eval_after=after), "black") is None


def test_colour_is_respected():
    """The stored evaluation is white-relative; the claim is about the player.

    Read from white's side this same position is a huge PLUS, so a detector
    that skipped the point-of-view flip would fire on the winning side.
    """
    assert detect_allowed_mate(_move(), "white") is None


def test_an_unparseable_line_never_raises():
    assert detect_allowed_mate(_move(pv_after_played=["Zz9#"]), "black") is None
    assert detect_allowed_mate(_move(fen_after="not a fen"), "black") is None


def test_the_claim_says_only_what_was_proven():
    found = detect_allowed_mate(_move(), "black")
    text = render_claim(found)
    assert "mate in one" in text
    assert "Qxf7#" in text
    # no speculation about the player
    for forbidden in ("careless", "rushed", "should have seen", "always"):
        assert forbidden not in text.lower()


def test_the_authorization_is_shadow_until_reviewed():
    from services.detector_quality import get_authorization

    auth = get_authorization(QUALITY_ID)
    assert auth.grade.value == "shadow"
    assert auth.limitations

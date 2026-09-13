"""The coach must not announce an opening that contradicts the board.

On 2026-09-10 one 90-second game carried three opening identities at once:

    opening_to_teach : italian_game_black
    detected_opening : french_defense
    announced to the player: "You're in the Knight First."

"Knight First" is a node label inside opening_curriculum.json, not an opening a
player would recognise, and it had nothing to do with the French Defence
actually on the board.

The three stored fields are legitimately different things -- intent, observation
and a curriculum node -- so the fix is not to merge them. It is that the
USER-FACING name must agree with the canonical per-move recognizer
(services/decryption_voice/opening_book.recognize_opening_from_history), which is
the authority on what is on the board. If the curriculum sub-line disagrees, the
family name is used; if that disagrees too, nothing is announced.

Saying nothing beats saying something contradictory.
"""
import io
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

ROUTE = BACKEND / "routes" / "coach_play.py"

GENERIC = {
    "defense", "defence", "game", "opening", "variation", "attack", "system",
    "line", "main", "gambit", "accepted", "declined", "classical", "modern",
    "closed", "open",
}


def _tokens(value: str) -> set:
    return {
        t for t in str(value).lower()
        .replace("-", " ").replace("_", " ").replace(",", " ").split()
        if len(t) > 3 and t not in GENERIC
    }


def _resolve(sub_name, canonical_id, family_name):
    """Mirror of the guard in coach_play, so the rule is testable in isolation."""
    name = sub_name
    if name and canonical_id and not (_tokens(name) & _tokens(canonical_id)):
        name = family_name if (_tokens(family_name) & _tokens(canonical_id)) else None
    return name


@pytest.mark.parametrize(
    "sub,canonical,family,expected,why",
    [
        ("Knight First", "french_defense", "Sicilian Defense", None,
         "the reported bug: a node label in a French game, wrong family"),
        ("Knight First", "french_defense", "French Defense", "French Defense",
         "node label, but the family does match the board"),
        ("French Defense, Advance", "french_defense", "French Defense",
         "French Defense, Advance", "sub-line agrees with the board"),
        ("Alapin Sicilian Defense", "sicilian_alapin", "Sicilian Defense",
         "Alapin Sicilian Defense", "a real sub-line survives"),
        ("Italian Game", "italian_game", "Italian Game", "Italian Game",
         "family only"),
        ("Ruy Lopez, Berlin", "ruy_lopez", "Ruy Lopez", "Ruy Lopez, Berlin",
         "multi-word family"),
    ],
)
def test_the_announced_name_must_agree_with_the_board(
    sub, canonical, family, expected, why
):
    assert _resolve(sub, canonical, family) == expected, why


def test_generic_words_alone_are_not_agreement():
    """The flaw this stopword list exists for.

    Without it, "Sicilian Defense" and "french_defense" share the token
    "defense", so the guard accepted a Sicilian name for a French game.
    """
    assert not (_tokens("Sicilian Defense") & _tokens("french_defense"))
    assert _tokens("French Defense") & _tokens("french_defense")


def test_the_route_consults_the_canonical_recognizer():
    src = io.open(ROUTE, encoding="utf-8").read()
    assert "recognize_opening_from_history(_played_san_list)" in src, (
        "the announcement must check what is actually on the board"
    )
    assert "_GENERIC_OPENING_WORDS" in src
    assert "suppressing announcement" in src, (
        "when nothing matches, the coach must stay quiet rather than guess"
    )


def test_no_announcement_when_nothing_is_recognised():
    """A canonical id of "" means the recognizer has no opinion.

    In that case the existing curriculum behaviour is preserved -- this change
    must not silence openings the recognizer simply does not cover.
    """
    assert _resolve("Knight First", "", "Sicilian Defense") == "Knight First"

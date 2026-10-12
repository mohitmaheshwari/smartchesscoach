"""The possessive in a why belongs to whoever MOVED, not to the reader.

Mohit, live on an opponent card:

    "They missed Nc6 - it puts your knight on a square where no pawn can
     chase it away."

Nc6 is THEIR move, so it is their knight.

_recommended_move_why already resolves this through _own and carries a
2026-09-30 note about fixing the same class on 47 of 238 cards.
_REC_PRINCIPLE_PHRASE escaped that fix by being a static lookup table:
four of its five entries baked a possessive into the string. It stayed
invisible while best_move_why only ever rendered on USER cards. The
moment the opponent-why fix (66fa05a5) made it render on opponent cards,
288 of 2,739 of them (10.5%) told the reader the opponent's piece was
theirs:

    rook_open_file  108      outpost  72
    center           73      castle   35

The lesson for the next table like this one: a string that is correct
only because of who happens to read it is a latent bug, not a correct
string.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_facts import (  # noqa: E402
    _REC_PRINCIPLE_PHRASE,
    _rec_principle_phrase,
)

USER, OPPONENT, UNKNOWN = True, False, None


def test_no_possessive_is_baked_into_the_table():
    """The regression guard. Any literal possessive here renders the same
    word for both sides, which is wrong for one of them."""
    for key, template in _REC_PRINCIPLE_PHRASE.items():
        lowered = template.lower()
        for banned in ("your ", "their ", "his ", "her ", "its "):
            assert banned not in lowered, (
                f"{key} bakes in {banned!r}; use {{own}}/{{own2}}/{{opp}}")


def test_every_template_renders_for_every_voice():
    """A KeyError here would return None and silently drop the why."""
    for key in _REC_PRINCIPLE_PHRASE:
        for voice in (USER, OPPONENT, UNKNOWN):
            out = _rec_principle_phrase(key, voice)
            assert out and "{" not in out, (key, voice, out)


@pytest.mark.parametrize("key", sorted(_REC_PRINCIPLE_PHRASE))
def test_opponent_voice_never_calls_their_piece_yours(key):
    """The exact defect Mohit caught."""
    out = _rec_principle_phrase(key, OPPONENT)
    assert "your knight" not in out, out
    assert "your king" not in out, out
    assert "your rook" not in out, out
    assert "your own" not in out, out


@pytest.mark.parametrize("key", sorted(_REC_PRINCIPLE_PHRASE))
def test_user_voice_never_calls_the_readers_piece_theirs(key):
    """The mirror. The opponent branch must not leak the other way."""
    out = _rec_principle_phrase(key, USER)
    for noun in ("knight", "king", "rook"):
        assert f"their {noun}" not in out, out


def test_his_pieces_card_now_names_the_right_side():
    """center describes the side NOT moving. It said "his pieces"
    unconditionally, so on an opponent card it meant the reader's."""
    assert "their pieces" in _rec_principle_phrase("center", USER)
    assert "your pieces" in _rec_principle_phrase("center", OPPONENT)


def test_the_flagged_sentence_itself():
    assert (_rec_principle_phrase("outpost", OPPONENT)
            == "puts their knight on a square where no pawn "
               "can chase it away")
    assert (_rec_principle_phrase("outpost", USER)
            == "puts your knight on a square where no pawn "
               "can chase it away")


def test_unknown_voice_goes_neutral_rather_than_guessing():
    """Same rule _recommended_move_why already applies to _own: a
    neutral phrase is never wrong."""
    for key in _REC_PRINCIPLE_PHRASE:
        out = _rec_principle_phrase(key, UNKNOWN)
        assert "your" not in out and "their" not in out, (key, out)
    # and it still reads as English, not "none of the own pawns"
    assert ("none of its own pawns"
            in _rec_principle_phrase("rook_open_file", UNKNOWN))


def test_unknown_key_returns_none_not_a_crash():
    assert _rec_principle_phrase("not_a_principle", USER) is None
    assert _rec_principle_phrase(None, USER) is None
    assert _rec_principle_phrase("", USER) is None


# ── the class guard, after fixing the same bug twice ─────────────────

def test_no_literal_possessive_in_any_why_string():
    """Source-level guard over the whole why generator.

    I fixed _REC_PRINCIPLE_PHRASE and called it done. Rendering two real
    games to check some LINKS then turned up a survivor in a different
    branch:

        "Play Bxa7 - it trades his bishop.
         They missed Nxe3 - it trades his bishop."

    The same sentence for our move and theirs, so one is wrong. Three
    more sites, all naming the side NOT moving: `trades his {name}` and
    two copies of `costs him ... if he takes back`.

    A literal possessive inside a returned string is the bug, wherever
    it lives: the function serves both voices, so a word fixed at author
    time is right for one reader and wrong for the other. Possessives
    must come from _own / _opp, which are resolved from mover_is_user.
    """
    import inspect
    import re

    from services import caption_facts

    source = inspect.getsource(caption_facts._recommended_move_why)
    # strings that are RETURNED to the caller, i.e. reach a card
    returned = re.findall(r'return \(?\s*f?"([^"]*)"', source)
    assert returned, "no return strings found - did the function move?"

    banned = ("your ", "their ", "his ", "him ", "her ", " he ", " she ")
    offenders = [
        s for s in returned
        if any(b in f" {s.lower()} " for b in banned)
        # the check branch resolves both voices explicitly in-line and is
        # asserted separately below
        and "forcing" not in s.lower()
    ]
    assert not offenders, (
        "literal possessive in a returned why string; use {_own}/{_opp}: "
        + repr(offenders))


def test_the_trade_phrase_follows_the_mover():
    """The exact survivor, locked."""
    import chess

    from services.caption_facts import _recommended_move_why

    board = chess.Board(
        "r1bqkbnr/ppp2ppp/2n5/3pp3/4P3/3B1N2/PPPP1PPP/RNBQK2R w KQkq - 0 4")
    move = board.parse_san("exd5")
    assert _recommended_move_why(board, move, True) == "trades their pawn"
    assert _recommended_move_why(board, move, False) == "trades your pawn"
    assert (_recommended_move_why(board, move, None)
            == "trades the opponent's pawn")

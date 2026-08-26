"""Tests for authoritative per-game rating extraction used by PIC."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.rating_resolver import (
    get_game_side_ratings,
    get_game_user_rating,
    resolve_game_user_rating,
)


PGN = '[WhiteElo "932"]\n[BlackElo "1187"]\n\n1. e4 e5 *'


def test_explicit_user_rating_wins_and_keeps_source():
    result = resolve_game_user_rating({
        "user_color": "white",
        "user_rating": 1010,
        "white_rating": 999,
        "pgn": PGN,
    })
    assert result == {"rating": 1010, "source": "stored_user_rating"}


def test_side_specific_field_precedes_pgn():
    result = resolve_game_user_rating({
        "user_color": "black",
        "black_rating": 1201,
        "pgn": PGN,
    })
    assert result == {"rating": 1201, "source": "black_rating"}


def test_side_api_object_is_authoritative():
    result = resolve_game_user_rating({
        "user_color": "white",
        "white": {"username": "player", "rating": 845},
    })
    assert result == {"rating": 845, "source": "white_api_rating"}


def test_pgn_rating_uses_user_color():
    assert get_game_user_rating({"user_color": "white", "pgn": PGN}) == 932
    assert get_game_user_rating({"user_color": "black", "pgn": PGN}) == 1187


def test_unknown_or_invalid_rating_never_defaults_to_1200():
    assert resolve_game_user_rating({"user_color": "white"}) == {
        "rating": None,
        "source": "unknown",
    }
    assert get_game_user_rating({"user_color": "white", "white_rating": 0}) is None
    assert get_game_user_rating({"user_color": "unknown", "pgn": PGN}) is None


def test_side_rating_extraction_combines_fields_api_and_pgn():
    ratings = get_game_side_ratings({
        "white_rating": 900,
        "black": {"rating": 1100},
        "pgn": PGN,
    })
    assert ratings == {"white": 900, "black": 1100}

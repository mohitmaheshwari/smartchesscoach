"""
Country resolution across two platforms with two different shapes (2026-08-24).

Lichess returns an ISO-3166 alpha-2 code. Chess.com returns a URL. Both must
land in `users.country` as the SAME shape, or every downstream comparison
breaks silently. Pure logic except one network function, which is not called here.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.player_country import (  # noqa: E402
    country_from_lichess_profile,
    country_update_fields,
    normalize_iso2,
)


def test_chesscom_url_normalises_to_iso_code():
    """The whole point: a URL must not be stored where an ISO code goes."""
    assert normalize_iso2("https://api.chess.com/pub/country/IN") == "IN"
    assert normalize_iso2("https://api.chess.com/pub/country/XE") == "XE"
    assert normalize_iso2("https://api.chess.com/pub/country/de/") == "DE"


def test_bare_iso_code_passes_through_uppercased():
    assert normalize_iso2("IN") == "IN"
    assert normalize_iso2("in") == "IN"


def test_junk_returns_none_rather_than_garbage():
    for bad in (None, "", "   ", "UNKNOWN", "United Kingdom",
                "https://api.chess.com/pub/country/", 42, {"country": "IN"}):
        assert normalize_iso2(bad) is None, bad


def test_chesscom_pseudo_codes():
    """chess.com is not pure ISO-3166. XE/XS/XW are real places and must be
    kept; XX is its "International / prefer not to say" marker and must NOT be
    stored as a country -- doing so asserts a fact the user declined to give.
    A live dry run over 117 users returned one XX."""
    assert normalize_iso2("https://api.chess.com/pub/country/XE") == "XE"
    assert normalize_iso2("https://api.chess.com/pub/country/XS") == "XS"
    assert normalize_iso2("https://api.chess.com/pub/country/XW") == "XW"
    assert normalize_iso2("https://api.chess.com/pub/country/XX") is None
    assert normalize_iso2("xx") is None
    assert country_update_fields(normalize_iso2("https://api.chess.com/pub/country/XX"),
                                 "chesscom") == {}


def test_lichess_nested_shape():
    """Lichess nests it under `profile`, which is frequently absent."""
    assert country_from_lichess_profile({"profile": {"country": "IN"}}) == "IN"
    assert country_from_lichess_profile({"profile": {}}) is None
    assert country_from_lichess_profile({}) is None
    assert country_from_lichess_profile(None) is None


def test_unknown_country_writes_nothing():
    """A failed lookup must add no keys at all -- writing None would erase a
    country the other platform already established for this user."""
    assert country_update_fields(None, "chesscom") == {}
    assert country_update_fields("", "lichess") == {}
    assert country_update_fields("IN", "lichess") == {
        "country": "IN", "country_source": "lichess"
    }


def test_both_platforms_produce_the_same_shape():
    """The invariant that makes one shared field safe."""
    lichess = country_update_fields(
        country_from_lichess_profile({"profile": {"country": "in"}}), "lichess")
    chesscom = country_update_fields(
        normalize_iso2("https://api.chess.com/pub/country/IN"), "chesscom")
    assert lichess["country"] == chesscom["country"] == "IN"
    assert lichess["country_source"] != chesscom["country_source"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

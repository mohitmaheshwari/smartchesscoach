"""Unit tests for the played_at_utc derivation.

The bug this guards against is an ordering bug, not a parsing bug: with
`date_played` compared as a string, "2026.04.15" sorts ABOVE every
"2026-09-11T..." timestamp because ASCII "." (0x2E) > "-" (0x2D). On
production that put 407 games from months earlier into 15 focuses'
"after" windows. `test_dotted_sorts_after_iso_as_strings` pins the broken
behaviour so nobody "simplifies" the canonical field away later.
"""

from datetime import datetime, timezone

import pytest

from scripts.backfill_played_at_utc import (
    OUTCOME_ELIGIBLE_SOURCES,
    SRC_COACH,
    SRC_NONE,
    SRC_PGN_LOCAL,
    SRC_PGN_UTC,
    SRC_STORED_ISO,
    derive,
    parse_stored,
)


def _pgn(headers: str) -> str:
    return headers + '\n\n1. e4 e5 2. Nf3 Nc6 1-0\n'


# --- the ordering defect itself -------------------------------------------

def test_dotted_sorts_after_iso_as_strings():
    """The production defect, pinned. A dotted date from April must not
    compare as later than a September timestamp -- but as strings it does."""
    april = "2026.04.15"
    september = "2026-09-11T14:23:10.646000"
    assert april > september          # the bug
    assert parse_stored(april) < parse_stored(september)   # the truth


def test_canonical_datetimes_order_correctly():
    a = derive({"pgn": _pgn('[Utcdate "2026.04.15"]\n[Utctime "05:45:33"]')})[0]
    b = derive({"pgn": _pgn('[Utcdate "2026.09.11"]\n[Utctime "14:23:10"]')})[0]
    assert a < b


# --- derivation ------------------------------------------------------------

def test_utc_headers_are_read_case_insensitively():
    """The import path normalises header case, so the real stored form is
    [Utcdate], not [UTCDate]. A case-sensitive reader finds nothing and
    concludes the timestamp is unrecoverable -- which is exactly what
    happened before this was measured."""
    dt, src = derive({"pgn": _pgn('[Utcdate "2026.03.01"]\n[Utctime "05:45:33"]')})
    assert src == SRC_PGN_UTC
    assert dt == datetime(2026, 3, 1, 5, 45, 33, tzinfo=timezone.utc)


def test_uppercase_headers_also_work():
    dt, src = derive({"pgn": _pgn('[UTCDate "2026.03.01"]\n[UTCTime "05:45:33"]')})
    assert src == SRC_PGN_UTC
    assert dt.hour == 5


def test_local_headers_used_only_when_zone_is_declared_utc():
    with_zone = _pgn('[Date "2026.03.01"]\n[Time "05:45:33"]\n[Timezone "UTC"]')
    dt, src = derive({"pgn": with_zone})
    assert src == SRC_PGN_LOCAL
    assert dt == datetime(2026, 3, 1, 5, 45, 33, tzinfo=timezone.utc)


def test_local_headers_without_zone_are_not_guessed():
    """An unknown offset must not be invented. Falls through to the stored
    ISO value, or to unrecoverable."""
    no_zone = _pgn('[Date "2026.03.01"]\n[Time "05:45:33"]')
    dt, src = derive({"pgn": no_zone, "platform": "chess.com"})
    assert src == SRC_NONE
    assert dt is None


def test_stored_iso_fallback_when_no_headers():
    dt, src = derive({
        "pgn": _pgn('[Event "x"]'),
        "platform": "lichess",
        "date_played": "2026-09-11T14:23:10+00:00",
    })
    assert src == SRC_STORED_ISO
    assert dt == datetime(2026, 9, 11, 14, 23, 10, tzinfo=timezone.utc)


def test_dotted_stored_value_is_not_used_as_a_fallback():
    """A bare dotted date has no time of day. Rather than pinning it to
    midnight and calling it exact, fall through -- in practice these all
    carry UTC headers anyway."""
    dt, src = derive({"pgn": "", "platform": "chess.com", "date_played": "2026.04.15"})
    assert src == SRC_NONE
    assert dt is None


# --- coach games -----------------------------------------------------------

def test_coach_game_uses_imported_at():
    stamp = datetime(2026, 8, 2, 9, 30, tzinfo=timezone.utc)
    dt, src = derive({"pgn": "", "platform": "coach", "imported_at": stamp})
    assert src == SRC_COACH
    assert dt == stamp


def test_coach_game_falls_back_to_created_at():
    stamp = datetime(2026, 8, 2, 9, 30, tzinfo=timezone.utc)
    dt, src = derive({"pgn": "", "platform": "coach", "created_at": stamp})
    assert src == SRC_COACH
    assert dt == stamp


def test_coach_game_accepts_an_iso_string_stamp():
    dt, src = derive({"pgn": "", "platform": "coach",
                      "imported_at": "2026-08-02T09:30:00+00:00"})
    assert src == SRC_COACH
    assert dt == datetime(2026, 8, 2, 9, 30, tzinfo=timezone.utc)


def test_coach_game_without_any_stamp_is_unrecoverable():
    dt, src = derive({"pgn": "", "platform": "coach"})
    assert src == SRC_NONE
    assert dt is None


def test_coach_games_count_toward_outcome_measurement():
    """Product decision, 2026-09-16: coach games count in a single pooled
    rate despite a measured ~7x lower miss rate. If this assertion is ever
    flipped, the comment on OUTCOME_ELIGIBLE_SOURCES must be updated too."""
    assert SRC_COACH in OUTCOME_ELIGIBLE_SOURCES


def test_naive_datetimes_are_treated_as_utc():
    naive = datetime(2026, 8, 2, 9, 30)
    dt, src = derive({"pgn": "", "platform": "coach", "imported_at": naive})
    assert dt.tzinfo is not None
    assert dt.hour == 9


# --- malformed input -------------------------------------------------------

@pytest.mark.parametrize("bad", [
    '[Utcdate "not-a-date"]\n[Utctime "05:45:33"]',
    '[Utcdate "2026.13.45"]\n[Utctime "05:45:33"]',
    '[Utcdate "2026.03.01"]\n[Utctime "99:99:99"]',
    '[Utcdate "2026.02.30"]\n[Utctime "05:45:33"]',
])
def test_malformed_headers_do_not_raise(bad):
    dt, src = derive({"pgn": _pgn(bad), "platform": "chess.com"})
    assert src == SRC_NONE
    assert dt is None


def test_leap_second_clamped_not_crashed():
    dt, _ = derive({"pgn": _pgn('[Utcdate "2026.03.01"]\n[Utctime "23:59:60"]')})
    assert dt is not None and dt.second == 59


def test_parse_stored_handles_junk():
    for junk in (None, "", "   ", 12345, [], {}, "yesterday"):
        assert parse_stored(junk) is None

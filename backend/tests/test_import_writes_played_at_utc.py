"""An imported game must carry its typed date, not wait for a migration.

`played_at_utc` is the only date field measurement reads. Nothing in the
product wrote it -- only `scripts/backfill_played_at_utc.py`, over history --
so every game imported after a migration run had no typed date and the focus
outcome window silently skipped it. Measured 2026-09-26: 1,553 of 17,804 games,
every one imported that month, every one still carrying a usable `date_played`.

A migration that has to be re-run after every import is not a migration. These
tests hold the field at the point of import instead.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.played_at import (  # noqa: E402
    SRC_COACH,
    SRC_NONE,
    SRC_PGN_UTC,
    derive,
)


def _pgn(headers: str) -> str:
    return headers + "\n\n1. e4 e5 2. Nf3 Nc6 1-0\n"


def test_the_backfill_and_the_import_path_share_one_function():
    """Not a copy of the rules -- the same object. Two date derivations that
    can disagree is how the string-sorting bug survived for months."""
    from scripts import backfill_played_at_utc as script

    assert script.derive is derive
    assert script.SRC_PGN_UTC is SRC_PGN_UTC


def test_an_imported_game_gets_an_exact_instant_from_utc_headers():
    game = {"pgn": _pgn('[Utcdate "2026.03.01"]\n[Utctime "05:45:33"]'),
            "platform": "chess.com"}
    when, source = derive(game)
    assert source == SRC_PGN_UTC
    assert when == datetime(2026, 3, 1, 5, 45, 33, tzinfo=timezone.utc)


def test_headers_are_read_case_insensitively():
    """The import path normalises header capitalisation, so "UTCDate" is
    stored as "Utcdate". A case-sensitive read finds nothing, which is exactly
    how this went unnoticed."""
    lower = derive({"pgn": _pgn('[utcdate "2026.03.01"]\n[utctime "05:45:33"]'),
                    "platform": "chess.com"})
    upper = derive({"pgn": _pgn('[UTCDate "2026.03.01"]\n[UTCTime "05:45:33"]'),
                    "platform": "chess.com"})
    assert lower[0] == upper[0] == datetime(2026, 3, 1, 5, 45, 33,
                                            tzinfo=timezone.utc)


def test_a_malformed_time_is_refused_not_rounded_to_midnight():
    """A fabricated instant wearing an exactness label is worse than no date."""
    when, source = derive({"pgn": _pgn('[Utcdate "2026.03.01"]\n'
                                       '[Utctime "99:99:99"]'),
                           "platform": "chess.com"})
    assert (when, source) != (datetime(2026, 3, 1, tzinfo=timezone.utc),
                              SRC_PGN_UTC)


def test_a_local_time_with_no_stated_zone_is_refused():
    """Without a TimeZone header the offset is unknown, and guessing it would
    move games across day boundaries."""
    _when, source = derive({"pgn": _pgn('[Date "2026.03.01"]\n[Time "05:45:33"]'),
                            "platform": "chess.com"})
    assert source != SRC_PGN_UTC


def test_a_coach_game_is_dated_from_its_import_stamp_and_tagged_as_such():
    """Play-with-Coach games carry no PGN date headers. They are created at the
    end of the session, so imported_at dates them to within one session -- and
    it is tagged distinctly rather than passed off as header-exact."""
    stamp = datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc)
    when, source = derive({"pgn": _pgn('[Result "1-0"]'), "platform": "coach",
                           "imported_at": stamp})
    assert source == SRC_COACH
    assert when == stamp


def test_nothing_derivable_stores_nothing():
    """The import path checks for exactly this before writing, so an
    unparseable game must be distinguishable from a dated one."""
    when, source = derive({"pgn": _pgn('[Result "1-0"]'),
                           "platform": "chess.com"})
    assert when is None
    assert source == SRC_NONE


def test_the_import_path_actually_calls_it():
    """The regression this file exists for was not a broken derivation -- it
    was a correct derivation nobody called from the import path."""
    source = (BACKEND_ROOT / "journey_service.py").read_text(encoding="utf-8")
    assert "from services.played_at import" in source
    assert 'game_doc["played_at_utc"]' in source


def test_the_backfill_script_can_still_reach_everything_it_moved():
    """Moving the derivation out broke the script at RUNTIME, not at import.

    `main` still referenced `_DOTTED` and `_ISO_PREFIX`, which had moved to the
    service. Nothing failed until the script ran against production, minutes
    into a dry run:

        NameError: name '_DOTTED' is not defined

    Importing the module cannot catch that: a global is only looked up when the
    function body executes. So this checks the one thing that actually broke --
    every name the service defines, which the script's source still mentions,
    must be reachable on the script module.

    Deliberately narrow. An earlier version of this test tried to resolve every
    name in the file and flagged comprehension variables (`d`, `r`, `key`),
    because a correct scope analyser is not something a test should contain.
    """
    import ast

    from scripts import backfill_played_at_utc as script
    from services import played_at

    service_names = {
        name for name in vars(played_at)
        if not name.startswith("__")
    }
    source = (BACKEND_ROOT / "scripts" / "backfill_played_at_utc.py").read_text(
        encoding="utf-8"
    )
    mentioned = {
        node.id for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Name) and node.id in service_names
    }
    assert mentioned, "positive control: the script should mention some of them"
    unreachable = sorted(n for n in mentioned if not hasattr(script, n))
    assert not unreachable, (
        "the script uses these but can no longer reach them: %s" % unreachable
    )

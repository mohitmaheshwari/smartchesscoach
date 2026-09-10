"""
When a game was played — one parser, because the stored shapes disagree
=======================================================================

Three date fields exist on `games` and none of them is reliable alone:

  date_played      written by the importer as ISO8601 with time
                   ("2026-08-30T13:51:45+00:00"), but older rows hold the raw
                   PGN form ("2026.03.31"). MIXED FORMATS IN ONE FIELD.
  date_played_iso  date only, no time, and written by a one-off backfill
                   script -- never by the importer. Frozen: its maximum was
                   2026-08-31 while games kept arriving daily, and it is
                   absent on ~1,200 games.
  imported_at      when WE fetched it, not when it was played, and stored as a
                   string so comparing it to a datetime silently matches
                   nothing.

Sorting by any of these gets chronology wrong, and gets it wrong SILENTLY:

  * "2026." sorts AFTER "2026-" (0x2E > 0x2D), so a lexical sort interleaves
    the two formats. One user's 807 games ordered from 2026-04-17 to
    2026.03.31 -- a maximum earlier than the minimum.
  * A descending sort on date_played_iso puts the ~1,200 rows that lack it
    last, so "the 60 most recent games" silently excluded them. This was a
    real bug in time_management_service on 2026-09-09: the profile read games
    up to 2026-08-30 and missed the player's 155 newest.

Every consumer should call `game_played_at` and sort in Python, or use
`sort_games_by_played_at`. Do not add a fourth date field.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

_PGN_DATE = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})")
_ISO_LEAD = re.compile(r"^\d{4}-\d{2}-\d{2}")

# Games older than this are almost certainly a placeholder date rather than a
# real one; PGN exports use "????.??.??" and some sources emit 1900-01-01.
_EARLIEST_PLAUSIBLE = datetime(1970, 1, 1, tzinfo=timezone.utc)


def parse_game_date(value: Any) -> Optional[datetime]:
    """Parse any of the stored shapes into an aware UTC datetime, or None.

    Accepts a datetime, an ISO8601 string with or without time, or the PGN
    "YYYY.MM.DD" form. Returns None rather than guessing when the value is a
    placeholder or unparseable, so callers can count what they skipped instead
    of silently ordering by a fabricated date.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    text = str(value or "").strip()
    if not text:
        return None

    match = _PGN_DATE.match(text)
    if match:
        try:
            parsed = datetime(
                int(match.group(1)), int(match.group(2)), int(match.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None
        return parsed if parsed >= _EARLIEST_PLAUSIBLE else None

    if _ISO_LEAD.match(text):
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.fromisoformat(text[:10])
            except ValueError:
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed if parsed >= _EARLIEST_PLAUSIBLE else None

    return None


def game_played_at(game: Dict[str, Any]) -> Optional[datetime]:
    """Best available "when was this played", preferring the field with time.

    date_played carries a time component when the importer wrote it, so it
    orders games within a day; date_played_iso is date-only and stale, and is
    only a fallback. imported_at is deliberately NOT consulted -- it is when we
    fetched the game, which for a backfill is nothing like when it was played.
    """
    for field in ("date_played", "date_played_iso"):
        parsed = parse_game_date(game.get(field))
        if parsed is not None:
            return parsed
    return None


def sort_games_by_played_at(
    games: Iterable[Dict[str, Any]], *, newest_first: bool = True
) -> List[Dict[str, Any]]:
    """Chronological order, dropping games whose date cannot be established.

    Dropping is deliberate: a game with no usable date cannot be placed in a
    before/after window, and giving it a default would put it at one end of
    every study.
    """
    dated = [(game_played_at(g), g) for g in games]
    usable = [(when, g) for when, g in dated if when is not None]
    usable.sort(key=lambda pair: pair[0], reverse=newest_first)
    return [g for _, g in usable]


def undated_count(games: Iterable[Dict[str, Any]]) -> int:
    """How many games a caller had to drop — worth reporting, never hiding."""
    return sum(1 for g in games if game_played_at(g) is None)

"""The canonical UTC instant a game was played, and where it came from.

This is the single owner of that derivation. It used to live inside
`scripts/backfill_played_at_utc.py`, which meant the import path could not
reach it without a service importing from `scripts/` -- so the import path did
not set the field at all, and `played_at_utc` existed only where a migration
had been run over history.

Measured 2026-09-26: 1,553 of 17,804 games had no `played_at_utc`, every one of
them imported that month, every one still carrying a usable `date_played`. The
field was not partially migrated, it was never written by the product. A
migration that has to be re-run after every import is not a migration.

WHY A TYPED FIELD AT ALL. `games.date_played` holds three incompatible shapes:
an ISO timestamp, chess.com's dotted `2026.04.15`, and nothing for
Play-with-Coach rows. ASCII "." (0x2E) sorts above "-" (0x2D), so under a
string comparison every dotted value sorts after every ISO timestamp whatever
date it represents. That put 407 games on the wrong side of 15 focus windows.

WHAT IT REFUSES TO DO. It never invents an instant. A present-but-malformed
time is not silently treated as midnight, and `[Date]`+`[Time]` are used only
when the PGN states the zone is UTC, because otherwise the offset is unknown.
When nothing is derivable it returns SRC_NONE and the caller stores nothing.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


SRC_PGN_UTC = "pgn_utc_headers"        # exact instant from [Utcdate]+[Utctime]
SRC_PGN_LOCAL = "pgn_local_headers"    # [Date]+[Time] with an explicit [Timezone "UTC"]
SRC_STORED_ISO = "stored_iso_fallback"  # no usable headers, stored value already ISO
SRC_COACH = "coach_imported_at"        # Play with Coach; no PGN date headers
SRC_NONE = "unrecoverable"

# Every source that may enter a before/after outcome window.
#
# SRC_COACH is included by an explicit product decision (2026-09-16): Play
# with Coach games count as evidence like any other game, in a single pooled
# rate. The decision was taken against the following measurement, which is
# recorded here so the bias is never rediscovered as a surprise:
#
#   Within the 3 users who have >=20 coach and >=100 imported PIC decisions,
#   the piece-safety miss rate is 2.12% in coach games (n=378) against 14.00%
#   in imported games (n=5,892) -- about 7x lower, same direction for all
#   three. The mechanism is not subtle: the pre-move Guardian stops the
#   mistake while the game is being played.
#
# The consequence is that a user who plays Play with Coach after a focus
# starts will tend to measure as improved partly because of live coaching
# rather than a changed habit. `played_at_source` is written on every row so
# the mix stays queryable and this can be revisited without another backfill.

OUTCOME_ELIGIBLE_SOURCES = {SRC_PGN_UTC, SRC_PGN_LOCAL, SRC_STORED_ISO, SRC_COACH}

# Header readers. Case-insensitive on purpose: the import path normalises
# header capitalisation, so "UTCDate" is stored as "Utcdate".
_H_UTCDATE = re.compile(r'\[\s*utcdate\s+"([^"]+)"\s*\]', re.I)
_H_UTCTIME = re.compile(r'\[\s*utctime\s+"([^"]+)"\s*\]', re.I)
_H_DATE = re.compile(r'\[\s*date\s+"([^"]+)"\s*\]', re.I)
_H_TIME = re.compile(r'\[\s*time\s+"([^"]+)"\s*\]', re.I)
_H_TZ = re.compile(r'\[\s*timezone\s+"([^"]+)"\s*\]', re.I)

_DOTTED = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})$")
_ISO_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}T")

# A derived instant this far from the stored value is reported for review
# rather than trusted silently.
DISAGREEMENT_TOLERANCE_SECONDS = 60 * 60 * 24  # one day


def _parse_dotted_date(value: str) -> Optional[Tuple[int, int, int]]:
    m = _DOTTED.match(value.strip())
    if not m:
        return None
    y, mo, d = (int(g) for g in m.groups())
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return y, mo, d


def _parse_clock(value: str) -> Optional[Tuple[int, int, int]]:
    parts = value.strip().split(":")
    if len(parts) < 2:
        return None
    try:
        h = int(parts[0])
        mi = int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= mi <= 59 and 0 <= s <= 60):
        return None
    return h, mi, min(s, 59)


def _combine(date_parts, clock_parts) -> Optional[datetime]:
    if not date_parts:
        return None
    y, mo, d = date_parts
    h, mi, s = clock_parts or (0, 0, 0)
    try:
        return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_stored(value: Any) -> Optional[datetime]:
    """Best-effort read of the legacy `date_played`, for comparison only."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if _ISO_PREFIX.match(raw):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    dotted = _parse_dotted_date(raw)
    if dotted:
        return _combine(dotted, None)
    return None


def derive(game: Dict[str, Any]) -> Tuple[Optional[datetime], str]:
    """Return (canonical UTC instant, provenance tag) for one game."""
    pgn = game.get("pgn") or ""

    # Both halves must parse. A present-but-malformed time used to fall
    # through `_combine`'s midnight default, so "[Utctime \"99:99:99\"]"
    # produced 00:00:00 tagged `pgn_utc_headers` -- a fabricated instant
    # wearing an exactness label. Caught by
    # test_malformed_headers_do_not_raise.
    ud, ut = _H_UTCDATE.search(pgn), _H_UTCTIME.search(pgn)
    if ud and ut:
        date_parts = _parse_dotted_date(ud.group(1))
        clock_parts = _parse_clock(ut.group(1))
        if date_parts and clock_parts:
            dt = _combine(date_parts, clock_parts)
            if dt:
                return dt, SRC_PGN_UTC

    # [Date]+[Time] are only usable when the PGN states the zone is UTC.
    # Without that, the offset is unknown and we do not invent one.
    d, t, tz = _H_DATE.search(pgn), _H_TIME.search(pgn), _H_TZ.search(pgn)
    if d and t and tz and tz.group(1).strip().upper() in ("UTC", "Z", "GMT"):
        date_parts = _parse_dotted_date(d.group(1))
        clock_parts = _parse_clock(t.group(1))
        if date_parts and clock_parts:
            dt = _combine(date_parts, clock_parts)
            if dt:
                return dt, SRC_PGN_LOCAL

    # Coach games are created live at the end of a session and carry no PGN
    # date headers, so `imported_at` is the moment the game was played to
    # within the length of one session. Tagged distinctly rather than
    # pretended to be header-exact.
    if (game.get("platform") or "").lower() == "coach":
        for field in ("imported_at", "created_at"):
            stamp = game.get(field)
            if isinstance(stamp, datetime):
                return (stamp if stamp.tzinfo
                        else stamp.replace(tzinfo=timezone.utc)), SRC_COACH
            parsed = parse_stored(stamp)
            if parsed:
                return parsed, SRC_COACH
        return None, SRC_NONE

    stored = parse_stored(game.get("date_played"))
    if stored and _ISO_PREFIX.match(str(game.get("date_played") or "")):
        return stored, SRC_STORED_ISO

    return None, SRC_NONE

"""Coach-promoted games must use the same timestamp wire format as imports.

`journey_service` writes games.imported_at / date_played and
game_analyses.created_at as ISO STRINGS. A BSON date in those fields is not a
cosmetic difference -- it breaks two whole classes of query silently:

  * BSON sorts Date ABOVE String, so every coach game would pin itself to the
    top of all `.sort("imported_at", -1)` recent-game lists forever, pushing
    real games out of every fixed-size window.
  * Range queries are type-bracketed, so `date_played: {"$gte": "<iso>"}`
    would never match a coach game at all.

Neither shows up in a fixture-only test, because fixtures are type-uniform.
This asserts the format at the source instead.
"""
import ast
import io
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
ROUTE = BACKEND / "routes" / "coach_play.py"
JOURNEY = BACKEND / "journey_service.py"

STRING_TIMESTAMP_FIELDS = {
    "imported_at", "date_played", "analyzed_at", "created_at",
}


def _promote_source() -> str:
    tree = ast.parse(io.open(ROUTE, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_promote_session_to_game":
            return ast.unparse(node)
    raise AssertionError("_promote_session_to_game not found")


def test_promotion_never_stores_a_bare_datetime_timestamp():
    source = _promote_source()
    assert "datetime.now(timezone.utc).isoformat()" in source, (
        "coach promotion must stamp ISO strings, not BSON dates"
    )
    for line in source.splitlines():
        stripped = line.strip()
        for field in STRING_TIMESTAMP_FIELDS:
            if stripped.startswith(f"'{field}'") or stripped.startswith(f'"{field}"'):
                assert "datetime.now(timezone.utc)," not in stripped + ",", (
                    f"{field} assigned a bare datetime: {stripped}"
                )


def test_imports_still_write_iso_strings():
    """If imports ever move to BSON dates, this file's premise changes."""
    journey = io.open(JOURNEY, encoding="utf-8").read()
    assert '"imported_at": datetime.now(timezone.utc).isoformat()' in journey, (
        "journey_service no longer writes imported_at as an ISO string; the "
        "coach-promotion format must be re-decided, not silently diverge"
    )


def test_promotion_normalizes_session_timestamps():
    source = _promote_source()
    assert "_as_iso_string(" in source, (
        "session ended_at/created_at must be normalized; coach_sessions "
        "stores ISO strings but the fallback is a datetime"
    )


def test_as_iso_string_handles_both_shapes():
    import sys
    sys.path.insert(0, str(BACKEND))
    from datetime import datetime, timezone
    from routes.coach_play import _as_iso_string

    assert _as_iso_string(None) is None
    assert _as_iso_string("") is None
    assert _as_iso_string("2026-09-10T00:00:00+00:00") == "2026-09-10T00:00:00+00:00"
    stamped = _as_iso_string(datetime(2026, 9, 10, tzinfo=timezone.utc))
    assert isinstance(stamped, str) and stamped.startswith("2026-09-10")

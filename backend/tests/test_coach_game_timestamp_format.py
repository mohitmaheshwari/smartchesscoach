"""Coach-promoted games must match the games schema's split timestamp format.

The schema is deliberately mixed, and both halves are load-bearing:

  * games.imported_at / date_played are ISO STRINGS (journey_service writes
    .isoformat()).  BSON sorts Date ABOVE String, so a datetime here would pin
    every coach game to the top of all 43 `.sort("imported_at", -1)`
    recent-game lists forever, pushing real games out of every fixed window.
  * games.analyzed_at and game_analyses.created_at are BSON DATES
    (analysis_worker writes datetime objects).  Range queries are
    type-bracketed, so a string here would never match
    `{"$gte": two_hours_ago}` in coach_advanced at all.

Neither failure shows up in a fixture-only test, because fixtures are
type-uniform: every document in one is written by the same code.  This asserts
the format at the source instead.
"""
import ast
import io
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
ROUTE = BACKEND / "routes" / "coach_play.py"
JOURNEY = BACKEND / "journey_service.py"

STRING_FIELDS = {"imported_at", "date_played"}
DATETIME_FIELDS = {"analyzed_at", "created_at"}


def _promote_node() -> ast.AsyncFunctionDef:
    tree = ast.parse(io.open(ROUTE, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_promote_session_to_game":
            return node
    raise AssertionError("_promote_session_to_game not found")


def _promote_source() -> str:
    return ast.unparse(_promote_node())


def _assignments():
    """Yield (field, unparsed value) for every timestamp key in a dict literal.

    Read from the AST, not the text: dict literals here span several lines and
    a line-based scan silently matches nothing, which would pass vacuously.
    """
    node = _promote_node()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Dict):
            continue
        for key, value in zip(sub.keys, sub.values):
            if isinstance(key, ast.Constant) and key.value in (
                STRING_FIELDS | DATETIME_FIELDS
            ):
                yield key.value, ast.unparse(value)


def test_string_fields_get_the_iso_string_and_dates_get_the_datetime():
    seen = set()
    for field, rhs in _assignments():
        seen.add(field)
        if field in STRING_FIELDS:
            assert rhs in {"completed_at_iso", "played_at"}, (
                f"games.{field} is an ISO string everywhere else; got {rhs!r}. "
                "A BSON date sorts above every existing string value, so coach "
                "games would pin themselves to the top of every recent list."
            )
        else:
            assert rhs == "completed_at", (
                f"{field} is a BSON date everywhere else; got {rhs!r}. "
                "A string never matches a type-bracketed $gte datetime query."
            )
    assert STRING_FIELDS <= seen, f"string timestamp fields missing: {STRING_FIELDS - seen}"
    assert DATETIME_FIELDS <= seen, f"date timestamp fields missing: {DATETIME_FIELDS - seen}"


def test_the_two_stamps_are_the_same_instant():
    source = _promote_source()
    assert "completed_at = datetime.now(timezone.utc)" in source
    assert "completed_at_iso = completed_at.isoformat()" in source, (
        "the string and date stamps must be derived from one instant, not "
        "two separate now() calls that can straddle a second boundary"
    )


def test_the_conventions_this_file_pins_still_hold_upstream():
    """If either upstream writer changes format, re-decide -- don't diverge."""
    journey = io.open(JOURNEY, encoding="utf-8").read()
    assert '"imported_at": datetime.now(timezone.utc).isoformat()' in journey, (
        "journey_service no longer writes games.imported_at as an ISO string"
    )
    worker = io.open(BACKEND / "analysis_worker.py", encoding="utf-8").read()
    assert '"analyzed_at": datetime.now(timezone.utc)' in worker, (
        "analysis_worker no longer writes games.analyzed_at as a BSON date"
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

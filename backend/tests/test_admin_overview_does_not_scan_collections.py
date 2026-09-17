"""The admin dashboard may not read every document to print a total.

Measured on production 2026-09-17, before this:

    /api/admin/overview          52.28s   for 894 bytes of JSON
      game_analyses.count_documents({})   73,704 ms
      games.count_documents({})            1,392 ms
      community_training_positions         896 ms
    /api/admin/users?limit=50     3.07s   (50 sequential per-user counts)

`count_documents({})` reads every document in order to count it. On
`game_analyses` that is 15,669 documents, each carrying every move
evaluation and every V5 review card, so the single call spent over a minute
of disk I/O to produce one integer. `estimated_document_count()` reads the
collection's own metadata and returned the identical figure in 100ms.

After: overview 517ms, users list 309ms, same numbers.

The trade is explicit: an estimate can drift from the true count after an
unclean shutdown. That is acceptable for a headline stat and is not
acceptable for anything that drives pagination, so `total` on the user list
stays an exact filtered count.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

SRC = BACKEND / "routes" / "admin.py"


def _code_only(block: str) -> str:
    """Strip comments, so the check reads the code and not the note about it.

    The comment explaining why `count_documents({})` was removed contains
    the phrase, which tripped the test that forbids it.
    """
    return "\n".join(
        line for line in block.splitlines()
        if not line.lstrip().startswith("#")
    )


def _overview() -> str:
    src = io.open(SRC, encoding="utf-8").read()
    start = src.index('@router.get("/admin/overview")')
    return _code_only(src[start:src.index("@router.", start + 10)])


def _list_users() -> str:
    src = io.open(SRC, encoding="utf-8").read()
    start = src.index('@router.get("/admin/users")')
    return _code_only(src[start:src.index("@router.", start + 10)])


def test_no_unfiltered_count_documents_in_the_overview():
    """`count_documents({})` is the exact call that cost 73 seconds."""
    body = _overview()
    assert "count_documents({})" not in body, (
        "an unfiltered count_documents scans the whole collection -- use "
        "estimated_document_count() for a whole-collection total"
    )


def test_the_big_collections_use_the_metadata_count():
    body = _overview()
    for collection in ("games", "game_analyses", "community_training_positions"):
        assert f"db.{collection}.estimated_document_count()" in body, collection


def test_filtered_counts_are_still_exact():
    """Only UNFILTERED totals may be estimated; a filter still has to count."""
    body = _overview()
    assert 'db.move_feedback.count_documents({"status": "pending"})' in body


def test_the_overview_reads_run_together():
    """Nine sequential awaits is nine round trips for independent numbers."""
    body = _overview()
    assert "asyncio.gather(" in body


def test_the_user_list_does_not_count_once_per_row():
    """The N+1: one count per user, sequentially, inside the render loop."""
    body = _list_users()
    assert 'await db.games.count_documents({"user_id": u["user_id"]})' not in body, (
        "one query per row -- group the whole page in a single aggregation"
    )
    assert "db.games.aggregate(" in body
    assert '"$group": {"_id": "$user_id", "n": {"$sum": 1}}' in body


def test_a_user_with_no_games_still_renders():
    """Absent from the aggregation is not absent from the page.

    The grouped query only returns users who have at least one game, so the
    lookup needs a default. Two accounts on page one have zero games; before
    the default existed they would have raised KeyError.
    """
    body = _list_users()
    assert re.search(r"counts\.get\(u\[.user_id.\],\s*0\)", body), (
        "game_count must default to 0 for users missing from the grouping"
    )


def test_pagination_total_is_not_estimated():
    """An estimate here would show a page that does not exist."""
    body = _list_users()
    assert "total = await db.users.count_documents(query)" in body

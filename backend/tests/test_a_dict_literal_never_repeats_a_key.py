"""A dict literal must never repeat a key.

Why this test exists
--------------------
On 2026-11-25 `quick_sync_loop` in server.py selected users with

    {"chess_com_username": {"$exists": True, "$ne": None, "$ne": ""}}

That is ONE dict with `$ne` twice, so Python keeps only the last pair and the
`$ne: None` test is silently dropped. Mongo then received `{"$exists": True,
"$ne": ""}`, which matches every user whose username is `None`.

Measured on prod the same day: the query selected 136 of 139 users, 66 of whom
had no username at all. The `.to_list(100)` cap was then filled with those
useless rows, pushing 8 of the 24 real lichess users out of the 5-minute sync
and onto the 6-hour one -- which is where the multi-hour "played ages ago,
imported just now" lags came from.

Nothing warns about this. It is valid Python, valid Mongo, and the query still
returns plausible-looking rows, so it survived in production. The same bug was
in `scripts/send_beta_feedback_email.py`, where it selected users with
`email=None` for an email send.

A regex over the source cannot do this job: the fixes left the bad pattern
quoted inside explanatory comments. So this walks the AST, where comments do
not exist, and it catches every duplicated literal key rather than only `$ne`.
"""

from __future__ import annotations

import ast
import io
from pathlib import Path
from typing import List, Tuple

BACKEND = Path(__file__).resolve().parent.parent

# Directories that are not shipped code.
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "venv", ".venv"}


def _python_files() -> List[Path]:
    out: List[Path] = []
    for path in BACKEND.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        out.append(path)
    return out


def _duplicate_keys(tree: ast.AST) -> List[Tuple[int, str]]:
    """Every dict literal in `tree` that repeats a constant key."""
    found: List[Tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        seen = set()
        for key in node.keys:
            # `{**a, "b": 1}` gives a None key; it carries no literal to compare.
            if key is None or not isinstance(key, ast.Constant):
                continue
            value = key.value
            if not isinstance(value, (str, int, float, bool, type(None))):
                continue
            marker = (type(value).__name__, value)
            if marker in seen:
                # Report the KEY's line, not the dict's: a long literal's
                # opening brace can be dozens of lines from the offender.
                found.append((key.lineno, repr(value)))
            seen.add(marker)
    return found


def test_no_dict_literal_repeats_a_key() -> None:
    offenders: List[str] = []
    unparseable: List[str] = []

    files = _python_files()
    assert files, "found no python files to scan -- the test is looking in the wrong place"

    for path in files:
        try:
            source = io.open(path, encoding="utf-8", errors="strict").read()
        except (UnicodeDecodeError, OSError):
            continue
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            # A file this interpreter cannot parse is not this test's business.
            unparseable.append(str(path.relative_to(BACKEND)))
            continue
        for lineno, key in _duplicate_keys(tree):
            offenders.append(f"{path.relative_to(BACKEND)}:{lineno} repeats key {key}")

    assert not offenders, (
        "a dict literal repeats a key, so Python silently discards every pair but "
        "the last -- the Mongo filter or kwargs you wrote is not the one that runs:\n  "
        + "\n  ".join(sorted(offenders))
    )


def test_the_scanner_actually_catches_the_bug() -> None:
    """A positive control: a zero above must mean "clean", not "scanner broken"."""
    bad = ast.parse(
        'q = {"chess_com_username": {"$exists": True, "$ne": None, "$ne": ""}}'
    )
    hits = _duplicate_keys(bad)
    assert hits, "the scanner failed to flag the exact production bug it exists for"
    assert hits[0][1] == repr("$ne")

    good = ast.parse('q = {"chess_com_username": {"$nin": [None, ""]}}')
    assert not _duplicate_keys(good), "the scanner flagged the correct form"


def test_true_and_one_are_not_confused() -> None:
    """`{True: a, 1: b}` is a real Python collision but reads as two keys.

    Kept as a documented non-finding: we compare (type, value), so True and 1
    are treated as distinct here. If that ever matters, this test is where to
    change the decision deliberately.
    """
    assert not _duplicate_keys(ast.parse("d = {True: 1, 1: 2}"))
    assert _duplicate_keys(ast.parse("d = {1: 'a', 1: 'b'}"))

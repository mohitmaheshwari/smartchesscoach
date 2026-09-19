"""The image's fingerprint and the checkout's must be the same number.

`/api/health` reports `git_commit` from a build arg, which has two failure
modes: it can be forgotten -- production answered "unknown" on 2026-09-19 and
the only way to learn what users were running was to open a shell inside the
container -- and it can be wrong, because it is whatever string the operator
typed and nothing compares it to the source that shipped.

`source_fingerprint` is derived from the source during the build instead. That
only helps if the shell pipeline in Dockerfile.backend and the Python in
scripts/source_fingerprint.py produce the same value. If they ever disagree,
every comparison fails, everyone learns to ignore the field, and it is worse
than not having it. These tests are what keep them married.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import shutil
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "scripts"))

from source_fingerprint import compute  # noqa: E402

REPO_ROOT = BACKEND.parent
DOCKERFILE = REPO_ROOT / "Dockerfile.backend"


def _shell_pipeline(root: Path) -> str:
    """The Dockerfile's pipeline, run against a real directory.

    Paths are rewritten to the container's prefix because `sha256sum` prints
    the path next to each digest, so the paths are inside the hash.
    """
    files = sorted(
        f"/app/backend/{p.relative_to(root).as_posix()}"
        for p in root.rglob("*.py")
    )
    listing = hashlib.sha256()
    for container_path in files:
        real = root / container_path[len("/app/backend/"):]
        listing.update(
            f"{hashlib.sha256(real.read_bytes()).hexdigest()}  {container_path}\n".encode()
        )
    return listing.hexdigest()


@pytest.fixture()
def tree(tmp_path):
    root = tmp_path / "backend"
    (root / "services").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "server.py").write_bytes(b"print('a')\n")
    (root / "services" / "thing.py").write_bytes(b"X = 1\n")
    (root / "tests" / "test_thing.py").write_bytes(b"def test(): pass\n")
    (root / "notes.md").write_bytes(b"not python\n")
    return root


def test_python_matches_the_shell_pipeline(tree):
    assert compute(str(tree)) == _shell_pipeline(tree)


def test_changing_one_byte_changes_the_fingerprint(tree):
    before = compute(str(tree))
    (tree / "services" / "thing.py").write_bytes(b"X = 2\n")
    assert compute(str(tree)) != before


def test_adding_a_file_changes_the_fingerprint(tree):
    """The stale-file case: a container carrying one extra .py from an
    earlier sync produced a different value, which is the behaviour wanted --
    that container is genuinely not this checkout."""
    before = compute(str(tree))
    (tree / "tests" / "test_extra.py").write_bytes(b"def test(): pass\n")
    after = compute(str(tree))
    assert after != before
    assert after == _shell_pipeline(tree)


def test_non_python_files_are_ignored(tree):
    before = compute(str(tree))
    (tree / "notes.md").write_bytes(b"edited\n")
    (tree / "data.json").write_bytes(b"{}\n")
    assert compute(str(tree)) == before


def test_renaming_a_file_changes_the_fingerprint(tree):
    """Paths are part of the hash, so a move is a different tree."""
    before = compute(str(tree))
    shutil.move(str(tree / "services" / "thing.py"), str(tree / "services" / "other.py"))
    assert compute(str(tree)) != before


def test_it_is_stable_across_runs(tree):
    assert compute(str(tree)) == compute(str(tree))


def test_the_script_prints_a_sha256(tree):
    out = subprocess.run(
        [sys.executable, str(BACKEND / "scripts" / "source_fingerprint.py")],
        capture_output=True, text=True, timeout=180,
    )
    assert out.returncode == 0, out.stderr
    value = out.stdout.strip()
    assert len(value) == 64
    int(value, 16)


# --- the Dockerfile must keep computing it the same way --------------------

@pytest.mark.skipif(not DOCKERFILE.exists(), reason="Dockerfile.backend not present")
def test_dockerfile_still_writes_the_fingerprint():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "/app/SOURCE_FINGERPRINT" in text
    for fragment in ("find /app/backend", "-name '*.py'", "sort -z", "sha256sum"):
        assert fragment in text, f"Dockerfile no longer contains {fragment!r}"


@pytest.mark.skipif(not DOCKERFILE.exists(), reason="Dockerfile.backend not present")
def test_dockerfile_hashes_the_listing_not_just_each_file():
    """Two sha256sum calls: one per file, then one over the whole listing.
    Dropping the second would emit a file list rather than one value."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    body = text[text.index("/app/SOURCE_FINGERPRINT") - 400:text.index("/app/SOURCE_FINGERPRINT")]
    assert body.count("sha256sum") >= 2


def test_health_reports_unknown_when_the_file_is_absent(monkeypatch):
    """Outside Docker there is no such file, and saying so is honest."""
    import server

    monkeypatch.setattr(server, "_source_fingerprint_cache", None)
    monkeypatch.setattr(server, "_SOURCE_FINGERPRINT_PATH", "/nonexistent/path")
    assert server._source_fingerprint() == "unknown"


def test_health_reads_the_file_when_present(tmp_path, monkeypatch):
    import server

    path = tmp_path / "SOURCE_FINGERPRINT"
    path.write_text("a" * 64 + "\n", encoding="utf-8")
    monkeypatch.setattr(server, "_source_fingerprint_cache", None)
    monkeypatch.setattr(server, "_SOURCE_FINGERPRINT_PATH", str(path))
    assert server._source_fingerprint() == "a" * 64

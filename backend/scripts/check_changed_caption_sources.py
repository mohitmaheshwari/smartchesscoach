"""Run the strict caption-source guard on the backend Python files in a Git diff.

The existing caption guard intentionally skips scripts and tests, so CI also
runs this module's contract tests on every change. This module owns only the
Git boundary; ``check_caption_sources.py`` remains the prose-policy authority.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


REPO_ROOT = Path(__file__).resolve().parents[2]
FULL_SHA = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class GateConfigurationError(RuntimeError):
    """The requested Git comparison cannot be evaluated safely."""


def _git(repo_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def _is_full_nonzero_sha(value: str) -> bool:
    return bool(FULL_SHA.fullmatch(value)) and any(char != "0" for char in value)


def _commit_exists(repo_root: Path, sha: str) -> bool:
    try:
        _git(repo_root, "cat-file", "-e", f"{sha}^{{commit}}")
    except subprocess.CalledProcessError:
        return False
    return True


def require_head(repo_root: Path, requested_head: str) -> str:
    head = requested_head.strip()
    if not _is_full_nonzero_sha(head) or not _commit_exists(repo_root, head):
        raise GateConfigurationError("head must be an existing full commit SHA")
    return head


def resolve_base(repo_root: Path, requested_base: str, head: str) -> str:
    base = requested_base.strip()
    if _is_full_nonzero_sha(base) and _commit_exists(repo_root, base):
        return base
    # Comparing a root commit to itself is empty and would under-scan a new
    # one-commit/orphan lineage. Git's canonical empty tree makes every file
    # in the head snapshot appear as added.
    return EMPTY_TREE_SHA


def changed_backend_python_paths(repo_root: Path, base: str, head: str) -> list[str]:
    raw = _git(
        repo_root,
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        "-z",
        base,
        head,
        "--",
    )
    selected: list[str] = []
    for encoded in raw.split(b"\0"):
        if not encoded:
            continue
        path = encoded.decode("utf-8", errors="surrogateescape")
        pure = PurePosixPath(path)
        if (
            pure.parts
            and pure.parts[0] == "backend"
            and ".." not in pure.parts
            and pure.suffix == ".py"
        ):
            selected.append(path)
    return sorted(set(selected))


def run_strict_guard(repo_root: Path, paths: list[str]) -> int:
    if not paths:
        print("[caption-guard] No changed backend Python files.")
        return 0
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "backend/scripts/check_caption_sources.py"),
            "--strict",
            *paths,
        ],
        cwd=repo_root,
        check=False,
    )
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args(argv)

    try:
        head = require_head(REPO_ROOT, args.head)
        base = resolve_base(REPO_ROOT, args.base, head)
        paths = changed_backend_python_paths(REPO_ROOT, base, head)
    except (GateConfigurationError, subprocess.CalledProcessError) as exc:
        print(f"[caption-guard] Configuration failure: {exc}", file=sys.stderr)
        return 2

    print(f"[caption-guard] Comparing {base}..{head}; files={len(paths)}")
    return run_strict_guard(REPO_ROOT, paths)


if __name__ == "__main__":
    raise SystemExit(main())

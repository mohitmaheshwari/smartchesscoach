#!/usr/bin/env python3
"""Fingerprint the backend source, so a container can be identified.

`/api/health` reports `git_commit`, but that comes from a build arg, and a
build arg has two failure modes: it can be forgotten (production answered
"unknown" on 2026-09-19, and the only way to learn what users were running
was to open a shell inside the container), and it can be wrong, because it is
whatever string the operator typed and nothing compares it to the source that
was actually copied in.

This is derived from the source itself. `Dockerfile.backend` computes it
during the build and writes /app/SOURCE_FINGERPRINT; this script computes the
same value from a checkout. If they match, that checkout is what is running.

    # what is production serving?
    curl -s https://chessguru.ai/api/health | python -c \
        "import json,sys; print(json.load(sys.stdin)['source_fingerprint'])"

    # is it this checkout?
    python backend/scripts/source_fingerprint.py

The two must agree byte for byte. Keep the algorithm here identical to the
RUN line in Dockerfile.backend: every *.py under backend/, NUL-separated,
sorted, `sha256sum` each, then `sha256sum` of that listing.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys


def compute(root: str) -> str:
    """Mirror of the Dockerfile's pipeline, in Python.

    `sha256sum` prints "<hex>  <path>\n" per file, and the digest is taken
    over that whole listing, so the paths are part of the hash. They are the
    container's paths (/app/backend/...), which is why `root` is rewritten to
    that prefix rather than hashed as it sits on the developer's disk.
    """
    paths = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".py"):
                paths.append(os.path.join(dirpath, name))

    # `sort -z` orders by raw bytes; Python's default str sort matches for
    # ASCII paths, which is all this tree has.
    rewritten = []
    for path in paths:
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        rewritten.append((f"/app/backend/{rel}", path))
    rewritten.sort(key=lambda pair: pair[0])

    listing = hashlib.sha256()
    for container_path, real_path in rewritten:
        with open(real_path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        listing.update(f"{digest}  {container_path}\n".encode("utf-8"))
    return listing.hexdigest()


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, ".."))
    if not os.path.isdir(root):
        print(f"no backend directory at {root}", file=sys.stderr)
        return 1
    print(compute(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

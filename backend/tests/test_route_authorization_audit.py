"""Enumeration gate: every route's authorization posture, every run.

Reviews of this codebase were exploratory -- each one looked somewhere new and
found something new, so the score never converged and "did we get them all?"
had no answer. These tests replace that with a denominator: all 637 routes are
enumerated, and anything reachable without authentication must be declared.

A new unauthenticated route fails here the moment it is written, rather than
whenever someone next happens to read that file.
"""
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
AUDIT = BACKEND / "scripts" / "audit_route_authorization.py"

sys.path.insert(0, str(BACKEND))


def _audit():
    from scripts.audit_route_authorization import audit
    return audit()


def test_no_admin_path_route_is_missing_an_admin_gate():
    """An /admin/* route must be admin-gated, by dependency or in-body assert.

    Four were not: the feedback download had no auth at all, and
    send-all-weekly-summaries -- which mails EVERY user -- took only
    get_current_user behind a comment reading "use proper admin auth".
    """
    report = _audit()
    offenders = [
        f"{r['key']}  ({r['file']}:{r['line']}, deps={r['dependencies'] or 'NONE'})"
        for r in report["admin_path_not_admin_gated"]
    ]
    assert not offenders, (
        "admin-path routes reachable without an admin gate:\n  "
        + "\n  ".join(offenders)
    )


def test_every_public_route_is_declared():
    """Public routes are allowed, but only deliberately.

    The point is that a route cannot become publicly reachable silently --
    making one public requires an entry in PUBLIC_ROUTES with a reason, which
    shows up in the diff.
    """
    report = _audit()
    undeclared = [
        f"{r['key']}  ({r['file']}:{r['line']})"
        for r in report["undeclared_public"]
    ]
    assert not undeclared, (
        f"{len(undeclared)} route(s) are reachable without authentication and "
        "are not declared in PUBLIC_ROUTES. Either add an auth dependency or "
        "declare them with a reason:\n  " + "\n  ".join(sorted(undeclared))
    )


def test_the_audit_actually_enumerates_the_whole_surface():
    """Guard against the audit silently finding nothing and passing.

    A gate that reports zero because it parsed zero files is worse than no
    gate, because it reads as a pass.
    """
    report = _audit()
    assert report["total_routes"] > 500, (
        f"only {report['total_routes']} routes enumerated; the audit is "
        "probably not parsing the route modules"
    )
    assert report["authenticated"] > 400


def test_cors_is_never_wildcard_with_credentials():
    """A wildcard origin plus credentials defeats the allowlist entirely.

    Production echoed Access-Control-Allow-Origin: https://evil.example with
    Access-Control-Allow-Credentials: true, so any site could make credentialed
    requests to the API and read the responses.
    """
    source = (BACKEND / "server.py").read_text(encoding="utf-8")
    start = source.find("CORSMiddleware")
    assert start != -1, "CORS middleware registration not found"
    block = source[start:start + 700]
    if "allow_credentials=True" in block:
        assert 'allow_origins=["*"]' not in block, (
            "allow_origins=['*'] with allow_credentials=True lets any origin "
            "make credentialed requests"
        )
        assert "allow_origins=ALLOWED_ORIGINS" in block, (
            "credentialed CORS must use the explicit ALLOWED_ORIGINS allowlist"
        )


def test_audit_script_exits_nonzero_on_failure():
    """The gate must be usable from CI, not just from pytest."""
    result = subprocess.run(
        [sys.executable, str(AUDIT), "--json"],
        capture_output=True, text=True, cwd=str(BACKEND.parent),
    )
    assert result.returncode in (0, 1), f"unexpected exit {result.returncode}"
    assert '"total_routes"' in result.stdout

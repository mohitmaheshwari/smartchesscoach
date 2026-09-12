"""The admin baseline override must stay narrow: one named account, never a cohort.

Admin accounts are kept out of the real-user Phase 8 cohort so they cannot skew
its reach and transfer metrics. That rule is about MEASUREMENT. Applied to
PROVISIONING it also denied the validation account the pre-enrollment baseline
that gates its own access, so on 2026-09-12
/api/game-review/recommendation returned:

    {"enabled": false, "reason": "baseline_missing"}

while 41 pilot users were correctly provisioned. Three separate scripts carried
the same exclusion (configure_phase8_pilot, migrate_destination_safety_focus,
capture_phase8_baselines), which is why the founder's own account could not see
the product it exists to validate.

`allow_admin` is the deliberate escape hatch. These tests hold its shape:
default off, single account only, and refused outright with --all.
"""
import ast
import io
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND / "scripts" / "capture_phase8_baselines.py"
SERVICE = BACKEND / "services" / "phase8_release_evidence.py"


def _src(path: Path) -> str:
    return io.open(path, encoding="utf-8").read()


def _func(path: Path, name: str):
    for node in ast.walk(ast.parse(_src(path))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path.name}")


def test_allow_admin_defaults_to_false():
    """Every existing caller must keep the old behaviour untouched."""
    fn = _func(SERVICE, "build_pre_enrollment_baseline")
    kwonly = {a.arg: d for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults)}
    assert "allow_admin" in kwonly, "the escape hatch must be an explicit keyword"
    default = kwonly["allow_admin"]
    assert isinstance(default, ast.Constant) and default.value is False, (
        "allow_admin must default to False so the cohort path is unchanged"
    )


def test_the_admin_guard_still_fires_without_the_override():
    src = _src(SERVICE)
    assert "not allow_admin" in src
    assert 'raise ValueError("admin accounts cannot enter the real-user baseline")' in src, (
        "the exclusion must remain the default for the real-user cohort"
    )


def test_the_flag_requires_a_single_named_account():
    src = _src(SCRIPT)
    assert 'if args.include_admin and not args.email:' in src, (
        "--include-admin without --email would have no named subject"
    )
    assert '"--include-admin requires --email for a single account"' in src


def test_the_flag_is_refused_with_all():
    """This is the property that stops it becoming a cohort-wide switch."""
    src = _src(SCRIPT)
    assert 'if args.include_admin and args.all_users:' in src
    assert '"--include-admin cannot be combined with --all"' in src


def test_the_override_is_also_narrowed_at_the_call_site():
    """Belt and braces: even if arg parsing were bypassed, email is required."""
    src = _src(SCRIPT)
    assert "allow_admin=include_admin and bool(email)" in src, (
        "the call site must re-check that a single account was named"
    )


def test_apply_still_needs_the_confirmation_phrase():
    """The override must not weaken any other safeguard."""
    src = _src(SCRIPT)
    assert "args.apply and args.confirm != CONFIRMATION" in src
    assert "--source-commit or GIT_COMMIT is required" in src


@pytest.mark.parametrize("role", ["admin", "super_admin"])
def test_both_privileged_roles_are_covered_by_the_default_guard(role):
    src = _src(SERVICE)
    assert role in src, f"{role} must still be named in the default exclusion"

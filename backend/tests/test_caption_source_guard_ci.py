import importlib.util
from pathlib import Path
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend/scripts/check_caption_sources.py"
CHANGED_GATE_PATH = REPO_ROOT / "backend/scripts/check_changed_caption_sources.py"
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/ci.yml"

SPEC = importlib.util.spec_from_file_location("check_caption_sources", SCRIPT_PATH)
guard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(guard)

CHANGED_SPEC = importlib.util.spec_from_file_location(
    "check_changed_caption_sources", CHANGED_GATE_PATH
)
changed_gate = importlib.util.module_from_spec(CHANGED_SPEC)
assert CHANGED_SPEC.loader is not None
CHANGED_SPEC.loader.exec_module(changed_gate)


def test_scan_detects_noncentral_chess_teaching_prose(tmp_path):
    source = tmp_path / "backend/new_caption_path.py"
    source.parent.mkdir()
    source.write_text(
        'import chess\nmessage = "You played Nf3, but Qh5 was better"\n',
        encoding="utf-8",
    )

    findings = guard.scan_file(source, tmp_path)

    assert len(findings) == 1
    assert findings[0][0] == "backend/new_caption_path.py"


def test_explicit_line_exception_is_narrow_and_visible(tmp_path):
    source = tmp_path / "backend/exempt_caption_path.py"
    source.parent.mkdir()
    source.write_text(
        'import chess\nmessage = "Qh5 was better"  # allow-noncentral-caption\n',
        encoding="utf-8",
    )

    assert guard.scan_file(source, tmp_path) == []


def test_strict_mode_returns_failure_when_a_target_has_a_finding(monkeypatch):
    monkeypatch.setattr(
        guard,
        "scan_file",
        lambda _path, _root: [("backend/new_path.py", 2, '"Qh5 was better"')],
    )

    assert guard.main(["--strict", str(SCRIPT_PATH)]) == 1


def test_warn_mode_does_not_masquerade_as_the_ci_contract(monkeypatch):
    monkeypatch.setattr(
        guard,
        "scan_file",
        lambda _path, _root: [("backend/legacy.py", 2, '"Qh5 was better"')],
    )

    assert guard.main([str(SCRIPT_PATH)]) == 0


@pytest.mark.parametrize("requested", ["", "0" * 40])
def test_invalid_or_zero_base_falls_back_to_the_single_root(monkeypatch, requested):
    head = "b" * 40
    root = "a" * 40

    def fake_git(_repo_root, *args):
        assert args == ("rev-list", "--max-parents=0", head)
        return f"{root}\n".encode("ascii")

    monkeypatch.setattr(changed_gate, "_git", fake_git)

    assert changed_gate.resolve_base(REPO_ROOT, requested, head) == root


def test_existing_full_base_is_used_without_root_fallback(monkeypatch):
    base = "a" * 40
    monkeypatch.setattr(changed_gate, "_commit_exists", lambda _root, sha: sha == base)
    monkeypatch.setattr(
        changed_gate,
        "_git",
        lambda *_args: pytest.fail("root lookup must not run for an existing base"),
    )

    assert changed_gate.resolve_base(REPO_ROOT, base, "b" * 40) == base


def test_invalid_or_missing_head_fails_closed(monkeypatch):
    monkeypatch.setattr(changed_gate, "_commit_exists", lambda *_args: False)

    with pytest.raises(changed_gate.GateConfigurationError):
        changed_gate.require_head(REPO_ROOT, "not-a-commit")


def test_changed_path_selection_uses_acmr_and_only_backend_python(monkeypatch):
    captured = []

    def fake_git(_repo_root, *args):
        captured.append(args)
        return (
            b"backend/a.py\0backend/nested/b.py\0frontend/c.py\0"
            b"backend/not_python.js\0outside/backend/d.py\0"
        )

    monkeypatch.setattr(changed_gate, "_git", fake_git)

    assert changed_gate.changed_backend_python_paths(
        REPO_ROOT, "a" * 40, "b" * 40
    ) == ["backend/a.py", "backend/nested/b.py"]
    assert captured == [
        (
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            "-z",
            "a" * 40,
            "b" * 40,
            "--",
        )
    ]


def test_changed_gate_propagates_strict_guard_status(monkeypatch):
    monkeypatch.setattr(changed_gate, "require_head", lambda *_args: "b" * 40)
    monkeypatch.setattr(changed_gate, "resolve_base", lambda *_args: "a" * 40)
    monkeypatch.setattr(
        changed_gate,
        "changed_backend_python_paths",
        lambda *_args: ["backend/new_path.py"],
    )
    seen = []

    def fake_run(_root, paths):
        seen.append(paths)
        return 1

    monkeypatch.setattr(changed_gate, "run_strict_guard", fake_run)

    assert changed_gate.main(["--base", "bad", "--head", "bad"]) == 1
    assert seen == [["backend/new_path.py"]]


def test_ci_runs_contract_and_changed_gate_without_discarding_status():
    source = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "fetch-depth: 0" in source
    assert "python -m pytest backend/tests/test_caption_source_guard_ci.py -q" in source
    assert "python backend/scripts/check_changed_caption_sources.py" in source
    assert '--base "$BASE_SHA"' in source
    assert '--head "$GITHUB_SHA"' in source
    assert "check_caption_sources.py || true" not in source

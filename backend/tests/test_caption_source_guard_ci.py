import importlib.util
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend/scripts/check_caption_sources.py"
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/ci.yml"

SPEC = importlib.util.spec_from_file_location("check_caption_sources", SCRIPT_PATH)
guard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(guard)


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


def test_ci_runs_strict_guard_on_changed_python_without_discarding_status():
    source = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert yaml.safe_load(source)
    assert "fetch-depth: 0" in source
    assert 'git diff --name-only --diff-filter=ACMR "$BASE_SHA" "$GITHUB_SHA"' in source
    assert 'backend/*.py) changed_python+=("$path")' in source
    assert 'check_caption_sources.py --strict "${changed_python[@]}"' in source
    assert "check_caption_sources.py || true" not in source

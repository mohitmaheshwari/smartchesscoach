import json
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
DOCKERFILES = (
    REPO_ROOT / "Dockerfile",
    REPO_ROOT / "Dockerfile.frontend",
    REPO_ROOT / "Dockerfile.frontend.build",
)
CI_WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"
LEGACY_PUBLISH = FRONTEND / "publish.ps1"


def test_yarn_is_the_only_frontend_resolution_authority():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))

    assert package["packageManager"] == "yarn@1.22.22+sha512.a6b2f7906b721bba3d67d4aff083df04dad64c399707841b7acf00f6b133b7ac24255f2652fa22ae3534329dc6180534e98d17432037ff6fd140556e2bb3137e"
    assert (FRONTEND / "yarn.lock").is_file()
    assert not (FRONTEND / "package-lock.json").exists()


def test_removed_calendar_dependency_cannot_return_unnoticed():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))

    assert "react-day-picker" not in package.get("dependencies", {})
    assert "react-day-picker" not in (FRONTEND / "yarn.lock").read_text(
        encoding="utf-8"
    )
    assert not (FRONTEND / "src/components/ui/calendar.jsx").exists()


def test_direct_frontend_dependencies_are_exactly_pinned():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    exact_version = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")

    for section in ("dependencies", "devDependencies"):
        for name, version in package.get(section, {}).items():
            assert exact_version.fullmatch(version), (
                f"{section}.{name} must be exact, got {version!r}"
            )


@pytest.mark.parametrize("dockerfile", DOCKERFILES, ids=lambda path: path.name)
def test_every_frontend_docker_install_consumes_the_frozen_yarn_lock(dockerfile):
    source = dockerfile.read_text(encoding="utf-8")

    assert "frontend/yarn.lock" in source
    assert "package-lock" not in source
    assert "yarn install --frozen-lockfile" in source


def test_frontend_ci_consumes_the_same_frozen_yarn_lock():
    source = CI_WORKFLOW.read_text(encoding="utf-8")

    assert 'cache: "yarn"' in source
    assert "cache-dependency-path: frontend/yarn.lock" in source
    assert "yarn install --frozen-lockfile" in source
    assert "package-lock" not in source
    assert "npm ci" not in source


def test_tracked_publish_script_cannot_resolve_or_publish_an_npm_graph():
    source = LEGACY_PUBLISH.read_text(encoding="utf-8")

    assert "yarn install --frozen-lockfile --ignore-engines --non-interactive" in source
    assert "yarn build" in source
    assert "npm install" not in source
    assert "npm run build" not in source
    assert "Skipping npm install" not in source

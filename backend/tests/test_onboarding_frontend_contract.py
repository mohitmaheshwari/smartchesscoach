"""Runnable guards for onboarding's critical browser/network boundaries.

The local frontend dependency tree cannot currently execute Testing Library,
so these guards enforce the two failure modes at source level while the JSX
files are independently parsed with Babel.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _source(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_account_verification_uses_chessguru_backend_not_third_party_browser_fetch():
    source = _source("frontend/src/pages/Onboarding.jsx")

    assert "api.chess.com/pub/player" not in source
    assert "lichess.org/api/user" not in source
    assert "`${API}/settings/link-account`" in source
    assert source.index("if (!linkRes.ok)") < source.index("setChessComVerified(true)")


def test_activation_actions_do_not_wait_for_profile_save():
    source = _source("frontend/src/pages/ActivationHub.jsx")

    assert "void markSeen();" in source
    assert "await markSeen();" not in source
    assert "navigate(path, { state: { fromActivationHub: true } });" in source
    assert "keepalive: true" in source


def test_activation_route_state_skips_only_onboarding_check():
    source = _source("frontend/src/App.js")

    assert "const activationHubBypass = location.state?.fromActivationHub === true;" in source
    assert "!skipOnboardingCheck && !demoBypass && !activationHubBypass" in source
    assert "if (!isAuthenticated || redirectTarget === '/')" in source

"""Regression guards for high-risk player-development claims.

These checks complement the behavioral PIC tests. They keep legacy surfaces
from reintroducing claims that their current data cannot support.
"""

from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _source(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_focus_window_completion_does_not_claim_mastery_or_improvement():
    from coach_state.focus_lock_service import get_lock_copy

    headline, message = get_lock_copy("COMPLETED", "FORCING_BLIND")

    assert headline == "Focus checkpoint passed."
    assert "master" not in headline.lower()
    assert "improv" not in message.lower()


def test_win_streak_copy_does_not_claim_real_improvement():
    source = _source("backend/home_intelligence_service.py")

    assert "win streak shows real improvement" not in source


def test_legacy_progress_records_do_not_render_fixed_or_mastered_claims():
    source = _source("backend/routes/player.py")

    assert '"message": f"Fixed:' not in source
    assert '"message": f"Mastered via reflection' not in source


def test_reengagement_email_does_not_claim_improvement_from_profile_label():
    from scripts.generate_reengagement_emails import build_subject, trend_hook

    subject = build_subject("Asha", "improving", "Italian", 30)
    hook = trend_hook("improving", 10)

    assert "getting better" not in subject.lower()
    assert "getting better" not in hook.lower()
    assert "improv" not in hook.lower()


def test_landing_describes_comparison_instead_of_claiming_recovery_detection():
    source = _source("frontend/src/pages/Landing.jsx")

    assert "knows when you've improved" not in source


def test_pricing_does_not_offer_unverified_recurring_checkout():
    source = _source("frontend/src/pages/Pricing.jsx")

    assert "Subscriptions temporarily unavailable" in source
    assert "complete coaching and billing" in source

"""Security regression tests for subscription entitlement mutation.

Production Pro access must come from the payment-provider verification path,
never from the legacy authenticated mock endpoint.
"""

from pathlib import Path
import sys

import pytest
from fastapi import HTTPException


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_mock_subscription_upgrade_route_is_not_registered():
    from routes.gamification import router

    registered = {
        (route.path, method)
        for route in router.routes
        for method in (route.methods or set())
    }

    assert ("/subscription/upgrade", "POST") not in registered


def test_subscription_service_has_no_direct_pro_upgrade_helper():
    import subscription_service

    assert not hasattr(subscription_service, "upgrade_to_pro")


def test_legacy_order_checkout_is_default_off_even_when_keys_exist(monkeypatch):
    from routes import billing

    monkeypatch.delenv(billing.LEGACY_CHECKOUT_FLAG, raising=False)
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_example")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")

    assert billing._checkout_enabled() is False
    with pytest.raises(HTTPException) as exc:
        billing._client()
    assert exc.value.status_code == 503


def test_legacy_order_checkout_cannot_be_enabled_with_live_keys(monkeypatch):
    from routes import billing

    monkeypatch.setenv(billing.LEGACY_CHECKOUT_FLAG, "true")
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_live_example")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")

    assert billing._checkout_enabled() is False


def test_legacy_order_checkout_can_only_be_enabled_for_explicit_sandbox_use(monkeypatch):
    from routes import billing

    monkeypatch.setenv(billing.LEGACY_CHECKOUT_FLAG, "true")
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_example")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")

    assert billing._checkout_enabled() is True


@pytest.mark.asyncio
async def test_billing_config_does_not_offer_legacy_checkout_by_default(monkeypatch):
    from routes import billing

    monkeypatch.delenv(billing.LEGACY_CHECKOUT_FLAG, raising=False)
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_example")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")

    config = await billing.billing_config()

    assert config["enabled"] is False
    assert config["legacy_one_time_checkout"] is False

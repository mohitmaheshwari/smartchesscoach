"""The coaching-room presentation gate.

The gate decides who is exposed to the redesign, so its failure modes matter
more than its happy path: an unset or malformed value must fail CLOSED.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import coaching_room_gate as gate  # noqa: E402


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv(gate.ALLOWLIST_ENV, raising=False)
    monkeypatch.delenv(gate.PERCENT_ENV, raising=False)


def test_unset_is_off_for_everyone():
    assert gate.is_enabled("user_anyone") is False
    assert gate.is_enabled("user_8b599930d7ef") is False  # a super-admin too


def test_named_account_is_on(monkeypatch):
    monkeypatch.setenv(gate.ALLOWLIST_ENV, "user_mohit,user_parth")
    assert gate.is_enabled("user_mohit") is True
    assert gate.is_enabled("user_parth") is True
    assert gate.is_enabled("user_someone_else") is False


def test_allowlist_tolerates_spacing(monkeypatch):
    monkeypatch.setenv(gate.ALLOWLIST_ENV, "  user_a , user_b ,, ")
    assert gate.is_enabled("user_a") is True
    assert gate.is_enabled("user_b") is True


def test_star_enables_everyone(monkeypatch):
    monkeypatch.setenv(gate.ALLOWLIST_ENV, "*")
    assert gate.is_enabled("user_anyone") is True


def test_missing_user_id_is_off(monkeypatch):
    monkeypatch.setenv(gate.ALLOWLIST_ENV, "*")
    assert gate.is_enabled(None) is False
    assert gate.is_enabled("") is False


def test_bucket_is_stable():
    first = gate.bucket_of("user_abc")
    assert first == gate.bucket_of("user_abc")
    assert 0 <= first < 100


def test_percent_rollout_is_roughly_right(monkeypatch):
    monkeypatch.setenv(gate.PERCENT_ENV, "10")
    ids = ["user_%04d" % i for i in range(2000)]
    on = [u for u in ids if gate.is_enabled(u)]
    # Hash spread, not an exact decile - assert the band, not a magic number.
    assert 150 <= len(on) <= 250, "10%% of 2000 landed at %d" % len(on)


def test_percent_is_monotonic(monkeypatch):
    ids = ["user_%04d" % i for i in range(500)]
    monkeypatch.setenv(gate.PERCENT_ENV, "10")
    small = {u for u in ids if gate.is_enabled(u)}
    monkeypatch.setenv(gate.PERCENT_ENV, "50")
    large = {u for u in ids if gate.is_enabled(u)}
    # Nobody may lose the redesign when the rollout widens.
    assert small <= large


def test_malformed_percent_fails_closed(monkeypatch):
    monkeypatch.setenv(gate.PERCENT_ENV, "ten")
    assert gate.is_enabled("user_anyone") is False


def test_percent_is_clamped(monkeypatch):
    monkeypatch.setenv(gate.PERCENT_ENV, "-5")
    assert gate.is_enabled("user_anyone") is False
    monkeypatch.setenv(gate.PERCENT_ENV, "500")
    assert gate.is_enabled("user_anyone") is True

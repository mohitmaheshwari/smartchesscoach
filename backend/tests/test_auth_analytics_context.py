from routes.auth import User


def test_auth_me_projection_exposes_only_coarse_analytics_provenance():
    payload = User(
        user_id="user_safe123",
        email="player@example.com",
        name="Player",
        is_demo=True,
        analytics_excluded=True,
    ).model_dump()

    assert payload["is_demo"] is True
    assert payload["analytics_excluded"] is True
    assert "analytics_id" not in payload


def test_analytics_provenance_defaults_do_not_exclude_real_players():
    payload = User(
        user_id="user_safe123",
        email="player@example.com",
        name="Player",
    ).model_dump()

    assert payload["is_demo"] is False
    assert payload["analytics_excluded"] is False

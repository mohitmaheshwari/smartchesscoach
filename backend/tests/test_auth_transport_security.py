"""Security contract for browser-cookie and native-bearer authentication."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import BackgroundTasks, HTTPException, Request, Response

from routes import auth as auth_routes


class FakeCollection:
    def __init__(self, documents):
        self.documents = list(documents)

    async def find_one(self, query, projection=None):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                result = dict(document)
                if projection and projection.get("_id") == 0:
                    result.pop("_id", None)
                return result
        return None

    async def insert_one(self, document):
        self.documents.append(dict(document))

    async def delete_many(self, query):
        self.documents = [
            document
            for document in self.documents
            if not all(document.get(key) == value for key, value in query.items())
        ]

        return None


class FakeDB:
    def __init__(self, sessions, users):
        self.user_sessions = FakeCollection(sessions)
        self.users = FakeCollection(users)


def make_request(*, cookie=None, bearer=None, oauth_nonce=None, path="/api/auth/me"):
    headers = []
    cookies = []
    if cookie:
        cookies.append(f"session_token={cookie}")
    if oauth_nonce:
        cookies.append(f"{auth_routes.OAUTH_STATE_COOKIE}={oauth_nonce}")
    if cookies:
        headers.append((b"cookie", "; ".join(cookies).encode("ascii")))
    if bearer:
        headers.append((b"authorization", f"Bearer {bearer}".encode("ascii")))
    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    })


@pytest.fixture
def auth_db(monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    database = FakeDB(
        sessions=[
            {"session_token": "web-token", "user_id": "web-user", "expires_at": future},
            {"session_token": "mobile-token", "user_id": "mobile-user", "expires_at": future, "is_mobile": True},
            {"session_token": "expired-token", "user_id": "web-user", "expires_at": "2000-01-01T00:00:00+00:00"},
        ],
        users=[
            {"user_id": "web-user", "email": "web@example.test", "name": "Web User"},
            {"user_id": "mobile-user", "email": "mobile@example.test", "name": "Mobile User"},
            {"user_id": auth_routes.DEV_USER_ID, "email": "dev@example.test", "name": "Dev User"},
        ],
    )
    monkeypatch.setattr(auth_routes, "db", database)
    monkeypatch.setattr(auth_routes, "DEV_MODE", False)
    return database


@pytest.mark.asyncio
async def test_browser_cookie_authenticates(auth_db):
    user = await auth_routes.get_current_user(make_request(cookie="web-token"))
    assert user.user_id == "web-user"


@pytest.mark.asyncio
async def test_explicit_mobile_bearer_authenticates(auth_db):
    user = await auth_routes.get_current_user(make_request(bearer="mobile-token"))
    assert user.user_id == "mobile-user"


@pytest.mark.asyncio
async def test_browser_session_cannot_be_replayed_as_bearer(auth_db):
    with pytest.raises(HTTPException) as error:
        await auth_routes.get_current_user(make_request(bearer="web-token"))
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_cookie_wins_when_cookie_and_bearer_are_both_present(auth_db):
    user = await auth_routes.get_current_user(
        make_request(cookie="web-token", bearer="mobile-token")
    )
    assert user.user_id == "web-user"


@pytest.mark.asyncio
@pytest.mark.parametrize("token", ["missing-token", "expired-token"])
async def test_bad_explicit_credential_never_falls_through_to_dev_user(auth_db, monkeypatch, token):
    monkeypatch.setattr(auth_routes, "DEV_MODE", True)
    with pytest.raises(HTTPException) as error:
        await auth_routes.get_current_user(make_request(cookie=token))
    assert error.value.status_code == 401


@pytest.mark.parametrize(
    "candidate,expected",
    [
        ("/home", "/home"),
        ("/game/abc", "/game/abc"),
        ("https://evil.example/steal", "/home"),
        ("//evil.example/steal", "/home"),
        ("home", "/home"),
        ("/home?token=leak", "/home"),
        ("/home#token=leak", "/home"),
        ("/home\nSet-Cookie: bad=1", "/home"),
    ],
)
def test_oauth_redirect_is_a_plain_local_path(candidate, expected):
    assert auth_routes._safe_frontend_redirect_path(candidate) == expected


def test_signed_oauth_state_round_trip():
    state = auth_routes._encode_oauth_state(
        platform="web",
        redirect_to="/welcome",
        nonce="browser-nonce",
        secret="test-secret",
        issued_at=1_000,
    )
    payload = auth_routes._decode_oauth_state(
        state,
        secret="test-secret",
        expected_nonce="browser-nonce",
        now=1_001,
    )
    assert payload == {
        "iat": 1_000,
        "nonce": "browser-nonce",
        "platform": "web",
        "redirect_to": "/welcome",
        "version": auth_routes.OAUTH_STATE_VERSION,
    }


@pytest.mark.parametrize(
    "failure",
    ["tampered", "expired", "future", "nonce", "missing-cookie", "platform", "redirect"],
)
def test_invalid_oauth_state_fails_closed(failure):
    issued_at = 10_000
    state = auth_routes._encode_oauth_state(
        platform="mobile",
        redirect_to="/home",
        nonce="right-nonce",
        secret="test-secret",
        issued_at=issued_at,
    )
    now = issued_at
    expected_nonce = "right-nonce"
    if failure == "tampered":
        state = state[:-1] + ("A" if state[-1] != "A" else "B")
    elif failure == "expired":
        now += auth_routes.OAUTH_STATE_MAX_AGE_SECONDS + 1
    elif failure == "future":
        now -= auth_routes.OAUTH_STATE_CLOCK_SKEW_SECONDS + 1
    elif failure == "nonce":
        expected_nonce = "wrong-nonce"
    elif failure == "missing-cookie":
        expected_nonce = None
    elif failure == "platform":
        state = auth_routes._encode_oauth_state(
            platform="desktop",
            redirect_to="/home",
            nonce="right-nonce",
            secret="test-secret",
            issued_at=issued_at,
        )
    elif failure == "redirect":
        state = auth_routes._encode_oauth_state(
            platform="web",
            redirect_to="https://evil.example/steal",
            nonce="right-nonce",
            secret="test-secret",
            issued_at=issued_at,
        )

    with pytest.raises(HTTPException) as error:
        auth_routes._decode_oauth_state(
            state,
            secret="test-secret",
            expected_nonce=expected_nonce,
            now=now,
        )
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_google_login_sets_browser_bound_nonce_and_opaque_state(monkeypatch):
    monkeypatch.setattr(
        auth_routes,
        "_get_google_config",
        lambda: (
            "client-id",
            "client-secret",
            "https://chessguru.ai/api/auth/google/callback",
            "https://chessguru.ai",
        ),
    )
    response = Response()
    result = await auth_routes.google_login(
        make_request(path="/api/auth/google/login"),
        response,
        platform="web",
        redirect_to="/welcome",
    )

    query = parse_qs(urlsplit(result["auth_url"]).query)
    state = query["state"][0]
    assert "/welcome" not in state
    assert "oauth_state_nonce=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_mobile_redirect_flow_starts_at_backend_and_sets_nonce(monkeypatch):
    monkeypatch.setattr(
        auth_routes,
        "_get_google_config",
        lambda: (
            "client-id",
            "client-secret",
            "https://chessguru.ai/api/auth/google/callback",
            "https://chessguru.ai",
        ),
    )
    result = await auth_routes.google_login(
        make_request(path="/api/auth/google/login"),
        Response(),
        platform="mobile",
        redirect_to="/home",
        flow="redirect",
    )
    assert result.status_code == 302
    assert result.headers["location"].startswith("https://accounts.google.com/")
    assert "oauth_state_nonce=" in result.headers["set-cookie"]


@pytest.mark.asyncio
async def test_callback_rejects_state_before_any_google_request(monkeypatch):
    monkeypatch.setattr(
        auth_routes,
        "_get_google_config",
        lambda: ("client-id", "client-secret", "", "https://chessguru.ai"),
    )

    class ForbiddenClient:
        def __init__(self):
            raise AssertionError("Google must not be called for invalid state")

    monkeypatch.setattr(auth_routes.httpx, "AsyncClient", ForbiddenClient)
    with pytest.raises(HTTPException) as error:
        await auth_routes.google_callback(
            "authorization-code",
            Response(),
            make_request(path="/api/auth/google/callback"),
            state="invalid-state",
            background_tasks=BackgroundTasks(),
        )
    assert error.value.status_code == 400


class FakeGoogleResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


class FakeGoogleClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, *_args, **_kwargs):
        return FakeGoogleResponse({"access_token": "google-access-token"})

    async def get(self, *_args, **_kwargs):
        return FakeGoogleResponse({
            "email": "oauth-player@example.test",
            "name": "OAuth Player",
            "picture": None,
        })


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["web", "mobile"])
async def test_successful_callback_keeps_web_tokenless_and_marks_mobile_sessions(
    auth_db, monkeypatch, platform
):
    monkeypatch.setattr(
        auth_routes,
        "_get_google_config",
        lambda: (
            "client-id",
            "client-secret",
            "https://chessguru.ai/api/auth/google/callback",
            "https://chessguru.ai",
        ),
    )
    monkeypatch.setattr(auth_routes.httpx, "AsyncClient", FakeGoogleClient)
    nonce = f"{platform}-nonce"
    state = auth_routes._encode_oauth_state(
        platform=platform,
        redirect_to="/welcome",
        nonce=nonce,
        secret="client-secret",
    )
    result = await auth_routes.google_callback(
        "authorization-code",
        Response(),
        make_request(oauth_nonce=nonce, path="/api/auth/google/callback"),
        state=state,
        background_tasks=BackgroundTasks(),
    )

    created_session = next(
        document
        for document in auth_db.user_sessions.documents
        if document.get("user_id", "").startswith("user_")
        and document.get("session_token", "").startswith("session_")
    )
    assert created_session["is_mobile"] is (platform == "mobile")
    if platform == "web":
        assert result.headers["location"] == "https://chessguru.ai/welcome?auth=success"
        assert "token=" not in result.headers["location"]
        assert "session_token=" in b"\n".join(value for _, value in result.raw_headers).decode("latin1")
    else:
        assert "chessguru://auth?token=" in result.body.decode("utf-8")


def test_web_auth_response_never_contains_session_token():
    payload = auth_routes._web_auth_payload({"user_id": "web-user"})
    assert payload == {"user": {"user_id": "web-user"}}
    assert "session_token" not in payload


@pytest.mark.asyncio
async def test_email_registration_returns_cookie_not_json_token(auth_db, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://chessguru.ai")
    response = Response()
    payload = await auth_routes.register(
        auth_routes.RegisterRequest(
            email="new-player@example.test",
            password="correct-horse-battery-staple",
            name="New Player",
        ),
        response,
    )
    assert set(payload) == {"user"}
    assert "session_token" not in payload
    assert "session_token=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_email_login_returns_cookie_not_json_token(auth_db, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://chessguru.ai")
    auth_db.users.documents.append({
        "user_id": "password-user",
        "email": "password@example.test",
        "name": "Password User",
        "password_hash": auth_routes.pwd_context.hash("strong-password"),
    })
    response = Response()
    payload = await auth_routes.login(
        auth_routes.LoginRequest(email="password@example.test", password="strong-password"),
        response,
    )
    assert set(payload) == {"user"}
    assert "session_token" not in payload
    assert "session_token=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]


def test_web_cookie_is_secure_in_production_and_usable_on_localhost(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://chessguru.ai")
    assert auth_routes._web_session_cookie_secure() is True
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    assert auth_routes._web_session_cookie_secure() is False


@pytest.mark.asyncio
async def test_demo_login_is_closed_when_dev_mode_is_off(auth_db):
    with pytest.raises(HTTPException) as error:
        await auth_routes.demo_login(auth_routes.DemoLoginRequest(email="real-user@example.test"))
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_native_logout_revokes_only_an_explicit_mobile_session(auth_db):
    response = Response()
    result = await auth_routes.logout(
        make_request(bearer="mobile-token", path="/api/auth/logout"),
        response,
    )
    assert result == {"message": "Logged out successfully"}
    assert not any(
        document.get("session_token") == "mobile-token"
        for document in auth_db.user_sessions.documents
    )
    assert any(
        document.get("session_token") == "web-token"
        for document in auth_db.user_sessions.documents
    )

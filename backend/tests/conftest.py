"""Shared pytest fixtures for backend tests"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://self-learning-coach.preview.emergentagent.com')


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def authenticated_session():
    """Session with dev login authentication"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Authenticate via dev login
    res = session.get(f"{BASE_URL}/api/auth/dev-login")
    if res.status_code != 200:
        pytest.skip("Dev login failed - skipping authenticated tests")
    
    return session

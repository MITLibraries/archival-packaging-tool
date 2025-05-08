import json

import pytest


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("WORKSPACE", "test")
    monkeypatch.setenv("SENTRY_DSN", "https://1234567890@00000.ingest.sentry.io/123456")
    monkeypatch.setenv("CHALLENGE_SECRET", "test-secret")


@pytest.fixture
def valid_event():
    """Valid event payload for an HTTP invocation."""
    return {
        "body": json.dumps(
            {"action": "ping", "challenge_secret": "test-secret", "verbose": True}
        ),
        "requestContext": {"http": {"method": "POST"}},
    }


@pytest.fixture
def valid_event_direct():
    """Valid event payload for a direct (non HTTP) invocation."""
    return {"action": "ping", "challenge_secret": "test-secret", "verbose": True}


@pytest.fixture
def invalid_event():
    return {
        "body": json.dumps(
            {"action": "unknown_action", "challenge_secret": "test-secret"}
        ),
        "requestContext": {"http": {"method": "POST"}},
    }


@pytest.fixture
def invalid_secret_event():
    return {
        "body": json.dumps({"action": "ping", "challenge_secret": "wrong-secret"}),
        "requestContext": {"http": {"method": "POST"}},
    }


@pytest.fixture
def malformed_event():
    return {"body": "...", "requestContext": {"http": {"method": "POST"}}}

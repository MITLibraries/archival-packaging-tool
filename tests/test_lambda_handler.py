# ruff: noqa: S105

import json
from http import HTTPStatus
from unittest.mock import patch

import pytest

from apt.lambda_handler import (
    InputPayload,
    generate_error_response,
    generate_result_response,
    lambda_handler,
    parse_payload,
    ping,
    validate_secret,
)


class TestLambdaHandler:
    def test_lambda_handler_ping(self, valid_event):
        """Test lambda_handler with a valid HTTP event."""
        response = lambda_handler(valid_event, {})
        assert response["statusCode"] == HTTPStatus.OK
        body = json.loads(response["body"])
        assert body["response"] == "pong"

    def test_lambda_handler_direct_event(self, valid_event_direct):
        """Test lambda_handler with a direct (non HTTP) event."""
        response = lambda_handler(valid_event_direct, {})
        assert response["statusCode"] == HTTPStatus.OK
        body = json.loads(response["body"])
        assert body["response"] == "pong"

    def test_lambda_handler_invalid_action(self, invalid_event):
        response = lambda_handler(invalid_event, {})
        assert response["statusCode"] == HTTPStatus.BAD_REQUEST
        body = json.loads(response["body"])
        assert "action not recognized" in body["error"]

    def test_lambda_handler_invalid_secret(self, invalid_secret_event):
        response = lambda_handler(invalid_secret_event, {})
        assert response["statusCode"] == HTTPStatus.UNAUTHORIZED
        body = json.loads(response["body"])
        assert "Challenge secret missing or mismatch" in body["error"]

    def test_lambda_handler_malformed_event(self, malformed_event):
        response = lambda_handler(malformed_event, {})
        assert response["statusCode"] == HTTPStatus.BAD_REQUEST
        body = json.loads(response["body"])
        assert "Expecting value" in body["error"]

    def test_lambda_handler_unhandled_exception(self, valid_event):
        with patch("apt.lambda_handler.ping", side_effect=Exception("Test error")):
            response = lambda_handler(valid_event, {})
            assert response["statusCode"] == HTTPStatus.INTERNAL_SERVER_ERROR
            body = json.loads(response["body"])
            assert body["error"] == "Test error"

    def test_parse_payload_valid(self, valid_event):
        payload = parse_payload(valid_event)
        assert isinstance(payload, InputPayload)
        assert payload.action == "ping"
        assert payload.challenge_secret == "test-secret"
        assert payload.verbose is True

    def test_parse_payload_direct(self, valid_event_direct):
        payload = parse_payload(valid_event_direct)
        assert isinstance(payload, InputPayload)
        assert payload.action == "ping"
        assert payload.challenge_secret == "test-secret"
        assert payload.verbose is True

    def test_parse_payload_invalid(self):
        with pytest.raises(ValueError, match="Invalid input payload"):
            parse_payload({"body": json.dumps({"not_action": "value"})})

    def test_validate_secret_valid(self, monkeypatch):
        monkeypatch.setenv("CHALLENGE_SECRET", "valid-secret")
        validate_secret("valid-secret")  # Should not raise an exception

    def test_validate_secret_invalid(self, monkeypatch):
        monkeypatch.setenv("CHALLENGE_SECRET", "valid-secret")
        with pytest.raises(RuntimeError, match="Challenge secret missing or mismatch"):
            validate_secret("invalid-secret")

    def test_validate_secret_none(self, monkeypatch):
        monkeypatch.setenv("CHALLENGE_SECRET", "valid-secret")
        with pytest.raises(RuntimeError, match="Challenge secret missing or mismatch"):
            validate_secret(None)

    def test_generate_error_response(self):
        error_details = {"detail": "test detail"}
        response = generate_error_response(
            "Test error", error_details, HTTPStatus.BAD_REQUEST
        )
        assert response["statusCode"] == HTTPStatus.BAD_REQUEST
        assert response["headers"]["Content-Type"] == "application/json"
        assert response["isBase64Encoded"] is False
        body = json.loads(response["body"])
        assert body["error"] == "Test error"
        assert body["error_details"] == error_details

    def test_generate_result_response(self):
        data = {"key": "value"}
        response = generate_result_response(data)
        assert response["statusCode"] == HTTPStatus.OK
        assert response["statusDescription"] == "200 OK"
        assert response["headers"]["Content-Type"] == "application/json"
        assert response["isBase64Encoded"] is False
        body = json.loads(response["body"])
        assert body == data

    def test_ping(self):
        response = ping()
        assert response["statusCode"] == HTTPStatus.OK
        body = json.loads(response["body"])
        assert body["response"] == "pong"

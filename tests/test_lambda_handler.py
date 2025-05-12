# ruff: noqa: S105, S106, SLF001

import json
from http import HTTPStatus
from unittest.mock import patch

import pytest
from jsonschema import ValidationError

from apt.lambda_handler import (
    BagitZipHandler,
    InputPayload,
    PingHandler,
    lambda_handler,
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
        assert "Action not recognized" in body["error"]

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
        with patch(
            "apt.lambda_handler.PingHandler.handle", side_effect=Exception("Test error")
        ):
            response = lambda_handler(valid_event, {})
            assert response["statusCode"] == HTTPStatus.INTERNAL_SERVER_ERROR
            body = json.loads(response["body"])
            assert body["error"] == "Test error"


class TestLambdaProcessor:
    def test_process_event_success(self, lambda_processor, valid_event):
        response = lambda_processor.process_event(valid_event, {})
        assert response["statusCode"] == HTTPStatus.OK
        body = json.loads(response["body"])
        assert body["response"] == "pong"

    def test_parse_payload_valid(self, lambda_processor, valid_event):
        payload = lambda_processor._parse_payload(valid_event)
        assert isinstance(payload, InputPayload)
        assert payload.action == "ping"
        assert payload.challenge_secret == "test-secret"
        assert payload.verbose is True

    def test_parse_payload_direct(self, lambda_processor, valid_event_direct):
        payload = lambda_processor._parse_payload(valid_event_direct)
        assert isinstance(payload, InputPayload)
        assert payload.action == "ping"
        assert payload.challenge_secret == "test-secret"
        assert payload.verbose is True

    def test_parse_payload_invalid(self, lambda_processor):
        with pytest.raises(ValueError, match="Invalid input payload"):
            lambda_processor._parse_payload({"body": json.dumps({"not_action": "value"})})

    def test_validate_secret_valid(self, lambda_processor, monkeypatch):
        monkeypatch.setenv("CHALLENGE_SECRET", "valid-secret")
        lambda_processor.config.CHALLENGE_SECRET = "valid-secret"
        lambda_processor._validate_secret("valid-secret")  # Should not raise an exception

    def test_validate_secret_invalid(self, lambda_processor, monkeypatch):
        monkeypatch.setenv("CHALLENGE_SECRET", "valid-secret")
        lambda_processor.config.CHALLENGE_SECRET = "valid-secret"
        with pytest.raises(RuntimeError, match="Challenge secret missing or mismatch"):
            lambda_processor._validate_secret("invalid-secret")

    def test_validate_secret_none(self, lambda_processor, monkeypatch):
        monkeypatch.setenv("CHALLENGE_SECRET", "valid-secret")
        lambda_processor.config.CHALLENGE_SECRET = "valid-secret"
        with pytest.raises(RuntimeError, match="Challenge secret missing or mismatch"):
            lambda_processor._validate_secret(None)

    def test_get_handler_ping(self, lambda_processor):
        handler = lambda_processor.get_handler("ping")
        assert isinstance(handler, PingHandler)

    def test_get_handler_create_bagit_zip(self, lambda_processor):
        handler = lambda_processor.get_handler("create-bagit-zip")
        assert isinstance(handler, BagitZipHandler)

    def test_get_handler_invalid(self, lambda_processor):
        with pytest.raises(ValueError, match="Action not recognized"):
            lambda_processor.get_handler("invalid-action")

    def test_generate_http_error_response(self, lambda_processor):
        error_details = {"detail": "test detail"}
        response = lambda_processor._generate_http_error_response(
            "Test error", error_details, HTTPStatus.BAD_REQUEST
        )
        assert response["statusCode"] == HTTPStatus.BAD_REQUEST
        assert response["headers"]["Content-Type"] == "application/json"
        assert response["isBase64Encoded"] is False
        body = json.loads(response["body"])
        assert body["error"] == "Test error"
        assert body["error_details"] == error_details

    def test_generate_http_success_response(self, lambda_processor):
        data = {"key": "value"}
        response = lambda_processor._generate_http_success_response(data)
        assert response["statusCode"] == HTTPStatus.OK
        assert response["statusDescription"] == "200 OK"
        assert response["headers"]["Content-Type"] == "application/json"
        assert response["isBase64Encoded"] is False
        body = json.loads(response["body"])
        assert body == data


class TestHandlers:
    def test_ping_handler(self, valid_input_payload):
        handler = PingHandler()
        result = handler.handle(valid_input_payload)
        assert result == {"response": "pong"}

    def test_bagit_zip_handler_success(self, valid_input_payload):
        handler = BagitZipHandler()

        valid_input_payload.input_files = [{"uri": "test.txt", "filepath": "test.text"}]
        valid_input_payload.output_zip_s3_uri = "s3://bucket/output.zip"
        valid_input_payload.compress_zip = True

        expected_result = {"status": "success"}
        with patch(
            "apt.bagit_archive.BagitArchive.process", return_value=expected_result
        ):
            result = handler.handle(valid_input_payload)
            assert result == expected_result

    def test_bagit_zip_handler_error_missing_parameter(self, valid_input_payload):
        handler = BagitZipHandler()

        valid_input_payload.input_files = [{"uri": "test.txt", "filepath": "test.text"}]
        valid_input_payload.output_zip_s3_uri = None  # missing parameter here
        valid_input_payload.compress_zip = True

        with pytest.raises(
            ValidationError, match="'output_zip_s3_uri' is a required property"
        ):
            handler.handle(valid_input_payload)


class TestInputPayload:
    def test_to_dict_filters_none_values(self):
        payload = InputPayload(
            action="ping",
            challenge_secret="secret",
            verbose=True,
            metadata=None,
            input_files=None,
        )
        result = payload.to_dict()
        assert "metadata" not in result
        assert "input_files" not in result
        assert result["action"] == "ping"
        assert result["challenge_secret"] == "secret"
        assert result["verbose"] is True

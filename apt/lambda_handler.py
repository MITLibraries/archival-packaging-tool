import json
import logging
from dataclasses import dataclass
from http import HTTPStatus

from apt.config import Config, configure_logger, configure_sentry

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

CONFIG = Config()


@dataclass
class InputPayload:
    action: str
    challenge_secret: str
    verbose: bool = False


def lambda_handler(event: dict, _context: dict) -> dict:
    """AWS Lambda entrypoint."""
    CONFIG.check_required_env_vars()
    configure_sentry()

    # parse payload
    try:
        payload = parse_payload(event)
    except ValueError as exc:
        logger.error(exc)  # noqa: TRY400
        return generate_error_response(str(exc), http_status_code=HTTPStatus.BAD_REQUEST)

    configure_logger(logging.getLogger(), verbose=payload.verbose)
    logger.debug(json.dumps(event))

    # check challenge secret
    try:
        validate_secret(payload.challenge_secret)
    except RuntimeError as exc:
        logger.error(exc)  # noqa: TRY400
        return generate_error_response(str(exc), http_status_code=HTTPStatus.UNAUTHORIZED)

    # perform requested action
    try:
        if payload.action == "ping":
            return ping()
        return generate_error_response(
            f"action not recognized: '{payload.action}'",
            http_status_code=HTTPStatus.BAD_REQUEST,
        )
    except Exception as exc:
        logger.exception("Unhandled exception")
        return generate_error_response(
            str(exc),
            http_status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )


def parse_payload(event: dict) -> InputPayload:
    """Parse input payload, raising an exception if invalid.

    This lambda will usually be invoked by an HTTP request to an ALB, resulting in an
    'event' payload as outlined here: https://docs.aws.amazon.com/apigateway/latest/
    developerguide/http-api-develop-integrations-lambda.html.  This function attempts to
    identify what format the event is in before parsing.
    """
    body = json.loads(event["body"]) if "requestContext" in event else event

    try:
        return InputPayload(
            **body,
        )
    except Exception as exc:
        message = f"Invalid input payload: {exc}"
        logger.error(message)  # noqa: TRY400
        raise ValueError(message) from exc


def validate_secret(challenge_secret: str | None) -> None:
    """Check that secret passed with lambda invocation matches secret env var."""
    if not challenge_secret or challenge_secret.strip() != CONFIG.CHALLENGE_SECRET:
        raise RuntimeError("Challenge secret missing or mismatch.")


def generate_error_response(
    error: str,
    error_details: dict | None = None,
    http_status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
) -> dict:
    """Produce a response object suitable for HTTP responses.

    See more: https://docs.aws.amazon.com/apigateway/latest/developerguide/
    http-api-develop-integrations-lambda.html
    """
    return {
        "statusCode": http_status_code,
        "headers": {"Content-Type": "application/json"},
        "isBase64Encoded": False,
        "body": json.dumps(
            {
                "error": error,
                "error_details": error_details,
            }
        ),
    }


def generate_result_response(response: dict) -> dict:
    """Produce a response object suitable for HTTP responses.

    See more: https://docs.aws.amazon.com/apigateway/latest/developerguide/
    http-api-develop-integrations-lambda.html
    """
    return {
        "statusCode": HTTPStatus.OK,
        "statusDescription": "200 OK",
        "headers": {"Content-Type": "application/json"},
        "isBase64Encoded": False,
        "body": json.dumps(response),
    }


def ping() -> dict:
    """Return simple 'pong' response."""
    return generate_result_response({"response": "pong"})

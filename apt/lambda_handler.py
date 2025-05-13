import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from http import HTTPStatus

from jsonschema import ValidationError, validate

from apt.bagit_archive import BagitArchive
from apt.config import Config, configure_logger, configure_sentry

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

CONFIG = Config()


@dataclass
class InputPayload:
    action: str
    challenge_secret: str
    verbose: bool = False

    metadata: dict | None = None
    input_files: list[dict] | None = None
    checksums_to_generate: list[str] | None = None
    output_zip_s3_uri: str | None = None
    compress_zip: bool | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


class RequestHandler(ABC):
    @abstractmethod
    def handle(self, payload: InputPayload) -> dict:
        """Process the request and return a response."""
        ...


class PingHandler(RequestHandler):
    """Handle ping requests."""

    def handle(self, _payload: InputPayload) -> dict:
        return {"response": "pong"}


class BagitZipHandler(RequestHandler):
    """Handle requests to create a Bagit zip file."""

    def handle(self, payload: InputPayload) -> dict:
        # validate payload against a JSONSchema
        with open("apt/schemas/request_schema.json") as f:
            schema = json.load(f)
        validate(instance=payload.to_dict(), schema=schema)

        if payload.metadata:
            bagit_archive = BagitArchive(bag_metadata=payload.metadata)
        else:
            bagit_archive = BagitArchive()

        return bagit_archive.process(
            input_files=payload.input_files,  # type: ignore[arg-type]
            output_zip_uri=payload.output_zip_s3_uri,  # type: ignore[arg-type]
            checksums=payload.checksums_to_generate,
            compress_zip=payload.compress_zip,  # type: ignore[arg-type]
        )


class LambdaProcessor:
    def __init__(self) -> None:
        self.config = CONFIG

    def process_event(self, event: dict, _context: dict) -> dict:
        self.config.check_required_env_vars()
        configure_sentry()

        try:
            payload = self._parse_payload(event)
        except (ValueError, ValidationError) as exc:
            logger.error(exc)  # noqa: TRY400
            return self._generate_http_error_response(
                str(exc), http_status_code=HTTPStatus.BAD_REQUEST
            )

        configure_logger(logging.getLogger(), verbose=payload.verbose)
        logger.debug(json.dumps(event))

        try:
            self._validate_secret(payload.challenge_secret)
        except RuntimeError as exc:
            logger.error(exc)  # noqa: TRY400
            return self._generate_http_error_response(
                str(exc), http_status_code=HTTPStatus.UNAUTHORIZED
            )

        try:
            handler = self.get_handler(payload.action)
            result = handler.handle(payload)
            return self._generate_http_success_response(result)
        except (ValueError, ValidationError) as exc:
            return self._generate_http_error_response(
                str(exc),
                http_status_code=HTTPStatus.BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("Unhandled exception")
            return self._generate_http_error_response(
                str(exc),
                http_status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _parse_payload(self, event: dict) -> InputPayload:
        """Parse input payload, raising an exception if invalid."""
        body = json.loads(event["body"]) if "requestContext" in event else event

        try:
            input_payload = InputPayload(**body)
        except Exception as exc:
            message = f"Invalid input payload: {exc}"
            logger.error(message)  # noqa: TRY400
            raise ValueError(message) from exc

        return input_payload

    def _validate_secret(self, challenge_secret: str | None) -> None:
        """Check that secret passed with lambda invocation matches secret env var."""
        if (
            not challenge_secret
            or challenge_secret.strip() != self.config.CHALLENGE_SECRET
        ):
            raise RuntimeError("Challenge secret missing or mismatch.")

    def get_handler(self, action: str) -> RequestHandler:
        if action == "ping":
            return PingHandler()
        if action == "create-bagit-zip":
            return BagitZipHandler()
        raise ValueError(f"Action not recognized: '{action}'")

    @staticmethod
    def _generate_http_error_response(
        error: str,
        error_details: dict | None = None,
        http_status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
    ) -> dict:
        """Produce an error HTTP response object.

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

    @staticmethod
    def _generate_http_success_response(response: dict) -> dict:
        """Produce a success HTTP response object.

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


def lambda_handler(event: dict, context: dict) -> dict:
    """AWS Lambda entrypoint."""
    return LambdaProcessor().process_event(event, context)

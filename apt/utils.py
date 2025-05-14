import logging
import re
import shutil
from pathlib import Path

import boto3
from boto3.s3.transfer import TransferConfig

logger = logging.getLogger(__name__)

S3_PATTERN = r"s3://([^/]+)/(.+)"


def stream_file_transfer(
    source_uri: str | Path,
    target_uri: str | Path,
    max_concurrency: int = 10,
    chunk_size: int = 100 * 1024 * 1024,  # 100MB
) -> str:
    """Stream file from source to target without loading entire file into memory.

    Works with both local paths and remote URIs (e.g., s3://).

    Args:
        source_uri: Source URI or path to read from
        target_uri: Target URI or path to write to
        max_concurrency: Maximum number of concurrent threads for S3 transfers
        chunk_size: Size of chunks for transfers in bytes
    """
    source_uri = str(source_uri)
    target_uri = str(target_uri)

    logger.debug(f"Streaming file from '{source_uri}' to '{target_uri}'")

    s3_client = boto3.client("s3")
    transfer_config = TransferConfig(
        multipart_threshold=chunk_size,
        max_concurrency=max_concurrency,
        multipart_chunksize=chunk_size,
        use_threads=True,
    )

    # S3-to-Local
    if re.match(S3_PATTERN, source_uri) and not re.match(S3_PATTERN, target_uri):
        source_bucket, source_key = parse_s3_uri(source_uri)
        # create local directory if not present
        Path(target_uri).parent.mkdir(parents=True, exist_ok=True)
        s3_client.download_file(
            Bucket=source_bucket,
            Key=source_key,
            Filename=target_uri,
            Config=transfer_config,
        )

    # Local-to-S3
    elif not re.match(S3_PATTERN, source_uri) and re.match(S3_PATTERN, target_uri):
        target_bucket, target_key = parse_s3_uri(target_uri)
        s3_client.upload_file(
            Filename=source_uri,
            Bucket=target_bucket,
            Key=target_key,
            Config=transfer_config,
        )

    # Local-to-Local
    elif not re.match(S3_PATTERN, source_uri) and not re.match(S3_PATTERN, target_uri):
        Path(target_uri).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_uri, target_uri)

    # S3-to-S3
    else:
        src_bucket, src_key = parse_s3_uri(source_uri)
        target_bucket, target_key = parse_s3_uri(target_uri)
        s3 = boto3.resource("s3")
        s3.meta.client.copy(
            {"Bucket": src_bucket, "Key": src_key},
            target_bucket,
            target_key,
            Config=transfer_config,
        )

    logger.debug(f"Transfer completed from {source_uri} to {target_uri}")
    return target_uri


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    match = re.match(S3_PATTERN, s3_uri)
    if not match:
        raise ValueError(f"Error parsing bucket and key from S3 URI: '{s3_uri}'")
    bucket, key = match.groups()
    return bucket, key

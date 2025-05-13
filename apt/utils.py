import logging
from pathlib import Path

from smart_open import open  # type: ignore[import] # noqa: A004

logger = logging.getLogger(__name__)

# size in megabytes (x * 1024 * 1024 = megabytes)
DEFAULT_CHUNK_SIZE = 50 * 1024 * 1024


def stream_file_transfer(
    source_uri: str | Path,
    target_uri: str | Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Stream file from source to target without loading entire file into memory.

    Works with both local paths and remote URIs (e.g., s3://).

    Args:
        source_uri: Source URI or path to read from
        target_uri: Target URI or path to write to
        chunk_size: Size of chunks to read/write in bytes
    """
    source_uri = str(source_uri)
    target_uri = str(target_uri)

    logger.debug(f"Streaming file from '{source_uri}' to '{target_uri}'")

    # ensure parent directory exists for local target paths
    if not target_uri.startswith("s3://"):
        target_path = Path(target_uri)
        target_path.parent.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    with open(source_uri, "rb") as source_file, open(target_uri, "wb") as target_file:
        while True:
            chunk = source_file.read(chunk_size)
            if not chunk:
                break
            target_file.write(chunk)
            total_bytes += len(chunk)

    return target_uri

import logging
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, ClassVar

import bagit  # type: ignore[import]

from apt.config import Config
from apt.utils import stream_file_transfer

logger = logging.getLogger(__name__)

CONFIG = Config()


class BagitArchive:
    """Class for creating a Bagit archive files."""

    DEFAULT_CHECKSUMS: ClassVar[list[str]] = [
        "md5",
        "sha256",
    ]

    def __init__(
        self,
        bag_metadata: dict | None = None,
    ):
        self.bag_metadata = bag_metadata or {"Contact-Name": "Default Contact"}

        self.bag = None
        self.bag_path: Path | None = None

    def download_file(self, source_uri: str, target_path: str | Path) -> Path:
        """Download a file from source URI to target path.

        Args:
            source_uri: Source URI (local path or s3://bucket/key)
            target_path: Path where to save the file
        """
        target_path = Path(target_path)
        stream_file_transfer(source_uri, target_path)
        return target_path

    def download_files(self, input_files: list[dict], bag_dir: Path) -> list[Path]:
        """Download files from source URIs to temporary bag location.

        Args:
            input_files: List of dicts with 'uri' and 'filepath'
            bag_dir: Root directory of Bag
        """
        logger.info(f"Downloading {len(input_files)} files to {bag_dir}")
        bag_dir.mkdir(parents=True, exist_ok=True)

        downloaded_files = []
        for input_file in input_files:
            uri = input_file["uri"]
            filepath = input_file["filepath"]
            bag_filepath = bag_dir / filepath

            self.download_file(uri, bag_filepath)
            downloaded_files.append(bag_filepath)

        return downloaded_files

    def create_bag(self, bag_dir: Path, checksums: list[str] | None = None) -> bagit.Bag:
        """Create a BagIt bag from a directory of files.

        Args:
            bag_dir: Directory containing files to bag (should have a data/ subfolder)
            checksums: List of checksum algorithms to use
        """
        if not checksums:
            checksums = self.DEFAULT_CHECKSUMS

        logger.info(f"Creating bag with checksums: {checksums}")
        bag = bagit.make_bag(bag_dir, self.bag_metadata, checksums=checksums)
        self.bag = bag
        self.bag_path = bag_dir
        return bag

    def validate_checksums(
        self, input_files: list[dict[str, Any]], bag: bagit.Bag
    ) -> None:
        """Validate checksums specified in input files against those in the bag manifest.

        Args:
            input_files: List of input file objects with optional checksums
            bag: Bag object to validate against

        Raises:
            ValueError: If a checksum doesn't match
        """
        for file_obj in input_files:
            if "checksums" not in file_obj:
                continue

            filepath = f"data/{file_obj['filepath']}"

            for algorithm, expected_value in file_obj["checksums"].items():
                if algorithm not in bag.algorithms:
                    logger.warning(
                        f"Checksum algorithm {algorithm} for {filepath} "
                        "not calculated as part of Bag creation."
                    )
                    continue

                # Get the actual checksum from the bag
                actual_value = bag.entries[filepath][algorithm]

                if actual_value != expected_value:
                    msg = (
                        f"Checksum mismatch for {filepath}: "
                        f"expected {expected_value}, got {actual_value}"
                    )
                    raise ValueError(msg)

        logger.info("All specified checksums validated successfully")

    def create_zip(self, output_path: str | Path, *, compress: bool = True) -> Path:
        """Create a zip file from the Bag at the specified local path.

        Args:
            output_path: Path where to save the zip file (local only)
            compress: Whether to compress the zip file

        Returns:
            Path to the created zip file
        """
        if not self.bag:
            msg = "No bag created yet, call create_bag first"
            raise ValueError(msg)

        output_path = Path(output_path)
        logger.info(f"Creating zip file at {output_path}, compress={compress}")
        bag_path = Path(self.bag.path)
        compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED

        # Create zip directly on disk
        with zipfile.ZipFile(output_path, "w", compression=compression) as zf:
            for file_path in bag_path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(bag_path)
                    zf.write(file_path, arcname)

        return output_path

    def upload_file(self, local_path: str | Path, remote_uri: str) -> str:
        """Upload a file to a remote location.

        Args:
            local_path: Path to the local file
            remote_uri: URI where to upload the file (e.g., s3://bucket/key)

        Returns:
            Remote URI where the file was uploaded
        """
        local_path = Path(local_path)
        logger.info(f"Uploading Bagit zip file to '{remote_uri}'")
        stream_file_transfer(local_path, remote_uri)
        return remote_uri

    def process(
        self,
        input_files: list[dict],
        output_zip_uri: str,
        checksums: list[str] | None = None,
        *,
        compress_zip: bool = True,
    ) -> dict[str, Any]:
        """Create a new Bagit archive zip file and save to the specified URI.

        Args:
            input_files: List of dicts with 'uri', 'filepath', and optional 'checksums'
            output_zip_uri: URI where to save the final zip file (local path or s3://bucket/key)
            checksums: List of checksum algorithms to use
            compress_zip: Whether to compress the zip file
        """
        start_time = time.perf_counter()
        result: dict = {
            "success": False,
            "error": None,
            "elapsed": 0,
            "bag": {"entries": {}},
        }

        try:
            with tempfile.TemporaryDirectory() as temp_bag_dir:
                temp_dir_path = Path(temp_bag_dir)

                # download input files
                self.download_files(input_files, temp_dir_path)

                # create Bag
                bag = self.create_bag(temp_dir_path, checksums=checksums)

                # validate any checksums passed with input files after Bag creation
                self.validate_checksums(input_files, bag)

                # create local Bag zip file
                local_zip_path = Path(temp_bag_dir) / "bag.zip"
                self.create_zip(local_zip_path, compress=compress_zip)

                # upload Bag zip file to target location
                self.upload_file(local_zip_path, output_zip_uri)

                # prepare results
                result["success"] = True
                result["bag"]["entries"] = bag.entries

        except Exception as e:
            logger.exception("Error creating Bag zip file.")
            result["error"] = str(e)

        result["elapsed"] = time.perf_counter() - start_time
        logger.debug(f"Bag created, elapsed: {result['elapsed']}")
        return result

import shutil
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import bagit
import pytest

from apt.bagit_archive import BagitArchive


class TestBagitArchive:
    @pytest.fixture
    def sample_file_path(self, tmp_path):
        """Return path to sample file fixture."""
        source_path = Path(__file__).parent / "fixtures" / "sample.txt"
        target_path = tmp_path / "sample.txt"
        target_path.write_text(source_path.read_text())
        return target_path

    @pytest.fixture
    def input_files(self, sample_file_path):
        """Create a list of input files for testing."""
        return [
            {
                "uri": str(sample_file_path),
                "filepath": "documents/sample.txt",
                "checksums": {
                    "md5": "a5e8cf45ba8f5f6df3823df3d0e452fa",
                    "sha256": "e71709bc3a8a2a9c602bcd8a35eefd56b3a4a38a10a06a75",
                },
            }
        ]

    def test_init_defaults(self):
        ba = BagitArchive()
        assert ba.bag is None
        assert ba.bag_path is None

    def test_init_custom_metadata(self):
        metadata = {"Contact-Name": "Test User", "Organization": "Test Org"}
        ba = BagitArchive(bag_metadata=metadata)
        assert ba.bag_metadata == metadata

    def test_download_file(self, tmp_path, sample_file_path):
        ba = BagitArchive()
        target_path = tmp_path / "target.txt"

        with patch("apt.bagit_archive.stream_file_transfer") as mock_transfer:
            ba.download_file(str(sample_file_path), target_path)
            mock_transfer.assert_called_once_with(str(sample_file_path), target_path)

    def test_download_files(self, tmp_path, input_files):
        ba = BagitArchive()

        with patch("apt.bagit_archive.BagitArchive.download_file") as mock_download:
            mock_download.return_value = Path("/fake/path")
            result = ba.download_files(input_files, tmp_path)

            # Verify the method created the right paths
            mock_download.assert_called_once_with(
                input_files[0]["uri"], tmp_path / input_files[0]["filepath"]
            )

            assert len(result) == 1
            assert isinstance(result[0], Path)

    def test_create_bag(self, tmp_path):
        ba = BagitArchive(bag_metadata={"Source-Organization": "Test Org"})

        # create a directory with un-bagged contents
        bag_path = tmp_path
        shutil.copy("tests/fixtures/sample.txt", bag_path)

        # create a bag from that directory
        result = ba.create_bag(bag_path)

        assert isinstance(result, bagit.Bag)
        assert result.path == str(bag_path)
        assert "data/sample.txt" in result.entries
        assert (bag_path / "data/sample.txt").exists()

    def test_validate_checksums_success(self):
        ba = BagitArchive()
        mock_bag = MagicMock(spec=bagit.Bag)
        mock_bag.algorithms = ["md5", "sha256"]
        mock_bag.entries = {"data/file.txt": {"md5": "abc123", "sha256": "def456"}}

        input_files = [
            {"filepath": "file.txt", "checksums": {"md5": "abc123", "sha256": "def456"}}
        ]

        ba.validate_checksums(input_files, mock_bag)

    def test_validate_checksums_mismatch(self):
        ba = BagitArchive()
        mock_bag = MagicMock(spec=bagit.Bag)
        mock_bag.algorithms = ["md5", "sha256"]
        mock_bag.entries = {"data/file.txt": {"md5": "abc123", "sha256": "def456"}}

        input_files = [
            {
                "filepath": "file.txt",
                "checksums": {"md5": "abc123", "sha256": "wrong_checksum"},
            }
        ]

        with pytest.raises(ValueError, match="Checksum mismatch for data/file.txt"):
            ba.validate_checksums(input_files, mock_bag)

    def test_create_zip(self, tmp_path):
        ba = BagitArchive()
        bag = bagit.Bag("tests/fixtures/bags/hello-world-bag")
        ba.bag_path = bag.path
        ba.bag = bag

        zip_path = tmp_path / "output.zip"
        result = ba.create_zip(zip_path)

        assert result == zip_path
        assert zip_path.exists()

        with zipfile.ZipFile(zip_path) as zf:
            assert set(zf.namelist()) == {
                "bagit.txt",
                "bag-info.txt",
                "tagmanifest-sha256.txt",
                "manifest-sha256.txt",
                "data/hello.txt",
            }

    def test_create_zip_no_bag(self):
        ba = BagitArchive()
        with pytest.raises(ValueError, match="No bag created yet"):
            ba.create_zip("output.zip")

    def test_upload_file(self):
        ba = BagitArchive()
        test_file = Path("tests/fixtures/bags/hello-world-bag.zip")
        target_uri = "s3://bucket/hello-world-bag.zip"
        with patch("apt.bagit_archive.stream_file_transfer") as mock_transfer:
            result = ba.upload_file(test_file, target_uri)
            mock_transfer.assert_called_once_with(test_file, target_uri)
            assert result == target_uri

    def test_process_success(self, tmp_path):
        ba = BagitArchive(bag_metadata={"Source-Organization": "Test Org"})
        bag = bagit.Bag("tests/fixtures/bags/hello-world-bag")

        with patch.multiple(
            "apt.bagit_archive.BagitArchive",
            download_files=MagicMock(return_value=[]),
            create_bag=MagicMock(return_value=bag),
            validate_checksums=MagicMock(),
            create_zip=MagicMock(return_value=tmp_path / "bag.zip"),
            upload_file=MagicMock(return_value="s3://bucket/bag.zip"),
        ):
            result = ba.process(
                [{"uri": "s3://input-bucket/hello.txt", "filepath": "hello.txt"}],
                "s3://bucket/bag.zip",
            )

            assert result["success"] is True
            assert "error" in result
            assert result["error"] is None
            assert "elapsed" in result
            assert result["bag"]["entries"] == bag.entries

    def test_process_error(self):
        ba = BagitArchive()

        with patch.object(
            BagitArchive, "download_files", side_effect=Exception("Test error")
        ):
            result = ba.process(
                [{"uri": "s3://input-bucket/file.txt", "filepath": "file.txt"}],
                "s3://bucket/bag.zip",
            )

            assert result["success"] is False
            assert result["error"] == "Test error"
            assert "elapsed" in result

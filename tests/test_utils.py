# ruff: noqa: S108

from unittest.mock import MagicMock, patch

import pytest

from apt.utils import parse_s3_uri, stream_file_transfer


class TestStreamFileTransfer:
    @patch("boto3.client")
    def test_s3_to_local_transfer(self, mock_boto_client):
        mock_s3_client = MagicMock()
        mock_boto_client.return_value = mock_s3_client
        source_uri = "s3://test-bucket/test-key"
        target_uri = "/tmp/local-file"

        result = stream_file_transfer(source_uri, target_uri)

        mock_boto_client.assert_called_once_with("s3")
        mock_s3_client.download_file.assert_called_once()
        assert mock_s3_client.download_file.call_args[1]["Bucket"] == "test-bucket"
        assert mock_s3_client.download_file.call_args[1]["Key"] == "test-key"
        assert mock_s3_client.download_file.call_args[1]["Filename"] == target_uri
        assert result == target_uri

    @patch("boto3.client")
    def test_local_to_s3_transfer(self, mock_boto_client):
        mock_s3_client = MagicMock()
        mock_boto_client.return_value = mock_s3_client
        source_uri = "/tmp/local-file"
        target_uri = "s3://test-bucket/test-key"

        result = stream_file_transfer(source_uri, target_uri)

        mock_boto_client.assert_called_once_with("s3")
        mock_s3_client.upload_file.assert_called_once()
        assert mock_s3_client.upload_file.call_args[1]["Filename"] == source_uri
        assert mock_s3_client.upload_file.call_args[1]["Bucket"] == "test-bucket"
        assert mock_s3_client.upload_file.call_args[1]["Key"] == "test-key"
        assert result == target_uri

    @patch("shutil.copyfile")
    def test_local_to_local_transfer(self, mock_copyfile):
        source_uri = "/tmp/source-file"
        target_uri = "/tmp/target-file"

        with patch("pathlib.Path.mkdir"):
            result = stream_file_transfer(source_uri, target_uri)

        mock_copyfile.assert_called_once_with(source_uri, target_uri)
        assert result == target_uri

    @patch("boto3.resource")
    def test_s3_to_s3_transfer(self, mock_boto_resource):
        mock_s3 = MagicMock()
        mock_boto_resource.return_value = mock_s3
        source_uri = "s3://source-bucket/source-key"
        target_uri = "s3://target-bucket/target-key"

        result = stream_file_transfer(source_uri, target_uri)

        mock_boto_resource.assert_called_once_with("s3")
        mock_s3.meta.client.copy.assert_called_once()
        copy_args = mock_s3.meta.client.copy.call_args[0]
        assert copy_args[0] == {"Bucket": "source-bucket", "Key": "source-key"}
        assert copy_args[1] == "target-bucket"
        assert copy_args[2] == "target-key"
        assert result == target_uri


class TestParseS3Uri:
    def test_parse_valid_s3_uri(self):
        bucket, key = parse_s3_uri("s3://test-bucket/test-key")
        assert bucket == "test-bucket"
        assert key == "test-key"

    def test_parse_invalid_s3_uri(self):
        with pytest.raises(ValueError, match="Error parsing bucket and key from S3 URI"):
            parse_s3_uri("not-an-s3-uri")

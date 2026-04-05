import tempfile
import unittest
from pathlib import Path

from dbt_vertex_agent.storage import (
    build_gcs_object_path,
    download_bytes,
    download_text,
    normalize_bucket_uri,
    parse_gcs_uri,
    upload_file,
)


class NormalizeBucketUriTests(unittest.TestCase):
    def test_normalize_bucket_uri_removes_trailing_slash(self) -> None:
        self.assertEqual(normalize_bucket_uri("gs://bucket-name/"), "gs://bucket-name")


class BuildGcsObjectPathTests(unittest.TestCase):
    def test_build_gcs_object_path_uses_bucket_and_object_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "project.zip"
            file_path.write_text("payload")

            object_path = build_gcs_object_path("gs://bucket-name", "submissions/run-123/project.zip")

            self.assertEqual(object_path, "gs://bucket-name/submissions/run-123/project.zip")


class ParseGcsUriTests(unittest.TestCase):
    def test_parse_gcs_uri_splits_bucket_and_object_key(self) -> None:
        self.assertEqual(
            parse_gcs_uri("gs://bucket-name/submissions/run-123/project.zip"),
            ("bucket-name", "submissions/run-123/project.zip"),
        )


class UploadFileTests(unittest.TestCase):
    def test_upload_file_uses_storage_client_bucket_and_blob(self) -> None:
        class FakeBlob:
            def __init__(self) -> None:
                self.uploaded_from = None

            def upload_from_filename(self, filename: str) -> None:
                self.uploaded_from = filename

        class FakeBucket:
            def __init__(self) -> None:
                self.last_blob_name = None
                self.blob_instance = FakeBlob()

            def blob(self, name: str) -> FakeBlob:
                self.last_blob_name = name
                return self.blob_instance

        class FakeClient:
            def __init__(self) -> None:
                self.bucket_name = None
                self.bucket_instance = FakeBucket()

            def bucket(self, name: str) -> FakeBucket:
                self.bucket_name = name
                return self.bucket_instance

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "project.zip"
            file_path.write_text("payload")
            client = FakeClient()

            uploaded_uri = upload_file(
                "gs://bucket-name",
                file_path,
                "submissions/run-123/project.zip",
                client=client,
            )

            self.assertEqual(uploaded_uri, "gs://bucket-name/submissions/run-123/project.zip")
            self.assertEqual(client.bucket_name, "bucket-name")
            self.assertEqual(client.bucket_instance.last_blob_name, "submissions/run-123/project.zip")
            self.assertEqual(client.bucket_instance.blob_instance.uploaded_from, str(file_path))


class DownloadTests(unittest.TestCase):
    def test_download_text_and_bytes_read_from_blob(self) -> None:
        class FakeBlob:
            def download_as_bytes(self) -> bytes:
                return b"payload"

        class FakeBucket:
            def blob(self, _name: str) -> FakeBlob:
                return FakeBlob()

        class FakeClient:
            def bucket(self, _name: str) -> FakeBucket:
                return FakeBucket()

        client = FakeClient()

        self.assertEqual(download_bytes("gs://bucket-name/path/file.txt", client=client), b"payload")
        self.assertEqual(download_text("gs://bucket-name/path/file.txt", client=client), "payload")

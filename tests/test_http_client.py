import tempfile
import unittest
from pathlib import Path

from dbt_vertex_agent.http_client import (
    build_multipart_body,
    normalize_base_url,
    post_review_to_local_service,
)
from dbt_vertex_agent.review_contract import ReviewResult


class NormalizeBaseUrlTests(unittest.TestCase):
    def test_normalize_base_url_removes_trailing_slash(self) -> None:
        self.assertEqual(normalize_base_url("http://127.0.0.1:8000/"), "http://127.0.0.1:8000")


class PostReviewToLocalServiceTests(unittest.TestCase):
    def test_post_review_to_local_service_uses_transport_callback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            project_zip = temp_path / "project.zip"
            manifest = temp_path / "manifest.json"
            project_zip.write_bytes(b"zip-bytes")
            manifest.write_text("{}")

            def fake_transport(_url, _project_path, _manifest_path, _debug_enabled):
                return {
                    "run_id": "run-123",
                    "status": "success",
                    "summary": "No findings detected.",
                    "findings": [],
                    "reviewed_files": [],
                }

            result = post_review_to_local_service(
                "http://127.0.0.1:8000/",
                project_zip,
                manifest,
                transport=fake_transport,
            )

            self.assertIsInstance(result, ReviewResult)
            self.assertEqual(result.run_id, "run-123")

    def test_post_review_to_local_service_passes_debug_flag_to_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            project_zip = temp_path / "project.zip"
            manifest = temp_path / "manifest.json"
            project_zip.write_bytes(b"zip-bytes")
            manifest.write_text("{}")
            captured = {}

            def fake_transport(_url, _project_path, _manifest_path, debug_enabled):
                captured["debug_enabled"] = debug_enabled
                return {
                    "run_id": "run-123",
                    "status": "success",
                    "summary": "No findings detected.",
                    "findings": [],
                    "reviewed_files": [],
                }

            post_review_to_local_service(
                "http://127.0.0.1:8000/",
                project_zip,
                manifest,
                debug_enabled=True,
                transport=fake_transport,
            )

            self.assertTrue(captured["debug_enabled"])


class BuildMultipartBodyTests(unittest.TestCase):
    def test_build_multipart_body_includes_debug_field_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            project_zip = temp_path / "project.zip"
            manifest = temp_path / "manifest.json"
            project_zip.write_bytes(b"zip-bytes")
            manifest.write_text("{}")

            body = build_multipart_body(
                project_zip,
                manifest,
                "test-boundary",
                debug_enabled=True,
            )

            self.assertIn(b'name="debug"', body)
            self.assertIn(b"true", body)

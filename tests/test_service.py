import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from dbt_vertex_agent.review_contract import ReviewResult
from dbt_vertex_agent.service import handle_health_request, handle_review_http_request
from dbt_vertex_agent.service_handlers import handle_review_upload


class HandleReviewUploadTests(unittest.TestCase):
    def test_handle_review_upload_returns_review_result_for_valid_artifacts(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/orders.sql", "select * from orders\n")

        manifest_bytes = json.dumps(
            {
                "nodes": {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "Orders model",
                    }
                }
            }
        ).encode()

        result = handle_review_upload(
            project_filename="project.zip",
            project_bytes=project_bytes.getvalue(),
            manifest_filename="manifest.json",
            manifest_bytes=manifest_bytes,
        )

        self.assertIsInstance(result, ReviewResult)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.reviewed_files, ["models/orders.sql"])

    def test_handle_review_upload_returns_warning_for_missing_manifest_target(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/customers.sql", "select * from customers\n")

        manifest_bytes = json.dumps(
            {
                "nodes": {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "Orders model",
                    }
                }
            }
        ).encode()

        result = handle_review_upload(
            project_filename="project.zip",
            project_bytes=project_bytes.getvalue(),
            manifest_filename="manifest.json",
            manifest_bytes=manifest_bytes,
        )

        self.assertEqual(result.status, "warning")
        self.assertEqual(result.findings[0].rule, "missing-reviewed-file")

    def test_handle_review_upload_uses_model_callback_when_provided(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/orders.sql", "select * from orders\n")

        manifest_bytes = json.dumps(
            {
                "nodes": {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "Orders model",
                    }
                }
            }
        ).encode()

        captured = {}

        def fake_model(context):
            captured["context"] = context
            return {
                "run_id": "run-123",
                "status": "success",
                "summary": "No findings detected.",
                "findings": [],
                "reviewed_files": ["models/orders.sql"],
            }

        result = handle_review_upload(
            project_filename="project.zip",
            project_bytes=project_bytes.getvalue(),
            manifest_filename="manifest.json",
            manifest_bytes=manifest_bytes,
            model_callback=fake_model,
        )

        self.assertEqual(result.run_id, "run-123")
        self.assertEqual(
            captured["context"].source_snippets,
            {"models/orders.sql": "select * from orders\n"},
        )
        self.assertIn("global/base.md", captured["context"].selected_guidance)

    def test_handle_review_upload_reports_missing_model_description(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/orders.sql", "select * from orders\n")

        manifest_bytes = json.dumps(
            {
                "nodes": {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "",
                    }
                }
            }
        ).encode()

        result = handle_review_upload(
            project_filename="project.zip",
            project_bytes=project_bytes.getvalue(),
            manifest_filename="manifest.json",
            manifest_bytes=manifest_bytes,
        )

        self.assertEqual(result.status, "warning")
        self.assertEqual(result.findings[0].rule, "missing-description")

    def test_handle_review_upload_reports_missing_column_description(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/orders.sql", "select * from orders\n")

        manifest_bytes = json.dumps(
            {
                "nodes": {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "Orders model",
                        "columns": {
                            "order_id": {
                                "name": "order_id",
                                "description": "",
                            }
                        },
                    }
                }
            }
        ).encode()

        result = handle_review_upload(
            project_filename="project.zip",
            project_bytes=project_bytes.getvalue(),
            manifest_filename="manifest.json",
            manifest_bytes=manifest_bytes,
        )

        self.assertEqual(result.status, "warning")
        self.assertEqual(result.findings[0].rule, "missing-column-description")

    def test_handle_review_upload_excludes_non_dbt_seed_content_from_model_context(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/orders.sql", "select * from orders\n")
            archive.writestr("seeds/raw_orders.csv", "id,amount\n1,10\n")

        manifest_bytes = json.dumps(
            {
                "nodes": {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "Orders model",
                    },
                    "seed.project.raw_orders": {
                        "resource_type": "seed",
                        "original_file_path": "seeds/raw_orders.csv",
                    },
                }
            }
        ).encode()

        captured = {}

        def fake_model(context):
            captured["context"] = context
            return {}

        handle_review_upload(
            project_filename="project.zip",
            project_bytes=project_bytes.getvalue(),
            manifest_filename="manifest.json",
            manifest_bytes=manifest_bytes,
            model_callback=fake_model,
        )

        self.assertEqual(
            captured["context"].source_snippets,
            {"models/orders.sql": "select * from orders\n"},
        )

    def test_handle_review_upload_writes_debug_artifacts_when_enabled(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/orders.sql", "select * from orders\n")

        manifest_bytes = json.dumps(
            {
                "nodes": {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "Orders model",
                    }
                }
            }
        ).encode()

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = handle_review_upload(
                project_filename="project.zip",
                project_bytes=project_bytes.getvalue(),
                manifest_filename="manifest.json",
                manifest_bytes=manifest_bytes,
                debug_enabled=True,
                output_root=Path(tmp_dir),
            )

            run_dir = Path(tmp_dir) / result.run_id
            self.assertTrue((run_dir / "context.json").exists())
            self.assertTrue((run_dir / "prompt.txt").exists())
            self.assertIn("Guidance: global/base.md", (run_dir / "prompt.txt").read_text())
            self.assertIn("models/orders.sql", (run_dir / "prompt.txt").read_text())

    def test_handle_review_upload_rejects_invalid_zip_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "ZIP"):
            handle_review_upload(
                project_filename="project.zip",
                project_bytes=b"not-a-zip",
                manifest_filename="manifest.json",
                manifest_bytes=b'{"nodes": {}}',
            )


class ServiceHttpTests(unittest.TestCase):
    def test_health_endpoint_returns_ok(self) -> None:
        status_code, payload = handle_health_request()

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "ok")

    def test_review_http_request_returns_json_payload_for_valid_uploads(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/orders.sql", "select * from orders\n")

        manifest_bytes = json.dumps(
            {
                "nodes": {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "Orders model",
                    }
                }
            }
        ).encode()

        status_code, payload = handle_review_http_request(
            project_filename="project.zip",
            project_bytes=project_bytes.getvalue(),
            manifest_filename="manifest.json",
            manifest_bytes=manifest_bytes,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["reviewed_files"], ["models/orders.sql"])

    def test_review_http_request_uses_model_callback_when_provided(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/orders.sql", "select * from orders\n")

        manifest_bytes = json.dumps(
            {
                "nodes": {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "Orders model",
                    }
                }
            }
        ).encode()

        def fake_model(_context):
            return {
                "run_id": "run-llm",
                "status": "success",
                "summary": "No findings detected.",
                "findings": [],
                "reviewed_files": ["models/orders.sql"],
            }

        status_code, payload = handle_review_http_request(
            project_filename="project.zip",
            project_bytes=project_bytes.getvalue(),
            manifest_filename="manifest.json",
            manifest_bytes=manifest_bytes,
            model_callback=fake_model,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["run_id"], "run-llm")

    def test_review_http_request_writes_debug_artifacts_when_requested(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/orders.sql", "select * from orders\n")

        manifest_bytes = json.dumps(
            {
                "nodes": {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "Orders model",
                    }
                }
            }
        ).encode()

        with tempfile.TemporaryDirectory() as tmp_dir:
            status_code, payload = handle_review_http_request(
                project_filename="project.zip",
                project_bytes=project_bytes.getvalue(),
                manifest_filename="manifest.json",
                manifest_bytes=manifest_bytes,
                debug_enabled=True,
                output_root=Path(tmp_dir),
            )

            self.assertEqual(status_code, 200)
            run_dir = Path(tmp_dir) / payload["run_id"]
            self.assertTrue((run_dir / "context.json").exists())
            self.assertTrue((run_dir / "prompt.txt").exists())

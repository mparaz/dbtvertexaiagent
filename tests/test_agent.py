import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from dbt_vertex_agent.agent import review_submission
from dbt_vertex_agent.models import SubmissionArtifacts


class ReviewSubmissionTests(unittest.TestCase):
    def test_review_submission_returns_targets_derived_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            project_zip = temp_path / "project.zip"
            manifest_path = temp_path / "manifest.json"

            manifest_path.write_text(
                json.dumps(
                    {
                        "nodes": {
                            "model.project.orders": {
                                "resource_type": "model",
                                "original_file_path": "models/orders.sql",
                                "description": "Orders model",
                            }
                        }
                    }
                )
            )

            with zipfile.ZipFile(project_zip, "w") as archive:
                archive.writestr("models/orders.sql", "select * from orders\n")

            submission = SubmissionArtifacts(
                run_id="run-123",
                project_uri=str(project_zip),
                manifest_uri=str(manifest_path),
            )

            result = review_submission(submission)

            self.assertEqual(result.status, "success")
            self.assertEqual(result.reviewed_files, ["models/orders.sql"])

    def test_review_submission_returns_structured_error_for_invalid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            project_zip = temp_path / "project.zip"
            manifest_path = temp_path / "manifest.json"
            manifest_path.write_text("{invalid json")

            with zipfile.ZipFile(project_zip, "w") as archive:
                archive.writestr("models/orders.sql", "select * from orders\n")

            submission = SubmissionArtifacts(
                run_id="run-123",
                project_uri=str(project_zip),
                manifest_uri=str(manifest_path),
            )

            result = review_submission(submission)

            self.assertEqual(result.status, "error")
            self.assertEqual(result.summary, "Manifest could not be parsed.")

    def test_review_submission_reports_missing_manifest_referenced_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            project_zip = temp_path / "project.zip"
            manifest_path = temp_path / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "nodes": {
                            "model.project.orders": {
                                "resource_type": "model",
                                "original_file_path": "models/orders.sql",
                                "description": "Orders model",
                            }
                        }
                    }
                )
            )

            with zipfile.ZipFile(project_zip, "w") as archive:
                archive.writestr("models/customers.sql", "select * from customers\n")

            submission = SubmissionArtifacts(
                run_id="run-123",
                project_uri=str(project_zip),
                manifest_uri=str(manifest_path),
            )

            result = review_submission(submission)

            self.assertEqual(result.status, "warning")
            self.assertEqual(result.findings[0].rule, "missing-reviewed-file")

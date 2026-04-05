import unittest

from dbt_vertex_agent.review_contract import Finding, ReviewResult


class ReviewResultTests(unittest.TestCase):
    def test_review_result_defaults_to_success_with_empty_findings(self) -> None:
        result = ReviewResult(run_id="run-123", findings=[])

        self.assertEqual(result.status, "success")
        self.assertEqual(result.summary, "No findings detected.")

    def test_review_result_can_capture_failure_summary(self) -> None:
        result = ReviewResult(
            run_id="run-123",
            status="error",
            summary="Manifest could not be parsed.",
            findings=[],
        )

        self.assertEqual(result.status, "error")
        self.assertEqual(result.summary, "Manifest could not be parsed.")


class FindingTests(unittest.TestCase):
    def test_finding_captures_severity_rule_and_file_path(self) -> None:
        finding = Finding(
            severity="warning",
            rule="missing-description",
            message="Model is missing a description.",
            file_path="models/orders.sql",
        )

        self.assertEqual(finding.file_path, "models/orders.sql")


class ReviewResultValidationTests(unittest.TestCase):
    def test_from_model_payload_builds_review_result(self) -> None:
        payload = {
            "run_id": "run-123",
            "status": "warning",
            "summary": "1 finding detected.",
            "findings": [
                {
                    "severity": "warning",
                    "rule": "missing-description",
                    "message": "Model is missing a description.",
                    "file_path": "models/orders.sql",
                }
            ],
            "reviewed_files": ["models/orders.sql"],
        }

        result = ReviewResult.from_model_payload(payload)

        self.assertEqual(result.run_id, "run-123")
        self.assertEqual(result.findings[0].rule, "missing-description")

    def test_from_model_payload_rejects_missing_required_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "summary"):
            ReviewResult.from_model_payload({"run_id": "run-123"})

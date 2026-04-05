import json
import tempfile
import unittest
from pathlib import Path

from dbt_vertex_agent.output import write_debug_artifacts, write_review_artifacts
from dbt_vertex_agent.rendering import render_markdown, render_terminal_summary
from dbt_vertex_agent.review_contract import Finding, ReviewResult
from dbt_vertex_agent.service_contract import DebugArtifacts, ReducedReviewContext


class RenderTerminalSummaryTests(unittest.TestCase):
    def test_render_terminal_summary_lists_findings_and_reviewed_files(self) -> None:
        result = ReviewResult(
            run_id="run-123",
            findings=[
                Finding(
                    severity="warning",
                    rule="missing-description",
                    message="Model is missing a description.",
                    file_path="models/orders.sql",
                )
            ],
            reviewed_files=["models/orders.sql"],
            summary="1 finding detected.",
        )

        summary = render_terminal_summary(result)

        self.assertIn("Run: run-123", summary)
        self.assertIn("1 finding detected.", summary)
        self.assertIn("warning missing-description models/orders.sql", summary)


class RenderMarkdownTests(unittest.TestCase):
    def test_render_markdown_outputs_readable_sections(self) -> None:
        result = ReviewResult(
            run_id="run-123",
            findings=[],
            reviewed_files=["models/orders.sql"],
        )

        markdown = render_markdown(result)

        self.assertIn("# dbt Review Report", markdown)
        self.assertIn("## Reviewed Files", markdown)
        self.assertIn("- `models/orders.sql`", markdown)


class WriteReviewArtifactsTests(unittest.TestCase):
    def test_write_review_artifacts_persists_json_and_markdown(self) -> None:
        result = ReviewResult(
            run_id="run-123",
            findings=[],
            reviewed_files=["models/orders.sql"],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_paths = write_review_artifacts(result, Path(tmp_dir))

            self.assertTrue(output_paths.json_path.exists())
            self.assertTrue(output_paths.markdown_path.exists())
            self.assertEqual(
                json.loads(output_paths.json_path.read_text())["run_id"],
                "run-123",
            )

    def test_write_debug_artifacts_persists_context_and_prompt(self) -> None:
        debug_artifacts = DebugArtifacts(
            context=ReducedReviewContext(
                run_id="run-123",
                reviewed_files=["models/orders.sql"],
                manifest_summary={"target_count": 1},
                source_snippets={"models/orders.sql": "select * from orders"},
            ),
            prompt="Review this dbt model.",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_paths = write_debug_artifacts(
                run_id="run-123",
                debug_artifacts=debug_artifacts,
                output_root=Path(tmp_dir),
            )

            self.assertTrue(output_paths.context_path.exists())
            self.assertTrue(output_paths.prompt_path.exists())
            self.assertEqual(
                json.loads(output_paths.context_path.read_text())["run_id"],
                "run-123",
            )
            self.assertEqual(
                output_paths.prompt_path.read_text(),
                "Review this dbt model.",
            )

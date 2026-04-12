import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from dbt_vertex_agent.agent import (
    extract_text_from_runner_events,
    get_manifest_summary,
    read_dbt_file,
)


def _make_zip(tmp_dir: Path, members: dict[str, str]) -> Path:
    """Write a zip archive containing the given filename -> content mapping."""
    archive_path = tmp_dir / "project.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return archive_path


def _make_manifest(tmp_dir: Path, nodes: dict) -> Path:
    manifest_path = tmp_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"nodes": nodes, "sources": {}}))
    return manifest_path


class GetManifestSummaryTests(unittest.TestCase):
    def test_returns_file_list_from_manifest_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = _make_manifest(
                Path(tmp_dir),
                {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "Orders model",
                        "config": {"materialized": "table"},
                        "tags": ["finance"],
                    }
                },
            )

            summary = get_manifest_summary(str(manifest_path))

            self.assertEqual(summary["total_files"], 1)
            files = summary["files"]
            assert isinstance(files, list)
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0]["path"], "models/orders.sql")
            self.assertEqual(files[0]["node_type"], "model")
            self.assertEqual(files[0]["materialized"], "table")
            self.assertEqual(files[0]["tags"], ["finance"])
            self.assertTrue(files[0]["has_description"])

    def test_returns_empty_file_list_for_empty_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = Path(tmp_dir) / "manifest.json"
            manifest_path.write_text('{"nodes": {}, "sources": {}}')

            summary = get_manifest_summary(str(manifest_path))

            self.assertEqual(summary["total_files"], 0)
            self.assertEqual(summary["files"], [])

    def test_deduplicates_paths_across_original_and_patch_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = Path(tmp_dir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "nodes": {
                            "model.project.orders": {
                                "resource_type": "model",
                                "original_file_path": "models/orders.sql",
                                "patch_path": "models/orders.sql",
                            }
                        },
                        "sources": {},
                    }
                )
            )

            summary = get_manifest_summary(str(manifest_path))

            self.assertEqual(summary["total_files"], 1)

    def test_marks_missing_description_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = _make_manifest(
                Path(tmp_dir),
                {
                    "model.project.orders": {
                        "resource_type": "model",
                        "original_file_path": "models/orders.sql",
                        "description": "",
                    }
                },
            )

            summary = get_manifest_summary(str(manifest_path))

            self.assertFalse(summary["files"][0]["has_description"])  # type: ignore[index]


class ReadDbtFileTests(unittest.TestCase):
    def test_returns_file_content_from_local_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_path = _make_zip(Path(tmp_dir), {"models/orders.sql": "select * from orders\n"})

            content = read_dbt_file(str(archive_path), "models/orders.sql")

            self.assertEqual(content, "select * from orders\n")

    def test_returns_error_for_unsupported_file_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_path = _make_zip(Path(tmp_dir), {"seeds/raw.csv": "id,name\n1,foo\n"})

            result = read_dbt_file(str(archive_path), "seeds/raw.csv")

            self.assertIn("not supported", result)

    def test_returns_error_for_missing_file_in_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_path = _make_zip(Path(tmp_dir), {"models/orders.sql": "select 1\n"})

            result = read_dbt_file(str(archive_path), "models/customers.sql")

            self.assertIn("not found", result)

    def test_truncates_content_at_4000_chars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            long_content = "x" * 5000
            archive_path = _make_zip(Path(tmp_dir), {"models/big.sql": long_content})

            result = read_dbt_file(str(archive_path), "models/big.sql")

            self.assertLessEqual(len(result), 4030)  # 4000 + truncation marker
            self.assertIn("-- truncated --", result)

    def test_returns_yaml_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_path = _make_zip(
                Path(tmp_dir),
                {"models/schema.yml": "version: 2\nmodels:\n  - name: orders\n"},
            )

            content = read_dbt_file(str(archive_path), "models/schema.yml")

            self.assertIn("version: 2", content)

    def test_returns_error_for_invalid_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_zip = Path(tmp_dir) / "bad.zip"
            bad_zip.write_bytes(b"not a zip file")

            result = read_dbt_file(str(bad_zip), "models/orders.sql")

            self.assertIn("not a valid ZIP", result)


class ExtractTextFromRunnerEventsTests(unittest.TestCase):
    def _make_event(self, text: str) -> MagicMock:
        """Build a mock ADK Event with the given text in content.parts[0].text."""
        part = MagicMock()
        part.text = text
        content = MagicMock()
        content.parts = [part]
        event = MagicMock()
        event.content = content
        return event

    def test_returns_text_from_last_event(self) -> None:
        events = [
            self._make_event("intermediate tool call"),
            self._make_event('{"run_id": "run-1", "status": "success"}'),
        ]

        text = extract_text_from_runner_events(events)

        self.assertIn("run-1", text)

    def test_returns_text_from_only_event(self) -> None:
        events = [self._make_event("hello")]

        text = extract_text_from_runner_events(events)

        self.assertEqual(text, "hello")

    def test_skips_events_without_content(self) -> None:
        empty_event = MagicMock()
        empty_event.content = None
        real_event = self._make_event("found it")

        text = extract_text_from_runner_events([empty_event, real_event])

        self.assertEqual(text, "found it")

    def test_raises_when_no_text_found(self) -> None:
        empty_event = MagicMock()
        empty_event.content = None

        with self.assertRaises(ValueError):
            extract_text_from_runner_events([empty_event])

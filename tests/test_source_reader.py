import io
import unittest
import zipfile
from pathlib import Path

from dbt_vertex_agent.source_reader import extract_source_snippets_from_bytes


class ExtractSourceSnippetsFromBytesTests(unittest.TestCase):
    def test_extracts_text_for_reviewable_dbt_files(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/orders.sql", "select * from orders\n")
            archive.writestr("models/schema.yml", "version: 2\n")

        snippets = extract_source_snippets_from_bytes(
            project_bytes.getvalue(),
            [Path("models/orders.sql"), Path("models/schema.yml")],
        )

        self.assertEqual(
            snippets,
            {
                "models/orders.sql": "select * from orders\n",
                "models/schema.yml": "version: 2\n",
            },
        )

    def test_skips_non_reviewable_extensions(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("seeds/raw_orders.csv", "id,amount\n1,10\n")
            archive.writestr("models/orders.sql", "select * from orders\n")

        snippets = extract_source_snippets_from_bytes(
            project_bytes.getvalue(),
            [Path("seeds/raw_orders.csv"), Path("models/orders.sql")],
        )

        self.assertEqual(snippets, {"models/orders.sql": "select * from orders\n"})

    def test_truncates_large_source_files(self) -> None:
        project_bytes = io.BytesIO()
        with zipfile.ZipFile(project_bytes, "w") as archive:
            archive.writestr("models/orders.sql", "a" * 5000)

        snippets = extract_source_snippets_from_bytes(
            project_bytes.getvalue(),
            [Path("models/orders.sql")],
            max_chars_per_file=100,
        )

        self.assertEqual(len(snippets["models/orders.sql"]), 116)
        self.assertTrue(snippets["models/orders.sql"].endswith("\n-- truncated --"))

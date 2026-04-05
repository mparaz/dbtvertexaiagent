import os
import unittest

from dbt_vertex_agent.config import Config, load_config


class LoadConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_env = os.environ.copy()
        for key in [
            "DBT_VERTEX_PROJECT_ID",
            "DBT_VERTEX_REGION",
            "DBT_VERTEX_STAGING_BUCKET",
            "DBT_VERTEX_OUTPUT_DIR",
        ]:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_load_config_reads_required_environment_variables(self) -> None:
        os.environ["DBT_VERTEX_PROJECT_ID"] = "test-project"
        os.environ["DBT_VERTEX_REGION"] = "us-central1"
        os.environ["DBT_VERTEX_STAGING_BUCKET"] = "gs://bucket-name"

        config = load_config()

        self.assertEqual(
            config,
            Config(
                project_id="test-project",
                region="us-central1",
                staging_bucket="gs://bucket-name",
                output_dir="runs",
            ),
        )

    def test_load_config_raises_for_missing_required_environment_variables(self) -> None:
        with self.assertRaisesRegex(ValueError, "DBT_VERTEX_PROJECT_ID"):
            load_config()

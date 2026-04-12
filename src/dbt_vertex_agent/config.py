import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # GCS and project settings are only required when using the remote Agent
    # Engine path. Local ADK Runner runs do not upload to GCS, so these fields
    # default to empty strings and are validated at use time rather than at
    # config load time.
    project_id: str = ""
    region: str = ""
    staging_bucket: str = ""
    output_dir: str = "runs"
    agent_resource_name: str | None = None


def load_config() -> Config:
    return Config(
        project_id=os.environ.get("DBT_VERTEX_PROJECT_ID", ""),
        region=os.environ.get("DBT_VERTEX_REGION", ""),
        staging_bucket=os.environ.get("DBT_VERTEX_STAGING_BUCKET", ""),
        output_dir=os.environ.get("DBT_VERTEX_OUTPUT_DIR", "runs"),
        agent_resource_name=os.environ.get("DBT_VERTEX_AGENT_RESOURCE_NAME"),
    )

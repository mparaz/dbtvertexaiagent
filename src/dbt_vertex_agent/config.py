import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # These fields represent the external runtime contract for the CLI.
    # Keeping them in one dataclass makes it easy to see which environment
    # variables control the system.
    project_id: str
    region: str
    staging_bucket: str
    output_dir: str = "runs"
    agent_resource_name: str | None = None
    local_service_url: str | None = None


def load_config() -> Config:
    # These are the minimum settings required to upload artifacts into GCP.
    required_keys = [
        "DBT_VERTEX_PROJECT_ID",
        "DBT_VERTEX_REGION",
        "DBT_VERTEX_STAGING_BUCKET",
    ]
    # Collect all missing keys first so the user gets one actionable error
    # instead of a slow series of one-variable-at-a-time failures.
    missing_keys = [key for key in required_keys if not os.environ.get(key)]
    if missing_keys:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_keys)}")

    # Optional settings let the same code work in two modes:
    # - local review only
    # - remote review against a deployed Agent Engine resource
    return Config(
        project_id=os.environ["DBT_VERTEX_PROJECT_ID"],
        region=os.environ["DBT_VERTEX_REGION"],
        staging_bucket=os.environ["DBT_VERTEX_STAGING_BUCKET"],
        output_dir=os.environ.get("DBT_VERTEX_OUTPUT_DIR", "runs"),
        agent_resource_name=os.environ.get("DBT_VERTEX_AGENT_RESOURCE_NAME"),
        local_service_url=os.environ.get("DBT_VERTEX_LOCAL_SERVICE_URL"),
    )

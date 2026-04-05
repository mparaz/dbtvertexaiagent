import os
from pathlib import Path
import sys


# The deployment script lives at the repo root, but the implementation code lives
# under `src/`. We add `src/` to the import path so the script can import the package
# without requiring an installed wheel first.
SRC_DIR = Path(__file__).parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import vertexai
from vertexai import agent_engines

from agent import root_agent


# Deployment configuration is read from environment variables so the same script
# can be reused across projects and environments.
PROJECT_ID = os.environ["DBT_VERTEX_PROJECT_ID"]
LOCATION = os.environ["DBT_VERTEX_REGION"]
STAGING_BUCKET = os.environ["DBT_VERTEX_STAGING_BUCKET"]
DISPLAY_NAME = os.environ.get("DBT_VERTEX_AGENT_DISPLAY_NAME", "dbt-review-agent")


def main() -> None:
    if root_agent is None:
        raise RuntimeError("Root agent could not be constructed. Install google-adk first.")

    # Initialize the Vertex AI SDK with the target project, region, and staging bucket.
    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
        staging_bucket=STAGING_BUCKET,
    )

    # Wrap the ADK root agent in an Agent Engine application object.
    app = agent_engines.AdkApp(
        agent=root_agent,
        enable_tracing=True,
    )

    # Create the remote Agent Engine resource. The requirements list tells Vertex
    # which Python packages to install inside the deployment environment.
    remote_app = agent_engines.create(
        agent_engine=app,
        display_name=DISPLAY_NAME,
        requirements=[
            "google-adk",
            "google-cloud-aiplatform[adk,agent_engines]",
            "google-cloud-storage>=2.16",
        ],
    )
    # The printed resource name can be fed back into the local CLI through
    # `DBT_VERTEX_AGENT_RESOURCE_NAME`.
    print(remote_app.resource_name)


if __name__ == "__main__":
    main()

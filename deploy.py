import os
import sys
from pathlib import Path

# The deployment script lives at the repo root, but the implementation code lives
# under `src/`. We add `src/` to the import path so the script can import the package
# without requiring an installed wheel first.
SRC_DIR = Path(__file__).parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> None:
    import vertexai
    from vertexai import agent_engines

    from agent import root_agent

    if root_agent is None:
        raise RuntimeError("Root agent could not be constructed. Install google-adk first.")

    project_id = os.environ["DBT_VERTEX_PROJECT_ID"]
    location = os.environ["DBT_VERTEX_REGION"]
    staging_bucket = os.environ["DBT_VERTEX_STAGING_BUCKET"]
    display_name = os.environ.get("DBT_VERTEX_AGENT_DISPLAY_NAME", "dbt-review-agent")

    # Initialize the Vertex AI SDK with the target project, region, and staging bucket.
    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=staging_bucket,
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
        display_name=display_name,
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

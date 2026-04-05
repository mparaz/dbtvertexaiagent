from pathlib import Path
import sys


# Agent Engine expects to import a top-level `agent.py` file.
# The actual package code lives under `src/`, so we add that directory to the
# import path before exposing `root_agent`.
SRC_DIR = Path(__file__).parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# `root_agent` is the ADK object that Vertex AI will deploy.
from dbt_vertex_agent.agent import root_agent  # noqa: E402

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ServiceSettings:
    # Keep service config separate from general CLI/GCP config so local HTTP mode
    # can evolve without polluting the rest of the runtime contract.
    host: str = "127.0.0.1"
    port: int = 8000


def load_service_settings() -> ServiceSettings:
    return ServiceSettings(
        host=os.environ.get("DBT_VERTEX_SERVICE_HOST", "127.0.0.1"),
        port=int(os.environ.get("DBT_VERTEX_SERVICE_PORT", "8000")),
    )

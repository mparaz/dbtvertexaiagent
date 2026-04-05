from dataclasses import dataclass


@dataclass(frozen=True)
class RunContext:
    # This is currently a placeholder for future run-level metadata.
    # Keeping the type now gives us a natural place to add timestamps, users,
    # or tracing identifiers later without reshaping function signatures again.
    run_id: str

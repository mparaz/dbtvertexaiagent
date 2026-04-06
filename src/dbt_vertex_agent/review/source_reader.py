import zipfile
from io import BytesIO
from pathlib import Path

REVIEWABLE_SOURCE_SUFFIXES = {".sql", ".yml", ".yaml", ".md"}


def filter_existing_archive_members(project_archive: Path, targets: list[Path]) -> list[str]:
    # Convert `Path` objects to archive-style POSIX names before comparing them
    # with the names stored inside the zip file.
    target_names = {target.as_posix() for target in targets}

    with zipfile.ZipFile(project_archive) as archive:
        return [name for name in archive.namelist() if name in target_names]


def filter_existing_archive_members_from_bytes(
    project_archive_bytes: bytes, targets: list[Path]
) -> list[str]:
    # The deployed path downloads zip bytes from GCS, so we need the same logic
    # as above but without going through a temporary file on disk.
    target_names = {target.as_posix() for target in targets}

    with zipfile.ZipFile(BytesIO(project_archive_bytes)) as archive:
        return [name for name in archive.namelist() if name in target_names]


def list_archive_members_from_bytes(project_archive_bytes: bytes) -> list[str]:
    # Some service paths want to validate zip integrity without filtering yet.
    with zipfile.ZipFile(BytesIO(project_archive_bytes)) as archive:
        return archive.namelist()


def extract_source_snippets_from_bytes(
    project_archive_bytes: bytes,
    targets: list[Path],
    max_chars_per_file: int = 4000,
) -> dict[str, str]:
    # The LLM path only needs human-readable dbt source files, not every archive
    # member. In particular, large CSV seeds would waste context without helping
    # SQL or YAML review.
    target_names = {
        target.as_posix()
        for target in targets
        if target.suffix.lower() in REVIEWABLE_SOURCE_SUFFIXES
    }

    snippets: dict[str, str] = {}
    with zipfile.ZipFile(BytesIO(project_archive_bytes)) as archive:
        for name in archive.namelist():
            if name not in target_names:
                continue

            text = archive.read(name).decode("utf-8", errors="replace")
            if len(text) > max_chars_per_file:
                text = f"{text[:max_chars_per_file]}\n-- truncated --"
            snippets[name] = text

    return snippets

from pathlib import Path


def normalize_bucket_uri(bucket_uri: str) -> str:
    # Accept both `gs://bucket` and `gs://bucket/` inputs and normalize them
    # to one canonical form before building object paths.
    return bucket_uri.rstrip("/")


def build_gcs_object_path(bucket_uri: str, object_key: str) -> str:
    return f"{normalize_bucket_uri(bucket_uri)}/{object_key}"


def parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    # Split a full GCS URI into the bucket name and object key because the
    # Python client library expects those as separate values.
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI, got: {gcs_uri}")

    bucket_and_key = gcs_uri[5:]
    bucket_name, _, object_key = bucket_and_key.partition("/")
    if not bucket_name or not object_key:
        raise ValueError(f"Expected bucket and object key in URI: {gcs_uri}")

    return bucket_name, object_key


def get_storage_client():
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-storage is required for real GCS operations."
        ) from exc

    # Import lazily so unit tests and local code review can run without the
    # Google packages installed.
    return storage.Client()


def upload_file(
    bucket_uri: str,
    source_path: Path,
    destination_blob_name: str,
    client=None,
) -> str:
    storage_client = client or get_storage_client()
    # We only need the bucket name from the bucket URI here; the destination blob
    # name is already passed separately.
    bucket_name, _ = parse_gcs_uri(f"{normalize_bucket_uri(bucket_uri)}/placeholder")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(str(source_path))
    return build_gcs_object_path(bucket_uri, destination_blob_name)


def download_bytes(gcs_uri: str, client=None) -> bytes:
    # Download raw bytes when the caller wants to interpret the payload itself,
    # such as opening a zip file from memory.
    storage_client = client or get_storage_client()
    bucket_name, object_key = parse_gcs_uri(gcs_uri)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(object_key)
    return blob.download_as_bytes()


def download_text(gcs_uri: str, client=None, encoding: str = "utf-8") -> str:
    # Text download is a thin convenience wrapper over the byte download helper.
    return download_bytes(gcs_uri, client=client).decode(encoding)

from os import getenv
from re import fullmatch
from urllib.parse import urlsplit


def connect_chroma():
    private_host = getenv("CHROMA_PRIVATE_HOST", "").strip()
    port = getenv("CHROMA_PORT", "").strip()
    url = getenv("CHROMA_URL", "").strip()
    api_key = getenv("CHROMA_API_KEY", "").strip()
    tenant = getenv("CHROMA_TENANT", "").strip()
    database = getenv("CHROMA_DATABASE", "").strip()
    if not any((private_host, port, url, api_key, tenant, database)):
        return None

    if private_host:
        if url or api_key:
            raise RuntimeError("CHROMA_PRIVATE_HOST cannot be combined with CHROMA_URL or CHROMA_API_KEY.")
        if not fullmatch(r"[a-zA-Z0-9.-]+\.railway\.internal", private_host):
            raise RuntimeError("CHROMA_PRIVATE_HOST must be a Railway private hostname without a scheme or port.")
        port = port or "8000"
        if not fullmatch(r"[0-9]{1,5}", port) or not 1 <= int(port) <= 65535:
            raise RuntimeError("CHROMA_PORT must be an integer between 1 and 65535.")
        url = f"http://{private_host}:{port}"
    elif port:
        raise RuntimeError("CHROMA_PORT requires CHROMA_PRIVATE_HOST.")

    if url:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None:
            raise RuntimeError("CHROMA_URL must be an HTTP(S) URL without credentials.")
        if api_key:
            raise RuntimeError("Use either CHROMA_URL or Chroma Cloud credentials.")
        import chromadb

        return chromadb.HttpClient(
            host=url,
            tenant=tenant or "default_tenant",
            database=database or "default_database",
        )

    if not all((api_key, tenant, database)):
        raise RuntimeError("Chroma Cloud requires CHROMA_API_KEY, CHROMA_TENANT, and CHROMA_DATABASE.")

    import chromadb

    return chromadb.CloudClient(api_key=api_key, tenant=tenant, database=database)

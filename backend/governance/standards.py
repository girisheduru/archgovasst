"""Import approved Word standards into Chroma."""

import argparse
from pathlib import Path

from .agent.documents import MAX_UPLOAD_BYTES
from .standards_store.ingestion import ingest_rules
from .standards_store.source_documents import extract_rules


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents", type=Path, nargs="+")
    args = parser.parse_args()
    rules = []
    try:
        for path in args.documents:
            with path.open("rb") as source:
                payload = source.read(MAX_UPLOAD_BYTES + 1)
            if len(payload) > MAX_UPLOAD_BYTES:
                raise ValueError(f"{path}: source documents must be at most 10 MB.")
            rules.extend(extract_rules(path.name, payload))
        added, updated = ingest_rules(rules)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Added {added} rule versions. Overwritten: {updated}.")

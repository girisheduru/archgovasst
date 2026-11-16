"""Load approved, rule-boundary standards into Chroma."""

import argparse
from pathlib import Path

from .standards_store.ingestion import ingest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rules", type=Path)
    args = parser.parse_args()
    print(f"Added {ingest(args.rules)} rule versions.")

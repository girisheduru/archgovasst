"""Validate, embed, and import rule versions."""

from ..providers.openai import embed_texts
from .catalog import collection_name, standards_client
from .models import Rule


class InvalidImport(ValueError):
    pass


def ingest_rules(rules: list[Rule]) -> tuple[int, int]:
    if not rules:
        raise InvalidImport("Supply at least one rule.")
    keys = []
    seen = set()
    for rule in rules:
        key = f"{rule.id}:{rule.effective_date.isoformat()}"
        if key in seen:
            raise InvalidImport(
                f"Rule version {key} appears more than once in the selected documents. "
                "Include it only once and retry."
            )
        seen.add(key)
        keys.append(key)

    collection = standards_client().get_or_create_collection(
        collection_name(), embedding_function=None, configuration={"hnsw": {"space": "cosine"}}
    )
    documents = [rule.model_dump_json() for rule in rules]
    existing = collection.get(ids=keys, include=[])
    embeddings = embed_texts([f"{rule.quote}\n{rule.evidence_required}" for rule in rules])
    collection.upsert(
        ids=keys,
        documents=documents,
        embeddings=embeddings,
        metadatas=[
            {
                "rule_id": rule.id,
                "standard": rule.standard,
                "effective_date": rule.effective_date.toordinal(),
            }
            for rule in rules
        ],
    )
    updated = len(existing["ids"])
    return len(keys) - updated, updated

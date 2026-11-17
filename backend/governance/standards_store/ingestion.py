"""Validate, embed, and import new rule versions."""

from pathlib import Path

from pydantic import TypeAdapter

from ..providers.openai import embed_texts
from .catalog import collection_name, standards_client
from .models import Rule


def ingest(path: Path) -> int:
    return ingest_rules(parse_rules(path.read_bytes()))


def parse_rules(payload: bytes) -> list[Rule]:
    return TypeAdapter(list[Rule]).validate_json(payload)


def ingest_rules(rules: list[Rule]) -> int:
    keys = [f"{rule.id}:{rule.effective_date.isoformat()}" for rule in rules]
    if not rules or len(set(keys)) != len(keys):
        raise ValueError("Supply at least one rule, with unique rule ID and effective date pairs.")

    collection = standards_client().get_or_create_collection(
        collection_name(), embedding_function=None, configuration={"hnsw": {"space": "cosine"}}
    )
    documents = [rule.model_dump_json() for rule in rules]
    existing = collection.get(ids=keys, include=["documents"])
    stored = dict(zip(existing["ids"], existing["documents"] or [], strict=True))
    for key, document in zip(keys, documents, strict=True):
        if key in stored and Rule.model_validate_json(stored[key]) != Rule.model_validate_json(document):
            raise ValueError(f"Rule {key} already exists with different content. Use a new effective date.")

    indices = [index for index, key in enumerate(keys) if key not in stored]
    if indices:
        embeddings = embed_texts([f"{rules[i].quote}\n{rules[i].evidence_required}" for i in indices])
        collection.add(
            ids=[keys[i] for i in indices],
            documents=[documents[i] for i in indices],
            embeddings=embeddings,
            metadatas=[
                {
                    "rule_id": rules[i].id,
                    "standard": rules[i].standard,
                    "effective_date": rules[i].effective_date.toordinal(),
                }
                for i in indices
            ],
        )
    return len(indices)

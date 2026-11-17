"""Validate, embed, and import rule versions."""

from logging import getLogger

from ..providers.openai import embed_texts
from .catalog import collection_name, standards_client
from .models import Rule

logger = getLogger(__name__)


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

    documents = [rule.model_dump_json() for rule in rules]
    step = "connect to Chroma"
    try:
        client = standards_client()
        step = "open or create the Chroma collection"
        collection = client.get_or_create_collection(
            collection_name(), embedding_function=None, configuration={"hnsw": {"space": "cosine"}}
        )
        step = "look up existing rule versions"
        existing = collection.get(ids=keys, include=[])
        updated = len(existing["ids"])
        step = "generate OpenAI embeddings"
        embeddings = embed_texts([f"{rule.quote}\n{rule.evidence_required}" for rule in rules])
        step = "write rule versions to Chroma"
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
    except Exception as exc:
        underlying = exc.__cause__ or exc.__context__
        error_type = type(exc).__name__
        if underlying is not None:
            error_type = f"{error_type}, underlying {type(underlying).__name__}"
        logger.error("Standards import failed at step '%s' (%s).", step, error_type)
        raise
    return len(keys) - updated, updated

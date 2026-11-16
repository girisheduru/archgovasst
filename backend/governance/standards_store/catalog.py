"""Resolve the approved, effective rule versions for a review."""

from datetime import date
from os import getenv

from .chroma import connect_chroma
from .models import DocumentType, Rule


class StandardsUnavailable(RuntimeError):
    pass


def standards_client():
    client = connect_chroma()
    if client is None:
        raise StandardsUnavailable("Configure a Chroma standards store before starting a review.")
    return client


def collection_name():
    return getenv("CHROMA_STANDARDS_COLLECTION", "governance-standards")


def load_rules(as_of: date, document_type: DocumentType) -> list[dict]:
    try:
        collection = standards_client().get_collection(collection_name(), embedding_function=None)
        rows = collection.get(
            where={"effective_date": {"$lte": as_of.toordinal()}},
            include=["documents"],
        )
        latest: dict[str, Rule] = {}
        for document in rows["documents"] or []:
            rule = Rule.model_validate_json(document)
            previous = latest.get(rule.id)
            if previous is None or previous.effective_date < rule.effective_date:
                latest[rule.id] = rule
    except StandardsUnavailable:
        raise
    except Exception as exc:
        raise StandardsUnavailable("Could not read the approved standards collection.") from exc

    applicable = [rule for rule in latest.values() if document_type in rule.document_types]
    if not applicable:
        raise StandardsUnavailable("No approved standards apply to this document type and date.")
    return [rule.model_dump(mode="json") for rule in sorted(applicable, key=lambda rule: rule.id)]

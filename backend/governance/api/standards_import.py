from hmac import compare_digest
from os import getenv
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from ..agent.documents import MAX_UPLOAD_BYTES, parse_document
from ..standards_store.ingestion import ingest_rules, parse_rules

router = APIRouter(prefix="/api/standards", tags=["Standards"])
bearer = HTTPBearer(auto_error=False)
import_lock = Lock()


def authorize_import(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    expected = getenv("STANDARDS_IMPORT_TOKEN", "").strip()
    if not expected:
        raise HTTPException(503, "Standards uploads are disabled on this backend.")
    if not credentials or not compare_digest(credentials.credentials.encode(), expected.encode()):
        raise HTTPException(401, "Enter a valid standards import token.", headers={"WWW-Authenticate": "Bearer"})


@router.post("/import", dependencies=[Depends(authorize_import)])
def import_standards(
    documents: Annotated[list[UploadFile], File()],
    catalog: Annotated[UploadFile, File()],
):
    if not 1 <= len(documents) <= 10:
        raise HTTPException(422, "Select between 1 and 10 source documents.")

    raw_catalog = catalog.file.read(1024 * 1024 + 1)
    if len(raw_catalog) > 1024 * 1024:
        raise HTTPException(413, "The JSON catalog must be at most 1 MB.")
    try:
        rules = parse_rules(raw_catalog)
    except ValidationError as exc:
        raise HTTPException(422, "The catalog must be a JSON array of approved rules with all required fields.") from exc

    if not 1 <= len(rules) <= 200:
        raise HTTPException(422, "Supply between 1 and 200 catalog rules per import.")

    sources = []
    total_bytes = 0
    for document in documents:
        name = Path(document.filename or "").name
        payload = document.file.read(MAX_UPLOAD_BYTES + 1)
        total_bytes += len(payload)
        if len(payload) > MAX_UPLOAD_BYTES or total_bytes > 2 * MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Source documents must be at most 10 MB each and 20 MB total.")
        try:
            sources.append(" ".join(parse_document(name, payload).values()))
        except Exception as exc:
            raise HTTPException(422, f"Could not extract text from {name}. Use a text-based PDF or Word document.") from exc

    for rule in rules:
        quote = " ".join(rule.quote.split())
        if not quote or not any(quote in source for source in sources):
            raise HTTPException(422, f"The quote for rule {rule.id} was not found in the uploaded documents.")

    try:
        with import_lock:
            added = ingest_rules(rules)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Could not import standards. Check the backend embedding and Chroma settings.") from exc

    return {"added": added, "unchanged": len(rules) - added}

from hmac import compare_digest
from os import getenv
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..agent.documents import MAX_UPLOAD_BYTES
from ..standards_store.ingestion import InvalidImport, ingest_rules
from ..standards_store.source_documents import extract_rules

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
):
    if not 1 <= len(documents) <= 10:
        raise HTTPException(422, "Select between 1 and 10 source documents.")

    rules = []
    total_bytes = 0
    for document in documents:
        name = Path(document.filename or "").name
        payload = document.file.read(MAX_UPLOAD_BYTES + 1)
        total_bytes += len(payload)
        if len(payload) > MAX_UPLOAD_BYTES or total_bytes > 2 * MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Source documents must be at most 10 MB each and 20 MB total.")
        try:
            rules.extend(extract_rules(name, payload))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    if len(rules) > 200:
        raise HTTPException(422, "Supply at most 200 rules per import.")

    try:
        with import_lock:
            added, updated = ingest_rules(rules)
    except InvalidImport as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Could not import standards. Check the backend embedding and Chroma settings.") from exc

    return {"added": added, "updated": updated}

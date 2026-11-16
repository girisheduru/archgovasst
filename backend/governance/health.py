from fastapi import APIRouter, HTTPException, Request, Response


router = APIRouter()


@router.get("/api/health/chroma")
def check_chroma(request: Request, response: Response) -> dict[str, str]:
    """Check whether the configured Chroma database accepts a read."""
    response.headers["Cache-Control"] = "no-store"
    client = request.app.state.chroma
    if client is None:
        return {"status": "disabled"}
    try:
        client.list_collections(limit=1)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Chroma database is unavailable.",
            headers={"Cache-Control": "no-store"},
        ) from None
    return {"status": "connected"}

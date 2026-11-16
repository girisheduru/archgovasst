"""Uvicorn entry point when launched from the repo root or backend directory."""

if __package__:
    from .governance.application import app
else:
    from governance.application import app

__all__ = ["app"]

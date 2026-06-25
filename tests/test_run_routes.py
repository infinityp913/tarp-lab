"""Tests for the /api/pgram/run/* route ordering.

Regression guard: the dynamic "/run/{kind}" route must NOT shadow the static
"/run/cancel" and "/run/status" routes. FastAPI/Starlette match in declaration
order, so if "/run/{kind}" were declared first, "POST /run/cancel" would resolve
to start_run(kind="cancel") and fail with "Unknown run type: cancel".

This avoids fastapi.testclient (which needs httpx) and instead replays Starlette's
own route matching, which is exactly what the ASGI app does per request.
"""
from starlette.routing import Match

from backend.routers import pgram


def _resolve(method: str, path: str):
    """Return the endpoint name the router would dispatch to (first full match wins)."""
    scope = {"type": "http", "method": method, "path": path}
    for route in pgram.router.routes:
        match, _ = route.matches(scope)
        if match is Match.FULL:
            return route.endpoint.__name__
    return None


def test_run_cancel_resolves_to_cancel_handler():
    """POST /run/cancel must dispatch to run_cancel, not start_run."""
    assert _resolve("POST", "/api/pgram/run/cancel") == "run_cancel"


def test_run_status_resolves_to_status_handler():
    """GET /run/status must dispatch to run_status."""
    assert _resolve("GET", "/api/pgram/run/status") == "run_status"


def test_real_kind_resolves_to_start_run():
    """A genuine kind still reaches start_run via the dynamic route."""
    assert _resolve("POST", "/api/pgram/run/both") == "start_run"

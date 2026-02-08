"""HTTP Basic Auth middleware for Starlette."""

from __future__ import annotations

import base64
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Paths that bypass authentication
_PUBLIC_PATHS = frozenset({"/api/v1/health"})


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic Auth: username 'dodo', password is the configured api_key.

    Health endpoint is exempt for monitoring.
    Browser shows native auth dialog (no custom login UI needed).
    """

    def __init__(self, app, api_key: str):
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return _unauthorized()

        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (ValueError, UnicodeDecodeError):
            return _unauthorized()

        # Constant-time comparison to prevent timing attacks
        if username != "dodo" or not secrets.compare_digest(password, self._api_key):
            return _unauthorized()

        return await call_next(request)


def _unauthorized() -> Response:
    return Response(
        content="Unauthorized",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="dodo"'},
    )

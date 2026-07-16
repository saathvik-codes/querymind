"""
Minimal API-key auth + in-process rate limiting for QueryMind.

Scope deliberately kept small for a single hardening pass:
- Auth: one static shared secret via X-API-Key, not a user/JWT system.
- Rate limiting: an in-memory sliding-window counter. This only works
  correctly for a single backend instance/process — if this app is ever
  scaled horizontally (multiple uvicorn workers or replicas), this needs
  to move to a shared store (e.g. Redis) since each process would otherwise
  keep its own independent counters.
"""
import os
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

API_KEY = os.environ.get("API_KEY")

RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "20"))
_WINDOW_SECONDS = 60.0

# client_key -> deque of request timestamps within the current window.
_request_log: dict[str, deque] = defaultdict(deque)


async def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """FastAPI dependency: rejects the request unless X-API-Key matches API_KEY.

    If API_KEY isn't configured at all, auth is left open (useful for pure
    local dev without an .env) but this should always be set in any deployed
    environment — see .env.example / README.
    """
    if not API_KEY:
        return "anonymous"
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")
    return x_api_key


def _client_identity(request: Request, api_key: str) -> str:
    if api_key and api_key != "anonymous":
        return api_key
    client = request.client
    return client.host if client else "unknown"


def enforce_rate_limit(request: Request, api_key: str) -> None:
    """Sliding-window limiter keyed by API key (falls back to client IP when
    auth is disabled). Raises 429 once the caller exceeds RATE_LIMIT_PER_MINUTE
    requests within the trailing 60 seconds."""
    key = _client_identity(request, api_key)
    now = time.monotonic()
    log = _request_log[key]

    while log and now - log[0] > _WINDOW_SECONDS:
        log.popleft()

    if len(log) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded — max {RATE_LIMIT_PER_MINUTE} requests per minute.",
        )

    log.append(now)

from __future__ import annotations

import os
import hashlib
import hmac
import time

SHARED_SECRET = os.environ.get("VYPER_SERVICE_TOKEN", "dev-secret-change-me")

def generate_service_token() -> str:
    """Generate timestamped HMAC token for inter-service auth."""
    timestamp = str(int(time.time()))
    signature = hmac.new(
        SHARED_SECRET.encode(),
        timestamp.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    return f"{timestamp}.{signature}"

def verify_service_token(token: str, max_age_seconds: int = 300) -> bool:
    """Verify HMAC token (max 5 minute age)."""
    try:
        timestamp_str, signature = token.split(".")
        timestamp = int(timestamp_str)
        if abs(time.time() - timestamp) > max_age_seconds:
            return False
        expected = hmac.new(
            SHARED_SECRET.encode(),
            timestamp_str.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        return hmac.compare_digest(signature, expected)
    except (ValueError, AttributeError):
        return False

def auth_middleware_factory(skip_paths=None):
    """Create a FastAPI middleware that validates X-Vyper-Token header.
    Skips health endpoint and optionally other paths."""
    from fastapi import Request, HTTPException
    from starlette.middleware.base import BaseHTTPMiddleware
    
    _skip_paths = skip_paths or {"/health"}
    
    class VyperAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if request.url.path in _skip_paths or request.url.path.startswith("/health"):
                return await call_next(request)
            token = request.headers.get("X-Vyper-Token", "")
            if not verify_service_token(token):
                raise HTTPException(status_code=401, detail="Invalid service token")
            return await call_next(request)
    
    return VyperAuthMiddleware

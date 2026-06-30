from __future__ import annotations

import hmac
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .routers import horses, ingest, sessions
from .routers.live import router as live_router

app = FastAPI(title="EquiSense Lite API")

# Schema lifecycle is managed by Alembic migrations.
# Run `alembic upgrade head` before starting the server (or in CI/deploy pipelines).
# For local dev: `make migrate-upgrade`
# Do NOT add Base.metadata.create_all() or manual ALTER TABLE statements here.

# CORS: allow Netlify production + deploy previews + local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://equisense-lite.netlify.app",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_origin_regex=r"https://.*\.netlify\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Token authentication middleware
# ---------------------------------------------------------------------------


def _tokens_match(provided: str, expected: str) -> bool:
    """Constant-time string comparison to prevent timing-based token leakage."""
    return hmac.compare_digest(provided.encode(), expected.encode())


@app.middleware("http")
async def token_guard(request: Request, call_next) -> Response:
    # Allow CORS preflight requests (they don't include auth headers)
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path

    # Public endpoints (no token required)
    if path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/health"):
        return await call_next(request)

    token = request.headers.get("x-api-token")
    if not token:
        return JSONResponse({"detail": "Missing X-API-Token"}, status_code=401)

    expected = os.getenv("API_TOKEN", "dev-token")
    if not _tokens_match(token, expected):
        return JSONResponse({"detail": "Invalid X-API-Token"}, status_code=401)

    return await call_next(request)


# ---------------------------------------------------------------------------
# Security headers middleware — registered last so it wraps all other
# middleware, including token_guard, and applies to *every* response.
# ---------------------------------------------------------------------------


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(horses.router)
app.include_router(sessions.router)
app.include_router(ingest.router)
app.include_router(live_router)

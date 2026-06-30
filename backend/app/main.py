from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from .routers import horses, ingest, sessions

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


@app.middleware("http")
async def token_guard(request, call_next):
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
    if token != expected:
        return JSONResponse({"detail": "Invalid X-API-Token"}, status_code=401)

    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(horses.router)
app.include_router(sessions.router)
app.include_router(ingest.router)

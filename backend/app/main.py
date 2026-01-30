from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import sessions, ingest, horses
from .db import Base, engine

app = FastAPI(title="EquiSense Lite API")
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.middleware("http")
async def token_guard(request, call_next):
    path = request.url.path
    if path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/health"):
        return await call_next(request)
    token = request.headers.get("x-api-token")
    if not token:
        from starlette.responses import JSONResponse
        return JSONResponse({"detail":"Missing X-API-Token"}, status_code=401)
    return await call_next(request)

@app.get("/health")
def health():
    return {"status":"ok"}

app.include_router(horses.router)
app.include_router(sessions.router)
app.include_router(ingest.router)

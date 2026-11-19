"""
web.api.app — FastAPI Application Entry Point

OpenSource Clipping Studio — Web GUI Backend

Run with:
    uvicorn web.api.app:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import os
import signal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.requests import Request

from scripts.studio_logging import configure_logging, log_event

from .routes import jobs, files, settings
from . import worker
from .logging_middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    log_path = configure_logging(role="api")
    log_event("api.startup.started", component="api", stage="startup")
    print("🚀 OpenSource Clipping Studio — Backend starting...")
    if log_path is not None:
        print(f"Studio diagnostic log: {log_path}", flush=True)
    log_event("api.startup.completed", component="api", stage="startup")
    try:
        yield
    finally:
        log_event("api.shutdown.started", component="api", stage="shutdown")
        try:
            await worker.cancel_all_jobs()
        except BaseException as exc:
            log_event("api.shutdown.failed", component="api", stage="shutdown", level="ERROR", error=exc)
            raise
        else:
            log_event("api.shutdown.completed", component="api", stage="shutdown")
        finally:
            print("👋 Backend shutting down...")


app = FastAPI(
    title="OpenSource Clipping Studio",
    description="AI Auto-Clipper & Teaser Generator — Web GUI API",
    version="1.12.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev servers, GitHub Pages, and ngrok tunnels
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestLoggingMiddleware)

# Routes
app.include_router(jobs.router)
app.include_router(files.router)
app.include_router(settings.router)

# Mount Studio Web GUI static files
studio_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs", "studio"))
if os.path.isdir(studio_dir):
    app.mount("/studio", StaticFiles(directory=studio_dir, html=True), name="studio")


@app.get("/")
async def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(url="/studio/")
    return {
        "name": "OpenSource Clipping Studio",
        "version": "1.13.0",
        "studio": "/studio/",
        "docs": "/docs",
        "health": "/api/health",
        "ready": "/api/ready",
    }


@app.get("/studio")
async def studio_redirect():
    return RedirectResponse(url="/studio/")


@app.post("/api/shutdown")
async def shutdown_server():
    """Trigger graceful shutdown of the FastAPI server."""
    log_event("api.shutdown.requested", component="api", stage="shutdown")
    # Send SIGINT to own process to trigger uvicorn graceful shutdown
    async def _shutdown():
        await asyncio.sleep(0.5)
        os.kill(os.getpid(), signal.SIGINT)
    
    asyncio.create_task(_shutdown())
    return {"status": "shutting down", "message": "Server is stopping..."}

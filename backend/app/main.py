"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger("app")

app = FastAPI(
    title="Freight AI Ops",
    version=__version__,
    description="AI-powered freight forwarding sales & operations assistant.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "freight-ai-ops", "version": __version__, "docs": "/docs"}


@app.on_event("startup")
def on_startup() -> None:
    log.info("app_startup", env=settings.app_env, llm_provider=settings.llm_provider)

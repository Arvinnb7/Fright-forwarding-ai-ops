"""FastAPI application entrypoint."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger("app")


def _startup_security_checks() -> None:
    """Refuse to stay quiet about insecure defaults outside local use."""
    insecure = []
    if settings.secret_key.startswith("change-me"):
        insecure.append("SECRET_KEY is the default value")
    if settings.admin_password == "change-me":
        insecure.append("ADMIN_PASSWORD is the default value")
    if not insecure:
        return
    if settings.app_env == "local":
        log.warning("insecure_defaults_local", issues=insecure)
    else:
        # Loud, unmissable, repeated — this must never reach a shared deployment.
        for issue in insecure:
            log.error("INSECURE_CONFIGURATION", issue=issue, app_env=settings.app_env)


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info(
        "app_startup",
        env=settings.app_env,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
    )
    _startup_security_checks()
    yield
    log.info("app_shutdown")


app = FastAPI(
    title="Freight AI Ops",
    version=__version__,
    description="AI-powered freight forwarding sales & operations assistant.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "Content-Disposition"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler: log the stack with a correlation id, return clean JSON.

    HTTPException and validation errors keep FastAPI's default handling; this
    only catches genuinely unexpected failures so the client never sees a bare
    HTML 500 or a leaked stack trace.
    """
    error_id = uuid.uuid4().hex[:12]
    log.error(
        "unhandled_exception",
        error_id=error_id,
        path=str(request.url.path),
        method=request.method,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error. The incident has been logged.",
            "error_id": error_id,
        },
    )


app.include_router(api_router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "freight-ai-ops", "version": __version__, "docs": "/docs"}

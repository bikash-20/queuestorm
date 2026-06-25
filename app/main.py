"""FastAPI application entrypoint.

Wires:
    * structured logging
    * request-context middleware
    * global exception handlers (domain + stdlib)
    * CORS
    * routers (/health, /sort-ticket)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.endpoints import health as health_router
from app.api.endpoints import tickets as tickets_router
from app.core.config import get_settings
from app.core.exceptions import QueueStormError
from app.core.logging import configure_logging, get_logger
from app.middleware import RequestContextMiddleware

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: D401
    """Eagerly initialize the classifier singleton."""
    from app.services.classifier import get_classifier

    settings = get_settings()
    classifier = get_classifier()
    logger.info(
        "app.startup",
        env=settings.app_env,
        version=__version__,
        classifier_backend=classifier.name,
    )
    yield
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    """Application factory — useful for tests."""
    settings = get_settings()

    app = FastAPI(
        title="QueueStorm",
        version=__version__,
        description=(
            "QueueStorm — production-grade CRM ticket classifier. "
            "Classifies customer messages into wrong_transfer, "
            "payment_failed, refund_request, phishing, or other; "
            "and routes them to the right department with safe summaries."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    # Middleware (order matters — context outermost)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )

    # Routers
    app.include_router(health_router.router)
    app.include_router(tickets_router.router)

    # Exception handlers — uniform JSON shape.
    @app.exception_handler(QueueStormError)
    async def _domain_error(_: Request, exc: QueueStormError) -> JSONResponse:
        logger.warning(
            "domain.error",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info("request.validation_error", errors=exc.errors())
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "details": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "http_error", "message": exc.detail},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled.exception", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "An unexpected error occurred"},
        )

    return app


app = create_app()

"""
FastAPI application entrypoint for the Travel Planning Agent.
"""
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.config import get_settings
from app.logging_config import configure_logging, get_logger
from app.models.schemas import ErrorResponse

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "app.startup",
        extra={
            "app_env": settings.app_env,
            "llm_provider": settings.llm_provider,
            "mock_apis": settings.use_mock_apis,
            "llm_configured": settings.has_llm_credentials,
        },
    )
    if not settings.has_llm_credentials:
        logger.warning(
            "app.startup.no_llm_credentials",
            extra={"hint": "Set OPENAI_API_KEY or ANTHROPIC_API_KEY to enable the agent."},
        )
    yield
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Travel Planning Agent API",
        description="An AI agent that plans personalized trips: itineraries, "
        "attractions, restaurants, hotels, transportation, and cost estimates.",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request.unhandled_exception", extra={"request_id": request_id})
            raise
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = request_id
        logger.info(
            "request.completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("unhandled_exception", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error="internal_server_error", detail="An unexpected error occurred.").model_dump(),
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["system"])
    def root():
        return {
            "service": "Travel Planning Agent API",
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
        }

    return app


app = create_app()

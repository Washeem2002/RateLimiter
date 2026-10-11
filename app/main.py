from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.api.routers import health, redirect, urls
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.core.logging import configure_logging, get_logger
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.infra.db import dispose_engine
from app.infra.redis import close_redis

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("startup")
    yield
    await close_redis()
    await dispose_engine()
    logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.middleware("http")
    async def metrics_middleware(
        request: Request, call_next: Callable[..., Awaitable[Response]]
    ) -> Response:
        method = request.method
        path = request.url.path

        with REQUEST_LATENCY.labels(method=method, path=path).time():
            response = await call_next(request)

        REQUEST_COUNT.labels(method=method, path=path, status=response.status_code).inc()
        return response

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(urls.router)
    app.include_router(health.router)
    app.include_router(redirect.router)

    return app


app = create_app()

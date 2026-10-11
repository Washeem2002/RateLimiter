from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from app.api.deps import get_client_ip, get_rate_limiter, get_url_service, hash_client_ip
from app.core.config import get_settings
from app.infra.rate_limiter import RateLimiter
from app.schemas.schemas import UrlCreateRequest, UrlMetadataResponse, UrlResponse, UrlStatsResponse
from app.services.url_service import UrlService

router = APIRouter(prefix="/api/v1/urls", tags=["urls"])


@router.post("", response_model=UrlResponse, status_code=status.HTTP_201_CREATED)
async def create_url(
    payload: UrlCreateRequest,
    response: Response,
    service: Annotated[UrlService, Depends(get_url_service)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    ip: Annotated[str, Depends(get_client_ip)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> UrlResponse:
    result = await limiter.check("create", ip, get_settings().rate_limit_create_per_min)
    for key, value in result.headers.items():
        response.headers[key] = value
    return await service.create_url(payload, idempotency_key)


@router.get("/{short_code}", response_model=UrlMetadataResponse)
async def get_url(
    short_code: str,
    service: Annotated[UrlService, Depends(get_url_service)],
) -> UrlMetadataResponse:
    return await service.get_metadata(short_code)


@router.delete("/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_url(
    short_code: str,
    service: Annotated[UrlService, Depends(get_url_service)],
) -> Response:
    await service.delete_url(short_code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{short_code}/stats", response_model=UrlStatsResponse)
async def get_stats(
    short_code: str,
    service: Annotated[UrlService, Depends(get_url_service)],
) -> UrlStatsResponse:
    return await service.get_stats(short_code)

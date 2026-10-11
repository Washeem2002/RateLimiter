from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from app.api.deps import get_rate_limiter, get_url_service, hash_client_ip
from app.core.config import get_settings
from app.core.metrics import REDIRECT_COUNT
from app.infra.rate_limiter import RateLimiter
from app.services.url_service import UrlService

router = APIRouter(tags=["redirect"])


@router.get("/{short_code}")
async def redirect(
    short_code: str,
    request: Request,
    response: Response,
    service: Annotated[UrlService, Depends(get_url_service)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    ip_hash: Annotated[str, Depends(hash_client_ip)],
) -> RedirectResponse:
    result = await limiter.check("redirect", ip_hash, get_settings().rate_limit_redirect_per_min)
    for key, value in result.headers.items():
        response.headers[key] = value

    long_url = await service.resolve(short_code)

    await service.record_click(
        short_code,
        {
            "referrer": request.headers.get("referer"),
            "user_agent": request.headers.get("user-agent"),
            "ip_hash": ip_hash,
        },
    )

    REDIRECT_COUNT.labels(cache="yes").inc()
    return RedirectResponse(url=long_url, status_code=302)

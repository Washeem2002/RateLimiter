from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class UrlCreateRequest(BaseModel):
    long_url: str = Field(..., max_length=2048)
    custom_alias: str | None = Field(default=None, min_length=4, max_length=20)
    expires_at: datetime | None = None

    @field_validator("long_url")
    @classmethod
    def strip_long_url(cls, v: str) -> str:
        return v.strip()


class UrlResponse(BaseModel):
    short_code: str
    short_url: str
    long_url: str
    created_at: datetime
    expires_at: datetime | None = None


class UrlMetadataResponse(BaseModel):
    short_code: str
    long_url: str
    created_at: datetime
    expires_at: datetime | None = None
    is_deleted: bool


class DailyClicks(BaseModel):
    day: str
    count: int


class TopReferrer(BaseModel):
    referrer: str
    count: int


class UrlStatsResponse(BaseModel):
    short_code: str
    total_clicks: int
    clicks_last_7_days: list[DailyClicks]
    top_referrers: list[TopReferrer]


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    database: str
    redis: str

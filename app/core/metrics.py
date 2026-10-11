from prometheus_client import Counter, Gauge, Histogram

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1.0),
)

REDIRECT_COUNT = Counter(
    "url_redirects_total",
    "Total redirects served",
    ["cache"],
)

URLS_CREATED = Counter(
    "urls_created_total",
    "Total short urls created",
)

RATE_LIMITED = Counter(
    "rate_limited_total",
    "Total requests rejected by rate limiter",
    ["endpoint"],
)

CACHE_LOOKUPS = Counter(
    "cache_lookups_total",
    "Cache lookup outcomes",
    ["result"],
)

STREAM_PUBLISH_FAILURES = Counter(
    "stream_publish_failures_total",
    "Failed click event publishes",
)

WORKER_BATCH_SIZE = Histogram(
    "worker_batch_size",
    "Click events inserted per worker batch",
    buckets=(1, 10, 50, 100, 250, 500),
)

WORKER_LAG = Gauge(
    "worker_stream_lag_seconds",
    "Approximate consumer lag of the click stream",
)

DB_POOL_SIZE = Gauge(
    "db_pool_size",
    "Current SQLAlchemy async pool size",
)

DB_POOL_CHECKED_OUT = Gauge(
    "db_pool_checked_out",
    "Current SQLAlchemy async pool checked out connections",
)

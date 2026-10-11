import ipaddress
import re
from urllib.parse import urlparse, urlunparse

from app.core.errors import ValidationAppError

MAX_URL_LENGTH = 2048
ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{4,20}$")

_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata",
    "metadata.google.internal",
}


def _is_private_host(hostname: str) -> bool:
    if hostname in _BLOCKED_HOSTNAMES:
        return True

    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        return False

    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def validate_and_normalize_url(raw_url: str, base_url: str) -> str:
    candidate = raw_url.strip()

    if not candidate:
        raise ValidationAppError("long_url must not be empty")
    if len(candidate) > MAX_URL_LENGTH:
        raise ValidationAppError(f"long_url must be at most {MAX_URL_LENGTH} characters")

    parsed = urlparse(candidate)

    if parsed.scheme not in ("http", "https"):
        raise ValidationAppError("long_url scheme must be http or https")

    hostname = parsed.hostname
    if not hostname:
        raise ValidationAppError("long_url must include a host")

    base_host = urlparse(base_url).hostname or base_url

    if hostname == base_host or hostname.endswith("." + base_host):
        raise ValidationAppError("long_url must not reference this service")

    if _is_private_host(hostname):
        raise ValidationAppError("long_url host is not allowed")

    normalized = parsed._replace(fragment="")
    return urlunparse(normalized)


def validate_alias(alias: str) -> str:
    if not ALIAS_PATTERN.match(alias):
        raise ValidationAppError(
            "custom_alias must be 4 to 20 characters of letters, numbers, underscore or dash"
        )
    return alias

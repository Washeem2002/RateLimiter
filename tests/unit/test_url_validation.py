import pytest

from app.core.errors import ValidationAppError
from app.services.url_validator import validate_alias, validate_and_normalize_url

BASE = "http://testserver"


def test_accepts_valid_https() -> None:
    assert validate_and_normalize_url("https://example.com/a", BASE) == "https://example.com/a"


def test_accepts_valid_http() -> None:
    assert validate_and_normalize_url("http://example.com", BASE) == "http://example.com"


def test_strips_whitespace() -> None:
    assert validate_and_normalize_url("  https://example.com  ", BASE) == "https://example.com"


def test_strips_fragment() -> None:
    assert validate_and_normalize_url("https://example.com/a#frag", BASE) == "https://example.com/a"


def test_rejects_bad_scheme() -> None:
    with pytest.raises(ValidationAppError):
        validate_and_normalize_url("ftp://example.com", BASE)


def test_rejects_empty() -> None:
    with pytest.raises(ValidationAppError):
        validate_and_normalize_url("", BASE)


def test_rejects_too_long() -> None:
    with pytest.raises(ValidationAppError):
        validate_and_normalize_url("https://example.com/" + "a" * 2100, BASE)


def test_rejects_no_host() -> None:
    with pytest.raises(ValidationAppError):
        validate_and_normalize_url("https://", BASE)


def test_rejects_self_reference() -> None:
    with pytest.raises(ValidationAppError):
        validate_and_normalize_url("http://testserver/x", BASE)


@pytest.mark.parametrize(
    "host",
    [
        "http://localhost/x",
        "http://127.0.0.1/x",
        "http://0.0.0.0/x",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/x",
        "http://192.168.1.1/x",
        "http://[::1]/x",
    ],
)
def test_rejects_private_hosts(host: str) -> None:
    with pytest.raises(ValidationAppError):
        validate_and_normalize_url(host, BASE)


def test_alias_valid() -> None:
    assert validate_alias("abcd") == "abcd"
    assert validate_alias("my-alias_123") == "my-alias_123"


@pytest.mark.parametrize("bad", ["abc", "a" * 21, "has space", "has/slash", "emoji😀"])
def test_alias_invalid(bad: str) -> None:
    with pytest.raises(ValidationAppError):
        validate_alias(bad)

import pytest

from app.services.id_generator import ALPHABET, BASE, base62_decode, base62_encode


def test_roundtrip_small_numbers() -> None:
    for n in [0, 1, 61, 62, 63, 100, 1000]:
        assert base62_decode(base62_encode(n)) == n


def test_roundtrip_large_numbers() -> None:
    for n in [1_000_000_000, 9_999_999_999, 123_456_789_012]:
        assert base62_decode(base62_encode(n)) == n


def test_encode_known_values() -> None:
    assert base62_encode(0) == "0"
    assert base62_encode(1) == "1"
    assert base62_encode(61) == "z"
    assert base62_encode(62) == "10"
    assert base62_encode(3843) == "zz"


def test_alphabet_size() -> None:
    assert len(ALPHABET) == BASE == 62


def test_encode_rejects_negative() -> None:
    with pytest.raises(ValueError):
        base62_encode(-1)


def test_decode_rejects_invalid_char() -> None:
    with pytest.raises(ValueError):
        base62_decode("ab-c")

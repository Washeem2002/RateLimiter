ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = 62


def base62_encode(num: int) -> str:
    if num < 0:
        raise ValueError("cannot encode negative numbers")
    if num == 0:
        return ALPHABET[0]

    chars: list[str] = []
    while num > 0:
        num, rem = divmod(num, BASE)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars))


def base62_decode(code: str) -> int:
    num = 0
    for ch in code:
        idx = ALPHABET.find(ch)
        if idx == -1:
            raise ValueError(f"invalid base62 character: {ch}")
        num = num * BASE + idx
    return num


class IdGenerator:
    def __init__(self, redis, repo, offset: int) -> None:
        self._redis = redis
        self._repo = repo
        self._offset = offset

    async def next_code(self) -> tuple[str, int]:
        try:
            counter = await self._redis.incr("url:counter")
            if counter == 1:
                await self._redis.set("url:counter", self._offset + 1)
                counter = self._offset + 1
            value = counter
        except Exception:
            value = await self._repo.sequence_next("url_counter") + self._offset

        return base62_encode(value), value
